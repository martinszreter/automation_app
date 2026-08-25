"""Portfolio boot script for the canon-backed internal views (boot5).

Until now this script existed only as the Railway environment variable
VIEWS_BOOT_PY on the ``portfolio`` service: nobody could review it, diff it or
roll it back. It lives here instead. Railway is expected to fetch this file
from the repository at boot — see README.md, section "Portfolio boot scripts".

What it does, once per container start:

* for every canon-backed view, read the canon key over the canon RW webhook,
  take the highest ``version`` row and write its ``content`` to /srv/<file>;
* for every repo-backed view, take the page shipped next to this file, fill in
  its runtime placeholders and write it to /srv/<file>;
* print one ``boot5 ok <KEY> <FILE> <BYTES>`` line per view, which is the same
  log grammar the environment-variable version used, so the deploy logs stay
  greppable;
* exit non-zero if any view failed, so the start command can fall back to the
  previous boot script instead of serving a half-empty /srv.

No endpoint URLs live in this file. The canon RW webhook accepts unauthenticated
inserts and deletes, so publishing it in a public repository would hand anyone a
write key to canon; it is read from the environment instead, and this file stays
safe to make public.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# canon key -> file served under /srv. Mirrors what the boot5 environment
# variable was writing on 2026-08-25, plus nothing else: these four keys are
# exactly the ones its deploy logs reported.
CANON_VIEWS: list[tuple[str, str]] = [
    ("STRAT_HTML", "trading-k4x9m2.html"),
    ("X_OPS_HTML", "x-ops-k4x9m2.html"),
    ("GROKYWOOD_OPS_HTML", "grokywood-ops-k4x9m2.html"),
    ("MOBILE_OPS_HTML", "mobile-ops-k4x9m2.html"),
]

# Views whose HTML is static and therefore belongs in the repo rather than in
# canon. The page is a shell; it fetches its data client-side.
REPO_VIEWS: list[tuple[str, str, str]] = [
    ("BUS_HTML", "pages/bus-k4x9m2.html", "bus-k4x9m2.html"),
]

# Placeholder -> environment variable. Substituted into repo-backed pages so
# that no live endpoint is hard-coded in the repository.
PLACEHOLDERS: dict[str, str] = {
    "__BUS_STATE_URL__": "BUS_STATE_URL",
}

DEFAULT_RAW_BASE = "https://raw.githubusercontent.com/martinszreter/automation_app/main/boot"
TIMEOUT_SECONDS = 25


def log(message: str) -> None:
    print(message, flush=True)


def canon_read(canon_url: str, key: str) -> str:
    """Return the content of the highest-version canon row for ``key``."""
    payload = json.dumps({"action": "read", "keyValue": key}).encode("utf-8")
    request = urllib.request.Request(
        canon_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        rows = json.loads(response.read().decode("utf-8"))

    if isinstance(rows, dict):
        rows = [rows]
    return pick_content(rows, key)


def pick_content(rows: object, key: str) -> str:
    """Highest ``version`` wins — that is the canon protocol."""
    if not isinstance(rows, list):
        raise ValueError(f"canon read for {key} returned {type(rows).__name__}, expected a list")

    usable = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("content") and row.get("version") is not None
    ]
    if not usable:
        raise ValueError(f"canon has no usable row for {key}")

    newest = max(usable, key=lambda row: int(row["version"]))
    return str(newest["content"])


def read_repo_page(relative_path: str) -> str:
    """Read a page shipped alongside this script, from disk or from the repo."""
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
    if os.path.isfile(local_path):
        with open(local_path, encoding="utf-8") as handle:
            return handle.read()

    raw_base = os.environ.get("REPO_RAW_BASE", DEFAULT_RAW_BASE).rstrip("/")
    with urllib.request.urlopen(f"{raw_base}/{relative_path}", timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def fill_placeholders(html: str, environ: dict[str, str] | None = None) -> str:
    environ = os.environ if environ is None else environ
    for placeholder, variable in PLACEHOLDERS.items():
        if placeholder not in html:
            continue
        value = (environ.get(variable) or "").strip()
        if not value:
            raise ValueError(f"{variable} is not set, cannot fill {placeholder}")
        html = html.replace(placeholder, value)
    return html


def write_view(srv_dir: str, filename: str, html: str) -> int:
    path = os.path.join(srv_dir, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)
    return len(html.encode("utf-8"))


def main() -> int:
    srv_dir = os.environ.get("SRV_DIR", "/srv")
    os.makedirs(srv_dir, exist_ok=True)
    failures = 0

    for key, relative_path, filename in REPO_VIEWS:
        try:
            html = fill_placeholders(read_repo_page(relative_path))
            log(f"boot5 ok {key} {filename} {write_view(srv_dir, filename, html)}")
        except (OSError, ValueError, urllib.error.URLError) as error:
            failures += 1
            log(f"boot5 FAIL {key} {filename} {error}")

    canon_url = (os.environ.get("CANON_RW_URL") or "").strip()
    if not canon_url:
        log(f"boot5 FAIL canon-views {len(CANON_VIEWS)} CANON_RW_URL is not set")
        return 1

    for key, filename in CANON_VIEWS:
        try:
            html = canon_read(canon_url, key)
            log(f"boot5 ok {key} {filename} {write_view(srv_dir, filename, html)}")
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
            failures += 1
            log(f"boot5 FAIL {key} {filename} {error}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
