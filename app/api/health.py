from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness: the app and its database answer."""
    await db.execute(text("SELECT 1"))
    return {"status": "healthy"}


@router.get("/healthz", include_in_schema=False)
async def liveness() -> JSONResponse:
    """Liveness: the process serves requests. Touches nothing, so a database
    outage shows up as /health red while /healthz stays green — which is the
    distinction an alert needs."""
    return JSONResponse({"status": "ok"}, headers={"Cache-Control": "no-store"})
