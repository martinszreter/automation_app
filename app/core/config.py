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

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
