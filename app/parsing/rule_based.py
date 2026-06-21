import re

from app.parsing.base import Intent, MessageParser, ParsedMessage

CONFIRM_KEYWORDS = {"ja", "bestätige", "bestätigen", "bestätigt", "yes", "ok", "jap"}
CANCEL_KEYWORDS = {"nein", "absagen", "stornieren", "stornierung", "cancel", "no"}


class RuleBasedParser(MessageParser):
    """Simple keyword/regex parser for German guest messages."""

    def parse(self, text: str) -> ParsedMessage:
        normalized = text.strip().lower()

        number_match = re.fullmatch(r"\d+", normalized)
        if number_match:
            return ParsedMessage(intent=Intent.CHANGE_PARTY_SIZE, party_size=int(normalized))

        if normalized in CONFIRM_KEYWORDS:
            return ParsedMessage(intent=Intent.CONFIRM)

        if normalized in CANCEL_KEYWORDS:
            return ParsedMessage(intent=Intent.CANCEL)

        return ParsedMessage(intent=Intent.UNKNOWN)
