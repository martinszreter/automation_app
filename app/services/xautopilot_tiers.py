"""The three /x-autopilot tiers: Stripe Checkout payload + landing buttons.

One tier is one Stripe Price created in the dashboard. The Price ids arrive
through the environment (``PRICE_ID_XA_149`` / ``_330`` / ``_990``) — no amount
and no Price id is ever hard-coded here, so a price change never needs a deploy.

A tier whose Price id is missing must not produce a broken link: the landing
page ships its buttons *disabled*, carrying ``data-missing-env`` with the name
of the variable that is missing, and the server upgrades a button to a real
link only for the tiers it can actually charge (:func:`render_tier_buttons`).
The safe state is therefore the state the file is written in — if the markup
ever drifts, the swap is a no-op and the button stays disabled.

The Stripe transport (auth, error mapping, signature checks) is the shared
helper in ``app.services.stripe_checkout``; this module only builds payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.stripe_checkout import StripeError, stripe_request

XA_PRODUCT = "x-autopilot"


class UnknownTier(ValueError):
    """The requested tier is not one of the three published tiers."""


class TierPriceNotConfigured(RuntimeError):
    """PRICE_ID_XA_<tier> is missing from the environment."""


@dataclass(frozen=True)
class Tier:
    slug: str
    env_var: str
    settings_attr: str
    # Shown on the landing page next to the button. The amount is copy, not a
    # charge: what Stripe bills is whatever the Price id in env says.
    price_label: str
    scope_label: str

    @property
    def checkout_path(self) -> str:
        return f"/x-autopilot/checkout/{self.slug}"


TIERS: tuple[Tier, ...] = (
    Tier("149", "PRICE_ID_XA_149", "price_id_xa_149", "CHF 149", "3 posts per day"),
    Tier("330", "PRICE_ID_XA_330", "price_id_xa_330", "CHF 330", "5 posts per day"),
    Tier("990", "PRICE_ID_XA_990", "price_id_xa_990", "CHF 990", "Custom rhythm"),
)

TIERS_BY_SLUG: dict[str, Tier] = {tier.slug: tier for tier in TIERS}


def get_tier(slug: str) -> Tier:
    tier = TIERS_BY_SLUG.get((slug or "").strip())
    if tier is None:
        raise UnknownTier(f"unknown tier {slug!r}")
    return tier


def tier_price_id(tier: Tier) -> str:
    return str(getattr(settings, tier.settings_attr, "") or "").strip()


def configured_tiers() -> set[str]:
    """Slugs of the tiers that currently have a Price id in the environment."""
    return {tier.slug for tier in TIERS if tier_price_id(tier)}


def checkout_urls(base_url: str) -> tuple[str, str]:
    """Success/cancel pair for a tier session.

    ``{CHECKOUT_SESSION_ID}`` is a Stripe placeholder — Stripe substitutes it
    when it redirects the buyer, so the success page can name the order.
    """
    base = base_url.rstrip("/")
    success = f"{base}/x-autopilot/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel = f"{base}/x-autopilot/"
    return success, cancel


def build_checkout_session_payload(
    base_url: str,
    tier: Tier,
    price_id: str,
    mode: str = "subscription",
) -> dict[str, str]:
    """Form-encoded body for POST /v1/checkout/sessions. Pure — unit-tested."""
    price = (price_id or "").strip()
    if not price:
        raise TierPriceNotConfigured(f"{tier.env_var} is not set")

    success_url, cancel_url = checkout_urls(base_url)
    payload = {
        "mode": mode,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "locale": "auto",
        "billing_address_collection": "required",
        "client_reference_id": XA_PRODUCT,
        "metadata[product]": XA_PRODUCT,
        "metadata[tier]": tier.slug,
        "metadata[price_id]": price,
        "line_items[0][price]": price,
        "line_items[0][quantity]": "1",
    }
    if mode == "subscription":
        # Repeated on the subscription so later invoice events stay attributable.
        payload["subscription_data[metadata][product]"] = XA_PRODUCT
        payload["subscription_data[metadata][tier]"] = tier.slug
    return payload


async def create_tier_checkout_session(base_url: str, slug: str) -> dict[str, Any]:
    tier = get_tier(slug)
    payload = build_checkout_session_payload(
        base_url,
        tier,
        tier_price_id(tier),
        settings.stripe_xa_tier_mode.strip() or "subscription",
    )
    session = await stripe_request("POST", "/checkout/sessions", payload)
    if not session.get("url"):
        raise StripeError("Checkout session missing url")
    return session


# --- landing page buttons -----------------------------------------------------


def disabled_button_html(tier: Tier) -> str:
    """The state the static file ships in: no link, and it says why."""
    return (
        f'<button class="btn btn-off" type="button" id="startBtn{tier.slug}" '
        f'data-tier="{tier.slug}" data-missing-env="{tier.env_var}" disabled>Start CHF {tier.slug}</button>'
    )


def link_button_html(tier: Tier) -> str:
    return (
        f'<a class="btn" id="startBtn{tier.slug}" data-tier="{tier.slug}" '
        f'href="{tier.checkout_path}">Start CHF {tier.slug}</a>'
    )


def render_tier_buttons(html: str, configured: set[str] | None = None) -> str:
    """Turn the disabled button of every configured tier into a checkout link."""
    live = configured_tiers() if configured is None else configured
    for tier in TIERS:
        if tier.slug in live:
            html = html.replace(disabled_button_html(tier), link_button_html(tier))
    return html
