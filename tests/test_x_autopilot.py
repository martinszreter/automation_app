import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db.models import PlanStatus, XAutopilotPlan
from app.db.session import get_db
from app.main import app
from app.services import xautopilot_orders as xa_orders
from app.services import xautopilot_tiers as xa_tiers
from app.services.google_oauth import GoogleNotConfigured, SheetsReconnectRequired, dumps_state
from app.services.stripe_checkout import (
    checkout_urls,
    create_checkout_session,
    sign_webhook_payload,
    verify_stripe_signature,
)


PAID_SESSION = {
    "id": "cs_test_1",
    "payment_status": "paid",
    "status": "complete",
    "customer_details": {"email": "buyer@example.com"},
    "customer_email": "buyer@example.com",
    "customer": "cus_test",
    "payment_intent": "pi_test",
    "amount_total": 100,
    "currency": "chf",
    "metadata": {"product": "x-autopilot"},
}


def _plan() -> XAutopilotPlan:
    return XAutopilotPlan(
        email="buyer@example.com",
        stripe_email="buyer@example.com",
        status=PlanStatus.ACTIVE,
        stripe_checkout_session_id="cs_test_1",
        stripe_payment_intent_id="pi_test",
        amount_cents=100,
        currency="chf",
    )


def _mock_db(existing: XAutopilotPlan | None = None) -> AsyncMock:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _client(db: AsyncMock) -> AsyncClient:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides() -> None:
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_impressum_page_has_company_details() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/impressum/")
        redirect = await client.get("/impressum")

    assert response.status_code == 200
    assert "Impressum" in response.text
    assert "STARTEND GmbH" in response.text
    assert "CHE-223.488.613" in response.text
    assert "Bahnhofstrasse 7" in response.text
    assert redirect.status_code == 301
    assert redirect.headers["location"] == "/impressum/"


@pytest.mark.asyncio
async def test_checkout_urls_land_on_panel_login() -> None:
    success, cancel = checkout_urls("https://www.startend.ch/")
    assert success == (
        "https://www.startend.ch/x-autopilot/panel/login?session_id={CHECKOUT_SESSION_ID}"
    )
    assert cancel == "https://www.startend.ch/x-autopilot/"


@pytest.mark.asyncio
async def test_create_checkout_session_uses_chf1_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    async def fake_request(method: str, path: str, data: dict | None = None) -> dict:
        captured["data"] = data
        return {"id": "cs_x", "url": "https://checkout.stripe.com/c/pay/cs_x"}

    monkeypatch.setattr("app.services.stripe_checkout.stripe_request", fake_request)
    monkeypatch.setattr(settings, "stripe_xautopilot_amount_cents", 100)
    monkeypatch.setattr(settings, "stripe_xautopilot_price_id", "")
    monkeypatch.setattr(settings, "stripe_xautopilot_mode", "payment")

    session = await create_checkout_session("https://www.startend.ch")

    assert session["url"].startswith("https://checkout.stripe.com/")
    assert captured["data"]["success_url"].endswith(
        "/x-autopilot/panel/login?session_id={CHECKOUT_SESSION_ID}"
    )
    assert captured["data"]["line_items[0][price_data][unit_amount]"] == "100"
    assert captured["data"]["line_items[0][price_data][currency]"] == "chf"


@pytest.mark.asyncio
async def test_checkout_redirects_to_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_create(base_url: str) -> dict:
        assert "test" in base_url
        return {"id": "cs_live", "url": "https://checkout.stripe.com/c/pay/cs_live"}

    monkeypatch.setattr("app.api.x_autopilot.create_checkout_session", fake_create)
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/checkout")

    assert response.status_code == 303
    assert response.headers["location"] == "https://checkout.stripe.com/c/pay/cs_live"


@pytest.mark.asyncio
async def test_checkout_unavailable_without_stripe_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/checkout")

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_webhook_marks_plan_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    payload = json.dumps(
        {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": PAID_SESSION}}
    ).encode()
    header = sign_webhook_payload(payload, "whsec_test")
    db = _mock_db()
    async with _client(db) as client:
        response = await client.post(
            "/x-autopilot/stripe/webhook",
            content=payload,
            headers={"stripe-signature": header, "content-type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    db.add.assert_called_once()
    stored = db.add.call_args.args[0]
    assert stored.email == "buyer@example.com"
    assert stored.status == PlanStatus.ACTIVE
    assert stored.amount_cents == 100
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    payload = json.dumps(
        {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": PAID_SESSION}}
    ).encode()
    db = _mock_db()
    async with _client(db) as client:
        response = await client.post(
            "/x-autopilot/stripe/webhook",
            content=payload,
            headers={"stripe-signature": "t=1,v1=deadbeef", "content-type": "application/json"},
        )

    assert response.status_code == 400
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_refund_marks_plan_refunded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    plan = _plan()
    payload = json.dumps(
        {
            "id": "evt_2",
            "type": "charge.refunded",
            "data": {"object": {"payment_intent": "pi_test"}},
        }
    ).encode()
    header = sign_webhook_payload(payload, "whsec_test")
    db = _mock_db(existing=plan)
    async with _client(db) as client:
        response = await client.post(
            "/x-autopilot/stripe/webhook",
            content=payload,
            headers={"stripe-signature": header, "content-type": "application/json"},
        )

    assert response.status_code == 200
    assert plan.status == PlanStatus.REFUNDED


def test_stripe_signature_roundtrip() -> None:
    secret = "whsec_x"
    payload = b'{"ok":true}'
    header = sign_webhook_payload(payload, secret)
    verify_stripe_signature(payload, header, secret)


@pytest.mark.asyncio
async def test_login_page_offers_google(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client")
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/panel/login?session_id=cs_test_1")

    assert response.status_code == 200
    assert "Sign in with Google" in response.text
    assert 'href="/x-autopilot/auth/google"' in response.text
    assert "Impressum" in response.text


@pytest.mark.asyncio
async def test_panel_requires_login() -> None:
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/panel")

    assert response.status_code == 303
    assert response.headers["location"] == "/x-autopilot/panel/login"


@pytest.mark.asyncio
async def test_google_signin_after_payment_shows_active_plan_and_sheets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan()
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "google-secret")
    monkeypatch.setattr(
        "app.api.x_autopilot.google_oauth.exchange_code",
        AsyncMock(return_value={"access_token": "ya29.token"}),
    )
    monkeypatch.setattr(
        "app.api.x_autopilot.google_oauth.fetch_userinfo",
        AsyncMock(return_value={"email": "buyer@example.com", "name": "Buyer", "sub": "123"}),
    )
    monkeypatch.setattr(
        "app.api.x_autopilot.retrieve_checkout_session",
        AsyncMock(return_value=PAID_SESSION),
    )
    monkeypatch.setattr(
        "app.api.x_autopilot.upsert_plan_from_checkout",
        AsyncMock(return_value=plan),
    )
    monkeypatch.setattr(
        "app.api.x_autopilot.get_active_plan_for_email",
        AsyncMock(return_value=plan),
    )
    monkeypatch.setattr(
        "app.api.x_autopilot.google_oauth.read_sheet_values",
        AsyncMock(
            return_value={
                "spreadsheet_id": "sheet1",
                "range": "Sheet1!A1:B2",
                "row_count": 2,
                "values": [["topic", "status"], ["pricing", "queued"]],
                "rows": [["topic", "status"], ["pricing", "queued"]],
            }
        ),
    )

    state = dumps_state({"purpose": "login", "checkout": "cs_test_1"})
    db = _mock_db(existing=plan)
    async with _client(db) as client:
        callback = await client.get(
            "/x-autopilot/auth/google/callback",
            params={"code": "auth-code", "state": state},
        )
        assert callback.status_code == 303
        assert callback.headers["location"] == "/x-autopilot/panel"
        panel = await client.get("/x-autopilot/panel")

    assert panel.status_code == 200
    assert "Plan aktiv" in panel.text
    assert "buyer@example.com" in panel.text
    assert "CHF 1" in panel.text
    assert "Lesen ok" in panel.text
    assert "pricing" in panel.text
    assert "CHF 1 Testzahlung erstatten" in panel.text


@pytest.mark.asyncio
async def test_refund_endpoint_calls_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    refund = AsyncMock(return_value=plan)
    monkeypatch.setattr("app.api.x_autopilot.get_active_plan_for_email", AsyncMock(return_value=plan))
    monkeypatch.setattr("app.api.x_autopilot.refund_plan", refund)
    monkeypatch.setattr(
        "app.api.x_autopilot.google_oauth.exchange_code",
        AsyncMock(return_value={"access_token": "ya29.token"}),
    )
    monkeypatch.setattr(
        "app.api.x_autopilot.google_oauth.fetch_userinfo",
        AsyncMock(return_value={"email": "buyer@example.com", "name": "Buyer", "sub": "123"}),
    )
    monkeypatch.setattr(
        "app.api.x_autopilot.retrieve_checkout_session",
        AsyncMock(return_value=PAID_SESSION),
    )
    monkeypatch.setattr("app.api.x_autopilot.upsert_plan_from_checkout", AsyncMock(return_value=plan))

    state = dumps_state({"purpose": "login", "checkout": "cs_test_1"})
    db = _mock_db(existing=plan)
    async with _client(db) as client:
        await client.get(
            "/x-autopilot/auth/google/callback",
            params={"code": "auth-code", "state": state},
        )
        response = await client.post("/x-autopilot/panel/refund")

    assert response.status_code == 303
    refund.assert_awaited_once()


@pytest.mark.asyncio
async def test_sheets_reconnect_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "google_sheets_reconnect_key", "secret-key")
    db = _mock_db()
    async with _client(db) as client:
        missing = await client.get("/x-autopilot/sheets/reconnect")
        wrong = await client.get("/x-autopilot/sheets/reconnect", params={"key": "nope"})

    assert missing.status_code == 404
    assert wrong.status_code == 404


@pytest.mark.asyncio
async def test_sheets_reconnect_starts_google_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "google_sheets_reconnect_key", "secret-key")
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "google-secret")
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/sheets/reconnect", params={"key": "secret-key"})

    assert response.status_code == 302
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "spreadsheets.readonly" in response.headers["location"]
    assert "access_type=offline" in response.headers["location"]


async def _open_panel_with_sheets_failure(
    monkeypatch: pytest.MonkeyPatch,
    *,
    failure: Exception,
    last_sent_at: float = 0.0,
    reconnect_key: str = "secret-key",
) -> tuple[int, AsyncMock]:
    """Sign in with an active plan whose Sheets read raises ``failure``.

    Returns the panel status code and the mocked ``send_hq_mail``.
    """
    import app.api.x_autopilot as xa_api

    monkeypatch.setitem(xa_api._sheets_reconnect_mail, "sent_at", last_sent_at)
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client")
    monkeypatch.setattr(settings, "google_sheets_reconnect_key", reconnect_key)
    plan = _plan()
    monkeypatch.setattr(
        "app.api.x_autopilot.google_oauth.exchange_code",
        AsyncMock(return_value={"access_token": "ya29.token"}),
    )
    monkeypatch.setattr(
        "app.api.x_autopilot.google_oauth.fetch_userinfo",
        AsyncMock(return_value={"email": "buyer@example.com", "name": "Buyer", "sub": "123"}),
    )
    monkeypatch.setattr("app.api.x_autopilot.get_active_plan_for_email", AsyncMock(return_value=plan))
    monkeypatch.setattr(
        "app.api.x_autopilot.google_oauth.read_sheet_values",
        AsyncMock(side_effect=failure),
    )
    sent = AsyncMock()
    monkeypatch.setattr("app.api.x_autopilot.send_hq_mail", sent)

    state = dumps_state({"purpose": "login", "checkout": ""})
    db = _mock_db(existing=plan)
    async with _client(db) as client:
        await client.get(
            "/x-autopilot/auth/google/callback",
            params={"code": "auth-code", "state": state},
        )
        panel = await client.get("/x-autopilot/panel")
    return panel.status_code, sent


@pytest.mark.asyncio
async def test_panel_asks_for_sheets_reconnect_by_email(monkeypatch: pytest.MonkeyPatch) -> None:
    status, sent = await _open_panel_with_sheets_failure(
        monkeypatch,
        failure=GoogleNotConfigured("GOOGLE_SHEETS_REFRESH_TOKEN is not set"),
    )

    assert status == 200
    sent.assert_awaited_once()
    subject, body = sent.await_args.args
    assert subject == "X Autopilot: Sheets reconnect needed"
    assert "/x-autopilot/sheets/reconnect?key=secret-key" in body
    assert "GOOGLE_SHEETS_REFRESH_TOKEN is not set" in body


@pytest.mark.asyncio
async def test_panel_asks_for_reconnect_when_refresh_token_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status, sent = await _open_panel_with_sheets_failure(
        monkeypatch,
        failure=SheetsReconnectRequired("Sheets refresh token was rejected; reconnect needed"),
        reconnect_key="se/cret key",
    )

    assert status == 200
    sent.assert_awaited_once()
    _subject, body = sent.await_args.args
    assert "reconnect?key=se%2Fcret%20key" in body
    assert "rejected" in body


@pytest.mark.asyncio
async def test_panel_sheets_reconnect_email_is_debounced(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    status, sent = await _open_panel_with_sheets_failure(
        monkeypatch,
        failure=GoogleNotConfigured("GOOGLE_SHEETS_REFRESH_TOKEN is not set"),
        last_sent_at=time.time(),
    )

    assert status == 200
    sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_panel_skips_reconnect_email_without_reconnect_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status, sent = await _open_panel_with_sheets_failure(
        monkeypatch,
        failure=GoogleNotConfigured("GOOGLE_SHEETS_REFRESH_TOKEN is not set"),
        reconnect_key="",
    )

    assert status == 200
    sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_transient_sheets_read_error_does_not_email(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.google_oauth import GoogleOAuthError

    status, sent = await _open_panel_with_sheets_failure(
        monkeypatch,
        failure=GoogleOAuthError("Sheets read failed"),
    )

    assert status == 200
    sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejected_refresh_token_raises_reconnect_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import google_oauth

    google_oauth.clear_sheets_access_cache()
    monkeypatch.setattr(settings, "google_oauth_client_id", "cid")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "csecret")
    monkeypatch.setattr(settings, "google_sheets_refresh_token", "revoked")

    def client_answering(status_code: int) -> type:
        class FakeResponse:
            def __init__(self) -> None:
                self.status_code = status_code
                self.text = '{"error": "invalid_grant"}'

            def json(self) -> dict:
                return {"error": "invalid_grant"}

        class FakeClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self) -> "FakeClient":
                return self

            async def __aexit__(self, *args) -> bool:
                return False

            async def post(self, url: str, data: dict | None = None) -> FakeResponse:
                return FakeResponse()

        return FakeClient

    monkeypatch.setattr("app.services.google_oauth.httpx.AsyncClient", client_answering(400))
    with pytest.raises(google_oauth.SheetsReconnectRequired):
        await google_oauth.sheets_access_token()

    monkeypatch.setattr("app.services.google_oauth.httpx.AsyncClient", client_answering(503))
    with pytest.raises(google_oauth.GoogleOAuthError) as excinfo:
        await google_oauth.sheets_access_token()
    assert not isinstance(excinfo.value, google_oauth.SheetsReconnectRequired)


@pytest.mark.asyncio
async def test_sheets_token_refresh_is_env_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import google_oauth

    google_oauth.clear_sheets_access_cache()
    monkeypatch.setattr(settings, "google_oauth_client_id", "cid")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "csecret")
    monkeypatch.setattr(settings, "google_sheets_refresh_token", "env-refresh-only")
    monkeypatch.setattr(settings, "google_sheets_spreadsheet_id", "sheet-id")
    monkeypatch.setattr(settings, "google_sheets_range", "Sheet1!A1:A1")

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self.status_code = 200
            self._payload = payload
            self.text = json.dumps(payload)

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args) -> bool:
            return False

        async def post(self, url: str, data: dict | None = None) -> FakeResponse:
            assert data is not None
            assert data["refresh_token"] == "env-refresh-only"
            assert data["grant_type"] == "refresh_token"
            return FakeResponse({"access_token": "ya29.from-refresh", "expires_in": 3600})

        async def get(self, url: str, headers: dict | None = None) -> FakeResponse:
            assert headers == {"Authorization": "Bearer ya29.from-refresh"}
            assert "sheet-id" in url
            return FakeResponse({"range": "Sheet1!A1:A1", "values": [["ok"]]})

    monkeypatch.setattr("app.services.google_oauth.httpx.AsyncClient", FakeClient)
    result = await google_oauth.read_sheet_values()
    assert result["row_count"] == 1
    assert result["rows"] == [["ok"]]


# --- three tiers: CHF 149 / 330 / 990 ----------------------------------------


TIER_PRICES = {"149": "price_xa_149", "330": "price_xa_330", "990": "price_xa_990"}


def _configure_tiers(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    for slug, price_id in {**TIER_PRICES, **overrides}.items():
        monkeypatch.setattr(settings, f"price_id_xa_{slug}", price_id)


def test_session_builder_covers_all_three_tiers() -> None:
    for slug, price_id in TIER_PRICES.items():
        tier = xa_tiers.get_tier(slug)
        payload = xa_tiers.build_checkout_session_payload(
            "https://www.startend.ch/", tier, price_id
        )

        assert payload["mode"] == "subscription"
        assert payload["line_items[0][price]"] == price_id
        assert payload["line_items[0][quantity]"] == "1"
        assert payload["metadata[tier]"] == slug
        assert payload["metadata[price_id]"] == price_id
        assert payload["metadata[product]"] == "x-autopilot"
        assert payload["subscription_data[metadata][tier]"] == slug
        assert payload["success_url"] == (
            "https://www.startend.ch/x-autopilot/success?session_id={CHECKOUT_SESSION_ID}"
        )
        assert payload["cancel_url"] == "https://www.startend.ch/x-autopilot/"
        # No amount is ever hard-coded: only the Price id reaches Stripe.
        assert not [key for key in payload if "price_data" in key]

    assert [tier.slug for tier in xa_tiers.TIERS] == ["149", "330", "990"]
    assert [tier.price_label for tier in xa_tiers.TIERS] == ["CHF 149", "CHF 330", "CHF 990"]


def test_session_builder_refuses_a_tier_without_a_price_id() -> None:
    with pytest.raises(xa_tiers.TierPriceNotConfigured) as excinfo:
        xa_tiers.build_checkout_session_payload(
            "https://www.startend.ch", xa_tiers.get_tier("330"), "  "
        )
    assert "PRICE_ID_XA_330" in str(excinfo.value)


def test_session_builder_supports_one_time_prices() -> None:
    payload = xa_tiers.build_checkout_session_payload(
        "https://www.startend.ch", xa_tiers.get_tier("990"), "price_once", mode="payment"
    )
    assert payload["mode"] == "payment"
    assert "subscription_data[metadata][tier]" not in payload


def test_unknown_tier_is_rejected() -> None:
    with pytest.raises(xa_tiers.UnknownTier):
        xa_tiers.get_tier("500")


@pytest.mark.asyncio
async def test_tier_checkout_redirects_to_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    _configure_tiers(monkeypatch)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test")

    async def fake_request(method: str, path: str, data: dict | None = None) -> dict:
        captured["path"] = path
        captured["data"] = data
        return {"id": "cs_tier", "url": "https://checkout.stripe.com/c/pay/cs_tier"}

    monkeypatch.setattr("app.services.xautopilot_tiers.stripe_request", fake_request)
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/checkout/330")

    assert response.status_code == 303
    assert response.headers["location"] == "https://checkout.stripe.com/c/pay/cs_tier"
    assert captured["path"] == "/checkout/sessions"
    assert captured["data"]["line_items[0][price]"] == "price_xa_330"


@pytest.mark.asyncio
async def test_tier_checkout_is_503_when_the_price_id_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_tiers(monkeypatch, **{"990": ""})
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test")
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/checkout/990")

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_unknown_tier_checkout_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test")
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/checkout/500")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_success_page_renders_for_any_session_id() -> None:
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/success?session_id=test")

    assert response.status_code == 200
    assert "test" in response.text
    # Confirmation + the X authorization step, which is the whole point of it.
    assert "Payment received" in response.text
    assert 'id="xOauthLink"' in response.text
    assert "/x-autopilot/onboarding.html?session_id=test" in response.text


@pytest.mark.asyncio
async def test_success_page_uses_the_configured_x_oauth_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "x_oauth_onboarding_url", "https://n8n.example/x-auth?v=1")
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/success?session_id=cs_test_1")

    assert response.status_code == 200
    assert "https://n8n.example/x-auth?v=1&amp;session_id=cs_test_1" in response.text


@pytest.mark.asyncio
async def test_success_page_without_a_session_id_still_renders() -> None:
    db = _mock_db()
    async with _client(db) as client:
        response = await client.get("/x-autopilot/success")

    assert response.status_code == 200
    assert 'href="/x-autopilot/onboarding.html"' in response.text


def test_tier_buttons_are_disabled_until_the_price_id_is_set() -> None:
    html = (
        '<div>'
        + "".join(xa_tiers.disabled_button_html(tier) for tier in xa_tiers.TIERS)
        + "</div>"
    )

    rendered = xa_tiers.render_tier_buttons(html, configured={"149", "990"})

    assert 'href="/x-autopilot/checkout/149"' in rendered
    assert 'href="/x-autopilot/checkout/990"' in rendered
    # The unconfigured tier keeps the disabled button and names the variable.
    assert 'data-missing-env="PRICE_ID_XA_330"' in rendered
    assert "/x-autopilot/checkout/330" not in rendered
    assert rendered.count("disabled") == 1


def test_tier_buttons_stay_disabled_when_the_markup_drifts() -> None:
    drifted = '<button class="btn" id="startBtn149">Start</button>'
    assert xa_tiers.render_tier_buttons(drifted, configured={"149"}) == drifted


def test_order_row_carries_the_tier() -> None:
    row = xa_orders.order_row_from_session(
        {**PAID_SESSION, "metadata": {"product": "x-autopilot", "tier": "330",
                                      "price_id": "price_xa_330"}}
    )

    assert row["table"] == "xautopilot_orders"
    assert row["kind"] == "paid"
    assert row["session_id"] == "cs_test_1"
    assert row["tier"] == "330"
    assert row["price_id"] == "price_xa_330"
    assert row["email"] == "buyer@example.com"
    assert row["amount_total_cents"] == 100
    assert row["currency"] == "chf"


def test_order_row_needs_a_session_id() -> None:
    with pytest.raises(ValueError):
        xa_orders.order_row_from_session({"payment_status": "paid"})


@pytest.mark.asyncio
async def test_webhook_posts_the_order_to_n8n(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(settings, "n8n_xautopilot_order_url", "https://n8n.example/orders")
    posted: dict = {}

    async def fake_post(row: dict) -> None:
        posted.update(row)

    monkeypatch.setattr("app.api.x_autopilot.post_order_row", fake_post)
    session = {**PAID_SESSION, "metadata": {"product": "x-autopilot", "tier": "990"}}
    payload = json.dumps(
        {"id": "evt_3", "type": "checkout.session.completed", "data": {"object": session}}
    ).encode()
    header = sign_webhook_payload(payload, "whsec_test")
    db = _mock_db()
    async with _client(db) as client:
        response = await client.post(
            "/x-autopilot/stripe/webhook",
            content=payload,
            headers={"stripe-signature": header, "content-type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json() == {"received": True, "status": "active", "stored": True}
    assert posted["session_id"] == "cs_test_1"
    assert posted["tier"] == "990"


@pytest.mark.asyncio
async def test_webhook_asks_stripe_to_retry_when_n8n_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(settings, "n8n_xautopilot_order_url", "https://n8n.example/orders")

    async def fake_post(row: dict) -> None:
        raise xa_orders.XAOrderError("n8n responded 500")

    monkeypatch.setattr("app.api.x_autopilot.post_order_row", fake_post)
    payload = json.dumps(
        {"id": "evt_4", "type": "checkout.session.completed", "data": {"object": PAID_SESSION}}
    ).encode()
    header = sign_webhook_payload(payload, "whsec_test")
    db = _mock_db()
    async with _client(db) as client:
        response = await client.post(
            "/x-autopilot/stripe/webhook",
            content=payload,
            headers={"stripe-signature": header, "content-type": "application/json"},
        )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_webhook_still_activates_the_plan_without_an_n8n_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(settings, "n8n_xautopilot_order_url", "")
    payload = json.dumps(
        {"id": "evt_5", "type": "checkout.session.completed", "data": {"object": PAID_SESSION}}
    ).encode()
    header = sign_webhook_payload(payload, "whsec_test")
    db = _mock_db()
    async with _client(db) as client:
        response = await client.post(
            "/x-autopilot/stripe/webhook",
            content=payload,
            headers={"stripe-signature": header, "content-type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json()["stored"] is False
    db.add.assert_called_once()
