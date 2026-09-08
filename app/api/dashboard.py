from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.templating import render
from app.db.models import Booking
from app.db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# The restaurants are Swiss; "today" is their today, not the container's.
_TZ = ZoneInfo("Europe/Zurich")


def _start_of_today() -> datetime:
    return datetime.now(_TZ).replace(hour=0, minute=0, second=0, microsecond=0)


async def _bookings_from_today(db: AsyncSession) -> list[Booking]:
    """Today's and upcoming bookings with guest and tenant already loaded."""
    result = await db.execute(
        select(Booking)
        .where(Booking.booked_at >= _start_of_today())
        .options(joinedload(Booking.guest), joinedload(Booking.tenant))
        .order_by(Booking.booked_at.asc())
    )
    return list(result.scalars().unique().all())


@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    bookings = await _bookings_from_today(db)
    return render(request, "dashboard.html", bookings=bookings, now=datetime.now(_TZ))


@router.get("/bookings-table", response_class=HTMLResponse)
async def bookings_table(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """HTMX partial: returns just the bookings table body for polling."""
    bookings = await _bookings_from_today(db)
    return render(request, "partials/bookings_table.html", bookings=bookings)
