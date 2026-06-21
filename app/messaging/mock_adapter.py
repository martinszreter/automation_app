import logging

from app.messaging.base import OutgoingMessage, WhatsAppAdapter

logger = logging.getLogger("startend.mock_whatsapp")


class MockWhatsAppAdapter(WhatsAppAdapter):
    """Logs messages instead of sending them. Used for local development."""

    def __init__(self) -> None:
        self.sent: list[OutgoingMessage] = []

    async def send_message(self, message: OutgoingMessage) -> dict:
        logger.info("MOCK WhatsApp → %s: %s", message.to_phone, message.body)
        self.sent.append(message)
        return {"status": "mock_sent", "to": message.to_phone}

    async def verify_webhook(self, token: str, challenge: str) -> str:
        logger.info("MOCK webhook verification: token=%s", token)
        return challenge
