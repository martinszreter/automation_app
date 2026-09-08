"""Stripe webhook: signature, confirmation mail, lead row, alerts on failure."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from zorbeck_app.config import settings
from zorbeck_app.mail import MailError, MailNotConfigured
from zorbeck_app.main import app
from zorbeck_app.stripe_api import StripeSignatureError, sign_webhook_payload, verify_stripe_signature

SECRET = "test-webhook-secret"
SESSION = {
    "id": "cs_test_1",
    "payment_status": "paid",
    "status": "complete",
    "amount_total": 100,
    "currency": "chf",
    "customer_details": {"email": "Anna@Beispiel.ch"},
    "metadata": {"venture": "zorbeck", "city": "Zug", "budget_min": "", "budget_max": "1200000"},
}


def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def event(session: dict, event_type: str = "checkout.session.completed") -> bytes:
    return json.dumps({"id": "evt_1", "type": event_type, "data": {"object": session}}).encode()


async def post(payload: bytes, secret: str = SECRET):
    # c.request rather than c.post: a test below patches httpx.AsyncClient.post
    # to capture the app's outbound lead row, and must not catch this call.
    async with client() as c:
        return await c.request(
            "POST",
            "/stripe/webhook",
            content=payload,
            headers={"stripe-signature": sign_webhook_payload(payload, secret), "content-type": "application/json"},
        )


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "signup_webhook_url", "")
    monkeypatch.setattr(settings, "alert_webhook_url", "")


# --- signature -------------------------------------------------------------------


def test_signature_round_trip() -> None:
    payload = b'{"ok":1}'
    verify_stripe_signature(payload, sign_webhook_payload(payload, SECRET), SECRET)


@pytest.mark.parametrize(
    "header",
    ["", "t=1,v1=abc", "garbage", "v1=onlysig"],
)
def test_malformed_or_wrong_signatures_are_rejected(header: str) -> None:
    with pytest.raises(StripeSignatureError):
        verify_stripe_signature(b"x", header, SECRET)


def test_old_signatures_are_rejected() -> None:
    payload = b"x"
    with pytest.raises(StripeSignatureError, match="tolerance"):
        verify_stripe_signature(payload, sign_webhook_payload(payload, SECRET, timestamp=1), SECRET)


def test_missing_secret_never_verifies() -> None:
    with pytest.raises(StripeSignatureError):
        verify_stripe_signature(b"x", sign_webhook_payload(b"x", ""), "")


# --- endpoint --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forged_signature_is_400_and_sends_nothing() -> None:
    mail = AsyncMock()
    with patch("zorbeck_app.main.send_mail", mail):
        response = await post(event(SESSION), secret="wrong")
    assert response.status_code == 400
    mail.assert_not_awaited()


@pytest.mark.asyncio
async def test_completed_checkout_mails_the_buyer_and_stores_the_lead(monkeypatch) -> None:
    monkeypatch.setattr(settings, "signup_webhook_url", "https://n8n.invalid/leads")
    mail = AsyncMock()
    lead = AsyncMock(return_value=type("R", (), {"status_code": 200, "raise_for_status": lambda self: None})())
    with patch("zorbeck_app.main.send_mail", mail), patch("httpx.AsyncClient.post", lead):
        response = await post(event(SESSION))
    assert response.status_code == 200
    assert response.json() == {"received": True, "mailed": True}

    subject, body, to = mail.await_args.args
    assert to == "anna@beispiel.ch"
    assert "Zug" in subject
    assert "CHF 1" in body and "bis CHF 1'200'000" in body
    assert "http://test/impressum" in body

    row = lead.await_args.kwargs["json"]
    assert row["status"] == "paid"
    assert row["session_id"] == "cs_test_1"
    assert row["amount_cents"] == 100
    assert row["city"] == "Zug"


@pytest.mark.asyncio
async def test_mail_failure_alerts_and_asks_stripe_to_retry() -> None:
    alert = AsyncMock(return_value=True)
    with (
        patch("zorbeck_app.main.send_mail", AsyncMock(side_effect=MailError("lane down"))),
        patch("zorbeck_app.main.send_alert", alert),
    ):
        response = await post(event(SESSION))
    assert response.status_code == 503
    assert alert.await_args.args[0] == "webhook.mail"


@pytest.mark.asyncio
async def test_unconfigured_mail_is_alerted_but_acknowledged() -> None:
    alert = AsyncMock(return_value=True)
    with (
        patch("zorbeck_app.main.send_mail", AsyncMock(side_effect=MailNotConfigured("unset"))),
        patch("zorbeck_app.main.send_alert", alert),
    ):
        response = await post(event(SESSION))
    assert response.status_code == 200
    assert response.json() == {"received": True, "mailed": False}
    assert "HQ_MAIL_WEBHOOK_URL" in alert.await_args.args[1]


@pytest.mark.asyncio
async def test_other_events_and_unpaid_sessions_are_acknowledged_silently() -> None:
    mail = AsyncMock()
    with patch("zorbeck_app.main.send_mail", mail):
        other = await post(event(SESSION, "charge.refunded"))
        unpaid = await post(event({**SESSION, "payment_status": "unpaid", "status": "open"}))
    assert other.status_code == 200 and other.json() == {"received": True}
    assert unpaid.status_code == 200 and unpaid.json() == {"received": True, "ignored": True}
    mail.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_json_with_a_valid_signature_is_400() -> None:
    response = await post(b"not json")
    assert response.status_code == 400
