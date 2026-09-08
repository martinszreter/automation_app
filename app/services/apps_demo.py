"""/apps/demo — a prospect books a live WhatsApp reservation demo.

Pure validation and mail rendering. The route sends the rendered mail through
HQ Mail to the HQ inbox only: the form never chooses a recipient, so the public
page cannot be used as a mail relay.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.templates.messages import apps_de

MAX_GUESTS = 50
_TEXT_MAX = 160
_NOTE_MAX = 500
_TIME_MAX = 16

try:
    ZURICH: tzinfo = ZoneInfo("Europe/Zurich")
except ZoneInfoNotFoundError:  # slim images without tzdata
    ZURICH = timezone(timedelta(hours=1))


def today_in_zurich() -> date:
    return datetime.now(ZURICH).date()


def _squash(value: str) -> str:
    return " ".join(str(value or "").split())


def demo_booking(
    restaurant_name: str,
    contact: str,
    booking_date: str,
    booking_time: str,
    guests: str | int,
    note: str = "",
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Validate and normalize one demo booking; ValueError names the bad field."""
    name = _squash(restaurant_name)
    if not name:
        raise ValueError("restaurant_name is required")

    who = _squash(contact)
    if len(who) < 5 or not ("@" in who or any(ch.isdigit() for ch in who)):
        raise ValueError("contact must be an email address or phone number")

    try:
        day = date.fromisoformat(str(booking_date or "").strip())
    except ValueError as exc:
        raise ValueError("date is invalid") from exc
    if day < (today or today_in_zurich()):
        raise ValueError("date is in the past")

    try:
        count = int(str(guests or "").strip())
    except ValueError as exc:
        raise ValueError("guests must be a number") from exc
    if not 1 <= count <= MAX_GUESTS:
        raise ValueError(f"guests must be between 1 and {MAX_GUESTS}")

    return {
        "restaurant_name": name[:_TEXT_MAX],
        "contact": who[:_TEXT_MAX],
        "date": day.isoformat(),
        "time": _squash(booking_time)[:_TIME_MAX],
        "guests": count,
        "note": _squash(note)[:_NOTE_MAX],
        "created_at": datetime.now(ZURICH).isoformat(timespec="seconds"),
    }


def demo_mail(booking: dict[str, Any]) -> tuple[str, str]:
    """(subject, body) for the HQ inbox, from the German template layer."""
    fields = {
        "restaurant": booking["restaurant_name"],
        "contact": booking["contact"],
        "date": booking["date"],
        "time": booking["time"] or "—",
        "guests": booking["guests"],
        "note": booking["note"] or "—",
    }
    return apps_de.DEMO_MAIL_SUBJECT.format(**fields), apps_de.DEMO_MAIL_BODY.format(**fields)
