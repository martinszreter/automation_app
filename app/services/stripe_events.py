"""Which venture a Stripe event belongs to, and how to read a signed event.

One Stripe account serves both ventures, so a single webhook endpoint has to
decide where an event goes. Two signals are used, in this order:

* the Price ids carried by the object's line items — ``PRICE_ID_XA_*`` means
  x-autopilot, ``PRICE_ID_APPS_*`` means apps. The ids arrive through the
  environment, so a new tier routes itself without a code change;
* ``metadata.venture`` (or the older ``metadata.product``) on the Checkout
  Session or the subscription, for events whose line items Stripe did not
  expand — ``checkout.session.completed`` does not include them by default.

Nothing here talks to Stripe: every function takes the event Stripe already
sent, so the whole routing layer is unit-testable without the network.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.services.stripe_checkout import verify_stripe_signature

VENTURE_XAUTOPILOT = "x-autopilot"
VENTURE_APPS = "apps"

# What the two checkout builders write into metadata, plus the spellings a
# Stripe dashboard entry is likely to use for the same thing.
_VENTURE_BY_METADATA: dict[str, str] = {
    "x-autopilot": VENTURE_XAUTOPILOT,
    "x_autopilot": VENTURE_XAUTOPILOT,
    "xautopilot": VENTURE_XAUTOPILOT,
    "apps": VENTURE_APPS,
}

# Settings whose name starts with one of these prefixes holds a Price id that
# belongs to that venture. Prefix rather than a fixed list: PRICE_ID_XA_1490
# would route itself the day it is added to the environment.
_VENTURE_BY_SETTINGS_PREFIX: tuple[tuple[str, str], ...] = (
    ("price_id_xa", VENTURE_XAUTOPILOT),
    ("price_id_apps", VENTURE_APPS),
    ("stripe_xautopilot_price_id", VENTURE_XAUTOPILOT),
)

_METADATA_KEYS = ("venture", "product")


# --- reading Stripe objects ----------------------------------------------------


def identifier(value: Any) -> str:
    """Stripe returns ids either bare (``"cus_1"``) or expanded into an object."""
    if isinstance(value, dict):
        return str(value.get("id") or "")
    return str(value or "")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iso_timestamp(value: Any) -> str:
    """Stripe sends times as unix seconds; fall back to now when absent."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return now_iso()
    if seconds <= 0:
        return now_iso()
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(timespec="seconds")


# --- routing -------------------------------------------------------------------


def _rows(container: Any) -> list[dict[str, Any]]:
    """``line_items``/``items`` arrive either as a list object or a bare list."""
    if isinstance(container, dict):
        container = container.get("data")
    if not isinstance(container, list):
        return []
    return [row for row in container if isinstance(row, dict)]


def price_ids(obj: dict[str, Any]) -> list[str]:
    """Every Price id the object mentions, in the order Stripe listed them.

    Covers a Checkout Session with expanded ``line_items``, a subscription's
    ``items``, the legacy ``plan`` shape, and the ``metadata[price_id]`` the
    x-autopilot tier checkout writes for exactly this purpose.
    """
    found: list[str] = []

    def add(value: Any) -> None:
        identifier_ = identifier(value)
        if identifier_ and identifier_ not in found:
            found.append(identifier_)

    for key in ("line_items", "items"):
        for row in _rows(obj.get(key)):
            add(row.get("price"))
            add(row.get("plan"))
    add(obj.get("plan"))
    metadata = obj.get("metadata") or {}
    if isinstance(metadata, dict):
        add(metadata.get("price_id"))
    return found


def venture_by_price_id() -> dict[str, str]:
    """Price id -> venture, built from the environment on every call.

    Rebuilt each time rather than cached at import: the settings object is what
    tests and a redeploy change, and a stale map would silently misroute money.
    """
    mapping: dict[str, str] = {}
    for field in type(settings).model_fields:
        venture = next(
            (name for prefix, name in _VENTURE_BY_SETTINGS_PREFIX if field.startswith(prefix)),
            None,
        )
        if venture is None:
            continue
        value = str(getattr(settings, field, "") or "").strip()
        if value:
            mapping.setdefault(value, venture)
    return mapping


def venture_from_price_ids(obj: dict[str, Any]) -> str | None:
    known = venture_by_price_id()
    for price_id in price_ids(obj):
        venture = known.get(price_id)
        if venture is not None:
            return venture
    return None


def venture_from_metadata(obj: dict[str, Any]) -> str | None:
    metadata = obj.get("metadata") or {}
    if not isinstance(metadata, dict):
        return None
    for key in _METADATA_KEYS:
        venture = _VENTURE_BY_METADATA.get(str(metadata.get(key) or "").strip().lower())
        if venture is not None:
            return venture
    return None


def venture_for_object(obj: dict[str, Any]) -> str | None:
    """Which venture this Checkout Session or subscription belongs to.

    ``None`` means neither signal recognised it — the caller acknowledges the
    event and stores nothing, because guessing writes an order row into the
    wrong table.
    """
    return venture_from_price_ids(obj) or venture_from_metadata(obj)


def event_object(event: dict[str, Any]) -> dict[str, Any]:
    obj = (event.get("data") or {}).get("object")
    return obj if isinstance(obj, dict) else {}


def load_event(payload: bytes, signature_header: str) -> dict[str, Any]:
    """Verify the Stripe signature and decode the event.

    Raises ``StripeSignatureError`` when the header (or the configured secret)
    does not check out, ``ValueError`` when the body is not a JSON object.
    """
    verify_stripe_signature(payload, signature_header, settings.stripe_webhook_secret)
    try:
        event = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid payload") from exc
    if not isinstance(event, dict):
        raise ValueError("invalid payload")
    return event
