from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ContactRequest
from app.db.session import get_db
from app.services.contact_email import send_contact_notification

router = APIRouter(tags=["public"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@router.get("/", response_class=FileResponse, include_in_schema=False)
async def homepage() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")


# Same offset-cross mark the pages embed inline; served here so every page on
# the domain gets an icon via the browser's /favicon.ico fallback.
_FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<path d='M16 0H64V48H48V64H0V16H16Z' fill='#DA291C'/>"
    "<rect x='26' y='12' width='12' height='40' fill='#fff'/>"
    "<rect x='12' y='26' width='40' height='12' fill='#fff'/>"
    "</svg>"
)


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(
        content=_FAVICON_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )



# --- /x-autopilot/ traffic counter -------------------------------------------
# Same shape as the pv object in nieczytaj/server.js: an in-process counter with
# a running total and a rolling window of per-day buckets. No storage, no
# library — it resets when the process restarts, exactly like nieczytaj.
_XA_TZ = ZoneInfo("Europe/Zurich")
_XA_DAYS_KEPT = 30
_XA_UTM_KEYS_KEPT = 50
_XA_TEARDOWN_INTEREST = "x-autopilot-teardown"


def _xa_bucket() -> dict:
    return {"total": 0, "days": {}, "utm_source": {}, "utm_campaign": {}}


_XA_STATS: dict = {
    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    # Counted separately so paid traffic can be read end to end:
    # landing view -> Stripe button click -> teardown email sent.
    "views": _xa_bucket(),
    "stripe_clicks": _xa_bucket(),
    "emails": _xa_bucket(),
}


def _xa_day() -> str:
    return datetime.now(_XA_TZ).strftime("%Y-%m-%d")


def _xa_utm(value: str | None) -> str:
    # Values come straight off the query string: clamp them so a crawler
    # cannot grow the counter without bound.
    return (value or "none").strip()[:40] or "none"


def _xa_tally(breakdown: dict, value: str) -> None:
    if value not in breakdown and len(breakdown) >= _XA_UTM_KEYS_KEPT:
        value = "other"
    breakdown[value] = breakdown.get(value, 0) + 1


def _xa_count(bucket_name: str, utm_source: str | None = None, utm_campaign: str | None = None) -> None:
    bucket = _XA_STATS[bucket_name]
    bucket["total"] += 1
    day = _xa_day()
    bucket["days"][day] = bucket["days"].get(day, 0) + 1
    _xa_tally(bucket["utm_source"], _xa_utm(utm_source))
    _xa_tally(bucket["utm_campaign"], _xa_utm(utm_campaign))
    days = sorted(bucket["days"])
    while len(days) > _XA_DAYS_KEPT:
        del bucket["days"][days.pop(0)]


@router.api_route("/x-autopilot", methods=["GET", "HEAD"], include_in_schema=False)
async def x_autopilot_no_slash() -> RedirectResponse:
    return RedirectResponse(url="/x-autopilot/", status_code=301)


@router.get("/x-autopilot/", response_class=FileResponse, include_in_schema=False)
async def x_autopilot_landing(request: Request) -> FileResponse:
    _xa_count(
        "views",
        utm_source=request.query_params.get("utm_source"),
        utm_campaign=request.query_params.get("utm_campaign"),
    )
    return FileResponse(
        _STATIC_DIR / "x-autopilot" / "index.html",
        media_type="text/html",
        # Every view has to reach the counter, so the page is never cached.
        headers={"Cache-Control": "no-store"},
    )


@router.post("/x-autopilot/event", include_in_schema=False)
async def x_autopilot_event(
    event: str = Form(...),
    utm_source: str = Form(""),
    utm_campaign: str = Form(""),
) -> Response:
    """Beacon from the landing page. Only the Stripe button reports here —
    teardown emails are counted server-side in POST /contact."""
    if event != "stripe":
        raise HTTPException(status_code=404)
    _xa_count("stripe_clicks", utm_source=utm_source, utm_campaign=utm_campaign)
    return Response(status_code=204)


@router.get("/x-autopilot/stats.json", include_in_schema=False)
async def x_autopilot_stats() -> JSONResponse:
    return JSONResponse(
        content=_XA_STATS,
        headers={
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@router.get("/x-autopilot/onboarding.html", response_class=FileResponse, include_in_schema=False)
async def x_autopilot_onboarding() -> FileResponse:
    return FileResponse(_STATIC_DIR / "x-autopilot" / "onboarding.html", media_type="text/html")


@router.api_route("/grokywood", methods=["GET", "HEAD"], include_in_schema=False)
async def grokywood_no_slash() -> RedirectResponse:
    return RedirectResponse(url="/grokywood/", status_code=301)


@router.get("/grokywood/", response_class=FileResponse, include_in_schema=False)
async def grokywood_landing() -> FileResponse:
    return FileResponse(_STATIC_DIR / "grokywood" / "index.html", media_type="text/html")


@router.post("/contact", response_class=FileResponse)
async def contact(
    name: str = Form(...),
    company: str = Form(""),
    email: str = Form(...),
    interest: str = Form(""),
    message: str = Form(...),
    call_requested: str = Form(""),
    website: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    # Honeypot: real users never fill the hidden "website" field — drop silently.
    if not website.strip():
        contact_request = ContactRequest(
            name=name,
            company=company or None,
            email=email,
            interest=interest or None,
            message=message,
            call_requested=bool(call_requested),
        )
        db.add(contact_request)
        await db.commit()
        await send_contact_notification(contact_request)
        if interest == _XA_TEARDOWN_INTEREST:
            _xa_count("emails")
    return FileResponse(_STATIC_DIR / "thanks.html", media_type="text/html")


# CANON_GENERIC_LANDING — the Railway start command (HOME_PY env var) injects a
# route under this marker at boot unless the marker already exists in this file.
# Keeping the route here pins it after every specific route above, so it can only
# match pages that nothing else claims. {page} cannot contain "/", so only
# first-level directories under static/ are reachable.
@router.api_route("/{page}", methods=["GET", "HEAD"], include_in_schema=False)
async def generic_landing_no_slash(page: str) -> RedirectResponse:
    if (_STATIC_DIR / page / "index.html").is_file():
        return RedirectResponse(url=f"/{page}/", status_code=301)
    raise HTTPException(status_code=404)


@router.get("/{page}/", response_class=FileResponse, include_in_schema=False)
async def generic_landing(page: str) -> FileResponse:
    index = _STATIC_DIR / page / "index.html"
    if index.is_file():
        return FileResponse(index, media_type="text/html")
    raise HTTPException(status_code=404)
