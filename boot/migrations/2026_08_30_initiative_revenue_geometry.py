from __future__ import annotations

"""One-off HQ canon migration: initiative-level revenue geometry.

Reuses the existing canon writer/race/prune helper in
scripts/hq_extend_targets_2029_2030.py. The section is deliberately a scenario
model, not a forecast: it corrects the raw arithmetic, separates recurring MRR
from setup/one-time revenue, and flags overlapping customer pools.
"""

import re

import hq_extend_targets_2029_2030 as core

MARK = "INITIATIVE_REVENUE_GEOMETRY_20260830"
BUS_MARK = "HQ_GPT_INITIATIVE_REVENUE_GEOMETRY_DONE"
core.MARK = MARK

DECISION = f"""2026-08-30 | HQ BOARD | DECISION | {MARK}. Add an initiative-level money table directly under Revenue & costs so every venture is forced into pool × conversion × price economics rather than only project-level totals. Preserve Kimi's useful structure but correct the arithmetic and revenue-type mismatch: the raw customer-pool line-sum is ~2.95M and the raw 1% line-sum is 29,500, not ~35,000. 4.1 Swiss Websites must not be counted as MRR: current working offer is CHF 1,390 for the first 10 clients, targeting CHF 1,790, with no monthly fee. Using the recurring rows only, the raw 1% scenario line-sum is 29,000 active customers and CHF 2.6685M MRR; at the modelled weighted recurring ARPU of ~CHF 92, CHF 1M MRR corresponds to ~10,900 active customers, ~37.5% of that recurring 1% line-sum. This remains a scenario, not a forecast: pools and ARPUs must be validated, and overlapping pools — especially 3.0 NHT SaaS versus its child initiatives — must never be summed as independent portfolio TAM.

updated_by=HQ_GPT"""

SECTION = r'''
<!-- INITIATIVE_REVENUE_GEOMETRY_20260830 -->
<h2><span class="k">INITIATIVE-LEVEL MONEY · SCENARIO, NOT FORECAST</span>What must be true for CHF 1M/month</h2>

<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:8px">
  <div class="card" style="flex:1 1 180px;border-left-color:#DA291C"><div class="label">RAW POOL LINE-SUM</div><div class="display" style="font-size:28px">~2.95M</div><div style="font-size:11px">Modelled customers. <b>Not additive TAM</b> because some pools overlap.</div></div>
  <div class="card" style="flex:1 1 180px;border-left-color:#DA291C"><div class="label">RAW 1% LINE-SUM</div><div class="display" style="font-size:28px">29,500</div><div style="font-size:11px">Corrected from ~35,000. Still overlapping.</div></div>
  <div class="card" style="flex:1 1 180px;border-left-color:#DA291C"><div class="label">RECURRING 1% SCENARIO</div><div class="display" style="font-size:28px">CHF 2.6685M</div><div style="font-size:11px">MRR line-sum across recurring rows only.</div></div>
  <div class="card" style="flex:1 1 180px;border-left-color:#DA291C"><div class="label">CHF 1M MRR MATH</div><div class="display" style="font-size:28px">~10.9k</div><div style="font-size:11px">Active customers at ~CHF 92 weighted model ARPU = ~37.5% of the recurring 1% line-sum.</div></div>
</div>

<div class="card" style="margin-top:10px;border-left-color:#DA291C;background:#fff3f3">
  <b>USE THIS TABLE AS A FORCING MODEL, NOT A PROMISE.</b> Pool × 1% × price is useful because it exposes the economics initiative by initiative. But the pools are not yet all validated, some initiatives overlap, and several prices below are Kimi-model assumptions rather than locked offers. The biggest anti-double-counting issue is <b>3.0 NHT SaaS versus 3.2 / 3.5a / 3.5b</b>. Do not add them together as if they were independent customers.
</div>

<div class="scroll" style="margin-top:10px"><table style="min-width:1180px;font-size:11px">
<tr><th>INITIATIVE</th><th>MODELLED CUSTOMER POOL</th><th>1% LINE-SUM</th><th>WORKING ECONOMICS</th><th>REVENUE IF 1% BUYS / IS ACTIVE</th><th>STATUS / CAVEAT</th></tr>
<tr><td><b>3.0 NHT SaaS</b></td><td>1,000,000</td><td>10,000</td><td>CHF 80/mo</td><td><b>CHF 800,000 MRR</b></td><td>MODEL. Umbrella pool may overlap 3.2 / 3.5a / 3.5b.</td></tr>
<tr><td><b>5.1 wordblast</b></td><td>500,000</td><td>5,000</td><td>CHF 49/mo</td><td><b>CHF 245,000 MRR</b></td><td>MODEL assumption; validate price + reachable pool before treating as plan.</td></tr>
<tr><td><b>5.2 optimizeyourkid</b></td><td>500,000</td><td>5,000</td><td>CHF 49/mo</td><td><b>CHF 245,000 MRR</b></td><td>MODEL assumption; validate price + reachable pool before treating as plan.</td></tr>
<tr><td><b>1.3 nieczytaj.pl</b></td><td>500,000</td><td>5,000</td><td>CHF 80/mo</td><td><b>CHF 400,000 MRR</b></td><td>MODEL assumption; monetisation must prove real willingness to pay.</td></tr>
<tr><td><b>3.5b Restaurant</b></td><td>100,000</td><td>1,000</td><td>CHF 1,990 setup + CHF 249/mo</td><td><b>CHF 249,000 MRR</b> + CHF 1.99M setup</td><td>Working offer. Separate setup cash from recurring MRR.</td></tr>
<tr><td><b>1.4 City Tech</b></td><td>100,000</td><td>1,000</td><td>CHF 80/mo</td><td><b>CHF 80,000 MRR</b></td><td>MODEL assumption.</td></tr>
<tr><td><b>1.7 Elon Wire</b></td><td>100,000</td><td>1,000</td><td>CHF 80/mo</td><td><b>CHF 80,000 MRR</b></td><td>MODEL assumption.</td></tr>
<tr><td><b>3.5a X Autopilot</b></td><td>50,000</td><td>500</td><td>CHF 990 setup + CHF 149/mo</td><td><b>CHF 74,500 MRR</b> + CHF 495,000 setup</td><td>Working offer. Setup and MRR shown separately.</td></tr>
<tr><td><b>3.2 Leadmine</b></td><td>50,000</td><td>500</td><td>CHF 490 setup + CHF 990/mo</td><td><b>CHF 495,000 MRR</b> + CHF 245,000 setup</td><td>Closest revenue asset; self-pay still the LIVE gate.</td></tr>
<tr><td><b>4.1 Swiss Websites</b></td><td>50,000</td><td>500</td><td>CHF 1,390 first 10 → CHF 1,790 target · one-time</td><td><b>CHF 695k–895k one-time</b></td><td><b>NOT MRR.</b> Current offer has no monthly fee; Kimi's CHF 80/mo row is intentionally corrected here.</td></tr>
<tr><td><b>RAW LINE-SUM</b></td><td><b>~2.95M</b></td><td><b>29,500</b></td><td>mixed</td><td><b>CHF 2.6685M recurring MRR</b> + ~CHF 3.425M–3.625M setup/one-time</td><td><b>DO NOT call this a portfolio forecast.</b> Overlaps + unvalidated assumptions remain.</td></tr>
</table></div>

<div class="card" style="margin-top:10px;border-left-color:#000">
  <b>THE USEFUL ARITHMETIC:</b> on the recurring rows, the raw 1% line-sum is 29,000 active customers producing CHF 2.6685M MRR, a modelled weighted ARPU of ~CHF 92/month. At that same mix, CHF 1M MRR needs about <b>10,900 active customers</b>, or about <b>37.5%</b> of the recurring 1% line-sum. The hard part is not the multiplication; it is proving the pools, avoiding overlap, acquiring customers legally and cheaply, retaining them, and keeping the ARPU real.
</div>
'''


def transform_decisions(content: str) -> str:
    if MARK in content:
        return content
    sep = re.search(r"(?m)^-{5,}\s*$", content)
    block = DECISION.rstrip() + "\n\n"
    if sep:
        return content[: sep.start()] + block + content[sep.start() :]
    return block + content


def transform_board(content: str) -> str:
    if MARK in content:
        return content

    # Place the initiative model directly after the existing Revenue & costs area,
    # before the next portfolio section. This keeps the money view together without
    # bloating the pinned target header.
    needles = ["Revenue &amp; costs", "Revenue & costs"]
    hit = -1
    for needle in needles:
        hit = content.find(needle)
        if hit >= 0:
            break
    if hit < 0:
        raise RuntimeError("Revenue & costs heading not found")

    next_h2 = content.find("<h2", hit + 1)
    if next_h2 < 0:
        raise RuntimeError("next section heading after Revenue & costs not found")

    changed = content[:next_h2] + "\n" + SECTION + "\n" + content[next_h2:]
    if MARK not in changed or "CHF 2.6685M" not in changed or "29,500" not in changed:
        raise RuntimeError("initiative revenue section verification failed")
    return changed


def main() -> None:
    # HARD RULE: read 02_ASSETS before any canon write and reuse the existing
    # canon writer instead of inventing a third mutation path.
    assets = core.latest("02_ASSETS")
    asset_text = str(assets.get("content", ""))
    reuse_hint = any(token in asset_text.lower() for token in ("canon", "board", "portfolio"))
    print("ASSETS_OK", assets.get("version"), assets.get("id"), "portfolio_reuse_hint=", reuse_hint)
    print("REUSE", "scripts/hq_extend_targets_2029_2030.py", "canon read/write/race/prune helper")

    v_decisions = core.write(
        "03_DECISIONS",
        transform_decisions,
        "Add corrected initiative-level revenue geometry and anti-double-counting rule",
    )
    v_board = core.write(
        "BOARD_HTML",
        transform_board,
        "Add initiative-level pool × 1% × price revenue model under Revenue & costs",
    )
    print("CANON_DONE", {"03_DECISIONS": v_decisions, "BOARD_HTML": v_board})

    status, bus = core.req(core.BUS)
    if status != 200 or not isinstance(bus, dict) or not bus.get("bus_cursor"):
        raise RuntimeError("bus cursor missing")
    recent = bus.get("recent", []) if isinstance(bus.get("recent", []), list) else []
    if not any(BUS_MARK in (item.get("what") or "") for item in recent if isinstance(item, dict)):
        ps, payload = core.req(core.BUS, {
            "team": "HQ_GPT",
            "project": "0 HQ",
            "type": "DONE",
            "what": f"{BUS_MARK} · Added corrected initiative-level money model under Revenue & costs. Raw 1% line-sum corrected to 29,500; 4.1 separated as one-time, not MRR; recurring line-sum CHF2.6685M MRR with overlap warnings. Canon: 03_DECISIONS v{v_decisions} · BOARD_HTML v{v_board}.",
            "next": "Keep 4.1 lock unchanged: first code merged to main / READY=100%, then pillar-3 queue and Leadmine self-pay.",
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
