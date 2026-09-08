"""X Autopilot panel data: calendar, metrics, pause/resume, next invoice, digest.

Posts are drafted and published by the n8n engines; this app reads what they
wrote through the panel lane (``N8N_XA_PANEL_URL``, an n8n webhook that
answers ``profile`` / ``recent_posts`` / ``set_status`` on the agents,
post_log and post_metrics tables). Every lane failure degrades to "not
available right now" — the panel never errors because n8n is slow.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from app.core.config import settings
from app.db.models import XAutopilotPlan
from app.services.stripe_checkout import StripeError, StripeNotConfigured, stripe_request
from app.templates.messages import xa_de

logger = logging.getLogger(__name__)

CALENDAR_DAYS = 7
DEFAULT_SLOTS_UTC = (time(7, 0),)  # 09:00 Zurich in summer, 08:00 in winter
MAX_DAILY_CAP = 10
_SLOT_RE = re.compile(r"^(\d{1,2})(?::(\d{2}))?$")

try:
    ZURICH = ZoneInfo("Europe/Zurich")
except ZoneInfoNotFoundError:  # slim images without tzdata
    ZURICH = timezone(timedelta(hours=1))  # type: ignore[assignment]


class PanelLaneNotConfigured(RuntimeError):
    """N8N_XA_PANEL_URL is not set."""


class PanelLaneError(RuntimeError):
    """The lane rejected the call or could not be reached."""


@dataclass
class CalendarSlot:
    at_utc: datetime
    at_local: datetime
    status: str  # "scheduled" | "paused"


@dataclass
class CalendarDay:
    day: date
    label: str
    slots: list[CalendarSlot] = field(default_factory=list)


@dataclass
class PanelData:
    agent: dict[str, Any] | None = None
    posts: list[dict[str, Any]] = field(default_factory=list)
    calendar: list[CalendarDay] = field(default_factory=list)
    scheduled_count: int = 0
    invoice: dict[str, Any] | None = None
    paused: bool = False
    lane_error: str | None = None


# --- lane --------------------------------------------------------------------


async def lane_call(action: str, **body: Any) -> dict[str, Any]:
    url = settings.n8n_xa_panel_url.strip()
    if not url:
        raise PanelLaneNotConfigured("N8N_XA_PANEL_URL is not set")
    payload = {"action": action, **body}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise PanelLaneError(f"panel lane unreachable: {exc}") from exc
    if response.status_code >= 400:
        logger.warning("panel lane %s rejected: %s %s", action, response.status_code, response.text[:300])
        raise PanelLaneError(f"panel lane responded {response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise PanelLaneError("panel lane returned no JSON") from exc
    return data if isinstance(data, dict) else {}


async def lane_profile(*, email: str, agent: str = "") -> dict[str, Any] | None:
    data = await lane_call("profile", email=email.strip().lower(), agent=agent)
    return data.get("agent") if data.get("found") else None


async def lane_recent_posts(agent: str, *, limit: int = 50) -> list[dict[str, Any]]:
    data = await lane_call("recent_posts", agent=agent, limit=limit)
    posts = data.get("posts") or []
    return [p for p in posts if isinstance(p, dict) and p.get("text")]


async def set_agent_status(agent: str, *, paused: bool) -> bool:
    data = await lane_call("set_status", agent=agent, status="paused" if paused else "active")
    return bool(data.get("ok"))


# --- calendar ----------------------------------------------------------------


def parse_slots(post_slot: Any) -> list[time]:
    """``"09:00, 13:30"`` / ``"9 13 18"`` (UTC, as the engines use) → sorted times."""
    slots: list[time] = []
    for token in re.split(r"[,\s;/]+", str(post_slot or "").strip()):
        match = _SLOT_RE.match(token)
        if not match:
            continue
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        if 0 <= hour < 24 and 0 <= minute < 60:
            slots.append(time(hour, minute))
    return sorted(set(slots)) or list(DEFAULT_SLOTS_UTC)


def build_calendar(
    *,
    now: datetime,
    slots_utc: list[time],
    daily_cap: int = 1,
    paused: bool = False,
    days: int = CALENDAR_DAYS,
) -> list[CalendarDay]:
    """The next ``days`` days, ``min(daily_cap, len(slots))`` posts per day, from tomorrow's first slot on."""
    now = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    per_day = max(1, min(int(daily_cap or 1), MAX_DAILY_CAP, len(slots_utc)))
    status = "paused" if paused else "scheduled"
    calendar: list[CalendarDay] = []
    start = (now.astimezone(ZURICH) + timedelta(days=1)).date()
    for offset in range(days):
        day = start + timedelta(days=offset)
        entries: list[CalendarSlot] = []
        for slot in slots_utc[:per_day]:
            at_utc = datetime.combine(day, slot, tzinfo=timezone.utc)
            entries.append(CalendarSlot(at_utc=at_utc, at_local=at_utc.astimezone(ZURICH), status=status))
        calendar.append(CalendarDay(day=day, label=day.strftime("%a %d.%m."), slots=entries))
    return calendar


# --- Stripe ------------------------------------------------------------------


async def upcoming_invoice(subscription_id: str | None) -> dict[str, Any] | None:
    if not subscription_id:
        return None
    try:
        invoice = await stripe_request("GET", f"/invoices/upcoming?subscription={subscription_id}")
    except (StripeNotConfigured, StripeError) as exc:
        logger.warning("upcoming invoice unavailable: %s", exc)
        return None
    due = invoice.get("next_payment_attempt") or invoice.get("period_end")
    return {
        "amount_due_cents": int(invoice.get("amount_due") or 0),
        "currency": str(invoice.get("currency") or "chf").upper(),
        "due_at": datetime.fromtimestamp(int(due), tz=timezone.utc).astimezone(ZURICH) if due else None,
    }


def format_chf(cents: int) -> str:
    """CHF 1'390 style (Swiss apostrophe thousands, no decimals when whole)."""
    francs, rappen = divmod(int(cents), 100)
    grouped = f"{francs:,}".replace(",", "'")
    return grouped if rappen == 0 else f"{grouped}.{rappen:02d}"


# --- assembly ----------------------------------------------------------------


async def load_panel_data(plan: XAutopilotPlan, *, now: datetime | None = None) -> PanelData:
    now = now or datetime.now(timezone.utc)
    data = PanelData(paused=plan.paused_at is not None)
    agent_name = (plan.agent_name or "").strip()
    try:
        profile = await lane_profile(email=plan.email, agent=agent_name)
        if profile:
            data.agent = profile
            agent_name = str(profile.get("agent_name") or agent_name)
        if agent_name:
            data.posts = await lane_recent_posts(agent_name)
    except PanelLaneNotConfigured:
        data.lane_error = None  # nothing to show, nothing to alarm about
    except PanelLaneError as exc:
        data.lane_error = str(exc)

    slots = parse_slots(data.agent.get("post_slot") if data.agent else "")
    cap = int((data.agent or {}).get("daily_cap") or 1)
    data.calendar = build_calendar(now=now, slots_utc=slots, daily_cap=cap, paused=data.paused)
    data.scheduled_count = sum(len(day.slots) for day in data.calendar)
    data.invoice = await upcoming_invoice(plan.stripe_subscription_id)
    return data


# --- weekly digest -----------------------------------------------------------


def digest_text(
    plan: XAutopilotPlan,
    posts: list[dict[str, Any]],
    *,
    scheduled: int,
    panel_url: str,
    now: datetime | None = None,
    days: int = 7,
) -> tuple[str, str]:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    recent: list[dict[str, Any]] = []
    for post in posts:
        stamp = _parse_when(post.get("posted_at"))
        if stamp is None or stamp >= since:
            recent.append(post)
    lines = [
        xa_de.DIGEST_LINE.format(
            date=_fmt_local(_parse_when(p.get("posted_at"))),
            impressions=p.get("impressions") if p.get("impressions") is not None else xa_de.DIGEST_NO_METRICS,
            likes=p.get("likes") if p.get("likes") is not None else xa_de.DIGEST_NO_METRICS,
            text=str(p.get("text") or "").strip(),
        )
        for p in recent
    ]
    period = f"{_fmt_local(since)} – {_fmt_local(now)}"
    subject = xa_de.DIGEST_SUBJECT.format(count=len(recent))
    body = xa_de.DIGEST_BODY.format(
        period=period,
        count=len(recent),
        lines="\n\n".join(lines) if lines else xa_de.DIGEST_NO_POSTS,
        scheduled=scheduled,
        status_line=xa_de.DIGEST_STATUS_PAUSED if plan.paused_at else xa_de.DIGEST_STATUS_ACTIVE,
        panel_url=panel_url,
    )
    return subject, body


def _parse_when(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _fmt_local(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone(ZURICH).strftime("%d.%m.%Y")
