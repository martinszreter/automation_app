"""X Autopilot self-serve: Stripe Checkout → Google Sign-In panel.

Tier flow (the three published tiers, CHF 149 / 330 / 990):

    GET  /x-autopilot/checkout/{tier}  -> Stripe Checkout for that tier's Price
    GET  /x-autopilot/success          confirmation + X authorization link
    POST /x-autopilot/stripe/webhook   checkout.session.completed -> n8n row
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import PlanStatus, XAutopilotPlan
from app.db.session import get_db
from app.services import google_oauth
from app.services.google_oauth import (
    GoogleNotConfigured,
    GoogleOAuthError,
    LOGIN_SCOPES,
    SHEETS_SCOPES,
)
from app.services.stripe_checkout import (
    StripeError,
    StripeNotConfigured,
    StripeSignatureError,
    create_checkout_session,
    public_base_url,
    retrieve_checkout_session,
    session_is_paid,
    verify_stripe_signature,
)
from app.services.xautopilot_orders import (
    XAOrderError,
    XAOrderNotConfigured,
    cancellation_row_from_subscription,
    order_row_from_session,
    post_order_row,
)
from app.services.xautopilot_plans import (
    get_active_plan_for_email,
    mark_plan_refunded,
    refund_plan,
    upsert_plan_from_checkout,
)
from app.services.xautopilot_tiers import (
    TierPriceNotConfigured,
    UnknownTier,
    create_tier_checkout_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/x-autopilot", tags=["x-autopilot"])
_USER_KEY = "xa_user"
_CHECKOUT_KEY = "xa_checkout_session_id"
_SESSION_ID_MAX = 160


def _base_url(request: Request) -> str:
    return public_base_url(
        str(request.base_url),
        request.headers.get("x-forwarded-proto"),
        request.headers.get("x-forwarded-host") or request.headers.get("host"),
    )


def _render(name: str, **context: Any) -> HTMLResponse:
    from app.main import templates

    # TemplateResponse needs a request; callers pass it in context.
    request: Request = context.pop("request")
    return templates.TemplateResponse(request=request, name=f"x_autopilot/{name}", context=context)


def _current_user(request: Request) -> dict[str, str] | None:
    user = request.session.get(_USER_KEY)
    if not isinstance(user, dict) or not user.get("email"):
        return None
    return {str(k): str(v) for k, v in user.items()}


def _format_chf(amount_cents: int) -> str:
    francs = amount_cents / 100
    if francs == int(francs):
        return f"CHF {int(francs)}"
    return f"CHF {francs:.2f}"


@router.api_route("/checkout", methods=["GET", "POST"], include_in_schema=False)
async def checkout(request: Request) -> RedirectResponse:
    try:
        session = await create_checkout_session(_base_url(request))
    except StripeNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except StripeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RedirectResponse(url=session["url"], status_code=303)


@router.api_route("/checkout/{tier}", methods=["GET", "POST"], include_in_schema=False)
async def checkout_tier(request: Request, tier: str) -> RedirectResponse:
    """One of the three published tiers -> its own Stripe Checkout Session."""
    try:
        session = await create_tier_checkout_session(_base_url(request), tier)
    except UnknownTier as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (StripeNotConfigured, TierPriceNotConfigured) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except StripeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RedirectResponse(url=session["url"], status_code=303)


def _onboarding_url(session_id: str) -> str:
    """Where the buyer authorizes posting on X. Env-configurable; the on-site
    onboarding form is the fallback so the page is never a dead end."""
    base = settings.x_oauth_onboarding_url.strip() or "/x-autopilot/onboarding.html"
    if not session_id:
        return base
    joiner = "&" if "?" in base else "?"
    return f"{base}{joiner}session_id={quote(session_id, safe='')}"


@router.get("/success", response_class=HTMLResponse, response_model=None, include_in_schema=False)
async def success(request: Request, session_id: str = "") -> HTMLResponse:
    """Shown right after Stripe. Never calls Stripe, so it renders even when the
    session id is unknown — the buyer has already paid and must not hit an error."""
    clean = session_id.strip()[:_SESSION_ID_MAX]
    if clean:
        request.session[_CHECKOUT_KEY] = clean
    return _render(
        "success.html",
        request=request,
        session_id=clean,
        onboarding_url=_onboarding_url(clean),
    )


async def _store_order_row(session: dict[str, Any]) -> bool:
    """Write the paid row to n8n. Returns False when there is nowhere to write."""
    try:
        row = order_row_from_session(session)
    except ValueError as exc:
        logger.warning("x-autopilot webhook has no usable session: %s", exc)
        return False
    try:
        await post_order_row(row)
    except XAOrderNotConfigured as exc:
        # Nothing to write to (local/dev): the plan is already stored in Postgres.
        logger.warning("x-autopilot order row not stored: %s", exc)
        return False
    except XAOrderError as exc:
        # 5xx makes Stripe retry, which is exactly what a lost order needs.
        logger.warning("x-autopilot order row could not be stored: %s", exc)
        raise HTTPException(status_code=503, detail="order store unavailable") from exc
    return True


async def handle_checkout_completed(
    session: dict[str, Any],
    db: AsyncSession,
    *,
    store_row: bool = True,
) -> Response:
    """Store the order row and activate the plan for one paid Checkout Session.

    Shared by ``/x-autopilot/stripe/webhook`` and the unified ``/stripe/webhook``
    dispatcher. The caller has already decided the session is x-autopilot's.
    """
    # The order row goes out first: it is the commercial record, and it does
    # not depend on the buyer's email the way the plan row does.
    stored = await _store_order_row(session) if store_row else False
    try:
        await upsert_plan_from_checkout(db, session)
    except ValueError as exc:
        logger.warning("Stripe webhook could not activate plan: %s", exc)
        return JSONResponse({"received": True, "stored": stored, "error": str(exc)}, status_code=422)
    return JSONResponse({"received": True, "status": "active", "stored": stored})


async def handle_subscription_deleted(subscription: dict[str, Any]) -> Response:
    """Store the cancellation row for a churned x-autopilot subscription."""
    try:
        row = cancellation_row_from_subscription(subscription)
    except ValueError as exc:
        logger.warning("x-autopilot cancellation has no usable subscription: %s", exc)
        return JSONResponse({"received": True, "error": str(exc)}, status_code=422)

    try:
        await post_order_row(row)
    except XAOrderNotConfigured as exc:
        # Nothing to write to (local/dev): acknowledge rather than make Stripe retry.
        logger.warning("x-autopilot cancellation row not stored: %s", exc)
        return JSONResponse({"received": True, "stored": False})
    except XAOrderError as exc:
        logger.warning("x-autopilot cancellation row could not be stored: %s", exc)
        raise HTTPException(status_code=503, detail="order store unavailable") from exc

    return JSONResponse({"received": True, "stored": True})


@router.post("/stripe/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    payload = await request.body()
    header = request.headers.get("stripe-signature", "")
    try:
        verify_stripe_signature(payload, header, settings.stripe_webhook_secret)
        event = json.loads(payload.decode("utf-8"))
    except StripeSignatureError as exc:
        logger.warning("Stripe webhook signature rejected: %s", exc)
        raise HTTPException(status_code=400, detail="invalid signature") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid payload") from exc

    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}

    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        metadata = obj.get("metadata") or {}
        if metadata.get("product") not in (None, "", "x-autopilot"):
            return JSONResponse({"received": True, "ignored": True})
        if not session_is_paid(obj) and event_type != "checkout.session.completed":
            return JSONResponse({"received": True, "pending": True})
        return await handle_checkout_completed(
            obj, db, store_row=event_type == "checkout.session.completed"
        )

    if event_type in {"charge.refunded", "refund.created"}:
        payment_intent = obj.get("payment_intent")
        if isinstance(payment_intent, dict):
            payment_intent = payment_intent.get("id")
        if payment_intent:
            await mark_plan_refunded(db, payment_intent)
        return JSONResponse({"received": True, "status": "refunded"})

    return JSONResponse({"received": True})


@router.get("/panel/login", response_class=HTMLResponse, response_model=None, include_in_schema=False)
async def panel_login(
    request: Request,
    session_id: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    if session_id:
        request.session[_CHECKOUT_KEY] = session_id
    user = _current_user(request)
    if user:
        return RedirectResponse(url="/x-autopilot/panel", status_code=303)
    return _render(
        "login.html",
        request=request,
        error=error,
        google_ready=bool(settings.google_oauth_client_id.strip()),
        session_id=session_id or request.session.get(_CHECKOUT_KEY) or "",
    )


@router.get("/auth/google", include_in_schema=False)
async def auth_google(request: Request) -> RedirectResponse:
    checkout_id = str(request.session.get(_CHECKOUT_KEY) or "")
    redirect_uri = f"{_base_url(request)}/x-autopilot/auth/google/callback"
    try:
        state = google_oauth.dumps_state({"purpose": "login", "checkout": checkout_id})
        url = google_oauth.authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            scopes=LOGIN_SCOPES,
        )
    except GoogleNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RedirectResponse(url=url, status_code=302)


@router.get("/auth/google/callback", response_model=None, include_in_schema=False)
async def auth_google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    if error:
        return RedirectResponse(
            url="/x-autopilot/panel/login?error=google_denied",
            status_code=303,
        )
    if not code or not state:
        return RedirectResponse(
            url="/x-autopilot/panel/login?error=google_missing",
            status_code=303,
        )
    redirect_uri = f"{_base_url(request)}/x-autopilot/auth/google/callback"
    try:
        payload = google_oauth.loads_state(state)
        tokens = await google_oauth.exchange_code(code, redirect_uri)
    except (GoogleOAuthError, GoogleNotConfigured):
        return RedirectResponse(
            url="/x-autopilot/panel/login?error=google_failed",
            status_code=303,
        )

    purpose = payload.get("purpose", "login")
    if purpose == "sheets":
        refresh = tokens.get("refresh_token") or ""
        access = tokens.get("access_token") or ""
        if access:
            google_oauth.cache_sheets_access_token(access, int(tokens.get("expires_in") or 3600))
        return _render(
            "sheets_token.html",
            request=request,
            refresh_token=refresh,
            has_refresh=bool(refresh),
        )

    access = tokens.get("access_token")
    if not access:
        return RedirectResponse(
            url="/x-autopilot/panel/login?error=google_failed",
            status_code=303,
        )
    try:
        info = await google_oauth.fetch_userinfo(access)
    except GoogleOAuthError:
        return RedirectResponse(
            url="/x-autopilot/panel/login?error=google_failed",
            status_code=303,
        )
    request.session[_USER_KEY] = {
        "email": info["email"],
        "name": info.get("name") or "",
        "picture": info.get("picture") or "",
        "sub": info.get("sub") or "",
    }
    checkout_id = payload.get("checkout") or request.session.get(_CHECKOUT_KEY)
    if checkout_id:
        try:
            session = await retrieve_checkout_session(str(checkout_id))
            if session_is_paid(session):
                await upsert_plan_from_checkout(db, session, access_email=info["email"])
        except (StripeError, StripeNotConfigured, ValueError) as exc:
            logger.warning("Could not attach checkout session after Google login: %s", exc)
    return RedirectResponse(url="/x-autopilot/panel", status_code=303)


@router.post("/auth/logout", include_in_schema=False)
async def auth_logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/x-autopilot/panel/login", status_code=303)


@router.get("/panel", response_class=HTMLResponse, response_model=None, include_in_schema=False)
async def panel(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    user = _current_user(request)
    if user is None:
        return RedirectResponse(url="/x-autopilot/panel/login", status_code=303)

    checkout_id = request.session.get(_CHECKOUT_KEY)
    plan: XAutopilotPlan | None = await get_active_plan_for_email(db, user["email"])
    if plan is None and checkout_id:
        try:
            session = await retrieve_checkout_session(str(checkout_id))
            if session_is_paid(session):
                plan = await upsert_plan_from_checkout(db, session, access_email=user["email"])
        except (StripeError, StripeNotConfigured, ValueError) as exc:
            logger.warning("Panel checkout attach failed: %s", exc)

    sheets: dict[str, Any] | None = None
    sheets_error: str | None = None
    if plan is not None and plan.status == PlanStatus.ACTIVE:
        try:
            sheets = await google_oauth.read_sheet_values()
        except GoogleNotConfigured as exc:
            sheets_error = str(exc)
        except GoogleOAuthError as exc:
            sheets_error = str(exc)

    return _render(
        "panel.html",
        request=request,
        user=user,
        plan=plan,
        plan_active=plan is not None and plan.status == PlanStatus.ACTIVE,
        amount_label=_format_chf(plan.amount_cents) if plan else "",
        sheets=sheets,
        sheets_error=sheets_error,
    )


@router.post("/panel/refund", include_in_schema=False)
async def panel_refund(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    """Refund the signed-in user's active plan (used for the CHF 1 smoke test)."""
    user = _current_user(request)
    if user is None:
        return RedirectResponse(url="/x-autopilot/panel/login", status_code=303)
    plan = await get_active_plan_for_email(db, user["email"])
    if plan is None:
        raise HTTPException(status_code=404, detail="no active plan")
    try:
        await refund_plan(db, plan)
    except (StripeError, StripeNotConfigured, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RedirectResponse(url="/x-autopilot/panel", status_code=303)


@router.get("/sheets/reconnect", include_in_schema=False)
async def sheets_reconnect(request: Request, key: str = Query("")) -> RedirectResponse:
    expected = settings.google_sheets_reconnect_key.strip()
    if not expected or key != expected:
        raise HTTPException(status_code=404)
    redirect_uri = f"{_base_url(request)}/x-autopilot/auth/google/callback"
    try:
        state = google_oauth.dumps_state({"purpose": "sheets", "checkout": ""})
        url = google_oauth.authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            scopes=SHEETS_SCOPES,
            offline=True,
        )
    except GoogleNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RedirectResponse(url=url, status_code=302)
