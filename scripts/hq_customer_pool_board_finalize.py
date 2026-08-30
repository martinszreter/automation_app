#!/usr/bin/env python3
import os,json,re,urllib.request as u
URL=os.environ['CANON_RW_URL']; WHO='HQ_GPT'; MARK='POOL BOARD FINALIZE HQ_GPT 2026-08-30'
PROJECT={'1':('88,000','880','shared X/brand buyer pool · inherited MODEL'),'2':('200,000','2,000','shared Grokywood/creator pool · inherited MODEL'),'3':('3,732,855','37,329','shared NHT reachable SME pool · inherited MODEL'),'4':('28,000','280','ChamDigital CH base pool · inherited MODEL'),'5':('280,000','2,800','shared mobile parent/consumer pool · inherited MODEL'),'6':('0','0','paper-only'),'7':('0','—','multiplier lane · not a product'),'8':('0','0','internal red-team · not a product')}
def req(p):
 r=u.urlopen(u.Request(URL,data=json.dumps(p).encode(),headers={'Content-Type':'application/json'}),timeout=60); raw=r.read().decode(); return json.loads(raw) if raw.strip() else None
def rows(k):
 x=req({'action':'read','keyValue':k});
 if not x: raise RuntimeError('EMPTY '+k)
 return sorted(x,key=lambda r:int(r.get('version',0)),reverse=True)
def latest(k): return rows(k)[0]
def delete(i): req({'action':'delete','id':str(i)})
def text(x): return re.sub(r'<[^>]+>','',x).replace('&nbsp;',' ').replace('&amp;','&').strip()
def proj(i):
 if i=='3.5c' or i.startswith('2'): return '2'
 for p in ['1','3','4','5','6','7','8']:
  if i.startswith(p): return p
 return None
def pool(i,name):
 n=name.lower()
 if 'leadmine' in n or 'smartlead' in n: return ('150,000','1,500','initiative model · overlaps NHT')
 if 'x autopilot' in n: return ('80,000','800','initiative model · posting SMEs/creators')
 if 'grokywood autopilot' in n: return ('200,000','2,000','initiative model · short-form creators')
 if 'custom' in n and 'agent' in n: return ('40,000','400','initiative model · DFY wedge')
 if 'restaurant' in n or 'booking' in n or i=='3.5b': return ('3,732,855','37,329','booking family · 10 verticals × 7 markets')
 if '39th floor' in n or i=='3.4': return ('5,000','50','initiative model · buyer still refining')
 if 'zorbeck' in n or i=='3.9': return ('40,000','400','initiative model')
 if 'swiss website' in n or 'chamdigital' in n: return ('28,000','280','ChamDigital CH base · 12k/28k/55k range')
 if 'optimizeyourkid' in n: return ('200,000','2,000','initiative model · parents ads-reachable')
 if 'wordblast' in n: return ('80,000','800','initiative model')
 if 'nieczytaj' in n: return ('8,000','80','B2B advertisers · not readers')
 if 'personal brand' in n: return ('200','2','warm brand-sale network')
 if 'tradebot' in n: return ('0','0','paper-only gate')
 p=proj(i); return PROJECT.get(p,('TBD','—','pool refinement pending'))
def cell(v,n): return f'<td class="prod" style="text-align:center"><b>{v}</b><br><span class="dim">{n}</span></td>'
def transform(c):
 marker='<h2><span class="k">Sorted by how big this can get, not by pillar &middot; column titles repeat in every tier</span>The portfolio</h2>'
 s=c.find(marker); e=c.find('<h2',s+len(marker)) if s>=0 else -1
 if s<0 or e<0: raise RuntimeError('portfolio section not found')
 sec=c[s:e]
 old='<tr><th>#</th><th>STREAM</th><th>DOMAIN</th><th>PRICE</th><th>CUST</th><th>TODAY CHF</th><th>CHANNEL / ADVERT</th><th>STAGE</th><th>READY %</th><th>STATUS</th><th>NEXT</th></tr>'
 new='<tr><th>#</th><th>STREAM</th><th>DOMAIN</th><th>PRICE</th><th>CUST</th><th>CUSTOMERS<br>POOL</th><th>1% SALES<br>POOL</th><th>TODAY CHF</th><th>CHANNEL / ADVERT</th><th>STAGE</th><th>READY %</th><th>STATUS</th><th>NEXT</th></tr>'
 sec=sec.replace(old,new)
 def repl(m):
  row=m.group(0); cells=re.findall(r'<td(?:\s[^>]*)?>.*?</td>',row,flags=re.S)
  if len(cells)<11: return row
  iid=text(cells[0]); name=text(cells[1]); a,b,n=pool(iid,name); pc=cell(a,n); oc=cell(b,'benchmark')
  if len(cells)==11: cells=cells[:5]+[pc,oc]+cells[5:]
  else: cells[5]=pc; cells[6]=oc
  return '<tr>'+''.join(cells)+'</tr>'
 sec=re.sub(r'<tr><td class="id">.*?</tr>',repl,sec,flags=re.S)
 sec=sec.replace('colspan="11"','colspan="13"')
 out=c[:s]+sec+c[e:]
 if '28,000' not in sec or '150,000' not in sec or '3,732,855' not in sec: raise RuntimeError('required initiative pools absent after transform')
 if MARK not in out: out=out.replace('<body><div class="wrap">','<body><div class="wrap"><!-- '+MARK+' -->',1)
 return out
def write():
 base=latest('BOARD_HTML'); v=int(base['version'])+1; c=transform(base['content'])
 req({'action':'insert','file':'BOARD_HTML','version':v,'content':c,'note':'Finalize Customers Pool + 1% Sales Pool on every detailed initiative row','updated_by':WHO})
 rr=rows('BOARD_HTML'); same=[r for r in rr if int(r['version'])==v]
 if len(same)>1:
  ours=[r for r in same if r.get('updated_by')==WHO and MARK in r.get('content','')]; other=[r for r in same if r not in ours]
  if not other: raise RuntimeError('race unresolved')
  v2=max(int(r['version']) for r in rr)+1
  req({'action':'insert','file':'BOARD_HTML','version':v2,'content':transform(other[0]['content']),'note':'Finalize pool columns · race repair','updated_by':WHO})
  for r in ours: delete(r['id'])
  v=v2
 rr=rows('BOARD_HTML')
 if len([r for r in rr if int(r['version'])==v])>1: raise RuntimeError('second race')
 for r in rr[3:]: delete(r['id'])
 top=latest('BOARD_HTML')
 if int(top['version'])!=v or MARK not in top['content']: raise RuntimeError('postwrite verify failed')
 print('WRITE_OK BOARD_HTML v',v,'id',top['id'],'len',len(top['content']),'28k',top['content'].count('28,000'),'headers',top['content'].count('CUSTOMERS<br>POOL'))
if __name__=='__main__':
 print('ASSETS_OK',latest('02_ASSETS')['version']); write()
