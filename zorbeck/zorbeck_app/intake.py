"""The buyer's intake: what they typed, validated, and how it travels through
Stripe metadata into the confirmation. No I/O here."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from zorbeck_app.messages import de
from zorbeck_app.money import chf, chf_plain

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_BUDGET = 1_000_000_000


class IntakeError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class Intake:
    email: str
    city: str
    budget_min: int | None
    budget_max: int | None

    def metadata(self) -> dict[str, str]:
        """What is written into the Checkout Session so the webhook and the
        success page can rebuild the intake without any database."""
        return {
            "city": self.city,
            "budget_min": "" if self.budget_min is None else str(self.budget_min),
            "budget_max": "" if self.budget_max is None else str(self.budget_max),
        }

    @property
    def budget_label(self) -> str:
        lo, hi = self.budget_min, self.budget_max
        if lo is None and hi is None:
            return de.BUDGET_UNLIMITED
        if lo is None:
            return de.BUDGET_TO.format(max=chf_plain(hi))
        if hi is None:
            return de.BUDGET_FROM.format(min=chf_plain(lo))
        return de.BUDGET_RANGE.format(min=chf_plain(lo), max=chf_plain(hi))

    def as_row(self, **extra: Any) -> dict[str, Any]:
        return {
            "email": self.email,
            "city": self.city,
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "source": "zorbeck-landing",
            **extra,
        }


def _budget(raw: Any) -> int | None:
    text = str(raw or "").strip().replace("'", "").replace(" ", "")
    if not text:
        return None
    if not text.isdigit() or int(text) > MAX_BUDGET:
        raise IntakeError("budget", de.ERROR_BUDGET)
    return int(text)


def parse_intake(data: dict[str, Any]) -> Intake:
    email = str(data.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise IntakeError("email", de.ERROR_EMAIL)
    city = " ".join(str(data.get("city") or "").split())[:80]
    if not city:
        raise IntakeError("city", de.ERROR_CITY)
    budget_min = _budget(data.get("budget_min"))
    budget_max = _budget(data.get("budget_max"))
    if budget_min is not None and budget_max is not None and budget_max <= budget_min:
        raise IntakeError("budget", de.ERROR_BUDGET_ORDER)
    return Intake(email=email, city=city, budget_min=budget_min, budget_max=budget_max)


def intake_from_session(session: dict[str, Any]) -> Intake:
    """Rebuild the intake from a Checkout Session's metadata + e-mail."""
    metadata = session.get("metadata") or {}
    details = session.get("customer_details") or {}
    email = str(details.get("email") or session.get("customer_email") or "").strip().lower()

    def number(key: str) -> int | None:
        value = str(metadata.get(key) or "").strip()
        return int(value) if value.isdigit() else None

    return Intake(
        email=email,
        city=str(metadata.get("city") or "").strip() or "Ihrer Stadt",
        budget_min=number("budget_min"),
        budget_max=number("budget_max"),
    )


def timeline_for(city: str) -> list[tuple[str, str]]:
    """The first-value steps with the buyer's city filled in."""
    return [(when, what.format(city=city)) for when, what in de.TIMELINE]


def confirmation_mail(intake: Intake, amount_cents: int, base_url: str) -> tuple[str, str]:
    """Subject and body of the confirmation the buyer receives."""
    subject = de.MAIL_SUBJECT.format(city=intake.city)
    steps = "\n".join(f"- {when}: {what}" for when, what in timeline_for(intake.city))
    body = de.MAIL_BODY.format(
        amount=chf(amount_cents),
        city=intake.city,
        budget=intake.budget_label,
        email=intake.email,
        timeline=steps,
        base_url=base_url.rstrip("/"),
    )
    return subject, body
