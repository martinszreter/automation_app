import pytest
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides["app.db.session.get_db"] = override_get_db

    from app.db.session import get_db
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    app.dependency_overrides.clear()
