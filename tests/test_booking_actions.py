import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.db.models import Booking, BookingStatus, Guest, Tenant
from app.messaging.mock_adapter import MockWhatsAppAdapter
from app.parsing.base import Intent, ParsedMessage
from app.services.booking_actions import apply_action


def _make_booking(status: BookingStatus = BookingStatus.PENDING, party_size: int = 4) -> Booking:
    tenant = Tenant(id=uuid.uuid4(), name="Testrestaurant", phone_number="+4900000000")
    guest = Guest(id=uuid.uuid4(), phone_number="+491111111111", name="Max Mustermann")
    booking = Booking(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        guest_id=guest.id,
        party_size=party_size,
        booked_at=datetime.now() + timedelta(days=1),
        status=status,
    )
    booking.tenant = tenant
    booking.guest = guest
    return booking


@pytest.mark.asyncio
async def test_confirm_booking() -> None:
    db = AsyncMock()
    adapter = MockWhatsAppAdapter()
    booking = _make_booking(BookingStatus.PENDING)

    await apply_action(db, booking, ParsedMessage(intent=Intent.CONFIRM), adapter)

    assert booking.status == BookingStatus.CONFIRMED
    assert len(adapter.sent) == 1
    assert "bestätigt" in adapter.sent[0].body
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_booking() -> None:
    db = AsyncMock()
    adapter = MockWhatsAppAdapter()
    booking = _make_booking(BookingStatus.CONFIRMED)

    await apply_action(db, booking, ParsedMessage(intent=Intent.CANCEL), adapter)

    assert booking.status == BookingStatus.CANCELLED
    assert len(adapter.sent) == 1
    assert "storniert" in adapter.sent[0].body


@pytest.mark.asyncio
async def test_change_party_size() -> None:
    db = AsyncMock()
    adapter = MockWhatsAppAdapter()
    booking = _make_booking(BookingStatus.CONFIRMED, party_size=4)

    await apply_action(db, booking, ParsedMessage(intent=Intent.CHANGE_PARTY_SIZE, party_size=6), adapter)

    assert booking.party_size == 6
    assert len(adapter.sent) == 1
    assert "6" in adapter.sent[0].body


@pytest.mark.asyncio
async def test_already_confirmed() -> None:
    db = AsyncMock()
    adapter = MockWhatsAppAdapter()
    booking = _make_booking(BookingStatus.CONFIRMED)

    await apply_action(db, booking, ParsedMessage(intent=Intent.CONFIRM), adapter)

    assert booking.status == BookingStatus.CONFIRMED
    assert "bereits bestätigt" in adapter.sent[0].body


@pytest.mark.asyncio
async def test_already_cancelled() -> None:
    db = AsyncMock()
    adapter = MockWhatsAppAdapter()
    booking = _make_booking(BookingStatus.CANCELLED)

    await apply_action(db, booking, ParsedMessage(intent=Intent.CANCEL), adapter)

    assert booking.status == BookingStatus.CANCELLED
    assert "bereits storniert" in adapter.sent[0].body


@pytest.mark.asyncio
async def test_unknown_intent() -> None:
    db = AsyncMock()
    adapter = MockWhatsAppAdapter()
    booking = _make_booking()

    await apply_action(db, booking, ParsedMessage(intent=Intent.UNKNOWN), adapter)

    assert len(adapter.sent) == 1
    assert "nicht verstanden" in adapter.sent[0].body
