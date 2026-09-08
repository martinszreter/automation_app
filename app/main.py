from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.apps import router as apps_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.origicast import router as origicast_router
from app.api.public import router as public_router
from app.api.stripe_webhook import router as stripe_webhook_router
from app.api.webhook import router as webhook_router
from app.api.x_autopilot import router as x_autopilot_router
from app.core.config import settings
from app.services.error_alerts import report_error

app = FastAPI(title="STARTEND", version="0.2.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="xa_session",
    same_site="lax",
    https_only=settings.session_https_only,
    max_age=60 * 60 * 24 * 14,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates" / "html"))


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    """Every unhandled exception becomes one alert to the Engine Error Alerts
    workflow, then a plain 500. HTTPException never lands here."""
    await report_error(request.url.path, request.method, exc)
    return JSONResponse({"detail": "internal error"}, status_code=500)


app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(x_autopilot_router)
# The one endpoint Stripe is configured against; the per-product webhook routes
# above stay reachable and share its handlers.
app.include_router(stripe_webhook_router)
# Before the public router: its /{page}/ catch-all would otherwise shadow /apps/
# and /origicast/.
app.include_router(apps_router)
app.include_router(origicast_router)
app.include_router(public_router)
