'use strict';
// Real HTTP routes with deterministic publisher fixtures; no external feeds or payments.
const assert = require('node:assert/strict');
process.env.TENANT = 'liesnicht';
process.env.ADS_JSON = JSON.stringify([{ slot: 'baner', country: 'ch', src: 'https://fixture.invalid/CHADONLY.png' }]);
const app = require('./server');
const { server, state, tenantFromHost, feedsFor, rebuildCountryEditions, tokens, buyLink } = app;
let checks = 0;
function check(ok, label) { assert.ok(ok, label); checks++; }
const requestFixture = require('./request-fixture');
function get(host, path) { return requestFixture(server, host, path); }
const cases = [
  { code: 'ch', name: 'Schweiz', locale: 'de-CH', currency: 'CHF', sources: ['srf', 'nzz'] },
  { code: 'de', name: 'Deutschland', locale: 'de-DE', currency: 'EUR', sources: ['tagesschau', 'spiegel'] },
  { code: 'at', name: 'Österreich', locale: 'de-AT', currency: 'EUR', sources: ['standard', 'orf'] },
];
function seed() {
  state.feedCache = {};
  const now = Date.now();
  for (const c of cases) {
    const feeds = feedsFor(tenantFromHost('liesnicht.' + c.code));
    check(feeds.length >= 2, c.code + ' has at least two publisher feeds');
    for (const feed of feeds) {
      const title = c.code.toUpperCase() + 'ONLY Parlament beschliesst Budgetreform und Infrastrukturprogramm';
      const item = { src: feed.id, srcName: feed.name, cat: 'kraj', title, link: 'https://fixture.invalid/' + c.code + '/' + feed.id, at: now, desc: title, img: '', toks: tokens(title) };
      const extra = Array.from({ length: 12 }, (_, i) => {
        const extraTitle = c.code.toUpperCase() + 'ONLY ' + feed.id + ' Einzelmeldung ' + i;
        return { ...item, title: extraTitle, link: item.link + '/' + i, cat: i % 2 ? 'sport' : 'tech', at: now - (i + 1) * 60000, toks: [c.code + feed.id + String.fromCharCode(97 + i), 'unique' + i + feed.id] };
      });
      state.feedCache[feed.id] = { ok: true, at: now, items: [item, ...extra], error: '' };
    }
  }
  rebuildCountryEditions(now);
  state.lastRefresh = now;
}
(async () => {
  try {
    seed();
    const ownedFeedIds = new Set();
    for (const c of cases) {
      const host = 'www.liesnicht.' + c.code;
      const t = tenantFromHost(host);
      for (const spelling of [host, 'liesnicht.' + c.code, host.toUpperCase() + ':8080', host + '.']) {
        check(tenantFromHost(spelling).country === c.code, 'normalized host ' + spelling);
      }
      check(t.locale === c.locale && t.currency === c.currency, c.code + ' locale/currency under TENANT pin');
      for (const feed of feedsFor(t)) {
        check(!ownedFeedIds.has(feed.id), 'publisher pool disjoint: ' + feed.id);
        ownedFeedIds.add(feed.id);
      }
      for (const path of ['/', '/werbung', '/impressum', '/datenschutz', '/health', '/api/top', '/rss.xml', '/sitemap.xml', '/robots.txt']) {
        const r = await get(host, path);
        check(r.status === 200, host + path + ' 200');
        if (['/', '/werbung', '/impressum', '/datenschutz'].includes(path)) {
          check(r.body.includes('lang="' + c.locale + '"'), c.code + path + ' regional HTML language');
          check(r.body.includes('rel="canonical" href="https://' + host + path + '"'), c.code + path + ' canonical');
          check(r.body.includes('og:locale" content="' + c.locale.replace('-', '_') + '"'), c.code + path + ' OG locale');
          check(r.body.includes('.' + c.code.toUpperCase() + '</span>'), c.code + path + ' domain masthead');
          check(r.body.includes(c.name), c.code + path + ' visible country');
          check(r.body.includes('aria-label="Länderausgabe"'), c.code + path + ' edition navigation');
          check(r.body.includes('STARTEND GmbH'), c.code + path + ' publisher');
        }
        if (['/', '/api/top', '/rss.xml'].includes(path)) {
          check(r.body.includes(c.code.toUpperCase() + 'ONLY'), c.code + path + ' own stories present');
          for (const other of cases.filter(x => x.code !== c.code)) check(!r.body.includes(other.code.toUpperCase() + 'ONLY'), c.code + path + ' excludes ' + other.code + ' stories');
        }
        if (path === '/') {
          check(c.code === 'ch' ? r.body.includes('CHADONLY') : !r.body.includes('CHADONLY'), c.code + ' ad targeting');
          check(!r.body.includes('DACH-Dienste'), c.code + ' no pooled-DACH label');
          check(!r.body.includes('mein Standort'), c.code + ' no nonfunctional city control');
        }
        if (path === '/health') {
          const h = JSON.parse(r.body);
          check(h.country === c.code && h.currency === c.currency, c.code + ' health identity');
          check(Object.keys(h.cities).length === 0, c.code + ' no Polish city metrics');
          check(h.feeds.every(f => feedsFor(t).some(allowed => allowed.id === f.id)), c.code + ' health correct publishers');
        }
        if (path === '/api/top') {
          const j = JSON.parse(r.body);
          check(j.country === c.code && j.clusters.every(item => item.key.startsWith(c.code + ':')), c.code + ' isolated summary keys');
        }
        if (path === '/rss.xml') check(r.body.includes('<language>' + c.locale + '</language>'), c.code + ' RSS locale');
        if (path === '/werbung') {
          check(r.body.includes(c.currency + ' 149') && r.body.includes(c.currency + ' 449'), c.code + ' approved price/currency');
          if (c.code !== 'ch') check(!r.body.includes('CHF'), c.code + ' no Swiss checkout or test payment');
        }
        if (path === '/sitemap.xml') check(r.body.includes('https://' + host + '/werbung'), c.code + ' country sitemap');
        if (path === '/robots.txt') check(r.body.includes('https://' + host + '/sitemap.xml'), c.code + ' country robots');
      }
    }
    // An empty Austrian source pool must not show the last Swiss/German selection.
    for (const f of feedsFor(tenantFromHost('liesnicht.at'))) delete state.feedCache[f.id];
    rebuildCountryEditions();
    const empty = await get('liesnicht.at', '/');
    check(empty.body.includes('keine Nachrichten für Österreich'), 'Austria has an honest empty state');
    check(!/CHONLY|DEONLY|ATONLY/.test(empty.body), 'empty Austria never borrows stories');
    check(JSON.parse((await get('liesnicht.at', '/api/top')).body).clusters.length === 0, 'empty country API');
    check((await get('liesnicht.ch', '/')).body.includes('CHONLY'), 'other edition survives source failure');
    process.env.STRIPE_BANER7 = 'https://buy.stripe.com/test_switzerland';
    process.env.STRIPE_DE_BANER7 = 'https://buy.stripe.com/test_germany';
    const chBuy = buyLink('baner7', 'Banner', 149, tenantFromHost('liesnicht.ch'));
    const deBuy = buyLink('baner7', 'Banner', 149, tenantFromHost('liesnicht.de'));
    const atBuy = buyLink('baner7', 'Banner', 149, tenantFromHost('liesnicht.at'));
    check(chBuy.includes('test_switzerland') && chBuy.includes('CHF 149'), 'legacy checkout only in CH');
    check(deBuy.includes('test_germany') && deBuy.includes('EUR 149') && !deBuy.includes('test_switzerland'), 'German checkout is country scoped');
    check(atBuy.includes('mailto:') && atBuy.includes('Anfragen · EUR 149') && !atBuy.includes('test_switzerland'), 'missing Austrian checkout is an enquiry');
    check(tenantFromHost('liesnicht-production.up.railway.app').country === 'ch', 'preview defaults to CH');
    check(tenantFromHost('www.liesnicht.de.attacker.invalid').country === 'ch', 'host suffix spoof cannot select Germany under brand pin');
    console.log(checks + ' country checks passed');
  } catch (error) {
    console.error(error);
    process.exitCode = 1;
  }
})();
