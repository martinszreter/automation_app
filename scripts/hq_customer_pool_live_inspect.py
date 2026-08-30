#!/usr/bin/env python3
import urllib.request as u
url='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'
with u.urlopen(url,timeout=30) as r:
    s=r.read().decode()
print('LEN',len(s))
for needle in ['150,000','28,000','28k','Swiss Websites','ChamDigital','CUSTOMERS<br>POOL','1% SALES<br>POOL']:
    print('COUNT',needle,s.count(needle))
    i=s.find(needle)
    if i>=0: print('SNIP',needle,s[max(0,i-1200):i+2200].replace('\n',' ')[:3400])
