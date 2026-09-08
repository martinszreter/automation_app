"""Order rows for the n8n data table behind ``N8N_XAUTOPILOT_ORDER_URL``.

Two kinds of row, both keyed by a Stripe id so a Stripe retry overwrites
rather than duplicates:

* ``paid``     — one row per paid Checkout Session, written by the
  ``checkout.session.completed`` webhook and keyed by the session id;
* ``canceled`` — written by ``customer.subscription.deleted``, keyed by the
  subscription id, so a churned tier stops looking like a live one.

The URL is env-only: an n8n webhook is a write key, so it never enters the repo.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services import n8n_rows
from app.services.stripe_events import identifier, iso_timestamp, now_iso, price_ids

ORDER_TABLE = "xautopilot_orders"
ROW_PAID = "paid"
ROW_CANCELED = "canceled"


class XAOrderNotConfigured(RuntimeError):
    """N8N_XAUTOPILOT_ORDER_URL is not set."""


class XAOrderError(RuntimeError):
    """The n8n webhook rejected the row or could not be reached."""


def order_row_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Flat ``xautopilot_orders`` row built from a Checkout Session object."""
    session_id = identifier(session.get("id"))
    if not session_id:
        raise ValueError("checkout session has no id")
    details = session.get("customer_details") or {}
    metadata = session.get("metadata") or {}
    return {
        "table": ORDER_TABLE,
        "kind": ROW_PAID,
        "session_id": session_id,
        "tier": str(metadata.get("tier") or ""),
        "price_id": str(metadata.get("price_id") or ""),
        "email": str(details.get("email") or session.get("customer_email") or "").strip().lower(),
        "customer_name": str(details.get("name") or "").strip(),
        "customer_id": identifier(session.get("customer")),
        "subscription_id": identifier(session.get("subscription")),
        "payment_status": str(session.get("payment_status") or ""),
        "amount_total_cents": int(session.get("amount_total") or 0),
        "currency": str(session.get("currency") or "chf").lower(),
        "created_at": now_iso(),
    }


def cancellation_row_from_subscription(subscription: dict[str, Any]) -> dict[str, Any]:
    """Flat ``xautopilot_orders`` row built from a deleted subscription object."""
    subscription_id = identifier(subscription.get("id"))
    if not subscription_id:
        raise ValueError("subscription has no id")
    metadata = subscription.get("metadata") or {}
    prices = price_ids(subscription)
    return {
        "table": ORDER_TABLE,
        "kind": ROW_CANCELED,
        "subscription_id": subscription_id,
        "customer_id": identifier(subscription.get("customer")),
        "tier": str(metadata.get("tier") or ""),
        "price_id": prices[0] if prices else "",
        "status": str(subscription.get("status") or ""),
        "canceled_at": iso_timestamp(subscription.get("canceled_at") or subscription.get("ended_at")),
        "created_at": now_iso(),
    }


async def post_order_row(row: dict[str, Any]) -> None:
    """Send one row to the n8n data table webhook."""
    url = settings.n8n_xautopilot_order_url.strip()
    if not url:
        raise XAOrderNotConfigured("N8N_XAUTOPILOT_ORDER_URL is not set")
    await n8n_rows.post_row(url, row, error=XAOrderError)
