from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.apps import router as apps_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.public import router as public_router
from app.api.webhook import router as webhook_router
from app.api.x_autopilot import router as x_autopilot_router
from app.core.config import settings

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

app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(x_autopilot_router)
# Before the public router: its /{page}/ catch-all would otherwise shadow /apps/.
app.include_router(apps_router)
app.include_router(public_router)
