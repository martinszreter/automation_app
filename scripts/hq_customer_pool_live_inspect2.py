#!/usr/bin/env python3
import urllib.request as u
url='https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html'
with u.urlopen(url,timeout=30) as r: s=r.read().decode()
print('LEN',len(s))
for needle in ['<td class="id">4.1','<td class="id">5.1','Swiss Websites','chamdigital.ch','150,000','28,000','28k']:
    positions=[]; p=0
    while True:
        i=s.find(needle,p)
        if i<0: break
        positions.append(i); p=i+1
    print('COUNT',needle,len(positions),positions[:10])
    for j,i in enumerate(positions[:6]):
        print('SNIP',needle,j,s[max(0,i-900):i+3200].replace('\n',' ')[:4100])
