import pytest
from unittest.mock import AsyncMock, MagicMock

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
async def test_contact_stores_request():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

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
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_contact_honeypot_skips_storage():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

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
    app.dependency_overrides.clear()
