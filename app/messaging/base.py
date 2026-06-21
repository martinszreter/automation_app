from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OutgoingMessage:
    to_phone: str
    body: str


class WhatsAppAdapter(ABC):
    """Interface for sending WhatsApp messages. Swap implementations via WHATSAPP_ADAPTER env var."""

    @abstractmethod
    async def send_message(self, message: OutgoingMessage) -> dict:
        ...

    @abstractmethod
    async def verify_webhook(self, token: str, challenge: str) -> str:
        ...
