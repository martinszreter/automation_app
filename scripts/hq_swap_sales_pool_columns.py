#!/usr/bin/env python3
import json, re, urllib.request as u

CANON='https://startend.app.n8n.cloud/webhook/canon-rw-9k2x7m4q'
BUS='https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k'
REDEPLOY='https://startend.app.n8n.cloud/webhook/redeploy-portfolio-7k4q9x'
BOARD='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'
WHO='HQ_GPT'

def req(url, payload=None):
    if payload is None:
        with u.urlopen(url, timeout=30) as r:
            raw=r.read().decode(); return r.status, json.loads(raw) if raw.strip().startswith(('{','[')) else raw
    q=u.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with u.urlopen(q,timeout=30) as r:
        raw=r.read().decode(); return r.status, json.loads(raw) if raw.strip().startswith(('{','[')) else raw

def canon_rows(key):
    s,x=req(CANON,{'action':'read','keyValue':key})
    if s!=200 or not isinstance(x,list) or not x:
        raise RuntimeError(f'canon read failed/empty for {key}: {s} {x!r}')
    return sorted(x,key=lambda r:int(r['version']),reverse=True)

def insert(key,version,content,note):
    s,x=req(CANON,{'action':'insert','file':key,'version':version,'content':content,'note':note,'updated_by':WHO})
    if s!=200: raise RuntimeError(f'insert {key} failed {s} {x!r}')
    return x

def delete_id(i):
    s,x=req(CANON,{'action':'delete','id':str(i)})
    if s!=200: raise RuntimeError(f'delete {i} failed {s} {x!r}')

def prune(key):
    rows=canon_rows(key)
    for r in rows[3:]: delete_id(r['id'])
    print('PRUNE',key,[(int(r['version']),r['id']) for r in canon_rows(key)])

def norm(s):
    return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',s)).strip().upper()

def swap_cells(row,i,j):
    ms=list(re.finditer(r'<t[hd]\b[^>]*>.*?</t[hd]>',row,re.I|re.S))
    if len(ms)<=max(i,j): return row
    ci,cj=ms[i].group(0),ms[j].group(0)
    repl=[(ms[i].start(),ms[i].end(),cj),(ms[j].start(),ms[j].end(),ci)]
    out=row
    for a,b,v in sorted(repl,reverse=True): out=out[:a]+v+out[b:]
    return out

def swap_table(table):
    if 'CUSTOMERS<br>POOL' not in table or '1% SALES<br>POOL' not in table: return table,False
    rows=list(re.finditer(r'<tr\b[^>]*>.*?</tr>',table,re.I|re.S))
    hi=hj=None
    for rm in rows:
        cells=list(re.finditer(r'<th\b[^>]*>.*?</th>',rm.group(0),re.I|re.S))
        if not cells: continue
        labels=[norm(c.group(0)) for c in cells]
        for k,l in enumerate(labels):
            if l=='CUSTOMERS POOL': hi=k
            if l=='1% SALES POOL': hj=k
        if hi is not None and hj is not None: break
    if hi is None or hj is None: return table,False
    # already in requested order
    if hj < hi: return table,False
    out=table
    replacements=[]
    for rm in rows:
        row=rm.group(0)
        cells=list(re.finditer(r'<t[hd]\b[^>]*>.*?</t[hd]>',row,re.I|re.S))
        if len(cells)>max(hi,hj):
            replacements.append((rm.start(),rm.end(),swap_cells(row,hi,hj)))
    for a,b,v in sorted(replacements,reverse=True): out=out[:a]+v+out[b:]
    return out,True

def transform(html):
    changed=0
    reps=[]
    for tm in re.finditer(r'<table\b[^>]*>.*?</table>',html,re.I|re.S):
        new,did=swap_table(tm.group(0))
        if did:
            changed+=1; reps.append((tm.start(),tm.end(),new))
    out=html
    for a,b,v in sorted(reps,reverse=True): out=out[:a]+v+out[b:]
    if changed==0:
        # validate requested order is already present in at least the two pool tables
        good=0
        for tm in re.finditer(r'<table\b[^>]*>.*?</table>',out,re.I|re.S):
            t=tm.group(0)
            a=t.find('1% SALES<br>POOL'); b=t.find('CUSTOMERS<br>POOL')
            if a>=0 and b>=0 and a<b: good+=1
        if good<2: raise RuntimeError(f'no swap performed and only {good} tables already ordered')
        return out,0
    # verify target ordering after transform
    good=0
    for tm in re.finditer(r'<table\b[^>]*>.*?</table>',out,re.I|re.S):
        t=tm.group(0)
        a=t.find('1% SALES<br>POOL'); b=t.find('CUSTOMERS<br>POOL')
        if a>=0 and b>=0:
            if a>b: raise RuntimeError('pool headers remain in wrong order')
            good+=1
    if good<2: raise RuntimeError(f'expected >=2 pool tables, got {good}')
    return out,changed

def has_true(x,key):
    if isinstance(x,dict):
        if x.get(key) is True:return True
        return any(has_true(v,key) for v in x.values())
    if isinstance(x,list):return any(has_true(v,key) for v in x)
    return False

def write_board():
    assets=canon_rows('02_ASSETS')[0]
    print('ASSETS_OK',assets['version'])
    base=canon_rows('BOARD_HTML')[0]
    new,changed=transform(base['content'])
    if not changed:
        print('NOOP board already ordered v',base['version'])
        return None
    version=int(base['version'])+1
    res=insert('BOARD_HTML',version,new,'Reorder pool columns: 1% SALES POOL first, CUSTOMERS POOL second.')
    rows=canon_rows('BOARD_HTML')
    same=[r for r in rows if int(r['version'])==version]
    if len(same)>1:
        own_id=None
        if isinstance(res,dict): own_id=res.get('id')
        other=next((r for r in same if str(r.get('id'))!=str(own_id)),same[0])
        merged,_=transform(other['content'])
        v2=max(int(r['version']) for r in rows)+1
        insert('BOARD_HTML',v2,merged,'Race merge: preserve parallel BOARD_HTML write and requested pool-column order.')
        if own_id: delete_id(own_id)
        version=v2
    prune('BOARD_HTML')
    latest=canon_rows('BOARD_HTML')[0]
    if int(latest['version'])!=version: raise RuntimeError('post-write latest version mismatch')
    print('WRITE_OK BOARD_HTML',version,'len',len(latest['content']))
    return version

def report_and_redeploy(version):
    s,b=req(BUS)
    if s!=200 or not isinstance(b,dict) or not b.get('bus_cursor'):
        raise RuntimeError(f'bus cursor failed {s} {b!r}')
    ps,p=req(BUS,{'team':'GPT_CURSOR','project':'0','type':'DONE','what':f'HQ_GPT reordered portfolio pool columns: 1% SALES POOL now appears before CUSTOMERS POOL in project and initiative tables. BOARD_HTML v{version}.','next':'Keep pool denominator definitions explicit; benchmark conversion against 1% before changing market assumptions.','link':BOARD,'bus_cursor':b['bus_cursor']})
    if ps!=200 or not isinstance(p,dict) or not p.get('accepted'):
        raise RuntimeError(f'bus DONE failed {ps} {p!r}')
    print('BUS_DONE',p.get('id'))
    rs,r=req(REDEPLOY,{'who':WHO,'why':f'BOARD_HTML v{version} pool column order'})
    if rs!=200 or not has_true(r,'serviceInstanceRedeploy'):
        raise RuntimeError(f'official redeploy failed {rs} {r!r}')
    print('REDEPLOY_OK',r)

def main():
    version=write_board()
    if version is not None: report_and_redeploy(version)

if __name__=='__main__': main()
