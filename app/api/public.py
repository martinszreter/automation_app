from pathlib import Path

from fastapi import APIRouter, Depends, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ContactRequest
from app.db.session import get_db
from app.services.contact_email import send_contact_notification

router = APIRouter(tags=["public"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@router.get("/", response_class=FileResponse, include_in_schema=False)
async def homepage() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")


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
