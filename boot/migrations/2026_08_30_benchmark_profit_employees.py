from __future__ import annotations

import html
import json
import os
import re
import urllib.request
from typing import Any, Callable

CANON_URL = (os.environ.get("CANON_RW_URL") or "https://startend.app.n8n.cloud/webhook/canon-rw-9k2x7m4q").strip()
UPDATED_BY = "HQ_GPT"
TIMEOUT = 60

BOARD_MARK = "HQ_GPT_BENCHMARK_NETPROFIT_EMPLOYEES_20260830"
DECISION_MARK = "BENCHMARK_NETPROFIT_EMPLOYEES_20260830"
OLD_MARK_START = "<!-- HQ_GPT_BENCHMARK_WATCHLIST_20260830 -->"
OLD_MARK_END = "<!-- /HQ_GPT_BENCHMARK_WATCHLIST_20260830 -->"
FORTUNE_MARK_START = "<!-- HQ_GPT_FORTUNE50_NETPROFIT_EMPLOYEES_20260830 -->"
FORTUNE_MARK_END = "<!-- /HQ_GPT_FORTUNE50_NETPROFIT_EMPLOYEES_20260830 -->"


def post(payload: dict[str, Any]) -> Any:
    req = urllib.request.Request(
        CANON_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw or "null")


def read_rows(key: str) -> list[dict[str, Any]]:
    rows = post({"action": "read", "keyValue": key})
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"STOP: canon read returned empty for {key}")
    return rows


def canonical(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(rows, key=lambda r: int(r.get("version") or 0))


def insert(key: str, version: int, content: str, note: str) -> Any:
    return post(
        {
            "action": "insert",
            "file": key,
            "version": version,
            "content": content,
            "note": note,
            "updated_by": UPDATED_BY,
        }
    )


def delete_id(row_id: Any) -> Any:
    return post({"action": "delete", "id": str(row_id)})


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def parse_profit(value: str) -> float:
    cleaned = value.replace(",", "").replace("$", "").replace("€", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not m:
        return float("-inf")
    return float(m.group(0))


EMPLOYEES = {
    "Amazon": "≈1.56M",
    "Walmart": "≈2.10M",
    "UnitedHealth Group": "≈400k",
    "Apple": "≈166k",
    "Alphabet": "≈190k",
    "CVS Health": "≈300k",
    "Berkshire Hathaway": "≈392k",
    "McKesson": "≈48k",
    "ExxonMobil Holdings": "≈61k",
    "Cencora": "≈46k",
    "Microsoft": "≈228k",
    "JPMorgan Chase": "≈318k",
    "Costco Wholesale": "≈341k",
    "Cigna Group": "≈72k",
    "Cardinal Health": "≈50k",
    "Nvidia": "≈36k",
    "Meta Platforms": "≈78k",
    "Elevance Health": "≈105k",
    "Centene": "≈60k",
    "Bank of America": "≈213k",
    "Chevron": "≈46k",
    "Ford Motor": "≈171k",
    "General Motors": "≈156k",
    "Citigroup": "≈227k",
    "Home Depot": "≈470k",
    "Fannie Mae": "≈8k",
    "Kroger": "≈409k",
    "Verizon Communications": "≈100k",
    "Phillips 66": "≈14k",
    "Marathon Petroleum": "≈18k",
    "StoneX Group": "≈5k",
    "State Farm Insurance": "≈96k",
    "Freddie Mac": "≈8k",
    "Humana": "≈65k",
    "AT&T": "≈135k",
    "Goldman Sachs Group": "≈49k",
    "Comcast": "≈179k",
    "Wells Fargo": "≈215k",
    "Morgan Stanley": "≈83k",
    "Valero Energy": "≈10k",
    "Dell Technologies": "≈108k",
    "Target": "≈440k",
    "Tesla": "≈126k",
    "Walt Disney": "≈189k",
    "Johnson & Johnson": "≈140k",
    "PepsiCo": "≈319k",
    "Boeing": "≈172k",
    "United Parcel Service": "≈490k",
    "RTX": "≈180k",
    "FedEx": "≈500k",
}


def extract_fortune_rows(content: str) -> list[tuple[str, str, str, str, str]]:
    pos = content.find("FORTUNE 500")
    if pos < 0:
        raise ValueError("Fortune 500 section missing")
    tbody_start = content.find("<tbody>", pos)
    tbody_end = content.find("</tbody>", tbody_start)
    if tbody_start < 0 or tbody_end < 0:
        raise ValueError("Fortune tbody missing")
    body = content[tbody_start + len("<tbody>") : tbody_end]
    rows: list[tuple[str, str, str, str, str]] = []
    for chunk in re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.I | re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", chunk, flags=re.I | re.S)
        if len(cells) != 5:
            continue
        vals = tuple(strip_tags(c) for c in cells)
        if vals[0].isdigit():
            rows.append(vals)  # type: ignore[arg-type]
    if len(rows) != 50:
        raise ValueError(f"Expected 50 Fortune rows, parsed {len(rows)}")
    return rows


def watchlist_html() -> str:
    rows = [
        ("Johnson & Johnson", "2025", "$94.193B", "$26.804B", "28.5%", "≈140k", "2031 north-star scale class"),
        ("Visa", "FY2025", "$40.000B", "$20.058B", "50.1%", "≈34k", "toll-road economics"),
        ("Tether", "2025", "n/a", ">$10B through Q3-2025", "n/a", "≈200 est.", "private; reserve/network economics"),
        ("Spotify", "2025", "€17.186B", "€2.212B", "12.9%", "≈7.3k", "global subscription/media platform"),
        ("Shopify", "2025", "$11.556B", "$1.231B", "10.7%", "≈8.1k", "commerce platform"),
        ("Telegram", "2024 actual", "$1.400B", "$0.540B", "38.6%", "≈50 core est.", "private, >1B users; latest reliable full-year actual"),
        ("HubSpot", "2025", "$3.130B", "$0.0459B GAAP", "1.5%", "≈8.8k", "SaaS/customer platform"),
        ("STARTEND", "2026 current", "CHF 0", "pre-revenue · quantified costs only", "n/a", "≈1 human + AI/contractors", "OUR LINE — update as we grow"),
    ]
    body = []
    for company, period, revenue, profit, margin, employees, why in rows:
        strong = company in {"Johnson & Johnson", "STARTEND"}
        c = f"<b>{html.escape(company)}</b>" if strong else html.escape(company)
        p = f"<b>{html.escape(profit)}</b>" if company == "Johnson & Johnson" else html.escape(profit)
        body.append(
            f"<tr><td>{c}</td><td>{html.escape(period)}</td><td>{html.escape(revenue)}</td>"
            f"<td>{p}</td><td>{html.escape(margin)}</td><td>{html.escape(employees)}</td><td>{html.escape(why)}</td></tr>"
        )
    return f'''<!-- {BOARD_MARK} -->
<h2 style="margin-top:4px">BENCHMARK WATCHLIST — REVENUE + NET PROFIT</h2>
<p class="dim" style="font-size:12px;margin-bottom:12px;line-height:1.5">Sorted by reported net profit, highest first. Employee counts are approximate latest public figures or private-company estimates. Mixed currencies are directional and not FX-normalized. STARTEND stays last so our line is always visible.</p>
<div class="scroll"><table style="table-layout:auto;min-width:1100px">
<thead><tr><th>COMPANY</th><th>PERIOD</th><th>REVENUE</th><th>NET PROFIT</th><th>NET MARGIN</th><th>EMPLOYEES ≈</th><th>WHY WATCH</th></tr></thead>
<tbody>{''.join(body)}</tbody></table></div>
<!-- /{BOARD_MARK} -->'''


def fortune_html(rows: list[tuple[str, str, str, str, str]]) -> str:
    sorted_rows = sorted(rows, key=lambda r: parse_profit(r[3]), reverse=True)
    trs = []
    for rank, company, revenue, profit, margin in sorted_rows:
        emp = EMPLOYEES.get(company, "≈TBD")
        special = ' style="border-left:4px solid var(--swiss)"' if company == "Johnson & Johnson" else ""
        trs.append(
            f"<tr{special}><td>{html.escape(rank)}</td><td>{html.escape(company)}</td><td>{html.escape(revenue)}</td>"
            f"<td><b>{html.escape(profit)}</b></td><td>{html.escape(margin)}</td><td>{html.escape(emp)}</td></tr>"
        )
    return f'''{FORTUNE_MARK_START}
<h2 style="margin-top:28px">FORTUNE 500 — TOP 50 U.S. BY REVENUE (2026 LIST; SORTED BY NET PROFIT)</h2>
<p class="dim" style="font-size:11px;margin-bottom:12px">These are the same Fortune revenue-top-50 companies; first column preserves original Fortune revenue rank. Rows are sorted here by net profit. Employee counts are approximate latest reported headcount.</p>
<div class="scroll"><table style="table-layout:auto;min-width:1050px">
<thead><tr><th>FORTUNE REV RANK</th><th>COMPANY</th><th>REVENUE USD B</th><th>NET PROFIT USD B</th><th>NET MARGIN</th><th>EMPLOYEES ≈</th></tr></thead>
<tbody>{''.join(trs)}</tbody></table></div>
<p class="dim" style="font-size:11px;margin-top:12px;line-height:1.5;font-style:italic">Baseline: Fortune 500 2026 / FY2025 company data already carried by this board. Headcount is approximate and should be refreshed with annual-report cycles.</p>
<div class="dark" style="background:var(--black);border-left:5px solid var(--swiss);margin-top:24px">
<h3 style="color:var(--swiss);font-family:'Didot','Bodoni MT',Georgia,serif;font-weight:400;font-size:20px;margin:0 0 8px">FOUNDER NORTH STAR — PERMANENT</h3>
<p style="color:#fff;margin:0;line-height:1.65;font-size:13px">Build STARTEND into the Johnson &amp; Johnson scale class: roughly $94B annual revenue and $27B annual net profit on the current benchmark. Revenue is not enough; profit, margin and low human-labour scaling matter. Target, not forecast. Keep this benchmark permanently visible.</p>
</div>
{FORTUNE_MARK_END}'''


def remove_existing_new_blocks(content: str) -> str:
    for start_mark, end_mark in [
        (f"<!-- {BOARD_MARK} -->", f"<!-- /{BOARD_MARK} -->"),
        (FORTUNE_MARK_START, FORTUNE_MARK_END),
    ]:
        while start_mark in content and end_mark in content:
            s = content.index(start_mark)
            e = content.index(end_mark, s) + len(end_mark)
            content = content[:s] + content[e:]
    return content


def transform_board(content: str) -> str:
    if BOARD_MARK in content and FORTUNE_MARK_START in content and "Where the money is" not in content:
        return content

    # Preserve the exact current Fortune data before removing the old combined benchmark block.
    rows = extract_fortune_rows(content)
    content = remove_existing_new_blocks(content)

    if OLD_MARK_START not in content or OLD_MARK_END not in content:
        raise ValueError("Old benchmark marker block missing; refusing stale/unsafe rewrite")
    old_s = content.index(OLD_MARK_START)
    old_e = content.index(OLD_MARK_END, old_s) + len(OLD_MARK_END)
    bottom = fortune_html(rows)
    content = content[:old_s] + bottom + content[old_e:]

    where_pos = content.find("Where the money is")
    if where_pos < 0:
        raise ValueError("Where the money is section missing before migration")
    where_start = content.rfind("<h2", 0, where_pos)
    next_h2 = content.find("<h2", where_pos + len("Where the money is"))
    if where_start < 0 or next_h2 < 0 or "Portfolio scale map" not in content[next_h2 : next_h2 + 500]:
        raise ValueError("Could not safely bound Where-the-money-is block")
    content = content[:where_start] + watchlist_html() + "\n\n" + content[next_h2:]

    # Required preservation checks.
    required = [
        "31 DEC 2030",
        "CHF 10B/year",
        "1% sales pool &amp; revenue",
        "STARTEND Commerce OS",
        "4.2",
    ]
    for token in required:
        if token not in content:
            raise ValueError(f"Preservation check failed: {token}")
    if "Where the money is" in content:
        raise ValueError("Where-the-money-is removal failed")
    if BOARD_MARK not in content or FORTUNE_MARK_START not in content:
        raise ValueError("Benchmark markers missing after transform")
    return content


def transform_decisions(content: str) -> str:
    if DECISION_MARK in content:
        return content
    entry = (
        "2026-08-30 | HQ BOARD | FOUNDER DECISION | BENCHMARK_NETPROFIT_EMPLOYEES_20260830. "
        "Benchmark watchlist moved to the former Where-the-money-is position; verbose Where-the-money-is block removed. "
        "Both benchmark tables carry approximate employee counts and are sorted by net profit, while preserving Fortune revenue rank. "
        "STARTEND is permanently the final watchlist row. Hard target ladder unchanged; 2030 remains CHF 10B/year. "
        "1% sales pool and 4.2 Commerce OS unchanged.\n\nupdated_by=HQ_GPT\n\n"
    )
    return entry + content


def prune_top3(key: str) -> None:
    rows = read_rows(key)
    ordered = sorted(rows, key=lambda r: (int(r.get("version") or 0), int(r.get("id") or 0)), reverse=True)
    for row in ordered[3:]:
        delete_id(row.get("id"))


def write_key(key: str, transform: Callable[[str], str], note: str, marker: str) -> dict[str, Any]:
    # Mandatory immediate re-read before write.
    rows = read_rows(key)
    base = canonical(rows)
    base_content = base.get("content") or ""
    if marker in base_content:
        return base
    new_content = transform(base_content)
    target_version = int(base.get("version") or 0) + 1
    response = insert(key, target_version, new_content, note)

    # Mandatory immediate read after write + race check.
    after = read_rows(key)
    same = [r for r in after if int(r.get("version") or 0) == target_version]
    ours = [r for r in same if marker in (r.get("content") or "") and r.get("updated_by") == UPDATED_BY]
    if len(same) > 1:
        # Re-merge on the competing row and insert max+1, then delete our orphan.
        other_candidates = [r for r in same if r not in ours]
        if not other_candidates:
            raise RuntimeError(f"Race detected for {key}, but competing row could not be identified")
        other = max(other_candidates, key=lambda r: int(r.get("id") or 0))
        merged = transform(other.get("content") or "")
        next_version = max(int(r.get("version") or 0) for r in after) + 1
        insert(key, next_version, merged, note + " · race remerge")
        for orphan in ours:
            delete_id(orphan.get("id"))
        after = read_rows(key)

    top = canonical(after)
    if marker not in (top.get("content") or ""):
        raise RuntimeError(f"Post-write marker missing from canonical {key}")
    prune_top3(key)
    return canonical(read_rows(key))


def verify_board(content: str) -> dict[str, Any]:
    pos = content.find("FORTUNE 500 — TOP 50 U.S. BY REVENUE (2026 LIST; SORTED BY NET PROFIT)")
    tbody_s = content.find("<tbody>", pos)
    tbody_e = content.find("</tbody>", tbody_s)
    rows = re.findall(r"<tr[^>]*>.*?</tr>", content[tbody_s:tbody_e], flags=re.I | re.S) if pos >= 0 else []
    return {
        "marker": BOARD_MARK in content,
        "fortune_rows": len(rows),
        "where_money_occurrences": content.count("Where the money is"),
        "startend_watchlist": "OUR LINE — update as we grow" in content,
        "target_2030_10b": "31 DEC 2030" in content and "CHF 10B/year" in content,
        "commerce_4_2": "STARTEND Commerce OS" in content and "4.2" in content,
        "one_pct": "1% sales pool &amp; revenue" in content,
        "employee_columns": content.count("EMPLOYEES ≈") >= 2,
    }


def main() -> None:
    if not CANON_URL:
        raise SystemExit("STOP: CANON_RW_URL missing")
    board = write_key(
        "BOARD_HTML",
        transform_board,
        "Net-profit benchmark sorting + employee estimates; move watchlist up; remove Where-the-money-is; preserve 1%/4.2/targets",
        BOARD_MARK,
    )
    decisions = write_key(
        "03_DECISIONS",
        transform_decisions,
        "Net-profit benchmark tables + approximate employees; STARTEND final row; Where-the-money-is removed",
        DECISION_MARK,
    )
    check = verify_board(board.get("content") or "")
    if not all(check.values()):
        raise RuntimeError(f"Verification failed: {check}")
    print(
        json.dumps(
            {
                "ok": True,
                "board": {"version": board.get("version"), "id": board.get("id"), "updated_by": board.get("updated_by"), **check},
                "decisions": {"version": decisions.get("version"), "id": decisions.get("id"), "updated_by": decisions.get("updated_by"), "marker": DECISION_MARK in (decisions.get("content") or "")},
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
