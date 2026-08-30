from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Callable

CANON_URL = (os.environ.get("CANON_RW_URL") or "").strip()
BUS_URL = "https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k"
UPDATED_BY = "HQ_GPT"
TIMEOUT = 45

INIT_MARKER = "STARTEND_COMMERCE_OS_20260830"
DECISION_MARKER = "SET_FOR_SUCCESS_TOLL_BOOTH_20260830"
BOARD_MARKER = "<!-- HQ_GPT_4_2_COMMERCE_OS_20260830 -->"
BENCH_MARKER = "<!-- HQ_GPT_TOLL_BOOTH_BENCHMARK_20260830 -->"

BOARD_URL = "https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html"


def log(*parts: object) -> None:
    print(*parts, flush=True)


def request_json(url: str, payload: dict[str, Any] | None = None, method: str | None = None) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method or ("POST" if data is not None else "GET"),
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read().decode("utf-8")
    if not body.strip():
        return None
    return json.loads(body)


def canon_read(file_name: str) -> list[dict[str, Any]]:
    rows = request_json(CANON_URL, {"action": "read", "keyValue": file_name})
    if rows == []:
        raise RuntimeError(f"STOP_EMPTY {file_name}")
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"STOP_BAD_READ {file_name}")
    usable = [r for r in rows if isinstance(r, dict) and r.get("version") is not None and "content" in r]
    if not usable:
        raise RuntimeError(f"STOP_NO_CANONICAL_ROW {file_name}")
    return usable


def canonical(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(rows, key=lambda r: int(r["version"]))


def extract_inserted_id(result: Any) -> Any:
    candidates: list[dict[str, Any]] = []
    if isinstance(result, dict):
        candidates.append(result)
        for key in ("data", "row", "result"):
            val = result.get(key)
            if isinstance(val, dict):
                candidates.append(val)
            elif isinstance(val, list):
                candidates.extend(x for x in val if isinstance(x, dict))
    elif isinstance(result, list):
        candidates.extend(x for x in result if isinstance(x, dict))
    for obj in candidates:
        for key in ("id", "ID", "row_id"):
            if obj.get(key) is not None:
                return obj[key]
    return None


def canon_insert(file_name: str, version: int, content: str, note: str) -> Any:
    return request_json(
        CANON_URL,
        {
            "action": "insert",
            "file": file_name,
            "version": version,
            "content": content,
            "note": note,
            "updated_by": UPDATED_BY,
        },
    )


def canon_delete(row_id: Any) -> None:
    if row_id is None:
        return
    request_json(CANON_URL, {"action": "delete", "id": str(row_id)})


def prune_top3(file_name: str) -> None:
    rows = canon_read(file_name)
    ordered = sorted(rows, key=lambda r: (int(r["version"]), int(r.get("id") or 0)), reverse=True)
    for row in ordered[3:]:
        if row.get("id") is not None:
            canon_delete(row["id"])
    final = canon_read(file_name)
    versions = sorted((int(r["version"]) for r in final), reverse=True)
    log("PRUNE", file_name, versions[:3])


def write_mutation(
    file_name: str,
    transform: Callable[[str], str],
    marker: str,
    note: str,
) -> tuple[int, Any]:
    before_rows = canon_read(file_name)
    before = canonical(before_rows)
    prior_content = str(before["content"])
    prior_version = int(before["version"])

    if marker in prior_content:
        log("NOOP", file_name, "v", prior_version, "marker-present")
        prune_top3(file_name)
        return prior_version, before.get("id")

    changed = transform(prior_content)
    if changed == prior_content or marker not in changed:
        raise RuntimeError(f"STOP_TRANSFORM_FAILED {file_name}")

    target_version = prior_version + 1
    result = canon_insert(file_name, target_version, changed, note)
    our_id = extract_inserted_id(result)

    after_rows = canon_read(file_name)
    same_version = [r for r in after_rows if int(r["version"]) == target_version]

    if len(same_version) > 1:
        log("RACE", file_name, "v", target_version, "rows", [r.get("id") for r in same_version])
        other_rows = [r for r in same_version if our_id is None or str(r.get("id")) != str(our_id)]
        base = other_rows[0] if other_rows else canonical(after_rows)
        merged = transform(str(base["content"]))
        max_version = max(int(r["version"]) for r in after_rows)
        race_result = canon_insert(file_name, max_version + 1, merged, note + " · race re-merge")
        race_id = extract_inserted_id(race_result)
        if our_id is not None:
            canon_delete(our_id)
        final_rows = canon_read(file_name)
        final = canonical(final_rows)
        if marker not in str(final["content"]):
            raise RuntimeError(f"STOP_RACE_VERIFY_FAILED {file_name}")
        prune_top3(file_name)
        log("WRITE_OK", file_name, "v", int(final["version"]), "id", final.get("id") or race_id)
        return int(final["version"]), final.get("id") or race_id

    final = canonical(after_rows)
    if int(final["version"]) < target_version or marker not in str(final["content"]):
        raise RuntimeError(f"STOP_VERIFY_FAILED {file_name}")
    prune_top3(file_name)
    log("WRITE_OK", file_name, "v", int(final["version"]), "id", final.get("id") or our_id)
    return int(final["version"]), final.get("id") or our_id


INIT_BLOCK = f"""\
{INIT_MARKER}
4.2 STARTEND COMMERCE OS — IDEA
Owner: HQ_GPT · Pillar 4 SERVICES
Scope: Separate initiative from 4.1 ChamDigital. Global self-serve merchant/store platform: one premium storefront engine configurable by industry and country, with vertical UX packs, language/localisation, local payment methods, tax/shipping integrations, catalogue/order flows and merchant editor.
Revenue model: recurring monthly SaaS + optional small GMV/platform fee using partner payment rails (Stripe Connect/local PSPs). Payments/hosting are BUY; core commerce UX, orchestration and own merchant data are BUILD.
Domain/brand: TBD — confirm before BUILD. Do not imitate or embed the Shopify trademark in the domain.
Stage: IDEA. Exponential test 1a is mandatory before BUILD.
Priority: 4.1 ChamDigital remains the active lock until READY=100%; 4.2 is next in Pillar 4, not scope expansion of 4.1.
Next: name/domain shortlist + exponential test 1a.
"""


def _table_initiative_row(headers: list[str]) -> str:
    cells: list[str] = []
    for idx, raw in enumerate(headers):
        h = re.sub(r"<[^>]+>", "", raw).strip().upper()
        if idx == 0 or h in {"#", "ID", "NO", "NUMBER"}:
            value = "4.2"
        elif any(k in h for k in ("INITIATIVE", "NAME", "STREAM", "VENTURE", "PRODUCT")):
            value = "STARTEND Commerce OS — global self-serve commerce platform"
        elif "PILLAR" in h or h == "PROJECT":
            value = "4 SERVICES"
        elif "OWNER" in h or "THINKS" in h:
            value = "HQ_GPT"
        elif "STAGE" in h or "STATUS" in h:
            value = "IDEA"
        elif "DOMAIN" in h:
            value = "TBD — confirm before BUILD"
        elif any(k in h for k in ("PRICE", "MODEL", "REVENUE")):
            value = "Monthly SaaS + optional small GMV/platform fee via partner payment rails"
        elif "NEXT" in h:
            value = "Name/domain + exponential test 1a; BUILD only after 4.1 READY=100%"
        elif any(k in h for k in ("SCOPE", "DESCRIPTION", "NOTES", "OFFER")):
            value = "Separate from ChamDigital; global industry/country storefront engine; local payments; self-serve"
        elif "REPO" in h or "RAILWAY" in h:
            value = "— until BUILD"
        elif "READY" in h:
            value = "0%"
        elif "TODAY" in h or "CUSTOMER" in h or "CUST" in h:
            value = "0"
        else:
            value = "—"
        cells.append(value)
    return "| " + " | ".join(cells) + " |"


def transform_initiatives(content: str) -> str:
    if INIT_MARKER in content:
        return content
    lines = content.splitlines()
    target = None
    for i, line in enumerate(lines):
        if re.search(r"\b4\.1\b", line) and re.search(r"ChamDigital|Swiss Websites|Swiss Web", line, re.I):
            target = i
            break
    if target is None:
        return content.rstrip() + "\n\n" + INIT_BLOCK + "\n"

    target_line = lines[target]
    if target_line.strip().startswith("|") and target_line.count("|") >= 3:
        fields = [x.strip() for x in target_line.strip().strip("|").split("|")]
        header_fields = None
        for j in range(target - 1, -1, -1):
            cand = lines[j]
            if cand.strip().startswith("|") and cand.count("|") == target_line.count("|"):
                parsed = [x.strip() for x in cand.strip().strip("|").split("|")]
                if any(re.search(r"ID|INITIATIVE|STAGE|OWNER|DOMAIN|NEXT|PROJECT", x, re.I) for x in parsed):
                    header_fields = parsed
                    break
            if target - j > 20:
                break
        if header_fields and len(header_fields) == len(fields):
            row = _table_initiative_row(header_fields)
        else:
            row_cells = ["—"] * len(fields)
            row_cells[0] = "4.2"
            if len(row_cells) > 1:
                row_cells[1] = "STARTEND Commerce OS — IDEA"
            if len(row_cells) > 2:
                row_cells[2] = "HQ_GPT · separate from 4.1 · domain TBD · next: 1a"
            row = "| " + " | ".join(row_cells) + " |"
        lines.insert(target + 1, row + f" <!-- {INIT_MARKER} -->")
        return "\n".join(lines) + ("\n" if content.endswith("\n") else "")

    insert_at = target + 1
    numbered = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?\d+\.\d+\b")
    while insert_at < len(lines):
        if numbered.search(lines[insert_at]) and not re.search(r"^\s*(?:[-*]\s*)?(?:\*\*)?4\.1\b", lines[insert_at]):
            break
        insert_at += 1
    block_lines = [""] + INIT_BLOCK.rstrip().splitlines() + [""]
    lines[insert_at:insert_at] = block_lines
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


DECISION_BLOCK = f"""\
{DECISION_MARKER}
30 AUG 2026 — SET FOR SUCCESS / TOLL-BOOTH ECONOMICS LOCKED
DECISION: STARTEND should prefer business-model geometry that earns from recurring throughput/usage instead of requiring us to be directionally right on every customer outcome. Benchmark the mechanism, not the logos: Bybit/Binance earn trading fees when volume executes; Visa/Mastercard assess/process network volume and transactions; Stripe monetises payment processing and Connect/platform flows; Shopify combines subscription revenue with merchant/payment solutions that grow with merchant GMV; Tether demonstrates reserve/network economics around stablecoin circulation; Citadel Securities is a market-making/liquidity/spread benchmark, NOT a risk-free model.
APPLICATION: 4.2 STARTEND Commerce OS is a separate Pillar-4 IDEA after ChamDigital: self-serve storefront software, industry/country packs, local payments through partner rails, monthly SaaS plus an optional small GMV/platform fee where commercially and legally sensible. STARTEND does not build a payment network or processor at IDEA stage. BUY the pipe; BUILD the offer and own data.
GUARDRAIL: These businesses still carry fraud, regulatory, operational, liquidity/inventory, credit and concentration risks. “Set for success” means the unit economics improve with legitimate customer activity and recurring volume; it never means risk-free.
PRIORITY: 4.1 ChamDigital remains locked first until READY=100%. 4.2 requires name/domain confirmation and exponential test 1a before BUILD.
"""


def transform_decisions(content: str) -> str:
    if DECISION_MARKER in content:
        return content
    sep = re.search(r"(?m)^-{5,}\s*$", content)
    insertion = DECISION_BLOCK.rstrip() + "\n\n"
    if sep:
        return content[: sep.start()] + insertion + content[sep.start() :]
    return insertion + content


COMMERCE_ROW = """<tr><!-- STARTEND_COMMERCE_OS_20260830 --><td class="id">4.2</td><td><span class="nm">STARTEND Commerce OS — local-first storefront platform</span><span class="ds">Working name. One premium storefront engine configurable by industry + country: vertical UX templates, language/localisation, local payment methods, tax/shipping integrations, catalogue/order flows and merchant editor. A merchant launches and keeps selling without talking to us. <b>Separate initiative from ChamDigital.</b></span><div class="dnote"><b>DOMAIN NOTE:</b> TBD — confirm brand/domain before BUILD. Do not imitate the Shopify trademark in a domain. Exponential test 1a before code.</div></td><td class="domcol"><span class="dm">own domain TBD</span> <span class="tbd">confirm before BUILD</span></td><td><span class="draft">monthly SaaS + optional small GMV/platform fee</span><br><span class="dim">exact pricing after 1a</span></td><td>0</td><td class="prod" style="text-align:center"><b>—</b><br><span class="dim">TBD after 1a</span></td><td class="prod" style="text-align:center"><span class="dim">GLOBAL</span></td><td class="prod" style="text-align:center"><span class="dim">GLOBAL</span></td><td class="prod" style="text-align:center"><span class="dim">GLOBAL</span></td><td class="prod" style="text-align:center"><span class="dim">GLOBAL</span></td><td style="text-align:center;font-weight:700;background:#f4cccc">0</td><td>Self-serve + paid acquisition + partners. Payments are BUY/partner rails (Stripe Connect/local PSP), not a processor build.</td><td class="yel"><div class="stw"><b>IDEA · exponential 1a</b><br><i>next: name/domain + 1a</i></div></td><td class="yel"><span class="rd">5%</span><span class="rdbar"><i style="width:5%;background:#DA291C"></i></span><div style="font-size:11px;color:#555;margin-top:5px;line-height:1.45">Model registered; no build. 4.1 remains first priority.</div></td><td>IDEA — global recurring merchant SaaS + throughput economics. Separate from 4.1; no scope expansion of ChamDigital.</td><td class="nx"><div><b style="font-size:10px;color:#888;letter-spacing:.5px">NEXT ACTION</b><br>Name/domain shortlist → exponential test 1a → only then own repo + Railway + domain + Stripe</div></td></tr>"""

COMMERCE_SECTION = f"""
{BOARD_MARKER}
<h2><span class="k">4.2 · separate initiative · after ChamDigital</span>STARTEND Commerce OS — global shops</h2>
<div class="card" style="border-left:5px solid #DA291C"><b>THE BET:</b> do not become another agency and do not clone Shopify feature-for-feature. Build one extremely polished commerce engine that can be configured by <b>industry × country</b>: storefront UX, language, catalogue/order flow, local payment methods, tax/shipping integrations and merchant editing. The merchant must be able to launch, sell and keep operating without talking to STARTEND.</div>
<div class="card"><b>ECONOMIC SHAPE:</b> monthly SaaS + an optional small GMV/platform fee through partner rails where it makes sense. Every additional merchant and transaction should add revenue much faster than human workload. <b>Payments are BUY:</b> Stripe Connect/local PSPs and other rails. <b>Core offer + own merchant data are BUILD.</b><br><b>STATUS:</b> IDEA · domain/brand TBD · exponential test 1a required. <b>Priority remains 4.1 ChamDigital until READY=100%.</b></div>
"""

BENCHMARK_SECTION = f"""
{BENCH_MARKER}
<h2><span class="k">Benchmark doctrine · throughput beats prediction</span>SET FOR SUCCESS / TOLL-BOOTH ECONOMICS</h2>
<div class="dark"><div class="display" style="font-size:34px;line-height:1.05">Earn when legitimate activity flows through the system.</div><div style="font-size:14px;font-weight:700;color:#DA291C;margin-top:8px">Do not require STARTEND to be right about every customer outcome.</div><div style="font-size:12.5px;color:#d9d5cb;margin-top:10px">This is not “risk-free.” The goal is better geometry: recurring usage, tiny fees at huge volume, software/network leverage, and marginal human work approaching zero.</div></div>
<div class="scroll"><table style="min-width:1050px"><tr><th>BENCHMARK</th><th>WHAT GETS MONETISED</th><th>STARTEND LESSON</th></tr>
<tr><td><b>Bybit / Binance</b></td><td>Trading activity / executed volume</td><td>Be the venue/tool and earn on throughput; do not need every trader to be right.</td></tr>
<tr><td><b>Visa / Mastercard</b></td><td>Payment volume + processed transactions</td><td>A tiny network/processing economics layer can compound across enormous transaction counts.</td></tr>
<tr><td><b>Stripe</b></td><td>Payment processing + Connect/platform flows</td><td>Make infrastructure easy; a platform can monetise payments without building the card rails.</td></tr>
<tr><td><b>Shopify</b></td><td>Subscription + merchant/payment solutions tied to merchant activity</td><td>Best template for 4.2: merchants pay to operate, and STARTEND can participate as they sell.</td></tr>
<tr><td><b>Tether</b></td><td>Stablecoin circulation + reserve economics</td><td>Distribution + balance-sheet/network demand can be extraordinarily scalable; regulatory/reserve risk remains real.</td></tr>
<tr><td><b>Citadel Securities</b></td><td>Market making, liquidity and spread economics</td><td>Benchmark pricing, liquidity and scale discipline — <b>not</b> a claim of risk-free profits.</td></tr>
<tr><td><b>STARTEND 4.2</b></td><td>Merchant SaaS + optional small GMV/platform fee through partner rails</td><td><b>SET FOR SUCCESS:</b> more successful merchant activity should automatically create more STARTEND revenue without proportional labour.</td></tr>
</table></div>
"""


def transform_board(content: str) -> str:
    if BOARD_MARKER in content and BENCH_MARKER in content and INIT_MARKER in content:
        return content

    out = content
    out = out.replace(
        '<div class="l">Initiatives tracked</div><div class="n ">33</div>',
        '<div class="l">Initiatives tracked</div><div class="n ">34</div>',
        1,
    )

    if "4.2 STARTEND Commerce OS" not in out:
        pat = re.compile(
            r'(<td class="v">4</td><td>SERVICES</td>\s*<td class="prod">)(.*?)(</td>)',
            re.S,
        )
        m = pat.search(out)
        if m:
            products = m.group(2)
            products += '<br><b>4.2 STARTEND Commerce OS</b><br><span class="dim">IDEA · global shops · domain TBD</span>'
            out = out[: m.start()] + m.group(1) + products + m.group(3) + out[m.end() :]

    if "STARTEND_COMMERCE_OS_20260830" not in out:
        anchor = '<tr><td class="id">4.1</td>'
        pos = out.find(anchor)
        if pos == -1:
            raise RuntimeError("BOARD_4_1_ROW_NOT_FOUND")
        end = out.find("</tr>", pos)
        if end == -1:
            raise RuntimeError("BOARD_4_1_ROW_END_NOT_FOUND")
        end += len("</tr>")
        out = out[:end] + "\n" + COMMERCE_ROW + out[end:]

    if BOARD_MARKER not in out:
        heading = '<h2><span class="k">Sorted by how big this can get, not by pillar'
        pos = out.find(heading)
        if pos == -1:
            raise RuntimeError("BOARD_PORTFOLIO_HEADING_NOT_FOUND")
        out = out[:pos] + COMMERCE_SECTION + "\n" + out[pos:]

    if BENCH_MARKER not in out:
        dist_patterns = [
            '<h2><span class="k">The logic, and who we are measuring against</span>Distribution &amp; the idols</h2>',
            '<h2><span class="k">The logic, and who we are measuring against</span>Distribution & the idols</h2>',
        ]
        pos = -1
        for anchor in dist_patterns:
            pos = out.find(anchor)
            if pos != -1:
                break
        if pos == -1:
            raise RuntimeError("BOARD_DISTRIBUTION_HEADING_NOT_FOUND")
        out = out[:pos] + BENCHMARK_SECTION + "\n" + out[pos:]

    if INIT_MARKER not in out:
        out = out.replace("</head>", f"<!-- {INIT_MARKER} -->\n</head>", 1)

    return out


def bus_done(versions: dict[str, int]) -> None:
    try:
        state = request_json(BUS_URL, None, "GET")
        cursor = None
        if isinstance(state, dict):
            cursor = state.get("bus_cursor")
        elif isinstance(state, list) and state and isinstance(state[0], dict):
            cursor = state[0].get("bus_cursor")
        if not cursor:
            log("BUS_SKIP no fresh cursor")
            return
        payload = {
            "team": "HQ_GPT",
            "project": "4.2 STARTEND Commerce OS",
            "type": "DONE",
            "what": "Registered 4.2 as separate IDEA after 4.1; added SET FOR SUCCESS / toll-booth benchmark and live board row. Domain/brand remains TBD; no build before exponential test 1a.",
            "next": "After 4.1 reaches READY=100%, shortlist the 4.2 name/domain and run exponential test 1a.",
            "link": BOARD_URL,
            "bus_cursor": cursor,
        }
        result = request_json(BUS_URL, payload)
        log("BUS_DONE", result)
    except Exception as exc:
        log("BUS_WARN", type(exc).__name__, str(exc)[:240])


def main() -> int:
    if not CANON_URL:
        log("STOP CANON_RW_URL missing")
        return 2

    try:
        protocol_rows = canon_read("_PROTOCOL")
        protocol = canonical(protocol_rows)
        log("PROTOCOL_OK", int(protocol["version"]))

        assets_rows = canon_read("02_ASSETS")
        assets = canonical(assets_rows)
        log("ASSETS_OK", int(assets["version"]), len(str(assets["content"])))

        for key in ("00_INITIATIVES", "03_DECISIONS", "BOARD_HTML"):
            row = canonical(canon_read(key))
            log("READ_OK", key, int(row["version"]), len(str(row["content"])))

        versions: dict[str, int] = {}
        versions["00_INITIATIVES"], _ = write_mutation(
            "00_INITIATIVES",
            transform_initiatives,
            INIT_MARKER,
            "Register 4.2 STARTEND Commerce OS as standalone Pillar-4 IDEA after ChamDigital; domain TBD; 1a before BUILD.",
        )
        versions["03_DECISIONS"], _ = write_mutation(
            "03_DECISIONS",
            transform_decisions,
            DECISION_MARKER,
            "Lock SET FOR SUCCESS / toll-booth economics doctrine and 4.2 commerce direction.",
        )
        versions["BOARD_HTML"], _ = write_mutation(
            "BOARD_HTML",
            transform_board,
            BOARD_MARKER,
            "Add 4.2 Commerce OS directly below 4.1 and toll-booth benchmark block; preserve ChamDigital priority.",
        )

        checks = {
            "00_INITIATIVES": INIT_MARKER,
            "03_DECISIONS": DECISION_MARKER,
            "BOARD_HTML": BOARD_MARKER,
        }
        for key, marker in checks.items():
            row = canonical(canon_read(key))
            text = str(row["content"])
            if marker not in text:
                raise RuntimeError(f"FINAL_VERIFY_MISSING {key}")
            if key == "BOARD_HTML":
                for required in (
                    BENCH_MARKER,
                    "STARTEND_COMMERCE_OS_20260830",
                    "4.2 STARTEND Commerce OS",
                    "SET FOR SUCCESS / TOLL-BOOTH ECONOMICS",
                ):
                    if required not in text:
                        raise RuntimeError(f"FINAL_BOARD_VERIFY_MISSING {required}")
            log("VERIFY_OK", key, int(row["version"]))

        bus_done(versions)
        log("CANON_DONE", versions)
        return 0
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        log("BLOCKED", type(exc).__name__, str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
