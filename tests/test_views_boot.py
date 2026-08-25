"""Tests for the portfolio boot script that now lives in the repo.

The boot script itself only runs on Railway, but the two pieces that decide
what ends up in /srv — which canon row wins, and whether a repo-backed page
gets its runtime URL — are pure functions and are worth pinning down here.
"""

import importlib.util
from pathlib import Path

import pytest

_BOOT_DIR = Path(__file__).resolve().parent.parent / "boot"


def _load_views_boot():
    spec = importlib.util.spec_from_file_location("views_boot", _BOOT_DIR / "views_boot.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


views_boot = _load_views_boot()


def test_highest_version_wins() -> None:
    rows = [
        {"version": 6, "content": "older"},
        {"version": 8, "content": "canonical"},
        {"version": 7, "content": "middle"},
    ]
    assert views_boot.pick_content(rows, "X_OPS_HTML") == "canonical"


def test_rows_without_content_are_ignored() -> None:
    rows = [{"version": 9, "content": ""}, {"version": 4, "content": "usable"}]
    assert views_boot.pick_content(rows, "STRAT_HTML") == "usable"


def test_empty_canon_key_is_an_error() -> None:
    with pytest.raises(ValueError, match="no usable row"):
        views_boot.pick_content([], "MOBILE_OPS_HTML")


def test_placeholder_is_filled_from_the_environment() -> None:
    filled = views_boot.fill_placeholders(
        "fetch('__BUS_STATE_URL__')", {"BUS_STATE_URL": "https://example.invalid/hook"}
    )
    assert filled == "fetch('https://example.invalid/hook')"


def test_missing_variable_fails_loudly_instead_of_shipping_the_placeholder() -> None:
    with pytest.raises(ValueError, match="BUS_STATE_URL"):
        views_boot.fill_placeholders("fetch('__BUS_STATE_URL__')", {})


def test_page_without_placeholders_needs_no_environment() -> None:
    assert views_boot.fill_placeholders("<p>static</p>", {}) == "<p>static</p>"


def test_bus_view_is_registered_like_the_other_views() -> None:
    files = [filename for _, _, filename in views_boot.REPO_VIEWS]
    assert "bus-k4x9m2.html" in files

    canon_files = [filename for _, filename in views_boot.CANON_VIEWS]
    assert canon_files == [
        "trading-k4x9m2.html",
        "x-ops-k4x9m2.html",
        "grokywood-ops-k4x9m2.html",
        "mobile-ops-k4x9m2.html",
    ]


def test_bus_page_ships_with_a_placeholder_not_a_live_endpoint() -> None:
    page = (_BOOT_DIR / "pages" / "bus-k4x9m2.html").read_text(encoding="utf-8")
    assert "__BUS_STATE_URL__" in page
    assert "n8n.cloud" not in page


def test_no_secrets_are_baked_into_the_boot_script() -> None:
    source = (_BOOT_DIR / "views_boot.py").read_text(encoding="utf-8")
    assert "n8n.cloud" not in source
    assert "CANON_RW_URL" in source
