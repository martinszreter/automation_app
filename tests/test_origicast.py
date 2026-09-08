"""/origicast — the 21+ door: gate, door, CHF 1 test checkout, flag-hidden
offers, imprint on every page, webhook routing, /healthz."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.origicast import (
    VENTURE,
    build_checkout_session_payload,
    checkout_urls,
    handle_checkout_completed,
)
from app.core.config import settings
from app.main import app
from app.services.hq_mail import HQMailError, HQMailNotConfigured
from app.services.stripe_checkout import sign_webhook_payload
from app.services.stripe_events import VENTURE_ORIGICAST, venture_for_object
from app.templates.messages import origicast_de as t

PAID_SESSION = {
    "id": "cs_test_origicast_1",
    "payment_status": "paid",
    "status": "complete",
    "amount_total": 100,
    "currency": "chf",
    "customer_details": {"email": "Gast@Example.CH"},
    "metadata": {"venture": "origicast"},
}


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _pass_gate(client: AsyncClient) -> None:
    response = await client.post("/origicast/gate", data={"answer": "yes"})
    assert response.status_code == 303
    assert response.headers["location"] == "/origicast/door"


# --- gate -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_landing_is_the_age_gate_in_german_with_imprint() -> None:
    async with _client() as client:
        response = await client.get("/origicast/")
    assert response.status_code == 200
    assert t.GATE_HEADLINE in response.text
    assert t.GATE_YES in response.text and t.GATE_NO in response.text
    assert 'lang="de"' in response.text
    assert "STARTEND GmbH" in response.text and "CHE-223.488.613" in response.text
    for href in ("/impressum/", "/agb/", "/datenschutz/"):
        assert f'href="{href}"' in response.text
    assert "fonts.googleapis" not in response.text
    assert "ß" not in response.text  # de-CH


@pytest.mark.asyncio
async def test_door_and_checkout_bounce_to_the_gate_until_it_is_passed() -> None:
    async with _client() as client:
        door = await client.get("/origicast/door")
        checkout = await client.post("/origicast/checkout")
    assert door.status_code == 303 and door.headers["location"] == "/origicast/"
    assert checkout.status_code == 303 and checkout.headers["location"] == "/origicast/"


@pytest.mark.asyncio
async def test_under_21_is_sent_to_the_leave_page_and_stays_locked_out() -> None:
    async with _client() as client:
        response = await client.post("/origicast/gate", data={"answer": "no"})
        assert response.status_code == 303 and response.headers["location"] == "/origicast/leave"
        leave = await client.get("/origicast/leave")
        door = await client.get("/origicast/door")
    assert t.LEAVE_HEADLINE in leave.text
    assert door.status_code == 303


@pytest.mark.asyncio
async def test_yes_opens_the_door_and_the_gate_remembers() -> None:
    async with _client() as client:
        await _pass_gate(client)
        door = await client.get("/origicast/door")
        again = await client.get("/origicast/")
    assert door.status_code == 200
    assert t.DOOR_HEADLINE in door.text
    assert t.TEST_BUTTON in door.text
    assert 'action="/origicast/checkout"' in door.text
    assert door.headers["cache-control"] == "no-store"
    # Once confirmed, the landing page goes straight to the door.
    assert again.status_code == 303 and again.headers["location"] == "/origicast/door"


# --- ORIGICAST_LIVE flag ------------------------------------------------------------


@pytest.mark.asyncio
async def test_offers_are_absent_until_origicast_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "origicast_live", False)
    async with _client() as client:
        await _pass_gate(client)
        door = await client.get("/origicast/door")
        season = await client.get("/origicast/season")
    for word in ("Season", "Hour", "Keep", "offer-season", "/origicast/hour"):
        assert word not in door.text
    assert season.status_code == 404


@pytest.mark.asyncio
async def test_offers_render_when_origicast_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "origicast_live", True)
    async with _client() as client:
        await _pass_gate(client)
        door = await client.get("/origicast/door")
        keep = await client.get("/origicast/keep")
    for anchor in ("offer-season", "offer-hour", "offer-keep"):
        assert f'id="{anchor}"' in door.text
    assert keep.status_code == 303 and keep.headers["location"] == "/origicast/door#offer-keep"


# --- CHF 1 checkout ---------------------------------------------------------------


def test_checkout_payload_is_a_one_time_chf_1_payment_tagged_for_routing() -> None:
    payload = build_checkout_session_payload("https://www.startend.ch/", 100)
    assert payload["mode"] == "payment"
    assert payload["line_items[0][price_data][currency]"] == "chf"
    assert payload["line_items[0][price_data][unit_amount]"] == "100"
    assert payload["line_items[0][price_data][product_data][name]"] == t.TEST_PRODUCT_NAME
    assert payload["metadata[venture]"] == VENTURE == "origicast"
    assert payload["locale"] == "de"
    assert payload["success_url"] == "https://www.startend.ch/origicast/success?session_id={CHECKOUT_SESSION_ID}"
    assert payload["cancel_url"] == "https://www.startend.ch/origicast/door"
    assert checkout_urls("https://x.test")[1] == "https://x.test/origicast/door"


def test_checkout_payload_refuses_a_zero_amount() -> None:
    with pytest.raises(ValueError):
        build_checkout_session_payload("https://x.test", 0)


@pytest.mark.asyncio
async def test_checkout_redirects_to_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    captured: dict = {}

    async def fake_stripe_request(method: str, path: str, data: dict | None = None) -> dict:
        captured.update({"method": method, "path": path, "data": data})
        return {"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1"}

    with patch("app.api.origicast.stripe_request", fake_stripe_request):
        async with _client() as client:
            await _pass_gate(client)
            response = await client.post("/origicast/checkout")
    assert response.status_code == 303
    assert response.headers["location"] == "https://checkout.stripe.com/c/pay/cs_test_1"
    assert captured["path"] == "/checkout/sessions"
    assert captured["data"]["line_items[0][price_data][unit_amount]"] == "100"


@pytest.mark.asyncio
async def test_checkout_without_stripe_key_returns_to_the_door_with_a_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    async with _client() as client:
        await _pass_gate(client)
        response = await client.post("/origicast/checkout")
        door = await client.get(response.headers["location"])
    assert response.status_code == 303
    assert response.headers["location"] == "/origicast/door?error=unavailable"
    assert t.TEST_UNAVAILABLE in door.text


@pytest.mark.asyncio
async def test_success_page_never_calls_stripe_and_shows_the_reference() -> None:
    with patch("app.api.origicast.stripe_request", AsyncMock(side_effect=AssertionError("no"))):
        async with _client() as client:
            response = await client.get("/origicast/success?session_id=cs_test_abc")
    assert response.status_code == 200
    assert t.SUCCESS_HEADLINE in response.text
    assert 'id="reference">cs_test_abc<' in response.text


# --- webhook ---------------------------------------------------------------------


def test_origicast_metadata_routes_to_its_venture() -> None:
    assert venture_for_object(PAID_SESSION) == VENTURE_ORIGICAST
    assert venture_for_object({"metadata": {"product": "origicast"}}) == VENTURE_ORIGICAST


@pytest.mark.asyncio
async def test_paid_test_is_mailed_to_hq_for_the_refund() -> None:
    mail = AsyncMock()
    with patch("app.api.origicast.send_hq_mail", mail):
        response = await handle_checkout_completed(PAID_SESSION)
    assert response.status_code == 200
    subject, body = mail.await_args.args
    assert subject == t.HQ_MAIL_SUBJECT
    assert "cs_test_origicast_1" in body and "gast@example.ch" in body and "1.00 CHF" in body


@pytest.mark.asyncio
async def test_paid_test_without_hq_mail_is_acknowledged_not_retried() -> None:
    with patch("app.api.origicast.send_hq_mail", AsyncMock(side_effect=HQMailNotConfigured("x"))):
        response = await handle_checkout_completed(PAID_SESSION)
    assert response.status_code == 200
    assert json.loads(response.body) == {"received": True, "mailed": False}


@pytest.mark.asyncio
async def test_hq_mail_outage_asks_stripe_to_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    payload = json.dumps({"type": "checkout.session.completed", "data": {"object": PAID_SESSION}}).encode()
    with patch("app.api.origicast.send_hq_mail", AsyncMock(side_effect=HQMailError("down"))):
        async with _client() as client:
            response = await client.post(
                "/stripe/webhook",
                content=payload,
                headers={"stripe-signature": sign_webhook_payload(payload, "whsec_test")},
            )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_unified_webhook_dispatches_origicast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    payload = json.dumps({"type": "checkout.session.completed", "data": {"object": PAID_SESSION}}).encode()
    mail = AsyncMock()
    with patch("app.api.origicast.send_hq_mail", mail):
        async with _client() as client:
            response = await client.post(
                "/stripe/webhook",
                content=payload,
                headers={"stripe-signature": sign_webhook_payload(payload, "whsec_test")},
            )
    assert response.status_code == 200
    assert json.loads(response.text) == {"received": True, "mailed": True}
    mail.assert_awaited_once()


# --- legal pages + ops ----------------------------------------------------------


@pytest.mark.asyncio
async def test_agb_and_datenschutz_pages_exist_in_de_ch() -> None:
    async with _client() as client:
        agb = await client.get("/agb/")
        privacy = await client.get("/datenschutz/")
    assert agb.status_code == 200 and "Allgemeine Geschäftsbedingungen" in agb.text
    assert privacy.status_code == 200 and "Datenschutzerklärung" in privacy.text
    assert "ß" not in agb.text and "ß" not in privacy.text
    assert "CHE-223.488.613" in agb.text


@pytest.mark.asyncio
async def test_healthz_answers_without_the_database() -> None:
    async with _client() as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
