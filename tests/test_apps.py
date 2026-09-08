"""Tests for /apps — the Stripe door for the WhatsApp reservation setup."""

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services.apps_demo import demo_booking, demo_mail
from app.services.hq_mail import HQMailError, HQMailNotConfigured
from app.services.apps_checkout import (
    AppsPricesNotConfigured,
    build_checkout_session_payload,
    checkout_urls,
    create_apps_checkout_session,
)
from app.services.apps_orders import (
    AppsOrderError,
    AppsOrderNotConfigured,
    DetailsInvalid,
    details_row,
    normalize_swiss_phone,
    paid_row_from_session,
    post_order_row,
)
from app.services.stripe_checkout import sign_webhook_payload

SETUP_PRICE = "price_setup_1990"
MONTHLY_PRICE = "price_monthly_249"

COMPLETED_SESSION = {
    "id": "cs_test_apps_1",
    "payment_status": "paid",
    "status": "complete",
    "customer_details": {"email": "Wirt@Beiz.CH", "name": "Beiz AG"},
    "customer": "cus_apps",
    "subscription": {"id": "sub_apps"},
    "amount_total": 224300,
    "currency": "chf",
    "metadata": {"product": "apps"},
}


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _event(session: dict, event_type: str = "checkout.session.completed") -> bytes:
    return json.dumps({"type": event_type, "data": {"object": session}}).encode("utf-8")


# --- session builder ---------------------------------------------------------


def test_checkout_urls_point_back_at_the_success_form() -> None:
    success, cancel = checkout_urls("https://www.startend.ch/")
    assert success == "https://www.startend.ch/apps/success?session_id={CHECKOUT_SESSION_ID}"
    assert cancel == "https://www.startend.ch/apps/"


def test_session_carries_setup_fee_and_subscription_in_one_session() -> None:
    payload = build_checkout_session_payload("https://www.startend.ch", SETUP_PRICE, MONTHLY_PRICE)

    # A recurring line item forces subscription mode; the one-time setup fee
    # rides along on the first invoice.
    assert payload["mode"] == "subscription"
    assert payload["line_items[0][price]"] == SETUP_PRICE
    assert payload["line_items[0][quantity]"] == "1"
    assert payload["line_items[1][price]"] == MONTHLY_PRICE
    assert payload["line_items[1][quantity]"] == "1"


def test_session_is_tagged_so_the_webhook_can_tell_products_apart() -> None:
    payload = build_checkout_session_payload("https://www.startend.ch", SETUP_PRICE, MONTHLY_PRICE)
    assert payload["metadata[product]"] == "apps"
    assert payload["subscription_data[metadata][product]"] == "apps"
    assert payload["client_reference_id"] == "apps"
    assert payload["locale"] == "de"


def test_no_amount_is_hard_coded_in_the_payload() -> None:
    payload = build_checkout_session_payload("https://www.startend.ch", SETUP_PRICE, MONTHLY_PRICE)
    assert not [key for key in payload if "price_data" in key or "unit_amount" in key]


def test_prices_are_trimmed_and_read_from_the_environment() -> None:
    payload = build_checkout_session_payload("https://x.test", f"  {SETUP_PRICE} ", f"{MONTHLY_PRICE}\n")
    assert payload["line_items[0][price]"] == SETUP_PRICE
    assert payload["line_items[1][price]"] == MONTHLY_PRICE


@pytest.mark.parametrize(
    "setup, monthly, expected",
    [
        ("", MONTHLY_PRICE, "PRICE_ID_APPS_SETUP"),
        (SETUP_PRICE, "   ", "PRICE_ID_APPS_MONTHLY"),
        ("", "", "PRICE_ID_APPS_SETUP and PRICE_ID_APPS_MONTHLY"),
    ],
)
def test_missing_price_ids_are_named_in_the_error(setup: str, monthly: str, expected: str) -> None:
    with pytest.raises(AppsPricesNotConfigured, match=expected):
        build_checkout_session_payload("https://x.test", setup, monthly)


@pytest.mark.asyncio
async def test_create_session_posts_the_built_payload_to_stripe(monkeypatch) -> None:
    monkeypatch.setattr(settings, "price_id_apps_setup", SETUP_PRICE)
    monkeypatch.setattr(settings, "price_id_apps_monthly", MONTHLY_PRICE)
    request = AsyncMock(return_value={"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"})

    with patch("app.services.apps_checkout.stripe_request", request):
        session = await create_apps_checkout_session("https://www.startend.ch")

    assert session["url"].startswith("https://checkout.stripe.com/")
    method, path, payload = request.await_args.args
    assert (method, path) == ("POST", "/checkout/sessions")
    assert payload["line_items[1][price]"] == MONTHLY_PRICE


# --- Swiss phone numbers -----------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "079 938 03 72",
        "+41 79 938 03 72",
        "0041 79 938 03 72",
        "+41799380372",
        "079/938.03.72",
        "079-938-03-72",
        "79 938 03 72",
    ],
)
def test_swiss_numbers_normalize_to_e164(raw: str) -> None:
    assert normalize_swiss_phone(raw) == "+41799380372"


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "12345", "+49 30 123456", "079 938 03 7", "0790938037200", "abc"],
)
def test_non_swiss_numbers_are_refused_not_guessed(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_swiss_phone(raw)


# --- order rows --------------------------------------------------------------


def test_paid_row_carries_what_the_order_needs() -> None:
    row = paid_row_from_session(COMPLETED_SESSION)
    assert row["table"] == "apps_orders"
    assert row["kind"] == "paid"
    assert row["session_id"] == "cs_test_apps_1"
    assert row["email"] == "wirt@beiz.ch"
    assert row["customer_id"] == "cus_apps"
    # Stripe may expand the subscription into an object.
    assert row["subscription_id"] == "sub_apps"
    assert row["amount_total_cents"] == 224300
    assert row["currency"] == "chf"
    assert row["created_at"]


def test_paid_row_needs_a_session_id() -> None:
    with pytest.raises(ValueError, match="no id"):
        paid_row_from_session({"payment_status": "paid"})


def test_details_row_normalizes_and_trims() -> None:
    row = details_row("cs_test_apps_1", "  Beiz am See  ", "079 938 03 72", " Di–Sa 18:00–23:00 ")
    assert row == {
        "table": "apps_orders",
        "kind": "details",
        "session_id": "cs_test_apps_1",
        "restaurant_name": "Beiz am See",
        "phone": "+41799380372",
        "opening_hours": "Di–Sa 18:00–23:00",
        "created_at": row["created_at"],
    }


@pytest.mark.parametrize(
    "name, phone, hours, expected",
    [
        ("", "079 938 03 72", "Mo–Fr", "restaurant_name"),
        ("Beiz", "079 938 03 72", "  ", "opening_hours"),
        ("Beiz", "+49 30 123456", "Mo–Fr", "Swiss"),
    ],
)
def test_details_row_rejects_incomplete_input(name, phone, hours, expected) -> None:
    with pytest.raises(ValueError, match=expected):
        details_row("cs_1", name, phone, hours)


@pytest.mark.parametrize(
    "name, phone, hours, field",
    [
        ("", "079 938 03 72", "Mo–Fr", "restaurant_name"),
        ("Beiz", "079 938 03 72", "  ", "opening_hours"),
        ("Beiz", "+49 30 123456", "Mo–Fr", "phone"),
    ],
)
def test_details_row_names_the_field_so_the_form_can_point_at_it(name, phone, hours, field) -> None:
    with pytest.raises(DetailsInvalid) as excinfo:
        details_row("cs_1", name, phone, hours)
    assert excinfo.value.field == field


@pytest.mark.asyncio
async def test_row_is_posted_to_the_n8n_url_from_the_environment(monkeypatch) -> None:
    monkeypatch.setattr(settings, "n8n_apps_order_url", "https://n8n.invalid/webhook/apps ")
    post = AsyncMock(return_value=type("R", (), {"status_code": 200, "text": "ok"})())

    with patch("httpx.AsyncClient.post", post):
        await post_order_row({"table": "apps_orders", "kind": "paid"})

    assert post.await_args.args[0] == "https://n8n.invalid/webhook/apps"
    assert post.await_args.kwargs["json"]["table"] == "apps_orders"


@pytest.mark.asyncio
async def test_missing_n8n_url_is_its_own_error(monkeypatch) -> None:
    monkeypatch.setattr(settings, "n8n_apps_order_url", "")
    with pytest.raises(AppsOrderNotConfigured, match="N8N_APPS_ORDER_URL"):
        await post_order_row({"kind": "paid"})


@pytest.mark.asyncio
async def test_n8n_error_status_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "n8n_apps_order_url", "https://n8n.invalid/webhook/apps")
    post = AsyncMock(return_value=type("R", (), {"status_code": 500, "text": "boom"})())

    with patch("httpx.AsyncClient.post", post), pytest.raises(AppsOrderError):
        await post_order_row({"kind": "paid"})


# --- pages -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_landing_page_sells_the_offer_with_the_imprint_footer() -> None:
    async with _client() as client:
        response = await client.get("/apps/")
        redirect = await client.get("/apps")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "WhatsApp" in response.text
    assert "CHF 1'990" in response.text
    assert "CHF 249" in response.text
    assert "/apps/checkout" in response.text
    for fragment in ("STARTEND GmbH", "CHE-223.488.613", "Bahnhofstrasse 7", "6330 Cham"):
        assert fragment in response.text
    assert redirect.status_code == 301
    assert redirect.headers["location"] == "/apps/"


@pytest.mark.asyncio
async def test_success_page_renders_for_any_session_id() -> None:
    # Acceptance criterion: the buyer has already paid, so this page never errors.
    async with _client() as client:
        response = await client.get("/apps/success?session_id=test")

    assert response.status_code == 200
    assert 'name="restaurant_name"' in response.text
    assert 'name="phone"' in response.text
    assert 'name="opening_hours"' in response.text
    assert 'value="test"' in response.text
    assert "CHE-223.488.613" in response.text


@pytest.mark.asyncio
async def test_success_page_renders_without_a_session_id() -> None:
    async with _client() as client:
        response = await client.get("/apps/success")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_success_form_writes_a_details_row(monkeypatch) -> None:
    monkeypatch.setattr(settings, "n8n_apps_order_url", "https://n8n.invalid/webhook/apps")
    sent = AsyncMock()

    with patch("app.api.apps.post_order_row", sent):
        async with _client() as client:
            response = await client.post(
                "/apps/success",
                data={
                    "session_id": "cs_test_apps_1",
                    "restaurant_name": "Beiz am See",
                    "phone": "079 938 03 72",
                    "opening_hours": "Di–Sa 18:00–23:00",
                },
            )

    assert response.status_code == 200
    assert "Danke" in response.text
    row = sent.await_args.args[0]
    assert row["kind"] == "details"
    assert row["phone"] == "+41799380372"
    assert row["session_id"] == "cs_test_apps_1"


@pytest.mark.asyncio
async def test_success_form_re_asks_in_german_for_a_bad_number() -> None:
    sent = AsyncMock()
    with patch("app.api.apps.post_order_row", sent):
        async with _client() as client:
            response = await client.post(
                "/apps/success",
                data={
                    "session_id": "cs_1",
                    "restaurant_name": "Beiz am See",
                    "phone": "+49 30 123456",
                    "opening_hours": "Di–Sa",
                },
            )

    assert response.status_code == 422
    assert "Schweizer Nummer" in response.text
    # What was typed comes back, so nothing has to be retyped.
    assert "Beiz am See" in response.text
    sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_form_asks_again_when_the_row_could_not_be_stored() -> None:
    with patch("app.api.apps.post_order_row", AsyncMock(side_effect=AppsOrderError("n8n down"))):
        async with _client() as client:
            response = await client.post(
                "/apps/success",
                data={
                    "session_id": "cs_1",
                    "restaurant_name": "Beiz am See",
                    "phone": "079 938 03 72",
                    "opening_hours": "Di–Sa",
                },
            )

    assert response.status_code == 502
    assert "nochmals" in response.text


@pytest.mark.asyncio
async def test_success_form_still_thanks_the_buyer_when_n8n_is_not_configured() -> None:
    with patch("app.api.apps.post_order_row", AsyncMock(side_effect=AppsOrderNotConfigured("unset"))):
        async with _client() as client:
            response = await client.post(
                "/apps/success",
                data={
                    "session_id": "cs_1",
                    "restaurant_name": "Beiz am See",
                    "phone": "079 938 03 72",
                    "opening_hours": "Di–Sa",
                },
            )

    assert response.status_code == 200
    assert "Danke" in response.text


@pytest.mark.asyncio
async def test_checkout_without_price_ids_is_unavailable_not_a_crash(monkeypatch) -> None:
    monkeypatch.setattr(settings, "price_id_apps_setup", "")
    monkeypatch.setattr(settings, "price_id_apps_monthly", "")

    async with _client() as client:
        response = await client.get("/apps/checkout", follow_redirects=False)

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_checkout_redirects_to_stripe(monkeypatch) -> None:
    monkeypatch.setattr(settings, "price_id_apps_setup", SETUP_PRICE)
    monkeypatch.setattr(settings, "price_id_apps_monthly", MONTHLY_PRICE)
    session = {"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"}

    with patch("app.api.apps.create_apps_checkout_session", AsyncMock(return_value=session)):
        async with _client() as client:
            response = await client.get("/apps/checkout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == session["url"]


# --- webhook -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_writes_the_order_row(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_apps")
    payload = _event(COMPLETED_SESSION)
    sent = AsyncMock()

    with patch("app.api.apps.post_order_row", sent):
        async with _client() as client:
            response = await client.post(
                "/apps/stripe/webhook",
                content=payload,
                headers={"stripe-signature": sign_webhook_payload(payload, "whsec_apps")},
            )

    assert response.status_code == 200
    assert response.json() == {"received": True, "stored": True}
    row = sent.await_args.args[0]
    assert row["kind"] == "paid"
    assert row["session_id"] == "cs_test_apps_1"


@pytest.mark.asyncio
async def test_webhook_rejects_a_forged_signature(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_apps")
    payload = _event(COMPLETED_SESSION)
    sent = AsyncMock()

    with patch("app.api.apps.post_order_row", sent):
        async with _client() as client:
            response = await client.post(
                "/apps/stripe/webhook",
                content=payload,
                headers={"stripe-signature": sign_webhook_payload(payload, "whsec_wrong")},
            )

    assert response.status_code == 400
    sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_ignores_other_products_and_other_events(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_apps")
    other_product = _event({**COMPLETED_SESSION, "metadata": {"product": "x-autopilot"}})
    other_event = _event(COMPLETED_SESSION, "charge.refunded")
    sent = AsyncMock()

    with patch("app.api.apps.post_order_row", sent):
        async with _client() as client:
            first = await client.post(
                "/apps/stripe/webhook",
                content=other_product,
                headers={"stripe-signature": sign_webhook_payload(other_product, "whsec_apps")},
            )
            second = await client.post(
                "/apps/stripe/webhook",
                content=other_event,
                headers={"stripe-signature": sign_webhook_payload(other_event, "whsec_apps")},
            )

    assert first.json() == {"received": True, "ignored": True}
    assert second.json() == {"received": True}
    sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_asks_stripe_to_retry_when_the_row_cannot_be_stored(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_apps")
    payload = _event(COMPLETED_SESSION)

    with patch("app.api.apps.post_order_row", AsyncMock(side_effect=AppsOrderError("n8n down"))):
        async with _client() as client:
            response = await client.post(
                "/apps/stripe/webhook",
                content=payload,
                headers={"stripe-signature": sign_webhook_payload(payload, "whsec_apps")},
            )

    assert response.status_code == 503


# --- CHF 1 test link + demo booking -----------------------------------------


CHF1_TEST_LINK = "https://buy.stripe.com/6oU5kE8RD3DrgzG2Tx0x20f"
FUTURE = (date.today() + timedelta(days=7)).isoformat()
DEMO_FORM = {
    "restaurant_name": "Beiz am See",
    "contact": "wirt@beiz.ch",
    "date": FUTURE,
    "time": "15:30",
    "guests": "4",
    "note": "Terrasse",
}


@pytest.mark.asyncio
async def test_landing_page_offers_the_chf1_test_link_and_the_demo() -> None:
    async with _client() as client:
        response = await client.get("/apps/")

    assert CHF1_TEST_LINK in response.text
    assert "CHF 1 Test" in response.text
    assert "/apps/demo" in response.text


def test_demo_booking_normalizes_and_validates() -> None:
    booking = demo_booking("  Beiz am See ", " wirt@beiz.ch ", FUTURE, " 15:30 ", "4", "  Terrasse  ")
    assert booking["restaurant_name"] == "Beiz am See"
    assert booking["contact"] == "wirt@beiz.ch"
    assert booking["date"] == FUTURE
    assert booking["time"] == "15:30"
    assert booking["guests"] == 4
    assert booking["note"] == "Terrasse"
    assert booking["created_at"]


@pytest.mark.parametrize(
    "restaurant, contact, day, guests, expected",
    [
        ("", "wirt@beiz.ch", FUTURE, "4", "restaurant_name"),
        ("Beiz", "x", FUTURE, "4", "contact"),
        ("Beiz", "wirt@beiz.ch", "2020-01-01", "4", "date"),
        ("Beiz", "wirt@beiz.ch", "not-a-date", "4", "date"),
        ("Beiz", "wirt@beiz.ch", FUTURE, "0", "guests"),
        ("Beiz", "wirt@beiz.ch", FUTURE, "51", "guests"),
        ("Beiz", "wirt@beiz.ch", FUTURE, "vier", "guests"),
    ],
)
def test_demo_booking_rejects_bad_input(restaurant, contact, day, guests, expected) -> None:
    with pytest.raises(ValueError, match=expected):
        demo_booking(restaurant, contact, day, "", guests)


def test_demo_mail_is_german_and_names_the_booking() -> None:
    booking = demo_booking("Beiz am See", "079 938 03 72", FUTURE, "", "4")
    subject, body = demo_mail(booking)
    assert "Beiz am See" in subject and FUTURE in subject and "4 Personen" in subject
    assert "079 938 03 72" in body
    assert "Uhrzeit: —" in body


@pytest.mark.asyncio
async def test_demo_page_renders_the_booking_form() -> None:
    async with _client() as client:
        response = await client.get("/apps/demo")

    assert response.status_code == 200
    for name in ("restaurant_name", "contact", "date", "guests"):
        assert f'name="{name}"' in response.text
    assert "CHE-223.488.613" in response.text


@pytest.mark.asyncio
async def test_demo_booking_sends_the_confirmation_mail_through_hq_mail() -> None:
    sent = AsyncMock()
    with patch("app.api.apps.send_hq_mail", sent):
        async with _client() as client:
            response = await client.post("/apps/demo", data=DEMO_FORM)

    assert response.status_code == 200
    assert "Demo gebucht" in response.text
    assert "Beiz am See" in response.text
    subject, body = sent.await_args.args
    assert "Beiz am See" in subject and FUTURE in subject
    assert "wirt@beiz.ch" in body and "Terrasse" in body
    # Only the HQ inbox is written to — the form never picks the recipient.
    assert "to" not in sent.await_args.kwargs


@pytest.mark.asyncio
async def test_demo_booking_re_asks_in_german_for_a_past_date() -> None:
    sent = AsyncMock()
    with patch("app.api.apps.send_hq_mail", sent):
        async with _client() as client:
            response = await client.post("/apps/demo", data={**DEMO_FORM, "date": "2020-01-01"})

    assert response.status_code == 422
    assert "Datum ab heute" in response.text
    # What was typed comes back, so nothing has to be retyped.
    assert "Beiz am See" in response.text
    sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_demo_booking_honeypot_swallows_bots() -> None:
    sent = AsyncMock()
    with patch("app.api.apps.send_hq_mail", sent):
        async with _client() as client:
            response = await client.post(
                "/apps/demo", data={**DEMO_FORM, "company_website": "http://spam.example"}
            )

    assert response.status_code == 200
    sent.assert_not_awaited()


@pytest.mark.parametrize("failure", [HQMailError("down"), HQMailNotConfigured("unset")])
@pytest.mark.asyncio
async def test_demo_booking_asks_again_when_the_mail_cannot_be_sent(failure) -> None:
    # A demo request nobody receives is a lost lead: never pretend it went through.
    with patch("app.api.apps.send_hq_mail", AsyncMock(side_effect=failure)):
        async with _client() as client:
            response = await client.post("/apps/demo", data=DEMO_FORM)

    assert response.status_code == 502
    assert "nochmals" in response.text
    assert "Beiz am See" in response.text


# --- no secrets --------------------------------------------------------------


def test_no_endpoint_or_key_is_baked_into_the_apps_code() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    sources = [
        root / "app" / "api" / "apps.py",
        root / "app" / "services" / "apps_checkout.py",
        root / "app" / "services" / "apps_orders.py",
        root / "app" / "services" / "apps_demo.py",
        root / "app" / "static" / "apps" / "index.html",
    ]
    for path in sources:
        source = path.read_text(encoding="utf-8")
        assert "n8n.cloud" not in source
        assert "sk_live" not in source and "sk_test" not in source
        assert "whsec_" not in source
        assert "price_1" not in source
