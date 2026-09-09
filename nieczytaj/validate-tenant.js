'use strict';
// LIESNICHT tenant validator (S05-B acceptance):
//   TENANT=liesnicht boots with DE strings on any Host, and the DE ads page
//   honours the STRIPE_* Payment Link env vars (mailto fallback when unset).
// Usage: node validate-tenant.js   (exit 0 = validator passes)

const PORT = 18083;
const FAKE_BANER7 = 'https://buy.stripe.com/test_liesnicht_baner7';
const fails = [];
function assert(cond, msg) {
  if (!cond) { fails.push(msg); console.log('FAIL', msg); }
  else console.log('OK  ', msg);
}

process.env.TENANT = 'liesnicht';
process.env.STRIPE_BANER7 = FAKE_BANER7;
process.env.STRIPE_BOX7 = '';
const { server } = require('./server');
const requestFixture = require('./request-fixture');
function req(host, urlPath) { return requestFixture(server, host, urlPath); }

(async () => {
  try {

    // Plain local host — no "liesnicht" in the Host header at all.
    const home = await req('localhost:' + PORT, '/');
    assert(home.status === 200, 'TENANT=liesnicht / 200');
    assert(/lang="de-CH"/.test(home.body), 'TENANT=liesnicht / html lang=de-CH');
    assert(/LIESNICHT/.test(home.body), 'TENANT=liesnicht / brand LIESNICHT');
    assert(!/NIECZYTAJ/.test(home.body), 'TENANT=liesnicht / no NIECZYTAJ');
    assert(/Nicht alles lesen/.test(home.body), 'TENANT=liesnicht / German copy');
    assert(/Werbung/.test(home.body), 'TENANT=liesnicht / Werbung link');

    // The pin wins even for a Polish Host — this service only serves DE.
    const plHost = await req('www.nieczytaj.pl', '/');
    assert(plHost.status === 200 && /lang="de-CH"/.test(plHost.body) && /LIESNICHT/.test(plHost.body),
      'TENANT=liesnicht overrides a nieczytaj.pl Host');

    const ads = await req('localhost:' + PORT, '/werbung');
    assert(ads.status === 200, 'DE /werbung 200');
    assert(/CHF 149/.test(ads.body) && /CHF 119/.test(ads.body) && /CHF 89/.test(ads.body), 'DE /werbung locked CHF prices');
    assert(ads.body.includes(FAKE_BANER7), 'DE /werbung uses STRIPE_BANER7 Payment Link');
    assert(/Bestellen · CHF 149/.test(ads.body), 'DE /werbung Stripe button label');
    assert(/mailto:info@startend\.ch/.test(ads.body), 'DE /werbung mailto fallback for unset STRIPE_* packages');
    assert(ads.body.includes('https://buy.stripe.com/6oU5kE8RD3DrgzG2Tx0x20f'), 'DE /werbung CHF1 Stripe test link');
    assert(/STARTEND GmbH/.test(ads.body), 'DE /werbung imprint');

    const imp = await req('localhost:' + PORT, '/impressum');
    assert(imp.status === 200 && /Impressum/.test(imp.body) && /STARTEND GmbH/.test(imp.body), 'DE /impressum 200');

    const reklama = await req('localhost:' + PORT, '/reklama');
    assert(reklama.status === 302 && reklama.location === '/werbung', 'DE /reklama → /werbung');

    const health = await req('localhost:' + PORT, '/health');
    const h = JSON.parse(health.body);
    assert(health.status === 200 && h.price.baner7 === 149 && h.price.kaf7 === 119 && h.price.box7 === 89, 'DE /health locked prices');

    const sitemap = await req('localhost:' + PORT, '/sitemap.xml');
    assert(sitemap.status === 200 && /liesnicht\.ch\//.test(sitemap.body) && !/nieczytaj/.test(sitemap.body), 'DE /sitemap.xml on the pinned tenant');
    const rss = await req('localhost:' + PORT, '/rss.xml');
    assert(rss.status === 200 && /<language>de-CH<\/language>/.test(rss.body), 'DE /rss.xml on the pinned tenant');
    assert(/<link rel="canonical" href="https:\/\/www\.liesnicht\.ch\/">/.test(home.body), 'DE canonical on the pinned tenant');
  } catch (e) {
    fails.push(String(e));
    console.log('FAIL', e);
  } finally {
    if (fails.length) {
      console.log('\n' + fails.length + ' failed — validator FAILED');
      process.exit(1);
    }
    console.log('\nvalidator passes');
  }
})();

