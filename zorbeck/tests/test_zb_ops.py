"""Ops: error alerts to the n8n handler, the CI stub's helpers, no secrets in code."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from zorbeck_app import stub
from zorbeck_app.alerts import alert_payload, send_alert
from zorbeck_app.config import Settings, settings
from zorbeck_app.main import app

ZORBECK = Path(__file__).resolve().parent.parent


# --- alerts ------------------------------------------------------------------


def test_alert_payload_matches_the_handlers_external_entry() -> None:
    payload = alert_payload("checkout", "Stripe API 500", description="d", stack="s", url="https://z/checkout")
    assert payload == {
        "app": "zorbeck",
        "workflow": "zorbeck",
        "node": "checkout",
        "message": "Stripe API 500",
        "description": "d",
        "stack": "s",
        "url": "https://z/checkout",
        "mode": "production",
    }


@pytest.mark.asyncio
async def test_alert_is_posted_to_the_env_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "alert_webhook_url", "https://n8n.invalid/alerts")
    post = AsyncMock(return_value=type("R", (), {"status_code": 200})())
    with patch("httpx.AsyncClient.post", post):
        ok = await send_alert("node", "msg", exc=RuntimeError("x"))
    assert ok is True
    assert post.await_args.args[0] == "https://n8n.invalid/alerts"
    body = post.await_args.kwargs["json"]
    assert body["app"] == "zorbeck"
    assert "RuntimeError: x" in body["stack"]


@pytest.mark.asyncio
async def test_alert_never_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "alert_webhook_url", "https://n8n.invalid/alerts")
    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=httpx.ConnectError("down"))):
        assert await send_alert("node", "msg") is False
    monkeypatch.setattr(settings, "alert_webhook_url", "")
    assert await send_alert("node", "msg") is False


@pytest.mark.asyncio
async def test_unhandled_errors_alert_and_answer_in_german() -> None:
    @app.get("/_test/boom", include_in_schema=False)
    async def boom() -> None:
        raise RuntimeError("kaputt")

    alert = AsyncMock(return_value=True)
    try:
        with patch("zorbeck_app.main.send_alert", alert):
            async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as c:
                response = await c.get("/_test/boom")
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/_test/boom"]

    assert response.status_code == 500
    assert "schiefgelaufen" in response.text
    assert "STARTEND GmbH" in response.text
    assert alert.await_args.args[0] == "/_test/boom"
    assert "RuntimeError: kaputt" in alert.await_args.args[1]


# --- settings -------------------------------------------------------------------


def test_settings_default_to_nothing_outbound(monkeypatch) -> None:
    for name in ("STRIPE_SECRET_KEY", "HQ_MAIL_WEBHOOK_URL", "ALERT_WEBHOOK_URL", "SIGNUP_WEBHOOK_URL", "ZORBECK_STUB"):
        monkeypatch.delenv(name, raising=False)
    fresh = Settings.from_env()
    assert fresh.stripe_secret_key == ""
    assert fresh.hq_mail_webhook_url == ""
    assert fresh.alert_webhook_url == ""
    assert fresh.stub is False
    assert fresh.stripe_api_base == "https://api.stripe.com/v1"
    assert fresh.price_cents == 4900


def test_settings_read_the_chf1_test_price(monkeypatch) -> None:
    monkeypatch.setenv("ZORBECK_PRICE_CENTS", "100")
    monkeypatch.setenv("ZORBECK_STUB", "1")
    monkeypatch.setenv("STRIPE_API_BASE", "http://127.0.0.1:8765/_stub/v1/")
    fresh = Settings.from_env()
    assert fresh.price_cents == 100
    assert fresh.stub is True
    assert fresh.stripe_api_base == "http://127.0.0.1:8765/_stub/v1"


# --- stub helpers --------------------------------------------------------------------


def test_stub_unflattens_stripe_form_encoding() -> None:
    flat = {
        "mode": "payment",
        "metadata[city]": "Zug",
        "line_items[0][price_data][unit_amount]": "100",
        "line_items[0][quantity]": "1",
    }
    nested = stub._nested(flat)
    assert nested["metadata"] == {"city": "Zug"}
    assert nested["line_items"]["0"]["price_data"]["unit_amount"] == "100"
    assert stub._line_amount(nested) == 100


def test_stub_charges_the_configured_price_for_a_price_id(monkeypatch) -> None:
    monkeypatch.setattr(settings, "price_cents", 100)
    assert stub._line_amount({"line_items": {"0": {"price": "price_x"}}}) == 100


# --- no secrets ---------------------------------------------------------------------


def test_no_endpoint_or_key_is_baked_into_the_code() -> None:
    sources = list((ZORBECK / "zorbeck_app").rglob("*.py")) + list((ZORBECK / "templates").glob("*.html"))
    sources += [ZORBECK / "app.py", ZORBECK / "README.md"]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert "n8n.cloud" not in text, path
        assert "sk_live" not in text and "sk_test_" not in text.replace("sk_test_stub", ""), path
        assert "whsec_" not in text, path
        assert "buy.stripe.com" not in text, path
