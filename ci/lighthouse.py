"""Lighthouse gate: mobile, four categories >= 0.90, no layout shift, no
console errors. Fails the build on the first page that misses.

Usage:
    python3 ci/lighthouse.py URL [URL ...]

Needs the ``lighthouse`` CLI from e2e/node_modules (``npm ci`` in e2e/) and a
Chromium the CLI can find — set CHROME_PATH when it is not on PATH. The
report JSON of every page is left in ``ci/out/`` for the workflow to upload.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ci" / "out"
CLI = ROOT / "e2e" / "node_modules" / ".bin" / "lighthouse"
CATEGORIES = ("performance", "accessibility", "best-practices", "seo")
MINIMUM = 0.90


def run(url: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")[-80:]
    report = OUT / f"lh-{name}.json"
    command = [
        str(CLI),
        url,
        "--quiet",
        "--chrome-flags=--headless=new --no-sandbox --disable-gpu",
        "--only-categories=" + ",".join(CATEGORIES),
        "--output=json",
        f"--output-path={report}",
    ]
    subprocess.run(command, check=True, cwd=ROOT, env=os.environ)
    return json.loads(report.read_text(encoding="utf-8"))


def check(url: str, result: dict) -> list[str]:
    problems: list[str] = []
    scores = {key: (result["categories"][key]["score"] or 0.0) for key in CATEGORIES}
    for key, score in scores.items():
        if score < MINIMUM:
            problems.append(f"{key} {score:.2f} < {MINIMUM:.2f}")
    audits = result["audits"]
    cls = float(audits["cumulative-layout-shift"].get("numericValue") or 0.0)
    if cls > 0:
        problems.append(f"layout shift {cls:.3f} > 0")
    console = audits.get("errors-in-console") or {}
    if console.get("score") not in (None, 1):
        problems.append("console errors: " + json.dumps(console.get("details", {}).get("items", []))[:300])

    line = "  ".join(f"{key}={score:.2f}" for key, score in scores.items())
    print(f"{'FAIL' if problems else 'ok  '} {url}  {line}  cls={cls:.3f}", flush=True)
    for audit_ref in result["categories"]["accessibility"]["auditRefs"] + result["categories"]["seo"]["auditRefs"]:
        audit = audits[audit_ref["id"]]
        if audit.get("score") is not None and audit["score"] < 1 and audit_ref.get("weight", 0) > 0:
            print(f"      {audit_ref['id']}: {audit.get('displayValue', '')}".rstrip(), flush=True)
    return problems


def main(urls: list[str]) -> int:
    if not urls:
        print(__doc__)
        return 2
    if not CLI.exists():
        print(f"lighthouse CLI missing at {CLI}; run `npm ci` in e2e/", file=sys.stderr)
        return 2
    failed = False
    for url in urls:
        problems = check(url, run(url))
        for problem in problems:
            print(f"      {problem}", flush=True)
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
