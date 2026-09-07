"""Rows for the n8n data table ``apps_orders``.

Two kinds of row are written for one sale, both keyed by the Stripe Checkout
Session id:

* ``paid``    — written by the ``checkout.session.completed`` webhook;
* ``details`` — written by the success page once the restaurant has filled in
  its name, phone number and opening hours.

A third kind, ``canceled``, is written by ``customer.subscription.deleted`` and
keyed by the subscription id, so a churned restaurant stops looking like a live
one.

The table lives in n8n, reached over the webhook URL in ``N8N_APPS_ORDER_URL``.
The URL is env-only: an n8n webhook is a write key, so it never enters the repo.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.services.stripe_events import price_ids

logger = logging.getLogger(__name__)

ORDER_TABLE = "apps_orders"
ROW_PAID = "paid"
ROW_DETAILS = "details"
ROW_CANCELED = "canceled"

_DIGITS = re.compile(r"[^0-9+]")
_OPENING_HOURS_MAX = 500
_NAME_MAX = 160


class AppsOrderNotConfigured(RuntimeError):
    """N8N_APPS_ORDER_URL is not set."""


class AppsOrderError(RuntimeError):
    """The n8n webhook rejected the row or could not be reached."""


def normalize_swiss_phone(raw: str) -> str:
    """Return a Swiss number in E.164 (``+41791234567``) or raise ValueError.

    Accepts the shapes guests actually type: ``079 938 03 72``,
    ``+41 79 938 03 72``, ``0041799380372``, with spaces, dots, slashes or
    dashes anywhere. Anything that is not a Swiss subscriber number is refused
    rather than guessed — WhatsApp has to reach this number.
    """
    cleaned = _DIGITS.sub("", (raw or "").strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if cleaned.startswith("+"):
        national = cleaned[3:] if cleaned.startswith("+41") else ""
        if not national:
            raise ValueError("not a Swiss country code")
    elif cleaned.startswith("41") and len(cleaned) == 11:
        national = cleaned[2:]
    elif cleaned.startswith("0"):
        national = cleaned[1:]
    else:
        national = cleaned
    if len(national) != 9 or not national.isdigit() or national.startswith("0"):
        raise ValueError("not a Swiss subscriber number")
    return f"+41{national}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _identifier(value: Any) -> str:
    """Stripe returns ids either bare or expanded into an object."""
    if isinstance(value, dict):
        return str(value.get("id") or "")
    return str(value or "")


def _timestamp(value: Any) -> str:
    """Stripe sends times as unix seconds; fall back to now when absent."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return _now()
    if seconds <= 0:
        return _now()
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(timespec="seconds")


def paid_row_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Flat ``apps_orders`` row built from a Checkout Session object."""
    session_id = _identifier(session.get("id"))
    if not session_id:
        raise ValueError("checkout session has no id")
    details = session.get("customer_details") or {}
    return {
        "table": ORDER_TABLE,
        "kind": ROW_PAID,
        "session_id": session_id,
        "email": str(details.get("email") or session.get("customer_email") or "").strip().lower(),
        "customer_name": str(details.get("name") or "").strip(),
        "customer_id": _identifier(session.get("customer")),
        "subscription_id": _identifier(session.get("subscription")),
        "payment_status": str(session.get("payment_status") or ""),
        "amount_total_cents": int(session.get("amount_total") or 0),
        "currency": str(session.get("currency") or "chf").lower(),
        "created_at": _now(),
    }


def details_row(
    session_id: str,
    restaurant_name: str,
    phone: str,
    opening_hours: str,
) -> dict[str, Any]:
    """Row carrying what the success page collects. Raises ValueError on bad input."""
    name = (restaurant_name or "").strip()[:_NAME_MAX]
    hours = (opening_hours or "").strip()[:_OPENING_HOURS_MAX]
    if not name:
        raise ValueError("restaurant_name is required")
    if not hours:
        raise ValueError("opening_hours is required")
    return {
        "table": ORDER_TABLE,
        "kind": ROW_DETAILS,
        "session_id": (session_id or "").strip()[:_NAME_MAX],
        "restaurant_name": name,
        "phone": normalize_swiss_phone(phone),
        "opening_hours": hours,
        "created_at": _now(),
    }


def cancellation_row_from_subscription(subscription: dict[str, Any]) -> dict[str, Any]:
    """Flat ``apps_orders`` row built from a deleted subscription object."""
    subscription_id = _identifier(subscription.get("id"))
    if not subscription_id:
        raise ValueError("subscription has no id")
    prices = price_ids(subscription)
    return {
        "table": ORDER_TABLE,
        "kind": ROW_CANCELED,
        "subscription_id": subscription_id,
        "customer_id": _identifier(subscription.get("customer")),
        "price_id": prices[0] if prices else "",
        "status": str(subscription.get("status") or ""),
        "canceled_at": _timestamp(subscription.get("canceled_at") or subscription.get("ended_at")),
        "created_at": _now(),
    }


async def post_order_row(row: dict[str, Any]) -> None:
    """Send one row to the n8n data table webhook."""
    url = settings.n8n_apps_order_url.strip()
    if not url:
        raise AppsOrderNotConfigured("N8N_APPS_ORDER_URL is not set")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=row)
    except httpx.HTTPError as exc:
        raise AppsOrderError(f"n8n request failed: {exc}") from exc
    if response.status_code >= 400:
        logger.warning(
            "n8n %s row rejected: %s %s", row.get("kind"), response.status_code, response.text[:300]
        )
        raise AppsOrderError(f"n8n responded {response.status_code}")
