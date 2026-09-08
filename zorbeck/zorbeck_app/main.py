"""Zorbeck routes: landing, checkout, success, Stripe webhook, legal, health."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from zorbeck_app import stub
from zorbeck_app.alerts import send_alert
from zorbeck_app.config import settings
from zorbeck_app.intake import Intake, IntakeError, confirmation_mail, intake_from_session, parse_intake
from zorbeck_app.mail import MailError, MailNotConfigured, send_mail
from zorbeck_app.messages import de
from zorbeck_app.money import chf
from zorbeck_app.stripe_api import (
    StripeError,
    StripeNotConfigured,
    StripeSignatureError,
    create_checkout_session,
    retrieve_checkout_session,
    session_is_paid,
    verify_stripe_signature,
)

BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger("zorbeck")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Zorbeck", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

if settings.stub:
    app.include_router(stub.router)

CHECKOUT_COMPLETED = "checkout.session.completed"

LEGAL = {
    "company": "STARTEND GmbH",
    "uid": "CHE-223.488.613",
    "street": "Bahnhofstrasse 7",
    "city": "6330 Cham",
    "email": "info@startend.ch",
}


# --- helpers -------------------------------------------------------------------


def base_url_for(request: Request) -> str:
    if settings.public_base_url:
        return settings.public_base_url
    proto = request.headers.get("x-forwarded-proto")
    host = request.headers.get("x-forwarded-host")
    if proto and host:
        return f"{proto.split(',')[0].strip()}://{host.split(',')[0].strip()}"
    return str(request.base_url).rstrip("/")


def render(request: Request, name: str, status_code: int = 200, **context: Any) -> HTMLResponse:
    context.setdefault("legal", LEGAL)
    context.setdefault("price_label", chf(settings.price_cents))
    context.setdefault("de", de)
    return templates.TemplateResponse(request, name, context, status_code=status_code)


async def form_data(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
    body = await request.body()
    # Stdlib parsing keeps requirements.txt free of python-multipart.
    return dict(parse_qsl(body.decode("utf-8", errors="replace")))


async def post_lead(intake: Intake, **extra: Any) -> None:
    """Lead row to n8n (SIGNUP_WEBHOOK_URL). Best effort: a lost row is alerted, never shown."""
    if not settings.signup_webhook_url:
        logger.info("SIGNUP_WEBHOOK_URL not set, lead only logged: %s", intake.as_row(**extra))
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.signup_webhook_url, json=intake.as_row(**extra))
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.exception("lead row delivery failed")
        await send_alert("post_lead", "lead row not stored", description=str(exc), exc=exc)


# --- errors -------------------------------------------------------------------


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> HTMLResponse:
    logger.exception("unhandled error on %s", request.url.path)
    await send_alert(request.url.path, f"{type(exc).__name__}: {exc}", exc=exc, url=str(request.url))
    return render(request, "error.html", status_code=500, message=de.ERROR_SERVER)


# --- pages --------------------------------------------------------------------


# Explicit HEAD alongside GET so HEAD / returns 200 directly —
# nieczytaj had uptime monitors stuck in a HEAD -> 302 redirect loop.
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    cancelled = request.query_params.get("abgebrochen") == "1"
    return render(request, "index.html", cancelled=cancelled, values={}, error=None)


@app.get("/impressum", response_class=HTMLResponse)
async def impressum(request: Request) -> HTMLResponse:
    return render(request, "impressum.html")


@app.get("/agb", response_class=HTMLResponse)
async def agb(request: Request) -> HTMLResponse:
    return render(request, "agb.html")


@app.get("/datenschutz", response_class=HTMLResponse)
async def datenschutz(request: Request) -> HTMLResponse:
    return render(request, "datenschutz.html")


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots() -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nAllow: /\nDisallow: /danke\nDisallow: /_stub/\n")


# --- health -------------------------------------------------------------------


def health_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "zorbeck",
        "stripe": bool(settings.stripe_secret_key),
        "webhook_secret": bool(settings.stripe_webhook_secret),
        "mail": bool(settings.hq_mail_webhook_url),
        "alerts": bool(settings.alert_webhook_url),
        "stub": settings.stub,
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    return health_payload()


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return health_payload()


# --- checkout -----------------------------------------------------------------


@app.post("/checkout")
async def checkout(request: Request) -> Response:
    data = await form_data(request)
    try:
        intake = parse_intake(data)
    except IntakeError as exc:
        # 200, not 422: the browser logs a console error for any 4xx document,
        # and a typo in the form is not an error of the page.
        return render(request, "index.html", cancelled=False, values=data, error=exc.message)

    await post_lead(intake, status="checkout_started")
    try:
        session = await create_checkout_session(base_url_for(request), intake.email, intake.metadata())
    except StripeNotConfigured:
        logger.error("checkout requested but STRIPE_SECRET_KEY is not set")
        return render(
            request, "index.html", status_code=503, cancelled=False, values=data, error=de.ERROR_PAYMENT_UNAVAILABLE
        )
    except StripeError as exc:
        await send_alert("checkout", "Stripe checkout session failed", description=str(exc), exc=exc)
        return render(request, "index.html", status_code=502, cancelled=False, values=data, error=de.ERROR_PAYMENT_FAILED)
    return RedirectResponse(session["url"], status_code=303)


@app.get("/danke", response_class=HTMLResponse)
async def danke(request: Request) -> HTMLResponse:
    session_id = request.query_params.get("session_id", "").strip()
    session: dict[str, Any] | None = None
    if session_id:
        try:
            session = await retrieve_checkout_session(session_id)
        except (StripeNotConfigured, StripeError) as exc:
            logger.warning("success page could not load session %s: %s", session_id[:40], exc)
    if session is None:
        return render(request, "danke.html", status_code=404, state="unknown", intake=None, amount=None)
    if not session_is_paid(session):
        return render(request, "danke.html", status_code=202, state="pending", intake=None, amount=None)
    intake = intake_from_session(session)
    amount = chf(int(session.get("amount_total") or settings.price_cents))
    return render(request, "danke.html", state="paid", intake=intake, amount=amount, session_id=session_id)


# --- Stripe webhook --------------------------------------------------------------


async def handle_checkout_completed(session: dict[str, Any], base_url: str) -> Response:
    if not session_is_paid(session):
        return JSONResponse({"received": True, "ignored": True})
    intake = intake_from_session(session)
    amount_cents = int(session.get("amount_total") or settings.price_cents)
    await post_lead(intake, status="paid", session_id=str(session.get("id") or ""), amount_cents=amount_cents)
    subject, body = confirmation_mail(intake, amount_cents, base_url)
    try:
        await send_mail(subject, body, intake.email)
    except MailNotConfigured:
        logger.error("HQ_MAIL_WEBHOOK_URL not set; confirmation for %s only logged", intake.email)
        await send_alert("webhook.mail", "HQ_MAIL_WEBHOOK_URL not set — buyer got no confirmation")
        return JSONResponse({"received": True, "mailed": False})
    except MailError as exc:
        await send_alert("webhook.mail", "confirmation mail failed", description=str(exc), exc=exc)
        # 503 makes Stripe retry the event, so the buyer still gets the mail.
        return JSONResponse({"received": False, "error": "mail"}, status_code=503)
    return JSONResponse({"received": True, "mailed": True})


@app.post("/stripe/webhook", include_in_schema=False)
async def stripe_webhook(request: Request) -> Response:
    payload = await request.body()
    try:
        verify_stripe_signature(payload, request.headers.get("stripe-signature", ""), settings.stripe_webhook_secret)
    except StripeSignatureError as exc:
        logger.warning("Stripe webhook signature rejected: %s", exc)
        return JSONResponse({"error": "invalid signature"}, status_code=400)
    try:
        event = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JSONResponse({"error": "invalid payload"}, status_code=400)
    if not isinstance(event, dict):
        return JSONResponse({"error": "invalid payload"}, status_code=400)
    if event.get("type") != CHECKOUT_COMPLETED:
        return JSONResponse({"received": True})
    obj = (event.get("data") or {}).get("object")
    if not isinstance(obj, dict):
        return JSONResponse({"error": "invalid payload"}, status_code=400)
    return await handle_checkout_completed(obj, base_url_for(request))


# --- legacy free signup (wave 1 form) -----------------------------------------


@app.post("/signup")
async def signup(request: Request) -> JSONResponse:
    data = await form_data(request)
    try:
        intake = parse_intake({**data, "city": data.get("city") or "-"})
    except IntakeError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": exc.message})
    await post_lead(intake, status="signup")
    return JSONResponse({"ok": True, "message": de.SIGNUP_OK.format(city=intake.city if intake.city != "-" else "Ihrer Stadt")})
