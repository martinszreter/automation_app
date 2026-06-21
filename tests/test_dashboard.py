import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Booking, BookingStatus, Guest, Tenant
from app.db.session import get_db
from app.main import app


def _make_booking() -> Booking:
    tenant = Tenant(id=uuid.uuid4(), name="Testrestaurant", phone_number="+4900000000")
    guest = Guest(id=uuid.uuid4(), phone_number="+491111111111", name="Max Mustermann")
    booking = Booking(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        guest_id=guest.id,
        party_size=4,
        booked_at=datetime.now() + timedelta(hours=3),
        status=BookingStatus.CONFIRMED,
    )
    booking.tenant = tenant
    booking.guest = guest
    return booking


@pytest.mark.asyncio
async def test_dashboard_loads() -> None:
    booking = _make_booking()

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.unique.return_value.all.return_value = [booking]
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/dashboard")

        assert response.status_code == 200
        assert "Max Mustermann" in response.text
        assert "Testrestaurant" in response.text
        assert "Confirmed" in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_empty() -> None:
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.unique.return_value.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/dashboard")

        assert response.status_code == 200
        assert "Keine kommenden Reservierungen" in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bookings_table_partial() -> None:
    booking = _make_booking()

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.unique.return_value.all.return_value = [booking]
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/dashboard/bookings-table")

        assert response.status_code == 200
        assert "<table>" in response.text
        assert "Max Mustermann" in response.text
    finally:
        app.dependency_overrides.clear()
