#!/usr/bin/env python3
import os, json, re, urllib.request as u

URL=os.environ['CANON_RW_URL']
WHO='HQ_GPT'
MARK='POOL RECONCILIATION HQ_GPT 2026-08-30'
OLD_MARK='## CUSTOMER POOL SCALE DOCTRINE 2026-08-30'

PROJECT = {
 '1':('88,000','880','shared X/brand buyer pool'),
 '2':('200,000','2,000','shared Grokywood/creator pool'),
 '3':('3,732,855','37,329','shared NHT reachable SME pool'),
 '4':('28,000','280','ChamDigital CH base pool'),
 '5':('280,000','2,800','shared mobile parent/consumer pool'),
 '6':('0','0','paper-only'),
 '7':('0','—','multiplier lane · not a product'),
 '8':('0','0','internal red-team · not a product'),
}

def req(p):
 r=u.urlopen(u.Request(URL,data=json.dumps(p).encode(),headers={'Content-Type':'application/json'}),timeout=60)
 raw=r.read().decode(); return json.loads(raw) if raw.strip() else None

def rows(k):
 x=req({'action':'read','keyValue':k})
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
 b=latest(k); v=int(b['version'])+1; c=fn(b['content']); ins(k,v,c,note)
 rr=rows(k); same=[r for r in rr if int(r['version'])==v]
 if len(same)>1:
  ours=[r for r in same if r.get('updated_by')==WHO and MARK in r.get('content','')]
  other=[r for r in same if r not in ours]
  if not other: raise RuntimeError('race cannot identify other '+k)
  v2=max(int(r['version']) for r in rr)+1
  ins(k,v2,fn(other[0]['content']),note+' · race repair')
  for r in ours: delete(r['id'])
  if len([r for r in rows(k) if int(r['version'])==v2])>1: raise RuntimeError('second race '+k)
  v=v2
 prune(k); top=latest(k)
 if int(top['version'])!=v or MARK not in top.get('content',''): raise RuntimeError('verify fail '+k)
 print('WRITE_OK',k,'v',v,'id',top['id'],'len',len(top['content']))
 return v

def remove_hq_gpt_duplicate(c, anchor):
 s=c.find(OLD_MARK)
 if s<0: return c
 # Include any leading '## ' line beginning exactly at s; cut until the other writer's preserved anchor.
 e=c.find(anchor,s)
 if e<0: raise RuntimeError('cannot find anchor while removing duplicate')
 return c[:s]+c[e:]

def strategy(c):
 c=remove_hq_gpt_duplicate(c,'BEAR TARGETS + POOL COLUMNS')
 if MARK in c: return c
 pre=(MARK+' — parallel-write merge. The initiative-specific pools already written by HQ_GROK are canonical wherever they are tighter than a project-level pool. Unlisted commercial initiatives inherit their project pool only as a provisional MODEL until research or live acquisition data replaces it. 1% Sales Pool remains a benchmark, not a forecast. Revenue floors unchanged: CHF 10k/day by 31 Dec 2026; CHF 1M/mo by 31 Dec 2027.\n\n')
 return pre+c

def initiatives(c):
 c=remove_hq_gpt_duplicate(c,'# 00_INITIATIVES — canonical tracker data')
 if MARK in c: return c
 pre=('## '+MARK+'\n\nParallel-write merge: preserve the initiative-specific pool model below. **Explicit initiative values override shared project pools. Any commercial row not explicitly listed inherits its project pool provisionally and must refine it with research / measured acquisition data by SELL.** 1% is a benchmark, never a promise, and overlapping rows must not be summed as unique buyers. The detailed HQ portfolio table now displays these values on every initiative row.\n\n')
 # Keep the existing canonical title first if it is at the start.
 title='# 00_INITIATIVES — canonical tracker data\n\n'
 if c.startswith(title): return title+pre+c[len(title):]
 return pre+c

def decisions(c):
 if MARK in c: return c
 b=(f'2026-08-30 | HQ / ALL COMMERCIAL INITIATIVES | DECISION | {MARK}. Parallel HQ_GROK/HQ_GPT writes reconciled. HQ_GROK initiative-specific pools are retained wherever tighter; HQ_GPT broader project assumptions are RETIRED where they differ. Unlisted initiative rows may inherit a shared project pool only as provisional MODEL v1 and must replace it with research/measured acquisition data by SELL. Board must show exact columns CUSTOMERS POOL and 1% SALES POOL both in the project split and detailed initiative portfolio. 1% = benchmark, not forecast; buyer overlap is not additive. Floors stand: CHF 10k/day run-rate by 31 Dec 2026 and CHF 1M/mo by 31 Dec 2027. Exponential-only / DFY-as-wedge / reusable-automation doctrine unchanged. Artifact: artifacts/HQ_CUSTOMER_POOL_SCALE_2026-08-30.md.\n\nupdated_by=HQ_GPT')
 return b+'\n\n-----\n'+c

def text(x): return re.sub(r'<[^>]+>','',x).replace('&nbsp;',' ').replace('&amp;','&').strip()

def proj(i):
 if i=='3.5c' or i.startswith('2'): return '2'
 for p in ['1','3','4','5','6','7','8']:
  if i.startswith(p): return p
 return None

def specific(i,name):
 n=name.lower()
 if 'leadmine' in n or 'smartlead' in n: return ('150,000','1,500','initiative model · overlaps NHT')
 if 'x autopilot' in n: return ('80,000','800','initiative model · posting SMEs/creators')
 if 'grokywood autopilot' in n: return ('200,000','2,000','initiative model · short-form creators')
 if 'custom' in n and 'agent' in n: return ('40,000','400','initiative model · DFY wedge')
 if 'restaurant' in n or i=='3.5b': return ('3,732,855','37,329','booking family · 10 verticals × 7 markets')
 if '39th floor' in n or i=='3.4': return ('5,000','50','initiative model · buyer still refining')
 if 'zorbeck' in n or i=='3.9': return ('40,000','400','initiative model')
 if 'swiss website' in n or 'chamdigital' in n or i=='4.1': return ('28,000','280','ChamDigital CH base · 12k/28k/55k range')
 if 'optimizeyourkid' in n: return ('200,000','2,000','initiative model · parents ads-reachable')
 if 'wordblast' in n: return ('80,000','800','initiative model')
 if 'nieczytaj' in n or i=='1.3': return ('8,000','80','B2B advertisers · not readers')
 if 'personal brand' in n or i=='1.8': return ('200','2','warm brand-sale network')
 if 'tradebot' in n or i=='6': return ('0','0','paper-only gate')
 p=proj(i)
 if p in PROJECT:
  a,b,d=PROJECT[p]; return (a,b,d+' · inherited MODEL')
 return ('TBD','—','pool refinement pending')

def cell(v,note): return f'<td class="prod" style="text-align:center"><b>{v}</b><br><span class="dim">{note}</span></td>'

def project_table(c):
 s=c.find('<h2><span class="k">Who thinks, who executes, per project</span>Project split across the AI teams</h2>')
 if s<0: raise RuntimeError('project table marker missing')
 e=c.find('<div class="card"><b>How Marcin works with them</b>',s)
 if e<0: raise RuntimeError('project table end missing')
 sec=c[s:e]
 sec=sec.replace('<th>POOL</th><th>1% SALES</th>','<th>CUSTOMERS<br>POOL</th><th>1% SALES<br>POOL</th>')
 sec=sec.replace('<th>CUSTOMERS POOL</th><th>1% SALES POOL</th>','<th>CUSTOMERS<br>POOL</th><th>1% SALES<br>POOL</th>')
 # Remove the broad HQ_GPT card from the parallel write; keep GROK's POOL · 1% SALES card.
 sec=re.sub(r'<div class="card" style="border-left-color:#DA291C"><b>CUSTOMER POOL SCALE RULE</b>.*?</div>\s*','',sec,flags=re.S)
 return c[:s]+sec+c[e:]

def main_table(c):
 marker='<h2><span class="k">Sorted by how big this can get, not by pillar &middot; column titles repeat in every tier</span>The portfolio</h2>'
 s=c.find(marker)
 if s<0: raise RuntimeError('main portfolio missing')
 e=c.find('<h2',s+len(marker)); e=e if e>=0 else len(c)
 sec=c[s:e]
 # Ensure exact headers.
 sec=sec.replace('<th>CUSTOMERS<br>POOL</th><th>1% SALES<br>POOL</th>','<th>CUSTOMERS<br>POOL</th><th>1% SALES<br>POOL</th>')
 def repl(m):
  row=m.group(0); cells=re.findall(r'<td(?:\s[^>]*)?>.*?</td>',row,flags=re.S)
  if len(cells)!=13: return row
  iid=text(cells[0]); name=text(cells[1]); a,b,n=specific(iid,name)
  return '<tr>'+''.join(cells[:5]+[cell(a,n),cell(b,'benchmark')]+cells[7:])+'</tr>'
 sec=re.sub(r'<tr><td class="id">.*?</tr>',repl,sec,flags=re.S)
 return c[:s]+sec+c[e:]

def ladder_html():
 return '''<h2><span class="k">Target, not forecast &middot; pool × conversion × ARPU</span>Revenue ladder</h2>
<div class="dark"><div class="label" style="color:#9A968D;margin-bottom:14px">Rung 1 = collected proof · Bear 2026 = 10k/day run-rate · 2027 = 1M/month</div><div style="display:flex;flex-wrap:wrap;gap:10px">
<div style="flex:1 1 175px;background:#2A0E0C;border-radius:4px;padding:16px;border-left:5px solid #DA291C"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#DA291C">TODAY</div><div class="display" style="font-size:36px;line-height:1.02;color:#fff;margin-top:6px">CHF 0</div><div style="font-size:12px;font-weight:700;color:#DA291C;margin-top:8px">stranger revenue</div></div>
<div style="flex:1 1 175px;background:#131317;border-radius:4px;padding:16px;border-left:5px solid #DA291C"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#5f5c56">PROOF RUNG</div><div class="display" style="font-size:36px;line-height:1.02;color:#fff;margin-top:6px">CHF 10k</div><div class="display" style="font-size:23px;line-height:1.1;color:#DA291C;margin-top:10px">30 SEP 2026</div><div style="font-size:12px;color:#9A968D;margin-top:5px">collected revenue</div></div>
<div style="flex:1 1 205px;background:#131317;border-radius:4px;padding:16px;border-left:5px solid #DA291C"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#DA291C">BEAR FLOOR</div><div class="display" style="font-size:34px;line-height:1.02;color:#fff;margin-top:6px">CHF 10k<span style="font-size:19px">/day</span></div><div class="display" style="font-size:23px;line-height:1.1;color:#DA291C;margin-top:10px">31 DEC 2026</div><div style="font-size:12px;color:#9A968D;margin-top:5px">~300k/mo · 3,750 customers @ CHF80 blended ARPU · <b style="color:#fff">0.10%</b> of 3.73M reachable SMEs</div></div>
<div style="flex:1 1 205px;background:#131317;border-radius:4px;padding:16px;border-left:5px solid #ECE8DF"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#ECE8DF">2027 TARGET</div><div class="display" style="font-size:34px;line-height:1.02;color:#fff;margin-top:6px">CHF 1M<span style="font-size:19px">/mo</span></div><div class="display" style="font-size:23px;line-height:1.1;color:#ECE8DF;margin-top:10px">31 DEC 2027</div><div style="font-size:12px;color:#9A968D;margin-top:5px">12,500 customers @ CHF80 blended ARPU · <b style="color:#fff">0.33%</b> of 3.73M reachable SMEs</div></div>
<div style="flex:1 1 165px;background:#131317;border-radius:4px;padding:16px;border-left:5px solid #ECE8DF"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#5f5c56">RUNG 4</div><div class="display" style="font-size:32px;line-height:1.02;color:#fff;margin-top:6px">CHF 10M<span style="font-size:17px">/mo</span></div><div class="display" style="font-size:23px;color:#ECE8DF;margin-top:10px">2029</div></div>
<div style="flex:1 1 165px;background:#131317;border-radius:4px;padding:16px;border-left:5px solid #ECE8DF"><div style="font-size:10px;font-weight:700;letter-spacing:.2em;color:#5f5c56">RUNG 5</div><div class="display" style="font-size:32px;line-height:1.02;color:#fff;margin-top:6px">CHF 100M<span style="font-size:17px">/mo</span></div><div class="display" style="font-size:23px;color:#ECE8DF;margin-top:10px">2030</div></div>
</div><div style="font-size:13px;color:#ECE8DF;margin-top:16px;border-top:1px solid #2E2E36;padding-top:12px"><b style="color:#DA291C">SCALE LAW:</b> every build must show Customers Pool → 1% Sales Pool → ARPU → revenue potential before BUILD. Quality investment is leverage only when it creates a reusable automated factory and drives marginal human work toward zero.</div></div>
'''

def ladder(c):
 # Current can be either GROK's original marker or GPT's interim marker.
 markers=['<h2><span class="k">Operating floors &middot; target, not forecast</span>Revenue ladder</h2>','<h2><span class="k">Two things matter here: the money and the date</span>Revenue ladder</h2>','<h2><span class="k">Target, not forecast &middot; pool × conversion × ARPU</span>Revenue ladder</h2>']
 pos=[(c.find(x),x) for x in markers if c.find(x)>=0]
 if not pos: raise RuntimeError('ladder start missing')
 s=min(pos,key=lambda z:z[0])[0]
 end='<h2><span class="k">The logic, and who we are measuring against</span>Distribution &amp; the idols</h2>'
 e=c.find(end,s)
 if e<0: raise RuntimeError('ladder end missing')
 return c[:s]+ladder_html()+c[e:]

def board(c):
 c=project_table(c); c=main_table(c); c=ladder(c)
 if MARK not in c: c=c.replace('<body><div class="wrap">','<body><div class="wrap"><!-- '+MARK+' -->',1)
 return c

def main():
 print('ASSETS',latest('02_ASSETS')['version'])
 out={}
 out['01_STRATEGY']=write('01_STRATEGY',strategy,'Reconcile parallel pool writes; retain initiative-specific model')
 out['00_INITIATIVES']=write('00_INITIATIVES',initiatives,'Reconcile pool model; explicit initiative > inherited project pool')
 out['03_DECISIONS']=write('03_DECISIONS',decisions,'Decision: reconcile Grok/GPT pool writes; detailed board columns mandatory')
 out['BOARD_HTML']=write('BOARD_HTML',board,'Reconcile pool values; Customers Pool + 1% Sales Pool on all detailed initiative rows')
 print('DONE',out)
if __name__=='__main__': main()
