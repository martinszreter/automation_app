"""/apps — WhatsApp reservation setup: Stripe Checkout, success form, webhook.

Flow:

    GET  /apps/                 landing page (static, German)
    GET  /apps/checkout         -> Stripe Checkout (setup fee + subscription)
    GET  /apps/success          form: restaurant name, Swiss number, hours
    POST /apps/success          -> row in the n8n data table apps_orders
    POST /apps/stripe/webhook   checkout.session.completed -> same table

The Stripe transport and the signature check are the shared helpers in
``app.services.stripe_checkout``; nothing about Stripe is re-implemented here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from app.core.config import settings
from app.services.apps_checkout import (
    APPS_PRODUCT,
    AppsPricesNotConfigured,
    create_apps_checkout_session,
)
from app.services.apps_orders import (
    AppsOrderError,
    AppsOrderNotConfigured,
    cancellation_row_from_subscription,
    details_row,
    paid_row_from_session,
    post_order_row,
)
from app.services.stripe_checkout import (
    StripeError,
    StripeNotConfigured,
    StripeSignatureError,
    public_base_url,
    verify_stripe_signature,
)
from app.templates.messages import apps_de

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apps", tags=["apps"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_SESSION_ID_MAX = 160


def _base_url(request: Request) -> str:
    return public_base_url(
        str(request.base_url),
        request.headers.get("x-forwarded-proto"),
        request.headers.get("x-forwarded-host") or request.headers.get("host"),
    )


def _render(name: str, **context: Any) -> HTMLResponse:
    from app.main import templates

    request: Request = context.pop("request")
    return templates.TemplateResponse(request=request, name=f"apps/{name}", context=context)


def _success_page(
    request: Request,
    session_id: str,
    *,
    restaurant_name: str = "",
    phone: str = "",
    opening_hours: str = "",
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    response = _render(
        "success.html",
        request=request,
        t=apps_de,
        session_id=session_id[:_SESSION_ID_MAX],
        restaurant_name=restaurant_name,
        phone=phone,
        opening_hours=opening_hours,
        error=error,
    )
    response.status_code = status_code
    return response


@router.api_route("", methods=["GET", "HEAD"], include_in_schema=False)
async def apps_no_slash() -> RedirectResponse:
    return RedirectResponse(url="/apps/", status_code=301)


@router.get("/", response_class=FileResponse, include_in_schema=False)
async def apps_landing() -> FileResponse:
    return FileResponse(_STATIC_DIR / "apps" / "index.html", media_type="text/html")


@router.api_route("/checkout", methods=["GET", "POST"], include_in_schema=False)
async def apps_checkout(request: Request) -> RedirectResponse:
    try:
        session = await create_apps_checkout_session(_base_url(request))
    except (StripeNotConfigured, AppsPricesNotConfigured) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except StripeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RedirectResponse(url=session["url"], status_code=303)


@router.get("/success", response_class=HTMLResponse, response_model=None, include_in_schema=False)
async def apps_success(request: Request, session_id: str = "") -> HTMLResponse:
    """Shown right after Stripe. Never calls Stripe, so it renders even when the
    session id is unknown — the buyer has already paid and must not hit an error."""
    return _success_page(request, session_id)


@router.post("/success", response_class=HTMLResponse, response_model=None, include_in_schema=False)
async def apps_success_submit(
    request: Request,
    session_id: str = Form(""),
    restaurant_name: str = Form(""),
    phone: str = Form(""),
    opening_hours: str = Form(""),
) -> HTMLResponse:
    try:
        row = details_row(session_id, restaurant_name, phone, opening_hours)
    except ValueError as exc:
        reason = str(exc)
        if reason.startswith("restaurant_name"):
            error = apps_de.ERROR_RESTAURANT_REQUIRED
        elif reason.startswith("opening_hours"):
            error = apps_de.ERROR_OPENING_HOURS_REQUIRED
        else:
            error = apps_de.ERROR_PHONE_INVALID
        return _success_page(
            request,
            session_id,
            restaurant_name=restaurant_name,
            phone=phone,
            opening_hours=opening_hours,
            error=error,
            status_code=422,
        )

    try:
        await post_order_row(row)
    except AppsOrderNotConfigured as exc:
        # Nothing to write to (local/dev): keep the buyer moving, flag it in the log.
        logger.warning("/apps details not stored: %s", exc)
    except AppsOrderError as exc:
        # The row is configured to go somewhere and did not get there — ask
        # again rather than silently losing what the restaurant typed.
        logger.warning("/apps details could not be stored: %s", exc)
        return _success_page(
            request,
            session_id,
            restaurant_name=restaurant_name,
            phone=phone,
            opening_hours=opening_hours,
            error=apps_de.ERROR_SAVE_FAILED,
            status_code=502,
        )

    return _render("done.html", request=request, t=apps_de)


async def handle_checkout_completed(session: dict[str, Any]) -> Response:
    """Store the paid row for one /apps Checkout Session.

    Shared by ``/apps/stripe/webhook`` and the unified ``/stripe/webhook``
    dispatcher, so both endpoints write the same row through the same errors.
    The caller has already decided the session belongs to /apps.
    """
    try:
        row = paid_row_from_session(session)
    except ValueError as exc:
        logger.warning("/apps webhook has no usable session: %s", exc)
        return JSONResponse({"received": True, "error": str(exc)}, status_code=422)

    try:
        await post_order_row(row)
    except (AppsOrderNotConfigured, AppsOrderError) as exc:
        # 5xx makes Stripe retry, which is exactly what a lost order needs.
        logger.warning("/apps order row not stored: %s", exc)
        raise HTTPException(status_code=503, detail="order store unavailable") from exc

    return JSONResponse({"received": True, "stored": True})


async def handle_subscription_deleted(subscription: dict[str, Any]) -> Response:
    """Store the cancellation row for a churned /apps subscription."""
    try:
        row = cancellation_row_from_subscription(subscription)
    except ValueError as exc:
        logger.warning("/apps cancellation has no usable subscription: %s", exc)
        return JSONResponse({"received": True, "error": str(exc)}, status_code=422)

    try:
        await post_order_row(row)
    except AppsOrderNotConfigured as exc:
        # Nothing to write to (local/dev): acknowledge rather than make Stripe retry.
        logger.warning("/apps cancellation row not stored: %s", exc)
        return JSONResponse({"received": True, "stored": False})
    except AppsOrderError as exc:
        logger.warning("/apps cancellation row could not be stored: %s", exc)
        raise HTTPException(status_code=503, detail="order store unavailable") from exc

    return JSONResponse({"received": True, "stored": True})


@router.post("/stripe/webhook", include_in_schema=False)
async def apps_stripe_webhook(request: Request) -> Response:
    payload = await request.body()
    header = request.headers.get("stripe-signature", "")
    try:
        verify_stripe_signature(payload, header, settings.stripe_webhook_secret)
        event = json.loads(payload.decode("utf-8"))
    except StripeSignatureError as exc:
        logger.warning("/apps Stripe webhook signature rejected: %s", exc)
        raise HTTPException(status_code=400, detail="invalid signature") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid payload") from exc

    if event.get("type") != "checkout.session.completed":
        return JSONResponse({"received": True})

    session = (event.get("data") or {}).get("object") or {}
    metadata = session.get("metadata") or {}
    if metadata.get("product") != APPS_PRODUCT:
        # The same endpoint may receive events for the other products.
        return JSONResponse({"received": True, "ignored": True})

    return await handle_checkout_completed(session)
