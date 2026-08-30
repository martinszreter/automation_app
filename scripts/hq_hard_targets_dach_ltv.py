#!/usr/bin/env python3
import os,json,re,html as H,urllib.request as u

CANON=os.environ['CANON_RW_URL']
BUS='https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k'
REDEPLOY='https://startend.app.n8n.cloud/webhook/redeploy-portfolio-7k4q9x'
BOARD='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'
WHO='HQ_GPT'
MARK='HARD TARGETS + DACH LIFETIME + CRITICAL MODE 2026-08-30'
BUS_MARK='HQ_GPT_HARD_TARGETS_DACH_LTV_DONE'


def request(url,payload=None):
    if payload is None:
        with u.urlopen(url,timeout=45) as r:
            raw=r.read().decode(); return r.status, json.loads(raw) if raw.strip().startswith(('{','[')) else raw
    q=u.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with u.urlopen(q,timeout=45) as r:
        raw=r.read().decode(); return r.status, json.loads(raw) if raw.strip().startswith(('{','[')) else raw

def rows(key):
    s,x=request(CANON,{'action':'read','keyValue':key})
    if s!=200 or not isinstance(x,list) or not x:
        raise RuntimeError(f'EMPTY canon read {key}: {s} {x!r}')
    return sorted(x,key=lambda r:int(r['version']),reverse=True)

def latest(key): return rows(key)[0]
def delete(row_id): request(CANON,{'action':'delete','id':str(row_id)})
def insert(key,v,c,note):
    s,x=request(CANON,{'action':'insert','file':key,'version':v,'content':c,'note':note,'updated_by':WHO})
    if s!=200: raise RuntimeError(f'insert failed {key}: {s} {x!r}')
    return x

def prune(key):
    rr=rows(key)
    for r in rr[3:]: delete(r['id'])
    print('PRUNE',key,[(int(r['version']),r['id']) for r in rows(key)])

def write(key,fn,note):
    # Mandatory fresh read immediately before write.
    base=latest(key)
    new=fn(base['content'])
    if new==base['content']:
        print('NOOP',key,'v',base['version'])
        return int(base['version'])
    v=int(base['version'])+1
    res=insert(key,v,new,note)
    # Mandatory fresh read immediately after write.
    rr=rows(key); same=[r for r in rr if int(r['version'])==v]
    if len(same)>1:
        own_id=res.get('id') if isinstance(res,dict) else None
        ours=[r for r in same if str(r.get('id'))==str(own_id)]
        other=next((r for r in same if str(r.get('id'))!=str(own_id)),None)
        if other is None: raise RuntimeError('race cannot identify other '+key)
        v2=max(int(r['version']) for r in rr)+1
        merged=fn(other['content'])
        insert(key,v2,merged,note+' · race repair')
        for r in ours: delete(r['id'])
        if len([r for r in rows(key) if int(r['version'])==v2])>1:
            raise RuntimeError('second race '+key)
        v=v2
    prune(key)
    top=latest(key)
    if int(top['version'])!=v or MARK not in top['content']:
        raise RuntimeError(f'post-write verify failed {key}: v{top.get("version")} expected {v}')
    print('WRITE_OK',key,'v',v,'id',top['id'],'len',len(top['content']))
    return v

DOCTRINE=f'''## {MARK}\n\n### HARD REVENUE TARGETS — TARGETS, NOT FORECASTS\nThese supersede every older conflicting Dec-2026/2027/2028 revenue milestone. The anti-gaming metric is **daily revenue = trailing-30-day COLLECTED portfolio revenue / 30**. Pipeline, signed-but-unpaid contracts and one exceptional invoice do not count as daily run-rate.\n\n- **31 Dec 2026 — CHF 10,000/day** = CHF 300,000 collected per trailing 30 days (~CHF 3.65M annualised run-rate).\n- **31 Dec 2027 — CHF 100,000/day** = CHF 3,000,000 collected per trailing 30 days (~CHF 36.5M annualised run-rate).\n- **31 Dec 2028 — CHF 1,000,000/day** = CHF 30,000,000 collected per trailing 30 days (~CHF 365M annualised run-rate).\n\nThis is a deliberate **10x/year forcing staircase**, not a claim that the current portfolio is on pace. From near-zero revenue, especially the 2026 rung is operationally extreme. Every report must show the gap rather than soften the target.\n\n### CRITICAL / STRESS-TEST MODE — PERMANENT\nAll STARTEND brains must be positive but critical. Never agree by default. For important strategy, pricing, market-size, product, distribution and scaling claims: challenge the assumptions; distinguish observation / model / target / forecast; expose missing evidence; test acquisition cost, conversion, fulfilment capacity, legality, retention, unit economics and founder/human bottlenecks. If a target is mathematically possible but operationally unsupported, say so. No motivational arithmetic presented as evidence.\n\n### EXPONENTIAL-ONLY GATE\nA commercial path is strategically acceptable only if 10x customers can be served without approximately 10x human labour. Prefer self-serve, config/data-row expansion, reusable templates, automated fulfilment, recurring revenue and reusable distribution/data assets. DFY/manual work is allowed as a validation wedge, not the destination. High upfront product quality is justified when it removes recurring labour or materially raises conversion; bespoke polish per customer is not.\n\n### DACH LAND → EXPAND THESIS — CH / AT / DE\nFor 4.1 ChamDigital, the website is **Door #1**, not the lifetime business. Prospecting and serving creates a DACH SME relationship/data asset: company, domain, category, location, public site diagnostics, stack, observed problems, generated preview, interactions, purchases, support history and product-fit signals. **Permission/legal basis is a separate state.** Researching a business once does not create permission to market forever; opt-out, retention and country-specific outreach rules remain binding.\n\nThe primary compounding asset is the **installed paying base**. Land with a high-value website/domain upgrade, then expand only into products that repeated customer evidence supports. Existing STARTEND assets must be reused before creating duplicates. Candidate ladder:\n1. website + domain / digital identity (Door #1, one-off wedge);\n2. care / hosting / updates / backups / security monitoring;\n3. Google Business Profile / reviews / local SEO;\n4. lead capture / booking / WhatsApp / forms — reuse 3.5b patterns where applicable;\n5. CRM / lead follow-up / pipeline automation;\n6. AI receptionist / FAQ / chat / voice — reuse Custom AI Agents patterns;\n7. content / social automation — reuse X Autopilot / Grokywood assets where fit exists;\n8. conversion landing pages / paid acquisition only after conversion proof;\n9. analytics / reputation / reporting;\n10. custom integrations, e-commerce/payments and ad-hoc automations when installed-base demand repeats.\n\n**NO PRODUCT ZOO:** this is a monetisation map, not a build backlog. Do not build ten add-ons now. Start with Door #1, record demand, then productise repeated requests. The founder intuition that ~95% of value should come after the first website is a **stretch thesis to validate, not an assumption**. First objective: prove that a majority of cohort LTV can come after Door #1, then raise the target from measured attach/retention data. Track second-product attach rate, recurring ARPU, gross retention, expansion revenue and LTV/CAC.\n'''

def strategy(c):
    if MARK in c: return c
    return DOCTRINE+'\n\n'+c

def initiatives(c):
    if MARK in c: return c
    block=f'''## {MARK} — TRACKER GATE\n\nAll commercial initiatives inherit the hard target ladder and critical-mode rule from 01_STRATEGY. Before BUILD/scale they must show a realistic customer pool, 1% benchmark, acquisition path, price/ARPU, recurring/expansion path and a credible route to 10x volume without 10x human labour. 4.1 ChamDigital is Door #1 of a DACH land→expand system; add-ons are validated from repeated installed-base demand, not pre-built as a product zoo. The “95% after Door #1” concept is a stretch LTV thesis until cohort evidence proves it.\n\n'''
    title='# 00_INITIATIVES — canonical tracker data\n\n'
    return title+block+c[len(title):] if c.startswith(title) else block+c

def decisions(c):
    if MARK in c: return c
    block=f'''2026-08-30 | HQ / ALL INITIATIVES | FOUNDER DECISION | {MARK}. HARD TARGETS supersede every older conflicting revenue milestone: CHF 10,000/day by 31 Dec 2026; CHF 100,000/day by 31 Dec 2027; CHF 1,000,000/day by 31 Dec 2028. Daily revenue is trailing-30-day COLLECTED portfolio revenue / 30; pipeline and one-off spikes cannot game the metric. Targets are forcing targets, not forecasts. Permanent CRITICAL MODE: all brains must stress-test important founder/agent assumptions and clearly separate facts, models, targets and forecasts; never agree by default. EXPONENTIAL-ONLY GATE: 10x customers must not require ~10x human labour. 4.1 / DACH doctrine: website/domain is Door #1; build a lawful CH/AT/DE SME relationship graph and maximise installed-base expansion over time using existing STARTEND assets first. Prospect research does not equal perpetual marketing permission. Candidate post-door lanes: care/security, local SEO/reviews, booking/WhatsApp, CRM/follow-up, AI receptionist/agents, content automation, conversion/ads after proof, analytics/reputation, custom integrations/e-commerce. This is a monetisation map, NOT a build backlog; productise only repeated demand. “95% of value after website” is a stretch thesis to validate with cohort attach, recurring ARPU, retention, expansion and LTV/CAC — not a planning fact.\n\nupdated_by=HQ_GPT'''
    # Newest must be above the separator; prepend without rewriting historic lines.
    return block+'\n\n'+c

def text(cell):
    s=re.sub(r'<[^>]+>',' ',cell)
    return re.sub(r'\s+',' ',H.unescape(s)).strip()

def table_cells(row,tag='td'):
    return re.findall(rf'<{tag}\b[^>]*>.*?</{tag}>',row,re.I|re.S)

def header_map(table):
    for rm in re.finditer(r'<tr\b[^>]*>.*?</tr>',table,re.I|re.S):
        hs=table_cells(rm.group(0),'th')
        if not hs: continue
        labs=[text(x).upper() for x in hs]
        if 'PROJECT' in labs and any('1% SALES' in x for x in labs):
            return {lab:i for i,lab in enumerate(labs)},labs
    raise RuntimeError('project table header not found')

def idx_like(labs,needle):
    for i,x in enumerate(labs):
        if needle in x: return i
    raise RuntimeError('missing header '+needle)

def build_split_tables(table):
    _,labs=header_map(table)
    idx={
      '#':idx_like(labs,'#'), 'PROJECT':idx_like(labs,'PROJECT'), 'PRODUCTS':idx_like(labs,'PRODUCTS'),
      'THINKS':idx_like(labs,'THINKS'), 'EXECUTES':idx_like(labs,'EXECUTES'), 'REVENUE':idx_like(labs,'REVENUE'),
      'ONE':idx_like(labs,'1% SALES'), 'CH':idx_like(labs,'CH'), 'DE':idx_like(labs,'DE'),
      'PL':idx_like(labs,'PL'), 'ENG':idx_like(labs,'ENG')
    }
    econ_rows=[]; ai_rows=[]
    for rm in re.finditer(r'<tr\b[^>]*>.*?</tr>',table,re.I|re.S):
        row=rm.group(0); ds=table_cells(row,'td')
        if not ds: continue
        rid=text(ds[0])
        if rid not in {str(i) for i in range(9)}: continue
        if len(ds)<=max(idx.values()): continue
        pick=lambda k: ds[idx[k]]
        econ_rows.append('<tr>'+''.join(pick(k) for k in ['#','PROJECT','PRODUCTS','REVENUE','ONE','CH','DE','PL','ENG'])+'</tr>')
        ai_rows.append('<tr>'+''.join(pick(k) for k in ['#','PROJECT','THINKS','EXECUTES'])+'</tr>')
    if len(econ_rows)<9 or len(ai_rows)<9: raise RuntimeError(f'expected 9 project rows, got econ={len(econ_rows)} ai={len(ai_rows)}')
    econ='''<h2><span class="k">Revenue, conversion benchmark and reachable markets</span>Portfolio scale map</h2>
<div class="scroll"><table style="min-width:1260px"><colgroup><col style="width:34px"><col style="width:115px"><col style="width:250px"><col style="width:115px"><col style="width:105px"><col style="width:105px"><col style="width:120px"><col style="width:105px"><col style="width:120px"></colgroup>
<tr><th>#</th><th>PROJECT</th><th>PRODUCTS</th><th>REVENUE</th><th>1% SALES<br>POOL</th><th>CH</th><th>DE (+AT)</th><th>PL</th><th>ENG<br><span class="dim">US+UK+AU</span></th></tr>'''+''.join(econ_rows)+'''</table></div>
<div class="card" style="padding:10px 14px"><b>POOL NOTE:</b> geography cells are reachable-pool models where known; DE display currently folds Austria into the German-language bucket. 1% is a benchmark, not a forecast. Do not sum overlapping product pools as unique humans.</div>'''
    ai='''<h2><span class="k">Compact operating ownership — economics moved above</span>AI operating map</h2>
<div class="scroll"><table style="min-width:760px"><colgroup><col style="width:36px"><col style="width:180px"><col style="width:230px"><col style="width:310px"></colgroup>
<tr><th>#</th><th>PROJECT</th><th>THINKS</th><th>EXECUTES</th></tr>'''+''.join(ai_rows)+'''</table></div>'''
    return econ+'\n'+ai

def top_targets():
    return '''<!-- HARD_TARGETS_DACH_LTV_20260830 -->
<div class="card" style="padding:10px 12px;border-left:5px solid #DA291C;margin:8px 0 14px">
<div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-end;flex-wrap:wrap;margin-bottom:7px"><b style="font-size:13px;letter-spacing:.09em">HARD REVENUE TARGETS · EXPONENTIAL ONLY</b><span class="dim" style="font-size:10px">TARGETS ≠ FORECASTS · daily = trailing-30d collected ÷ 30</span></div>
<table style="width:100%;min-width:0"><tr><th>DEADLINE</th><th>DAILY</th><th>TRAILING 30D</th><th>ANNUALISED RUN-RATE</th></tr>
<tr><td><b>31 DEC 2026</b></td><td><b>CHF 10k/day</b></td><td>CHF 300k</td><td>CHF 3.65M</td></tr>
<tr><td><b>31 DEC 2027</b></td><td><b>CHF 100k/day</b></td><td>CHF 3M</td><td>CHF 36.5M</td></tr>
<tr><td><b>31 DEC 2028</b></td><td><b>CHF 1M/day</b></td><td>CHF 30M</td><td>CHF 365M</td></tr></table>
<div style="font-size:10.5px;margin-top:7px"><b>Gate:</b> 10× customers must not require ~10× human labour. Every AI brain must stress-test the path and show the gap; no yes-by-default.</div></div>'''

def dach_section():
    rows='''
<tr><td><b>1 · LAND</b></td><td>Website + domain / digital identity</td><td>Door #1 · one-off wedge</td><td>4.1 site-engine / ChamDigital</td></tr>
<tr><td><b>2 · RETAIN</b></td><td>Care, hosting, updates, backups, security monitoring</td><td>Recurring base</td><td>Productise only after first cohort</td></tr>
<tr><td><b>3 · DISCOVERY</b></td><td>Google Business Profile, reviews, local SEO</td><td>Recurring / performance</td><td>Build after repeated request</td></tr>
<tr><td><b>4 · LEADS</b></td><td>Forms, booking, WhatsApp, intake</td><td>Recurring</td><td>Reuse 3.5b patterns</td></tr>
<tr><td><b>5 · FOLLOW-UP</b></td><td>CRM, lead pipeline, reminders, follow-up automation</td><td>Recurring</td><td>Reuse existing automation stack</td></tr>
<tr><td><b>6 · AI FRONT DESK</b></td><td>AI receptionist, FAQ/chat/voice</td><td>Recurring / usage</td><td>Reuse 3.5d Custom Agents</td></tr>
<tr><td><b>7 · CONTENT</b></td><td>Social/content automation</td><td>Recurring</td><td>Reuse 3.5a / Grokywood where fit exists</td></tr>
<tr><td><b>8 · GROWTH</b></td><td>Conversion landing pages + paid acquisition</td><td>Retainer / performance</td><td>Only after conversion proof</td></tr>
<tr><td><b>9 · INSIGHT</b></td><td>Analytics, reputation, reporting</td><td>Recurring</td><td>Attach to installed base</td></tr>
<tr><td><b>10 · EXPAND</b></td><td>Custom integrations, e-commerce/payments, ad-hoc automation</td><td>Project + recurring</td><td>Only when demand repeats</td></tr>'''
    return '''<h2><span class="k">CH · AT · DE only · website is Door #1</span>DACH lifetime SME engine</h2>
<div class="card" style="border-left:5px solid #DA291C"><b>LAND ONCE → LEARN → EXPAND.</b> The costly output of prospecting is not just a website sale; it is a structured SME relationship graph. For every lawful prospect/customer record preserve useful business facts, site diagnostics, generated preview, interactions, product-fit signals and purchase/support history. <b>Marketing permission/legal basis/opt-out/retention stays separate.</b> A researched non-buyer is not permission to contact forever. The compounding monetisation priority is the paying installed base.</div>
<div class="scroll"><table style="min-width:1050px"><tr><th>STEP</th><th>PRODUCT / NEED</th><th>ECONOMIC ROLE</th><th>BUILD RULE</th></tr>'''+rows+'''</table></div>
<div class="card"><b>CRITICAL CHECK:</b> “95% after the website” is a useful stretch direction, but today it is <b>not evidence</b>. Do not pre-build this ladder. First prove Door #1, then measure second-product attach, recurring ARPU, gross retention, expansion revenue and LTV/CAC. Productise only repeated demand, reusing existing STARTEND assets before creating anything new. The near-term objective is to prove <b>majority of cohort LTV after Door #1</b>; 80–95% becomes a later target only if cohort data supports it.</div>'''

def patch_old_target_text(c):
    # Only normalize current operating-target prose; historic findings remain untouched unless they use these exact target phrases.
    reps={
      'CHF 1M/mo by 31 Dec 2027':'CHF 100k/day by 31 Dec 2027',
      'CHF 1M/month by 31 Dec 2027':'CHF 100k/day by 31 Dec 2027',
      'CHF 1,000,000/month by 31 Dec 2027':'CHF 100,000/day by 31 Dec 2027',
      'CHF 1M/mo by 31 DEC 2027':'CHF 100k/day by 31 DEC 2027',
      '2027 = 1M/month':'2027 = 100k/day',
      '2027 = CHF 1M/month':'2027 = CHF 100k/day',
    }
    for a,b in reps.items(): c=c.replace(a,b)
    return c

def board(c):
    if MARK in c and 'DACH lifetime SME engine' in c and 'CHF 1M/day' in c and 'Portfolio scale map' in c:
        return c
    c=patch_old_target_text(c)
    # Put the target strip at the first usable page-content boundary.
    t=top_targets()
    if 'HARD_TARGETS_DACH_LTV_20260830' not in c:
        anchor='<body><div class="wrap">'
        if anchor in c: c=c.replace(anchor,anchor+'\n'+t,1)
        else:
            m=re.search(r'<body[^>]*>',c,re.I)
            if not m: raise RuntimeError('body tag missing')
            c=c[:m.end()]+'\n'+t+c[m.end():]
    # Split the overloaded top project table into economics + operating ownership.
    h=re.search(r'<h2><span class="k">Who thinks, who executes, per project</span>Project split across the AI teams</h2>',c,re.I|re.S)
    if not h: raise RuntimeError('project split heading missing')
    tm=re.search(r'<div class="scroll"><table\b[^>]*>.*?</table></div>',c[h.end():],re.I|re.S)
    if not tm: raise RuntimeError('project split table missing')
    a=h.start(); b=h.end()+tm.end()
    c=c[:a]+build_split_tables(tm.group(0))+c[b:]
    # Replace the bulky duplicate revenue ladder with one concise stress card if present.
    rm=re.search(r'<h2><span class="k">[^<]*Target[^<]*</span>Revenue ladder</h2>',c,re.I|re.S)
    if rm:
        nx=c.find('<h2',rm.end())
        if nx>0:
            mini='<div class="card"><b>TARGET STRESS:</b> canonical ladder is pinned at the top. Report actual trailing-30d collected revenue against it. A 10× annual target is intentionally severe; if acquisition, delivery or support scales roughly linearly with people, the initiative fails the exponential gate.</div>\n'
            c=c[:rm.start()]+mini+c[nx:]
    # Insert DACH lifetime strategy near the detailed 4.1 section if possible; otherwise before the ranked portfolio.
    d=dach_section()
    if 'DACH lifetime SME engine' not in c:
        p=c.find('<h2><span class="k">Sorted by how big this can get')
        if p<0: p=c.find('</body>')
        if p<0: p=len(c)
        c=c[:p]+d+'\n'+c[p:]
    # Make the permanent marker explicit for post-write verification.
    c=c.replace('HARD_TARGETS_DACH_LTV_20260830 -->','HARD_TARGETS_DACH_LTV_20260830 -->\n<!-- '+MARK+' -->',1)
    checks=['CHF 10k/day','CHF 100k/day','CHF 1M/day','Portfolio scale map','AI operating map','DACH lifetime SME engine','no yes-by-default']
    missing=[x for x in checks if x not in c]
    if missing: raise RuntimeError('board transform missing '+repr(missing))
    return c

def has_true(x,key):
    if isinstance(x,dict):
        if x.get(key) is True: return True
        return any(has_true(v,key) for v in x.values())
    if isinstance(x,list): return any(has_true(v,key) for v in x)
    return False

def main():
    # Asset reuse gate before any portfolio mutation.
    asset=latest('02_ASSETS'); print('ASSETS_OK',asset['version'],asset['id'])
    versions={}
    versions['01_STRATEGY']=write('01_STRATEGY',strategy,'Hard 10x revenue targets + exponential gate + critical mode + DACH land-expand doctrine')
    versions['00_INITIATIVES']=write('00_INITIATIVES',initiatives,'Tracker-wide hard targets, critical mode and DACH installed-base expansion gate')
    versions['03_DECISIONS']=write('03_DECISIONS',decisions,'Founder hard targets 2026/27/28; critical stress-test mode; DACH lifetime thesis')
    versions['BOARD_HTML']=write('BOARD_HTML',board,'Pin hard targets at top; split scale/AI tables; add DACH lifetime SME engine')
    print('CANON_DONE',versions)
    # Bus guard prevents recursion on the official canon-backed redeploy.
    s,b=request(BUS)
    if s!=200 or not isinstance(b,dict) or not b.get('bus_cursor'): raise RuntimeError('bus cursor missing')
    if any(BUS_MARK in (x.get('what') or '') for x in b.get('recent',[])):
        print('GUARD bus DONE exists; skip duplicate bus/redeploy'); return
    what=(f'{BUS_MARK} · HQ_GPT hard-coded collected-revenue targets: CHF10k/day 2026, CHF100k/day 2027, CHF1M/day 2028; daily=trailing30d collected/30. '
          f'Permanent critical/stress-test + exponential-only rule saved. Project table split into compact scale map and AI operating map. DACH CH/AT/DE land→expand doctrine saved: website is Door #1, installed base is expansion asset, nonbuyer research != perpetual marketing permission. Canon versions '+json.dumps(versions,sort_keys=True))
    ps,p=request(BUS,{'team':'GPT_CURSOR','project':'0','type':'DONE','what':what,'next':'4.1 execution lock unchanged: finish stranger checkout + legal + Börlin hard gaps, re-score, self-pay, then SELL and begin measuring cohort attach/expansion.','link':BOARD,'bus_cursor':b['bus_cursor']})
    if ps!=200 or not isinstance(p,dict) or not p.get('accepted'): raise RuntimeError(f'bus failed {ps} {p!r}')
    print('BUS_DONE',p.get('id'))
    rs,r=request(REDEPLOY,{'who':WHO,'why':f'BOARD_HTML v{versions["BOARD_HTML"]} hard targets + compact tables + DACH lifetime'})
    if rs!=200 or not has_true(r,'serviceInstanceRedeploy'): raise RuntimeError(f'redeploy failed {rs} {r!r}')
    print('REDEPLOY_OK',r)

if __name__=='__main__': main()
