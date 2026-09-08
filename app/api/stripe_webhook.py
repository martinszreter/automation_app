"""One Stripe webhook endpoint for both ventures: ``POST /stripe/webhook``.

The Stripe account is shared, so a single endpoint registered in the dashboard
is less to keep in sync than one per product. This module owns nothing but the
routing decision: it verifies the signature, asks
:mod:`app.services.stripe_events` which venture the object belongs to, and
hands the object to the handler that already exists for that venture.

The two older endpoints (``/apps/stripe/webhook`` and
``/x-autopilot/stripe/webhook``) keep working and call the very same handlers,
so an endpoint still configured in Stripe against either URL behaves as before.

Two event types are dispatched:

* ``checkout.session.completed``    -> the paid order row (and, for
  x-autopilot, the plan row in Postgres);
* ``customer.subscription.deleted`` -> the cancellation row.

Anything else is acknowledged with 200 so Stripe stops retrying it.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import apps as apps_api
from app.api import origicast as origicast_api
from app.api import x_autopilot as xautopilot_api
from app.db.session import get_db
from app.services.stripe_checkout import StripeSignatureError
from app.services.stripe_events import (
    VENTURE_APPS,
    VENTURE_ORIGICAST,
    VENTURE_XAUTOPILOT,
    event_object,
    load_event,
    venture_for_object,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stripe"])

CHECKOUT_COMPLETED = "checkout.session.completed"
SUBSCRIPTION_DELETED = "customer.subscription.deleted"
HANDLED_EVENTS = frozenset({CHECKOUT_COMPLETED, SUBSCRIPTION_DELETED})


async def dispatch_event(event: dict[str, Any], db: AsyncSession) -> Response:
    """Route one already-verified Stripe event to its venture's handler."""
    event_type = str(event.get("type") or "")
    if event_type not in HANDLED_EVENTS:
        return JSONResponse({"received": True, "ignored": True})

    obj = event_object(event)
    venture = venture_for_object(obj)
    if venture is None:
        # Neither the Price ids nor the metadata name a venture: acknowledge,
        # store nothing. A guess would write the row into the wrong table.
        logger.warning(
            "Stripe %s %s matches no venture", event_type, str(event.get("id") or "")[:80]
        )
        return JSONResponse({"received": True, "ignored": True})

    if event_type == CHECKOUT_COMPLETED:
        if venture == VENTURE_APPS:
            return await apps_api.handle_checkout_completed(obj)
        if venture == VENTURE_ORIGICAST:
            return await origicast_api.handle_checkout_completed(obj)
        return await xautopilot_api.handle_checkout_completed(obj, db)

    if venture == VENTURE_APPS:
        return await apps_api.handle_subscription_deleted(obj)
    if venture == VENTURE_ORIGICAST:
        # The CHF 1 test is a one-time payment; there is no subscription to end.
        return JSONResponse({"received": True, "ignored": True})
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


__all__ = ["router", "dispatch_event", "VENTURE_APPS", "VENTURE_ORIGICAST", "VENTURE_XAUTOPILOT"]
