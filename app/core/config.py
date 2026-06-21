from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://startend:startend_dev@db:5432/startend"
    whatsapp_adapter: str = "mock"
    meta_whatsapp_token: str = ""
    meta_phone_number_id: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
