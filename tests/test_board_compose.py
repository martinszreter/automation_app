"""The composed board (ptf-k4x9m2): live layer from the checklist JSON on top
of the canon BOARD_HTML, which must come through unchanged."""

import importlib.util
import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_DIR = _ROOT / "boot"
_FIXTURE = (_ROOT / "ci" / "fixtures" / "BOARD_HTML.html").read_text(encoding="utf-8")


def _load_views_boot():
    spec = importlib.util.spec_from_file_location("views_boot_board", _BOOT_DIR / "views_boot.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


vb = _load_views_boot()


def _checklist() -> dict:
    return vb.load_checklist((_BOOT_DIR / "data" / "checklist.json").read_text(encoding="utf-8"))


# --- checklist ------------------------------------------------------------------


def test_repo_checklist_is_valid_and_targets_25() -> None:
    checklist = _checklist()
    assert checklist["target"] == 25
    assert len(checklist["initiatives"]) == 25
    assert 0 < vb.live_count(checklist) <= 25


def test_checklist_rejects_a_row_without_a_stage() -> None:
    bad = json.dumps({"initiatives": [{"id": "a", "name": "A", "next": "x", "owner": "MARCIN"}]})
    with pytest.raises(ValueError, match="missing `stage`"):
        vb.load_checklist(bad)


def test_checklist_rejects_duplicate_ids_and_unknown_stages() -> None:
    row = {"id": "a", "name": "A", "stage": "build", "next": "x", "owner": "MARCIN"}
    with pytest.raises(ValueError, match="appears twice"):
        vb.load_checklist(json.dumps({"initiatives": [row, dict(row)]}))
    with pytest.raises(ValueError, match="unknown stage"):
        vb.load_checklist(json.dumps({"initiatives": [dict(row, stage="soon")]}))


def test_live_is_counted_only_when_literally_true() -> None:
    rows = [
        {"id": "a", "name": "A", "stage": "live", "next": "x", "owner": "MARCIN", "live": True},
        {"id": "b", "name": "B", "stage": "sell", "next": "x", "owner": "MARCIN", "live": False},
        {"id": "c", "name": "C", "stage": "sell", "next": "x", "owner": "MARCIN"},
    ]
    assert vb.live_count(vb.load_checklist(json.dumps({"initiatives": rows}))) == 1


def test_click_queue_takes_explicit_marcin_actions_and_rows_he_owns() -> None:
    rows = [
        {"id": "a", "name": "A", "stage": "live", "next": "x", "owner": "CLAUDE_CLAUDECODE",
         "marcin": {"action": "Refund the CHF 1 test", "link": "https://example.invalid/a"}},
        {"id": "b", "name": "B", "stage": "spec", "next": "Decide the name", "owner": "MARCIN"},
        {"id": "c", "name": "C", "stage": "build", "next": "y", "owner": "GPT_CURSOR"},
    ]
    queue = vb.click_queue(vb.load_checklist(json.dumps({"initiatives": rows})))
    assert [item["id"] for item in queue] == ["a", "b"]
    assert queue[0]["action"] == "Refund the CHF 1 test"
    assert queue[1]["action"] == "Decide the name"


# --- composing --------------------------------------------------------------------


def test_canon_body_and_styles_come_through_unchanged() -> None:
    page = vb.compose_board(_FIXTURE, _checklist(), built_at="2026-09-08 10:00Z")
    _style, body, _ = vb.split_canon(_FIXTURE)
    assert body in page  # byte for byte
    assert "<!-- FIXTURE_BOARD_CANON -->" in page
    assert ".scroll{overflow-x:auto}" in page  # canon css carried over
    assert "Views registry" in page


def test_live_counter_and_stamp_are_rendered_from_the_checklist() -> None:
    checklist = _checklist()
    page = vb.compose_board(_FIXTURE, checklist, built_at="2026-09-08 10:00Z")
    assert f'<b id="lb-live">{vb.live_count(checklist)}/25</b>' in page
    assert 'id="lb-updated">2026-09-08</b>' in page
    assert "board built <b>2026-09-08 10:00Z</b>" in page


def test_every_initiative_gets_a_row_with_stage_next_owner_blocker() -> None:
    checklist = _checklist()
    page = vb.compose_board(_FIXTURE, checklist, built_at="x")
    for row in checklist["initiatives"]:
        assert f'id="i-{row["id"]}"' in page
    assert page.count('<li class="lb-row') == 25
    assert 'data-l="Stage"' in page and 'data-l="Next"' in page
    assert 'data-l="Owner"' in page and 'data-l="Blocker"' in page
    assert "Paper only by rule" in page


def test_composed_board_has_no_external_fonts_or_requests() -> None:
    page = vb.compose_board(_FIXTURE, _checklist(), built_at="x")
    assert "fonts.googleapis" not in page
    assert "fonts.gstatic" not in page
    assert not re.search(r"<link[^>]+rel=[\"']?(stylesheet|preconnect)", page)
    assert "<script src=" not in page
    _, _, dropped = vb.split_canon(_FIXTURE)
    assert len(dropped) == 2  # the fixture's preconnect + stylesheet were reported


def test_composed_page_is_a_valid_shell_with_viewport_and_title() -> None:
    page = vb.compose_board(_FIXTURE, _checklist(), built_at="x")
    assert page.startswith("<!DOCTYPE html>")
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in page
    assert "<title>STARTEND — Portfolio</title>" in page
    assert page.count("<html") == 1 and page.count("<body") == 1


def test_recomposing_an_already_composed_page_does_not_nest_it() -> None:
    checklist = _checklist()
    once = vb.compose_board(_FIXTURE, checklist, built_at="x")
    twice = vb.compose_board(once, checklist, built_at="x")
    assert twice == once
    assert twice.count("<!-- FIXTURE_BOARD_CANON -->") == 1
    assert twice.count('id="lb-live"') == 1


def test_html_in_checklist_values_is_escaped() -> None:
    rows = [{"id": "a", "name": "<img src=x onerror=alert(1)>", "stage": "build",
             "next": "x", "owner": "MARCIN", "blocker": "<b>bold</b>"}]
    page = vb.compose_board(_FIXTURE, vb.load_checklist(json.dumps({"initiatives": rows})), built_at="x")
    assert "<img src=x" not in page
    assert "&lt;img src=x" in page
    assert "<b>bold</b>" not in page
    assert "&lt;b&gt;bold&lt;/b&gt;" in page


def test_board_is_registered_as_a_composed_view() -> None:
    assert ("BOARD_HTML", "ptf-k4x9m2.html", "board") in vb.COMPOSED_VIEWS
    assert vb.CHECKLIST_FILE == "checklist-k4x9m2.json"


def test_disk_fallback_is_used_when_canon_is_unreachable(tmp_path: Path) -> None:
    srv = tmp_path / "ptf-k4x9m2.html"
    srv.write_text(_FIXTURE, encoding="utf-8")
    html, source = vb.read_canon_or_disk("http://127.0.0.1:9/", "BOARD_HTML", str(srv))
    assert source == "disk"
    assert html == _FIXTURE
    with pytest.raises(ValueError, match="no canon content"):
        vb.read_canon_or_disk("", "BOARD_HTML", str(tmp_path / "missing.html"))
