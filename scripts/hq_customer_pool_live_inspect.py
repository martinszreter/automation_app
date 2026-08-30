#!/usr/bin/env python3
import urllib.request as u
url='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'
with u.urlopen(url,timeout=30) as r:
    s=r.read().decode()
print('LEN',len(s))
for needle in ['<td class="id">4.1','150,000','28,000','28k','CUSTOMERS<br>POOL','1% SALES<br>POOL']:
    print('COUNT',needle,s.count(needle))
    starts=[]; pos=0
    while True:
        i=s.find(needle,pos)
        if i<0: break
        starts.append(i); pos=i+1
    for j,i in enumerate(starts[:5]):
        print('SNIP',needle,j,s[max(0,i-700):i+2600].replace('\n',' ')[:3300])
