"""Intake parsing, CHF formatting and the confirmation mail — no I/O."""

import pytest

from zorbeck_app.intake import (
    Intake,
    IntakeError,
    confirmation_mail,
    intake_from_session,
    parse_intake,
    timeline_for,
)
from zorbeck_app.money import chf, chf_plain


@pytest.mark.parametrize(
    "cents, expected",
    [(100, "CHF 1"), (4900, "CHF 49"), (139000, "CHF 1'390"), (123456789, "CHF 1'234'567.89"), (150, "CHF 1.50")],
)
def test_chf_uses_apostrophe_thousands(cents: int, expected: str) -> None:
    assert chf(cents) == expected


def test_chf_plain_groups_whole_francs() -> None:
    assert chf_plain(1200000) == "CHF 1'200'000"
    assert chf_plain(None) == ""


def test_valid_intake_is_normalized() -> None:
    intake = parse_intake({"email": " Anna@Beispiel.CH ", "city": "  Zug  ", "budget_min": "500'000", "budget_max": "1 200 000"})
    assert intake == Intake(email="anna@beispiel.ch", city="Zug", budget_min=500000, budget_max=1200000)
    assert intake.metadata() == {"city": "Zug", "budget_min": "500000", "budget_max": "1200000"}
    assert intake.budget_label == "CHF 500'000 bis CHF 1'200'000"


@pytest.mark.parametrize(
    "data, field",
    [
        ({"email": "nope", "city": "Zug"}, "email"),
        ({"email": "a@b.ch", "city": "   "}, "city"),
        ({"email": "a@b.ch", "city": "Zug", "budget_max": "viel"}, "budget"),
        ({"email": "a@b.ch", "city": "Zug", "budget_min": "900000", "budget_max": "800000"}, "budget"),
        ({"email": "a@b.ch", "city": "Zug", "budget_max": "-5"}, "budget"),
    ],
)
def test_bad_intake_names_the_field_in_german(data: dict, field: str) -> None:
    with pytest.raises(IntakeError) as info:
        parse_intake(data)
    assert info.value.field == field
    assert "Sie" in info.value.message or "Bitte" in info.value.message
    assert "ß" not in info.value.message


def test_budget_labels_cover_every_shape() -> None:
    assert Intake("a@b.ch", "Zug", None, None).budget_label == "ohne Obergrenze"
    assert Intake("a@b.ch", "Zug", None, 900000).budget_label == "bis CHF 900'000"
    assert Intake("a@b.ch", "Zug", 300000, None).budget_label == "ab CHF 300'000"


def test_intake_is_rebuilt_from_session_metadata() -> None:
    session = {
        "customer_details": {"email": "Anna@Beispiel.ch"},
        "metadata": {"venture": "zorbeck", "city": "Basel", "budget_min": "", "budget_max": "750000"},
    }
    intake = intake_from_session(session)
    assert intake == Intake(email="anna@beispiel.ch", city="Basel", budget_min=None, budget_max=750000)


def test_intake_from_a_bare_session_still_works() -> None:
    intake = intake_from_session({"customer_email": "x@y.ch"})
    assert intake.city == "Ihrer Stadt"
    assert intake.email == "x@y.ch"


def test_confirmation_mail_is_german_and_names_the_intake() -> None:
    intake = Intake("anna@beispiel.ch", "Zug", None, 1200000)
    subject, body = confirmation_mail(intake, 4900, "https://zorbeck.example/")
    assert subject == "Ihr Zorbeck Deal-Alarm für Zug ist eingerichtet"
    assert "CHF 49" in body
    assert "Stadt: Zug" in body
    assert "bis CHF 1'200'000" in body
    assert "anna@beispiel.ch" in body
    assert "https://zorbeck.example/impressum" in body
    assert "ß" not in subject + body
    assert "Sie" in body
    # The first value: the timeline, with the city filled in, in the mail too.
    assert "Was jetzt passiert" in body
    for when, what in timeline_for("Zug"):
        assert f"- {when}: {what}" in body


def test_timeline_has_four_steps_with_the_city_and_no_human_in_it() -> None:
    steps = timeline_for("Basel")
    assert [when for when, _ in steps] == ["Sofort", "Innerhalb von 24 Stunden", "30 Tage lang", "Danach"]
    assert sum("Basel" in what for _, what in steps) == 2
    joined = " ".join(what for _, what in steps)
    for human in ("melden uns", "Rückruf", "Termin", "Berater"):
        assert human not in joined
    assert "ß" not in joined
