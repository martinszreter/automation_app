"""/origicast — the 21+ door.

Flow:

    GET  /origicast/            age gate (or straight to the door once confirmed)
    POST /origicast/gate        answer=yes -> session flag -> /origicast/door
                                answer=no  -> /origicast/leave
    GET  /origicast/door        the door: CHF 1 test; Season / Hour / Keep only
                                when ORIGICAST_LIVE is set
    POST /origicast/checkout    -> Stripe Checkout, CHF 1.00, payment mode
    GET  /origicast/success     confirmation (never calls Stripe)
    GET  /origicast/leave       under 21

The age answer lives in the signed session cookie the app already uses
(SessionMiddleware): functional only, no tracking. The Stripe transport is
the shared helper in ``app.services.stripe_checkout``; the unified
``/stripe/webhook`` hands ``checkout.session.completed`` for this venture to
:func:`handle_checkout_completed`, which mails HQ so the CHF 1 can be
refunded.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.core.config import settings
from app.services.hq_mail import HQMailError, HQMailNotConfigured, send_hq_mail
from app.services.stripe_checkout import (
    StripeError,
    StripeNotConfigured,
    public_base_url,
    session_email,
    stripe_request,
)
from app.templates.messages import origicast_de as t

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/origicast", tags=["origicast"])

VENTURE = "origicast"
SESSION_KEY = "origicast_21"
_SESSION_ID_MAX = 160


def _base_url(request: Request) -> str:
    return public_base_url(
        str(request.base_url),
        request.headers.get("x-forwarded-proto"),
        request.headers.get("x-forwarded-host") or request.headers.get("host"),
    )


def _render(name: str, request: Request, status_code: int = 200, **context: Any) -> HTMLResponse:
    from app.main import templates

    response = templates.TemplateResponse(
        request=request, name=f"origicast/{name}", context={"t": t, **context}
    )
    response.status_code = status_code
    # Every page differs by session state; never let a shared cache keep one.
    response.headers["Cache-Control"] = "no-store"
    return response


def gate_passed(request: Request) -> bool:
    try:
        return request.session.get(SESSION_KEY) is True
    except AssertionError:  # SessionMiddleware not installed (never in the app)
        return False


def checkout_urls(base_url: str) -> tuple[str, str]:
    base = base_url.rstrip("/")
    return f"{base}/origicast/success?session_id={{CHECKOUT_SESSION_ID}}", f"{base}/origicast/door"


def build_checkout_session_payload(base_url: str, amount_cents: int) -> dict[str, str]:
    """Form-encoded body for POST /checkout/sessions — the CHF 1 test. Pure."""
    if int(amount_cents) <= 0:
        raise ValueError("ORIGICAST_TEST_AMOUNT_CENTS must be positive")
    success_url, cancel_url = checkout_urls(base_url)
    return {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "locale": "de",
        "client_reference_id": VENTURE,
        "metadata[venture]": VENTURE,
        "metadata[product]": VENTURE,
        "payment_intent_data[metadata][venture]": VENTURE,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "chf",
        "line_items[0][price_data][unit_amount]": str(int(amount_cents)),
        "line_items[0][price_data][product_data][name]": t.TEST_PRODUCT_NAME,
    }


async def create_checkout_session(base_url: str) -> dict[str, Any]:
    payload = build_checkout_session_payload(base_url, settings.origicast_test_amount_cents)
    session = await stripe_request("POST", "/checkout/sessions", payload)
    if not session.get("url"):
        raise StripeError("Checkout session missing url")
    return session


# --- pages ----------------------------------------------------------------------


@router.api_route("", methods=["GET", "HEAD"], include_in_schema=False)
async def origicast_no_slash() -> RedirectResponse:
    return RedirectResponse(url="/origicast/", status_code=301)


@router.get("/", response_class=HTMLResponse, response_model=None, include_in_schema=False)
async def origicast_gate(request: Request) -> Response:
    if gate_passed(request):
        return RedirectResponse(url="/origicast/door", status_code=303)
    return _render("gate.html", request)


@router.post("/gate", include_in_schema=False)
async def origicast_gate_answer(request: Request, answer: str = Form("")) -> RedirectResponse:
    if answer == "yes":
        request.session[SESSION_KEY] = True
        return RedirectResponse(url="/origicast/door", status_code=303)
    request.session.pop(SESSION_KEY, None)
    return RedirectResponse(url="/origicast/leave", status_code=303)


@router.get("/leave", response_class=HTMLResponse, response_model=None, include_in_schema=False)
async def origicast_leave(request: Request) -> HTMLResponse:
    return _render("leave.html", request)


@router.get("/door", response_class=HTMLResponse, response_model=None, include_in_schema=False)
async def origicast_door(request: Request, error: str = "") -> Response:
    if not gate_passed(request):
        return RedirectResponse(url="/origicast/", status_code=303)
    return _render(
        "door.html",
        request,
        offers_live=bool(settings.origicast_live),
        error=t.TEST_UNAVAILABLE if error == "unavailable" else None,
    )


@router.api_route("/checkout", methods=["GET", "POST"], include_in_schema=False)
async def origicast_checkout(request: Request) -> RedirectResponse:
    if not gate_passed(request):
        return RedirectResponse(url="/origicast/", status_code=303)
    try:
        session = await create_checkout_session(_base_url(request))
    except (StripeNotConfigured, ValueError) as exc:
        logger.warning("/origicast checkout not configured: %s", exc)
        return RedirectResponse(url="/origicast/door?error=unavailable", status_code=303)
    except StripeError as exc:
        logger.warning("/origicast checkout failed at Stripe: %s", exc)
        return RedirectResponse(url="/origicast/door?error=unavailable", status_code=303)
    return RedirectResponse(url=session["url"], status_code=303)


@router.get("/success", response_class=HTMLResponse, response_model=None, include_in_schema=False)
async def origicast_success(request: Request, session_id: str = "") -> HTMLResponse:
    """Shown right after Stripe. Never calls Stripe: the buyer has paid and
    must not see an error because a lookup hiccupped."""
    return _render("success.html", request, session_id=session_id[:_SESSION_ID_MAX])


# --- Season / Hour / Keep: exist only once ORIGICAST_LIVE is set ------------------


@router.get("/{offer}", include_in_schema=False)
async def origicast_offer(request: Request, offer: str) -> Response:
    if offer not in ("season", "hour", "keep") or not settings.origicast_live:
        raise HTTPException(status_code=404)
    if not gate_passed(request):
        return RedirectResponse(url="/origicast/", status_code=303)
    # Placeholder until the first season opens: back to the door, offer named.
    return RedirectResponse(url=f"/origicast/door#offer-{offer}", status_code=303)


# --- webhook ------------------------------------------------------------------------


async def handle_checkout_completed(session: dict[str, Any]) -> Response:
    """One CHF 1 test was paid: tell HQ so it gets refunded. Shared with the
    unified ``/stripe/webhook`` dispatcher; the caller already routed it."""
    session_id = str(session.get("id") or "")
    amount = session.get("amount_total")
    body = t.HQ_MAIL_BODY.format(
        session_id=session_id or "—",
        email=session_email(session) or "—",
        amount=f"{int(amount) / 100:.2f}" if isinstance(amount, int) else "—",
        currency=str(session.get("currency") or "chf").upper(),
    )
    try:
        await send_hq_mail(t.HQ_MAIL_SUBJECT, body)
    except HQMailNotConfigured as exc:
        logger.warning("/origicast paid test not mailed (no HQ Mail): %s %s", session_id, exc)
        return JSONResponse({"received": True, "mailed": False})
    except HQMailError as exc:
        # 5xx makes Stripe retry, so the refund reminder is never lost.
        logger.warning("/origicast paid test could not be mailed: %s", exc)
        raise HTTPException(status_code=503, detail="hq mail unavailable") from exc
    return JSONResponse({"received": True, "mailed": True})
