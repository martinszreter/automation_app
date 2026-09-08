"""Unhandled 5xx -> one alert to the Engine Error Alerts webhook, then a 500."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services.error_alerts import build_alert, report_error

_boom = APIRouter()


@_boom.get("/_test/boom", include_in_schema=False)
async def boom() -> None:
    raise RuntimeError("kaboom")


app.include_router(_boom)


def test_alert_carries_the_diagnosis_and_nothing_personal() -> None:
    alert = build_alert(path="/origicast/checkout", method="post", error=RuntimeError("x" * 900))
    assert alert["service"] == settings.service_name
    assert alert["path"] == "/origicast/checkout"
    assert alert["method"] == "POST"
    assert alert["status"] == 500
    assert alert["error"].startswith("RuntimeError: xxx")
    assert len(alert["error"]) < 700
    assert set(alert) == {"service", "path", "method", "status", "error", "ts"}


@pytest.mark.asyncio
async def test_report_is_skipped_when_no_webhook_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "error_alert_webhook_url", "")
    assert await report_error("/x", "GET", RuntimeError("x")) is False


@pytest.mark.asyncio
async def test_report_posts_json_to_the_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "error_alert_webhook_url", "https://example.invalid/hook")
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["json"] = request.read()
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    with patch("app.services.error_alerts.httpx.AsyncClient", client_factory):
        assert await report_error("/x", "GET", RuntimeError("bad")) is True
    assert seen["url"] == "https://example.invalid/hook"
    assert b'"RuntimeError: bad"' in seen["json"]


@pytest.mark.asyncio
async def test_report_never_raises_when_the_webhook_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "error_alert_webhook_url", "https://example.invalid/hook")

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    real_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    with patch("app.services.error_alerts.httpx.AsyncClient", client_factory):
        assert await report_error("/x", "GET", RuntimeError("bad")) is False


@pytest.mark.asyncio
async def test_unhandled_exception_alerts_and_answers_500() -> None:
    report = AsyncMock(return_value=True)
    with patch("app.main.report_error", report):
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            response = await client.get("/_test/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}
    path, method, error = report.await_args.args
    assert (path, method) == ("/_test/boom", "GET")
    assert isinstance(error, RuntimeError)
