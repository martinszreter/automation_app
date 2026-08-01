import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.db.session import get_db


def _client_with_mock_db(mock_session: AsyncMock) -> AsyncClient:
    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_homepage_serves_index_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "No Human" in response.text
    assert "Bahnhofstrasse 7, 6330 Cham" in response.text
    assert "CHE-223.488.613" in response.text


@pytest.mark.asyncio
async def test_x_autopilot_landing_serves_index_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/x-autopilot/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "X Autopilot" in response.text
    assert "Your X account, on autopilot." in response.text


@pytest.mark.asyncio
async def test_x_autopilot_onboarding_serves_onboarding_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/x-autopilot/onboarding.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Now let's capture your voice." in response.text


@pytest.mark.asyncio
async def test_x_autopilot_without_slash_redirects():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/x-autopilot")

    assert response.status_code == 301
    assert response.headers["location"] == "/x-autopilot/"


@pytest.mark.asyncio
async def test_x_autopilot_without_slash_redirects_on_head():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.head("/x-autopilot")

    assert response.status_code == 301
    assert response.headers["location"] == "/x-autopilot/"


@pytest.mark.asyncio
async def test_grokywood_landing_serves_index_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/grokywood/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Grokywood" in response.text


@pytest.mark.asyncio
async def test_grokywood_without_slash_redirects():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/grokywood")

    assert response.status_code == 301
    assert response.headers["location"] == "/grokywood/"


@pytest.mark.asyncio
async def test_favicon_serves_svg_with_long_cache():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "#DA291C" in response.text


@pytest.mark.asyncio
async def test_contact_stores_request_and_sends_email():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with patch("app.api.public.send_contact_notification", new_callable=AsyncMock) as mock_notify:
        async with _client_with_mock_db(mock_session) as client:
            response = await client.post(
                "/contact",
                data={
                    "name": "Anna",
                    "company": "ACME AG",
                    "email": "anna@example.com",
                    "interest": "enterprise",
                    "message": "Hello",
                    "call_requested": "yes",
                    "website": "",
                },
            )

    assert response.status_code == 200
    assert "Thank you" in response.text
    mock_session.add.assert_called_once()
    stored = mock_session.add.call_args.args[0]
    assert stored.name == "Anna"
    assert stored.email == "anna@example.com"
    assert stored.call_requested is True
    mock_session.commit.assert_awaited_once()
    mock_notify.assert_awaited_once_with(stored)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_contact_honeypot_skips_storage_and_email():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with patch("app.api.public.send_contact_notification", new_callable=AsyncMock) as mock_notify:
        async with _client_with_mock_db(mock_session) as client:
            response = await client.post(
                "/contact",
                data={
                    "name": "Bot",
                    "email": "bot@spam.com",
                    "message": "spam",
                    "website": "http://spam.example",
                },
            )

    assert response.status_code == 200
    assert "Thank you" in response.text
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_awaited()
    mock_notify.assert_not_awaited()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_contact_smtp_failure_still_stores_and_thanks():
    """Email must never break the form: SMTP errors are logged and swallowed."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    smtp_settings = {
        "smtp_host": "smtp.example.com",
        "smtp_user": "noreply@example.com",
        "smtp_pass": "secret",
        "contact_to": "inbox@example.com",
    }
    with (
        patch.multiple("app.services.contact_email.settings", **smtp_settings),
        patch(
            "app.services.contact_email._send_sync",
            side_effect=ConnectionRefusedError("SMTP down"),
        ),
    ):
        async with _client_with_mock_db(mock_session) as client:
            response = await client.post(
                "/contact",
                data={
                    "name": "Anna",
                    "email": "anna@example.com",
                    "message": "Hello",
                    "website": "",
                },
            )

    assert response.status_code == 200
    assert "Thank you" in response.text
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_contact_email_message_content():
    """The notification email carries all form fields."""
    from app.db.models import ContactRequest
    from app.services.contact_email import _build_message

    contact = ContactRequest(
        name="Anna",
        company="ACME AG",
        email="anna@example.com",
        interest="enterprise",
        message="Hello there",
        call_requested=True,
    )
    smtp_settings = {
        "smtp_user": "noreply@example.com",
        "contact_to": "inbox@example.com",
    }
    with patch.multiple("app.services.contact_email.settings", **smtp_settings):
        msg = _build_message(contact)

    assert msg["From"] == "noreply@example.com"
    assert msg["To"] == "inbox@example.com"
    assert msg["Subject"] == "New contact: Anna — enterprise"
    body = msg.get_content()
    for expected in ["Anna", "ACME AG", "anna@example.com", "enterprise", "yes", "Hello there"]:
        assert expected in body
