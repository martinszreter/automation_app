#!/usr/bin/env python3
"""Verify a publish of the HQ views by sha256: what is served must be what
this repository renders.

Three modes:

    python3 scripts/publish_verify.py --manifest
        sha256 of every repo-rendered view, normalised (below). Paste into a
        review; compare across machines.

    python3 scripts/publish_verify.py --srv srv
        Compare against a directory boot/views_boot.py just wrote (CI does
        this right after the build step).

    python3 scripts/publish_verify.py --live https://hq.startend.ch
        Fetch every view from the live service and compare. Non-zero exit on
        the first mismatch, so a deploy that served a stale or half-written
        page is caught the same minute.

What "normalised" means: the parts that legitimately differ between the
repository and a boot are neutralised before hashing — the ``page built``
/ ``board built`` stamp, the ``<title>`` (it comes from canon) and the two
canon blocks between the ``canon:*`` markers (canon content is read at boot
on Railway and is not in git). Everything else — the live layer, the
checklist JSON, the SOP page, the CSS, the scripts — must match byte for
byte. Pages that need a runtime placeholder (the bus page) are verified only
when the variable is in the environment, and reported as SKIP otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOT = ROOT / "boot"


def load_views_boot():
    spec = importlib.util.spec_from_file_location("views_boot_verify", BOOT / "views_boot.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


vb = load_views_boot()

_STAMP_RE = re.compile(r"(board built|page built) <b>[^<]*</b>")
_TITLE_RE = re.compile(r"<title>.*?</title>", re.S)
_STYLE_RE = re.compile(re.escape(vb.CANON_STYLE_BEGIN) + r".*?" + re.escape(vb.CANON_STYLE_END), re.S)
_BODY_RE = re.compile(re.escape(vb.CANON_BODY_BEGIN) + r".*?" + re.escape(vb.CANON_BODY_END), re.S)


def normalize(text: str) -> str:
    """Neutralise the boot-time and canon-time parts of a composed page."""
    text = _STAMP_RE.sub(r"\1 <b>STAMP</b>", text)
    text = _TITLE_RE.sub("<title>TITLE</title>", text)
    text = _STYLE_RE.sub("CANON_STYLE", text)
    text = _BODY_RE.sub("CANON_BODY", text)
    return text


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def local_renders(environ: dict[str, str] | None = None) -> dict[str, str | None]:
    """file -> normalised local render (None = cannot render here: SKIP)."""
    environ = os.environ if environ is None else environ
    checklist = vb.load_checklist((BOOT / vb.CHECKLIST_PATH).read_text(encoding="utf-8"))
    sop = vb.load_sop((BOOT / vb.SOP_PATH).read_text(encoding="utf-8"))
    # Raw renders — compare() and manifest() normalise both sides uniformly,
    # so a repo-only page's <title> is neutralised on the expected side too.
    renders: dict[str, str | None] = {
        vb.CHECKLIST_FILE: json.dumps(checklist, ensure_ascii=False, indent=1),
        "ptf-k4x9m2.html": vb.compose_board("", checklist, built_at="STAMP"),
        "next-k4x9m2.html": vb.compose_next("", checklist, built_at="STAMP"),
        "sop-k4x9m2.html": vb.compose_sop("", checklist, sop, built_at="STAMP"),
    }
    for _key, relative_path, filename in vb.REPO_VIEWS:
        page = (BOOT / relative_path).read_text(encoding="utf-8")
        try:
            renders[filename] = vb.fill_placeholders(page, environ)
        except ValueError:
            renders[filename] = None  # placeholder variable not in this environment
    return renders


def read_served(source: str, filename: str) -> str | None:
    """From a directory or over HTTPS; None when the file is absent."""
    if "://" in source:
        url = f"{source.rstrip('/')}/{filename}"
        try:
            with urllib.request.urlopen(url, timeout=25) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise
    path = Path(source) / filename
    return path.read_text(encoding="utf-8") if path.is_file() else None


def compare(source: str, environ: dict[str, str] | None = None) -> int:
    mismatches = 0
    for filename, expected in local_renders(environ).items():
        if expected is None:
            print(f"SKIP      {filename}  (placeholder variable not set locally)")
            continue
        served = read_served(source, filename)
        if served is None:
            mismatches += 1
            print(f"MISSING   {filename}")
            continue
        want, got = sha256(normalize(expected)), sha256(normalize(served))
        if want == got:
            print(f"OK        {filename}  {want[:16]}")
        else:
            mismatches += 1
            print(f"MISMATCH  {filename}  repo {want[:16]} served {got[:16]}")
    return mismatches


def manifest(environ: dict[str, str] | None = None) -> list[tuple[str, str]]:
    return [
        (filename, sha256(normalize(text)) if text is not None else "SKIP")
        for filename, text in local_renders(environ).items()
    ]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--manifest", action="store_true", help="print sha256 of every repo render")
    group.add_argument("--srv", metavar="DIR", help="compare against a directory written by views_boot.py")
    group.add_argument("--live", metavar="BASE_URL", help="compare against the live service")
    args = parser.parse_args(argv)

    if args.manifest:
        for filename, digest in manifest():
            print(f"{digest}  {filename}")
        return 0

    source = args.srv or args.live
    mismatches = compare(source)
    print(f"{'FAIL' if mismatches else 'PASS'}  {mismatches} mismatch(es) against {source}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
