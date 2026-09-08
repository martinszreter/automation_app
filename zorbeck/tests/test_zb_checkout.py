"""Checkout: form -> Stripe Checkout Session -> success page."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from zorbeck_app.config import settings
from zorbeck_app.main import app
from zorbeck_app.stripe_api import StripeError, build_checkout_payload, checkout_urls

FORM = {"email": "anna@beispiel.ch", "city": "Zug", "budget_min": "", "budget_max": "1'200'000"}
PAID_SESSION = {
    "id": "cs_test_1",
    "payment_status": "paid",
    "status": "complete",
    "amount_total": 100,
    "currency": "chf",
    "customer_details": {"email": "anna@beispiel.ch"},
    "metadata": {"venture": "zorbeck", "city": "Zug", "budget_min": "", "budget_max": "1200000"},
}


def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def quiet_leads(monkeypatch):
    monkeypatch.setattr(settings, "signup_webhook_url", "")
    monkeypatch.setattr(settings, "alert_webhook_url", "")


# --- payload ---------------------------------------------------------------------


def test_checkout_urls_return_to_the_success_page() -> None:
    success, cancel = checkout_urls("https://zorbeck.example/")
    assert success == "https://zorbeck.example/danke?session_id={CHECKOUT_SESSION_ID}"
    assert cancel == "https://zorbeck.example/?abgebrochen=1"


def test_payload_is_one_time_chf_in_german_with_the_intake_in_metadata(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_price_id", "")
    monkeypatch.setattr(settings, "price_cents", 4900)
    payload = build_checkout_payload("https://zorbeck.example", "anna@beispiel.ch", {"city": "Zug", "budget_max": "1200000"})
    assert payload["mode"] == "payment"
    assert payload["locale"] == "de"
    assert payload["customer_email"] == "anna@beispiel.ch"
    assert payload["metadata[venture]"] == "zorbeck"
    assert payload["metadata[city]"] == "Zug"
    assert payload["metadata[budget_max]"] == "1200000"
    assert payload["line_items[0][price_data][currency]"] == "chf"
    assert payload["line_items[0][price_data][unit_amount]"] == "4900"
    assert payload["line_items[0][quantity]"] == "1"
    assert "recurring" not in str(payload)


def test_a_price_id_replaces_the_inline_amount(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_price_id", "price_from_env")
    payload = build_checkout_payload("https://zorbeck.example", "a@b.ch", {})
    assert payload["line_items[0][price]"] == "price_from_env"
    assert not [key for key in payload if "price_data" in key]


# --- POST /checkout ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_bad_input_re_renders_the_form_with_what_was_typed() -> None:
    async with client() as c:
        response = await c.post("/checkout", data={**FORM, "email": "nope"})
    assert response.status_code == 200  # a typo is not a page error (no console error)
    assert 'data-testid="form-error"' in response.text
    assert "E-Mail-Adresse" in response.text
    assert 'value="Zug"' in response.text


@pytest.mark.asyncio
async def test_checkout_without_stripe_key_is_unavailable_not_a_crash(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    async with client() as c:
        response = await c.post("/checkout", data=FORM)
    assert response.status_code == 503
    assert "nicht möglich" in response.text


@pytest.mark.asyncio
async def test_checkout_redirects_to_stripe(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "k")
    session = {"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"}
    create = AsyncMock(return_value=session)
    with patch("zorbeck_app.main.create_checkout_session", create):
        async with client() as c:
            response = await c.post("/checkout", data=FORM, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == session["url"]
    base_url, email, metadata = create.await_args.args
    assert base_url == "http://test"
    assert email == "anna@beispiel.ch"
    assert metadata == {"city": "Zug", "budget_min": "", "budget_max": "1200000"}


@pytest.mark.asyncio
async def test_checkout_honours_the_forwarded_host(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "k")
    monkeypatch.setattr(settings, "public_base_url", "")
    create = AsyncMock(return_value={"id": "cs_1", "url": "https://checkout.stripe.com/x"})
    with patch("zorbeck_app.main.create_checkout_session", create):
        async with client() as c:
            await c.post(
                "/checkout",
                data=FORM,
                headers={"x-forwarded-proto": "https", "x-forwarded-host": "zorbeck.example"},
                follow_redirects=False,
            )
    assert create.await_args.args[0] == "https://zorbeck.example"


@pytest.mark.asyncio
async def test_stripe_failure_is_alerted_and_told_to_the_buyer(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "k")
    alert = AsyncMock(return_value=True)
    with (
        patch("zorbeck_app.main.create_checkout_session", AsyncMock(side_effect=StripeError("Stripe API 500"))),
        patch("zorbeck_app.main.send_alert", alert),
    ):
        async with client() as c:
            response = await c.post("/checkout", data=FORM)
    assert response.status_code == 502
    assert "nochmals" in response.text
    assert alert.await_args.args[0] == "checkout"


@pytest.mark.asyncio
async def test_checkout_accepts_json_too(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "k")
    create = AsyncMock(return_value={"id": "cs_1", "url": "https://checkout.stripe.com/x"})
    with patch("zorbeck_app.main.create_checkout_session", create):
        async with client() as c:
            response = await c.post("/checkout", json=FORM, follow_redirects=False)
    assert response.status_code == 303


# --- GET /danke -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_page_without_a_session_is_a_soft_404() -> None:
    async with client() as c:
        response = await c.get("/danke")
    assert response.status_code == 404
    assert 'data-testid="unknown"' in response.text
    assert "STARTEND GmbH" in response.text


@pytest.mark.asyncio
async def test_success_page_shows_the_paid_intake(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "k")
    with patch("zorbeck_app.main.retrieve_checkout_session", AsyncMock(return_value=PAID_SESSION)):
        async with client() as c:
            response = await c.get("/danke?session_id=cs_test_1")
    assert response.status_code == 200
    assert 'data-testid="success-title"' in response.text
    assert ">Zug<" in response.text
    # Jinja escapes the apostrophe; the browser shows CHF 1'200'000.
    assert "bis CHF 1&#39;200&#39;000" in response.text
    assert ">CHF 1<" in response.text
    assert "anna@beispiel.ch" in response.text


@pytest.mark.asyncio
async def test_unpaid_session_asks_to_reload(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "k")
    unpaid = {**PAID_SESSION, "payment_status": "unpaid", "status": "open"}
    with patch("zorbeck_app.main.retrieve_checkout_session", AsyncMock(return_value=unpaid)):
        async with client() as c:
            response = await c.get("/danke?session_id=cs_test_1")
    assert response.status_code == 202
    assert 'data-testid="pending"' in response.text


@pytest.mark.asyncio
async def test_stripe_outage_on_the_success_page_degrades_to_unknown(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "k")
    with patch("zorbeck_app.main.retrieve_checkout_session", AsyncMock(side_effect=StripeError("boom"))):
        async with client() as c:
            response = await c.get("/danke?session_id=cs_test_1")
    assert response.status_code == 404
    assert "info@startend.ch" in response.text
