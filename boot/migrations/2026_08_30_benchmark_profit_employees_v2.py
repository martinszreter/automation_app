from __future__ import annotations

import html
import json
import os
import re
import urllib.request
from typing import Any

CANON_URL=(os.environ.get('CANON_RW_URL') or 'https://startend.app.n8n.cloud/webhook/canon-rw-9k2x7m4q').strip()
UPDATED_BY='HQ_GPT'
TIMEOUT=60
BOARD_MARK='HQ_GPT_BENCHMARK_NETPROFIT_EMPLOYEES_V2_20260830'
DECISION_MARK='BENCHMARK_NETPROFIT_EMPLOYEES_V2_20260830'
OLD_START='<!-- HQ_GPT_BENCHMARK_WATCHLIST_20260830 -->'
OLD_END='<!-- /HQ_GPT_BENCHMARK_WATCHLIST_20260830 -->'
NEW_FORTUNE_START='<!-- HQ_GPT_FORTUNE50_NETPROFIT_EMPLOYEES_V2_20260830 -->'
NEW_FORTUNE_END='<!-- /HQ_GPT_FORTUNE50_NETPROFIT_EMPLOYEES_V2_20260830 -->'

EMP={
'Amazon':'≈1.56M','Walmart':'≈2.10M','UnitedHealth Group':'≈400k','Apple':'≈166k','Alphabet':'≈190k','CVS Health':'≈300k','Berkshire Hathaway':'≈392k','McKesson':'≈48k','ExxonMobil Holdings':'≈61k','Cencora':'≈46k','Microsoft':'≈228k','JPMorgan Chase':'≈318k','Costco Wholesale':'≈341k','Cigna Group':'≈72k','Cardinal Health':'≈50k','Nvidia':'≈36k','Meta Platforms':'≈78k','Elevance Health':'≈105k','Centene':'≈60k','Bank of America':'≈213k','Chevron':'≈46k','Ford Motor':'≈171k','General Motors':'≈156k','Citigroup':'≈227k','Home Depot':'≈470k','Fannie Mae':'≈8k','Kroger':'≈409k','Verizon Communications':'≈100k','Phillips 66':'≈14k','Marathon Petroleum':'≈18k','StoneX Group':'≈5k','State Farm Insurance':'≈96k','Freddie Mac':'≈8k','Humana':'≈65k','AT&T':'≈135k','Goldman Sachs Group':'≈49k','Comcast':'≈179k','Wells Fargo':'≈215k','Morgan Stanley':'≈83k','Valero Energy':'≈10k','Dell Technologies':'≈108k','Target':'≈440k','Tesla':'≈126k','Walt Disney':'≈189k','Johnson & Johnson':'≈140k','PepsiCo':'≈319k','Boeing':'≈172k','United Parcel Service':'≈490k','RTX':'≈180k','FedEx':'≈500k'}


def post(payload:dict[str,Any])->Any:
    # Compact UTF-8 is deliberate: BOARD_HTML is large and the canon webhook has a tight JSON parser ceiling.
    body=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    req=urllib.request.Request(CANON_URL,data=body,headers={'Content-Type':'application/json; charset=utf-8'},method='POST')
    with urllib.request.urlopen(req,timeout=TIMEOUT) as r:
        raw=r.read().decode('utf-8')
    return json.loads(raw or 'null')


def read_rows(key:str)->list[dict[str,Any]]:
    rows=post({'action':'read','keyValue':key})
    if not isinstance(rows,list) or not rows:
        raise SystemExit('STOP empty canon read '+key)
    return rows


def top(rows:list[dict[str,Any]])->dict[str,Any]:
    return max(rows,key=lambda r:int(r.get('version') or 0))


def insert(key:str,version:int,content:str,note:str)->Any:
    return post({'action':'insert','file':key,'version':version,'content':content,'note':note,'updated_by':UPDATED_BY})


def delete(row_id:Any)->Any:
    return post({'action':'delete','id':str(row_id)})


def clean(x:str)->str:
    x=re.sub(r'<br\s*/?>',' ',x,flags=re.I)
    x=re.sub(r'<[^>]+>','',x)
    return html.unescape(x).strip()


def profit_num(x:str)->float:
    m=re.search(r'-?\d+(?:\.\d+)?',x.replace(',',''))
    return float(m.group(0)) if m else float('-inf')


def find_fortune_rows(content:str)->list[tuple[str,str,str,str,str]]:
    pos=content.find('FORTUNE 500 — TOP 50 U.S. BY REVENUE')
    if pos<0:
        raise ValueError('specific Fortune top-50 title missing')
    ts=content.find('<tbody>',pos); te=content.find('</tbody>',ts)
    if ts<0 or te<0: raise ValueError('Fortune tbody missing')
    out=[]
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>',content[ts+7:te],flags=re.I|re.S):
        cells=re.findall(r'<td[^>]*>(.*?)</td>',tr,flags=re.I|re.S)
        if len(cells)==5:
            vals=tuple(clean(c) for c in cells)
            if vals[0].isdigit(): out.append(vals)
    if len(out)!=50: raise ValueError(f'Fortune rows parsed={len(out)}')
    return out


def small_watchlist()->str:
    rows=[
      ('Johnson & Johnson','2025','$94.193B','$26.804B','28.5%','≈140k','2031 north-star scale class'),
      ('Visa','FY2025','$40.000B','$20.058B','50.1%','≈34k','toll-road economics'),
      ('Tether','2025','n/a','>$10B through Q3-2025','n/a','≈200 est.','private; reserve/network economics'),
      ('Spotify','2025','€17.186B','€2.212B','12.9%','≈7.3k','global subscription/media platform'),
      ('Shopify','2025','$11.556B','$1.231B','10.7%','≈8.1k','commerce platform'),
      ('Telegram','2024 actual','$1.400B','$0.540B','38.6%','≈50 core est.','private, >1B users; latest reliable full-year actual'),
      ('HubSpot','2025','$3.130B','$0.0459B GAAP','1.5%','≈8.8k','SaaS/customer platform'),
      ('STARTEND','2026 current','CHF 0','pre-revenue · quantified costs only','n/a','≈1 human + AI/contractors','OUR LINE — update as we grow')]
    trs=''.join('<tr><td>'+('<b>'+html.escape(c)+'</b>' if c in {'Johnson & Johnson','STARTEND'} else html.escape(c))+'</td><td>'+html.escape(p)+'</td><td>'+html.escape(r)+'</td><td>'+html.escape(n)+'</td><td>'+html.escape(m)+'</td><td>'+html.escape(e)+'</td><td>'+html.escape(w)+'</td></tr>' for c,p,r,n,m,e,w in rows)
    return f'''<!-- {BOARD_MARK} --><h2 style="margin-top:4px">BENCHMARK WATCHLIST — REVENUE + NET PROFIT</h2><p class="dim" style="font-size:12px;margin-bottom:12px;line-height:1.5">Sorted by reported net profit, highest first. Employee counts are approximate latest public figures or private-company estimates. Mixed currencies are directional, not FX-normalized. STARTEND stays last so our line is always visible.</p><div class="scroll"><table style="table-layout:auto;min-width:1100px"><thead><tr><th>COMPANY</th><th>PERIOD</th><th>REVENUE</th><th>NET PROFIT</th><th>NET MARGIN</th><th>EMPLOYEES ≈</th><th>WHY WATCH</th></tr></thead><tbody>{trs}</tbody></table></div><!-- /{BOARD_MARK} -->'''


def fortune_block(rows:list[tuple[str,str,str,str,str]])->str:
    rows=sorted(rows,key=lambda r:profit_num(r[3]),reverse=True)
    trs=[]
    for rank,c,rev,prof,margin in rows:
        style=' style="border-left:4px solid var(--swiss)"' if c=='Johnson & Johnson' else ''
        trs.append(f'<tr{style}><td>{html.escape(rank)}</td><td>{html.escape(c)}</td><td>{html.escape(rev)}</td><td><b>{html.escape(prof)}</b></td><td>{html.escape(margin)}</td><td>{html.escape(EMP.get(c,"≈TBD"))}</td></tr>')
    return f'''{NEW_FORTUNE_START}<h2 style="margin-top:28px">FORTUNE 500 — TOP 50 U.S. BY REVENUE (2026 LIST; SORTED BY NET PROFIT)</h2><p class="dim" style="font-size:11px;margin-bottom:12px">Same Fortune revenue-top-50 universe; first column preserves original Fortune revenue rank. Rows below are sorted by net profit. Employee counts are approximate latest reported headcount.</p><div class="scroll"><table style="table-layout:auto;min-width:1050px"><thead><tr><th>FORTUNE REV RANK</th><th>COMPANY</th><th>REVENUE USD B</th><th>NET PROFIT USD B</th><th>NET MARGIN</th><th>EMPLOYEES ≈</th></tr></thead><tbody>{''.join(trs)}</tbody></table></div><p class="dim" style="font-size:11px;margin-top:12px;font-style:italic">Baseline: Fortune 500 2026 / FY2025 data already carried by this board. Headcount is approximate; refresh with annual-report cycles.</p><div class="dark" style="background:var(--black);border-left:5px solid var(--swiss);margin-top:24px"><h3 style="color:var(--swiss);font-family:'Didot','Bodoni MT',Georgia,serif;font-weight:400;font-size:20px;margin:0 0 8px">FOUNDER NORTH STAR — PERMANENT</h3><p style="color:#fff;margin:0;line-height:1.65;font-size:13px">Build STARTEND into the Johnson &amp; Johnson scale class: roughly $94B annual revenue and $27B annual net profit on the current benchmark. Revenue is not enough; profit, margin and low human-labour scaling matter. Target, not forecast. Keep this benchmark permanently visible.</p></div>{NEW_FORTUNE_END}'''


def board_done(c:str)->bool:
    return (BOARD_MARK in c and NEW_FORTUNE_START in c and 'Where the money is' not in c and c.count('EMPLOYEES ≈')>=2 and 'OUR LINE — update as we grow' in c and 'SORTED BY NET PROFIT' in c and 'CHF 10B/year' in c and 'STARTEND Commerce OS' in c and '1% sales pool &amp; revenue' in c)


def transform_board(c:str)->str:
    if board_done(c): return c
    rows=find_fortune_rows(c)
    # Remove any complete prior V1/V2 transformed blocks so retry is safe.
    pairs=[
      ('<!-- HQ_GPT_BENCHMARK_NETPROFIT_EMPLOYEES_20260830 -->','<!-- /HQ_GPT_BENCHMARK_NETPROFIT_EMPLOYEES_20260830 -->'),
      (f'<!-- {BOARD_MARK} -->',f'<!-- /{BOARD_MARK} -->'),
      ('<!-- HQ_GPT_FORTUNE50_NETPROFIT_EMPLOYEES_20260830 -->','<!-- /HQ_GPT_FORTUNE50_NETPROFIT_EMPLOYEES_20260830 -->'),
      (NEW_FORTUNE_START,NEW_FORTUNE_END)]
    for s,e in pairs:
        while s in c and e in c:
            a=c.index(s); b=c.index(e,a)+len(e); c=c[:a]+c[b:]
    # Replace old combined bottom benchmark block with Fortune-only block.
    if OLD_START not in c or OLD_END not in c: raise ValueError('old bottom benchmark block missing')
    a=c.index(OLD_START); b=c.index(OLD_END,a)+len(OLD_END)
    c=c[:a]+fortune_block(rows)+c[b:]
    # Replace the verbose Where-the-money-is block, bounded by Portfolio scale map.
    wp=c.find('Where the money is')
    if wp<0: raise ValueError('Where the money is missing')
    a=c.rfind('<h2',0,wp)
    np=c.find('Portfolio scale map',wp)
    b=c.rfind('<h2',wp,np+1) if np>=0 else -1
    if a<0 or b<=a: raise ValueError('unsafe Where-the-money-is bounds')
    c=c[:a]+small_watchlist()+'\n'+c[b:]
    for token in ['31 DEC 2030','CHF 10B/year','1% sales pool &amp; revenue','STARTEND Commerce OS','4.2']:
        if token not in c: raise ValueError('preservation failure '+token)
    if not board_done(c): raise ValueError('structural verification failed after transform')
    return c


def decision_done(c:str)->bool:
    return DECISION_MARK in c


def transform_decision(c:str)->str:
    if decision_done(c): return c
    entry='2026-08-30 | HQ BOARD | FOUNDER DECISION | '+DECISION_MARK+'. Benchmark watchlist moved to the former Where-the-money-is position; verbose Where-the-money-is block removed. Both benchmark tables carry approximate employee counts and are sorted by net profit, while preserving Fortune revenue rank. STARTEND is permanently the final watchlist row. Hard target ladder unchanged; 2030 remains CHF 10B/year. 1% sales pool and 4.2 Commerce OS unchanged.\n\nupdated_by=HQ_GPT\n\n'
    return entry+c


def prune(key:str)->None:
    rows=sorted(read_rows(key),key=lambda r:(int(r.get('version') or 0),int(r.get('id') or 0)),reverse=True)
    for r in rows[3:]: delete(r.get('id'))


def write_key(key:str,transform,done,note:str)->dict[str,Any]:
    # Immediate re-read before write.
    rows=read_rows(key); base=top(rows); content=base.get('content') or ''
    if done(content):
        print('NOOP',key,base.get('version'),'structure-present',flush=True); prune(key); return top(read_rows(key))
    new=transform(content); v=int(base.get('version') or 0)+1
    print('INSERT',key,'from',base.get('version'),'to',v,'chars',len(new),flush=True)
    insert(key,v,new,note)
    # Immediate re-read and race handling.
    after=read_rows(key); same=[r for r in after if int(r.get('version') or 0)==v]
    ours=[r for r in same if r.get('updated_by')==UPDATED_BY and done(r.get('content') or '')]
    if len(same)>1:
        other=[r for r in same if r not in ours]
        if not other: raise RuntimeError('race without identifiable competitor '+key)
        competitor=max(other,key=lambda r:int(r.get('id') or 0))
        merged=transform(competitor.get('content') or '')
        nv=max(int(r.get('version') or 0) for r in after)+1
        insert(key,nv,merged,note+' · race remerge')
        for r in ours: delete(r.get('id'))
        after=read_rows(key)
    current=top(after)
    if not done(current.get('content') or ''): raise RuntimeError('canonical structural verification failed '+key)
    prune(key); return top(read_rows(key))


def verify(c:str)->dict[str,Any]:
    pos=c.find('FORTUNE 500 — TOP 50 U.S. BY REVENUE (2026 LIST; SORTED BY NET PROFIT)')
    ts=c.find('<tbody>',pos); te=c.find('</tbody>',ts)
    fr=[]
    if pos>=0 and ts>=0 and te>=0:
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>',c[ts+7:te],flags=re.I|re.S):
            cells=re.findall(r'<td[^>]*>(.*?)</td>',tr,flags=re.I|re.S)
            if len(cells)==6 and clean(cells[0]).isdigit(): fr.append(tuple(clean(x) for x in cells))
    profits=[profit_num(r[3]) for r in fr]
    return {'marker':BOARD_MARK in c,'where_money':c.count('Where the money is'),'employee_headers':c.count('EMPLOYEES ≈'),'startend_row':'OUR LINE — update as we grow' in c,'fortune_rows':len(fr),'fortune_sorted':profits==sorted(profits,reverse=True),'target_2030':'31 DEC 2030' in c and 'CHF 10B/year' in c,'one_pct':'1% sales pool &amp; revenue' in c,'commerce_4_2':'STARTEND Commerce OS' in c and '4.2' in c}


def main()->None:
    b=write_key('BOARD_HTML',transform_board,board_done,'Benchmark tables: net-profit sort + approximate employees; move watchlist up; preserve targets/1%/4.2')
    d=write_key('03_DECISIONS',transform_decision,decision_done,'Benchmark net-profit/employee diff completed; protected target/1%/4.2 unchanged')
    checks=verify(b.get('content') or '')
    if not (checks['marker'] and checks['where_money']==0 and checks['employee_headers']>=2 and checks['startend_row'] and checks['fortune_rows']==50 and checks['fortune_sorted'] and checks['target_2030'] and checks['one_pct'] and checks['commerce_4_2']): raise RuntimeError('final verify '+repr(checks))
    print(json.dumps({'ok':True,'board':{'version':b.get('version'),'id':b.get('id'),**checks},'decisions':{'version':d.get('version'),'id':d.get('id'),'marker':DECISION_MARK in (d.get('content') or '')}},ensure_ascii=False),flush=True)

if __name__=='__main__': main()
