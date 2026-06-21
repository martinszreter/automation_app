from app.core.config import settings
from app.messaging.base import WhatsAppAdapter
from app.messaging.mock_adapter import MockWhatsAppAdapter


def get_whatsapp_adapter() -> WhatsAppAdapter:
    if settings.whatsapp_adapter == "mock":
        return MockWhatsAppAdapter()
    raise ValueError(f"Unknown WhatsApp adapter: {settings.whatsapp_adapter}")
