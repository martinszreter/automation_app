#!/usr/bin/env python3
import os,json,re,urllib.request as u

CANON=os.environ['CANON_RW_URL']
BUS='https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k'
REDEPLOY='https://startend.app.n8n.cloud/webhook/redeploy-portfolio-7k4q9x'
WHO='HQ_GPT'
MARK='HARD TARGET EXTENSION 2029-2030 2026-08-30'
BUS_MARK='HQ_GPT_TARGETS_2029_2030_DONE'


def req(url,p=None):
    if p is None:
        with u.urlopen(url,timeout=45) as r:
            raw=r.read().decode(); return r.status,json.loads(raw) if raw.strip().startswith(('{','[')) else raw
    q=u.Request(url,data=json.dumps(p).encode(),headers={'Content-Type':'application/json'})
    with u.urlopen(q,timeout=45) as r:
        raw=r.read().decode(); return r.status,json.loads(raw) if raw.strip().startswith(('{','[')) else raw

def rows(k):
    s,x=req(CANON,{'action':'read','keyValue':k})
    if s!=200 or not isinstance(x,list) or not x: raise RuntimeError(f'EMPTY canon read {k}: {s} {x!r}')
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
    base=latest(k)  # mandatory immediate re-read before write
    new=fn(base['content'])
    if new==base['content']:
        print('NOOP',k,'v',base['version']); return int(base['version'])
    v=int(base['version'])+1
    res=insert(k,v,new,note)
    rr=rows(k)  # mandatory immediate re-read after write
    same=[r for r in rr if int(r['version'])==v]
    if len(same)>1:
        own_id=res.get('id') if isinstance(res,dict) else None
        other=next((r for r in same if str(r.get('id'))!=str(own_id)),None)
        if other is None: raise RuntimeError('race cannot identify other '+k)
        v2=max(int(r['version']) for r in rr)+1
        insert(k,v2,fn(other['content']),note+' · race repair')
        if own_id: delete(own_id)
        if len([r for r in rows(k) if int(r['version'])==v2])>1: raise RuntimeError('second race '+k)
        v=v2
    prune(k)
    top=latest(k)
    if int(top['version'])!=v or MARK not in top['content']: raise RuntimeError('post-write verify '+k)
    print('WRITE_OK',k,'v',v,'id',top['id'])
    return v

BLOCK=f'''## {MARK}\n\nFOUNDER HARD TARGET EXTENSION — these are portfolio forcing targets, not forecasts, and they supersede any conflicting later-year targets:\n- **31 Dec 2029 — CHF 1,000,000,000/day** = CHF 30B trailing-30-day collected revenue; ~CHF 365B annualised run-rate.\n- **31 Dec 2030 — CHF 2,000,000,000/day** = CHF 60B trailing-30-day collected revenue; ~CHF 730B annualised run-rate.\n\nThe anti-gaming metric remains **daily revenue = trailing-30-day COLLECTED portfolio revenue / 30**. The sequence is deliberately discontinuous: 2028 → 2029 is a **1,000× jump** (CHF 1M/day → CHF 1B/day), then 2029 → 2030 is 2×. Do not describe this as a smooth 10× annual staircase. Every strategy review must expose the gap and reject linear-human-scale plans.\n'''

def strategy(c):
    if MARK in c: return c
    return BLOCK+'\n\n'+c

def decisions(c):
    if MARK in c: return c
    b=f'''2026-08-30 | HQ / ALL INITIATIVES | FOUNDER DECISION | {MARK}. Extend the hard portfolio revenue targets: **CHF 1B/day by 31 Dec 2029** and **CHF 2B/day by 31 Dec 2030**, measured as trailing-30-day COLLECTED revenue / 30. This supersedes conflicting later-year targets. 2028→2029 is explicitly a 1,000× jump, not a normal 10× step; 2029→2030 is 2×. Targets remain forcing functions, not forecasts. Any strategy that requires roughly linear human labour with revenue is structurally incompatible with these rungs.\n\nupdated_by=HQ_GPT'''
    return b+'\n\n'+c

def board(c):
    if MARK in c: return c
    marker='<!-- HARD_TARGETS_DACH_LTV_20260830 -->'
    s=c.find(marker)
    if s<0: raise RuntimeError('target marker missing')
    t0=c.find('<table',s); t1=c.find('</table>',t0)
    if t0<0 or t1<0: raise RuntimeError('target table missing')
    table=c[t0:t1]
    if '31 DEC 2029' not in table:
        rows='''\n<tr><td><b>31 DEC 2029</b></td><td><b>CHF 1B/day</b></td><td>CHF 30B</td><td>CHF 365B</td></tr>\n<tr><td><b>31 DEC 2030</b></td><td><b>CHF 2B/day</b></td><td>CHF 60B</td><td>CHF 730B</td></tr>'''
        c=c[:t1]+rows+c[t1:]
    # Add the discontinuity warning directly under the table, once.
    t1=c.find('</table>',t0)+len('</table>')
    note='''\n<div style="font-size:10.5px;margin-top:6px"><b>Founder forcing sequence:</b> 2028→2029 is <b>1,000×</b>, then 2029→2030 is <b>2×</b>. These are targets, not forecasts; the gap must stay visible.</div>'''
    if 'Founder forcing sequence:' not in c[s:s+5000]: c=c[:t1]+note+c[t1:]
    return c.replace(marker,marker+'<!-- '+MARK+' -->',1)

def main():
    # HARD RULE: asset inventory first; existence means reuse, never a new parallel system.
    assets=latest('02_ASSETS')
    print('ASSETS_OK',assets['version'],assets['id'])
    v1=write('01_STRATEGY',strategy,'Extend hard revenue targets to CHF1B/day 2029 and CHF2B/day 2030')
    v2=write('03_DECISIONS',decisions,'Founder hard target extension through 2030')
    v3=write('BOARD_HTML',board,'Add 2029/2030 hard targets to top revenue ladder')
    # fresh bus cursor for DONE
    s,b=req(BUS)
    if s!=200 or not isinstance(b,dict) or not b.get('bus_cursor'): raise RuntimeError('bus cursor missing')
    recent=b.get('recent',[])
    if not any(BUS_MARK in (x.get('what') or '') for x in recent):
        ps,p=req(BUS,{'team':'GPT_CURSOR','project':'0','type':'DONE','what':f'{BUS_MARK} · Hard targets extended: CHF1B/day by 31 Dec 2029 and CHF2B/day by 31 Dec 2030. Canon: 01_STRATEGY v{v1} · 03_DECISIONS v{v2} · BOARD_HTML v{v3}. 2028→2029 is explicitly shown as 1,000×; daily metric remains trailing-30d collected ÷ 30.','next':'Keep current execution lock on 4.1; use the five-rung ladder only as a scale filter and expose the operational gap in every strategy review.','link':'https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html','bus_cursor':b['bus_cursor']})
        if ps!=200 or not isinstance(p,dict) or not p.get('accepted'): raise RuntimeError(f'bus failed {ps} {p!r}')
        print('BUS_DONE',p.get('id'))
        rs,r=req(REDEPLOY,{'who':WHO,'why':f'BOARD_HTML v{v3} hard targets through 2030'})
        ok=isinstance(r,(dict,list)) and 'serviceInstanceRedeploy' in json.dumps(r) and 'true' in json.dumps(r).lower()
        if rs!=200 or not ok: raise RuntimeError(f'redeploy confirmation missing {rs} {r!r}')
        print('REDEPLOY_OK',r)
    else:
        print('GUARD bus DONE exists; skip duplicate redeploy')

if __name__=='__main__': main()
