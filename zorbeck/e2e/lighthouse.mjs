// Lighthouse gate: mobile, every category >= 90, zero layout shift, zero
// console errors — on every public page. Exits 1 when any page misses.
//
//   ZORBECK_BASE_URL=http://127.0.0.1:8765 node lighthouse.mjs
//
// Chrome is found by chrome-launcher (CHROME_PATH overrides).

import { launch } from 'chrome-launcher';
import lighthouse from 'lighthouse';
import { writeFileSync, mkdirSync } from 'node:fs';

const BASE = (process.env.ZORBECK_BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
const PATHS = (process.env.LIGHTHOUSE_PATHS || '/,/impressum,/agb,/datenschutz').split(',');
const MIN = Number(process.env.LIGHTHOUSE_MIN || 0.9);
const CATEGORIES = ['performance', 'accessibility', 'best-practices', 'seo'];
const OUT = process.env.LIGHTHOUSE_OUT || 'lighthouse-results';

mkdirSync(OUT, { recursive: true });

const chrome = await launch({
  chromeFlags: ['--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
});

let failed = false;
const rows = [];
try {
  for (const path of PATHS) {
    const url = BASE + path;
    const result = await lighthouse(url, {
      port: chrome.port,
      output: 'json',
      logLevel: 'error',
      onlyCategories: CATEGORIES,
      // Lighthouse's default is the mobile form factor with simulated throttling.
    });
    const lhr = result.lhr;
    const scores = Object.fromEntries(CATEGORIES.map((c) => [c, lhr.categories[c].score]));
    const cls = lhr.audits['cumulative-layout-shift']?.numericValue ?? 0;
    const consoleOk = (lhr.audits['errors-in-console']?.score ?? 1) === 1;
    const slug = path === '/' ? 'landing' : path.replace(/\W+/g, '_');
    writeFileSync(`${OUT}/${slug}.json`, JSON.stringify(lhr, null, 1));

    const misses = [];
    for (const c of CATEGORIES) if (scores[c] === null || scores[c] < MIN) misses.push(`${c}=${Math.round((scores[c] ?? 0) * 100)}`);
    if (cls > 0) misses.push(`CLS=${cls.toFixed(3)}`);
    if (!consoleOk) misses.push('console-errors');
    if (misses.length) failed = true;
    rows.push({
      path,
      ...Object.fromEntries(CATEGORIES.map((c) => [c, Math.round((scores[c] ?? 0) * 100)])),
      cls: Number(cls.toFixed(3)),
      console: consoleOk ? 'clean' : 'ERRORS',
      result: misses.length ? `FAIL ${misses.join(' ')}` : 'ok',
    });
  }
} finally {
  await chrome.kill();
}

console.table(rows);
if (failed) {
  console.error(`Lighthouse gate failed (min ${MIN * 100} per category, CLS 0, no console errors).`);
  process.exit(1);
}
console.log(`Lighthouse gate passed on ${rows.length} page(s).`);
