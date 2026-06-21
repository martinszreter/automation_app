from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import Booking, BookingStatus, Guest
from app.messaging.base import OutgoingMessage, WhatsAppAdapter
from app.parsing.base import Intent, ParsedMessage
from app.templates.messages import de


def _booking_vars(booking: Booking) -> dict:
    return {
        "guest_name": booking.guest.name or "Gast",
        "restaurant": booking.tenant.name,
        "date": booking.booked_at.strftime("%d.%m.%Y"),
        "time": booking.booked_at.strftime("%H:%M"),
        "party_size": booking.party_size,
    }


async def find_active_booking(db: AsyncSession, guest_phone: str) -> Booking | None:
    """Find the most recent non-terminal booking for a guest phone number."""
    active_statuses = [BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.REMINDER_SENT]
    result = await db.execute(
        select(Booking)
        .join(Guest)
        .where(Guest.phone_number == guest_phone)
        .where(Booking.status.in_(active_statuses))
        .options(joinedload(Booking.guest), joinedload(Booking.tenant))
        .order_by(Booking.booked_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def apply_action(
    db: AsyncSession,
    booking: Booking,
    parsed: ParsedMessage,
    adapter: WhatsAppAdapter,
) -> str:
    """Apply a parsed intent to a booking, send a reply, return the reply text."""
    phone = booking.guest.phone_number
    bv = _booking_vars(booking)

    if parsed.intent == Intent.CONFIRM:
        if booking.status == BookingStatus.CONFIRMED:
            reply = de.ALREADY_CONFIRMED.format(**bv)
        else:
            booking.status = BookingStatus.CONFIRMED
            reply = de.BOOKING_CONFIRMED.format(**bv)

    elif parsed.intent == Intent.CANCEL:
        if booking.status == BookingStatus.CANCELLED:
            reply = de.ALREADY_CANCELLED.format(**bv)
        else:
            booking.status = BookingStatus.CANCELLED
            reply = de.BOOKING_CANCELLED.format(**bv)

    elif parsed.intent == Intent.CHANGE_PARTY_SIZE:
        booking.party_size = parsed.party_size
        bv["party_size"] = parsed.party_size
        reply = de.PARTY_SIZE_CHANGED.format(**bv)

    else:
        reply = de.UNKNOWN_MESSAGE

    await db.commit()
    await adapter.send_message(OutgoingMessage(to_phone=phone, body=reply))
    return reply
