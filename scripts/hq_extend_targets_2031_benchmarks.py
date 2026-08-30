#!/usr/bin/env python3
"""Extend the HQ hard-revenue ladder to 2031 and add revenue-scale company anchors.

Reuses scripts/hq_extend_targets_2029_2030.py for the canon read/write/race/prune
protocol. This script is intentionally one-off and idempotent.
"""
from __future__ import annotations

import re
import hq_extend_targets_2029_2030 as core

MARK = "HARD TARGET LADDER 10X 2030/2031 + SCALE BENCHMARKS 2026-08-30"
BUS_MARK = "HQ_GPT_TARGETS_2031_BENCHMARKS_DONE"

# Reuse the existing canon writer but give this migration its own durable marker.
core.MARK = MARK

STRATEGY_BLOCK = f'''## {MARK}\n\nFounder-ratified portfolio forcing ladder; targets, not forecasts:\n- **31 Dec 2026 — CHF 10k/day** = CHF 300k trailing-30d = CHF 3.65M annualised.\n- **31 Dec 2027 — CHF 100k/day** = CHF 3M trailing-30d = CHF 36.5M annualised.\n- **31 Dec 2028 — CHF 1M/day** = CHF 30M trailing-30d = CHF 365M annualised.\n- **31 Dec 2029 — CHF 1B/year** ≈ CHF 2.74M/day = CHF 82.2M trailing-30d.\n- **31 Dec 2030 — CHF 10B/year** ≈ CHF 27.4M/day = CHF 822M trailing-30d.\n- **31 Dec 2031 — CHF 100B/year** ≈ CHF 274M/day = CHF 8.22B trailing-30d.\n\n2030 and 2031 intentionally force a 10× annual step: CHF 1B → CHF 10B → CHF 100B. The anti-gaming convention remains collected revenue.\n'''

TABLE_ROWS = '''
<tr><th>DEADLINE</th><th>DAILY</th><th>TRAILING 30D</th><th>ANNUALISED RUN-RATE</th><th>5 REVENUE-SCALE ANCHORS</th></tr>
<tr><td><b>31 DEC 2026</b></td><td><b>CHF 10k/day</b></td><td>CHF 300k</td><td>CHF 3.65M</td><td><b>Founder-led micro-SaaS scale:</b> Tally · Carrd · Photo AI · Senja · Bannerbear</td></tr>
<tr><td><b>31 DEC 2027</b></td><td><b>CHF 100k/day</b></td><td>CHF 3M</td><td>CHF 36.5M</td><td><b>Tens-of-millions scale:</b> Kit (ConvertKit) · beehiiv · Buffer · Ghost · 37signals</td></tr>
<tr><td><b>31 DEC 2028</b></td><td><b>CHF 1M/day</b></td><td>CHF 30M</td><td>CHF 365M</td><td><b>Hundreds-of-millions scale:</b> Fiverr · Coursera · PagerDuty · Sprout Social · Lemonade</td></tr>
<tr><td><b>31 DEC 2029</b></td><td><b>CHF 2.74M/day</b></td><td>CHF 82.2M</td><td><b>CHF 1B/year</b></td><td><b>Single-digit-billions scale:</b> HubSpot · Duolingo · GitLab · Klaviyo · monday.com</td></tr>
<tr><td><b>31 DEC 2030</b></td><td><b>CHF 27.4M/day</b></td><td>CHF 822M</td><td><b>CHF 10B/year</b></td><td><b>~CHF 10B scale:</b> Shopify · Airbnb · ServiceNow · Workday · Intuit</td></tr>
<tr><td><b>31 DEC 2031</b></td><td><b>CHF 274M/day</b></td><td>CHF 8.22B</td><td><b>CHF 100B/year</b></td><td><b>~CHF 100B scale:</b> Tesla · TSMC · Tencent · Disney · Alibaba</td></tr>
'''.strip()

NOTE = '''<div style="font-size:9.5px;margin-top:5px"><b>2029–2031 are annual targets:</b> CHF 1B/year → CHF 10B/year → CHF 100B/year. 2026–2028 remain daily run-rate targets. <b>Company names are illustrative order-of-magnitude scale anchors, not exact peers;</b> private-company figures can be estimates, reporting periods/currencies differ, and the list is for strategic scale context only. Targets ≠ forecasts.</div>'''


def strategy(content: str) -> str:
    if MARK in content:
        return content
    # Correct current strategy truth without rewriting the historical decisions log.
    content = content.replace("CHF 2,000,000,000/year", "CHF 10,000,000,000/year")
    content = content.replace("CHF 2B/year by 31 Dec 2030", "CHF 10B/year by 31 Dec 2030")
    content = content.replace("CHF 2B/year by Dec-2030", "CHF 10B/year by Dec-2030")
    content = content.replace("CHF 2B/year by Dec 2030", "CHF 10B/year by Dec 2030")
    return STRATEGY_BLOCK + "\n" + content


def decisions(content: str) -> str:
    if MARK in content:
        return content
    line = f'''2026-08-30 | HQ / ALL INITIATIVES | FOUNDER DECISION | {MARK}. Replace the 31 Dec 2030 hard target with **CHF 10B/year** and add **31 Dec 2031 — CHF 100B/year**, preserving the 10× annual forcing step after CHF 1B/year in 2029. Operating equivalents: 2030 ≈ CHF 27.4M/day / CHF 822M trailing-30d; 2031 ≈ CHF 274M/day / CHF 8.22B trailing-30d. Add a fifth hard-target-table column with five illustrative company scale anchors per row, including HubSpot around the single-digit-billions band and Shopify around the ~CHF 10B band. Benchmarks are order-of-magnitude context, not claims of exact revenue parity.\n\nupdated_by=HQ_GPT'''
    return line + "\n\n" + content


def board(content: str) -> str:
    marker = '<!-- HARD_TARGETS_DACH_LTV_20260830 -->'
    start = content.find(marker)
    if start < 0:
        raise RuntimeError("hard-target marker missing")

    t0 = content.find('<table', start)
    t1 = content.find('</table>', t0)
    if t0 < 0 or t1 < 0:
        raise RuntimeError("hard-target table missing")
    open_end = content.find('>', t0)
    if open_end < 0 or open_end > t1:
        raise RuntimeError("hard-target table opening tag malformed")
    opening = content[t0:open_end + 1]
    # Keep the existing compact table styling from the reused target asset.
    if 'font-size:10px' not in opening:
        if 'style="' in opening:
            opening = opening.replace('style="', 'style="font-size:10px;line-height:1.1;', 1)
        else:
            opening = opening[:-1] + ' style="font-size:10px;line-height:1.1">'

    colgroup = '<colgroup><col style="width:12%"><col style="width:12%"><col style="width:14%"><col style="width:16%"><col style="width:46%"></colgroup>'
    replacement = opening + colgroup + TABLE_ROWS + '</table>'
    content = content[:t0] + replacement + content[t1 + len('</table>'):]

    # Remove the previous 2029/2030 note and insert the new 2029–2031 note once.
    content = re.sub(
        r'<div[^>]*>\s*<b>2029/2030 are annual targets:</b>.*?</div>',
        '',
        content,
        count=1,
        flags=re.S,
    )
    new_t0 = content.find('<table', start)
    new_t1 = content.find('</table>', new_t0) + len('</table>')
    tail = content[new_t1:new_t1 + 1800]
    if '2029–2031 are annual targets' not in tail:
        content = content[:new_t1] + '\n' + NOTE + content[new_t1:]

    if MARK not in content:
        content = content.replace(marker, marker + '<!-- ' + MARK + ' -->', 1)

    checks = [
        '31 DEC 2030', 'CHF 10B/year', 'CHF 27.4M/day', 'CHF 822M',
        '31 DEC 2031', 'CHF 100B/year', 'CHF 274M/day', 'CHF 8.22B',
        '5 REVENUE-SCALE ANCHORS', 'Shopify', 'HubSpot', 'Tesla', MARK,
    ]
    missing = [item for item in checks if item not in content]
    if missing:
        raise RuntimeError('board checks missing ' + repr(missing))
    return content


def main() -> None:
    # Hard rule: inspect the canonical asset registry before touching canon.
    assets = core.latest('02_ASSETS')
    print('ASSETS_OK', assets['version'], assets['id'], 'reuse=scripts/hq_extend_targets_2029_2030.py')

    v1 = core.write('01_STRATEGY', strategy, 'Extend hard ladder to CHF10B/year 2030 and CHF100B/year 2031')
    v2 = core.write('03_DECISIONS', decisions, 'Founder target ladder: 10B/year 2030; 100B/year 2031; add scale anchors')
    v3 = core.write('BOARD_HTML', board, 'Update pinned hard-target table through 2031 and add five company scale anchors per row')
    print('CANON_DONE', {'01_STRATEGY': v1, '03_DECISIONS': v2, 'BOARD_HTML': v3})

    status, bus = core.req(core.BUS)
    if status != 200 or not isinstance(bus, dict) or not bus.get('bus_cursor'):
        raise RuntimeError('bus cursor missing')
    recent = bus.get('recent', []) if isinstance(bus.get('recent', []), list) else []
    if not any(BUS_MARK in (item.get('what') or '') for item in recent if isinstance(item, dict)):
        ps, payload = core.req(core.BUS, {
            'team': 'HQ_GPT',
            'project': '0 HQ',
            'type': 'DONE',
            'what': f'{BUS_MARK} · Hard ladder now CHF1B/year 2029 → CHF10B/year 2030 → CHF100B/year 2031. Added five illustrative revenue-scale company anchors to every target row. Canon: 01_STRATEGY v{v1} · 03_DECISIONS v{v2} · BOARD_HTML v{v3}.',
            'next': 'Keep 4.1 execution lock unchanged: merge first code to main, reach READY=100%, then Leadmine self-pay is portfolio-critical LIVE.',
            'link': core.BOARD,
            'bus_cursor': bus['bus_cursor'],
        })
        if ps != 200:
            raise RuntimeError(f'bus failed {ps} {payload!r}')
        print('BUS_DONE', payload)
    else:
        print('BUS_GUARD existing DONE found')


if __name__ == '__main__':
    main()
