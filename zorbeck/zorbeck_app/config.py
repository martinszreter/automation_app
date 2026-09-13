"""Environment-only configuration. Nothing here has a default that could pay,
mail or alert anywhere real: every outbound URL and key is empty until Railway
sets it, and the code degrades explicitly (503 / logged) when one is missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields

STRIPE_API_DEFAULT = "https://api.stripe.com/v1"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int_env(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    # Public origin of this service, e.g. https://zorbeck.ch — used for Stripe
    # success/cancel URLs. Empty falls back to the request's forwarded host.
    public_base_url: str = ""

    # Stripe (test mode until stated otherwise). Checkout is created over the
    # REST API with httpx; no SDK.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Optional Stripe Price id. When set, the amount below is ignored.
    stripe_price_id: str = ""
    # One offer, one price. Default is the list price; set 100 for the CHF 1
    # smoke test (then refund in the dashboard).
    price_cents: int = 4900
    # Overridable only so the CI stub can stand in for api.stripe.com.
    stripe_api_base: str = STRIPE_API_DEFAULT

    # HQ Mail Lane (n8n) — POST {subject, body, to}. Sends the intake
    # confirmation to the buyer.
    hq_mail_webhook_url: str = ""
    # Engine Error Alerts (n8n workflow N6gYXlzZUn6OXOs4) — POST
    # {app, workflow, node, message, description, stack, url, mode}.
    alert_webhook_url: str = ""
    # Lead row sink (n8n) — every intake, paid or not, as one JSON row.
    signup_webhook_url: str = ""

    # Persistent marketplace state. Never silently use an ephemeral production DB.
    marketplace_db_path: str = ""
    cookie_secure: bool = True
    admin_bootstrap_hash: str = ""
    promotion_link: str = ""
    promotion_link_id: str = ""
    smoke_link: str = ""
    smoke_link_id: str = ""
    marketplace_webhook_secret: str = ""

    # CI only: mounts the in-process Stripe/mail/alert stub under /_stub.
    # Never set this on the Railway service.
    stub: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            public_base_url=_env("PUBLIC_BASE_URL").rstrip("/"),
            stripe_secret_key=_env("STRIPE_SECRET_KEY"),
            stripe_webhook_secret=_env("STRIPE_WEBHOOK_SECRET"),
            stripe_price_id=_env("STRIPE_PRICE_ID"),
            price_cents=_int_env("ZORBECK_PRICE_CENTS", 4900),
            stripe_api_base=_env("STRIPE_API_BASE", STRIPE_API_DEFAULT).rstrip("/") or STRIPE_API_DEFAULT,
            hq_mail_webhook_url=_env("HQ_MAIL_WEBHOOK_URL"),
            alert_webhook_url=_env("ALERT_WEBHOOK_URL"),
            signup_webhook_url=_env("SIGNUP_WEBHOOK_URL"),
            marketplace_db_path=_env("ZORBECK_DATABASE_PATH"),
            cookie_secure=_env("ZORBECK_COOKIE_SECURE", "true") != "false",
            admin_bootstrap_hash=_env("ZORBECK_ADMIN_BOOTSTRAP_HASH"),
            promotion_link=_env("ZORBECK_PROMOTION_LINK"),
            promotion_link_id=_env("ZORBECK_PROMOTION_LINK_ID"),
            smoke_link=_env("ZORBECK_SMOKE_LINK"),
            smoke_link_id=_env("ZORBECK_SMOKE_LINK_ID"),
            marketplace_webhook_secret=_env("ZORBECK_MARKETPLACE_WEBHOOK_SECRET"),
            stub=_env("ZORBECK_STUB") in {"1", "true", "yes"},
        )

    def reload(self) -> None:
        """Re-read the environment in place (tests, stub bootstrap)."""
        fresh = self.from_env()
        for field in fields(self):
            setattr(self, field.name, getattr(fresh, field.name))


settings = Settings.from_env()
