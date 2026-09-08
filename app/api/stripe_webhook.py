"""One Stripe webhook endpoint for both ventures: ``POST /stripe/webhook``.

The Stripe account is shared, so a single endpoint registered in the dashboard
is less to keep in sync than one per product. This module owns nothing but the
routing decision: it verifies the signature, asks
:mod:`app.services.stripe_events` which venture the object belongs to, and
hands the object to the handler that already exists for that venture.

The two older endpoints (``/apps/stripe/webhook`` and
``/x-autopilot/stripe/webhook``) keep working and call the very same handlers,
so an endpoint still configured in Stripe against either URL behaves as before.

Four kinds of event are dispatched:

* ``checkout.session.completed``                -> the paid order row (and, for
  x-autopilot, the plan row in Postgres);
* ``checkout.session.async_payment_succeeded``  -> the same handlers. A bank
  transfer completes the session first and pays later; the plan only turns
  active, and the order row only says ``paid``, on this second event;
* ``customer.subscription.deleted``             -> the cancellation row;
* ``charge.refunded`` / ``refund.created``      -> the x-autopilot plan whose
  payment intent was refunded is marked refunded. A Charge carries no venture
  metadata, so this is routed by the payment intent lookup itself: a refund
  for /apps simply finds no plan.

Anything else is acknowledged with 200 so Stripe stops retrying it.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import apps as apps_api
from app.api import x_autopilot as xautopilot_api
from app.db.session import get_db
from app.services.stripe_checkout import StripeSignatureError
from app.services.stripe_events import (
    VENTURE_APPS,
    VENTURE_XAUTOPILOT,
    event_object,
    identifier,
    load_event,
    venture_for_object,
)
from app.services.xautopilot_plans import mark_plan_refunded

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stripe"])

CHECKOUT_COMPLETED = "checkout.session.completed"
CHECKOUT_ASYNC_PAID = "checkout.session.async_payment_succeeded"
SUBSCRIPTION_DELETED = "customer.subscription.deleted"
CHECKOUT_EVENTS = frozenset({CHECKOUT_COMPLETED, CHECKOUT_ASYNC_PAID})
REFUND_EVENTS = frozenset({"charge.refunded", "refund.created"})
HANDLED_EVENTS = CHECKOUT_EVENTS | {SUBSCRIPTION_DELETED} | REFUND_EVENTS


async def dispatch_event(event: dict[str, Any], db: AsyncSession) -> Response:
    """Route one already-verified Stripe event to its venture's handler."""
    event_type = str(event.get("type") or "")
    if event_type not in HANDLED_EVENTS:
        return JSONResponse({"received": True, "ignored": True})

    obj = event_object(event)

    if event_type in REFUND_EVENTS:
        payment_intent = identifier(obj.get("payment_intent"))
        if not payment_intent:
            return JSONResponse({"received": True, "ignored": True})
        plan = await mark_plan_refunded(db, payment_intent)
        return JSONResponse({"received": True, "status": "refunded", "plan": plan is not None})

    venture = venture_for_object(obj)
    if venture is None:
        # Neither the Price ids nor the metadata name a venture: acknowledge,
        # store nothing. A guess would write the row into the wrong table.
        logger.warning(
            "Stripe %s %s matches no venture", event_type, str(event.get("id") or "")[:80]
        )
        return JSONResponse({"received": True, "ignored": True})

    if event_type in CHECKOUT_EVENTS:
        if venture == VENTURE_APPS:
            return await apps_api.handle_checkout_completed(obj)
        return await xautopilot_api.handle_checkout_completed(obj, db)

    if venture == VENTURE_APPS:
        return await apps_api.handle_subscription_deleted(obj)
    return await xautopilot_api.handle_subscription_deleted(obj)


@router.post("/stripe/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    payload = await request.body()
    header = request.headers.get("stripe-signature", "")
    try:
        event = load_event(payload, header)
    except StripeSignatureError as exc:
        logger.warning("Stripe webhook signature rejected: %s", exc)
        raise HTTPException(status_code=400, detail="invalid signature") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid payload") from exc
    return await dispatch_event(event, db)


__all__ = ["router", "dispatch_event", "VENTURE_APPS", "VENTURE_XAUTOPILOT"]
