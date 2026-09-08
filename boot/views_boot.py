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

import datetime as _dt
import html as _html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Callable

# canon key -> file served under /srv.
CANON_VIEWS: list[tuple[str, str]] = [
    ("STRAT_HTML", "trading-k4x9m2.html"),
    ("X_OPS_HTML", "x-ops-k4x9m2.html"),
    ("GROKYWOOD_OPS_HTML", "grokywood-ops-k4x9m2.html"),
    ("MOBILE_OPS_HTML", "mobile-ops-k4x9m2.html"),
    ("NEXT_HTML", "next-k4x9m2.html"),
    ("INIT_CHAMDIGITAL_HTML", "init-chamdigital-k4x9m2.html"),
    ("INIT_APPS_HTML", "init-apps-k4x9m2.html"),
    ("INIT_GROKYWOOD_HTML", "init-grokywood-k4x9m2.html"),
    ("INIT_LEADMINE_HTML", "init-leadmine-k4x9m2.html"),
    ("INIT_XAUTOPILOT_HTML", "init-x-autopilot-k4x9m2.html"),
    ("INIT_TRADERSLAND_HTML", "init-tradersland-k4x9m2.html"),
    ("INIT_OPTIMIZEYOURKID_HTML", "init-optimizeyourkid-k4x9m2.html"),
    ("INIT_WORDBLAST_HTML", "init-wordblast-k4x9m2.html"),
    ("INIT_ZORBECK_HTML", "init-zorbeck-k4x9m2.html"),
    ("INIT_LIESNICHT_HTML", "init-liesnicht-k4x9m2.html"),
    ("INIT_NIECZYTAJ_HTML", "init-nieczytaj-k4x9m2.html"),
    ("INIT_39THFLOOR_HTML", "init-39thfloor-k4x9m2.html"),
    ("INIT_XCOM_HTML", "init-xcom-k4x9m2.html"),
    ("INIT_AIKOMPETENZ_HTML", "init-aikompetenz-k4x9m2.html"),
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

# Operational state rendered into the composed views below. Edited by pull
# request; canon (strategy, decisions) is deliberately not in this repository.
CHECKLIST_PATH = "data/checklist.json"
CHECKLIST_FILE = "checklist-k4x9m2.json"
CHECKLIST_TARGET = 25

# Composed views: a canon-backed page wrapped in a repo-owned live layer. The
# canon content is carried over byte for byte (styles and body) — only the
# document shell around it is ours. If the canon read fails, the file the
# earlier boot script already wrote to /srv is used as the canon source, so a
# canon outage never blanks the board.
#   canon key -> (file, composer)
COMPOSED_VIEWS: list[tuple[str, str, str]] = [
    ("BOARD_HTML", "ptf-k4x9m2.html", "board"),
    ("NEXT_HTML", "next-k4x9m2.html", "next"),
    ("SOP_HTML", "sop-k4x9m2.html", "sop"),
]
# Composed views with no canon page behind them: rendered from repo data only.
REPO_ONLY_COMPOSED = frozenset({"SOP_HTML"})
SOP_PATH = "data/sop.json"

DEFAULT_RAW_BASE = "https://raw.githubusercontent.com/martinszreter/automation_app/main/boot"
TIMEOUT_SECONDS = 25

CANON_STYLE_BEGIN = "<!-- canon:style begin -->"
CANON_STYLE_END = "<!-- canon:style end -->"
CANON_BODY_BEGIN = "<!-- canon:body begin -->"
CANON_BODY_END = "<!-- canon:body end -->"

FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Cpath d='M16 0H64V48H48V64H0V16H16Z' fill='%23DA291C'/%3E"
    "%3Crect x='26' y='12' width='12' height='40' fill='%23fff'/%3E"
    "%3Crect x='12' y='26' width='40' height='12' fill='%23fff'/%3E%3C/svg%3E"
)

# System fonts only: the quality bar forbids external fonts, and every byte
# the page needs is in the file itself, so it renders in one round trip.
LIVE_LAYER_CSS = """
.lb{--lb-ink:#111114;--lb-grey:#6B6B72;--lb-line:#DCDCE2;--lb-wash:#F6F5F2;--lb-swiss:#DA291C;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  color:var(--lb-ink);background:#fff;line-height:1.5;-webkit-font-smoothing:antialiased;
  padding:16px 16px 24px;border-bottom:2px solid var(--lb-ink);box-sizing:border-box}
.lb *{box-sizing:border-box}
.lb a{color:inherit}
.lb-top{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px 24px;margin:0 0 14px}
.lb-title{margin:0;font-size:clamp(22px,5vw,34px);line-height:1;letter-spacing:.01em;text-transform:uppercase;font-weight:700}
.lb-title span{color:var(--lb-swiss)}
.lb-counter{display:flex;align-items:baseline;gap:8px;white-space:nowrap}
.lb-counter b{font-size:clamp(34px,9vw,56px);line-height:1;font-weight:700;letter-spacing:-.02em}
.lb-counter small{font-size:11px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--lb-grey)}
.lb-stamp{margin:0 0 16px;font-size:12px;color:var(--lb-grey)}
.lb-stamp b{color:var(--lb-ink);font-weight:600}
.lb-head{display:none}
.lb-rows{list-style:none;margin:0;padding:0;border-top:2px solid var(--lb-ink)}
.lb-row{display:grid;grid-template-columns:1fr auto;gap:2px 12px;padding:10px 0;border-bottom:1px solid var(--lb-line);align-items:start}
.lb-row.is-live{background:linear-gradient(90deg,#FDF3F2,transparent 45%)}
.lb-row>div{min-width:0;font-size:14px;overflow-wrap:anywhere}
.lb-row>div::before{content:attr(data-l) " ";font-size:10px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--lb-grey);margin-right:6px}
.lb-row>[data-l="Initiative"]::before,.lb-row>[data-l="Stage"]::before,.lb-row>[data-l="Next"]::before{content:none}
.lb-row>[data-l="Next"]{grid-column:1 / -1;color:#2C2C33}
.lb-row>[data-l="Owner"]{grid-column:1 / -1;font-size:12px}
.lb-row>[data-l="Blocker"]{grid-column:1 / -1;font-size:12px}
.lb-row>[data-l="Blocker"] .lb-none{display:none}
.lb-row>[data-l="Blocker"]:has(.lb-none)::before{content:none}
.lb-name{font-weight:600;font-size:15px}
.lb-stage{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;padding:2px 7px;border:1px solid var(--lb-ink);margin-top:2px}
.lb-stage.live{background:var(--lb-swiss);border-color:var(--lb-swiss);color:#fff}
.lb-stage.sell{background:var(--lb-ink);color:#fff}
.lb-stage.spec,.lb-stage.paused{border-color:var(--lb-line);color:var(--lb-grey)}
.lb-blocker{color:#B3261E;font-weight:600}
.lb-none{color:var(--lb-grey)}
.lb-owner{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}
@media (min-width:760px){
  .lb{padding:24px 28px 28px}
  .lb-head,.lb-row{grid-template-columns:minmax(180px,1.4fr) 80px 2fr 130px 1.2fr}
  .lb-head{display:grid;gap:16px;padding:8px 0;font-size:10px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--lb-grey)}
  .lb-row>div::before{content:none}
  .lb-row>[data-l="Next"],.lb-row>[data-l="Owner"],.lb-row>[data-l="Blocker"]{grid-column:auto;font-size:14px}
  .lb-row>[data-l="Blocker"] .lb-none{display:inline}
}
/* sections, click queue, search (NEXT + SOP) */
.lb-search{display:flex;align-items:center;gap:10px;margin:0 0 14px}
.lb-search input{flex:1 1 auto;min-width:0;font:inherit;font-size:16px;padding:10px 12px;border:1px solid var(--lb-ink);border-radius:0;background:#fff;color:var(--lb-ink)}
.lb-search input:focus{outline:2px solid var(--lb-swiss);outline-offset:1px}
.lb-search output{font-size:12px;color:var(--lb-grey);white-space:nowrap}
.lb-sec{border-top:2px solid var(--lb-ink);padding:0 0 6px}
.lb-sec summary{cursor:pointer;list-style:none;display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;padding:12px 0;font-size:17px;font-weight:700}
.lb-sec summary .lb-st{flex:1 1 200px}
.lb-sec summary::-webkit-details-marker{display:none}
.lb-sec summary::before{content:'';width:9px;height:9px;background:var(--lb-swiss);flex:none;transition:transform .15s}
.lb-sec:not([open]) summary::before{transform:rotate(-90deg);background:var(--lb-grey)}
.lb-sec summary .lb-n{margin-left:auto;font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--lb-grey)}
.lb-q{list-style:none;margin:0;padding:0}
.lb-qi{display:grid;grid-template-columns:1fr auto;gap:2px 12px;align-items:center;padding:10px 0;border-top:1px solid var(--lb-line)}
.lb-qi:first-child{border-top:0}
.lb-qi .lb-qn{font-size:12px;color:var(--lb-grey)}
.lb-qi .lb-qa{font-size:15px;font-weight:600;grid-column:1}
.lb a.lb-go,.lb-go{grid-column:2;grid-row:1 / span 2;display:inline-block;padding:9px 14px;background:var(--lb-swiss);color:#fff;text-decoration:none;font-size:12px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;white-space:nowrap}
.lb-go.off{background:#fff;border:1px solid var(--lb-line);color:var(--lb-grey);pointer-events:none}
.lb-group{margin:8px 0 4px;font-size:11px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--lb-grey)}
.lb-when{margin:0 0 8px;font-size:13px;color:var(--lb-grey)}
.lb-steps{margin:0;padding-left:22px}
.lb-steps li{padding:4px 0;font-size:14.5px}
.lb-steps code,.lb-qa code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.92em;background:var(--lb-wash);padding:1px 4px}
.lb-links{margin:8px 0 0;font-size:13px}
.lb-links a{margin-right:14px}
.lb-hide{display:none !important}
.lb-canon-note{margin:0 0 8px;font-size:12px;color:var(--lb-grey)}
"""

SEARCH_SCRIPT = """
(function(){
  'use strict';
  var input = document.getElementById('lb-search');
  var count = document.getElementById('lb-search-count');
  if (!input) return;
  var items = Array.prototype.slice.call(document.querySelectorAll('[data-s]'));
  var sections = Array.prototype.slice.call(document.querySelectorAll('details.lb-sec'));
  function apply(){
    var q = input.value.trim().toLowerCase();
    var visible = 0;
    items.forEach(function(el){
      var hit = !q || (el.textContent || '').toLowerCase().indexOf(q) !== -1;
      el.classList.toggle('lb-hide', !hit);
      if (hit) visible += 1;
    });
    sections.forEach(function(sec){
      var own = sec.querySelectorAll('[data-s]');
      if (!own.length) return;               // free-form section: leave it alone
      if (q) sec.open = true;
      var any = Array.prototype.some.call(own, function(el){ return !el.classList.contains('lb-hide'); });
      sec.classList.toggle('lb-hide', !!q && !any);
    });
    if (count) count.textContent = q ? String(visible) : String(items.length);
  }
  input.addEventListener('input', apply);
  apply();
})();
"""

LIVE_LAYER_SCRIPT = """
(function(){
  'use strict';
  // Same-origin only: the JSON is written next to this page at boot.
  if (!window.fetch) return;
  fetch('__CHECKLIST_FILE__', {cache:'no-store'}).then(function(r){ return r.ok ? r.json() : null; })
    .then(function(c){
      if (!c || !Array.isArray(c.initiatives)) return;
      var live = c.initiatives.filter(function(i){ return i && i.live === true; }).length;
      var el = document.getElementById('lb-live');
      if (el) el.textContent = live + '/' + (c.target || __TARGET__);
      var st = document.getElementById('lb-updated');
      if (st && c.updated) st.textContent = String(c.updated);
    }).catch(function(){});
})();
"""


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


# --- checklist -----------------------------------------------------------------

STAGES = ("spec", "build", "sell", "live", "paused")
OWNERS = ("MARCIN", "CLAUDE_CLAUDECODE", "GPT_CURSOR", "GROK_MARKET")


def load_checklist(text: str) -> dict:
    """Parse and validate the checklist JSON. Strict on purpose: a malformed
    row would otherwise render as a blank card and nobody would notice."""
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("initiatives"), list):
        raise ValueError("checklist must be an object with an `initiatives` list")
    seen: set[str] = set()
    for index, row in enumerate(data["initiatives"]):
        if not isinstance(row, dict):
            raise ValueError(f"checklist row {index} is not an object")
        for field in ("id", "name", "stage", "next", "owner"):
            if not str(row.get(field) or "").strip():
                raise ValueError(f"checklist row {index} is missing `{field}`")
        if row["id"] in seen:
            raise ValueError(f"checklist id {row['id']!r} appears twice")
        seen.add(row["id"])
        if row["stage"] not in STAGES:
            raise ValueError(f"checklist row {row['id']!r} has unknown stage {row['stage']!r}")
        if row["owner"] not in OWNERS:
            raise ValueError(f"checklist row {row['id']!r} has unknown owner {row['owner']!r}")
        if not isinstance(row.get("live", False), bool):
            raise ValueError(f"checklist row {row['id']!r}: `live` must be true or false")
        row.setdefault("blocker", "")
        row.setdefault("link", "")
    data.setdefault("target", CHECKLIST_TARGET)
    data.setdefault("updated", "")
    return data


def live_count(checklist: dict) -> int:
    return sum(1 for row in checklist["initiatives"] if row.get("live") is True)


def click_queue(checklist: dict) -> list[dict]:
    """Rows that wait on one click from Marcin: an explicit `marcin` action,
    or a row he owns. The NEXT and SOP views put these at the top."""
    queue: list[dict] = []
    for row in checklist["initiatives"]:
        action = row.get("marcin")
        if isinstance(action, dict) and str(action.get("action") or "").strip():
            queue.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "action": str(action["action"]).strip(),
                    "link": str(action.get("link") or row.get("link") or "").strip(),
                }
            )
        elif row.get("owner") == "MARCIN":
            queue.append(
                {"id": row["id"], "name": row["name"], "action": row["next"], "link": row.get("link", "")}
            )
    return queue


# --- composing a canon page into a repo-owned shell -----------------------------

_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.S | re.I)
_LINK_RE = re.compile(r"<link\b[^>]*>", re.I)
_BODY_RE = re.compile(r"<body\b[^>]*>(.*)</body>", re.S | re.I)
_HEAD_RE = re.compile(r"<head\b[^>]*>(.*?)</head>", re.S | re.I)
_TITLE_RE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.S | re.I)


def split_canon(html: str) -> tuple[str, str, list[str]]:
    """Return (style_html, body_inner, dropped_external_links).

    Accepts either a raw canon page or a page this script composed earlier
    (the on-disk fallback), thanks to the canon:* markers. The canon's own
    ``<style>`` blocks and body are returned verbatim; only external
    stylesheet/preconnect links are dropped, and reported, because the
    quality bar forbids external fonts.
    """
    if CANON_BODY_BEGIN in html and CANON_BODY_END in html:
        body = html.split(CANON_BODY_BEGIN, 1)[1].split(CANON_BODY_END, 1)[0]
        style = ""
        if CANON_STYLE_BEGIN in html and CANON_STYLE_END in html:
            style = html.split(CANON_STYLE_BEGIN, 1)[1].split(CANON_STYLE_END, 1)[0].strip("\n")
        return style, body, []

    head_match = _HEAD_RE.search(html)
    body_match = _BODY_RE.search(html)
    head = head_match.group(1) if head_match else (html[: body_match.start()] if body_match else "")
    body = body_match.group(1) if body_match else html

    styles = _STYLE_RE.findall(head)
    dropped = [
        link
        for link in _LINK_RE.findall(head)
        if re.search(r"rel=[\"']?(stylesheet|preconnect|preload)", link, re.I)
    ]
    return "\n".join(styles), body, dropped


def canon_title(html: str, default: str) -> str:
    match = _TITLE_RE.search(html)
    return _html.unescape(match.group(1)).strip() if match and match.group(1).strip() else default


def esc(value: object) -> str:
    return _html.escape(str("" if value is None else value), quote=True)


def _link(text: str, href: str, css: str = "") -> str:
    if href:
        return f'<a href="{esc(href)}" class="{css}">{esc(text)}</a>'
    return f'<span class="{css}">{esc(text)}</span>'


def render_rows(checklist: dict) -> str:
    """Per-initiative rows: name, stage, next, owner, blocker. One <li> each;
    the CSS turns them into cards on a phone and a grid on a desktop."""
    parts = [
        '<div class="lb-head" aria-hidden="true"><div>Initiative</div><div>Stage</div>'
        '<div>Next</div><div>Owner</div><div>Blocker</div></div>',
        '<ul class="lb-rows">',
    ]
    for row in checklist["initiatives"]:
        stage = row["stage"]
        blocker = str(row.get("blocker") or "").strip()
        live = " is-live" if row.get("live") is True else ""
        parts.append(
            f'<li class="lb-row{live}" id="i-{esc(row["id"])}">'
            f'<div data-l="Initiative">{_link(row["name"], row.get("link", ""), "lb-name")}</div>'
            f'<div data-l="Stage"><span class="lb-stage {esc(stage)}">{esc(stage)}</span></div>'
            f'<div data-l="Next">{esc(row["next"])}</div>'
            f'<div data-l="Owner"><span class="lb-owner">{esc(row["owner"])}</span></div>'
            f'<div data-l="Blocker">'
            + (f'<span class="lb-blocker">{esc(blocker)}</span>' if blocker else '<span class="lb-none">—</span>')
            + "</div></li>"
        )
    parts.append("</ul>")
    return "".join(parts)


def utc_now_stamp(now: _dt.datetime | None = None) -> str:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    return now.strftime("%Y-%m-%d %H:%MZ")


def compose_document(
    *,
    title: str,
    description: str,
    layer_css: str,
    layer_html: str,
    layer_script: str,
    canon_style: str,
    canon_body: str,
    lang: str = "en",
    canon_before: str = "",
    canon_after: str = "",
) -> str:
    """The one document shell every composed view uses. ``canon_before`` /
    ``canon_after`` wrap the canon body (e.g. in a collapsible section)
    without touching it: the markers sit directly around the body.

    No robots noindex on purpose: the Lighthouse SEO gate (>= 90) fails a page
    that blocks indexing, and the contract makes that gate the acceptance
    criterion. The views stay unlinked and under their k4x9m2 suffix.
    """
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{lang}">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta name="description" content="{esc(description)}">\n'
        f"<title>{esc(title)}</title>\n"
        f'<link rel="icon" href="{FAVICON}">\n'
        f"<style>{layer_css}</style>\n"
        f"{CANON_STYLE_BEGIN}\n{canon_style}\n{CANON_STYLE_END}\n"
        "</head>\n<body>\n"
        f"{layer_html}\n"
        f"{canon_before}{CANON_BODY_BEGIN}{canon_body}{CANON_BODY_END}{canon_after}\n"
        f"<script>{layer_script}</script>\n"
        "</body>\n</html>\n"
    )


def load_sop(text: str) -> dict:
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("sops"), list) or not data["sops"]:
        raise ValueError("sop must be an object with a non-empty `sops` list")
    seen: set[str] = set()
    for index, sop in enumerate(data["sops"]):
        if not isinstance(sop, dict):
            raise ValueError(f"sop {index} is not an object")
        for field in ("id", "title", "owner", "when"):
            if not str(sop.get(field) or "").strip():
                raise ValueError(f"sop {index} is missing `{field}`")
        if sop["id"] in seen:
            raise ValueError(f"sop id {sop['id']!r} appears twice")
        seen.add(sop["id"])
        steps = sop.get("steps")
        if not isinstance(steps, list) or not steps or not all(isinstance(s, str) and s.strip() for s in steps):
            raise ValueError(f"sop {sop['id']!r} needs a non-empty list of step strings")
        if sop["owner"] not in OWNERS:
            raise ValueError(f"sop {sop['id']!r} has unknown owner {sop['owner']!r}")
        sop.setdefault("links", [])
    data.setdefault("updated", "")
    return data


_CODE_RE = re.compile(r"`([^`]+)`")


def rich(text: str) -> str:
    """Escape, then turn `code` spans into <code>. Nothing else is markup."""
    return _CODE_RE.sub(r"<code>\1</code>", esc(text))


def section(section_id: str, title: str, badge: str, inner: str, *, is_open: bool = True) -> str:
    open_attr = " open" if is_open else ""
    return (
        f'<details class="lb-sec" id="{esc(section_id)}"{open_attr}>'
        f'<summary><span class="lb-st">{esc(title)}</span><span class="lb-n">{esc(badge)}</span></summary>'
        f"{inner}</details>"
    )


def render_click_queue(checklist: dict) -> str:
    queue = click_queue(checklist)
    if not queue:
        items = '<p class="lb-canon-note" data-s>Nothing waits on Marcin.</p>'
    else:
        items = '<ol class="lb-q">' + "".join(
            f'<li class="lb-qi" data-s><span class="lb-qn">{esc(item["name"])}</span>'
            f'<span class="lb-qa">{rich(item["action"])}</span>'
            + (
                f'<a class="lb-go" href="{esc(item["link"])}">Open</a>'
                if item["link"]
                else '<span class="lb-go off">No link</span>'
            )
            + "</li>"
            for item in queue
        ) + "</ol>"
    return section("click-queue", "Marcin — click queue", f"{len(queue)} to click", items)


def render_search() -> str:
    return (
        '<form class="lb-search" role="search" onsubmit="return false">'
        '<label for="lb-search" class="lb-none" style="position:absolute;left:-9999px">Search this page</label>'
        '<input id="lb-search" type="search" placeholder="Search initiatives, steps, blockers" autocomplete="off">'
        '<output id="lb-search-count" for="lb-search" aria-live="polite"></output>'
        "</form>"
    )


def render_blockers(checklist: dict) -> str:
    rows = [row for row in checklist["initiatives"] if str(row.get("blocker") or "").strip()]
    if not rows:
        inner = '<p class="lb-canon-note" data-s>No blockers on the checklist.</p>'
    else:
        inner = '<ol class="lb-q">' + "".join(
            f'<li class="lb-qi" data-s><span class="lb-qn">{esc(row["name"])} · {esc(row["owner"])}</span>'
            f'<span class="lb-qa lb-blocker">{esc(row["blocker"])}</span>'
            + (f'<a class="lb-go" href="{esc(row["link"])}">Open</a>' if row.get("link") else "")
            + "</li>"
            for row in rows
        ) + "</ol>"
    return section("blockers", "Blockers", f"{len(rows)} open", inner)


def render_by_owner(checklist: dict) -> str:
    groups: dict[str, list[dict]] = {}
    for row in checklist["initiatives"]:
        groups.setdefault(row["owner"], []).append(row)
    parts = []
    for owner in OWNERS:
        rows = groups.get(owner)
        if not rows:
            continue
        parts.append(f'<div class="lb-group">{esc(owner)} · {len(rows)}</div><ol class="lb-q">')
        for row in rows:
            parts.append(
                f'<li class="lb-qi" data-s><span class="lb-qn">{esc(row["name"])} · '
                f'<span class="lb-stage {esc(row["stage"])}">{esc(row["stage"])}</span></span>'
                f'<span class="lb-qa">{esc(row["next"])}</span>'
                + (f'<a class="lb-go" href="{esc(row["link"])}">Open</a>' if row.get("link") else "")
                + "</li>"
            )
        parts.append("</ol>")
    total = len(checklist["initiatives"])
    return section("by-owner", "Next step per initiative", f"{total} rows", "".join(parts), is_open=False)


def compose_next(canon_html: str, checklist: dict, sop: dict | None = None, *, built_at: str | None = None) -> str:
    """next-k4x9m2: click queue, blockers, per-owner next steps, then the
    canon NEXT page unchanged — every section collapsible, one search box."""
    canon_style, canon_body, _dropped = split_canon(canon_html)
    built = built_at or utc_now_stamp()
    queue_size = len(click_queue(checklist))
    layer = (
        '<section class="lb" id="live" aria-labelledby="lb-title">'
        '<div class="lb-top"><h1 class="lb-title" id="lb-title">Next <span>Clicks</span></h1>'
        f'<div class="lb-counter" aria-label="Clicks waiting on Marcin"><b id="lb-queue">{queue_size}</b><small>to click</small></div></div>'
        f'<p class="lb-stamp">Checklist updated <b id="lb-updated">{esc(checklist.get("updated") or "—")}</b> · page built <b>{esc(built)}</b></p>'
        f"{render_search()}"
        f"{render_click_queue(checklist)}"
        f"{render_blockers(checklist)}"
        f"{render_by_owner(checklist)}"
        "</section>"
    )
    canon_before = (
        '<details class="lb-sec lb" id="canon-next" open><summary><span class="lb-st">NEXT — canon page</span><span class="lb-n">unchanged</span></summary>'
        '<p class="lb-canon-note">Read from canon NEXT_HTML at boot; nothing below is edited here.</p>'
    )
    return compose_document(
        title=canon_title(canon_html, "STARTEND — NEXT"),
        description=f"STARTEND NEXT: {queue_size} clicks waiting on Marcin, open blockers, next step per initiative, then the canon NEXT page.",
        layer_css=LIVE_LAYER_CSS,
        layer_html=layer,
        layer_script=SEARCH_SCRIPT,
        canon_style=canon_style,
        canon_body=canon_body,
        canon_before=canon_before,
        canon_after="</details>",
    )


def render_sops(sop: dict) -> str:
    parts = []
    for item in sop["sops"]:
        steps = "".join(f"<li data-s>{rich(step)}</li>" for step in item["steps"])
        links = "".join(
            f'<a href="{esc(link.get("url", ""))}">{esc(link.get("label", link.get("url", "")))}</a>'
            for link in item.get("links", [])
            if isinstance(link, dict) and link.get("url")
        )
        inner = (
            f'<p class="lb-when" data-s>When: {esc(item["when"])}</p>'
            f'<ol class="lb-steps">{steps}</ol>'
            + (f'<p class="lb-links">{links}</p>' if links else "")
        )
        parts.append(section(f"sop-{item['id']}", item["title"], item["owner"], inner))
    return "".join(parts)


def compose_sop(canon_html: str, checklist: dict, sop: dict | None = None, *, built_at: str | None = None) -> str:
    """sop-k4x9m2: click queue first, then one collapsible section per SOP."""
    if sop is None:
        raise ValueError("SOP view needs the sop data")
    built = built_at or utc_now_stamp()
    queue_size = len(click_queue(checklist))
    layer = (
        '<section class="lb" id="live" aria-labelledby="lb-title">'
        '<div class="lb-top"><h1 class="lb-title" id="lb-title">SOP <span>Runbook</span></h1>'
        f'<div class="lb-counter" aria-label="Procedures"><b id="lb-sops">{len(sop["sops"])}</b><small>procedures</small></div></div>'
        f'<p class="lb-stamp">SOP updated <b>{esc(sop.get("updated") or "—")}</b> · checklist updated <b id="lb-updated">{esc(checklist.get("updated") or "—")}</b> · page built <b>{esc(built)}</b></p>'
        f"{render_search()}"
        f"{render_click_queue(checklist)}"
        f"{render_sops(sop)}"
        "</section>"
    )
    return compose_document(
        title="STARTEND — SOP",
        description=f"STARTEND standard operating procedures: {len(sop['sops'])} runbooks for redeploying the HQ views, moving initiatives, the CHF 1 test and refund, error alerts.",
        layer_css=LIVE_LAYER_CSS,
        layer_html=layer,
        layer_script=SEARCH_SCRIPT,
        canon_style="",
        canon_body="",
    )


def compose_board(canon_html: str, checklist: dict, sop: dict | None = None, *, built_at: str | None = None) -> str:
    """ptf-k4x9m2: live layer (counter, rows, stamp) above the canon board."""
    canon_style, canon_body, _dropped = split_canon(canon_html)
    live = live_count(checklist)
    target = int(checklist.get("target") or CHECKLIST_TARGET)
    updated = str(checklist.get("updated") or "—")
    built = built_at or utc_now_stamp()

    layer = (
        '<section class="lb" id="live" aria-labelledby="lb-title">'
        '<div class="lb-top">'
        '<h1 class="lb-title" id="lb-title">Portfolio <span>Live</span></h1>'
        f'<div class="lb-counter" aria-label="Initiatives live"><b id="lb-live">{live}/{target}</b><small>live</small></div>'
        "</div>"
        f'<p class="lb-stamp">Checklist updated <b id="lb-updated">{esc(updated)}</b> · board built <b>{esc(built)}</b> · '
        f'<a href="{CHECKLIST_FILE}">checklist JSON</a></p>'
        f"{render_rows(checklist)}"
        "</section>"
    )
    script = LIVE_LAYER_SCRIPT.replace("__CHECKLIST_FILE__", CHECKLIST_FILE).replace("__TARGET__", str(target))
    return compose_document(
        title=canon_title(canon_html, "STARTEND — Portfolio"),
        description=f"STARTEND portfolio board: {live} of {target} initiatives live, stage, next step, owner and blocker per initiative.",
        layer_css=LIVE_LAYER_CSS,
        layer_html=layer,
        layer_script=script,
        canon_style=canon_style,
        canon_body=canon_body,
    )


COMPOSERS: dict[str, Callable[[str, dict, dict | None], str]] = {
    "board": compose_board,
    "next": compose_next,
    "sop": compose_sop,
}


def read_canon_or_disk(canon_url: str, key: str, srv_path: str) -> tuple[str, str]:
    """Canon first; the file an earlier boot step wrote is the fallback."""
    if canon_url:
        try:
            return canon_read(canon_url, key), "canon"
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
            log(f"boot5 WARN {key} canon read failed, trying disk: {error}")
    if os.path.isfile(srv_path):
        with open(srv_path, encoding="utf-8") as handle:
            return handle.read(), "disk"
    raise ValueError(f"no canon content for {key} (canon unreachable and {srv_path} absent)")


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

    checklist: dict | None = None
    try:
        checklist = load_checklist(read_repo_page(CHECKLIST_PATH))
        size = write_view(srv_dir, CHECKLIST_FILE, json.dumps(checklist, ensure_ascii=False, indent=1))
        log(f"boot5 ok CHECKLIST_JSON {CHECKLIST_FILE} {size}")
    except (OSError, ValueError, urllib.error.URLError) as error:
        failures += 1
        log(f"boot5 FAIL CHECKLIST_JSON {CHECKLIST_FILE} {error}")

    canon_url = (os.environ.get("CANON_RW_URL") or "").strip()
    if not canon_url:
        log(f"boot5 FAIL canon-views {len(CANON_VIEWS)} CANON_RW_URL is not set")
        failures += 1
    else:
        for key, filename in CANON_VIEWS:
            try:
                html = canon_read(canon_url, key)
                log(f"boot5 ok {key} {filename} {write_view(srv_dir, filename, html)}")
            except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
                failures += 1
                log(f"boot5 FAIL {key} {filename} {error}")

    sop: dict | None = None
    try:
        sop = load_sop(read_repo_page(SOP_PATH))
    except (OSError, ValueError, urllib.error.URLError) as error:
        failures += 1
        log(f"boot5 FAIL SOP_JSON {SOP_PATH} {error}")

    for key, filename, composer in COMPOSED_VIEWS:
        if checklist is None:
            log(f"boot5 FAIL {key} {filename} checklist unavailable")
            failures += 1
            continue
        try:
            if key in REPO_ONLY_COMPOSED:
                canon_html, source = "", "repo"
            else:
                canon_html, source = read_canon_or_disk(canon_url, key, os.path.join(srv_dir, filename))
                _style, _body, dropped = split_canon(canon_html)
                for link in dropped:
                    log(f"boot5 WARN {key} dropped external link {link[:120]}")
            html = COMPOSERS[composer](canon_html, checklist, sop)
            log(f"boot5 ok {key} {filename} {write_view(srv_dir, filename, html)} source={source}")
        except (OSError, ValueError) as error:
            failures += 1
            log(f"boot5 FAIL {key} {filename} {error}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
