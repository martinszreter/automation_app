"""X Autopilot self-serve: Stripe Checkout → Google Sign-In panel.

Tier flow (the three published tiers, CHF 149 / 330 / 990):

    GET  /x-autopilot/checkout/{tier}  -> Stripe Checkout for that tier's Price
    GET  /x-autopilot/success          confirmation + X authorization link
    POST /x-autopilot/stripe/webhook   checkout.session.completed -> n8n row
"""

from __future__ import annotations

import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
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
    SheetsReconnectRequired,
)
from app.services.hq_mail import HQMailError, HQMailNotConfigured, send_hq_mail
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
from app.services.xautopilot_panel import (
    PanelLaneError,
    PanelLaneNotConfigured,
    digest_text,
    format_chf,
    lane_recent_posts,
    load_panel_data,
    set_agent_status,
)
from app.services.xautopilot_plans import (
    ensure_e2e_plan,
    get_active_plan_for_email,
    list_active_plans,
    mark_plan_refunded,
    refund_plan,
    set_plan_paused,
    upsert_plan_from_checkout,
)
from app.templates.messages import xa_de
from app.services.xautopilot_generate import (
    GenerationError,
    GenerationNotConfigured,
    generate_variants,
)
from app.services.xautopilot_judge import (
    RecentPost,
    ToneProfile,
    parse_posted_at,
    pick_best,
    record_vetoes,
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
# Don't re-send the Sheets reconnect request on every panel view.
_SHEETS_RECONNECT_EMAIL_COOLDOWN = 6 * 3600
_SHEETS_RECONNECT_SUBJECT = "X Autopilot: Sheets reconnect needed"
_sheets_reconnect_mail: dict[str, float] = {"sent_at": 0.0}


def _base_url(request: Request) -> str:
    return public_base_url(
        str(request.base_url),
        request.headers.get("x-forwarded-proto"),
        request.headers.get("x-forwarded-host") or request.headers.get("host"),
    )


async def _request_sheets_reconnect(request: Request, reason: str) -> None:
    """Ask Marcin (via HQ Mail) to reconnect Sheets. Debounced; never raises."""
    now = time.time()
    if now - _sheets_reconnect_mail["sent_at"] < _SHEETS_RECONNECT_EMAIL_COOLDOWN:
        return
    key = settings.google_sheets_reconnect_key.strip()
    if not key or not settings.google_oauth_client_id.strip():
        # Without a reconnect key or a Google client the link could not work.
        logger.warning("Sheets reconnect needed (%s) but no reconnect link can be built", reason)
        return
    reconnect_url = f"{_base_url(request)}/x-autopilot/sheets/reconnect?key={quote(key, safe='')}"
    body = (
        f"X Autopilot's Google Sheets access needs to be reconnected: {reason}.\n\n"
        f"Reconnect: {reconnect_url}\n\n"
        "This grants read-only access to the configured spreadsheet and shows a "
        "new GOOGLE_SHEETS_REFRESH_TOKEN to paste into Railway."
    )
    try:
        await send_hq_mail(_SHEETS_RECONNECT_SUBJECT, body)
    except (HQMailNotConfigured, HQMailError) as exc:
        logger.warning("Could not send Sheets reconnect email: %s", exc)
        return
    _sheets_reconnect_mail["sent_at"] = now


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
    panel_data = None
    if plan is not None and plan.status == PlanStatus.ACTIVE:
        try:
            sheets = await google_oauth.read_sheet_values()
        except (GoogleNotConfigured, SheetsReconnectRequired) as exc:
            sheets_error = str(exc)
            await _request_sheets_reconnect(request, str(exc))
        except GoogleOAuthError as exc:
            sheets_error = str(exc)
        panel_data = await load_panel_data(plan)
        learned = str((panel_data.agent or {}).get("agent_name") or "").strip()
        if learned and learned != (plan.agent_name or ""):
            plan.agent_name = learned
            await db.commit()

    return _render(
        "panel.html",
        request=request,
        t=xa_de,
        user=user,
        plan=plan,
        plan_active=plan is not None and plan.status == PlanStatus.ACTIVE,
        amount_label=_format_chf(plan.amount_cents) if plan else "",
        invoice_label=format_chf(panel_data.invoice["amount_due_cents"]) if panel_data and panel_data.invoice else "",
        panel=panel_data,
        sheets=sheets,
        sheets_error=sheets_error,
    )


async def _set_paused(request: Request, db: AsyncSession, *, paused: bool) -> RedirectResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse(url="/x-autopilot/panel/login", status_code=303)
    plan = await get_active_plan_for_email(db, user["email"])
    if plan is None:
        raise HTTPException(status_code=404, detail="no active plan")
    await set_plan_paused(db, plan, paused=paused)
    if plan.agent_name:
        try:
            await set_agent_status(plan.agent_name, paused=paused)
        except PanelLaneNotConfigured:
            pass
        except PanelLaneError as exc:
            logger.warning("panel lane could not %s %s: %s", "pause" if paused else "resume", plan.agent_name, exc)
    return RedirectResponse(url="/x-autopilot/panel", status_code=303)


@router.post("/panel/pause", include_in_schema=False)
async def panel_pause(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    return await _set_paused(request, db, paused=True)


@router.post("/panel/resume", include_in_schema=False)
async def panel_resume(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    return await _set_paused(request, db, paused=False)


@router.get("/e2e/login", include_in_schema=False)
async def e2e_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    key: str = Query(""),
    email: str = Query(""),
) -> RedirectResponse:
    """CI only (XA_E2E_KEY set): sign a synthetic paid buyer in so Playwright can drive the panel."""
    expected = settings.xa_e2e_key.strip()
    if not expected or not key or not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=404)
    clean = email.strip().lower()
    if "@" not in clean:
        raise HTTPException(status_code=422, detail="email required")
    plan = await ensure_e2e_plan(db, clean)
    request.session[_USER_KEY] = {"email": plan.email, "name": "E2E Buyer", "picture": "", "sub": "e2e"}
    return RedirectResponse(url="/x-autopilot/panel", status_code=303)


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


# --- post quality judge (called by the n8n engines before posting) -----------


class ToneProfileIn(BaseModel):
    customer: str = ""
    language: str = "de"
    banned_terms: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    voice: str = ""
    max_hashtags: int = Field(default=2, ge=0, le=10)

    def to_profile(self) -> ToneProfile:
        return ToneProfile(
            customer=self.customer,
            language=self.language,
            banned_terms=list(self.banned_terms),
            topics=list(self.topics),
            voice=self.voice,
            max_hashtags=self.max_hashtags,
        )


class RecentPostIn(BaseModel):
    text: str
    posted_at: str | None = None


class JudgeRequest(BaseModel):
    profile: ToneProfileIn = Field(default_factory=ToneProfileIn)
    candidates: list[str] = Field(default_factory=list, max_length=10)
    recent_posts: list[RecentPostIn] = Field(default_factory=list, max_length=500)


class ComposeRequest(BaseModel):
    profile: ToneProfileIn = Field(default_factory=ToneProfileIn)
    brief: str = Field(min_length=1, max_length=4000)
    recent_posts: list[RecentPostIn] = Field(default_factory=list, max_length=500)
    variants: int = Field(default=3, ge=1, le=5)


def _require_judge_key(x_judge_key: str | None = Header(default=None)) -> None:
    expected = settings.xautopilot_judge_key.strip()
    if not expected:
        raise HTTPException(status_code=503, detail="XAUTOPILOT_JUDGE_KEY is not set")
    if not x_judge_key or not hmac.compare_digest(x_judge_key.strip(), expected):
        raise HTTPException(status_code=401, detail="invalid judge key")


async def _judge_candidates(
    profile_in: ToneProfileIn, candidates: list[str], recent_in: list[RecentPostIn]
) -> dict[str, Any]:
    profile = profile_in.to_profile()
    recent = [RecentPost(p.text, parse_posted_at(p.posted_at)) for p in recent_in]
    best, reports = pick_best(candidates, profile, recent)
    recorded = await record_vetoes(profile, reports)
    return {
        "best": best.text if best else None,
        "reports": [report.to_dict() for report in reports],
        "vetoes_recorded": recorded,
    }


@router.post("/judge", dependencies=[Depends(_require_judge_key)], include_in_schema=False)
async def judge_candidates(payload: JudgeRequest) -> JSONResponse:
    """Veto hard fails among the candidates and name the best one."""
    result = await _judge_candidates(payload.profile, payload.candidates, payload.recent_posts)
    return JSONResponse(result)


@router.post("/compose", dependencies=[Depends(_require_judge_key)], include_in_schema=False)
async def compose_post(payload: ComposeRequest) -> JSONResponse:
    """Draft N variants with Claude, then judge them and pick the best."""
    try:
        candidates = await generate_variants(payload.brief, payload.profile.to_profile(), count=payload.variants)
    except GenerationNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    result = await _judge_candidates(payload.profile, candidates, payload.recent_posts)
    return JSONResponse(result)


@router.post("/digest/run", dependencies=[Depends(_require_judge_key)], include_in_schema=False)
async def digest_run(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Weekly digest: one mail per active plan (n8n schedule calls this with X-Judge-Key)."""
    panel_url = f"{_base_url(request)}/x-autopilot/panel"
    sent = 0
    skipped: list[dict[str, str]] = []
    for plan in await list_active_plans(db):
        posts: list[dict[str, Any]] = []
        if plan.agent_name:
            try:
                posts = await lane_recent_posts(plan.agent_name)
            except (PanelLaneNotConfigured, PanelLaneError) as exc:
                logger.warning("digest: no posts for %s: %s", plan.agent_name, exc)
        data = await load_panel_data(plan)
        subject, body = digest_text(plan, posts or data.posts, scheduled=data.scheduled_count, panel_url=panel_url)
        try:
            await send_hq_mail(subject, body, to=plan.email)
            sent += 1
        except (HQMailNotConfigured, HQMailError) as exc:
            skipped.append({"email": plan.email, "reason": str(exc)})
    return JSONResponse({"sent": sent, "skipped": skipped})
