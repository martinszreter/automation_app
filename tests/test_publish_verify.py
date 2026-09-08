"""scripts/publish_verify.py: served views must hash to what the repo renders."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("publish_verify", _ROOT / "scripts" / "publish_verify.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


pv = _load()


def _build(srv: Path) -> None:
    """Write /srv the way Railway does. Canon is unreachable here, so seed the
    disk fallback for the composed canon-backed views with the fixtures —
    exactly the path boot/views_boot.py takes when canon is down on a redeploy."""
    for filename, key in (("ptf-k4x9m2.html", "BOARD_HTML"), ("next-k4x9m2.html", "NEXT_HTML")):
        (srv / filename).write_text(
            (_ROOT / "ci" / "fixtures" / f"{key}.html").read_text(encoding="utf-8"), encoding="utf-8"
        )
    env = {**os.environ, "SRV_DIR": str(srv), "CANON_RW_URL": "", "BUS_STATE_URL": "https://example.invalid/bus"}
    env.pop("REPO_RAW_BASE", None)
    subprocess.run([sys.executable, str(_ROOT / "boot" / "views_boot.py")], env=env, capture_output=True)


def test_normalize_neutralises_stamp_title_and_canon_blocks() -> None:
    page = (
        "<title>From canon</title>"
        f"{pv.vb.CANON_STYLE_BEGIN}\nbody{{}}\n{pv.vb.CANON_STYLE_END}"
        "board built <b>2026-09-08 10:00Z</b>"
        f"{pv.vb.CANON_BODY_BEGIN}<div>canon</div>{pv.vb.CANON_BODY_END}"
    )
    assert pv.normalize(page) == "<title>TITLE</title>CANON_STYLEboard built <b>STAMP</b>CANON_BODY"


def test_two_boots_with_different_canon_and_time_hash_the_same() -> None:
    checklist = pv.vb.load_checklist((_ROOT / "boot" / "data" / "checklist.json").read_text(encoding="utf-8"))
    canon_a = "<html><head><title>A</title><style>a{}</style></head><body>A</body></html>"
    canon_b = "<html><head><title>B</title><style>b{}</style></head><body>B</body></html>"
    one = pv.vb.compose_board(canon_a, checklist, built_at="2026-09-08 10:00Z")
    two = pv.vb.compose_board(canon_b, checklist, built_at="2026-09-09 11:11Z")
    assert one != two
    assert pv.sha256(pv.normalize(one)) == pv.sha256(pv.normalize(two))


def test_manifest_lists_every_view_and_skips_placeholder_pages_without_env() -> None:
    entries = dict(pv.manifest({}))
    for filename in ("checklist-k4x9m2.json", "ptf-k4x9m2.html", "next-k4x9m2.html", "sop-k4x9m2.html"):
        assert len(entries[filename]) == 64
    assert entries["bus-k4x9m2.html"] == "SKIP"
    assert len(dict(pv.manifest({"BUS_STATE_URL": "https://example.invalid/bus"}))["bus-k4x9m2.html"]) == 64


def test_a_directory_written_by_the_boot_script_verifies_clean(tmp_path: Path) -> None:
    srv = tmp_path / "srv"
    srv.mkdir()
    _build(srv)
    assert pv.compare(str(srv), {"BUS_STATE_URL": "https://example.invalid/bus"}) == 0


def test_a_tampered_or_missing_file_is_a_mismatch(tmp_path: Path, capsys) -> None:
    srv = tmp_path / "srv"
    srv.mkdir()
    _build(srv)
    board = srv / "ptf-k4x9m2.html"
    board.write_text(board.read_text(encoding="utf-8").replace("Portfolio <span>Live</span>", "Edited"), encoding="utf-8")
    (srv / "sop-k4x9m2.html").unlink()
    assert pv.compare(str(srv), {"BUS_STATE_URL": "https://example.invalid/bus"}) == 2
    out = capsys.readouterr().out
    assert "MISMATCH  ptf-k4x9m2.html" in out
    assert "MISSING   sop-k4x9m2.html" in out


def test_cli_manifest_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "publish_verify.py"), "--manifest"],
        capture_output=True, text=True, cwd=_ROOT,
    )
    assert result.returncode == 0
    assert "sop-k4x9m2.html" in result.stdout
