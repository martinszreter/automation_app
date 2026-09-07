import re

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://startend:startend_dev@db:5432/startend"

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        self.database_url = re.sub(
            r"^postgres(ql)?://", "postgresql+asyncpg://", self.database_url
        )
        return self
    port: int = 80
    whatsapp_adapter: str = "mock"
    meta_whatsapp_token: str = ""
    meta_phone_number_id: str = ""

    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_pass: str = ""
    contact_to: str = ""

    public_base_url: str = ""
    session_secret: str = "dev-session-secret-change-me"
    session_https_only: bool = False

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # List price on /x-autopilot/ is CHF 149 / month. Override to 100 for a CHF 1 smoke test.
    stripe_xautopilot_amount_cents: int = 14900
    stripe_xautopilot_mode: str = "payment"
    stripe_xautopilot_price_id: str = ""

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_sheets_refresh_token: str = ""
    google_sheets_spreadsheet_id: str = ""
    google_sheets_range: str = "Sheet1!A1:D20"
    google_sheets_reconnect_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
