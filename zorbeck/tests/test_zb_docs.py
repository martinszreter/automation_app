"""The handover and the self-review are part of the product: a stranger who
inherits the service must find what they need without asking."""

from pathlib import Path

import pytest

ZORBECK = Path(__file__).resolve().parent.parent
README = (ZORBECK / "README.md").read_text(encoding="utf-8")
REVIEW = (ZORBECK / "docs" / "REVIEW_2026-09-08.md").read_text(encoding="utf-8")


def test_readme_has_a_handover_with_everything_a_stranger_needs() -> None:
    assert "## HANDOVER" in README
    for heading in ("### URLs", "### Environment variables", "### How a stranger buys", "### How to refund", "### CI"):
        assert heading in README, heading


@pytest.mark.parametrize(
    "variable",
    [
        "PUBLIC_BASE_URL",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "ZORBECK_PRICE_CENTS",
        "HQ_MAIL_WEBHOOK_URL",
        "ALERT_WEBHOOK_URL",
        "SIGNUP_WEBHOOK_URL",
        "ZORBECK_STUB",
    ],
)
def test_every_setting_is_documented(variable: str) -> None:
    assert f"`{variable}`" in README, variable


def test_handover_documents_the_alert_handler_and_the_webhook_endpoint() -> None:
    assert "N6gYXlzZUn6OXOs4" in README
    assert "/stripe/webhook" in README
    assert "checkout.session.completed" in README
    assert "/healthz" in README


def test_self_review_is_honest_about_gaps_and_names_the_prs() -> None:
    for heading in ("## Quality bar", "## What I would flag", "## Tests", "## Open items"):
        assert heading in REVIEW, heading
    for pr in ("/pull/62", "/pull/63", "/pull/64"):
        assert pr in REVIEW, pr
    # The one thing a buyer could be let down by is written down, not hidden.
    assert "not in this repo" in REVIEW
    assert "ZORBECK_STUB" in REVIEW
