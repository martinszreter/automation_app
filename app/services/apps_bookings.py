"""Local copy of what /apps collects, for the admin list.

The n8n data table (``apps_orders``) stays the commercial ledger; this table
lets /apps/admin show demo requests and setup details without a lane. Writes
are best-effort from the customer's point of view: a storage error is logged
and the customer flow continues.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppsBooking

logger = logging.getLogger(__name__)

KIND_DEMO = "demo"
KIND_SETUP = "setup"
STATUS_NEW = "new"


async def add_demo_booking(db: AsyncSession, booking: dict[str, Any]) -> AppsBooking | None:
    """Store one validated demo booking (see apps_demo.demo_booking). None when storage fails."""
    row = AppsBooking(
        kind=KIND_DEMO,
        status=STATUS_NEW,
        restaurant_name=str(booking.get("restaurant_name") or "")[:160],
        contact=str(booking.get("contact") or "")[:160] or None,
        booking_date=date.fromisoformat(booking["date"]) if booking.get("date") else None,
        booking_time=str(booking.get("time") or "")[:16] or None,
        guests=int(booking["guests"]) if booking.get("guests") is not None else None,
        note=str(booking.get("note") or "") or None,
    )
    return await _store(db, row)


async def add_setup_details(db: AsyncSession, details: dict[str, Any]) -> AppsBooking | None:
    """Store the success-page details row (restaurant, Swiss number, hours)."""
    row = AppsBooking(
        kind=KIND_SETUP,
        status=STATUS_NEW,
        restaurant_name=str(details.get("restaurant_name") or "")[:160],
        phone=str(details.get("phone") or "")[:32] or None,
        opening_hours=str(details.get("opening_hours") or "") or None,
        session_id=str(details.get("session_id") or "")[:255] or None,
    )
    return await _store(db, row)


async def list_bookings(db: AsyncSession, *, limit: int = 200) -> list[AppsBooking]:
    result = await db.execute(select(AppsBooking).order_by(AppsBooking.created_at.desc()).limit(limit))
    return list(result.scalars().all())


async def _store(db: AsyncSession, row: AppsBooking) -> AppsBooking | None:
    try:
        db.add(row)
        await db.commit()
        await db.refresh(row)
    except SQLAlchemyError as exc:
        logger.warning("apps booking not stored locally: %s", exc)
        try:
            await db.rollback()
        except SQLAlchemyError:
            pass
        return None
    return row
