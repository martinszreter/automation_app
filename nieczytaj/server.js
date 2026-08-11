// ============================================================
// NIECZYTAJ.PL — v1.6
// Single-file, dependency-free Node 22 app.
// Pulls Polish RSS feeds, clusters stories across outlets,
// ranks HOT = co-coverage x freshness, renders a Polish page.
// STARTEND GmbH — venture 1.3
// ============================================================
'use strict';
const http = require('http');
const { execFile } = require('child_process');

const PORT = parseInt(process.env.PORT || '8080', 10);
const REFRESH_MIN = parseInt(process.env.REFRESH_MIN || '15', 10);
const PUSH_TOKEN = process.env.PUSH_TOKEN || '';
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY || '';
const ANTHROPIC_MODEL = process.env.ANTHROPIC_MODEL || 'claude-haiku-4-5';
const UA = 'Mozilla/5.0 (compatible; NieczytajBot/1.0; +https://nieczytaj.pl)';
const MAX_AGE_H = 48;

const FEEDS = [
  { id: 'onet',    name: 'Onet',              url: 'https://wiadomosci.onet.pl/.feed',              cat: 'kraj' },
  { id: 'wp',      name: 'WP',                url: 'https://wiadomosci.wp.pl/rss.xml',              cat: 'kraj' },
  { id: 'interia', name: 'Interia',           url: 'https://fakty.interia.pl/feed',                 cat: 'kraj' },
  { id: 'rmf',     name: 'RMF24',             url: 'https://www.rmf24.pl/feed',                     cat: 'kraj' },
  { id: 'tvn24',   name: 'TVN24',             url: 'https://tvn24.pl/najnowsze.xml',                cat: 'kraj' },
  { id: 'polsat',  name: 'Polsat News',       url: 'https://www.polsatnews.pl/rss/wszystkie.xml',   cat: 'kraj' },
  { id: 'fakt',    name: 'Fakt',              url: 'https://www.fakt.pl/.feed',                     cat: 'kraj' },
  { id: 'natemat', name: 'naTemat',           url: 'https://natemat.pl/rss/wszystkie',              cat: 'kraj' },
  { id: 'rp',      name: 'Rzeczpospolita',    url: 'https://www.rp.pl/rss/1019',                    cat: 'kraj' },
  { id: 'money',   name: 'money.pl',          url: 'https://www.money.pl/rss/',                     cat: 'biznes' },
  { id: 'bankier', name: 'Bankier',           url: 'https://www.bankier.pl/rss/wiadomosci.xml',     cat: 'biznes' },
  { id: 'bipl',    name: 'Business Insider',  url: 'https://businessinsider.com.pl/.feed',          cat: 'biznes' },
  { id: 'intsport',name: 'Interia Sport',     url: 'https://sport.interia.pl/feed',                 cat: 'sport' },
  { id: 'psport',  name: 'Przegląd Sportowy', url: 'https://przegladsportowy.onet.pl/.feed',        cat: 'sport' },
  { id: 'spiders', name: "Spider's Web",      url: 'https://spidersweb.pl/feed',                    cat: 'tech' },
  { id: 'pudelek', name: 'Pudelek',           url: 'https://www.pudelek.pl/rss.xml',                cat: 'rozrywka' },
  { id: 'wprost',  name: 'Wprost',            url: 'https://www.wprost.pl/rss',                     cat: 'kraj' },
  { id: 'o2',      name: 'o2',                url: 'https://www.o2.pl/rss.xml',                     cat: 'kraj' },
];

const CATS = [
  { id: 'kraj',     label: 'Wiadomości' },
  { id: 'biznes',   label: 'Biznes' },
  { id: 'sport',    label: 'Sport' },
  { id: 'tech',     label: 'Technologie' },
  { id: 'rozrywka', label: 'Rozrywka' },
];

const CITIES = [
  { slug: 'warszawa',   name: 'Warszawa',   lat: 52.2297, lon: 21.0122, feeds: [
    { id: 'onetwaw',  name: 'Onet Warszawa',      url: 'https://warszawa.onet.pl/.feed' },
    { id: 'rdc',      name: 'RDC',                url: 'https://www.rdc.pl/feed/' },
    { id: 'wpigulce', name: 'Warszawa w Pigułce', url: 'https://warszawawpigulce.pl/feed' },
  ]},
  { slug: 'krakow',     name: 'Kraków',     lat: 50.0647, lon: 19.945, feeds: [
    { id: 'onetkrk',  name: 'Onet Kraków',        url: 'https://krakow.onet.pl/.feed' },
    { id: 'gkrak',    name: 'Gazeta Krakowska',   url: 'https://gazetakrakowska.pl/rss/gazetakrakowska.xml' },
    { id: 'lovekrk',  name: 'LoveKraków',         url: 'https://lovekrakow.pl/rss.xml' },
  ]},
  { slug: 'wroclaw',    name: 'Wrocław',    lat: 51.1079, lon: 17.0385, feeds: [
    { id: 'onetwro',  name: 'Onet Wrocław',       url: 'https://wroclaw.onet.pl/.feed' },
    { id: 'gwro',     name: 'Gazeta Wrocławska',  url: 'https://gazetawroclawska.pl/rss/gazetawroclawska.xml' },
    { id: 'wroclawpl',name: 'wroclaw.pl',         url: 'https://www.wroclaw.pl/rss' },
  ]},
  { slug: 'trojmiasto', name: 'Trójmiasto', lat: 54.42, lon: 18.6, feeds: [
    { id: 'onet3m',   name: 'Onet Trójmiasto',    url: 'https://trojmiasto.onet.pl/.feed' },
    { id: 'dzbalt',   name: 'Dziennik Bałtycki',  url: 'https://dziennikbaltycki.pl/rss/dziennikbaltycki.xml' },
    { id: 'rgdansk',  name: 'Radio Gdańsk',       url: 'https://radiogdansk.pl/feed/' },
  ]},
  { slug: 'poznan',     name: 'Poznań',     lat: 52.4064, lon: 16.9252, feeds: [
    { id: 'onetpoz',  name: 'Onet Poznań',        url: 'https://poznan.onet.pl/.feed' },
    { id: 'gloswlkp', name: 'Głos Wielkopolski',  url: 'https://gloswielkopolski.pl/rss/gloswielkopolski.xml' },
    { id: 'epoznan',  name: 'ePoznań',            url: 'https://epoznan.pl/rss' },
  ]},
  { slug: 'slask',      name: 'Śląsk',      lat: 50.2599, lon: 19.0216, feeds: [
    { id: 'onetsla',  name: 'Onet Śląsk',         url: 'https://slask.onet.pl/.feed' },
    { id: 'dzzach',   name: 'Dziennik Zachodni',  url: 'https://dziennikzachodni.pl/rss/dziennikzachodni.xml' },
  ]},
];
for (const c of CITIES) for (const f of c.feeds) f.cat = 'city';

// ------------------------- state -------------------------
const state = {
  boot: Date.now(),
  lastRefresh: 0,
  refreshCount: 0,
  feedCache: {},
  clusters: [],
  byCat: {},
  latest: [],
  cities: {},
  summaries: new Map(),
  pv: { total: 0, days: {}, cities: {}, geo: {} },
  lastError: '',
};

// ------------------------- utils -------------------------
const ENT = { nbsp: ' ', amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", ndash: '–', mdash: '—',
  hellip: '…', bdquo: '„', rdquo: '”', ldquo: '“', rsquo: '’', lsquo: '‘', laquo: '«', raquo: '»',
  oacute: 'ó', Oacute: 'Ó', shy: '', zwnj: '', eacute: 'é', uuml: 'ü', auml: 'ä', ouml: 'ö', szlig: 'ß' };
function decodeEnt(s) {
  return String(s || '')
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
    .replace(/&([a-zA-Z]+);/g, (m, n) => (n in ENT ? ENT[n] : m));
}
function stripTags(s) { return String(s || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim(); }
function esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function tag(block, name) {
  const m = block.match(new RegExp('<' + name + '(?:\\s[^>]*)?>([\\s\\S]*?)</' + name + '>', 'i'));
  return m ? m[1].trim() : '';
}
const DIA = { 'ą':'a','ć':'c','ę':'e','ł':'l','ń':'n','ó':'o','ś':'s','ż':'z','ź':'z' };
function normTxt(s) {
  return String(s || '').toLowerCase().replace(/[ąćęłńóśżź]/g, c => DIA[c] || c).replace(/[^a-z0-9 ]+/g, ' ');
}
const STOP = new Set(('i w we z ze na do nie sie jest ze po za od o u a jak ale czy to ten ta te tym tego tej temu ' +
  'co cos dla przez przy oraz byc byl byla bylo beda bedzie sa ma mial miala maja juz tylko takze tez moze gdy aby ' +
  'ktory ktora ktore ktorzy ktorych pod nad przed ich jego jej ono ona on oni my wy je go mu im nas was niz bardzo ' +
  'lat lata roku rok zl mln mld proc procent wiecej mniej dzis dzisiaj wczoraj jutro godz min tys jak sie kiedy gdzie ' +
  'dlaczego czym jaki jaka jakie jest znow znowu wobec m in oto tak nie ma czy hit szok pilne wideo zdjecia zobacz ' +
  'sprawdz relacja live quiz sondaz komentarz opinia').split(/\s+/));
function tokens(title) {
  const out = [];
  for (const w of normTxt(title).split(/\s+/)) {
    if (w.length >= 3 && !STOP.has(w) && !/^\d+$/.test(w)) out.push(w);
  }
  return [...new Set(out)];
}
// daily template content — never "hot news", pollutes clustering
const JUNK = /(pogoda|horoskop|wyniki losowania|lotto|kartka z kalendarza|imieniny obchodz|jaki to dzien|jaki dzis dzien|krzyzowka|quiz|program tv|co obejrzec)/;
function tokMatch(a, b) {
  if (a === b) return true;
  if (a.length >= 5 && b.length >= 5) return a.slice(0, 5) === b.slice(0, 5);
  return false;
}
function overlap(ta, tb) {
  let n = 0;
  for (const a of ta) if (tb.some(b => tokMatch(a, b))) n++;
  return n;
}
function warsaw(fmtOpts, d) {
  return new Intl.DateTimeFormat('pl-PL', Object.assign({ timeZone: 'Europe/Warsaw' }, fmtOpts)).format(d || new Date());
}
function warsawDay() {
  const p = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Warsaw', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  return p; // YYYY-MM-DD
}
function agoPL(ms) {
  const m = Math.max(0, Math.round((Date.now() - ms) / 60000));
  if (m < 2) return 'przed chwilą';
  if (m < 60) return m + ' min temu';
  const h = Math.round(m / 60);
  if (h < 24) return h + (h === 1 ? ' godz. temu' : ' godz. temu');
  const d = Math.round(h / 24);
  return d + (d === 1 ? ' dzień temu' : ' dni temu');
}

// ------------------------- fetch & parse -------------------------
function curlGet(url) {
  return new Promise((resolve, reject) => {
    execFile('curl', ['-sL', '--max-time', '12', '--compressed', '-A', UA,
      '-H', 'accept: application/rss+xml,application/xml;q=0.9,*/*;q=0.8', url],
      { maxBuffer: 8e6, timeout: 15000 },
      (err, stdout) => (err ? reject(err) : resolve(String(stdout))));
  });
}
function itemImg(b) {
  let m = b.match(/<enclosure[^>]+url="([^"]+)"[^>]*\/?>/i);
  if (m && (/type="image/i.test(m[0]) || /\.(jpe?g|png|webp|gif)(\?|$)/i.test(m[1]))) return decodeEnt(m[1]);
  m = b.match(/<media:content[^>]+url="([^"]+)"/i) || b.match(/<media:thumbnail[^>]+url="([^"]+)"/i);
  if (m) return decodeEnt(m[1]);
  m = b.match(/<img[^>]+src="(https?:\/\/[^"]+)"/i);
  if (m) return decodeEnt(m[1]);
  return '';
}
async function fetchFeed(feed) {
  let xml = '', via = 'fetch';
  try {
    const res = await fetch(feed.url, { headers: { 'user-agent': UA, 'accept': 'application/rss+xml,application/xml,text/xml,*/*' }, redirect: 'follow', signal: AbortSignal.timeout(12000) });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    xml = await res.text();
    if (!/<item[\s>]/i.test(xml)) throw new Error('no items via fetch');
  } catch (e) {
    // Some Polish CDNs (Ring Publishing, TVN24) block Node's TLS fingerprint — curl passes.
    xml = await curlGet(feed.url);
    via = 'curl';
    if (!/<item[\s>]/i.test(xml)) throw new Error('no items (fetch: ' + String(e && e.message || e).slice(0, 60) + ')');
  }
  feed.via = via;
  const items = [];
  const blocks = xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || [];
  for (const b of blocks) {
    const title = stripTags(decodeEnt(tag(b, 'title')));
    let link = decodeEnt(tag(b, 'link')) || '';
    if (!link) { const g = tag(b, 'guid'); if (/^https?:/i.test(g)) link = decodeEnt(g); }
    link = link.trim();
    const dateStr = tag(b, 'pubDate') || tag(b, 'dc:date') || tag(b, 'date') || '';
    let at = Date.parse(decodeEnt(dateStr));
    if (!Number.isFinite(at)) at = Date.now();
    const desc = stripTags(decodeEnt(tag(b, 'description'))).slice(0, 400);
    if (!title || title.length < 6 || !/^https?:/i.test(link)) continue;
    if (JUNK.test(normTxt(title)) || /\d{1,2}\.\d{1,2}\.\d{4}/.test(title)) continue;
    items.push({ src: feed.id, srcName: feed.name, cat: feed.cat, title, link, at, desc, img: itemImg(b), toks: tokens(title) });
  }
  return items;
}

async function refresh() {
  const ALL = FEEDS.concat(CITIES.flatMap(c => c.feeds));
  const results = await Promise.allSettled(ALL.map(f => fetchFeed(f)));
  const now = Date.now();
  results.forEach((r, i) => {
    const f = ALL[i];
    if (r.status === 'fulfilled' && r.value.length) {
      state.feedCache[f.id] = { items: r.value, at: now, ok: true, error: '' };
    } else {
      const prev = state.feedCache[f.id];
      state.feedCache[f.id] = { items: prev ? prev.items : [], at: prev ? prev.at : 0, ok: false, error: r.status === 'rejected' ? String(r.reason).slice(0, 120) : 'empty' };
    }
  });
  // pool: fresh, deduped by link
  const seen = new Set();
  const pool = [];
  for (const f of FEEDS) {
    const c = state.feedCache[f.id];
    if (!c) continue;
    for (const it of c.items) {
      if (now - it.at > MAX_AGE_H * 3600e3) continue;
      if (it.at > now + 3600e3) continue;
      const k = it.link.replace(/[?#].*$/, '');
      if (seen.has(k)) continue;
      seen.add(k);
      pool.push(it);
    }
  }
  cluster(pool);
  // per-city pools
  for (const c of CITIES) {
    const cseen = new Set();
    const cpool = [];
    for (const f of c.feeds) {
      const fc = state.feedCache[f.id];
      if (!fc) continue;
      for (const it of fc.items) {
        if (now - it.at > MAX_AGE_H * 3600e3 || it.at > now + 3600e3) continue;
        const k = it.link.replace(/[?#].*$/, '');
        if (cseen.has(k)) continue;
        cseen.add(k);
        cpool.push(it);
      }
    }
    state.cities[c.slug] = cityCluster(cpool);
  }
  state.lastRefresh = now;
  state.refreshCount++;
  const okN = FEEDS.filter(f => state.feedCache[f.id] && state.feedCache[f.id].ok).length;
  console.log(`[refresh #${state.refreshCount}] feeds ok=${okN}/${FEEDS.length} pool=${pool.length} clusters=${state.clusters.length} hot=${state.clusters.filter(c => c.srcCount >= 2).length} pv_today=${state.pv.days[warsawDay()] || 0}`);
  if (ANTHROPIC_API_KEY) selfSummarize().catch(e => console.log('[ai] error: ' + String(e).slice(0, 200)));
}

// ------------------------- clustering & ranking -------------------------
const BREAKING = /(pilne|nagle|nie zyje|zmarl|zmarla|katastrofa|wybuch|trzesienie|eksplozja|atak|ewakuacja|alarm|awaria|tragedia|wypadek)/;
function buildClusters(pool) {
  pool.sort((a, b) => b.at - a.at);
  const clusters = [];
  for (const it of pool) {
    let best = null, bestN = 0;
    for (const c of clusters) {
      const n = overlap(it.toks, c.toks);
      const need = Math.min(it.toks.length, c.leadToks) <= 4 ? 2 : 3;
      if (n >= need && n / Math.min(it.toks.length, c.leadToks) >= 0.45 && n > bestN) { best = c; bestN = n; }
    }
    if (best) {
      best.items.push(it);
      for (const t of it.toks) if (!best.toks.some(x => tokMatch(x, t))) best.toks.push(t);
    } else {
      clusters.push({ items: [it], toks: [...it.toks], leadToks: it.toks.length });
    }
  }
  return clusters;
}
function cityCluster(pool) {
  const clusters = buildClusters(pool);
  scoreClusters(clusters);
  clusters.sort((a, b) => b.score - a.score);
  const hot = clusters.slice(0, 13);
  const hotLinks = new Set(hot.flatMap(c => c.items.map(i => i.link)));
  return { clusters: hot, latest: pool.filter(i => !hotLinks.has(i.link)).slice(0, 14) };
}
function scoreClusters(clusters) {
  const now = Date.now();
  for (const c of clusters) {
    c.items.sort((a, b) => b.at - a.at);
    const srcs = [...new Set(c.items.map(i => i.src))];
    c.srcCount = srcs.length;
    c.newest = c.items[0].at;
    const counts = {};
    for (const i of c.items) counts[i.cat] = (counts[i.cat] || 0) + 1;
    c.cat = Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
    c.lead = c.items[0];
    const ageH = (now - c.newest) / 3600e3;
    const breaking = BREAKING.test(normTxt(c.lead.title)) ? 1 : 0;
    // co-coverage is the signal, freshness decays it: hot = everyone writes about it NOW
    c.score = c.srcCount * 10 * Math.exp(-ageH / 10) + breaking * 4;
    c.key = [...c.lead.toks].sort().slice(0, 5).join('-') || c.lead.link;
    const withImg = c.items.find(i => i.img);
    c.img = withImg ? withImg.img : '';
    const per = new Map();
    for (const i of c.items) if (!per.has(i.src)) per.set(i.src, i);
    c.chips = [...per.values()];
  }
}
function cluster(pool) {
  const clusters = buildClusters(pool);
  scoreClusters(clusters);
  clusters.sort((a, b) => b.score - a.score);
  const hot = clusters.filter(c => c.srcCount >= 2).slice(0, 12);
  const hotLinks = new Set(hot.flatMap(c => c.items.map(i => i.link)));
  const byCat = {};
  for (const cat of CATS) byCat[cat.id] = [];
  for (const c of clusters) {
    if (hot.includes(c)) continue;
    const it = c.lead;
    if (hotLinks.has(it.link)) continue;
    if (byCat[c.cat] && byCat[c.cat].length < 8) byCat[c.cat].push(c);
  }
  state.clusters = hot;
  state.byCat = byCat;
  state.latest = pool.filter(i => !hotLinks.has(i.link)).slice(0, 16);
}
// ------------------------- AI briefs -------------------------
function clustersNeedingSummary() {
  return state.clusters.filter(c => c.srcCount >= 2 && !state.summaries.has(c.key)).slice(0, 10);
}
async function selfSummarize() {
  const need = clustersNeedingSummary();
  if (!need.length) return;
  const input = need.map((c, i) => ({
    n: i, key: c.key,
    titles: c.items.slice(0, 6).map(it => `[${it.srcName}] ${it.title}`),
    leads: c.items.slice(0, 3).map(it => it.desc).filter(Boolean).map(d => d.slice(0, 200)),
  }));
  const body = {
    model: ANTHROPIC_MODEL, max_tokens: 1600,
    system: 'Jesteś redaktorem serwisu nieczytaj.pl. Dla każdego tematu napisz JEDNO zdanie po polsku (maks. 30 słów), neutralne, informacyjne, własnymi słowami — co się stało i dlaczego to ważne. Bez clickbaitu, bez oceny. Zwróć WYŁĄCZNIE JSON: [{"key":"...","text":"..."}]',
    messages: [{ role: 'user', content: JSON.stringify(input) }],
  };
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify(body), signal: AbortSignal.timeout(45000),
  });
  if (!res.ok) throw new Error('anthropic HTTP ' + res.status);
  const j = await res.json();
  const txt = (j.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
  const m = txt.match(/\[[\s\S]*\]/);
  if (!m) throw new Error('no JSON in AI reply');
  for (const s of JSON.parse(m[0])) {
    if (s && s.key && s.text) putSummary(s.key, String(s.text).slice(0, 300), 'app');
  }
  console.log(`[ai] summarized ${need.length} clusters (self)`);
}
function putSummary(key, text, by) {
  state.summaries.set(key, { text, at: Date.now(), by });
  if (state.summaries.size > 300) {
    const oldest = [...state.summaries.entries()].sort((a, b) => a[1].at - b[1].at).slice(0, 50);
    for (const [k] of oldest) state.summaries.delete(k);
  }
}

// ------------------------- page -------------------------
function chipHtml(it) {
  return `<a class="chip" href="${esc(it.link)}" target="_blank" rel="noopener">${esc(it.srcName)}</a>`;
}
function srcBadge(c) {
  return `<span class="src${c.srcCount >= 4 ? ' many' : ''}">🔥 ${c.srcCount} ${c.srcCount === 1 ? 'źródło' : (c.srcCount < 5 ? 'źródła' : 'źródeł')}</span>`;
}
function tileHtml(c, big) {
  const s = big ? state.summaries.get(c.key) : null;
  const img = c.img ? `<a class="timg" href="${esc(c.lead.link)}" target="_blank" rel="noopener"><img src="${esc(c.img)}" alt="" ${big ? '' : 'loading="lazy" '}onerror="this.parentNode.style.display='none'"></a>` : `<a class="timg noimg" href="${esc(c.lead.link)}" target="_blank" rel="noopener"><span>NIECZYTAJ.PL</span></a>`;
  return `<article class="tile${big ? ' hero' : ''}">
${img}
<h3><a href="${esc(c.lead.link)}" target="_blank" rel="noopener">${esc(c.lead.title)}</a></h3>
${s ? `<p class="ai"><span class="ailab">AI w skrócie</span> ${esc(s.text)}</p>` : ''}
<div class="cm">${srcBadge(c)}<span>${agoPL(c.newest)}</span></div>
</article>`;
}
function railRow(it) {
  return `<div class="rrow">
${it.img ? `<a class="rimg" href="${esc(it.link)}" target="_blank" rel="noopener"><img src="${esc(it.img)}" alt="" loading="lazy" onerror="this.parentNode.style.display='none'"></a>` : ''}
<div class="rtx"><h4><a href="${esc(it.link)}" target="_blank" rel="noopener">${esc(it.title)}</a></h4>
<div class="rmeta">${esc(it.srcName)} · ${agoPL(it.at)}</div></div>
</div>`;
}
// ------------------------- ads -------------------------
// ADS_JSON env: [{"slot":"baner|kafelek|box","type":"img|video","src":"https://…","href":"https://…","alt":"…","until":"2026-09-01"}]
let ADS = [];
try { ADS = JSON.parse(process.env.ADS_JSON || '[]'); } catch (e) { console.log('[ads] bad ADS_JSON'); ADS = []; }
const PRICE = { baner7: 490, baner30: 1490, kaf7: 390, kaf30: 990, box7: 190, box30: 590 };
function adFor(slot) {
  const now = Date.now();
  return ADS.find(a => a && a.slot === slot && a.src && (!a.until || Date.parse(a.until) > now)) || null;
}
function adCreative(a) {
  return a.type === 'video'
    ? `<video class="adcre" src="${esc(a.src)}" autoplay muted loop playsinline preload="metadata"></video>`
    : `<img class="adcre" src="${esc(a.src)}" alt="${esc(a.alt || 'Reklama')}" loading="lazy">`;
}
function adSlot(slot, houseText) {
  const a = adFor(slot);
  if (a) return `<a class="adbox ${slot}" href="${esc(a.href || '/reklama')}" target="_blank" rel="noopener sponsored"><span class="adlab">Reklama</span>${adCreative(a)}</a>`;
  return `<a class="adbox ${slot} house" href="/reklama"><span class="adlab">Reklama</span><b>${houseText}</b><span class="adcta">Zobacz ofertę →</span></a>`;
}
const adBanner = () => `<div class="adwrap">${adSlot('baner', `Twoja reklama tutaj — od ${PRICE.baner7} zł/tydzień`)}</div>`;
// paid kafelek keeps its own high slot; house kafelek only ever fills a hole in the grid
const adTileSold = () => (adFor('kafelek') ? `<article class="tile ad">${adSlot('kafelek', '')}</article>` : '');
const adTileHouse = () => `<article class="tile ad"><a class="adbox kafelek house" href="/reklama"><span class="adlab">Reklama</span><b>Twoja reklama — od ${PRICE.kaf7} zł/tydzień</b><span class="adcta">Zobacz ofertę →</span></a></article>`;
const adRail = () => `<div class="adwrap">${adSlot('box', `Reklama — od ${PRICE.box7} zł/tydzień`)}</div>`;

function page(cityDef) {
  const upd = state.lastRefresh ? warsaw({ hour: '2-digit', minute: '2-digit' }, new Date(state.lastRefresh)) : '—';
  const today = warsaw({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const cd = cityDef ? (state.cities[cityDef.slug] || { clusters: [], latest: [] }) : null;
  const hot = cd ? cd.clusters : state.clusters;
  const loading = !state.lastRefresh;
  const aiOn = ANTHROPIC_API_KEY || [...state.summaries.values()].some(s => Date.now() - s.at < 3 * 3600e3);
  const hero = hot[0];
  const rest = hot.slice(1);
  const latest = cd ? cd.latest : (state.latest || []);
  // single pill: shows the current edition. On a local edition it returns to Polska; on Polska it finds your area.
  const pill = cityDef
    ? `<a class="edpill on" href="/" title="Wróć do wydania krajowego">📍 ${esc(cityDef.name)} <span class="pillx">✕</span></a>`
    : `<button class="edpill" onclick="ncGeo()" title="Wiadomości z Twojej okolicy">📍 Polska</button>`;
  // 3-column grid: a trailing hole is either sold space or a dropped tile — never empty air
  let fillers = 0;
  const MAX_FILLERS = 3;
  const grid = (tiles) => {
    let a = tiles.filter(Boolean);
    const r = a.length % 3;
    if (r === 1) a = a.slice(0, -1);
    else if (r === 2) {
      if (fillers < MAX_FILLERS) { a.push(adTileHouse()); fillers++; }
      else a = a.slice(0, -2);
    }
    return a.length ? `<div class="ggrid">${a.join('\n')}</div>` : '';
  };
  const pillHint = cityDef
    ? '✕ = powrót do całej Polski'
    : 'kliknij → wiadomości z Twojej okolicy';
  return `<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="600">
<title>NIECZYTAJ.PL${cityDef ? ' · ' + cityDef.name : ''} — nie czytaj wszystkiego. AI wybiera gorące wiadomości</title>
<meta name="description" content="AI czyta polskie serwisy informacyjne co ${REFRESH_MIN} minut i pokazuje tylko to, o czym naprawdę się mówi. Nie czytaj wszystkiego — czytaj to, co gorące.">
<meta property="og:title" content="NIECZYTAJ.PL — gorące wiadomości wybrane przez AI">
<meta property="og:description" content="Nie czytaj wszystkiego. AI monitoruje ${FEEDS.length} polskich serwisów i ranguje tematy, o których mówią wszyscy.">
<style>
:root{--paper:#fbfbfa;--ink:#141414;--mut:#6f6a64;--acc:#c8102e;--line:#e7e5e1;--aibg:#f3f0ea}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.4 -apple-system,'Segoe UI',Roboto,Arial,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:0 14px 40px}
header{padding:14px 0 10px;border-bottom:3px solid var(--ink);display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 20px}
.logo{font-family:Georgia,'Times New Roman',serif;font-size:30px;font-weight:700;letter-spacing:-1px;margin:0}
.logo a{color:var(--ink);text-decoration:none}.logo .pl{color:var(--acc)}
.tagline{margin:0;font-size:12.5px;color:var(--mut)}
.tagline b{color:var(--ink)}
.edwrap{margin-left:auto;display:flex;flex-direction:column;align-items:center;gap:4px}
.edhint{font-size:10.5px;line-height:1.2;color:var(--mut);text-align:center;white-space:nowrap}
.edpill{font:700 13px -apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:var(--ink);background:#fff;border:1.5px solid var(--ink);border-radius:20px;padding:7px 14px;cursor:pointer;text-decoration:none;display:inline-block}
.edpill:disabled{opacity:.6;cursor:wait}
.edpill.on{background:var(--acc);border-color:var(--acc);color:#fff}
.pillx{opacity:.75;margin-left:3px}
.updline{display:flex;gap:9px;flex-wrap:wrap;align-items:center;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px}
.dotlive{color:var(--acc);font-weight:700}
.geolink{color:var(--acc);font-weight:700;text-decoration:none;border-bottom:1px dotted var(--acc);cursor:pointer}
.geonote{font-size:11px;color:var(--acc);font-weight:700;text-transform:uppercase;letter-spacing:.4px}
.nctoast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#141414;color:#fff;padding:10px 16px;border-radius:8px;font-size:13px;z-index:99;opacity:1;transition:opacity .5s;max-width:90vw;text-align:center}
.adwrap{margin:18px 0}
.adbox{display:block;position:relative;border:1px solid var(--line);border-radius:8px;overflow:hidden;text-decoration:none;background:#fff}
.adlab{position:absolute;top:6px;left:6px;z-index:2;font-size:9px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;background:rgba(20,20,20,.7);color:#fff;padding:2px 7px;border-radius:3px}
.adcre{width:100%;display:block;object-fit:cover}
.adbox.baner .adcre{aspect-ratio:970/170}
.adbox.kafelek .adcre{aspect-ratio:16/10;border-radius:6px}
.adbox.box .adcre{aspect-ratio:1/1}
.adbox.house{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;padding:26px 16px;color:var(--ink);background:repeating-linear-gradient(45deg,#faf8f4,#faf8f4 11px,#f4f1ea 11px,#f4f1ea 22px)}
.adbox.house b{font-size:15px;font-weight:700}
.adbox.kafelek.house{padding:34px 12px;text-align:center;height:100%}
.adbox.kafelek.house b{font-size:13.5px}
.adcta{color:var(--acc);font-weight:700;font-size:12.5px}
h2{font-family:Georgia,serif;font-size:13.5px;letter-spacing:1.5px;text-transform:uppercase;border-bottom:2px solid var(--ink);padding-bottom:5px;margin:24px 0 12px}
h2 .n{color:var(--acc)}
.layout{display:grid;grid-template-columns:1fr;gap:24px}
@media(min-width:1080px){.layout{grid-template-columns:minmax(0,1fr) 300px}}
.ggrid{display:grid;gap:16px 14px;grid-template-columns:repeat(2,1fr)}
@media(min-width:700px){.ggrid{grid-template-columns:repeat(3,1fr)}}
.tile{min-width:0}
.tile.hero{grid-column:span 2;grid-row:span 2}
.timg{display:block;position:relative}
.timg img{width:100%;aspect-ratio:16/10;object-fit:cover;border-radius:6px;background:#e8e6e2;display:block}
.tile.hero .timg img{aspect-ratio:16/9;border-radius:8px}
.timg.noimg{aspect-ratio:16/10;border-radius:6px;background:#efece7;display:flex;align-items:center;justify-content:center;text-decoration:none}
.timg.noimg span{font-family:Georgia,serif;font-weight:700;color:#c9c4bc;font-size:14px;letter-spacing:1px}
.tile h3{margin:7px 0 0;font-size:14.5px;line-height:1.3;font-weight:700}
.tile.hero h3{font-size:23px;line-height:1.2;margin-top:10px}
.tile h3 a,h4 a{color:var(--ink);text-decoration:none}
.tile h3 a:hover,h4 a:hover{color:var(--acc)}
.ai{margin:8px 0 0;font-size:13.5px;line-height:1.45;background:var(--aibg);border-left:3px solid var(--acc);padding:7px 10px;border-radius:0 6px 6px 0}
.ailab{font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--acc);margin-right:6px}
.cm{display:flex;gap:9px;align-items:center;margin-top:5px;font-size:11px;color:var(--mut)}
.src{font-weight:700;color:#a33}.src.many{color:var(--acc)}
.rail h2{margin-top:24px}
@media(min-width:1080px){.rail h2:first-child{margin-top:24px}}
.rrow{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--line);align-items:flex-start}
.rimg{flex:none}
.rimg img{width:78px;height:52px;object-fit:cover;border-radius:5px;background:#e8e6e2;display:block}
.rtx{min-width:0}
.rrow h4{margin:0;font-size:13px;line-height:1.3;font-weight:600}
.rmeta{font-size:10.5px;color:var(--mut);margin-top:3px}
footer{margin-top:40px;padding-top:12px;border-top:3px solid var(--ink);font-size:12px;color:var(--mut);line-height:1.6}
footer a{color:var(--mut)}
.empty{padding:60px 0;text-align:center;color:var(--mut);font-size:17px}
@media(max-width:520px){.logo{font-size:26px}.tile.hero h3{font-size:18.5px}.updline{margin-left:0}.tile h3{font-size:13.5px}.edwrap{align-items:flex-start;margin-left:0}.edhint{text-align:left}}
</style></head><body><div class="wrap">
<header>
<h1 class="logo"><a href="/">NIECZYTAJ<span class="pl">.PL</span></a></h1>
<p class="tagline"><b>Nie czytaj wszystkiego.</b> AI czyta ${cityDef ? 'lokalne serwisy' : FEEDS.length + ' serwisów'} co ${REFRESH_MIN} min — Ty czytasz to, co gorące.</p>
<div class="edwrap">${pill}<span class="edhint">${pillHint}</span></div>
<div class="updline"><span class="dotlive">● NA ŻYWO</span><span>${esc(today)}</span><span>aktualizacja ${esc(upd)}</span><a class="geolink" onclick="ncGeo();return false" href="#">📍 moja lokalizacja</a><span id="geonote" class="geonote" style="display:none"></span>${aiOn ? '<span>skróty: AI</span>' : ''}<a class="geolink" href="/reklama" style="border:0">reklama</a></div>
</header>
${loading ? `<div class="empty">Pobieram najnowsze wiadomości…<br>Strona odświeży się automatycznie.</div><script>setTimeout(()=>location.reload(),8000)</script>` : `
<div class="layout">
<main>
<h2><span class="n">🔥</span> ${cityDef ? 'Gorące: ' + cityDef.name : 'Gorące teraz — o tym mówią wszyscy'}</h2>
<div class="ggrid">
${hero ? tileHtml(hero, true) : ''}
${rest.slice(0, 2).map(c => tileHtml(c, false)).join('\n')}
</div>
${adBanner()}
${grid([adTileSold(), ...rest.slice(2).map(c => tileHtml(c, false))])}
${cityDef ? '' : CATS.map(cat => {
    const list = (state.byCat[cat.id] || []).slice(0, 8);
    if (!list.length) return '';
    return `<h2>${cat.label}</h2>${grid(list.map(c => tileHtml(c, false)))}`;
  }).join('\n')}
</main>
<aside class="rail">
<h2>Najnowsze${cityDef ? ': ' + cityDef.name : ''}</h2>
${latest.slice(0, 4).map(railRow).join('\n')}
${adRail()}
${latest.slice(4).map(railRow).join('\n')}
</aside>
</div>`}
<footer>
<b>NIECZYTAJ.PL</b> — strona w pełni automatyczna: AI agreguje nagłówki i miniatury z polskich serwisów, grupuje tematy i ranguje je według liczby źródeł i świeżości. Nagłówki, zdjęcia i linki prowadzą do serwisów źródłowych — wszystkie prawa do artykułów i zdjęć należą do ich wydawców. Krótkie podsumowania pisze AI własnymi słowami.<br>
MVP · © ${new Date().getFullYear()} <a href="https://startend.ch">STARTEND GmbH</a>, Cham (CH) · <a href="/reklama">reklama na nieczytaj.pl</a> · <a href="/regulamin">regulamin</a> · kontakt: <a href="mailto:info@startend.ch">info@startend.ch</a>
</footer>
</div>
<script>
var NC_GEO=${JSON.stringify(CITIES.map(c => ({ s: c.slug, n: c.name, a: c.lat, o: c.lon })))};
function ncDist(a1,o1,a2,o2){var R=6371,dA=(a2-a1)*Math.PI/180,dO=(o2-o1)*Math.PI/180,x=Math.sin(dA/2)*Math.sin(dA/2)+Math.cos(a1*Math.PI/180)*Math.cos(a2*Math.PI/180)*Math.sin(dO/2)*Math.sin(dO/2);return 2*R*Math.asin(Math.sqrt(x));}
function ncToast(m){var t=document.createElement('div');t.className='nctoast';t.textContent=m;document.body.appendChild(t);setTimeout(function(){t.style.opacity='0';},2800);setTimeout(function(){if(t.parentNode)t.parentNode.removeChild(t);},3500);}
function ncBeacon(n,d){try{if(navigator.sendBeacon)navigator.sendBeacon('/api/geo',JSON.stringify({n:n,d:d}));}catch(e){}}
function ncBtnReset(){var b=document.querySelector('.edpill');if(b&&b.tagName==='BUTTON'){b.disabled=false;b.innerHTML='📍 Polska';}}
function ncGeo(){
  if(!navigator.geolocation){ncToast('Twoja przeglądarka nie obsługuje lokalizacji');return;}
  var b=document.querySelector('.edpill');if(b&&b.tagName==='BUTTON'){b.disabled=true;b.innerHTML='📍 …';}
  navigator.geolocation.getCurrentPosition(function(p){
    var la=p.coords.latitude,lo=p.coords.longitude,best=null,bd=1e9;
    for(var i=0;i<NC_GEO.length;i++){var c=NC_GEO[i],d=ncDist(la,lo,c.a,c.o);if(d<bd){bd=d;best=c;}}
    if(best&&bd<=100){
      ncBeacon(best.s,'match');
      try{localStorage.setItem('nc_city',best.s)}catch(e){}
      location.href='/'+best.s+'?geo=1';
    }else{
      ncBeacon(best?best.s:'none',bd<=150?'100-150':'>150');
      ncToast('Twoja okolica już wkrótce 📍 Najbliższa edycja: '+(best?best.n:'—')+' ('+Math.round(bd)+' km)');
      ncBtnReset();
    }
  },function(err){
    ncToast(err&&err.code===1?'Odmówiono dostępu do lokalizacji':'Nie udało się pobrać lokalizacji');
    ncBtnReset();
  },{enableHighAccuracy:false,timeout:8000,maximumAge:600000});
}
(function(){
  if(location.search.indexOf('geo=1')>-1){
    var p=location.pathname.replace(/\\//g,'');
    for(var i=0;i<NC_GEO.length;i++){
      if(NC_GEO[i].s===p){var g=document.getElementById('geonote');if(g){g.textContent='📍 Wykryto: '+NC_GEO[i].n;g.style.display='inline';}break;}
    }
  }
})();
</script>
</body></html>`;
}
// ------------------------- /reklama -------------------------
function buyLink(pkg, label, price) {
  const env = process.env['STRIPE_' + pkg.toUpperCase()];
  const href = env || `mailto:info@startend.ch?subject=${encodeURIComponent('Reklama nieczytaj.pl — ' + label)}&body=${encodeURIComponent('Dzień dobry,\n\nchcę zarezerwować: ' + label + ' (' + price + ' zł netto).\n\nFirma:\nNIP:\nMateriał (obraz/wideo):\nLink docelowy:\nStart kampanii:\n\n')}`;
  return `<a class="buy" href="${esc(href)}"${env ? ' target="_blank" rel="noopener"' : ''}>Zamów · ${price} zł</a>`;
}
function reklamaPage() {
  const pv = state.pv.days[warsawDay()] || 0;
  return `<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reklama na NIECZYTAJ.PL — obraz lub wideo, od ${PRICE.box7} zł/tydzień</title>
<meta name="description" content="Reklama graficzna i wideo na nieczytaj.pl — automatycznym serwisie z gorącymi wiadomościami. Ceny startowe, rezerwacja online.">
<style>
:root{--paper:#fbfbfa;--ink:#141414;--mut:#6f6a64;--acc:#c8102e;--line:#e7e5e1;--aibg:#f3f0ea}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 -apple-system,'Segoe UI',Roboto,Arial,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:0 16px 60px}
header{padding:14px 0 10px;border-bottom:3px solid var(--ink);display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.logo{font-family:Georgia,serif;font-size:28px;font-weight:700;letter-spacing:-1px;margin:0}
.logo a{color:var(--ink);text-decoration:none}.logo .pl{color:var(--acc)}
.back{margin-left:auto;font-size:13px}.back a{color:var(--mut);text-decoration:none;border:1.5px solid var(--line);border-radius:20px;padding:6px 13px}
h1{font-family:Georgia,serif;font-size:36px;line-height:1.15;margin:34px 0 10px}
.lede{font-size:17px;color:var(--mut);max-width:62ch}
.lede b{color:var(--ink)}
h2{font-family:Georgia,serif;font-size:14px;letter-spacing:1.5px;text-transform:uppercase;border-bottom:2px solid var(--ink);padding-bottom:5px;margin:38px 0 14px}
.fmt{display:grid;grid-template-columns:1fr;gap:16px}
@media(min-width:720px){.fmt{grid-template-columns:1fr 1fr 1fr}}
.card{border:1px solid var(--line);border-radius:12px;padding:18px;background:#fff;display:flex;flex-direction:column;gap:8px}
.card h3{font-family:Georgia,serif;font-size:19px;margin:0}
.mock{border-radius:6px;background:repeating-linear-gradient(45deg,#faf8f4,#faf8f4 10px,#f4f1ea 10px,#f4f1ea 20px);display:flex;align-items:center;justify-content:center;color:#b9b3a9;font-size:11px;font-weight:700;letter-spacing:.1em}
.m1{aspect-ratio:970/170}.m2{aspect-ratio:16/10}.m3{aspect-ratio:1/1;max-width:150px}
.card p{margin:0;font-size:14px;color:var(--mut)}
.prices{margin-top:auto;padding-top:6px;display:flex;flex-direction:column;gap:6px}
.buy{display:block;text-align:center;background:var(--acc);color:#fff;font-weight:700;text-decoration:none;border-radius:8px;padding:9px 12px;font-size:14px}
.buy:hover{opacity:.9}
table{border-collapse:collapse;width:100%;font-size:14px;background:#fff;border:1px solid var(--line);border-radius:8px;overflow:hidden}
th{background:var(--ink);color:#fff;text-align:left;padding:9px 12px;font-size:12px;letter-spacing:.06em;text-transform:uppercase}
td{border-bottom:1px solid var(--line);padding:9px 12px}
td.p{font-weight:700;white-space:nowrap}
.note{background:var(--aibg);border-left:3px solid var(--acc);padding:14px 16px;border-radius:0 8px 8px 0;font-size:14.5px;margin:26px 0}
.note b{color:var(--ink)}
ul{padding-left:18px}li{margin:5px 0;font-size:14.5px}
footer{margin-top:44px;padding-top:14px;border-top:3px solid var(--ink);font-size:12.5px;color:var(--mut);line-height:1.6}
footer a{color:var(--mut)}
</style></head><body><div class="wrap">
<header>
<h1 class="logo"><a href="/">NIECZYTAJ<span class="pl">.PL</span></a></h1>
<div class="back"><a href="/">← Wróć do wiadomości</a></div>
</header>
<h1>Reklama, której nikt nie przewija</h1>
<p class="lede"><b>Obraz albo wideo</b> — w miejscu, w którym czytelnik i tak patrzy: między gorącymi newsami dnia. Bez pop-upów, bez autoodtwarzania z dźwiękiem, bez śledzenia użytkowników. Rezerwacja w minutę, materiał publikujemy tego samego dnia.</p>

<h2>Formaty</h2>
<div class="fmt">
<div class="card">
<div class="mock m1">BANER 970×170</div>
<h3>Baner główny</h3>
<p>Pełna szerokość, bezpośrednio pod głównym newsem dnia — pierwsze, co widać po wejściu. Obraz lub wideo (bez dźwięku, pętla). Minimalny okres: 7 dni.</p>
<div class="prices">
${buyLink('baner7', 'Baner główny — 7 dni', PRICE.baner7)}
${buyLink('baner30', 'Baner główny — 30 dni', PRICE.baner30)}
</div>
</div>
<div class="card">
<div class="mock m2">KAFELEK 16:10</div>
<h3>Kafelek w siatce</h3>
<p>Wygląda jak news, oznaczony „Reklama" — najwyższa klikalność. Obraz lub wideo.</p>
<div class="prices">
${buyLink('kaf7', 'Kafelek — 7 dni', PRICE.kaf7)}
${buyLink('kaf30', 'Kafelek — 30 dni', PRICE.kaf30)}
</div>
</div>
<div class="card">
<div class="mock m3">BOX 1:1</div>
<h3>Box w kolumnie</h3>
<p>Kwadrat w kolumnie „Najnowsze", widoczny przy przewijaniu. Obraz lub wideo.</p>
<div class="prices">
${buyLink('box7', 'Box — 7 dni', PRICE.box7)}
${buyLink('box30', 'Box — 30 dni', PRICE.box30)}
</div>
</div>
</div>

<h2>Cennik</h2>
<table>
<tr><th>Format</th><th>7 dni</th><th>30 dni</th></tr>
<tr><td>Baner główny (obraz / wideo)</td><td class="p">${PRICE.baner7} zł</td><td class="p">${PRICE.baner30} zł</td></tr>
<tr><td>Kafelek w siatce (obraz / wideo)</td><td class="p">${PRICE.kaf7} zł</td><td class="p">${PRICE.kaf30} zł</td></tr>
<tr><td>Box w kolumnie</td><td class="p">${PRICE.box7} zł</td><td class="p">${PRICE.box30} zł</td></tr>
</table>
<p style="font-size:13px;color:var(--mut);margin-top:8px">Ceny netto, minimalny okres 7 dni. Sprzedaż wyłącznie B2B — faktura z STARTEND GmbH (Szwajcaria), podatek rozliczany przez nabywcę (reverse charge). Płatność z góry. <a href="/regulamin" style="color:var(--acc)">Regulamin</a>.</p>

<div class="note"><b>Gramy w otwarte karty:</b> nieczytaj.pl to nowy serwis — dlatego podajemy realne liczby zamiast obietnic. Dziś: <b>${pv}</b> odsłon (licznik od północy, bez botów). Kupujesz miejsce na wczesnym etapie — a Twoja stawka na czas kampanii zostaje, nawet gdy cennik pójdzie w górę.</div>

<h2>Specyfikacja</h2>
<ul>
<li><b>Obraz:</b> JPG lub PNG — baner 1940×340 px, kafelek 1200×750 px, box 1000×1000 px.</li>
<li><b>Wideo:</b> MP4 (H.264), do 15 sekund, bez dźwięku, do 6 MB — odtwarza się w pętli, bez dźwięku i bez pełnego ekranu.</li>
<li>Materiał i link docelowy wysyłasz mailem po zamówieniu — publikujemy w ciągu 24 godzin roboczych.</li>
<li>Każda reklama jest oznaczona etykietą „Reklama" zgodnie z prawem prasowym.</li>
<li>Nie przyjmujemy reklam: hazardu bez licencji, treści dla dorosłych, pożyczek-chwilówek, leków na receptę, kryptowalut spekulacyjnych.</li>
</ul>

<h2>Kontakt</h2>
<p>Pytania, kampanie niestandardowe, pakiety roczne: <a href="mailto:info@startend.ch" style="color:var(--acc);font-weight:700">info@startend.ch</a></p>
<footer>
<b>NIECZYTAJ.PL</b> — automatyczny serwis informacyjny. © ${new Date().getFullYear()} <a href="https://startend.ch">STARTEND GmbH</a>, Cham, Szwajcaria · <a href="/regulamin">Regulamin reklamy</a>.
</footer>
</div></body></html>`;
}

// ------------------------- /regulamin -------------------------
function regulaminPage() {
  return `<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Regulamin reklamy — NIECZYTAJ.PL</title>
<style>
:root{--paper:#fbfbfa;--ink:#141414;--mut:#6f6a64;--acc:#c8102e;--line:#e7e5e1;--aibg:#f3f0ea}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 -apple-system,'Segoe UI',Roboto,Arial,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:0 16px 60px}
header{padding:14px 0 10px;border-bottom:3px solid var(--ink);display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.logo{font-family:Georgia,serif;font-size:28px;font-weight:700;letter-spacing:-1px;margin:0}
.logo a{color:var(--ink);text-decoration:none}.logo .pl{color:var(--acc)}
.back{margin-left:auto;font-size:13px}.back a{color:var(--mut);text-decoration:none;border:1.5px solid var(--line);border-radius:20px;padding:6px 13px}
h1{font-family:Georgia,serif;font-size:30px;margin:30px 0 6px}
.sub{color:var(--mut);font-size:13.5px;margin:0 0 8px}
h2{font-family:Georgia,serif;font-size:13px;letter-spacing:1.4px;text-transform:uppercase;border-bottom:2px solid var(--ink);padding-bottom:5px;margin:30px 0 12px}
ol{padding-left:20px}li{margin:7px 0}
.note{background:var(--aibg);border-left:3px solid var(--acc);padding:12px 15px;border-radius:0 8px 8px 0;margin:22px 0;font-size:14.5px}
footer{margin-top:40px;padding-top:14px;border-top:3px solid var(--ink);font-size:12.5px;color:var(--mut)}
footer a{color:var(--mut)}
a{color:var(--acc)}
</style></head><body><div class="wrap">
<header>
<h1 class="logo"><a href="/">NIECZYTAJ<span class="pl">.PL</span></a></h1>
<div class="back"><a href="/reklama">← Cennik reklamy</a></div>
</header>
<h1>Regulamin emisji reklam</h1>
<p class="sub">Obowiązuje od 9 sierpnia 2026. Wydawca: STARTEND GmbH, Cham, Szwajcaria (UID CHE-223.488.613), kontakt: <a href="mailto:info@startend.ch">info@startend.ch</a>.</p>

<h2>1. Kto może kupić</h2>
<ol>
<li>Reklamy sprzedajemy <b>wyłącznie przedsiębiorcom</b> (B2B). Składając zamówienie, Zamawiający oświadcza, że działa w ramach działalności gospodarczej lub zawodowej.</li>
<li>Umowa nie jest umową z konsumentem — nie stosuje się do niej prawa odstąpienia w terminie 14 dni.</li>
<li>Zamawiający podaje numer NIP/VAT. Fakturę wystawia STARTEND GmbH; podatek rozlicza nabywca (odwrotne obciążenie).</li>
</ol>

<h2>2. Zamówienie i emisja</h2>
<ol start="4">
<li>Ceny podane w cenniku są cenami netto. Minimalny okres emisji: <b>7 dni</b>. Płatność z góry.</li>
<li>Po opłaceniu Zamawiający otrzymuje link do formularza, w którym samodzielnie podaje materiał reklamowy, adres docelowy i datę startu.</li>
<li>Emisja rusza automatycznie, najpóźniej następnego dnia roboczego po przesłaniu poprawnego materiału. Opóźnienie po stronie Zamawiającego (brak materiału) nie przedłuża okresu emisji ponad 30 dni od zapłaty.</li>
<li>Jedno miejsce reklamowe zajmuje w danym momencie jeden reklamodawca. Przy kolizji terminów decyduje kolejność zapłaty; następny Zamawiający dostaje najbliższy wolny termin, o czym informujemy mailem.</li>
<li>Każda reklama jest widocznie oznaczona etykietą „Reklama".</li>
</ol>

<h2>3. Czego nie przyjmujemy</h2>
<ol start="9">
<li>Nie emitujemy reklam: hazardu bez polskiej licencji, treści dla dorosłych, pożyczek krótkoterminowych („chwilówek"), leków na receptę, spekulacyjnych instrumentów finansowych i kryptowalut, treści naruszających prawo, dyskryminujących lub wprowadzających w błąd.</li>
<li>Materiał nie może udawać treści redakcyjnej ani elementów interfejsu serwisu, migać, odtwarzać dźwięku ani otwierać okien bez akcji użytkownika.</li>
<li>Zamawiający oświadcza, że ma prawa do przesłanego materiału i ponosi odpowiedzialność za jego treść oraz za stronę docelową.</li>
</ol>

<div class="note"><b>12. Usunięcie reklamy.</b> Wydawca może w każdej chwili i bez uprzedzenia usunąć reklamę, która narusza pkt 9–11. W takim przypadku <b>opłata nie podlega zwrotowi</b> — sankcja obejmuje cały opłacony okres emisji. Wydawca może też odmówić emisji przed jej startem; wtedy zwraca pełną opłatę w ciągu 14 dni.</div>

<h2>4. Serwis i odpowiedzialność</h2>
<ol start="13">
<li>NIECZYTAJ.PL jest serwisem zautomatyzowanym: dobór i kolejność treści ustala algorytm, krótkie streszczenia generuje AI. Sąsiedztwo reklamy z konkretną treścią jest losowe i nie stanowi rekomendacji żadnej ze stron.</li>
<li>Nie gwarantujemy określonej liczby odsłon ani kliknięć. Statystyki serwisu podajemy jawnie na stronie <a href="/reklama">cennika</a>.</li>
<li>Przy przerwie technicznej dłuższej niż 24 godziny okres emisji przedłużamy o czas przerwy. Odpowiedzialność Wydawcy ogranicza się do wartości opłaconego zamówienia.</li>
<li>Dane Zamawiającego przetwarzamy wyłącznie w celu realizacji zamówienia i rozliczeń. Płatności obsługuje Stripe — nie przechowujemy danych kart.</li>
<li>Spory rozstrzyga prawo szwajcarskie, sąd właściwy dla siedziby Wydawcy (Zug, Szwajcaria).</li>
</ol>
<footer>
<b>NIECZYTAJ.PL</b> · © ${new Date().getFullYear()} <a href="https://startend.ch">STARTEND GmbH</a>, Cham (CH) · <a href="/reklama">cennik</a> · <a href="mailto:info@startend.ch">info@startend.ch</a>
</footer>
</div></body></html>`;
}

// ------------------------- server -------------------------
function countView(city) {
  state.pv.total++;
  const d = warsawDay();
  state.pv.days[d] = (state.pv.days[d] || 0) + 1;
  if (city) state.pv.cities[city] = (state.pv.cities[city] || 0) + 1;
  const keys = Object.keys(state.pv.days).sort();
  while (keys.length > 14) delete state.pv.days[keys.shift()];
}
function readBody(req, cb) {
  let b = '';
  req.on('data', c => { b += c; if (b.length > 1e6) req.destroy(); });
  req.on('end', () => cb(b));
}
const server = http.createServer((req, res) => {
  const url = (req.url || '/').split('?')[0];
  try {
    if (url === '/' && req.method === 'GET') {
      countView();
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'public, max-age=120' });
      return res.end(page());
    }
    if (url === '/reklama' && req.method === 'GET') {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'public, max-age=300' });
      return res.end(reklamaPage());
    }
    if (url === '/regulamin' && req.method === 'GET') {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'public, max-age=3600' });
      return res.end(regulaminPage());
    }
    if (url === '/api/geo' && req.method === 'POST') {
      return readBody(req, b => {
        try {
          const j = JSON.parse(b || '{}');
          const k = String(j.n || 'none').slice(0, 24) + ':' + String(j.d || '?').slice(0, 12);
          state.pv.geo[k] = (state.pv.geo[k] || 0) + 1;
        } catch (e) {}
        res.writeHead(204); res.end();
      });
    }
    const cityDef = CITIES.find(c => '/' + c.slug === url);
    if (cityDef && req.method === 'GET') {
      countView(cityDef.slug);
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'public, max-age=120' });
      return res.end(page(cityDef));
    }
    if (url === '/health') {
      const okN = FEEDS.filter(f => state.feedCache[f.id] && state.feedCache[f.id].ok).length;
      res.writeHead(200, { 'content-type': 'application/json' });
      return res.end(JSON.stringify({
        ok: state.lastRefresh > 0, lastRefresh: new Date(state.lastRefresh).toISOString(),
        refreshCount: state.refreshCount, feedsOk: okN, feedsTotal: FEEDS.length,
        hot: state.clusters.length, summaries: state.summaries.size,
        cities: Object.fromEntries(CITIES.map(c => [c.slug, (state.cities[c.slug] || { clusters: [] }).clusters.length])),
        ads: ADS.length, price: PRICE, aiSelf: !!ANTHROPIC_API_KEY, pv: state.pv,
        uptimeMin: Math.round((Date.now() - state.boot) / 60000),
        feeds: FEEDS.map(f => ({ id: f.id, ok: !!(state.feedCache[f.id] && state.feedCache[f.id].ok), n: state.feedCache[f.id] ? state.feedCache[f.id].items.length : 0, via: f.via || '', err: state.feedCache[f.id] ? state.feedCache[f.id].error : 'pending' })),
      }));
    }
    if (url === '/api/top') {
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
      return res.end(JSON.stringify({
        generatedAt: new Date().toISOString(),
        clusters: state.clusters.map(c => ({
          key: c.key, cat: c.cat, srcCount: c.srcCount, ageMin: Math.round((Date.now() - c.newest) / 60000),
          title: c.lead.title, hasSummary: state.summaries.has(c.key),
          sources: c.items.slice(0, 6).map(i => ({ name: i.srcName, title: i.title, link: i.link, desc: i.desc.slice(0, 200) })),
        })),
      }));
    }
    if (url === '/api/summaries' && req.method === 'POST') {
      if (!PUSH_TOKEN || req.headers['x-push-token'] !== PUSH_TOKEN) { res.writeHead(401); return res.end('unauthorized'); }
      return readBody(req, b => {
        try {
          const j = JSON.parse(b);
          let n = 0;
          for (const s of (j.summaries || [])) if (s && s.key && s.text) { putSummary(s.key, String(s.text).slice(0, 300), 'n8n'); n++; }
          console.log(`[ai] received ${n} summaries (n8n)`);
          res.writeHead(200, { 'content-type': 'application/json' });
          res.end(JSON.stringify({ ok: true, stored: n }));
        } catch (e) { res.writeHead(400); res.end('bad json'); }
      });
    }
    if (url === '/robots.txt') { res.writeHead(200, { 'content-type': 'text/plain' }); return res.end('User-agent: *\nAllow: /\n'); }
    if (url === '/favicon.ico') { res.writeHead(204); return res.end(); }
    res.writeHead(302, { location: '/' });
    res.end();
  } catch (e) {
    state.lastError = String(e).slice(0, 300);
    console.log('[server] error: ' + state.lastError);
    try { res.writeHead(500); res.end('error'); } catch (_) {}
  }
});
server.listen(PORT, () => console.log(`nieczytaj.pl v1.6 listening on :${PORT} (refresh ${REFRESH_MIN} min, feeds: ${FEEDS.length}+${CITIES.reduce((a, c) => a + c.feeds.length, 0)} city, ads: ${ADS.length})`));
refresh().catch(e => console.log('[refresh] boot error: ' + String(e).slice(0, 300)));
setInterval(() => refresh().catch(e => console.log('[refresh] error: ' + String(e).slice(0, 300))), REFRESH_MIN * 60000);

// ---- cennik reklam (nadpisanie konfiguracyjne; zmiana ceny = tylko ta zmienna) ----
Object.assign(PRICE, { baner7: 490, baner30: 1490, kaf7: 390, kaf30: 990, box7: 190, box30: 590 });
console.log('[ads] cennik:', JSON.stringify(PRICE));

// ---- config tail: ceny nadpisywane tutaj (najtansza zmiana - tylko ta zmienna) ----
Object.assign(PRICE, { baner7: 490, baner30: 1490, kaf7: 390, kaf30: 990, box7: 290, box30: 690 });
console.log('[ads] cennik (tail):', JSON.stringify(PRICE));
