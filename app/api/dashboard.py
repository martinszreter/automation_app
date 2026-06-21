from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import Booking
from app.db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(Booking)
        .where(Booking.booked_at >= today)
        .options(joinedload(Booking.guest), joinedload(Booking.tenant))
        .order_by(Booking.booked_at.asc())
    )
    bookings = result.scalars().unique().all()

    from app.main import templates
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"bookings": bookings, "now": datetime.now()},
    )


@router.get("/bookings-table", response_class=HTMLResponse)
async def bookings_table(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """HTMX partial: returns just the bookings table body for polling."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(Booking)
        .where(Booking.booked_at >= today)
        .options(joinedload(Booking.guest), joinedload(Booking.tenant))
        .order_by(Booking.booked_at.asc())
    )
    bookings = result.scalars().unique().all()

    from app.main import templates
    return templates.TemplateResponse(
        request=request,
        name="partials/bookings_table.html",
        context={"bookings": bookings},
    )
