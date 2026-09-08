import re

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anything Postgres-shaped (postgres://, postgresql://, postgresql+psycopg://…)
# is rewritten onto the one async driver this app ships with.
_POSTGRES_SCHEME = re.compile(r"^postgres(?:ql)?(?:\+\w+)?://")

DEV_SESSION_SECRET = "dev-session-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://startend:startend_dev@db:5432/startend"

    whatsapp_adapter: str = "mock"
    meta_whatsapp_token: str = ""
    meta_phone_number_id: str = ""

    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_pass: str = ""
    contact_to: str = ""

    public_base_url: str = ""
    session_secret: str = DEV_SESSION_SECRET
    session_https_only: bool = False

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # List price on /x-autopilot/ is CHF 149 / month. Override to 100 for a CHF 1 smoke test.
    stripe_xautopilot_amount_cents: int = 14900
    stripe_xautopilot_mode: str = "payment"
    stripe_xautopilot_price_id: str = ""

    # /x-autopilot tiers — one Stripe Price id per published tier. Unset means
    # the tier's button stays disabled instead of pointing at a broken link.
    price_id_xa_149: str = ""
    price_id_xa_330: str = ""
    price_id_xa_990: str = ""
    # The tier Prices are recurring monthly, so their sessions run in
    # subscription mode. Override to "payment" for one-time tier Prices.
    stripe_xa_tier_mode: str = "subscription"
    # n8n data table webhook that stores the xautopilot_orders rows.
    n8n_xautopilot_order_url: str = ""
    # Where the success page sends the buyer to authorize posting on X.
    # Empty falls back to the on-site onboarding form.
    x_oauth_onboarding_url: str = ""

    # /apps — WhatsApp reservation setup. One Checkout Session carries both
    # prices: the one-time setup fee and the monthly subscription.
    price_id_apps_setup: str = ""
    price_id_apps_monthly: str = ""
    # n8n data table webhook that stores the apps_orders rows.
    n8n_apps_order_url: str = ""

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_sheets_refresh_token: str = ""
    google_sheets_spreadsheet_id: str = ""
    google_sheets_range: str = "Sheet1!A1:D20"
    google_sheets_reconnect_key: str = ""

    # HQ Mail Lane — reusable outbound email webhook for internal HQ
    # notifications (e.g. asking Marcin to reconnect Sheets access). Env-only:
    # a webhook URL is a write key, so it never enters the repo.
    hq_mail_webhook_url: str = ""

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        self.database_url = _POSTGRES_SCHEME.sub("postgresql+asyncpg://", self.database_url)
        return self


settings = Settings()
