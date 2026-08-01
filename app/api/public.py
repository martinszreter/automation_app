from pathlib import Path

from fastapi import APIRouter, Depends, Form
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ContactRequest
from app.db.session import get_db
from app.services.contact_email import send_contact_notification

router = APIRouter(tags=["public"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@router.get("/", response_class=FileResponse, include_in_schema=False)
async def homepage() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")


# Same Swiss-cross mark the pages embed inline; served here so every page on
# the domain gets an icon via the browser's /favicon.ico fallback.
_FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<rect width='64' height='64' fill='#DA291C'/>"
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


@router.api_route("/x-autopilot", methods=["GET", "HEAD"], include_in_schema=False)
async def x_autopilot_no_slash() -> RedirectResponse:
    return RedirectResponse(url="/x-autopilot/", status_code=301)


@router.get("/x-autopilot/", response_class=FileResponse, include_in_schema=False)
async def x_autopilot_landing() -> FileResponse:
    return FileResponse(_STATIC_DIR / "x-autopilot" / "index.html", media_type="text/html")


@router.get("/x-autopilot/onboarding.html", response_class=FileResponse, include_in_schema=False)
async def x_autopilot_onboarding() -> FileResponse:
    return FileResponse(_STATIC_DIR / "x-autopilot" / "onboarding.html", media_type="text/html")


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
    return FileResponse(_STATIC_DIR / "thanks.html", media_type="text/html")
