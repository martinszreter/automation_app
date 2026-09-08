// Lighthouse gate: mobile, every category >= 90, zero layout shift, zero
// console errors — on every public page. Exits 1 when any page misses.
//
//   ZORBECK_BASE_URL=http://127.0.0.1:8765 node lighthouse.mjs
//
// Each page is measured LIGHTHOUSE_RUNS times (default 3) and the median score
// per category is gated, as Lighthouse itself recommends: a single run on a
// cold, shared CI runner swings by 20+ points on performance without any change
// to the page. Chrome is found by chrome-launcher (CHROME_PATH overrides).

import { launch } from 'chrome-launcher';
import lighthouse from 'lighthouse';
import { writeFileSync, mkdirSync } from 'node:fs';

const BASE = (process.env.ZORBECK_BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
const PATHS = (process.env.LIGHTHOUSE_PATHS || '/,/impressum,/agb,/datenschutz').split(',');
const MIN = Number(process.env.LIGHTHOUSE_MIN || 0.9);
const RUNS = Math.max(1, Number(process.env.LIGHTHOUSE_RUNS || 3));
const CATEGORIES = ['performance', 'accessibility', 'best-practices', 'seo'];
const OUT = process.env.LIGHTHOUSE_OUT || 'lighthouse-results';

mkdirSync(OUT, { recursive: true });

const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
};

const chrome = await launch({
  chromeFlags: ['--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
});

let failed = false;
const rows = [];
try {
  for (const path of PATHS) {
    const url = BASE + path;
    const slug = path === '/' ? 'landing' : path.replace(/\W+/g, '_');
    const runs = [];
    for (let i = 0; i < RUNS; i += 1) {
      const result = await lighthouse(url, {
        port: chrome.port,
        output: 'json',
        logLevel: 'error',
        onlyCategories: CATEGORIES,
        // Lighthouse's default is the mobile form factor with simulated throttling.
      });
      const lhr = result.lhr;
      writeFileSync(`${OUT}/${slug}-${i + 1}.json`, JSON.stringify(lhr, null, 1));
      runs.push({
        scores: Object.fromEntries(CATEGORIES.map((c) => [c, lhr.categories[c].score ?? 0])),
        cls: lhr.audits['cumulative-layout-shift']?.numericValue ?? 0,
        consoleOk: (lhr.audits['errors-in-console']?.score ?? 1) === 1,
      });
    }

    const scores = Object.fromEntries(CATEGORIES.map((c) => [c, median(runs.map((r) => r.scores[c]))]));
    const cls = median(runs.map((r) => r.cls));
    const consoleOk = runs.every((r) => r.consoleOk);

    const misses = [];
    for (const c of CATEGORIES) if (scores[c] < MIN) misses.push(`${c}=${Math.round(scores[c] * 100)}`);
    if (cls > 0) misses.push(`CLS=${cls.toFixed(3)}`);
    if (!consoleOk) misses.push('console-errors');
    if (misses.length) failed = true;
    rows.push({
      path,
      ...Object.fromEntries(CATEGORIES.map((c) => [c, Math.round(scores[c] * 100)])),
      'perf runs': runs.map((r) => Math.round(r.scores.performance * 100)).join('/'),
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
  console.error(`Lighthouse gate failed (median of ${RUNS} runs; min ${MIN * 100} per category, CLS 0, no console errors).`);
  process.exit(1);
}
console.log(`Lighthouse gate passed on ${rows.length} page(s), median of ${RUNS} runs each.`);
