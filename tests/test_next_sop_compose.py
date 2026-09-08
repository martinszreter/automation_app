"""NEXT and SOP views: Marcin's click queue first, collapsible sections, a
search box, and (for NEXT) the canon page carried over unchanged."""

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_DIR = _ROOT / "boot"
_NEXT_FIXTURE = (_ROOT / "ci" / "fixtures" / "NEXT_HTML.html").read_text(encoding="utf-8")


def _load_views_boot():
    spec = importlib.util.spec_from_file_location("views_boot_next", _BOOT_DIR / "views_boot.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


vb = _load_views_boot()


def _checklist() -> dict:
    return vb.load_checklist((_BOOT_DIR / "data" / "checklist.json").read_text(encoding="utf-8"))


def _sop() -> dict:
    return vb.load_sop((_BOOT_DIR / "data" / "sop.json").read_text(encoding="utf-8"))


def _first_section_id(page: str) -> str:
    start = page.index('<details class="lb-sec"')
    return page[start:].split('id="', 1)[1].split('"', 1)[0]


# --- data -----------------------------------------------------------------------


def test_repo_sop_is_valid() -> None:
    sop = _sop()
    assert len(sop["sops"]) >= 5
    assert {"redeploy-hq", "update-checklist", "chf1-test", "error-alerts"} <= {s["id"] for s in sop["sops"]}


def test_sop_rejects_missing_steps_and_duplicate_ids() -> None:
    base = {"id": "a", "title": "A", "owner": "MARCIN", "when": "now", "steps": ["x"]}
    with pytest.raises(ValueError, match="non-empty list of step"):
        vb.load_sop(json.dumps({"sops": [dict(base, steps=[])]}))
    with pytest.raises(ValueError, match="appears twice"):
        vb.load_sop(json.dumps({"sops": [base, dict(base)]}))


def test_sop_json_carries_no_write_keys() -> None:
    text = (_BOOT_DIR / "data" / "sop.json").read_text(encoding="utf-8")
    assert "n8n.cloud/webhook" not in text
    assert "railway.app" not in text


# --- NEXT ---------------------------------------------------------------------------


def test_next_puts_the_click_queue_first_and_keeps_canon_unchanged() -> None:
    page = vb.compose_next(_NEXT_FIXTURE, _checklist(), built_at="x")
    assert _first_section_id(page) == "click-queue"
    assert "Marcin — click queue" in page
    _style, body, _ = vb.split_canon(_NEXT_FIXTURE)
    assert body in page
    assert "<!-- FIXTURE_NEXT_CANON -->" in page
    assert page.count("<!DOCTYPE html>") == 1


def test_next_has_search_collapsible_sections_and_queue_items() -> None:
    checklist = _checklist()
    page = vb.compose_next(_NEXT_FIXTURE, checklist, built_at="x")
    assert '<input id="lb-search" type="search"' in page
    assert 'id="lb-search-count"' in page
    for section_id in ("click-queue", "blockers", "by-owner"):
        assert f'<details class="lb-sec" id="{section_id}"' in page
    # The canon page sits inside its own collapsible section, markers intact.
    assert '<details class="lb-sec lb" id="canon-next" open>' in page
    assert page.index('id="canon-next"') < page.index(vb.CANON_BODY_BEGIN) < page.index("</details>\n<script>")
    queue = vb.click_queue(checklist)
    assert len(queue) > 0
    assert page.count('<li class="lb-qi" data-s>') >= len(queue) + len(checklist["initiatives"])
    assert f'<b id="lb-queue">{len(queue)}</b>' in page
    for item in queue:
        assert vb.esc(item["action"]) in page or vb.rich(item["action"]) in page


def test_next_lists_blockers_with_their_owner() -> None:
    page = vb.compose_next(_NEXT_FIXTURE, _checklist(), built_at="x")
    assert "Checkout gate not passed" in page
    assert "4.1 · ChamDigital (Swiss websites, site-engine) · GPT_CURSOR" in page


# --- SOP ----------------------------------------------------------------------------


def test_sop_view_puts_the_click_queue_first_then_one_section_per_sop() -> None:
    sop = _sop()
    page = vb.compose_sop("", _checklist(), sop, built_at="x")
    assert _first_section_id(page) == "click-queue"
    for item in sop["sops"]:
        assert f'<details class="lb-sec" id="sop-{item["id"]}" open>' in page
        assert vb.esc(item["title"]) in page
    assert page.count("<li data-s>") == sum(len(item["steps"]) for item in sop["sops"])
    assert '<input id="lb-search" type="search"' in page
    assert "<!-- canon:body begin --><!-- canon:body end -->" in page


def test_sop_steps_render_code_spans_but_no_other_markup() -> None:
    sop = {"sops": [{"id": "a", "title": "T <b>x</b>", "owner": "MARCIN", "when": "w",
                     "steps": ["Run `pytest -q` then <script>alert(1)</script>"]}]}
    page = vb.compose_sop("", _checklist(), vb.load_sop(json.dumps(sop)), built_at="x")
    assert "<code>pytest -q</code>" in page
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "T &lt;b&gt;x&lt;/b&gt;" in page


def test_sop_view_refuses_to_render_without_sop_data() -> None:
    with pytest.raises(ValueError, match="needs the sop data"):
        vb.compose_sop("", _checklist(), None, built_at="x")


def test_next_and_sop_are_registered_composed_views() -> None:
    assert ("NEXT_HTML", "next-k4x9m2.html", "next") in vb.COMPOSED_VIEWS
    assert ("SOP_HTML", "sop-k4x9m2.html", "sop") in vb.COMPOSED_VIEWS
    assert "SOP_HTML" in vb.REPO_ONLY_COMPOSED
    assert "NEXT_HTML" not in vb.REPO_ONLY_COMPOSED


def test_composed_views_have_no_external_fonts() -> None:
    for page in (
        vb.compose_next(_NEXT_FIXTURE, _checklist(), built_at="x"),
        vb.compose_sop("", _checklist(), _sop(), built_at="x"),
    ):
        assert "fonts.googleapis" not in page
        assert '<link rel="stylesheet"' not in page
        assert "<script src=" not in page
