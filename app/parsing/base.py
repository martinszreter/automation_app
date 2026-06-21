from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class Intent(str, Enum):
    CONFIRM = "confirm"
    CANCEL = "cancel"
    CHANGE_PARTY_SIZE = "change_party_size"
    UNKNOWN = "unknown"


@dataclass
class ParsedMessage:
    intent: Intent
    party_size: int | None = None


class MessageParser(ABC):
    """Interface for parsing inbound guest messages into structured intents.
    Swap implementations (rule-based → AI) via the same pattern as WhatsAppAdapter."""

    @abstractmethod
    def parse(self, text: str) -> ParsedMessage:
        ...
