import logging

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.apps import router as apps_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.public import router as public_router
from app.api.stripe_webhook import router as stripe_webhook_router
from app.api.webhook import router as webhook_router
from app.api.x_autopilot import router as x_autopilot_router
from app.core.alerts import install_error_alerts
from app.core.config import DEV_SESSION_SECRET, settings
from app.core.templating import templates

__all__ = ["app", "templates"]

logger = logging.getLogger(__name__)

if settings.session_secret == DEV_SESSION_SECRET:
    # Loud rather than fatal: local runs are fine with it, production is not.
    logger.warning("SESSION_SECRET is the development default; set it before going live")

app = FastAPI(title="STARTEND", version="0.2.0")
install_error_alerts(app)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="xa_session",
    same_site="lax",
    https_only=settings.session_https_only,
    max_age=60 * 60 * 24 * 14,
)

app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(x_autopilot_router)
# The one endpoint Stripe is configured against; the per-product webhook routes
# above stay reachable and share its handlers.
app.include_router(stripe_webhook_router)
# Before the public router: its /{page}/ catch-all would otherwise shadow /apps/.
app.include_router(apps_router)
app.include_router(public_router)
