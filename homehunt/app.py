# Zorbeck — landing page collecting signups for property deal alerts.
# Separate Railway service (Root Directory = homehunt), independent of app/.
import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Zorbeck")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

logger = logging.getLogger("homehunt")
logging.basicConfig(level=logging.INFO)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SIGNUP_SOURCE = "zorbeck-landing"


# Explicit HEAD alongside GET so HEAD / returns 200 directly —
# nieczytaj had uptime monitors stuck in a HEAD -> 302 redirect loop.
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


def _parse_budget(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@app.post("/signup")
async def signup(request: Request) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data: dict[str, Any] = await request.json()
        except ValueError:
            data = {}
    else:
        # Stdlib parsing keeps requirements.txt free of python-multipart.
        body = await request.body()
        data = dict(parse_qsl(body.decode("utf-8", errors="replace")))

    email = str(data.get("email") or "").strip()
    if not EMAIL_RE.match(email):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Please enter a valid email address."},
        )

    city = str(data.get("city") or "").strip()
    payload = {
        "email": email,
        "city": city or None,
        "budget_min": _parse_budget(data.get("budget_min")),
        "budget_max": _parse_budget(data.get("budget_max")),
        "source": SIGNUP_SOURCE,
    }

    webhook_url = os.environ.get("SIGNUP_WEBHOOK_URL")
    if webhook_url:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("signup webhook delivery failed")
            return JSONResponse(
                status_code=502,
                content={"ok": False, "error": "Something went wrong. Please try again."},
            )
    else:
        logger.info("SIGNUP_WEBHOOK_URL not set, logging signup only: %s", payload)

    return JSONResponse(
        content={
            "ok": True,
            "message": f"You're in. Zorbeck will email you when we cover {city or 'your city'}.",
        }
    )
