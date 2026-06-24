import logging
import re

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def normalize_db_url(url: str) -> str:
    return re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", url)


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://startend:startend_dev@db:5432/startend"
    port: int = 80
    whatsapp_adapter: str = "mock"
    meta_whatsapp_token: str = ""
    meta_phone_number_id: str = ""

    @field_validator("database_url", mode="after")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        return normalize_db_url(v)

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
logger.info("database_url scheme: %s", settings.database_url.split("://")[0])
