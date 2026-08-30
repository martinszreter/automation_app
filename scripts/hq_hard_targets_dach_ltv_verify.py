#!/usr/bin/env python3
import urllib.request as u
BOARD='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'
BOOT='https://portfolio-production-f01d.up.railway.app/bootmode.txt'
def get(url):
    with u.urlopen(url,timeout=35) as r: return r.status,r.read().decode()
bs,b=get(BOARD); ms,m=get(BOOT)
checks={
 'board_200':bs==200,
 'bootmode_canon':m.strip()=='canon',
 'target_marker':'HARD_TARGETS_DACH_LTV_20260830' in b,
 'target_top':0<=b.find('HARD_TARGETS_DACH_LTV_20260830')<b.find('Portfolio scale map'),
 '2026':'CHF 10k/day' in b and 'CHF 300k' in b,
 '2027':'CHF 100k/day' in b and 'CHF 3M' in b,
 '2028':'CHF 1M/day' in b and 'CHF 30M' in b,
 'anti_gaming':'trailing-30d collected' in b,
 'scale_table':'Portfolio scale map' in b and '1% SALES<br>POOL' in b and 'DE (+AT)' in b,
 'ai_table':'AI operating map' in b,
 'old_overloaded_heading':'Project split across the AI teams' not in b,
 'dach_ltv':'DACH lifetime SME engine' in b and 'LAND ONCE' in b and 'Reuse 3.5b patterns' in b,
 'critical_mode':'no yes-by-default' in b and 'CRITICAL CHECK' in b,
 '95_not_fact':'95% after the website' in b and 'not evidence' in b,
 'old_2027_current':'2027 = 1M/month' not in b and 'CHF 1M/mo by 31 Dec 2027' not in b,
}
print('LIVE_VERIFY',len(b),m.strip(),checks)
if not all(checks.values()): raise RuntimeError('live verification failed '+repr(checks))
