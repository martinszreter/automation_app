from app.parsing.base import MessageParser
from app.parsing.rule_based import RuleBasedParser


def get_message_parser() -> MessageParser:
    return RuleBasedParser()
