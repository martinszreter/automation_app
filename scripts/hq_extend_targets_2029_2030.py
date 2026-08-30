#!/usr/bin/env python3
import os,json,re,urllib.request as u

CANON=os.environ['CANON_RW_URL']
BUS='https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k'
REDEPLOY='https://startend.app.n8n.cloud/webhook/redeploy-portfolio-7k4q9x'
BOARD='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'
WHO='HQ_GPT'
MARK='HARD TARGET EXTENSION ANNUAL + STICKY TOP 2026-08-30'
BUS_MARK='HQ_GPT_TARGETS_ANNUAL_STICKY_DONE'


def req(url,p=None):
    if p is None:
        with u.urlopen(url,timeout=45) as r:
            raw=r.read().decode(); return r.status,json.loads(raw) if raw.strip().startswith(('{','[')) else raw
    q=u.Request(url,data=json.dumps(p).encode(),headers={'Content-Type':'application/json'})
    with u.urlopen(q,timeout=45) as r:
        raw=r.read().decode(); return r.status,json.loads(raw) if raw.strip().startswith(('{','[')) else raw

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
    base=latest(k)
    new=fn(base['content'])
    if new==base['content']:
        print('NOOP',k,'v',base['version']); return int(base['version'])
    v=int(base['version'])+1
    res=insert(k,v,new,note)
    rr=rows(k); same=[r for r in rr if int(r['version'])==v]
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
    if int(top['version'])!=v or MARK not in top['content']:
        raise RuntimeError(f'post-write verify {k}: top={top.get("version")} expected={v}')
    print('WRITE_OK',k,'v',v,'id',top['id'],'len',len(top['content']))
    return v

ANNUAL='''## HARD TARGET EXTENSION — 2029/2030 ARE ANNUAL TARGETS\n\nThese are portfolio forcing targets, not forecasts, and supersede conflicting later-year targets:\n- **31 Dec 2029 — CHF 1,000,000,000/year**. Equivalent operating pace: ~CHF 2.74M/day, ~CHF 82.2M per trailing 30 days.\n- **31 Dec 2030 — CHF 2,000,000,000/year**. Equivalent operating pace: ~CHF 5.48M/day, ~CHF 164.4M per trailing 30 days.\n\nThe anti-gaming convention remains collected revenue. The ladder is therefore: CHF 10k/day by Dec-2026 → CHF 100k/day by Dec-2027 → CHF 1M/day by Dec-2028 → CHF 1B/year by Dec-2029 → CHF 2B/year by Dec-2030. 2028→2029 is ~2.74× on annualised run-rate; 2029→2030 is 2×. These are targets, not forecasts.\n'''

def strategy(c):
    c=c.replace('CHF 1,000,000,000/day','CHF 1,000,000,000/year').replace('CHF 2,000,000,000/day','CHF 2,000,000,000/year')
    c=c.replace('CHF 1B/day by 31 Dec 2029','CHF 1B/year by 31 Dec 2029').replace('CHF 2B/day by 31 Dec 2030','CHF 2B/year by 31 Dec 2030')
    if MARK in c: return c
    return '## '+MARK+'\n\n'+ANNUAL+'\n'+c

def decisions(c):
    c=c.replace('CHF 1B/day by 31 Dec 2029','CHF 1B/year by 31 Dec 2029').replace('CHF 2B/day by 31 Dec 2030','CHF 2B/year by 31 Dec 2030')
    if MARK in c: return c
    b=f'''2026-08-30 | HQ / ALL INITIATIVES | FOUNDER DECISION | {MARK}. Extend the hard portfolio revenue ladder with **CHF 1B/year by 31 Dec 2029** and **CHF 2B/year by 31 Dec 2030**. Equivalents: 2029 ≈ CHF 2.74M/day / CHF 82.2M trailing-30d; 2030 ≈ CHF 5.48M/day / CHF 164.4M trailing-30d. These are forcing targets, not forecasts. Preserve the anti-gaming collected-revenue convention. The top STARTEND target block on BOARD_HTML must remain sticky/pinned while scrolling.\n\nupdated_by=HQ_GPT'''
    return b+'\n\n'+c

def board(c):
    c=c.replace('CHF 1B/day','CHF 1B/year').replace('CHF 2B/day','CHF 2B/year')
    c=c.replace('CHF 30B</td><td>CHF 365B','CHF 82.2M</td><td>CHF 1B').replace('CHF 60B</td><td>CHF 730B','CHF 164.4M</td><td>CHF 2B')
    marker='<!-- HARD_TARGETS_DACH_LTV_20260830 -->'
    s=c.find(marker)
    if s<0: raise RuntimeError('hard-target marker missing')
    t0=c.find('<table',s); t1=c.find('</table>',t0)
    if t0<0 or t1<0: raise RuntimeError('hard-target table missing')
    table=c[t0:t1]
    if '31 DEC 2029' not in table:
        add='''\n<tr><td><b>31 DEC 2029</b></td><td><b>CHF 2.74M/day</b></td><td>CHF 82.2M</td><td><b>CHF 1B/year</b></td></tr>\n<tr><td><b>31 DEC 2030</b></td><td><b>CHF 5.48M/day</b></td><td>CHF 164.4M</td><td><b>CHF 2B/year</b></td></tr>'''
        c=c[:t1]+add+c[t1:]
    else:
        c=re.sub(r'<tr><td><b>31 DEC 2029</b></td>.*?</tr>', '<tr><td><b>31 DEC 2029</b></td><td><b>CHF 2.74M/day</b></td><td>CHF 82.2M</td><td><b>CHF 1B/year</b></td></tr>', c, count=1, flags=re.S)
        c=re.sub(r'<tr><td><b>31 DEC 2030</b></td>.*?</tr>', '<tr><td><b>31 DEC 2030</b></td><td><b>CHF 5.48M/day</b></td><td>CHF 164.4M</td><td><b>CHF 2B/year</b></td></tr>', c, count=1, flags=re.S)
    card_start=c.find('<div class="card"',s)
    if card_start<0: raise RuntimeError('target card missing')
    card_open_end=c.find('>',card_start)
    opening=c[card_start:card_open_end+1]
    if 'position:sticky' not in opening:
        if 'style="' in opening:
            opening=opening.replace('style="','style="position:sticky;top:0;z-index:999;background:#f7f4ec;box-shadow:0 8px 22px rgba(0,0,0,.14);',1)
        else:
            opening=opening[:-1]+' style="position:sticky;top:0;z-index:999;background:#f7f4ec;box-shadow:0 8px 22px rgba(0,0,0,.14)">'
        c=c[:card_start]+opening+c[card_open_end+1:]
    card_open_end=c.find('>',card_start)
    next_chunk=c[card_open_end+1:card_open_end+1200]
    if 'EXPONENTIAL ONLY' not in next_chunk or 'STARTEND' not in next_chunk:
        brand='''\n<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:-2px 0 6px"><div style="font-weight:900;font-size:15px;letter-spacing:.18em">STARTEND <span style="color:#DA291C">·</span> HQ</div><div class="dim" style="font-size:9px;letter-spacing:.08em">EXPONENTIAL ONLY</div></div>'''
        c=c[:card_open_end+1]+brand+c[card_open_end+1:]
    t0=c.find('<table',s); open_end=c.find('>',t0)
    topen=c[t0:open_end+1]
    if 'font-size:10px' not in topen:
        if 'style="' in topen: topen=topen.replace('style="','style="font-size:10px;line-height:1.1;',1)
        else: topen=topen[:-1]+' style="font-size:10px;line-height:1.1">'
        c=c[:t0]+topen+c[open_end+1:]
    t1=c.find('</table>',t0)+len('</table>')
    if '2029/2030 are annual targets' not in c[t1:t1+1400]:
        note='''\n<div style="font-size:9.5px;margin-top:5px"><b>2029/2030 are annual targets:</b> CHF 1B/year → CHF 2B/year. 2026–2028 remain daily run-rate targets. Targets ≠ forecasts.</div>'''
        c=c[:t1]+note+c[t1:]
    if MARK not in c: c=c.replace(marker,marker+'<!-- '+MARK+' -->',1)
    checks=['position:sticky','EXPONENTIAL ONLY','STARTEND','31 DEC 2029','CHF 1B/year','31 DEC 2030','CHF 2B/year']
    miss=[x for x in checks if x not in c]
    if miss: raise RuntimeError('board checks missing '+repr(miss))
    return c

def has_true(x,key):
    if isinstance(x,dict):
        if x.get(key) is True:return True
        return any(has_true(v,key) for v in x.values())
    if isinstance(x,list):return any(has_true(v,key) for v in x)
    return False

def main():
    a=latest('02_ASSETS'); print('ASSETS_OK',a['version'],a['id'])
    v1=write('01_STRATEGY',strategy,'Correct 2029/2030 to annual hard targets; retain exponential forcing ladder')
    v2=write('03_DECISIONS',decisions,'Founder targets: CHF1B/year 2029; CHF2B/year 2030; pin STARTEND target block')
    v3=write('BOARD_HTML',board,'Pin STARTEND + target ladder; add annual 2029/2030 targets')
    print('CANON_DONE',{'01_STRATEGY':v1,'03_DECISIONS':v2,'BOARD_HTML':v3})
    s,b=req(BUS)
    if s!=200 or not isinstance(b,dict) or not b.get('bus_cursor'): raise RuntimeError('bus cursor missing')
    if not any(BUS_MARK in (x.get('what') or '') for x in b.get('recent',[])):
        ps,p=req(BUS,{'team':'GPT_CURSOR','project':'0','type':'DONE','what':f'{BUS_MARK} · Corrected long-range targets to CHF1B/year 2029 and CHF2B/year 2030; pinned existing STARTEND hard-target block at top while scrolling. Canon: 01_STRATEGY v{v1} · 03_DECISIONS v{v2} · BOARD_HTML v{v3}.','next':'4.1 execution lock unchanged: finish product-quality gate and self-pay; target bar stays visible as scale filter.','link':BOARD,'bus_cursor':b['bus_cursor']})
        if ps!=200 or not isinstance(p,dict) or not p.get('accepted'): raise RuntimeError(f'bus failed {ps} {p!r}')
        print('BUS_DONE',p.get('id'))
        rs,r=req(REDEPLOY,{'who':WHO,'why':f'BOARD_HTML v{v3} sticky targets + annual 2029/2030'})
        if rs!=200 or not has_true(r,'serviceInstanceRedeploy'): raise RuntimeError(f'redeploy failed {rs} {r!r}')
        print('REDEPLOY_OK',r)
    else:
        print('GUARD bus DONE exists; skip duplicate redeploy')

if __name__=='__main__': main()
