#!/usr/bin/env python3
"""Add STARTEND GTM execution columns + operating strategy to BOARD_HTML.

This is an idempotent canon migration. It preserves existing portfolio rows and
unknown metrics stay as em dashes until measured. No sales/traction is invented.

Run with CANON_RW_URL set. After the canon write it asks the existing portfolio
redeploy webhook to republish the board.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request as u

WHO = "HQ_GPT"
MARK = "GTM OPERATING SYSTEM 2026-09-16"
REDEPLOY = os.environ.get("PORTFOLIO_REDEPLOY_URL", "https://startend.app.n8n.cloud/webhook/redeploy-portfolio-7k4q9x")
BOARD = os.environ.get("PORTFOLIO_BOARD_URL", "https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html")
CANON = os.environ.get("CANON_RW_URL", "").strip()

PRIORITY = {
    "chamdigital": (1, "Owner-led 10/day high-fit local SME", "Google Search + local SEO + referrals", "55%", "45%", "Prepare 10 high-fit local SMEs/day; prove paid website #1"),
    "leadmine": (2, "Selective agency/recruiter/consultancy outreach", "High-intent SEO/Search + product-led email capture", "70%", "65%", "Use LeadMine GTM queue; convert first external CHF 490 pilot"),
    "x-autopilot": (3, "Founder/agency account outreach", "X/content + referral loop", "45%", "55%", "Prove one external paying account then repeat the same ICP"),
    "grokywood": (4, "Agency/content-buyer outreach", "Creator/social proof + SEO", "40%", "50%", "Prove one buyer using the simplest paid door"),
    "ai-kompetenz": (5, "HR/ops/team buyer outreach", "LinkedIn/content + Google Search + partners", "35%", "35%", "Package one clear paid training offer and target 10 Swiss teams"),
    "ai-exposure-check": (6, "Privacy/professional-services partners", "Search/SEO + shareable assessment", "25%", "25%", "Finish buyer/source definition, then acquire first assessed company"),
    "restaurant-app": (7, "10/day restaurant owner outreach", "Local SEO + partner/referral", "50%", "40%", "Get first paying restaurant in Zug/Zurich"),
    "hoppado": (8, "Schools/clubs/partner outreach", "Parent search/content + referrals", "20%", "25%", "Validate adult buyer and one paid learning cohort"),
    "optimizeyourkid": (9, "Youth-sports organisations/partners", "Parent search/social + referrals", "25%", "30%", "Prove one adult buyer after CHF 1 production smoke"),
    "unfairstart": (10, "Sports/learning partner outreach", "Search/content/referrals", "15%", "20%", "Define one paid wedge and buyer before scaling traffic"),
    "wordblast": (11, "Language-school/partner outreach", "App-store/search/content", "20%", "25%", "Get first adult-run partner/customer"),
    "liesnicht": (12, "Advertiser/agency partnerships", "SEO/social/content inventory", "35%", "35%", "Prove advertiser demand, not reader traffic alone"),
    "nieczytaj": (15, "Polish advertiser/agency partnerships", "SEO/social/content inventory", "25%", "30%", "Define advertiser offer and first paid partner"),
    "39thfloor": (16, "Tourism/media partnership outreach", "SEO/social/live-camera discovery", "20%", "35%", "Validate who pays before increasing camera inventory"),
    "zorbeck": (17, "Seller/agency partnerships", "SEO/property discovery + referrals", "30%", "35%", "Prove one external paid placement/customer"),
    "tradersland": (20, "Partner/research outreach only", "Content/community after product proof", "10%", "15%", "Keep commercial claims behind validated product/results"),
}

ALIASES = {
    "swiss website": "chamdigital", "chamdigital": "chamdigital",
    "leadmine": "leadmine", "smartlead": "leadmine",
    "x autopilot": "x-autopilot", "grokywood": "grokywood",
    "ai kompetenz": "ai-kompetenz", "aikompetenz": "ai-kompetenz",
    "ai exposure": "ai-exposure-check", "restaurant": "restaurant-app", "booking": "restaurant-app",
    "hoppado": "hoppado", "optimizeyourkid": "optimizeyourkid", "unfairstart": "unfairstart",
    "wordblast": "wordblast", "liesnicht": "liesnicht", "nieczytaj": "nieczytaj",
    "39th floor": "39thfloor", "39thfloor": "39thfloor", "zorbeck": "zorbeck", "tradersland": "tradersland",
}

HEADERS = ["GTM<br>PRIORITY", "PUSH", "PULL", "DIST<br>READY", "GTM<br>AUTO", "READY<br>LEADS", "CONTACTED", "REPLIES", "SALES", "NEXT GTM ACTION"]

STRATEGY_HTML = f'''<!-- {MARK} -->
<section id="go-to-market-strategy" style="margin-top:36px">
<h2><span class="k">Distribution is a first-class system</span>Go-to-market strategy</h2>
<div class="card">
<p><b>CORE RULE:</b> Get stranger #1 &rarr; reproduce it &rarr; make reproduction cheaper and increasingly automatic &rarr; scale.</p>
<p><b>Commercial ladder:</b> 0 PROOF &rarr; 1 PAID STRANGER &rarr; REPEATABLE &rarr; AUTOMATED &rarr; SCALING. A LIVE website is not proof of demand.</p>
<h3>1 &middot; PROOF — manual demand discovery</h3>
<p>Manual outreach is temporary. Its purpose is to learn the winning ICP &times; offer &times; message &times; channel. Automate prospect discovery, scoring, research, draft preparation, reminders, funnel tracking and reporting immediately. Keep human sending/review where law, platform policy or judgment requires it. Ten excellent prospects/day can be better than 100 generic messages/day.</p>
<h3>2 &middot; REPRODUCE — prove repeatability</h3>
<p>Customer #1 proves somebody will pay. Customers #2/#3/#10 prove whether the same loop repeats. Record ICP, problem, offer, price, message, channel, proof and sales cycle for every win.</p>
<h3>3 &middot; AUTOMATE — remove founder routine work</h3>
<p>Every manual sales activity gets an expiry path: automate it, eliminate it, or replace it with a scalable channel. Target flow: traffic/lead source &rarr; qualification &rarr; personalised offer &rarr; first-party capture &rarr; permissioned nurture &rarr; checkout &rarr; fulfilment &rarr; upsell/referral &rarr; measurement &rarr; optimisation. Track GTM automation % per initiative.</p>
<h3>4 &middot; SCALE — grow only proven loops</h3>
<p>Scale geography, partnerships, SEO/content, paid traffic and automation only when conversion and economics are measurable. Long-term PULL: high-intent search, SEO/content, product-led capture, opt-in lifecycle email, referrals/partners, social/creator distribution and paid acquisition where CAC/payback works.</p>
<h3>Timing expectations</h3>
<p><b>Weeks 1–2:</b> targeting + first replies/conversations. <b>Weeks 3–6:</b> first external paying customers become a serious expectation. <b>Months 2–3:</b> several customers and first repeatable combinations. <b>Months 3–6:</b> predictable small engine; manual work starts disappearing. <b>Months 6–12:</b> concentrate on winners and compound PULL channels.</p>
<p><b>30–45 day rule:</b> disciplined qualified outreach with no external customer means change target/offer/price/trust/message/channel — do not merely increase volume.</p>
<p><b>90-day scorecard:</b> Day 30: are strangers responding? Day 60: are strangers paying? Day 90: can we make strangers pay repeatedly?</p>
<p class="dim">Unknown funnel numbers remain blank until measured. Never invent traction. Once one loop repeats, scaling that loop outranks creating another unproven initiative.</p>
</div>
</section>'''


def _post(url: str, payload: dict):
    req = u.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with u.urlopen(req, timeout=60) as r:
        raw = r.read().decode()
    return json.loads(raw) if raw.strip() else None


def _rows(key: str):
    rows = _post(CANON, {"action": "read", "keyValue": key})
    if not rows:
        raise RuntimeError(f"EMPTY {key}")
    if isinstance(rows, dict):
        rows = [rows]
    return sorted(rows, key=lambda x: int(x.get("version", 0)), reverse=True)


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).replace("&nbsp;", " ").replace("&amp;", "&").strip()


def _key(iid: str, name: str) -> str | None:
    n = f"{iid} {name}".lower()
    for needle, key in ALIASES.items():
        if needle in n:
            return key
    return None


def _cell(value: str, note: str = "") -> str:
    extra = f'<br><span class="dim">{note}</span>' if note else ""
    return f'<td class="gtm-col"><b>{value}</b>{extra}</td>'


def _gtm_cells(iid: str, name: str) -> str:
    key = _key(iid, name)
    if not key or key not in PRIORITY:
        return "".join([
            _cell("—", "rank when buyer/channel is defined"), _cell("TBD"), _cell("TBD"), _cell("—"), _cell("—"),
            _cell("—", "not measured"), _cell("—"), _cell("—"), _cell("—"), _cell("Define buyer + first proof")
        ])
    p, push, pull, ready, auto, next_action = PRIORITY[key]
    return "".join([
        _cell(str(p)), _cell(push), _cell(pull), _cell(ready), _cell(auto),
        _cell("—", "measure in LeadMine"), _cell("—"), _cell("—"), _cell("—"), _cell(next_action)
    ])


def transform(content: str) -> str:
    if MARK in content and "GTM<br>PRIORITY" in content:
        return content
    marker = '<h2><span class="k">Sorted by how big this can get, not by pillar &middot; column titles repeat in every tier</span>The portfolio</h2>'
    start = content.find(marker)
    if start < 0:
        raise RuntimeError("portfolio section not found")
    end = content.find("<h2", start + len(marker))
    if end < 0:
        end = content.find("</body>", start)
    if end < 0:
        end = len(content)
    section = content[start:end]

    def header_repl(match):
        row = match.group(0)
        if "GTM<br>PRIORITY" in row:
            return row
        return row[:-5] + "".join(f"<th>{h}</th>" for h in HEADERS) + "</tr>"

    section = re.sub(r"<tr><th>#</th>.*?</tr>", header_repl, section, flags=re.S)

    def row_repl(match):
        row = match.group(0)
        if 'class="gtm-col"' in row:
            return row
        cells = re.findall(r"<td(?:\s[^>]*)?>.*?</td>", row, flags=re.S)
        if len(cells) < 2:
            return row
        iid = _text(cells[0])
        name = _text(cells[1])
        return row[:-5] + _gtm_cells(iid, name) + "</tr>"

    section = re.sub(r"<tr><td class="id">.*?</tr>", row_repl, section, flags=re.S)

    def colspan_repl(m):
        return f'colspan="{int(m.group(1)) + len(HEADERS)}"'
    section = re.sub(r'colspan="(\d+)"', colspan_repl, section)

    out = content[:start] + section + content[end:]
    if MARK not in out:
        pos = out.rfind("</body>")
        if pos < 0:
            pos = len(out)
        out = out[:pos] + STRATEGY_HTML + "\n" + out[pos:]

    if "GTM<br>PRIORITY" not in out or "Get stranger #1" not in out:
        raise RuntimeError("GTM transform verification failed")
    return out


def write_canon():
    if not CANON:
        raise RuntimeError("CANON_RW_URL is not set")
    base = _rows("BOARD_HTML")[0]
    new = transform(base["content"])
    if new == base["content"]:
        print("NO_CHANGE BOARD_HTML already contains GTM operating system")
        return int(base["version"])
    version = int(base["version"]) + 1
    _post(CANON, {
        "action": "insert", "file": "BOARD_HTML", "version": version, "content": new,
        "note": "Add GTM priority/PUSH/PULL/readiness/automation/funnel columns + bottom GTM operating system",
        "updated_by": WHO,
    })
    top = _rows("BOARD_HTML")[0]
    if int(top["version"]) != version or MARK not in top.get("content", ""):
        raise RuntimeError("post-write canon verification failed")
    print("CANON_OK BOARD_HTML v", version, "len", len(top["content"]))
    return version


def redeploy():
    try:
        result = _post(REDEPLOY, {"who": WHO, "why": MARK})
        print("REDEPLOY", result)
    except Exception as exc:
        print("REDEPLOY_WARN", exc)


if __name__ == "__main__":
    v = write_canon()
    redeploy()
    print("READY_FOR_LIVE_VERIFY", BOARD, "canon_version", v)
