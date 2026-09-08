import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core import alerts
from app.core.config import settings


class _FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.text = "{}"


class _FakeClient:
    posts: list[tuple[str, dict]] = []
    status_code = 200
    fail = False

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def post(self, url: str, json: dict) -> _FakeResponse:
        if self.fail:
            raise alerts.httpx.ConnectError("down")
        _FakeClient.posts.append((url, json))
        return _FakeResponse(self.status_code)


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch) -> type[_FakeClient]:
    _FakeClient.posts = []
    _FakeClient.status_code = 200
    _FakeClient.fail = False
    monkeypatch.setattr("app.core.alerts.httpx.AsyncClient", _FakeClient)
    monkeypatch.setattr(settings, "error_alert_webhook_url", "https://startend.app.n8n.cloud/webhook/leadmine-error-7q4x9m2k")
    monkeypatch.setattr(settings, "session_https_only", True)
    return _FakeClient


def _app_that_breaks() -> FastAPI:
    app = FastAPI()
    alerts.install_error_alerts(app)

    @app.get("/boom")
    async def boom() -> dict:
        raise RuntimeError("kaputt")

    @app.get("/fine")
    async def fine() -> dict:
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_unhandled_exception_is_reported_and_answered_in_german(fake_http: type[_FakeClient]) -> None:
    transport = ASGITransport(app=_app_that_breaks(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom?x=1")

    assert response.status_code == 500
    assert "Interner Fehler" in response.text and "kaputt" not in response.text
    assert len(fake_http.posts) == 1
    url, payload = fake_http.posts[0]
    assert url.endswith("/leadmine-error-7q4x9m2k")
    assert payload["app"] == "startend-fastapi"
    assert payload["workflow"] == "/boom"
    assert payload["node"] == "GET /boom"
    assert payload["message"] == "RuntimeError: kaputt"
    assert "RuntimeError: kaputt" in payload["stack"]
    assert payload["url"] == "http://test/boom?x=1"
    assert payload["mode"] == "production"


@pytest.mark.asyncio
async def test_healthy_routes_do_not_alert(fake_http: type[_FakeClient]) -> None:
    async with AsyncClient(transport=ASGITransport(app=_app_that_breaks()), base_url="http://test") as client:
        response = await client.get("/fine")

    assert response.status_code == 200
    assert fake_http.posts == []


@pytest.mark.asyncio
async def test_alert_never_raises_when_webhook_is_down(fake_http: type[_FakeClient]) -> None:
    fake_http.fail = True
    ok = await alerts.send_error_alert(workflow="w", node="n", message="m")
    assert ok is False

    fake_http.fail = False
    fake_http.status_code = 500
    ok = await alerts.send_error_alert(workflow="w", node="n", message="m")
    assert ok is False


@pytest.mark.asyncio
async def test_alert_is_skipped_without_webhook(monkeypatch: pytest.MonkeyPatch, fake_http: type[_FakeClient]) -> None:
    monkeypatch.setattr(settings, "error_alert_webhook_url", "")
    ok = await alerts.send_error_alert(workflow="w", node="n", message="m")
    assert ok is False and fake_http.posts == []


def test_payload_is_bounded_and_mode_follows_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "session_https_only", False)
    payload = alerts.alert_payload(workflow="w", node="n", message="m" * 900, stack="s" * 9000)
    assert payload["mode"] == "development"
    assert len(payload["message"]) == 500
    assert len(payload["stack"]) == 4000
