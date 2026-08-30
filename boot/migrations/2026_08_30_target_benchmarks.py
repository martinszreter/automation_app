from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any, Callable

CANON_URL = (os.environ.get("CANON_RW_URL") or "").strip()
UPDATED_BY = "HQ_GPT"
TIMEOUT = 45

MARK_STRATEGY = "HQ_GPT_TARGET_BENCHMARK_LADDER_20260830"
MARK_DECISION = "TARGET_LADDER_COMPANY_BENCHMARKS_20260830"
MARK_BOARD = "<!-- HQ_GPT_TARGET_BENCHMARK_LADDER_20260830 -->"
MARK_GIANTS = "<!-- HQ_GPT_WORLD_GIANTS_PROFIT_20260830 -->"


def log(*parts: object) -> None:
    print(*parts, flush=True)


def request_json(payload: dict[str, Any]) -> Any:
    if not CANON_URL:
        raise RuntimeError("CANON_RW_URL missing")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        CANON_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read().decode("utf-8")
    if not body.strip():
        return None
    return json.loads(body)


def canon_read(file_name: str) -> list[dict[str, Any]]:
    rows = request_json({"action": "read", "keyValue": file_name})
    if rows == []:
        raise RuntimeError(f"STOP_EMPTY {file_name}")
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"STOP_BAD_READ {file_name}")
    usable = [
        r for r in rows
        if isinstance(r, dict) and r.get("version") is not None and "content" in r
    ]
    if not usable:
        raise RuntimeError(f"STOP_NO_CANONICAL_ROW {file_name}")
    return usable


def canonical(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(rows, key=lambda r: int(r["version"]))


def insert(file_name: str, version: int, content: str, note: str) -> Any:
    return request_json({
        "action": "insert",
        "file": file_name,
        "version": version,
        "content": content,
        "note": note,
        "updated_by": UPDATED_BY,
    })


def delete(row_id: Any) -> None:
    if row_id is None:
        return
    request_json({"action": "delete", "id": str(row_id)})


def extract_id(result: Any) -> Any:
    objs: list[dict[str, Any]] = []
    if isinstance(result, dict):
        objs.append(result)
        for k in ("data", "row", "result"):
            v = result.get(k)
            if isinstance(v, dict):
                objs.append(v)
            elif isinstance(v, list):
                objs.extend(x for x in v if isinstance(x, dict))
    elif isinstance(result, list):
        objs.extend(x for x in result if isinstance(x, dict))
    for obj in objs:
        for k in ("id", "ID", "row_id"):
            if obj.get(k) is not None:
                return obj[k]
    return None


def prune_top3(file_name: str) -> None:
    rows = canon_read(file_name)
    ordered = sorted(
        rows,
        key=lambda r: (int(r["version"]), int(r.get("id") or 0)),
        reverse=True,
    )
    for row in ordered[3:]:
        delete(row.get("id"))
    final = canon_read(file_name)
    top = sorted(
        final,
        key=lambda r: (int(r["version"]), int(r.get("id") or 0)),
        reverse=True,
    )[:3]
    log("PRUNE_OK", file_name, [(r.get("version"), r.get("id")) for r in top])


def write_mutation(
    file_name: str,
    transform: Callable[[str], str],
    marker: str,
    note: str,
) -> int:
    # Mandatory immediate re-read before write.
    before_rows = canon_read(file_name)
    before = canonical(before_rows)
    prior = str(before["content"])
    prior_v = int(before["version"])

    if marker in prior:
        log("NOOP", file_name, prior_v, "marker-present")
        prune_top3(file_name)
        return prior_v

    changed = transform(prior)
    if changed == prior or marker not in changed:
        raise RuntimeError(f"STOP_TRANSFORM_FAILED {file_name}")

    target_v = prior_v + 1
    result = insert(file_name, target_v, changed, note)
    our_id = extract_id(result)

    # Mandatory immediate verification read.
    after_rows = canon_read(file_name)
    same = [r for r in after_rows if int(r["version"]) == target_v]

    if len(same) > 1:
        log("RACE", file_name, target_v, [r.get("id") for r in same])
        competitors = [
            r for r in same
            if our_id is None or str(r.get("id")) != str(our_id)
        ]
        if competitors:
            base = max(competitors, key=lambda r: int(r.get("id") or 0))
        else:
            differing = [r for r in same if str(r.get("content")) != changed]
            base = max(differing or same, key=lambda r: int(r.get("id") or 0))
        merged = transform(str(base["content"]))
        if marker not in merged:
            raise RuntimeError(f"STOP_RACE_TRANSFORM_FAILED {file_name}")
        max_v = max(int(r["version"]) for r in after_rows)
        race_result = insert(file_name, max_v + 1, merged, note + " · race re-merge")
        race_id = extract_id(race_result)

        if our_id is not None:
            delete(our_id)
        else:
            for row in same:
                if str(row.get("content")) == changed and row.get("id") != base.get("id"):
                    delete(row.get("id"))
                    break

        verified_rows = canon_read(file_name)
        final = canonical(verified_rows)
        if marker not in str(final["content"]) or int(final["version"]) < max_v + 1:
            raise RuntimeError(f"STOP_RACE_VERIFY_FAILED {file_name}")
        prune_top3(file_name)
        log("WRITE_OK", file_name, int(final["version"]), final.get("id") or race_id)
        return int(final["version"])

    final = canonical(after_rows)
    if int(final["version"]) < target_v or marker not in str(final["content"]):
        raise RuntimeError(f"STOP_VERIFY_FAILED {file_name}")
    prune_top3(file_name)
    log("WRITE_OK", file_name, int(final["version"]), final.get("id") or our_id)
    return int(final["version"])


STRATEGY_BLOCK = f"""\
## {MARK_STRATEGY}

### HARD REVENUE TARGET LADDER + REAL-COMPANY BENCHMARKS — 30 AUG 2026
Founder decision. This block **supersedes the older 2030 = CHF 2B/year extension below**; the underlying anti-gaming convention remains unchanged: daily revenue = trailing-30-day COLLECTED portfolio revenue / 30. Targets are forcing targets, not forecasts.

- **31 Dec 2026 — CHF 10,000/day** = CHF 300,000 trailing 30d = ~CHF 3.65M/year.
- **31 Dec 2027 — CHF 100,000/day** = CHF 3.0M trailing 30d = ~CHF 36.5M/year.
- **31 Dec 2028 — CHF 1,000,000/day** = CHF 30.0M trailing 30d = ~CHF 365M/year.
- **31 Dec 2029 — CHF 1B/year** = ~CHF 2.74M/day = ~CHF 82.2M trailing 30d.
- **31 Dec 2030 — CHF 10B/year** = ~CHF 27.4M/day = ~CHF 822M trailing 30d.
- **31 Dec 2031 — CHF 100B/year** = ~CHF 274M/day = ~CHF 8.22B trailing 30d.

Benchmark doctrine: the sticky HQ target table must include a real-company annual-revenue comparison column. Use reported operating revenue/sales, never market cap or valuation. Current reference rungs: Telegram (~USD 1.4B, 2024) + HubSpot (USD 3.13B, 2025) around the 2029 scale; Shopify (USD 11.56B, 2025) + Spotify (EUR 17.19B, 2025) around/above the 2030 scale; Johnson & Johnson (USD 94.19B, 2025) around the 2031 scale. At the end of BOARD_HTML keep a separate revenue + **net profit** benchmark table so giant low-margin throughput businesses and high-margin profit machines are not confused.

"""


def transform_strategy(content: str) -> str:
    if MARK_STRATEGY in content:
        return content
    return STRATEGY_BLOCK + content


DECISION_BLOCK = f"""\
2026-08-30 | HQ / ALL INITIATIVES | FOUNDER DECISION | {MARK_DECISION}. Keep **CHF 1B/year by 31 Dec 2029**. Supersede only the older 2030 extension: **CHF 10B/year by 31 Dec 2030**; add **CHF 100B/year by 31 Dec 2031**. Equivalents: 2029 ≈ CHF 2.74M/day / CHF 82.2M trailing-30d; 2030 ≈ CHF 27.4M/day / CHF 822M trailing-30d; 2031 ≈ CHF 274M/day / CHF 8.22B trailing-30d. BOARD_HTML sticky target table adds a real-company benchmark column based on latest reported annual revenue/sales, never valuation/market cap. Reference rungs include Telegram + HubSpot, Shopify + Spotify, and Johnson & Johnson. Add a bottom WORLD GIANTS section with revenue and **net profit**, including Amazon and the 2026 Fortune 500 U.S. top 10, plus selected profitability benchmarks including Microsoft, Saudi Aramco, Meta, J&J, Visa, Mastercard, Shopify, Spotify, HubSpot, Telegram and Tether. Tether's profit may be shown while revenue is explicitly non-comparable/not disclosed in the same way as public-company operating revenue. Targets remain forcing targets, not forecasts.

updated_by=HQ_GPT

"""


def transform_decisions(content: str) -> str:
    if MARK_DECISION in content:
        return content
    return DECISION_BLOCK + content


TARGET_TABLE = f"""\
{MARK_BOARD}
<table style="font-size:10px;line-height:1.1;width:100%;min-width:0"><tr><th>DEADLINE</th><th>DAILY</th><th>TRAILING 30D</th><th>ANNUALISED RUN-RATE</th><th>REAL COMPANY REVENUE BENCHMARK</th></tr>
<tr><td><b>31 DEC 2026</b></td><td><b>CHF 10k/day</b></td><td>CHF 300k</td><td>CHF 3.65M</td><td><span class="dim">Pre-scale vs selected major-company benchmarks</span></td></tr>
<tr><td><b>31 DEC 2027</b></td><td><b>CHF 100k/day</b></td><td>CHF 3M</td><td>CHF 36.5M</td><td><span class="dim">Pre-scale vs selected major-company benchmarks</span></td></tr>
<tr><td><b>31 DEC 2028</b></td><td><b>CHF 1M/day</b></td><td>CHF 30M</td><td>CHF 365M</td><td>Next scale: <b>Telegram ~$1.4B</b> · HubSpot $3.13B</td></tr>
<tr><td><b>31 DEC 2029</b></td><td><b>CHF 2.74M/day</b></td><td>CHF 82.2M</td><td><b>CHF 1B/year</b></td><td><b>Telegram ~$1.4B</b> · HubSpot $3.13B</td></tr>
<tr><td><b>31 DEC 2030</b></td><td><b>CHF 27.4M/day</b></td><td>CHF 822M</td><td><b>CHF 10B/year</b></td><td><b>Shopify $11.56B</b> · Spotify €17.19B</td></tr>
<tr><td><b>31 DEC 2031</b></td><td><b>CHF 274M/day</b></td><td>CHF 8.22B</td><td><b>CHF 100B/year</b></td><td><b>Johnson &amp; Johnson $94.19B</b> · ≈ target scale</td></tr></table>
<div style="font-size:9.5px;margin-top:5px"><b>2029–2031 are annual targets:</b> CHF 1B/year → CHF 10B/year → CHF 100B/year. 2026–2028 remain daily run-rate targets. Company benchmarks use reported annual revenue/sales, not valuation or market cap. Telegram is 2024; other rung references are 2025. Targets ≠ forecasts.</div>"""


GIANTS_SECTION = f"""
{MARK_GIANTS}
<h2><span class="k">Scale benchmark · revenue is not valuation · profit matters</span>World giants — revenue &amp; net profit</h2>
<div class="card" style="border-left:5px solid #000"><b>WHY THIS IS HERE:</b> revenue alone can hide terrible economics. Compare both <b>money flowing through the company</b> and <b>what the company actually keeps</b>. The tables use reported annual figures; currencies remain as reported rather than pretending FX makes them perfectly comparable. Private-company disclosures (Telegram, Tether) are less directly comparable than audited public-company filings.</div>

<div class="card"><b>2026 FORTUNE GLOBAL 500 — TOP 10 BY REVENUE:</b> 1 Amazon · 2 Walmart · 3 State Grid · 4 UnitedHealth Group · 5 Saudi Aramco · 6 Apple · 7 McKesson · 8 Alphabet · 9 CVS Health · 10 China National Petroleum. <b>Amazon is now the scale anchor at the top.</b></div>

<h2 style="font-size:24px"><span class="k">2026 Fortune 500 · U.S. ranking figures · USD</span>Top 10 U.S. companies by revenue — with profit</h2>
<div class="scroll"><table style="min-width:900px"><tr><th>#</th><th>COMPANY</th><th>REVENUE</th><th>NET PROFIT</th><th>NET MARGIN</th></tr>
<tr><td class="v">1</td><td><b>Amazon</b></td><td>$716.924B</td><td><b>$77.670B</b></td><td>10.8%</td></tr>
<tr><td class="v">2</td><td><b>Walmart</b></td><td>$713.163B</td><td><b>$21.893B</b></td><td>3.1%</td></tr>
<tr><td class="v">3</td><td><b>UnitedHealth Group</b></td><td>$447.567B</td><td><b>$12.056B</b></td><td>2.7%</td></tr>
<tr><td class="v">4</td><td><b>Apple</b></td><td>$416.161B</td><td><b>$112.010B</b></td><td>26.9%</td></tr>
<tr><td class="v">5</td><td><b>Alphabet</b></td><td>$402.836B</td><td><b>$132.170B</b></td><td>32.8%</td></tr>
<tr><td class="v">6</td><td><b>CVS Health</b></td><td>$402.067B</td><td><b>$1.768B</b></td><td>0.4%</td></tr>
<tr><td class="v">7</td><td><b>Berkshire Hathaway</b></td><td>$371.444B</td><td><b>$66.968B</b></td><td>18.0%</td></tr>
<tr><td class="v">8</td><td><b>McKesson</b></td><td>$359.051B</td><td><b>$3.295B</b></td><td>0.9%</td></tr>
<tr><td class="v">9</td><td><b>ExxonMobil Holdings</b></td><td>$332.238B</td><td><b>$28.844B</b></td><td>8.7%</td></tr>
<tr><td class="v">10</td><td><b>Cencora</b></td><td>$321.333B</td><td><b>$1.554B</b></td><td>0.5%</td></tr>
</table></div>

<h2 style="font-size:24px"><span class="k">Latest reported FY · selected economics benchmarks</span>Profit machines &amp; STARTEND reference companies</h2>
<div class="scroll"><table style="min-width:1100px"><tr><th>COMPANY</th><th>PERIOD</th><th>REVENUE / SALES</th><th>NET PROFIT</th><th>NET MARGIN</th><th>STARTEND LESSON</th></tr>
<tr><td><b>Microsoft</b></td><td>FY2026</td><td>$331.839B</td><td><b>$133.749B</b></td><td>40.3%</td><td>Software economics at global scale.</td></tr>
<tr><td><b>Saudi Aramco</b></td><td>2025</td><td>$445.654B</td><td><b>$93.389B</b></td><td>21.0%</td><td>Global scale + enormous absolute profit.</td></tr>
<tr><td><b>Meta</b></td><td>2025</td><td>$200.966B</td><td><b>$60.458B</b></td><td>30.1%</td><td>Distribution becomes the economic engine.</td></tr>
<tr><td><b>Johnson &amp; Johnson</b></td><td>2025</td><td>$94.193B</td><td><b>$26.804B</b></td><td>28.5%</td><td>Almost exactly the STARTEND CHF 100B 2031 revenue rung.</td></tr>
<tr><td><b>Visa</b></td><td>FY2025</td><td>$40.000B</td><td><b>$20.058B</b></td><td>50.1%</td><td>Toll-booth/network economics: small slice of huge payment flow.</td></tr>
<tr><td><b>Mastercard</b></td><td>2025</td><td>$32.791B</td><td><b>$14.968B</b></td><td>45.6%</td><td>Transaction/network economics with extraordinary margins.</td></tr>
<tr><td><b>Spotify</b></td><td>2025</td><td>€17.186B</td><td><b>€2.212B</b></td><td>12.9%</td><td>Global subscription platform near the 2030 rung.</td></tr>
<tr><td><b>Shopify</b></td><td>2025</td><td>$11.556B</td><td><b>$1.231B</b></td><td>10.7%</td><td>Direct 4.2 benchmark: merchant SaaS + merchant solutions.</td></tr>
<tr><td><b>HubSpot</b></td><td>2025</td><td>$3.131B</td><td><b>$45.9M</b></td><td>1.5%</td><td>Global B2B SaaS scale; revenue can arrive before large GAAP profit.</td></tr>
<tr><td><b>Telegram</b></td><td>2024 private</td><td>~$1.4B</td><td><b>~$540M</b></td><td>~38.6%</td><td>Massive distribution with a lean platform model.</td></tr>
<tr><td><b>Tether</b></td><td>2025 attestation</td><td><span class="dim">n/a comparable operating-revenue disclosure</span></td><td><b>&gt;$10B</b></td><td>n/a</td><td>Profit benchmark for reserve/network economics; do not fake a revenue comparison.</td></tr>
</table></div>
<div class="legend"><b>SOURCES / BASIS:</b> Fortune 500 2026 and Fortune Global 500 2026 for rankings; company annual reports/earnings for Microsoft, Saudi Aramco, Meta, Johnson &amp; Johnson, Visa, Mastercard, Spotify, Shopify and HubSpot; Financial Times for Telegram 2024 private-company revenue/profit; Tether Q4 2025 attestation for profit. Figures are rounded. This is a scale/profitability benchmark, not an investment ranking.</div>
"""


def transform_board(content: str) -> str:
    if MARK_BOARD in content and MARK_GIANTS in content:
        return content

    out = content
    table_pat = re.compile(
        r'<table style="font-size:10px;line-height:1\.1;width:100%;min-width:0">'
        r'<tr><th>DEADLINE</th><th>DAILY</th><th>TRAILING 30D</th><th>ANNUALISED RUN-RATE</th></tr>'
        r'.*?</table>\s*'
        r'<div style="font-size:9\.5px;margin-top:5px"><b>2029/2030 are annual targets:</b>.*?</div>',
        re.S,
    )
    if not table_pat.search(out):
        raise RuntimeError("BOARD_TARGET_TABLE_NOT_FOUND")
    out = table_pat.sub(TARGET_TABLE, out, count=1)

    if MARK_GIANTS not in out:
        wrap_close = out.rfind("</div></body>")
        if wrap_close != -1:
            out = out[:wrap_close] + GIANTS_SECTION + "\n" + out[wrap_close:]
        else:
            close = out.rfind("</body>")
            if close == -1:
                raise RuntimeError("BOARD_BODY_END_NOT_FOUND")
            out = out[:close] + GIANTS_SECTION + "\n" + out[close:]

    return out


def main() -> int:
    log("TARGET_BENCHMARK_MIGRATION_START")
    versions: dict[str, int] = {}
    versions["01_STRATEGY"] = write_mutation(
        "01_STRATEGY",
        transform_strategy,
        MARK_STRATEGY,
        "Founder target ladder: 2029 CHF1B, 2030 CHF10B, 2031 CHF100B + real-company benchmark doctrine",
    )
    versions["03_DECISIONS"] = write_mutation(
        "03_DECISIONS",
        transform_decisions,
        MARK_DECISION,
        "Founder target ladder + company benchmarks + net-profit comparison",
    )
    versions["BOARD_HTML"] = write_mutation(
        "BOARD_HTML",
        transform_board,
        MARK_BOARD,
        "Sticky target benchmarks; 2030 CHF10B, 2031 CHF100B; Amazon/J&J/top-US revenue + net-profit section",
    )

    for file_name, marker in (
        ("01_STRATEGY", MARK_STRATEGY),
        ("03_DECISIONS", MARK_DECISION),
        ("BOARD_HTML", MARK_BOARD),
    ):
        rows = canon_read(file_name)
        row = canonical(rows)
        text = str(row["content"])
        if marker not in text:
            raise RuntimeError(f"FINAL_VERIFY_MISSING {file_name}")
        if file_name == "BOARD_HTML":
            required = [
                "CHF 10B/year",
                "CHF 100B/year",
                "REAL COMPANY REVENUE BENCHMARK",
                "Amazon",
                "Johnson &amp; Johnson",
                "Tether",
                MARK_GIANTS,
            ]
            missing = [x for x in required if x not in text]
            if missing:
                raise RuntimeError(f"FINAL_BOARD_VERIFY_MISSING {missing}")
        log("FINAL_OK", file_name, int(row["version"]))

    log("TARGET_BENCHMARK_MIGRATION_DONE", versions)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log("BLOCKED", type(exc).__name__, str(exc))
        raise
