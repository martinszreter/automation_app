"""Stripe Checkout for /apps — WhatsApp reservation setup.

One Checkout Session carries both prices the offer is made of:

* ``PRICE_ID_APPS_SETUP``   — one-time setup fee (CHF 1'990)
* ``PRICE_ID_APPS_MONTHLY`` — recurring subscription (CHF 249 / month)

Stripe allows a one-time price next to a recurring one in ``mode=subscription``:
the one-time line lands on the first invoice, the recurring line starts the
subscription. Both amounts therefore come from the Stripe dashboard — no price
is ever hard-coded here.

The transport (auth, error mapping, signature checks) is the shared helper in
``app.services.stripe_checkout``; this module only builds the session payload.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.stripe_checkout import StripeError, stripe_request

APPS_PRODUCT = "apps"


class AppsPricesNotConfigured(RuntimeError):
    """PRICE_ID_APPS_SETUP / PRICE_ID_APPS_MONTHLY are missing from the env."""


def checkout_urls(base_url: str) -> tuple[str, str]:
    """Success/cancel pair for the /apps session.

    ``{CHECKOUT_SESSION_ID}`` is a Stripe placeholder — it is substituted by
    Stripe when it redirects the buyer, so the success page can name the order.
    """
    base = base_url.rstrip("/")
    success = f"{base}/apps/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel = f"{base}/apps/"
    return success, cancel


def build_checkout_session_payload(
    base_url: str,
    setup_price_id: str,
    monthly_price_id: str,
) -> dict[str, str]:
    """Form-encoded body for POST /v1/checkout/sessions. Pure — unit-tested."""
    setup = (setup_price_id or "").strip()
    monthly = (monthly_price_id or "").strip()
    missing = [
        name
        for name, value in (("PRICE_ID_APPS_SETUP", setup), ("PRICE_ID_APPS_MONTHLY", monthly))
        if not value
    ]
    if missing:
        raise AppsPricesNotConfigured(f"{' and '.join(missing)} is not set")

    success_url, cancel_url = checkout_urls(base_url)
    return {
        # Recurring line present -> the session has to run in subscription mode.
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "locale": "de",
        "billing_address_collection": "required",
        "client_reference_id": APPS_PRODUCT,
        "metadata[product]": APPS_PRODUCT,
        # Repeated on the subscription so later invoice events stay attributable.
        "subscription_data[metadata][product]": APPS_PRODUCT,
        "line_items[0][price]": setup,
        "line_items[0][quantity]": "1",
        "line_items[1][price]": monthly,
        "line_items[1][quantity]": "1",
    }


async def create_apps_checkout_session(base_url: str) -> dict[str, Any]:
    payload = build_checkout_session_payload(
        base_url,
        settings.price_id_apps_setup,
        settings.price_id_apps_monthly,
    )
    session = await stripe_request("POST", "/checkout/sessions", payload)
    if not session.get("url"):
        raise StripeError("Checkout session missing url")
    return session
