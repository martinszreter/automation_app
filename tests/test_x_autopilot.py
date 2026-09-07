import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db.models import PlanStatus, XAutopilotPlan
from app.db.session import get_db
from app.main import app
from app.services.google_oauth import dumps_state
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
    assert "Plan active" in panel.text
    assert "buyer@example.com" in panel.text
    assert "CHF 1" in panel.text
    assert "Read ok" in panel.text
    assert "pricing" in panel.text
    assert "Refund CHF 1 test payment" in panel.text


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
