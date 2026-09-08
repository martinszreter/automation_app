import pytest

from app.core.config import settings
from app.services import hq_mail


@pytest.mark.asyncio
async def test_send_hq_mail_requires_webhook_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "hq_mail_webhook_url", "")
    with pytest.raises(hq_mail.HQMailNotConfigured):
        await hq_mail.send_hq_mail("subject", "body")


@pytest.mark.asyncio
async def test_send_hq_mail_posts_subject_and_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "hq_mail_webhook_url", "https://startend.app.n8n.cloud/webhook/hq-mail-9k2x7m4q")

    class FakeResponse:
        status_code = 200
        text = "{}"

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args) -> bool:
            return False

        async def post(self, url: str, json: dict) -> FakeResponse:
            assert url == "https://startend.app.n8n.cloud/webhook/hq-mail-9k2x7m4q"
            assert json == {"subject": "Reconnect Sheets", "body": "please reconnect"}
            return FakeResponse()

    monkeypatch.setattr("app.services.hq_mail.httpx.AsyncClient", FakeClient)
    await hq_mail.send_hq_mail("Reconnect Sheets", "please reconnect")


@pytest.mark.asyncio
async def test_send_hq_mail_includes_optional_recipient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "hq_mail_webhook_url", "https://startend.app.n8n.cloud/webhook/hq-mail-9k2x7m4q")

    class FakeResponse:
        status_code = 200
        text = "{}"

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args) -> bool:
            return False

        async def post(self, url: str, json: dict) -> FakeResponse:
            assert json["to"] == "marcin@startend.ch"
            return FakeResponse()

    monkeypatch.setattr("app.services.hq_mail.httpx.AsyncClient", FakeClient)
    await hq_mail.send_hq_mail("subject", "body", to="marcin@startend.ch")


@pytest.mark.asyncio
async def test_send_hq_mail_raises_on_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "hq_mail_webhook_url", "https://startend.app.n8n.cloud/webhook/hq-mail-9k2x7m4q")

    class FakeResponse:
        status_code = 500
        text = "boom"

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args) -> bool:
            return False

        async def post(self, url: str, json: dict) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.services.hq_mail.httpx.AsyncClient", FakeClient)
    with pytest.raises(hq_mail.HQMailError):
        await hq_mail.send_hq_mail("subject", "body")
