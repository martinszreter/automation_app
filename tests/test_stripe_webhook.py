"""The unified Stripe endpoint: POST /stripe/webhook.

One endpoint in the Stripe dashboard serves both ventures, so the routing
decision — which venture an event belongs to — is what these tests pin down,
next to the two flows that decision feeds: the paid order row and the
cancellation row for each venture.

Signatures are stubbed with ``sign_webhook_payload``, the helper the signature
check itself is built from, so no test needs a real Stripe secret.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db.models import PlanStatus, XAutopilotPlan
from app.db.session import get_db
from app.main import app
from app.services import apps_orders, xautopilot_orders
from app.services.stripe_checkout import sign_webhook_payload
from app.services.stripe_events import (
    VENTURE_APPS,
    VENTURE_XAUTOPILOT,
    price_ids,
    venture_for_object,
)

SECRET = "whsec_unified"
XA_PRICE = "price_xa_149_test"
APPS_SETUP_PRICE = "price_apps_setup_test"
APPS_MONTHLY_PRICE = "price_apps_monthly_test"

# No metadata at all: this session is routed purely by its line item Price ids.
APPS_SESSION = {
    "id": "cs_unified_apps",
    "payment_status": "paid",
    "status": "complete",
    "customer_details": {"email": "Wirt@Beiz.CH", "name": "Beiz AG"},
    "customer": "cus_apps",
    "subscription": {"id": "sub_apps"},
    "amount_total": 224300,
    "currency": "chf",
    "line_items": {
        "data": [
            {"price": {"id": APPS_SETUP_PRICE}},
            {"price": {"id": APPS_MONTHLY_PRICE}},
        ]
    },
}

# Stripe does not expand line items into checkout.session.completed by default,
# so this one carries metadata.venture instead.
XA_SESSION = {
    "id": "cs_unified_xa",
    "payment_status": "paid",
    "status": "complete",
    "customer_details": {"email": "buyer@example.com"},
    "customer_email": "buyer@example.com",
    "customer": "cus_xa",
    "payment_intent": "pi_xa",
    "amount_total": 14900,
    "currency": "chf",
    "metadata": {"venture": "x-autopilot", "tier": "149"},
}

APPS_SUBSCRIPTION = {
    "id": "sub_apps",
    "customer": "cus_apps",
    "status": "canceled",
    "canceled_at": 1735689600,
    "items": {"data": [{"price": {"id": APPS_MONTHLY_PRICE}}]},
}

XA_SUBSCRIPTION = {
    "id": "sub_xa",
    "customer": {"id": "cus_xa"},
    "status": "canceled",
    "canceled_at": 1735689600,
    "metadata": {"venture": "x-autopilot", "tier": "990"},
    "items": {"data": [{"price": {"id": XA_PRICE}}]},
}


def _mock_db() -> AsyncMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _client(db: AsyncMock | None = None) -> AsyncClient:
    async def override_get_db():
        yield db if db is not None else _mock_db()

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _prices(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Price ids the routing reads live in the environment, never in code."""
    monkeypatch.setattr(settings, "stripe_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "price_id_xa_149", XA_PRICE)
    monkeypatch.setattr(settings, "price_id_apps_setup", APPS_SETUP_PRICE)
    monkeypatch.setattr(settings, "price_id_apps_monthly", APPS_MONTHLY_PRICE)


def _event(obj: dict, event_type: str, event_id: str = "evt_unified") -> bytes:
    return json.dumps({"id": event_id, "type": event_type, "data": {"object": obj}}).encode("utf-8")


async def _post(client: AsyncClient, payload: bytes, *, signed: bool = True):
    headers = {"content-type": "application/json"}
    if signed:
        headers["stripe-signature"] = sign_webhook_payload(payload, SECRET)
    return await client.post("/stripe/webhook", content=payload, headers=headers)


# --- routing -----------------------------------------------------------------


def test_price_ids_are_read_from_every_shape_stripe_sends() -> None:
    assert price_ids(APPS_SESSION) == [APPS_SETUP_PRICE, APPS_MONTHLY_PRICE]
    assert price_ids(XA_SUBSCRIPTION) == [XA_PRICE]
    assert price_ids({"metadata": {"price_id": XA_PRICE}}) == [XA_PRICE]
    assert price_ids({}) == []


def test_line_item_price_id_decides_the_venture() -> None:
    assert venture_for_object(APPS_SESSION) == VENTURE_APPS
    assert venture_for_object(XA_SUBSCRIPTION) == VENTURE_XAUTOPILOT


def test_metadata_venture_decides_when_line_items_are_absent() -> None:
    assert venture_for_object(XA_SESSION) == VENTURE_XAUTOPILOT
    assert venture_for_object({"metadata": {"venture": "apps"}}) == VENTURE_APPS
    # The older key the two checkout builders already write.
    assert venture_for_object({"metadata": {"product": "apps"}}) == VENTURE_APPS


def test_an_unknown_object_routes_nowhere() -> None:
    assert venture_for_object({"id": "cs_other", "metadata": {"venture": "grokywood"}}) is None
    assert venture_for_object({"line_items": {"data": [{"price": {"id": "price_other"}}]}}) is None


def test_an_unconfigured_price_id_does_not_route(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty PRICE_ID_* must never match the empty string on an object.
    monkeypatch.setattr(settings, "price_id_xa_330", "")
    assert venture_for_object({"items": {"data": [{"price": {"id": ""}}]}}) is None


# --- signature ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_unsigned_request_is_rejected_not_missing() -> None:
    async with _client() as client:
        response = await _post(client, _event(APPS_SESSION, "checkout.session.completed"), signed=False)

    # 400 rather than 404: the endpoint exists, the request is what is wrong.
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_forged_signature_is_rejected() -> None:
    payload = _event(APPS_SESSION, "checkout.session.completed")
    async with _client() as client:
        response = await client.post(
            "/stripe/webhook",
            content=payload,
            headers={"stripe-signature": "t=1,v1=deadbeef"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_body_that_is_not_json_is_rejected() -> None:
    async with _client() as client:
        response = await _post(client, b"not json")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_the_older_endpoints_reject_a_non_object_body_the_same_way() -> None:
    # A JSON array is valid JSON but not an event: 400, never a 500 from .get().
    payload = b"[1, 2, 3]"
    async with _client() as client:
        responses = [
            await client.post(
                path,
                content=payload,
                headers={"stripe-signature": sign_webhook_payload(payload, SECRET)},
            )
            for path in ("/apps/stripe/webhook", "/x-autopilot/stripe/webhook", "/stripe/webhook")
        ]

    assert [response.status_code for response in responses] == [400, 400, 400]


# --- checkout.session.completed ----------------------------------------------


@pytest.mark.asyncio
async def test_apps_checkout_writes_the_apps_order_row(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = AsyncMock()
    monkeypatch.setattr("app.api.apps.post_order_row", sent)

    async with _client() as client:
        response = await _post(client, _event(APPS_SESSION, "checkout.session.completed"))

    assert response.status_code == 200
    assert response.json() == {"received": True, "stored": True}
    row = sent.await_args.args[0]
    assert row["table"] == apps_orders.ORDER_TABLE
    assert row["kind"] == apps_orders.ROW_PAID
    assert row["session_id"] == "cs_unified_apps"
    assert row["email"] == "wirt@beiz.ch"


@pytest.mark.asyncio
async def test_xautopilot_checkout_writes_its_row_and_activates_the_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "n8n_xautopilot_order_url", "https://n8n.invalid/xa")
    sent = AsyncMock()
    monkeypatch.setattr("app.api.x_autopilot.post_order_row", sent)
    db = _mock_db()

    async with _client(db) as client:
        response = await _post(client, _event(XA_SESSION, "checkout.session.completed"))

    assert response.status_code == 200
    assert response.json() == {"received": True, "status": "active", "stored": True}
    row = sent.await_args.args[0]
    assert row["table"] == xautopilot_orders.ORDER_TABLE
    assert row["session_id"] == "cs_unified_xa"
    assert row["tier"] == "149"
    stored = db.add.call_args.args[0]
    assert stored.email == "buyer@example.com"
    assert stored.status == PlanStatus.ACTIVE


@pytest.mark.asyncio
async def test_apps_row_that_cannot_be_stored_asks_stripe_to_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failing = AsyncMock(side_effect=apps_orders.AppsOrderError("n8n responded 500"))
    monkeypatch.setattr("app.api.apps.post_order_row", failing)

    async with _client() as client:
        response = await _post(client, _event(APPS_SESSION, "checkout.session.completed"))

    assert response.status_code == 503


# --- customer.subscription.deleted -------------------------------------------


@pytest.mark.asyncio
async def test_apps_subscription_deleted_writes_a_cancellation_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = AsyncMock()
    monkeypatch.setattr("app.api.apps.post_order_row", sent)

    async with _client() as client:
        response = await _post(client, _event(APPS_SUBSCRIPTION, "customer.subscription.deleted"))

    assert response.status_code == 200
    assert response.json() == {"received": True, "stored": True}
    row = sent.await_args.args[0]
    assert row["table"] == apps_orders.ORDER_TABLE
    assert row["kind"] == apps_orders.ROW_CANCELED
    assert row["subscription_id"] == "sub_apps"
    assert row["price_id"] == APPS_MONTHLY_PRICE
    assert row["canceled_at"] == "2025-01-01T00:00:00+00:00"


@pytest.mark.asyncio
async def test_xautopilot_subscription_deleted_writes_a_cancellation_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = AsyncMock()
    monkeypatch.setattr("app.api.x_autopilot.post_order_row", sent)

    async with _client() as client:
        response = await _post(client, _event(XA_SUBSCRIPTION, "customer.subscription.deleted"))

    assert response.status_code == 200
    assert response.json() == {"received": True, "stored": True}
    row = sent.await_args.args[0]
    assert row["table"] == xautopilot_orders.ORDER_TABLE
    assert row["kind"] == xautopilot_orders.ROW_CANCELED
    assert row["subscription_id"] == "sub_xa"
    assert row["customer_id"] == "cus_xa"
    assert row["tier"] == "990"
    assert row["price_id"] == XA_PRICE


@pytest.mark.asyncio
async def test_cancellation_is_acknowledged_when_there_is_nowhere_to_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unset = AsyncMock(side_effect=xautopilot_orders.XAOrderNotConfigured("unset"))
    monkeypatch.setattr("app.api.x_autopilot.post_order_row", unset)

    async with _client() as client:
        response = await _post(client, _event(XA_SUBSCRIPTION, "customer.subscription.deleted"))

    # Nothing to retry into: a 5xx here would make Stripe hammer the endpoint.
    assert response.status_code == 200
    assert response.json() == {"received": True, "stored": False}


@pytest.mark.asyncio
async def test_cancellation_that_cannot_be_stored_asks_stripe_to_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failing = AsyncMock(side_effect=xautopilot_orders.XAOrderError("n8n responded 500"))
    monkeypatch.setattr("app.api.x_autopilot.post_order_row", failing)

    async with _client() as client:
        response = await _post(client, _event(XA_SUBSCRIPTION, "customer.subscription.deleted"))

    assert response.status_code == 503


# --- checkout.session.async_payment_succeeded --------------------------------


@pytest.mark.asyncio
async def test_a_bank_transfer_activates_the_plan_when_the_payment_lands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """checkout.session.completed arrives unpaid for a bank transfer; the plan
    goes active only on async_payment_succeeded, which this endpoint must
    therefore dispatch like a completed session."""
    monkeypatch.setattr("app.api.x_autopilot.post_order_row", AsyncMock())
    db = _mock_db()
    paid_later = {**XA_SESSION, "payment_status": "paid"}

    async with _client(db) as client:
        response = await _post(client, _event(paid_later, "checkout.session.async_payment_succeeded"))

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert db.add.call_args.args[0].status == PlanStatus.ACTIVE


@pytest.mark.asyncio
async def test_an_apps_bank_transfer_rewrites_the_paid_row(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = AsyncMock()
    monkeypatch.setattr("app.api.apps.post_order_row", sent)

    async with _client() as client:
        response = await _post(client, _event(APPS_SESSION, "checkout.session.async_payment_succeeded"))

    assert response.status_code == 200
    # Keyed by session id, so this overwrites the "unpaid" row from the first event.
    assert sent.await_args.args[0]["payment_status"] == "paid"


# --- refunds -----------------------------------------------------------------


def _plan() -> XAutopilotPlan:
    return XAutopilotPlan(
        email="buyer@example.com",
        status=PlanStatus.ACTIVE,
        stripe_checkout_session_id="cs_unified_xa",
        stripe_payment_intent_id="pi_xa",
        amount_cents=100,
        currency="chf",
    )


@pytest.mark.asyncio
async def test_a_refund_marks_the_plan_refunded_on_the_shared_endpoint() -> None:
    plan = _plan()
    db = _mock_db()
    db.execute.return_value.scalar_one_or_none.return_value = plan
    charge = {"id": "ch_xa", "payment_intent": "pi_xa", "refunded": True}

    async with _client(db) as client:
        response = await _post(client, _event(charge, "charge.refunded"))

    assert response.status_code == 200
    assert response.json() == {"received": True, "status": "refunded", "plan": True}
    assert plan.status == PlanStatus.REFUNDED


@pytest.mark.asyncio
async def test_a_refund_for_an_unknown_payment_is_acknowledged() -> None:
    # No plan for this payment intent (an /apps refund, say): nothing to mark.
    async with _client() as client:
        response = await _post(client, _event({"payment_intent": {"id": "pi_apps"}}, "refund.created"))

    assert response.status_code == 200
    assert response.json() == {"received": True, "status": "refunded", "plan": False}


# --- everything else ---------------------------------------------------------


@pytest.mark.asyncio
async def test_an_event_for_neither_venture_is_acknowledged_and_stored_nowhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apps_sent = AsyncMock()
    xa_sent = AsyncMock()
    monkeypatch.setattr("app.api.apps.post_order_row", apps_sent)
    monkeypatch.setattr("app.api.x_autopilot.post_order_row", xa_sent)
    session = {"id": "cs_other", "metadata": {"venture": "grokywood"}}

    async with _client() as client:
        response = await _post(client, _event(session, "checkout.session.completed"))

    assert response.status_code == 200
    assert response.json() == {"received": True, "ignored": True}
    apps_sent.assert_not_awaited()
    xa_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_unhandled_event_type_is_acknowledged() -> None:
    async with _client() as client:
        response = await _post(client, _event(APPS_SESSION, "invoice.paid"))

    assert response.status_code == 200
    assert response.json() == {"received": True, "ignored": True}


# --- the older per-product endpoints ------------------------------------------


@pytest.mark.asyncio
async def test_the_apps_endpoint_still_stores_its_row(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = AsyncMock()
    monkeypatch.setattr("app.api.apps.post_order_row", sent)
    session = {**APPS_SESSION, "metadata": {"product": "apps"}}
    payload = _event(session, "checkout.session.completed")

    async with _client() as client:
        response = await client.post(
            "/apps/stripe/webhook",
            content=payload,
            headers={"stripe-signature": sign_webhook_payload(payload, SECRET)},
        )

    assert response.status_code == 200
    assert response.json() == {"received": True, "stored": True}
    assert sent.await_args.args[0]["session_id"] == "cs_unified_apps"


@pytest.mark.asyncio
async def test_the_xautopilot_endpoint_still_activates_the_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = AsyncMock()
    monkeypatch.setattr("app.api.x_autopilot.post_order_row", sent)
    payload = _event(XA_SESSION, "checkout.session.completed")
    db = _mock_db()

    async with _client(db) as client:
        response = await client.post(
            "/x-autopilot/stripe/webhook",
            content=payload,
            headers={"stripe-signature": sign_webhook_payload(payload, SECRET)},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert db.add.call_args.args[0].status == PlanStatus.ACTIVE
