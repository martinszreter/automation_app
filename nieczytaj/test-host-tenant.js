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
    assert(/lang="de"/.test(deHome.body), 'DE / html lang=de');
    assert(/LIESNICHT/.test(deHome.body), 'DE / brand LIESNICHT');
    assert(!/NIECZYTAJ/.test(deHome.body), 'DE / no NIECZYTAJ');
    assert(/Nicht alles lesen/.test(deHome.body), 'DE / German copy');
    assert(/Werbung/.test(deHome.body), 'DE / Werbung link');

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
