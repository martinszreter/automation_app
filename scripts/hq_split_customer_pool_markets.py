#!/usr/bin/env python3
import json, re, html as H, urllib.request as u

CANON='https://startend.app.n8n.cloud/webhook/canon-rw-9k2x7m4q'
BUS='https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k'
REDEPLOY='https://startend.app.n8n.cloud/webhook/redeploy-portfolio-7k4q9x'
BOARD='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'
WHO='HQ_GPT'

# Claude 7-market model @ 60% reachable; AT is folded into DE bucket by founder display request.
NHT={'CH':86112,'DE':564265,'PL':231840,'ENG':2850638}

PROJECT={
 '0':None,
 '1':{'CH':0,'DE':0,'PL':8000,'ENG':80000},
 '2':{'CH':0,'DE':0,'PL':0,'ENG':200000},
 '3':NHT,
 '4':{'CH':28000,'DE':0,'PL':0,'ENG':0},
 '5':{'CH':0,'DE':0,'PL':0,'ENG':280000},
 '6':{'CH':0,'DE':0,'PL':0,'ENG':0},
 '7':None,
 '8':{'CH':0,'DE':0,'PL':0,'ENG':0},
}

INIT={
 '4.1':{'CH':28000,'DE':0,'PL':0,'ENG':0},
 '3.5b':NHT,
 '3.5b-V':NHT,
 '3.2':{'CH':3460,'DE':22674,'PL':9316,'ENG':114550},
 '3.5a':{'CH':0,'DE':0,'PL':0,'ENG':80000},
 '3.5c':{'CH':0,'DE':0,'PL':0,'ENG':200000},
 '5.2':{'CH':0,'DE':0,'PL':0,'ENG':200000},
 '5.3':{'CH':0,'DE':0,'PL':0,'ENG':80000},
 '3.5d':{'CH':40000,'DE':0,'PL':0,'ENG':0},
 '1.3':{'CH':0,'DE':0,'PL':8000,'ENG':0},
 '1.3-DE':{'CH':0,'DE':8000,'PL':0,'ENG':0},
 '1.3-EN':{'CH':0,'DE':0,'PL':0,'ENG':8000},
 '3.4':None,
 '1.8':None,
 '3.9':None,
}

def request(url,payload=None):
    if payload is None:
        with u.urlopen(url,timeout=30) as r:
            raw=r.read().decode(); return r.status, json.loads(raw) if raw.strip().startswith(('{','[')) else raw
    q=u.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with u.urlopen(q,timeout=30) as r:
        raw=r.read().decode(); return r.status, json.loads(raw) if raw.strip().startswith(('{','[')) else raw

def rows(key):
    s,x=request(CANON,{'action':'read','keyValue':key})
    if s!=200 or not isinstance(x,list) or not x: raise RuntimeError(f'canon read empty {key}: {s} {x!r}')
    return sorted(x,key=lambda r:int(r['version']),reverse=True)

def insert(key,v,content,note):
    s,x=request(CANON,{'action':'insert','file':key,'version':v,'content':content,'note':note,'updated_by':WHO})
    if s!=200: raise RuntimeError(f'insert failed {key}: {s} {x!r}')
    return x

def delete(i):
    s,x=request(CANON,{'action':'delete','id':str(i)})
    if s!=200: raise RuntimeError(f'delete failed {i}: {s} {x!r}')

def prune(key):
    rr=rows(key)
    for r in rr[3:]: delete(r['id'])
    print('PRUNE',key,[(int(r['version']),r['id']) for r in rows(key)])

def txt(cell):
    s=re.sub(r'<[^>]+>',' ',cell)
    return re.sub(r'\s+',' ',H.unescape(s)).strip()

def fmt(n): return f'{n:,}'

def geo_cells(d, note=''):
    if d is None:
        return ''.join('<td class="prod" style="text-align:center"><span class="dim">TBD</span></td>' for _ in range(4))
    out=[]
    for k in ('CH','DE','PL','ENG'):
        n=d.get(k,0)
        val='—' if n==0 else fmt(n)
        extra=''
        if note and n: extra=f'<br><span class="dim">{note}</span>'
        out.append(f'<td class="prod" style="text-align:center"><b>{val}</b>{extra}</td>')
    return ''.join(out)

def table_kind(table):
    up=txt(table).upper()
    if 'PROJECT' in up and 'PRODUCTS' in up and 'THINKS' in up: return 'project'
    if 'INITIATIVE' in up or 'READINESS' in up or 'NEXT ACTION' in up: return 'initiative'
    # detailed initiative table does not always spell INITIATIVE in the current board header; IDs disambiguate it.
    if 'DOMAINS' in up and 'PRICE' in up: return 'initiative'
    return 'unknown'

def transform_table(table):
    if '1% SALES<br>POOL' not in table or 'CUSTOMERS<br>POOL' not in table: return table,False
    kind=table_kind(table)
    rms=list(re.finditer(r'<tr\b[^>]*>.*?</tr>',table,re.I|re.S))
    header_idx=pool_idx=None
    for rm in rms:
        cs=list(re.finditer(r'<th\b[^>]*>.*?</th>',rm.group(0),re.I|re.S))
        if not cs: continue
        labs=[txt(c.group(0)).upper() for c in cs]
        for i,l in enumerate(labs):
            if '1% SALES' in l: header_idx=i
            if 'CUSTOMERS' in l and 'POOL' in l: pool_idx=i
        if header_idx is not None and pool_idx is not None: break
    if pool_idx is None: return table,False
    reps=[]
    for rm in rms:
        row=rm.group(0)
        # Group separator rows with colspan need +3 columns.
        if re.search(r'colspan="\d+"',row,re.I) and not re.search(r'<th\b',row,re.I):
            row2=re.sub(r'colspan="(\d+)"',lambda m:f'colspan="{int(m.group(1))+3}"',row,count=1,flags=re.I)
            reps.append((rm.start(),rm.end(),row2)); continue
        cells=list(re.finditer(r'<t[hd]\b[^>]*>.*?</t[hd]>',row,re.I|re.S))
        if len(cells)<=pool_idx: continue
        if re.search(r'<th\b',row,re.I):
            old=cells[pool_idx]
            hdr=(
              '<th>CH<br><span class="dim">CUSTOMERS POOL</span></th>'
              '<th>DE (+AT)<br><span class="dim">CUSTOMERS POOL</span></th>'
              '<th>PL<br><span class="dim">CUSTOMERS POOL</span></th>'
              '<th>ENG<br><span class="dim">US + UK + AU</span></th>'
            )
            row2=row[:old.start()]+hdr+row[old.end():]
            reps.append((rm.start(),rm.end(),row2)); continue
        rid=txt(cells[0].group(0))
        old=cells[pool_idx]
        current=txt(old.group(0)).upper()
        d=(PROJECT.get(rid) if kind=='project' else INIT.get(rid))
        # Preserve honest zero/n-a/TBD status when no geography model exists.
        if d is None:
            if re.search(r'(^|\D)0($|\D)',current) and 'TBD' not in current:
                d={'CH':0,'DE':0,'PL':0,'ENG':0}
            elif any(x in current for x in ['N/A','NOT A PRODUCT','—']):
                repl=''.join('<td class="prod" style="text-align:center"><span class="dim">—</span></td>' for _ in range(4))
                row2=row[:old.start()]+repl+row[old.end():]
                reps.append((rm.start(),rm.end(),row2)); continue
            else:
                repl=geo_cells(None)
                row2=row[:old.start()]+repl+row[old.end():]
                reps.append((rm.start(),rm.end(),row2)); continue
        note=''
        if rid in ('3','3.5b','3.5b-V'): note='DE includes AT'
        elif rid=='3.2': note='7-market mix'
        row2=row[:old.start()]+geo_cells(d,note)+row[old.end():]
        reps.append((rm.start(),rm.end(),row2))
    out=table
    for a,b,v in sorted(reps,reverse=True): out=out[:a]+v+out[b:]
    return out,True

def transform(doc):
    reps=[]; changed=0
    for tm in re.finditer(r'<table\b[^>]*>.*?</table>',doc,re.I|re.S):
        new,did=transform_table(tm.group(0))
        if did:
            changed+=1; reps.append((tm.start(),tm.end(),new))
    if changed<2: raise RuntimeError(f'expected project + initiative pool tables, transformed {changed}')
    out=doc
    for a,b,v in sorted(reps,reverse=True): out=out[:a]+v+out[b:]
    # Clarify bucket semantics once near existing pool explanation.
    marker='<b>POOL · 1% SALES</b>'
    note='<b>MARKET SPLIT:</b> CH = Switzerland · DE = Germany + Austria bucket · PL = Poland · ENG = USA + UK + Australia. Country cells are reachable-pool models; they must sum to the denominator behind the 1% benchmark where a split is known. '
    p=out.find(marker)
    if p>=0 and note not in out:
        q=out.find('</div>',p)
        if q>=0: out=out[:q]+note+out[q:]
    # widen the top summary table if exact old width is still present
    out=out.replace('style="min-width:1520px"','style="min-width:1880px"',1)
    return out

def has_true(x,key):
    if isinstance(x,dict):
        if x.get(key) is True:return True
        return any(has_true(v,key) for v in x.values())
    if isinstance(x,list):return any(has_true(v,key) for v in x)
    return False

def main():
    print('ASSETS_OK',rows('02_ASSETS')[0]['version'])
    base=rows('BOARD_HTML')[0]  # mandatory immediate re-read
    new=transform(base['content'])
    v=int(base['version'])+1
    res=insert('BOARD_HTML',v,new,'Split CUSTOMERS POOL into CH / DE(+AT) / PL / ENG while keeping 1% SALES POOL as one leading benchmark column.')
    rr=rows('BOARD_HTML')
    same=[r for r in rr if int(r['version'])==v]
    if len(same)>1:
        own_id=res.get('id') if isinstance(res,dict) else None
        other=next((r for r in same if str(r.get('id'))!=str(own_id)),same[0])
        merged=transform(other['content'])
        v2=max(int(r['version']) for r in rr)+1
        insert('BOARD_HTML',v2,merged,'Race merge: preserve parallel BOARD_HTML change and market-split customer pool columns.')
        if own_id: delete(own_id)
        v=v2
    prune('BOARD_HTML')
    latest=rows('BOARD_HTML')[0]
    if int(latest['version'])!=v: raise RuntimeError('post-write latest mismatch')
    c=latest['content']
    checks={
      'one_first': c.find('1% SALES<br>POOL') < c.find('CH<br><span class="dim">CUSTOMERS POOL'),
      'ch': 'CH<br><span class="dim">CUSTOMERS POOL' in c,
      'de': 'DE (+AT)<br><span class="dim">CUSTOMERS POOL' in c,
      'pl': 'PL<br><span class="dim">CUSTOMERS POOL' in c,
      'eng': 'ENG<br><span class="dim">US + UK + AU' in c,
      'nht_ch':'86,112' in c,
      'nht_de':'564,265' in c,
      'nht_pl':'231,840' in c,
      'nht_eng':'2,850,638' in c,
      'chamdigital':'28,000' in c,
    }
    print('CANON_VERIFY',v,checks)
    if not all(checks.values()): raise RuntimeError(checks)
    s,b=request(BUS)
    if s!=200 or not isinstance(b,dict) or not b.get('bus_cursor'): raise RuntimeError('bus cursor missing')
    ps,p=request(BUS,{'team':'GPT_CURSOR','project':'0','type':'DONE','what':f'HQ_GPT split customer pool geography on portfolio: 1% SALES POOL first, then CH / DE(+AT) / PL / ENG (US+UK+AU). BOARD_HTML v{v}. NHT 7-market reachable split = 86,112 / 564,265 / 231,840 / 2,850,638; ChamDigital CH = 28,000.','next':'Benchmark each initiative geography with measured reachable-market data as it reaches SELL; keep 4.1 Swiss-only until CH proof gate passes.','link':BOARD,'bus_cursor':b['bus_cursor']})
    if ps!=200 or not isinstance(p,dict) or not p.get('accepted'): raise RuntimeError(f'bus failed {ps} {p!r}')
    print('BUS_DONE',p.get('id'))
    rs,r=request(REDEPLOY,{'who':WHO,'why':f'BOARD_HTML v{v} market split customer pools'})
    if rs!=200 or not has_true(r,'serviceInstanceRedeploy'): raise RuntimeError(f'redeploy failed {rs} {r!r}')
    print('REDEPLOY_OK',r)

if __name__=='__main__': main()
