from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.webhook import router as webhook_router

app = FastAPI(title="STARTEND", version="0.2.0")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates" / "html"))

app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(dashboard_router)
