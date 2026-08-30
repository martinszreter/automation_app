#!/usr/bin/env python3
import json, urllib.request as u

BOARD='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'
BOOT='https://portfolio-production-f01d.up.railway.app/bootmode.txt'
BUS='https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k'
REDEPLOY='https://startend.app.n8n.cloud/webhook/redeploy-portfolio-7k4q9x'
MARK='HQ_GPT_POOL_V67_DONE'

def get(url):
    with u.urlopen(url, timeout=30) as r:
        return r.status, r.read().decode()

def post(url,payload):
    req=u.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with u.urlopen(req,timeout=30) as r:
        raw=r.read().decode(); return r.status, json.loads(raw) if raw.strip() else None

def has_true(x,key):
    if isinstance(x,dict):
        if x.get(key) is True: return True
        return any(has_true(v,key) for v in x.values())
    if isinstance(x,list): return any(has_true(v,key) for v in x)
    return False

def main():
    bs,board=get(BOARD); ms,boot=get(BOOT)
    checks={
      'board_200':bs==200,
      'bootmode_canon':boot.strip()=='canon',
      'customers_pool':'CUSTOMERS<br>POOL' in board,
      'one_percent_pool':'1% SALES<br>POOL' in board,
      'leadmine_pool':'150,000' in board and '1,500' in board,
      'chamdigital_pool':'28,000' in board and '>280<' in board,
      'bear_2026':'CHF 10k' in board and '/day' in board and '31 DEC 2026' in board,
      'target_2027':'CHF 1M' in board and '/mo' in board and '31 DEC 2027' in board,
      'reconciliation':'POOL RECONCILIATION HQ_GPT 2026-08-30' in board,
    }
    print('LIVE_VERIFY',len(board),boot.strip(),checks)
    if not all(checks.values()):
        raise RuntimeError('live board verification failed: '+repr(checks))

    # Fresh bus cursor; if this exact completion is already there, this is the webhook-triggered redeploy and we stop.
    gs,g=get(BUS); data=json.loads(g)
    recent=data.get('recent',[])
    if any(MARK in (r.get('what') or '') for r in recent):
        print('GUARD existing bus DONE; skip duplicate bus/redeploy')
        return
    cursor=data['bus_cursor']
    what=(MARK+' · HQ_GPT reconciled the parallel customer-pool work and published exact CUSTOMERS POOL + 1% SALES POOL columns at project and detailed initiative level. '
          'Founder floors locked: CHF 10k/day run-rate by 31 Dec 2026 and CHF 1M/mo by 31 Dec 2027. Initiative-specific Grok values override broad inherited models; 1% is a benchmark, not a forecast. Canon: 01_STRATEGY v37 · 00_INITIATIVES v51 · 03_DECISIONS v148 · BOARD_HTML v67.')
    ps,p=post(BUS,{
      'team':'GPT_CURSOR','project':'0','type':'DONE','what':what,
      'next':'Keep 4.1 build lock: finish checkout/legal/product-quality gate. As each initiative reaches SELL, replace provisional pool models with measured reachable-pool and conversion data.',
      'link':BOARD,'bus_cursor':cursor
    })
    print('BUS_DONE',ps,p)
    if ps!=200 or not isinstance(p,dict) or not p.get('accepted'):
        raise RuntimeError('bus DONE rejected')

    rs,r=post(REDEPLOY,{'who':'HQ_GPT','why':'BOARD_HTML v67 customer pool + 1% sales pool publish'})
    print('REDEPLOY',rs,r)
    if rs!=200 or not has_true(r,'serviceInstanceRedeploy'):
        raise RuntimeError('official redeploy did not confirm serviceInstanceRedeploy=true')

if __name__=='__main__': main()
