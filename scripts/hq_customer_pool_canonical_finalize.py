#!/usr/bin/env python3
import os,json,re,urllib.request as u
URL=os.environ['CANON_RW_URL']; WHO='HQ_GPT'; MARK='CUSTOMER POOL INTEGRITY FINAL 2026-08-30'

def req(p):
 r=u.urlopen(u.Request(URL,data=json.dumps(p).encode(),headers={'Content-Type':'application/json'}),timeout=60); raw=r.read().decode(); return json.loads(raw) if raw.strip() else None
def rows(k):
 x=req({'action':'read','keyValue':k});
 if not x: raise RuntimeError('EMPTY canon read '+k)
 return sorted(x,key=lambda r:int(r.get('version',0)),reverse=True)
def latest(k): return rows(k)[0]
def delete(i): req({'action':'delete','id':str(i)})
def ins(k,v,c,n): req({'action':'insert','file':k,'version':v,'content':c,'note':n,'updated_by':WHO})
def prune(k):
 rr=rows(k)
 for r in rr[3:]: delete(r['id'])
 print('PRUNE',k,[(int(r['version']),r['id']) for r in rows(k)[:3]])
def write(k,fn,note):
 b=latest(k); v=int(b['version'])+1; c=fn(b['content']); ins(k,v,c,note); rr=rows(k)
 same=[r for r in rr if int(r['version'])==v]
 if len(same)>1:
  ours=[r for r in same if r.get('updated_by')==WHO and MARK in r.get('content','')]; other=[r for r in same if r not in ours]
  if not other: raise RuntimeError('race cannot identify other '+k)
  v2=max(int(r['version']) for r in rr)+1; ins(k,v2,fn(other[0]['content']),note+' · race repair')
  for r in ours: delete(r['id'])
  if len([r for r in rows(k) if int(r['version'])==v2])>1: raise RuntimeError('second race '+k)
  v=v2
 prune(k); top=latest(k)
 if int(top['version'])!=v or MARK not in top['content']: raise RuntimeError('post-write verify '+k)
 print('WRITE_OK',k,'v',v,'id',top['id'],'len',len(top['content']))
 return v

def initiatives(c):
 if MARK in c: return c
 block='''## CUSTOMER POOL INTEGRITY FINAL 2026-08-30\n\n**No fake precision.** A numeric `Customers Pool` is allowed only when the initiative has a defined sellable offer / buyer or a deliberate buyer model. `TBD` means the buyer or offer is not defined enough to size honestly. `n/a` means internal engine, audience asset or research lane with no direct customer offer. Never inherit a pillar pool merely because an old initiative number starts with that pillar number. **1% Sales Pool is a benchmark, not a forecast, and overlapping buyer pools must never be summed as unique humans.**\n\nExplicit commercial benchmarks retained: 3.2 Leadmine 150,000 → 1,500 · 3.5a X Autopilot 80,000 → 800 · 3.5b booking family / vertical clones 3,732,855 → 37,329 shared · 3.5c Grokywood Autopilot 200,000 → 2,000 · 3.5d Custom Agents 40,000 → 400 · 3.4 39th Floor 5,000 → 50 model · 3.9 Zorbeck 40,000 → 400 model · **4.1 ChamDigital CH 28,000 → 280** · 5.2 optimizeyourkid 200,000 → 2,000 · wordblast 80,000 → 800 · 1.3 nieczytaj advertiser pool 8,000 → 80 · **1.8 Personal Brand sales 200 → 2 warm buyers**. Paper trading = 0. Undefined ideas show TBD until their buyer/offer is stated.\n\nRevenue floors remain: **CHF 10,000/day run-rate by 31 Dec 2026** and **CHF 1,000,000/month by 31 Dec 2027**. Build only exponential/self-serve or sellable-asset paths; DFY is a wedge.\n\n'''
 title='# 00_INITIATIVES — canonical tracker data\n\n'
 return title+block+c[len(title):] if c.startswith(title) else block+c

def decisions(c):
 if MARK in c: return c
 b='''2026-08-30 | HQ / ALL INITIATIVES | DECISION | CUSTOMER POOL INTEGRITY FINAL 2026-08-30. Numeric Customers Pool only for a defined commercial offer/buyer or explicit buyer model. Undefined buyer/offer = TBD. Internal engine, audience-only or research lane = n/a. Do not blindly inherit pillar pools from historic numbering. 1% Sales Pool remains a benchmark, not forecast; overlapping pools are not additive. Explicit 4.1 row = 28,000 CH base → 280 at 1%; Personal Brand sales = 200 warm reachable → 2 at 1%; paper trading = 0. This integrity rule supersedes broad inherited MODEL values on non-commercial/undefined rows. Revenue floors unchanged: CHF 10k/day Dec-2026; CHF 1M/mo Dec-2027.\n\nupdated_by=HQ_GPT'''
 return b+'\n\n-----\n'+c

def txt(x): return re.sub(r'<[^>]+>','',x).replace('&nbsp;',' ').replace('&amp;','&').strip()
def pool(i,name):
 n=name.lower()
 # Explicit commercial offers / buyer models first.
 if 'personal brands' in n or i=='1.8': return ('200','2','warm brand-sale buyers · explicit model')
 if 'leadmine' in n or 'smartlead' in n: return ('150,000','1,500','initiative model · overlaps NHT')
 if 'x autopilot' in n: return ('80,000','800','initiative model · posting SMEs/creators')
 if 'grokywood autopilot' in n: return ('200,000','2,000','initiative model · short-form creators')
 if 'custom ai agents' in n or i=='3.5d': return ('40,000','400','initiative model · DFY wedge')
 if 'restaurant reservation' in n or 'vertical clones' in n or i in ('3.5b','3.5b-V'): return ('3,732,855','37,329','shared booking family · do not sum clones')
 if 'corneroffice' in n or '39th floor' in n or i=='3.4': return ('5,000','50','buyer model · refine before scale')
 if 'zorbeck' in n or i=='3.9': return ('40,000','400','initiative model')
 if 'swiss websites' in n or 'chamdigital' in n or i=='4.1': return ('28,000','280','CH base · 12k / 28k / 55k range')
 if 'optimizeyourkid' in n: return ('200,000','2,000','parents ads-reachable · initiative model')
 if 'wordblast' in n: return ('80,000','800','parent buyer model')
 if 'nieczytaj' in n: return ('8,000','80','B2B advertisers · not readers')
 # Hard non-commercial / regulated gates.
 if 'tradebot' in n or 'blofin' in n or 'jane street' in n or (i in ('5','6') and 'trading' in n): return ('0','0','paper/research only')
 if 'x.com growth' in n or 'alex & filip' in n or 'city tech profiles' in n or '@martintradingch' in n or 'manifesto' in n or 'elon ecosystem wire' in n: return ('n/a','—','audience asset · no direct offer')
 if i=='2' or 'ai video multi-platform' in n: return ('n/a','—','internal/distribution engine · no direct offer')
 if 'x.com analytics tool' in n: return ('n/a','—','folded asset · no standalone offer')
 # Undefined commercial concepts must earn a number through buyer definition.
 if 'swisseasy' in n or 'life matrix' in n or 'homehount' in n or 'cash apps' in n or 'no human touch' in n or 'ai persona' in n or 'resourceful-recreation' in n or 'apps idea backlog' in n: return ('TBD','—','buyer/offer undefined · size before BUILD')
 return ('TBD','—','pool research required')
def cell(v,n): return f'<td class="prod" style="text-align:center"><b>{v}</b><br><span class="dim">{n}</span></td>'
def cham_row():
 return '''<tr><td class="id">4.1</td><td><span class="nm">Swiss Websites / ChamDigital &mdash; automated SME website factory</span><span class="ds">Preview-before-talk factory for Swiss SMEs. One reusable multilingual template/generator, keyed customer editor and automated preview &rarr; checkout &rarr; edit &rarr; publish path. Product quality is leverage only when it removes recurring human work.</span><div class="dnote"><b>SCALE NOTE:</b> CH high-priority pool model = 12k conservative / <b>28k base</b> / 55k aggressive. Switzerland proves the machine; DACH activates only after paid proof.</div></td><td class="domcol"><a href="https://www.chamdigital.ch/">www.chamdigital.ch</a> <span class="ok">PRIMARY</span><br><span class="dm">martinszreter/site-engine</span> <span class="ok">own repo + Railway</span></td><td><span class="draft">price pending final ratification</span></td><td>0</td><td class="prod" style="text-align:center"><b>28,000</b><br><span class="dim">CH base · realistic high-priority pool</span></td><td class="prod" style="text-align:center"><b>280</b><br><span class="dim">1% benchmark</span></td><td style="text-align:center;font-weight:700;background:#f4cccc">0</td><td>Private personalised previews + manual individual Swiss outreach after LIVE; self-serve/ads become the scale layer.</td><td class="yel"><div class="stw"><b>product quality gate</b><br><i>next: checkout + legal</i></div></td><td class="yel"><span class="rd">45%</span><span class="rdbar"><i style="width:45%;background:#DA291C"></i></span><div style="font-size:11px;color:#555;margin-top:5px;line-height:1.45">30 Aug stress score: checkout/legal/B&ouml;rlin hard gaps remain. Outbound locked until gate passes.</div></td><td>&#9733; ACTIVE 4.1 &mdash; build the reusable factory to the gate, then self-pay smoke test, then SELL. No bespoke-per-client trap.</td><td class="nx"><div><b style="font-size:10px;color:#888;letter-spacing:.5px">NEXT ACTION</b><br>Wire stranger checkout + real legal pages + remove B&ouml;rlin placeholders &rarr; re-score &rarr; self-pay &rarr; outbound</div></td></tr>'''
def board(c):
 marker='<h2><span class="k">Sorted by how big this can get, not by pillar &middot; column titles repeat in every tier</span>The portfolio</h2>'
 s=c.find(marker); e=c.find('<h2',s+len(marker)) if s>=0 else -1
 if s<0 or e<0: raise RuntimeError('main portfolio section missing')
 sec=c[s:e]
 def repl(m):
  row=m.group(0); cells=re.findall(r'<td(?:\s[^>]*)?>.*?</td>',row,flags=re.S)
  if len(cells)<11: return row
  i=txt(cells[0]); name=txt(cells[1]); a,b,n=pool(i,name); pc=cell(a,n); oc=cell(b,'1% benchmark' if b not in ('—','0') else ('paper gate' if b=='0' else 'not applicable'))
  if len(cells)==11: cells=cells[:5]+[pc,oc]+cells[5:]
  else: cells[5]=pc; cells[6]=oc
  return '<tr>'+''.join(cells)+'</tr>'
 sec=re.sub(r'<tr><td class="id">.*?</tr>',repl,sec,flags=re.S)
 # 4.1 was missing from the detailed ranked table. Insert it immediately after X Autopilot if absent.
 if '<td class="id">4.1</td>' not in sec:
  m=re.search(r'<tr><td class="id">3\.5a</td>.*?</tr>',sec,flags=re.S)
  if not m: raise RuntimeError('cannot place 4.1 detailed row')
  sec=sec[:m.end()]+'\n'+cham_row()+sec[m.end():]
 if '28,000' not in sec or '<td class="id">4.1</td>' not in sec or '>200</b>' not in sec: raise RuntimeError('final pool assertions failed')
 out=c[:s]+sec+c[e:]
 if MARK not in out: out=out.replace('<body><div class="wrap">','<body><div class="wrap"><!-- '+MARK+' -->',1)
 return out

def main():
 print('ASSETS_OK',latest('02_ASSETS')['version'])
 v1=write('00_INITIATIVES',initiatives,'Pool integrity: explicit commercial numbers only; TBD/n-a otherwise')
 v2=write('03_DECISIONS',decisions,'Pool integrity final; no fake inherited precision')
 v3=write('BOARD_HTML',board,'Add explicit 4.1 detailed row; correct non-commercial/TBD pools')
 print('DONE',{'00_INITIATIVES':v1,'03_DECISIONS':v2,'BOARD_HTML':v3})
if __name__=='__main__': main()
