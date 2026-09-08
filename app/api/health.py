from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "healthy"}


@router.get("/healthz", include_in_schema=False)
async def healthz(request: Request) -> dict:
    """Liveness alias in the shape the STARTEND ops bar and live checklist
    expect: 200 with ``{"ok": true, "app": <name>}``. Deliberately touches no
    database — it answers whenever the process serves HTTP, so a database
    outage shows up on ``/health`` (Railway's healthcheck), not here."""
    return {"ok": True, "app": request.app.title}
