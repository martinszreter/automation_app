import pytest

from app.parsing.base import Intent
from app.parsing.rule_based import RuleBasedParser


@pytest.fixture
def parser() -> RuleBasedParser:
    return RuleBasedParser()


class TestConfirmIntent:
    def test_ja(self, parser: RuleBasedParser) -> None:
        result = parser.parse("ja")
        assert result.intent == Intent.CONFIRM

    def test_bestaetige(self, parser: RuleBasedParser) -> None:
        result = parser.parse("bestätige")
        assert result.intent == Intent.CONFIRM

    def test_ok(self, parser: RuleBasedParser) -> None:
        result = parser.parse("OK")
        assert result.intent == Intent.CONFIRM

    def test_yes(self, parser: RuleBasedParser) -> None:
        result = parser.parse("Yes")
        assert result.intent == Intent.CONFIRM


class TestCancelIntent:
    def test_nein(self, parser: RuleBasedParser) -> None:
        result = parser.parse("nein")
        assert result.intent == Intent.CANCEL

    def test_absagen(self, parser: RuleBasedParser) -> None:
        result = parser.parse("absagen")
        assert result.intent == Intent.CANCEL

    def test_stornieren(self, parser: RuleBasedParser) -> None:
        result = parser.parse("stornieren")
        assert result.intent == Intent.CANCEL


class TestPartySizeChange:
    def test_number(self, parser: RuleBasedParser) -> None:
        result = parser.parse("4")
        assert result.intent == Intent.CHANGE_PARTY_SIZE
        assert result.party_size == 4

    def test_large_number(self, parser: RuleBasedParser) -> None:
        result = parser.parse("12")
        assert result.intent == Intent.CHANGE_PARTY_SIZE
        assert result.party_size == 12


class TestUnknown:
    def test_random_text(self, parser: RuleBasedParser) -> None:
        result = parser.parse("was ist das?")
        assert result.intent == Intent.UNKNOWN

    def test_empty(self, parser: RuleBasedParser) -> None:
        result = parser.parse("")
        assert result.intent == Intent.UNKNOWN

    def test_whitespace_handling(self, parser: RuleBasedParser) -> None:
        result = parser.parse("  Ja  ")
        assert result.intent == Intent.CONFIRM
