"""Order rows for the n8n data table behind ``N8N_XAUTOPILOT_ORDER_URL``.

One row per paid Checkout Session, written by the
``checkout.session.completed`` webhook and keyed by the session id, so a Stripe
retry overwrites rather than duplicates.

The URL is env-only: an n8n webhook is a write key, so it never enters the repo.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ORDER_TABLE = "xautopilot_orders"
ROW_PAID = "paid"


class XAOrderNotConfigured(RuntimeError):
    """N8N_XAUTOPILOT_ORDER_URL is not set."""


class XAOrderError(RuntimeError):
    """The n8n webhook rejected the row or could not be reached."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _identifier(value: Any) -> str:
    """Stripe returns ids either bare or expanded into an object."""
    if isinstance(value, dict):
        return str(value.get("id") or "")
    return str(value or "")


def order_row_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Flat ``xautopilot_orders`` row built from a Checkout Session object."""
    session_id = _identifier(session.get("id"))
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
        "customer_id": _identifier(session.get("customer")),
        "subscription_id": _identifier(session.get("subscription")),
        "payment_status": str(session.get("payment_status") or ""),
        "amount_total_cents": int(session.get("amount_total") or 0),
        "currency": str(session.get("currency") or "chf").lower(),
        "created_at": _now(),
    }


async def post_order_row(row: dict[str, Any]) -> None:
    """Send one row to the n8n data table webhook."""
    url = settings.n8n_xautopilot_order_url.strip()
    if not url:
        raise XAOrderNotConfigured("N8N_XAUTOPILOT_ORDER_URL is not set")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=row)
    except httpx.HTTPError as exc:
        raise XAOrderError(f"n8n request failed: {exc}") from exc
    if response.status_code >= 400:
        logger.warning(
            "n8n x-autopilot row rejected: %s %s", response.status_code, response.text[:300]
        )
        raise XAOrderError(f"n8n responded {response.status_code}")
