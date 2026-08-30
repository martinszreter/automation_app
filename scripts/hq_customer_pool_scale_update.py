#!/usr/bin/env python3
import os, json, re, time, urllib.request as u

URL = os.environ['CANON_RW_URL']
UPDATED_BY = 'HQ_GPT'
DATE = '2026-08-30'
MARK = 'CUSTOMER POOL SCALE DOCTRINE 2026-08-30'

PROJECT_POOLS = {
    '0': ('n/a', '—', 'governance'),
    '1': ('100,000', '1,000', 'MODEL v1 · brands / agencies / creators / media buyers'),
    '2': ('2,000,000', '20,000', 'MODEL v1 · recurring short-form-video buyers'),
    '3': ('3,732,855', '37,329', 'SOURCE · Claude model reachable B2B market'),
    '4': ('28,000', '280', 'SOURCE/MODEL · ChamDigital base high-priority CH pool'),
    '5': ('10,000,000', '100,000', 'MODEL v1 · consumer / parent / family audience'),
    '6': ('2,000,000', '20,000', 'MODEL v1 · retail trader / investor audience'),
    '7': ('ALL ACTIVE', '—', 'multiplier lane · no standalone product'),
    '8': ('n/a', '—', 'internal red-team lane'),
}

# Initiative-specific overrides. Everything else inherits its project's pool.
INIT_OVERRIDES = {
    '3.5b': ('676,242', '6,762', 'SOURCE · restaurants: 1,127,070 TAM × 60% reachable'),
    '3.8': ('10,000,000', '100,000', 'MODEL v1 · consumer audience'),
    '4.1': ('28,000', '280', 'SOURCE/MODEL · ChamDigital base high-priority CH pool'),
}

def req(payload):
    r = u.urlopen(u.Request(URL, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}), timeout=60)
    raw = r.read().decode()
    return json.loads(raw) if raw.strip() else None

def read_rows(key):
    rows = req({'action':'read','keyValue':key})
    if not rows:
        raise RuntimeError(f'EMPTY canon read for {key}; STOP')
    return sorted(rows, key=lambda x:int(x.get('version',0)), reverse=True)

def latest(key):
    return read_rows(key)[0]

def delete_row(row_id):
    req({'action':'delete','id':str(row_id)})

def prune(key):
    rows = read_rows(key)
    for r in rows[3:]:
        delete_row(r['id'])
    kept = [(int(r['version']), r['id']) for r in read_rows(key)[:3]]
    print('PRUNE', key, kept)

def insert(key, version, content, note):
    return req({'action':'insert','file':key,'version':version,'content':content,'note':note,'updated_by':UPDATED_BY})

def write_with_race_repair(key, transform, note):
    # Mandatory immediate re-read before write.
    base = latest(key)
    v = int(base['version']) + 1
    new_content = transform(base['content'])
    insert(key, v, new_content, note)
    rows = read_rows(key)  # Mandatory immediate re-read after write.
    same = [r for r in rows if int(r['version']) == v]
    if len(same) > 1:
        print('RACE', key, 'version', v, 'rows', [(r['id'],r.get('updated_by')) for r in same])
        ours = [r for r in same if r.get('updated_by') == UPDATED_BY and MARK in r.get('content','')]
        others = [r for r in same if r not in ours]
        if not others:
            raise RuntimeError(f'Race on {key} but cannot identify other writer row')
        other = others[0]
        rows2 = read_rows(key)
        v2 = max(int(r['version']) for r in rows2) + 1
        repaired = transform(other['content'])
        insert(key, v2, repaired, note + ' · race repair')
        for r in ours:
            delete_row(r['id'])
        rows3 = read_rows(key)
        if len([r for r in rows3 if int(r['version']) == v2]) > 1:
            raise RuntimeError(f'Second race on {key} version {v2}; STOP')
        v = v2
    prune(key)
    top = latest(key)
    if int(top['version']) != v or MARK not in top.get('content',''):
        raise RuntimeError(f'Post-write verification failed for {key}: top v{top.get("version")} expected {v}')
    print('WRITE_OK', key, 'v', v, 'id', top['id'], 'len', len(top['content']))
    return v

def doctrine_md(title):
    return f'''## {MARK} — {title}\n\nFOUNDER TARGETS — these supersede prior Dec-2026 / Dec-2027 revenue milestones wherever they conflict:\n- **BEAR FLOOR: CHF 10,000/day portfolio revenue run-rate by 31 Dec 2026** (~CHF 300,000/month using the 30-day operating convention; ~CHF 3.65M annual run-rate).\n- **2027 TARGET: CHF 1,000,000/month portfolio revenue by 31 Dec 2027** (CHF 12M ARR run-rate).\n- Targets are operating targets, not forecasts or guarantees. Near-term first-payment / Sep-2026 proof gates remain useful, but they do not replace these floors.\n\nCUSTOMER POOL RULE — mandatory for every commercial initiative:\n1. **Customers Pool** = realistically targetable prospects reachable through lawful outbound, owned distribution, referrals, partnerships and/or paid acquisition. It is NOT theoretical TAM.\n2. **1% Sales Pool** = 1% of Customers Pool. It is a scale benchmark / stress scenario, NOT a forecast.\n3. Products sharing the same buyers inherit one shared pool until initiative-specific evidence justifies a tighter number; overlapping products do not create extra humans.\n4. Any pool marked MODEL v1 is an explicit hypothesis to benchmark and replace with measured data.\n\nPROJECT BENCHMARKS v1:\n| Project | Customers Pool | 1% Sales Pool | Basis |\n|---|---:|---:|---|\n| 1 X.COM | 100,000 | 1,000 | MODEL v1 — brand / agency / creator / media buyers |\n| 2 GROKYWOOD | 2,000,000 | 20,000 | MODEL v1 — creators + SMEs with recurring short-form-video demand |\n| 3 NHT APPS | 3,732,855 | 37,329 | SOURCE — attached Claude model: 6,221,425 TAM × 60% reachable |\n| 4 SERVICES / ChamDigital | 28,000 | 280 | SOURCE/MODEL — base high-priority Swiss pool; 12k conservative / 28k base / 55k aggressive |\n| 5 MOBILE APPS | 10,000,000 | 100,000 | MODEL v1 — target-market consumer / parent / family audience |\n| 6 TRADING | 2,000,000 | 20,000 | MODEL v1 — reachable retail trader / investor audience; paper-only gates unchanged |\n| 7 SALES & MARKETING | ALL ACTIVE POOLS | — | multiplier lane, no standalone customer pool |\n| 8 SECURITY & STRESS | n/a | — | internal red-team lane, not a commercial product |\n\nINITIATIVE OVERRIDE ALREADY GROUNDED: **3.5b Restaurant = 676,242 reachable restaurants → 6,762 at 1%**, from the attached Claude model (1,127,070 restaurant TAM × 60% reachable).\n\nEXPONENTIAL BUILD RULE: build only paths that can scale self-serve and/or become a sellable startup asset, with marginal human labour approaching zero as sales scale. DFY/manual delivery is a validation wedge, never the destination. Upfront engineering and product quality are justified when they remove recurring manual work and improve conversion. For 4.1 ChamDigital the 95% gate means one excellent reusable multilingual factory and automated preview → checkout → edit → publish flow — never bespoke polishing per customer. Before BUILD, every new commercial initiative must state pool, 1% pool, acquisition path, price/ARPU and automation path, and show that scale matters against the portfolio floors.\n'''

def transform_strategy(content):
    if MARK in content:
        return content
    return doctrine_md('PORTFOLIO REVENUE + EXPONENTIAL SCALE') + '\n\n' + content

def transform_initiatives(content):
    if MARK in content:
        return content
    return doctrine_md('TRACKER-WIDE SCALE GATE') + '\n\n' + content

def transform_decisions(content):
    if MARK in content:
        return content
    block = f'''{DATE} | HQ / ALL COMMERCIAL INITIATIVES | FOUNDER DECISION | {MARK}. Every commercial initiative must carry Customers Pool = realistically targetable prospects and 1% Sales Pool = 1% benchmark, not forecast. Shared buyers use one shared pool until initiative evidence refines it. Portfolio operating floors supersede older conflicting milestones: BEAR FLOOR CHF 10,000/day revenue run-rate by 31 Dec 2026 (~CHF 300k/mo); TARGET CHF 1,000,000/mo by 31 Dec 2027. Build only exponential/self-serve or sellable-asset paths; DFY is a wedge. Upfront 95% reusable factory quality is correct when it removes recurring human labour and increases conversion; bespoke polish is not. Baselines: P1 100k/1k MODEL v1; P2 2m/20k MODEL v1; P3 3,732,855/37,329 from attached Claude model; P4 ChamDigital 28k/280 base; P5 10m/100k MODEL v1; P6 2m/20k MODEL v1; 3.5b restaurant override 676,242/6,762 from Claude model. Benchmark and replace MODEL v1 with measured data. Artifact: martinszreter/automation_app artifacts/HQ_CUSTOMER_POOL_SCALE_2026-08-30.md.\n\nupdated_by=HQ_GPT'''
    return block + '\n\n-----\n' + content

def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s).replace('&nbsp;',' ').strip()

def pool_for_project(pid):
    return PROJECT_POOLS.get(pid, ('TBD','—','MODEL v1 pending'))

def project_pool_cell(pid):
    p, one, basis = pool_for_project(pid)
    return (f'<td class="prod" style="text-align:center"><b>{p}</b><br><span class="dim">{basis}</span></td>',
            f'<td class="prod" style="text-align:center"><b>{one}</b><br><span class="dim">benchmark</span></td>')

def patch_project_table(content):
    marker = '<h2><span class="k">Who thinks, who executes, per project</span>Project split across the AI teams</h2>'
    s = content.find(marker)
    if s < 0: raise RuntimeError('Project split marker not found')
    e = content.find('<div class="card"><b>How Marcin works with them</b>', s)
    if e < 0: raise RuntimeError('Project split end marker not found')
    section = content[s:e]
    # Idempotency: if already patched, just return.
    if 'CUSTOMERS<br>POOL' in section and '1% SALES<br>POOL' in section:
        return content
    section = re.sub(r'<table style="min-width:[^"]+">', '<table style="min-width:1520px">', section, count=1)
    section = re.sub(r'<colgroup>.*?</colgroup>', '<colgroup><col style="width:38px"><col style="width:140px"><col style="width:240px"><col style="width:150px"><col style="width:120px"><col style="width:130px"><col style="width:155px"><col style="width:170px"></colgroup>', section, count=1, flags=re.S)
    section = section.replace('<tr><th>#</th><th>PROJECT</th><th>PRODUCTS</th><th>THINKS</th><th>EXECUTES</th><th>REVENUE</th></tr>', '<tr><th>#</th><th>PROJECT</th><th>PRODUCTS</th><th>CUSTOMERS<br>POOL</th><th>1% SALES<br>POOL</th><th>THINKS</th><th>EXECUTES</th><th>REVENUE</th></tr>')
    section = section.replace('colspan="6"', 'colspan="8"')
    def row_repl(m):
        row = m.group(0)
        cells = re.findall(r'<td(?:\s[^>]*)?>.*?</td>', row, flags=re.S)
        if len(cells) != 6:
            return row
        pid = strip_tags(cells[0])
        if pid not in PROJECT_POOLS:
            return row
        a,b = project_pool_cell(pid)
        return '<tr>' + ''.join(cells[:3] + [a,b] + cells[3:]) + '</tr>'
    section = re.sub(r'<tr><td class="v">.*?</tr>', row_repl, section, flags=re.S)
    # Non-project infrastructure rows: insert n/a cells so table remains aligned.
    def infra_repl(label, sec):
        patt = rf'<tr><td class="v">&mdash;</td><td>{re.escape(label)}</td>(.*?)</tr>'
        mm = re.search(patt, sec, flags=re.S)
        if not mm: return sec
        row = mm.group(0)
        cells = re.findall(r'<td(?:\s[^>]*)?>.*?</td>', row, flags=re.S)
        if len(cells)==6:
            a='<td class="prod" style="text-align:center"><span class="dim">n/a</span></td>'
            b='<td class="prod" style="text-align:center"><span class="dim">—</span></td>'
            nr='<tr>'+''.join(cells[:3]+[a,b]+cells[3:])+'</tr>'
            sec=sec.replace(row,nr,1)
        return sec
    section = infra_repl('CLAUDE BACKGROUND', section)
    section = infra_repl('RESERVE POOL', section)
    card = '''<div class="card" style="border-left-color:#DA291C"><b>CUSTOMER POOL SCALE RULE</b> &mdash; <b>Customers Pool</b> means realistically targetable prospects, not theoretical TAM. <b>1% Sales Pool</b> is a benchmark scenario, not a forecast. Source-backed today: NHT = 3,732,855 reachable businesses from the attached Claude model; 3.5b restaurants = 676,242; ChamDigital base = 28,000. Everything marked MODEL v1 is an explicit hypothesis to benchmark and replace with measured data. Products sharing the same buyers inherit one pool rather than double-counting people. <b>Portfolio floors: CHF 10k/day by 31 Dec 2026; CHF 1M/mo by 31 Dec 2027.</b></div>\n'''
    return content[:s] + section + card + content[e:]

def initiative_project(iid):
    if iid == '3.5c' or iid.startswith('2'):
        return '2'
    if iid.startswith('1'):
        return '1'
    if iid.startswith('3'):
        return '3'
    if iid.startswith('4'):
        return '4'
    if iid.startswith('5'):
        return '5'
    if iid.startswith('6'):
        return '6'
    if iid.startswith('7'):
        return '7'
    if iid.startswith('8'):
        return '8'
    return None

def initiative_pool(iid):
    if iid in INIT_OVERRIDES:
        return INIT_OVERRIDES[iid]
    p = initiative_project(iid)
    if p and p in PROJECT_POOLS:
        return PROJECT_POOLS[p]
    return ('TBD','—','MODEL v1 pending')

def patch_main_portfolio(content):
    marker = '<h2><span class="k">Sorted by how big this can get, not by pillar &middot; column titles repeat in every tier</span>The portfolio</h2>'
    s = content.find(marker)
    if s < 0: raise RuntimeError('Main portfolio marker not found')
    # Find next h2 after current section.
    e = content.find('<h2', s + len(marker))
    if e < 0: e = len(content)
    section = content[s:e]
    if 'CUSTOMERS<br>POOL' in section and '1% SALES<br>POOL' in section:
        return content
    section = section.replace('<table class="main" style="min-width:1620px">', '<table class="main" style="min-width:1920px">', 1)
    old_col = '<colgroup><col style="width:52px"><col style="width:250px"><col style="width:132px"><col style="width:118px"><col style="width:46px"><col style="width:64px"><col style="width:118px"><col style="width:112px"><col style="width:112px"><col style="width:250px"><col></colgroup>'
    new_col = '<colgroup><col style="width:52px"><col style="width:250px"><col style="width:132px"><col style="width:118px"><col style="width:60px"><col style="width:125px"><col style="width:105px"><col style="width:64px"><col style="width:118px"><col style="width:112px"><col style="width:112px"><col style="width:250px"><col></colgroup>'
    section = section.replace(old_col, new_col, 1)
    old_h = '<tr><th>#</th><th>STREAM</th><th>DOMAIN</th><th>PRICE</th><th>CUST</th><th>TODAY CHF</th><th>CHANNEL / ADVERT</th><th>STAGE</th><th>READY %</th><th>STATUS</th><th>NEXT</th></tr>'
    new_h = '<tr><th>#</th><th>STREAM</th><th>DOMAIN</th><th>PRICE</th><th>CUST</th><th>CUSTOMERS<br>POOL</th><th>1% SALES<br>POOL</th><th>TODAY CHF</th><th>CHANNEL / ADVERT</th><th>STAGE</th><th>READY %</th><th>STATUS</th><th>NEXT</th></tr>'
    section = section.replace(old_h, new_h)
    section = section.replace('colspan="11"', 'colspan="13"')
    def row_repl(m):
        row = m.group(0)
        cells = re.findall(r'<td(?:\s[^>]*)?>.*?</td>', row, flags=re.S)
        if len(cells) != 11:
            return row
        iid = strip_tags(cells[0])
        pool, one, basis = initiative_pool(iid)
        a = f'<td class="prod" style="text-align:center"><b>{pool}</b><br><span class="dim">{basis}</span></td>'
        b = f'<td class="prod" style="text-align:center"><b>{one}</b><br><span class="dim">benchmark</span></td>'
        return '<tr>' + ''.join(cells[:5] + [a,b] + cells[5:]) + '</tr>'
    section = re.sub(r'<tr><td class="id">.*?</tr>', row_repl, section, flags=re.S)
    return content[:s] + section + content[e:]

def new_ladder():
    return '''<h2><span class="k">Operating floors &middot; target, not forecast</span>Revenue ladder</h2>
<div class="dark"><div class="label" style="color:#9A968D;margin-bottom:14px">Every commercial initiative must have enough pool + automation to matter against these portfolio numbers</div><div style="display:flex;flex-wrap:wrap;gap:10px">
<div style="flex:1 1 175px;background:#2A0E0C;border-radius:4px;padding:16px;border-left:5px solid #DA291C"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#DA291C">TODAY</div><div class="display" style="font-size:36px;line-height:1.02;color:#fff;margin-top:6px">CHF 0</div><div style="font-size:12px;font-weight:700;color:#DA291C;margin-top:8px">stranger revenue · prove payment first</div></div>
<div style="flex:1 1 175px;background:#131317;border-radius:4px;padding:16px;border-left:5px solid #DA291C"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#5f5c56">PROOF RUNG</div><div class="display" style="font-size:36px;line-height:1.02;color:#fff;margin-top:6px">CHF 10k</div><div class="display" style="font-size:24px;line-height:1.1;color:#DA291C;margin-top:10px">30 SEP 2026</div><div style="font-size:12px;color:#9A968D;margin-top:5px">first collected-revenue proof</div></div>
<div style="flex:1 1 195px;background:#131317;border-radius:4px;padding:16px;border-left:5px solid #DA291C"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#DA291C">BEAR FLOOR</div><div class="display" style="font-size:34px;line-height:1.02;color:#fff;margin-top:6px">CHF 10k<span style="font-size:19px">/day</span></div><div class="display" style="font-size:24px;line-height:1.1;color:#DA291C;margin-top:10px">31 DEC 2026</div><div style="font-size:12px;color:#9A968D;margin-top:5px">~CHF 300k/mo · ~CHF 3.65M annual run-rate</div></div>
<div style="flex:1 1 195px;background:#131317;border-radius:4px;padding:16px;border-left:5px solid #ECE8DF"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#ECE8DF">2027 TARGET</div><div class="display" style="font-size:34px;line-height:1.02;color:#fff;margin-top:6px">CHF 1M<span style="font-size:19px">/mo</span></div><div class="display" style="font-size:24px;line-height:1.1;color:#ECE8DF;margin-top:10px">31 DEC 2027</div><div style="font-size:12px;color:#9A968D;margin-top:5px">CHF 12M ARR run-rate</div></div>
<div style="flex:1 1 175px;background:#131317;border-radius:4px;padding:16px;border-left:5px solid #ECE8DF"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#5f5c56">RUNG 4</div><div class="display" style="font-size:34px;line-height:1.02;color:#fff;margin-top:6px">CHF 10M<span style="font-size:19px">/mo</span></div><div class="display" style="font-size:24px;line-height:1.1;color:#ECE8DF;margin-top:10px">2029</div></div>
<div style="flex:1 1 175px;background:#131317;border-radius:4px;padding:16px;border-left:5px solid #ECE8DF"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#5f5c56">RUNG 5</div><div class="display" style="font-size:34px;line-height:1.02;color:#fff;margin-top:6px">CHF 100M<span style="font-size:19px">/mo</span></div><div class="display" style="font-size:24px;line-height:1.1;color:#ECE8DF;margin-top:10px">2030</div></div>
</div><div style="font-size:13px;color:#ECE8DF;margin-top:16px;border-top:1px solid #2E2E36;padding-top:12px"><b style="color:#DA291C">Scale doctrine:</b> pool × conversion × ARPU must be visible before BUILD. 1% Sales Pool is the common benchmark. The business wins by reusable factories, self-serve checkout and near-zero marginal human work — not by multiplying bespoke labour.</div></div>
'''

def patch_ladder(content):
    start = '<h2><span class="k">Two things matter here: the money and the date</span>Revenue ladder</h2>'
    end = '<h2><span class="k">The logic, and who we are measuring against</span>Distribution &amp; the idols</h2>'
    s = content.find(start)
    e = content.find(end, s if s>=0 else 0)
    if s < 0 or e < 0:
        # Already replaced?
        if 'BEAR FLOOR' in content and 'CHF 10k<span style="font-size:19px">/day' in content:
            return content
        raise RuntimeError('Revenue ladder markers not found')
    return content[:s] + new_ladder() + content[e:]

def transform_board(content):
    out = patch_project_table(content)
    out = patch_main_portfolio(out)
    out = patch_ladder(out)
    # Keep the marker in HTML for race identification and future idempotency.
    if MARK not in out:
        out = out.replace('<body><div class="wrap">', '<body><div class="wrap"><!-- '+MARK+' -->', 1)
    # Update only the visible hardcoded date/map label if the exact stale phrase exists.
    out = out.replace('Hardcoded 29 Aug 2026 &middot; ownership map v4', 'Hardcoded 30 Aug 2026 &middot; ownership map v5')
    return out

def main():
    # Asset check required before build. This script is itself reuse of canon/board pipe; still verify latest asset row exists.
    assets = latest('02_ASSETS')
    print('ASSETS_OK', assets['version'], assets['id'], 'len', len(assets['content']))
    vers = {}
    vers['01_STRATEGY'] = write_with_race_repair('01_STRATEGY', transform_strategy, 'Founder scale floors + Customers Pool doctrine + exponential build rule')
    vers['00_INITIATIVES'] = write_with_race_repair('00_INITIATIVES', transform_initiatives, 'Tracker-wide Customers Pool + 1% Sales Pool gate; new 2026/2027 floors')
    vers['03_DECISIONS'] = write_with_race_repair('03_DECISIONS', transform_decisions, 'Founder decision: 10k/day Dec-2026; 1M/mo Dec-2027; mandatory pool math')
    vers['BOARD_HTML'] = write_with_race_repair('BOARD_HTML', transform_board, 'Add Customers Pool + 1% Sales Pool columns project + initiative tables; replace revenue ladder')
    print('DONE', vers)

if __name__ == '__main__':
    main()
