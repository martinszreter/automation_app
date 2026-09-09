import re

from app.parsing.base import Intent, MessageParser, ParsedMessage

CONFIRM_KEYWORDS = {"ja", "bestätige", "bestätigen", "bestätigt", "yes", "ok", "jap"}
CANCEL_KEYWORDS = {"nein", "absagen", "stornieren", "stornierung", "cancel", "no"}

# A bare number is a new party size. Zero is not a table, and a number with
# more digits than any real table is a typo or a phone number, not a request.
_PARTY_SIZE = re.compile(r"\d{1,3}")


class RuleBasedParser(MessageParser):
    """Simple keyword/regex parser for German guest messages."""

    def parse(self, text: str) -> ParsedMessage:
        normalized = text.strip().lower()

        if _PARTY_SIZE.fullmatch(normalized) and int(normalized) > 0:
            return ParsedMessage(intent=Intent.CHANGE_PARTY_SIZE, party_size=int(normalized))

        if normalized in CONFIRM_KEYWORDS:
            return ParsedMessage(intent=Intent.CONFIRM)

        if normalized in CANCEL_KEYWORDS:
            return ParsedMessage(intent=Intent.CANCEL)

        return ParsedMessage(intent=Intent.UNKNOWN)
