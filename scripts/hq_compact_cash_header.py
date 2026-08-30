#!/usr/bin/env python3
import os, json, re, urllib.request as u

CANON=os.environ['CANON_RW_URL']
BUS='https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k'
REDEPLOY='https://startend.app.n8n.cloud/webhook/redeploy-portfolio-7k4q9x'
BOARD='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'
WHO='HQ_GPT'
MARK='STICKY REAL BRAND + SIMPLE CASH TABLE 2026-08-30'
BUS_MARK='HQ_GPT_STICKY_REAL_BRAND_SIMPLE_CASH_DONE'

REAL_BRAND='''<div class="brandline"><svg width="30" height="30" viewBox="0 0 64 64" aria-hidden="true" style="margin-right:10px"><path d="M16 0H64V48H48V64H0V16H16Z" fill="#DA291C"/><rect x="26" y="12" width="12" height="40" fill="#fff"/><rect x="12" y="26" width="40" height="12" fill="#fff"/></svg><span class="wordmark">startend<span>.ch</span></span><span class="hqtag">HQ &middot; portfolio</span></div>'''

TEXT_BRAND='''<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:-2px 0 6px"><div style="font-weight:900;font-size:15px;letter-spacing:.18em">STARTEND <span style="color:#DA291C">·</span> HQ</div><div class="dim" style="font-size:9px;letter-spacing:.08em">EXPONENTIAL ONLY</div></div>'''

STICKY_BRAND='''<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:-2px 0 6px"><div class="brandline" style="padding:0;border-bottom:0;margin:0"><svg width="30" height="30" viewBox="0 0 64 64" aria-hidden="true" style="margin-right:10px"><path d="M16 0H64V48H48V64H0V16H16Z" fill="#DA291C"/><rect x="26" y="12" width="12" height="40" fill="#fff"/><rect x="12" y="26" width="40" height="12" fill="#fff"/></svg><span class="wordmark">startend<span>.ch</span></span><span class="hqtag">HQ &middot; portfolio</span></div><div class="dim" style="font-size:9px;letter-spacing:.08em">EXPONENTIAL ONLY</div></div>'''

SIMPLE_CASH='''<h2 style="margin-top:4px"><span class="k">Collected revenue &middot; quantified costs only</span>Revenue &amp; costs</h2>
<table class="kpi"><colgroup><col style="width:19%"><col style="width:12%"><col style="width:16%"><col style="width:17%"><col style="width:36%"></colgroup>
<tr><th>FLOW</th><th>TODAY</th><th>PER MONTH</th><th>PER YEAR</th><th>COMMENTS</th></tr>
<tr><td class="lab">MONEY IN</td><td><span class="big red">CHF 0</span></td><td><span class="big red">CHF 0</span></td><td><span class="big red">CHF 0</span></td><td class="kn">0 stranger revenue collected yet.</td></tr>
<tr><td class="lab">MONEY OUT</td><td><span class="big dim">&mdash;</span></td><td><span class="big">USD 156</span></td><td><span class="big">USD 1,875</span></td><td class="kn">Known quantified costs: Grokywood USD 126/mo &middot; X.COM USD 30.28/mo. <b>Other active vendors remain unpriced, so the true run-rate is higher.</b></td></tr>
</table>'''


def req(url,p=None):
    if p is None:
        with u.urlopen(url,timeout=45) as r:
            raw=r.read().decode(); return r.status, json.loads(raw) if raw.strip().startswith(('{','[')) else raw
    q=u.Request(url,data=json.dumps(p).encode(),headers={'Content-Type':'application/json'})
    with u.urlopen(q,timeout=45) as r:
        raw=r.read().decode(); return r.status, json.loads(raw) if raw.strip().startswith(('{','[')) else raw


def rows(k):
    s,x=req(CANON,{'action':'read','keyValue':k})
    if s!=200 or not isinstance(x,list) or not x:
        raise RuntimeError(f'EMPTY canon read {k}: {s} {x!r}')
    return sorted(x,key=lambda r:int(r['version']),reverse=True)


def latest(k): return rows(k)[0]
def delete(i): req(CANON,{'action':'delete','id':str(i)})


def insert(k,v,c,n):
    s,x=req(CANON,{'action':'insert','file':k,'version':v,'content':c,'note':n,'updated_by':WHO})
    if s!=200: raise RuntimeError(f'insert failed {k}: {s} {x!r}')
    return x


def prune(k):
    rr=rows(k)
    for r in rr[3:]: delete(r['id'])
    print('PRUNE',k,[(int(r['version']),r['id']) for r in rows(k)])


def write(k,fn,note):
    # Canon protocol: re-read immediately before write.
    base=latest(k)
    new=fn(base['content'])
    if new==base['content']:
        print('NOOP',k,'v',base['version'])
        return int(base['version'])
    v=int(base['version'])+1
    res=insert(k,v,new,note)
    # Canon protocol: re-read immediately after write and repair races.
    rr=rows(k); same=[r for r in rr if int(r['version'])==v]
    if len(same)>1:
        own_id=res.get('id') if isinstance(res,dict) else None
        other=next((r for r in same if str(r.get('id'))!=str(own_id)),None)
        if other is None: raise RuntimeError('race cannot identify other '+k)
        v2=max(int(r['version']) for r in rr)+1
        insert(k,v2,fn(other['content']),note+' · race repair')
        if own_id: delete(own_id)
        if len([r for r in rows(k) if int(r['version'])==v2])>1:
            raise RuntimeError('second race '+k)
        v=v2
    prune(k)
    top=latest(k)
    if int(top['version'])!=v or MARK not in top['content']:
        raise RuntimeError(f'post-write verify {k}: top={top.get("version")} expected={v}')
    print('WRITE_OK',k,'v',v,'id',top['id'],'len',len(top['content']))
    return v


def decisions(c):
    if MARK in c: return c
    line=(f'''2026-08-30 | HQ BOARD | DECISION | {MARK}. Reuse the existing visual startend.ch + Swiss-cross wordmark as the sticky portfolio header; remove the duplicate lower brandline. Rename the old “The numbers” section to “Revenue & costs” and show only MONEY IN and MONEY OUT. MONEY OUT displays quantified known costs only; unpriced active vendors remain explicitly disclosed in the comment so USD 156/mo is never mistaken for total portfolio cost. NET is derived and removed from the display.\n\nupdated_by=HQ_GPT''')
    return line+'\n\n'+c


def board(c):
    if MARK in c and 'Revenue &amp; costs' in c and c.count('class="brandline"')==1:
        return c

    marker='<!-- HARD_TARGETS_DACH_LTV_20260830 -->'
    s=c.find(marker)
    if s<0: raise RuntimeError('hard target marker missing')

    # Remove the lower duplicate brand first, then reuse that exact component in the sticky card.
    if REAL_BRAND in c:
        c=c.replace(REAL_BRAND,'',1)
    if TEXT_BRAND in c:
        c=c.replace(TEXT_BRAND,STICKY_BRAND,1)
    elif STICKY_BRAND not in c:
        raise RuntimeError('sticky text brand not found and real sticky brand not present')

    # Replace the first cash KPI section only; keep the tiles immediately below unchanged.
    hp=c.find('<h2 style="margin-top:4px">',s)
    if hp<0: raise RuntimeError('cash heading start missing')
    h_end=c.find('</h2>',hp)
    if h_end<0: raise RuntimeError('cash heading end missing')
    heading=c[hp:h_end+5]
    if 'The numbers' not in heading and 'Revenue &amp; costs' not in heading:
        raise RuntimeError('unexpected cash heading: '+heading[:200])
    table_start=c.find('<table class="kpi">',h_end)
    table_end=c.find('</table>',table_start)
    if table_start<0 or table_end<0: raise RuntimeError('cash table missing')
    old_block=c[hp:table_end+8]
    if 'MONEY IN' not in old_block:
        raise RuntimeError('unexpected first KPI table')
    c=c[:hp]+SIMPLE_CASH+c[table_end+8:]

    # Mark the exact board migration for post-write verification.
    if MARK not in c:
        c=c.replace(marker,marker+'<!-- '+MARK+' -->',1)

    # Assertions: one real brand only, sticky targets retained, cash section is genuinely two-flow only.
    sec_start=c.find('Revenue &amp; costs')
    sec_end=c.find('<div class="tiles">',sec_start)
    if sec_start<0 or sec_end<0: raise RuntimeError('new cash section boundaries missing')
    cash=c[sec_start:sec_end]
    checks={
      'sticky':'position:sticky' in c,
      'real_wordmark':'<span class="wordmark">startend<span>.ch</span></span>' in c,
      'hq_portfolio':'HQ &middot; portfolio' in c,
      'one_brandline':c.count('class="brandline"')==1,
      'no_text_brand':'STARTEND <span style="color:#DA291C">·</span> HQ' not in c,
      'revenue_costs':'Revenue &amp; costs' in c,
      'money_in':'<td class="lab">MONEY IN</td>' in cash,
      'money_out':'<td class="lab">MONEY OUT</td>' in cash,
      'no_net':'<td class="lab">NET</td>' not in cash,
      'no_unpriced_row':'MONEY OUT &mdash; unpriced' not in cash,
      'cost_caveat':'true run-rate is higher' in cash,
      '2029':'CHF 1B/year' in c,
      '2030':'CHF 2B/year' in c,
      'tiles_kept':'Checkouts live' in c and 'Domains owned' in c,
    }
    print('BOARD_CHECKS',checks)
    if not all(checks.values()): raise RuntimeError('board assertions failed '+repr(checks))
    return c


def has_true(x,key):
    if isinstance(x,dict):
        if x.get(key) is True:return True
        return any(has_true(v,key) for v in x.values())
    if isinstance(x,list):return any(has_true(v,key) for v in x)
    return False


def main():
    # Mandatory asset-reuse gate before building/mutating.
    a=latest('02_ASSETS')
    print('ASSETS_OK',a['version'],a['id'])

    v1=write('03_DECISIONS',decisions,'Reuse real STARTEND brand in sticky HQ header; simplify cash display to money in/out')
    v2=write('BOARD_HTML',board,'Reuse visual startend.ch logo in sticky target block; Revenue & costs = MONEY IN + MONEY OUT only')
    print('CANON_DONE',{'03_DECISIONS':v1,'BOARD_HTML':v2})

    s,b=req(BUS)
    if s!=200 or not isinstance(b,dict) or not b.get('bus_cursor'): raise RuntimeError('bus cursor missing')
    if not any(BUS_MARK in (x.get('what') or '') for x in b.get('recent',[])):
        ps,p=req(BUS,{
          'team':'GPT_CURSOR','project':'0','type':'DONE',
          'what':f'{BUS_MARK} · HQ board: reused the existing startend.ch SVG/wordmark inside the sticky target block, removed lower duplicate, renamed The numbers → Revenue & costs, reduced cash table to MONEY IN / MONEY OUT while retaining the unpriced-cost caveat. 03_DECISIONS v{v1} · BOARD_HTML v{v2}.',
          'next':'4.1 lock unchanged: finish stranger checkout + legal + Börlin hard gaps, re-score, self-pay, then SELL.',
          'link':BOARD,'bus_cursor':b['bus_cursor']})
        if ps!=200 or not isinstance(p,dict) or not p.get('accepted'): raise RuntimeError(f'bus failed {ps} {p!r}')
        print('BUS_DONE',p.get('id'))
        rs,r=req(REDEPLOY,{'who':WHO,'why':f'BOARD_HTML v{v2} real sticky brand + simple cash'})
        if rs!=200 or not has_true(r,'serviceInstanceRedeploy'): raise RuntimeError(f'redeploy failed {rs} {r!r}')
        print('REDEPLOY_OK',r)
    else:
        print('GUARD bus DONE exists; skip duplicate redeploy')


if __name__=='__main__': main()
