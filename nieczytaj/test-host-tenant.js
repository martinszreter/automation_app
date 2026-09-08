'use strict';
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

const PORT = 18082;
const fails = [];
function assert(cond, msg) {
  if (!cond) { fails.push(msg); console.log('FAIL', msg); }
  else console.log('OK  ', msg);
}

function req(host, urlPath) {
  return new Promise((resolve, reject) => {
    const r = http.request({
      hostname: '127.0.0.1', port: PORT, path: urlPath, method: 'GET',
      headers: { host },
    }, res => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve({
        status: res.statusCode,
        location: res.headers.location || '',
        body: Buffer.concat(chunks).toString('utf8'),
      }));
    });
    r.on('error', reject);
    r.end();
  });
}

const child = spawn(process.execPath, [path.join(__dirname, 'server.js')], {
  cwd: __dirname,
  env: { ...process.env, PORT: String(PORT) },
  stdio: ['ignore', 'pipe', 'pipe'],
});
let buf = '';
const ready = new Promise((resolve, reject) => {
  const t = setTimeout(() => reject(new Error('server start timeout')), 8000);
  function onOut(d) {
    buf += d;
    if (/listening/.test(buf)) { clearTimeout(t); resolve(); }
  }
  child.stdout.on('data', onOut);
  child.stderr.on('data', onOut);
  child.on('exit', code => reject(new Error('server exited ' + code + '\n' + buf)));
});

(async () => {
  try {
    await ready;
    const deHome = await req('www.liesnicht.ch', '/');
    assert(deHome.status === 200, 'DE / 200');
    assert(/lang="de-CH"/.test(deHome.body), 'DE / html lang=de-CH');
    assert(/LIESNICHT/.test(deHome.body), 'DE / brand LIESNICHT');
    assert(!/NIECZYTAJ/.test(deHome.body), 'DE / no NIECZYTAJ');
    assert(/Nicht alles lesen/.test(deHome.body), 'DE / German copy');
    assert(/DACH/.test(deHome.body), 'DE / DACH feeds copy');
    assert(/Werbung/.test(deHome.body), 'DE / Werbung link');
    assert(/href="https:\/\/www\.liesnicht\.ch\/"/.test(deHome.body) && /rel="canonical"/.test(deHome.body), 'DE / canonical www.liesnicht.ch');
    assert(/hreflang="de-CH"/.test(deHome.body) && /hreflang="fr-CH"/.test(deHome.body) && /hreflang="it-CH"/.test(deHome.body) && /hreflang="en-CH"/.test(deHome.body), 'DE / hreflang de-CH/fr-CH/it-CH/en-CH');
    assert(/>DE<\/a>/.test(deHome.body) && />FR<\/a>/.test(deHome.body) && />IT<\/a>/.test(deHome.body) && />EN<\/a>/.test(deHome.body), 'DE / switcher DE|FR|IT|EN');
    assert(/data-r="10"/.test(deHome.body) && /data-r="20"/.test(deHome.body) && /data-r="50"/.test(deHome.body), 'DE / radius chips 10/20/50');
    assert(/mein Standort/i.test(deHome.body), 'DE / Mein Standort');
    const geoJson = deHome.body.match(/var NC_GEO=(\[[^\]]*\])/);
    assert(geoJson && JSON.parse(geoJson[1]).length === 9, 'DE / NC_GEO exactly 9 CH cities');
    assert(!/warszawa/.test(deHome.body), 'DE / no PL city list');
    assert(!/<article class="tile[\s\S]*?\d+\s*km/.test(deHome.body), 'DE / no fake km on tiles');

    const deRail = await req('liesnicht-production.up.railway.app', '/');
    assert(deRail.status === 200 && /LIESNICHT/.test(deRail.body) && !/NIECZYTAJ/.test(deRail.body), 'railway.app host is DE');

    const plHome = await req('www.nieczytaj.pl', '/');
    assert(plHome.status === 200, 'PL / 200');
    assert(/lang="pl"/.test(plHome.body), 'PL / html lang=pl');
    assert(/NIECZYTAJ/.test(plHome.body), 'PL / brand NIECZYTAJ');
    assert(!/LIESNICHT/.test(plHome.body), 'PL / no LIESNICHT');
    assert(/Nie czytaj wszystkiego/.test(plHome.body), 'PL / Polish copy');

    const deAds = await req('www.liesnicht.ch', '/werbung');
    assert(deAds.status === 200, 'DE /werbung 200');
    assert(/CHF 149/.test(deAds.body) && /CHF 119/.test(deAds.body) && /CHF 89/.test(deAds.body), 'DE 7d locked 149/119/89');
    assert(/CHF 449/.test(deAds.body) && /CHF 299/.test(deAds.body) && /CHF 199/.test(deAds.body), 'DE 30d locked 449/299/199');
    assert(!/490/.test(deAds.body) && !/NIECZYTAJ/.test(deAds.body), 'DE /werbung no Polish prices/brand');
    assert(deAds.body.includes('https://buy.stripe.com/6oU5kE8RD3DrgzG2Tx0x20f'), 'DE /werbung CHF1 Stripe test link');
    assert(/CHF 1/.test(deAds.body), 'DE /werbung CHF 1 label');

    const plAds = await req('www.nieczytaj.pl', '/reklama');
    assert(plAds.status === 200, 'PL /reklama 200');
    assert(/490/.test(plAds.body) && /390/.test(plAds.body) && /290/.test(plAds.body), 'PL prices 490/390/290');
    assert(/1490/.test(plAds.body), 'PL 30d 1490');
    assert(!/CHF 149/.test(plAds.body), 'PL /reklama no DE locked CHF 149');

    const imp = await req('www.liesnicht.ch', '/impressum');
    const ds = await req('www.liesnicht.ch', '/datenschutz');
    assert(imp.status === 200 && /Impressum/.test(imp.body) && /STARTEND GmbH/.test(imp.body), 'DE /impressum 200');
    assert(ds.status === 200 && /Datenschutz/.test(ds.body), 'DE /datenschutz 200');

    const plWerbung = await req('www.nieczytaj.pl', '/werbung');
    assert(plWerbung.status === 302 && plWerbung.location === '/reklama', 'PL /werbung → /reklama');

    const deHealth = await req('www.liesnicht.ch', '/health');
    const plHealth = await req('www.nieczytaj.pl', '/health');
    const deJ = JSON.parse(deHealth.body);
    const plJ = JSON.parse(plHealth.body);
    assert(deJ.price.baner7 === 149 && deJ.price.kaf7 === 119 && deJ.price.box7 === 89, 'DE health locked prices');
    assert(plJ.price.baner7 === 490 && plJ.price.kaf7 === 390 && plJ.price.box7 === 290, 'PL health 490/390/290');
    assert((deJ.feeds || []).some(f => f.id === 'tagesschau'), 'DE health lists DACH feeds');
    assert((plJ.feeds || []).some(f => f.id === 'onet') && !(plJ.feeds || []).some(f => f.id === 'tagesschau'), 'PL health still Polish feeds');
    assert(deJ.cities && deJ.cities.zuerich !== undefined && deJ.cities.bern !== undefined && !deJ.cities.warszawa, 'DE health CH snap cities');
    assert(plJ.cities && plJ.cities.warszawa !== undefined && !plJ.cities.zuerich, 'PL health still PL cities');

    for (const host of ['www.liesnicht.de', 'www.liesnicht.at', 'www.liesnicht.com']) {
      const h = await req(host, '/');
      assert(h.status === 200 && /LIESNICHT/.test(h.body) && !/NIECZYTAJ/.test(h.body), host + ' is LIESNICHT');
    }

    const frHome = await req('www.liesnicht.ch', '/fr');
    assert(frHome.status === 200, 'FR /fr 200');
    assert(/lang="fr-CH"/.test(frHome.body), 'FR / html lang=fr-CH');
    assert(/Ne lis pas tout/.test(frHome.body), 'FR / French chrome');
    assert(/Publicité/.test(frHome.body), 'FR / Publicité chrome');
    assert(/LIESNICHT/.test(frHome.body) && !/NIECZYTAJ/.test(frHome.body), 'FR / still LIESNICHT');
    assert(/href="\/fr\/werbung"/.test(frHome.body), 'FR / ads path prefixed');

    const itHome = await req('www.liesnicht.ch', '/it');
    const enHome = await req('www.liesnicht.ch', '/en');
    assert(itHome.status === 200 && /lang="it-CH"/.test(itHome.body) && /Non leggere tutto/.test(itHome.body), 'IT chrome');
    assert(enHome.status === 200 && /lang="en-CH"/.test(enHome.body) && /Don’t read everything|Don.t read everything/.test(enHome.body), 'EN chrome');
    assert(/Advertising/.test(enHome.body), 'EN / Advertising chrome');

    const frAds = await req('www.liesnicht.ch', '/fr/werbung');
    assert(frAds.status === 200 && /CHF 149/.test(frAds.body) && /CHF 89/.test(frAds.body), 'FR /werbung locked prices');
    assert(/lang="fr-CH"/.test(frAds.body) && /Une pub/.test(frAds.body), 'FR /werbung French chrome');
    assert(frAds.body.includes('https://buy.stripe.com/6oU5kE8RD3DrgzG2Tx0x20f'), 'FR /werbung CHF1 Stripe');

    const zh = await req('www.liesnicht.ch', '/zuerich');
    const zhFr = await req('www.liesnicht.ch', '/fr/zuerich');
    assert(zh.status === 200 && /Zürich|Zurich/.test(zh.body) && /lang="de-CH"/.test(zh.body), 'DE /zuerich snap city');
    assert(zhFr.status === 200 && /Zürich|Zurich/.test(zhFr.body) && /lang="fr-CH"/.test(zhFr.body), 'FR /fr/zuerich');
    assert(/canonical/.test(zh.body) && /www\.liesnicht\.ch\/zuerich/.test(zh.body), 'city canonical');

    const sm = await req('www.liesnicht.ch', '/sitemap.xml');
    assert(sm.status === 200 && /www\.liesnicht\.ch/.test(sm.body), 'sitemap 200 + canon host');
    assert(/\/fr<\/loc>/.test(sm.body) && /\/it<\/loc>/.test(sm.body) && /\/en<\/loc>/.test(sm.body), 'sitemap locales');
    assert(/zuerich/.test(sm.body) && /werbung/.test(sm.body) && /impressum/.test(sm.body), 'sitemap cities + legal');

    const robots = await req('www.liesnicht.ch', '/robots.txt');
    assert(/Sitemap: https:\/\/www\.liesnicht\.ch\/sitemap\.xml/.test(robots.body), 'robots sitemap');

    const plFr = await req('www.nieczytaj.pl', '/fr');
    assert(plFr.status === 302 && plFr.location === '/', 'PL /fr → / (no LIESNICHT chrome)');
    const plSm = await req('www.nieczytaj.pl', '/sitemap.xml');
    assert(plSm.status === 302, 'PL /sitemap.xml unchanged (no CH sitemap)');
  } catch (e) {
    fails.push(String(e));
    console.log('FAIL', e);
  } finally {
    child.kill('SIGTERM');
    if (fails.length) {
      console.log('\n' + fails.length + ' failed');
      process.exit(1);
    }
    console.log('\nall passed');
  }
})();
