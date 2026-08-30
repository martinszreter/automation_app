#!/usr/bin/env python3
import json,re,urllib.request as u
BOARD='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'; BOOT='https://portfolio-production-f01d.up.railway.app/bootmode.txt'; BUS='https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k'; REDEPLOY='https://startend.app.n8n.cloud/webhook/redeploy-portfolio-7k4q9x'; MARK='HQ_GPT_POOL_V68_FINAL_DONE'
def get(url):
 with u.urlopen(url,timeout=30) as r: return r.status,r.read().decode()
def post(url,p):
 q=u.Request(url,data=json.dumps(p).encode(),headers={'Content-Type':'application/json'});
 with u.urlopen(q,timeout=30) as r:
  raw=r.read().decode(); return r.status,json.loads(raw) if raw.strip() else None
def has_true(x,k):
 if isinstance(x,dict): return x.get(k) is True or any(has_true(v,k) for v in x.values())
 if isinstance(x,list): return any(has_true(v,k) for v in x)
 return False
def row(board,i):
 m=re.search(r'<tr><td class="id">'+re.escape(i)+r'</td>.*?</tr>',board,flags=re.S); return m.group(0) if m else ''
def main():
 bs,b=get(BOARD); _,boot=get(BOOT); r41=row(b,'4.1'); r32=row(b,'3.2'); r18=row(b,'1.8'); r5=row(b,'5')
 checks={
  'board_200':bs==200,'bootmode_canon':boot.strip()=='canon',
  'project_header':'CUSTOMERS<br>POOL' in b and '1% SALES<br>POOL' in b,
  'detailed_4.1':bool(r41) and '28,000' in r41 and '>280</b>' in r41,
  'leadmine':bool(r32) and '150,000' in r32 and '>1,500</b>' in r32,
  'personal_brand':bool(r18) and '>200</b>' in r18 and '>2</b>' in r18,
  'paper_trading':bool(r5) and '>0</b>' in r5 and 'paper/research only' in r5,
  'bear_2026':'CHF 10k' in b and '/day' in b and '31 DEC 2026' in b,
  'target_2027':'CHF 1M' in b and '/mo' in b and '31 DEC 2027' in b,
  'integrity_marker':'CUSTOMER POOL INTEGRITY FINAL 2026-08-30' in b,
 }
 print('LIVE_VERIFY',len(b),boot.strip(),checks)
 if not all(checks.values()): raise RuntimeError('live verify failed '+repr(checks))
 _,raw=get(BUS); data=json.loads(raw)
 if any(MARK in (x.get('what') or '') for x in data.get('recent',[])):
  print('GUARD bus DONE exists; skip duplicate redeploy'); return
 ps,p=post(BUS,{'team':'GPT_CURSOR','project':'0','type':'DONE','what':MARK+' · HQ_GPT published portfolio-wide Customers Pool + 1% Sales Pool benchmark logic. Canon final: 00_INITIATIVES v52 · 03_DECISIONS v149 · BOARD_HTML v68; 01_STRATEGY v37 already carries the revenue/exponential doctrine. Explicit 4.1 detailed row = 28,000 → 280; Leadmine 150,000 → 1,500; 3.5b booking family 3,732,855 → 37,329 shared; Personal Brand sales 200 → 2; paper trading 0. Undefined buyer/offer = TBD and internal/audience/research = n/a so we do not fabricate scale. Floors: CHF 10k/day by 31 Dec 2026; CHF 1M/mo by 31 Dec 2027. 1% is benchmark, not forecast.','next':'Current execution lock stays 4.1: finish stranger checkout + legal + Börlin hard gaps, re-score product gate, self-pay smoke test, then SELL. For every other initiative, replace MODEL/TBD pool with measured reachable pool when the buyer/offer is validated.','link':BOARD,'bus_cursor':data['bus_cursor']})
 print('BUS_DONE',ps,p)
 if ps!=200 or not isinstance(p,dict) or not p.get('accepted'): raise RuntimeError('bus rejected')
 rs,r=post(REDEPLOY,{'who':'HQ_GPT','why':'BOARD_HTML v68 Customers Pool + 1% Sales Pool final'})
 print('REDEPLOY',rs,r)
 if rs!=200 or not has_true(r,'serviceInstanceRedeploy'): raise RuntimeError('redeploy confirmation missing')
if __name__=='__main__': main()
