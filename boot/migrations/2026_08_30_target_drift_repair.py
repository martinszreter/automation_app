from __future__ import annotations

"""Repair BOARD_HTML target-table drift without creating a new publishing path.

The target benchmark migration marker can survive while another board mutation
leaves an older 2030=CHF2B table in place. This repair reuses the existing
TARGET_TABLE asset and the existing canon writer, and verifies content rather
than trusting marker presence alone.
"""

import re

import hq_extend_targets_2029_2030 as core
import target_benchmarks as target

MARK = "TARGET_DRIFT_REPAIR_10B_100B_20260830"
BUS_MARK = "HQ_GPT_TARGET_DRIFT_REPAIR_DONE"
core.MARK = MARK

DECISION = f"""2026-08-30 | HQ BOARD | OPERATING DECISION | {MARK}. Repair the live sticky hard-target table after content drift left the older CHF 2B/year 2030 row visible even though the target-benchmark marker already existed. Canon truth remains CHF 1B/year by 2029 → CHF 10B/year by 2030 → CHF 100B/year by 2031. Reuse the existing target benchmark table asset; verification must check the actual 2030/2031 values and company benchmark column, not marker presence alone.

updated_by=HQ_GPT"""


def transform_decisions(content: str) -> str:
    if MARK in content:
        return content
    sep = re.search(r"(?m)^-{5,}\s*$", content)
    block = DECISION.rstrip() + "\n\n"
    if sep:
        return content[: sep.start()] + block + content[sep.start() :]
    return block + content


def transform_board(content: str) -> str:
    if MARK in content and all(x in content for x in ("CHF 10B/year", "CHF 100B/year", "REAL COMPANY REVENUE BENCHMARK")):
        return content

    hard = "<!-- HARD_TARGETS_DACH_LTV_20260830 -->"
    hs = content.find(hard)
    if hs < 0:
        raise RuntimeError("hard target anchor missing")
    t0 = content.find("<table", hs)
    t1 = content.find("</table>", t0)
    if t0 < 0 or t1 < 0:
        raise RuntimeError("hard target table missing")
    t1 += len("</table>")

    # If the existing benchmark marker sits directly before the table, replace it
    # together with the table so the canonical asset appears exactly once.
    replacement_start = t0
    marker_pos = content.rfind(target.MARK_BOARD, hs, t0)
    if marker_pos >= hs:
        replacement_start = marker_pos

    # Remove the immediately-following target explanatory note (old or new), then
    # insert the canonical target asset from the existing benchmark migration.
    after = t1
    tail = content[after : after + 1800]
    note_match = re.match(
        r"\s*<div[^>]*>\s*<b>2029(?:/2030|–2031|&#8211;2031).*?</div>",
        tail,
        flags=re.S,
    )
    if note_match:
        after += note_match.end()

    repaired = target.TARGET_TABLE + "\n<!-- " + MARK + " -->"
    changed = content[:replacement_start] + repaired + content[after:]

    checks = [
        "31 DEC 2030", "CHF 27.4M/day", "CHF 822M", "CHF 10B/year",
        "31 DEC 2031", "CHF 274M/day", "CHF 8.22B", "CHF 100B/year",
        "REAL COMPANY REVENUE BENCHMARK", "Shopify", "Telegram", "Johnson &amp; Johnson",
        MARK,
    ]
    missing = [x for x in checks if x not in changed]
    if missing:
        raise RuntimeError("target drift repair checks missing " + repr(missing))
    return changed


def main() -> None:
    assets = core.latest("02_ASSETS")
    print("ASSETS_OK", assets.get("version"), assets.get("id"))
    print("REUSE", "target_benchmarks.TARGET_TABLE", "+ scripts/hq_extend_targets_2029_2030.py")

    vd = core.write(
        "03_DECISIONS",
        transform_decisions,
        "Repair live target-table drift; verify actual 10B/100B content rather than marker only",
    )
    vb = core.write(
        "BOARD_HTML",
        transform_board,
        "Repair sticky hard-target table to 10B/year 2030 and 100B/year 2031 using existing benchmark asset",
    )
    print("CANON_DONE", {"03_DECISIONS": vd, "BOARD_HTML": vb})

    status, bus = core.req(core.BUS)
    if status != 200 or not isinstance(bus, dict) or not bus.get("bus_cursor"):
        raise RuntimeError("bus cursor missing")
    recent = bus.get("recent", []) if isinstance(bus.get("recent", []), list) else []
    if not any(BUS_MARK in (item.get("what") or "") for item in recent if isinstance(item, dict)):
        ps, payload = core.req(core.BUS, {
            "team": "HQ_GPT",
            "project": "0 HQ",
            "type": "DONE",
            "what": f"{BUS_MARK} · Repaired live sticky targets to CHF10B/year 2030 and CHF100B/year 2031 using the existing target benchmark asset. Canon: 03_DECISIONS v{vd} · BOARD_HTML v{vb}.",
            "next": "Keep initiative-level money model visible under Revenue & costs; keep 4.1 execution lock unchanged.",
            "link": core.BOARD,
            "bus_cursor": bus["bus_cursor"],
        })
        if ps != 200:
            raise RuntimeError(f"bus failed {ps} {payload!r}")
        print("BUS_DONE", payload)
    else:
        print("BUS_GUARD existing DONE found")


if __name__ == "__main__":
    main()
