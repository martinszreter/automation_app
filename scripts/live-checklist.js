'use strict';

// LIVE checklist: plain HTTP GETs against our own product URLs. For every
// target it records, with a reason for each verdict:
//   https     the page loads over HTTPS with a 2xx
//   healthz   /healthz answers 200 with {"ok":true}
//   imprint   the landing page names the imprint company (STARTEND GmbH)
//   checkout  a checkout link exists and answers 2xx or redirects to Stripe
//   login     a sign-in entry point is present on the landing page
// Output: <out>/latest.json (per-target results + reasons + regressions) and
// <out>/index.html (the board). A check that passed last time and fails now
// is a regression; with BUS_URL set, regressions are posted to the agent bus
// as one SIGNAL.
//
//   node scripts/live-checklist.js [--targets live-targets.json] [--out reports/live]
//                                  [--previous <file or URL>] [--report-url <url>]
// Env: BUS_URL (agent bus intake), CHECKLIST_TIMEOUT_MS (default 15000).

const fs = require('node:fs');
const path = require('node:path');

const IMPRINT = process.env.CHECKLIST_IMPRINT || 'STARTEND GmbH';
const TIMEOUT_MS = Number(process.env.CHECKLIST_TIMEOUT_MS || 15_000);
const CHECKS = ['https', 'healthz', 'imprint', 'checkout', 'login'];
const UA = 'startend-live-checklist/1 (+https://github.com/martinszreter/deploy-template)';

const esc = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

async function get(url, { redirect = 'follow', accept = 'text/html' } = {}) {
  const started = Date.now();
  try {
    const res = await fetch(url, {
      redirect,
      headers: { 'user-agent': UA, accept },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const text = await res.text();
    return { ok: true, status: res.status, url: res.url || url, text, ms: Date.now() - started, location: res.headers.get('location') };
  } catch (err) {
    // Node wraps socket errors: the useful code sits on err.cause (or on the
    // first of an AggregateError's errors when several addresses were tried).
    const cause = err.cause || {};
    const reason =
      err.name === 'TimeoutError'
        ? `no answer within ${TIMEOUT_MS} ms`
        : cause.code || cause.errors?.[0]?.code || cause.message || err.message;
    return { ok: false, status: 0, url, text: '', ms: Date.now() - started, error: reason };
  }
}

const pass = (reason, extra = {}) => ({ ok: true, reason, ...extra });
const fail = (reason, extra = {}) => ({ ok: false, reason, ...extra });

// Finds the first checkout-ish link on the page: /checkout, a Stripe payment
// link, or a form posting to /checkout.
function findCheckoutLink(html, base) {
  const m =
    html.match(/(?:href|action)=["']([^"']*(?:\/checkout|checkout\.stripe\.com|buy\.stripe\.com)[^"']*)["']/i);
  if (!m) return null;
  try {
    return new URL(m[1], base).toString();
  } catch {
    return null;
  }
}

const hasLogin = (html) =>
  /(?:href=["'][^"']*\/(?:auth|login|signin|sign-in|anmelden)[^"']*["'])|(?:sign in|log in|login|anmelden|einloggen)/i.test(html);

async function checkTarget(target) {
  const checks = {};
  const landing = await get(target.url);
  const origin = new URL(landing.url || target.url).origin;
  const wantsTls = target.url.startsWith('https://');

  if (!landing.ok) checks.https = fail(`landing page unreachable: ${landing.error}`, { ms: landing.ms });
  else if (landing.status < 200 || landing.status >= 300)
    checks.https = fail(`landing page answered ${landing.status}`, { status: landing.status, ms: landing.ms });
  else if (wantsTls && !landing.url.startsWith('https://'))
    checks.https = fail(`landed on ${landing.url} (not HTTPS)`, { status: landing.status, ms: landing.ms });
  else checks.https = pass(`${landing.status} in ${landing.ms} ms${wantsTls ? ' over HTTPS' : ' (http target, no TLS check)'}`, { status: landing.status, ms: landing.ms });

  const health = await get(`${origin}/healthz`, { accept: 'application/json' });
  if (!health.ok) checks.healthz = fail(`/healthz unreachable: ${health.error}`);
  else if (health.status !== 200) checks.healthz = fail(`/healthz answered ${health.status}`, { status: health.status });
  else {
    let body = null;
    try { body = JSON.parse(health.text); } catch { /* not JSON */ }
    checks.healthz = body && body.ok === true
      ? pass(`200 {"ok":true}${body.app ? ` app=${body.app}` : ''}`, { status: 200 })
      : fail(`/healthz is 200 but body is not {"ok":true}: ${health.text.slice(0, 80)}`, { status: 200 });
  }

  const html = landing.text || '';
  checks.imprint = html.toLowerCase().includes(IMPRINT.toLowerCase())
    ? pass(`landing page names ${IMPRINT}`)
    : fail(landing.ok ? `"${IMPRINT}" not found on the landing page` : 'landing page not loaded');

  const checkoutUrl = landing.ok ? findCheckoutLink(html, landing.url) : null;
  if (!checkoutUrl) checks.checkout = fail(landing.ok ? 'no checkout link on the landing page' : 'landing page not loaded');
  else {
    const co = await get(checkoutUrl, { redirect: 'manual' });
    const toStripe = co.status >= 300 && co.status < 400 && /stripe\.com/i.test(co.location || '');
    if (!co.ok) checks.checkout = fail(`${checkoutUrl} unreachable: ${co.error}`, { url: checkoutUrl });
    else if ((co.status >= 200 && co.status < 300) || toStripe)
      checks.checkout = pass(toStripe ? `${co.status} → Stripe Checkout` : `${co.status} from ${checkoutUrl}`, { url: checkoutUrl, status: co.status });
    else if (co.status >= 300 && co.status < 400)
      checks.checkout = fail(`${checkoutUrl} redirects to ${co.location} instead of Stripe`, { url: checkoutUrl, status: co.status });
    else checks.checkout = fail(`${checkoutUrl} answered ${co.status}`, { url: checkoutUrl, status: co.status });
  }

  checks.login = hasLogin(html)
    ? pass('sign-in entry point present on the landing page')
    : fail(landing.ok ? 'no sign-in link or wording on the landing page' : 'landing page not loaded');

  const expect = { healthz: true, imprint: true, checkout: true, login: true, ...(target.expect || {}), https: true };
  const failing = CHECKS.filter((c) => expect[c] && !checks[c].ok);
  return {
    name: target.name,
    project: target.project || '',
    url: target.url,
    checkedAt: new Date().toISOString(),
    ok: failing.length === 0,
    failing,
    expect,
    checks,
  };
}

// ok → fail on a check the target expects = regression.
function detectRegressions(previous, current) {
  const before = new Map((previous?.targets || []).map((t) => [t.name, t]));
  const regressions = [];
  for (const t of current) {
    const p = before.get(t.name);
    if (!p) continue;
    for (const c of CHECKS) {
      if (t.expect[c] && p.checks?.[c]?.ok === true && t.checks[c].ok === false) {
        regressions.push({ target: t.name, url: t.url, check: c, reason: t.checks[c].reason });
      }
    }
  }
  return regressions;
}

function renderBoard(report) {
  const cell = (t, c) => {
    const r = t.checks[c];
    const cls = r.ok ? 'ok' : t.expect[c] ? 'fail' : 'na';
    const mark = r.ok ? '✓' : t.expect[c] ? '✗' : '–';
    return `<td class="${cls}" title="${esc(r.reason)}">${mark}<small>${esc(r.reason)}</small></td>`;
  };
  const rows = report.targets
    .map(
      (t) => `<tr class="${t.ok ? 'pass' : 'broken'}">
<th scope="row"><a href="${esc(t.url)}">${esc(t.name)}</a><br><small>${esc(t.project)}</small></th>
${CHECKS.map((c) => cell(t, c)).join('\n')}
</tr>`
    )
    .join('\n');
  const regs = report.regressions.length
    ? `<section class="regressions"><h2>Regressionen (${report.regressions.length})</h2><ul>${report.regressions
        .map((r) => `<li><strong>${esc(r.target)}</strong> · ${esc(r.check)}: ${esc(r.reason)}</li>`)
        .join('')}</ul></section>`
    : '<p class="muted">Keine Regressionen gegenüber dem letzten Lauf.</p>';
  const s = report.summary;
  return `<!doctype html>
<html lang="de-CH">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>LIVE-Checkliste — STARTEND</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 72rem; padding: 0 1rem; line-height: 1.4; color: #111; background: #fff; }
  h1 { margin: 0 0 .25rem; } .muted { color: #666; }
  .kpi { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0 1.5rem; }
  .kpi div { border: 1px solid #ddd; border-radius: 8px; padding: .6rem 1rem; min-width: 8rem; }
  .kpi strong { display: block; font-size: 1.6rem; }
  table { border-collapse: collapse; width: 100%; font-size: .9rem; }
  th, td { border: 1px solid #e5e5e5; padding: .45rem .5rem; text-align: left; vertical-align: top; }
  thead th { background: #f6f6f6; }
  th[scope=row] { white-space: nowrap; }
  td small { display: block; color: #666; font-size: .72rem; max-width: 16rem; }
  td.ok { background: #e8f7ec; } td.fail { background: #fde8e8; } td.na { background: #f7f7f7; color: #999; }
  tr.broken th[scope=row] { border-left: 4px solid #d33; }
  .regressions { background: #fff3cd; border: 1px solid #ffe69c; border-radius: 8px; padding: .5rem 1rem; margin: 1rem 0; }
  footer { margin-top: 2rem; font-size: .85rem; color: #666; }
</style>
</head>
<body>
<h1>LIVE-Checkliste</h1>
<p class="muted">Stand ${esc(report.generatedAt)} · alle 4 Stunden · <a href="latest.json">latest.json</a></p>
<div class="kpi">
<div><strong>${s.targets}</strong>Ziele</div>
<div><strong>${s.passing}</strong>in Ordnung</div>
<div><strong>${s.failing}</strong>mit Befund</div>
<div><strong>${s.regressions}</strong>Regressionen</div>
</div>
${regs}
<table>
<thead><tr><th scope="col">Ziel</th><th scope="col">HTTPS</th><th scope="col">/healthz</th><th scope="col">Impressum</th><th scope="col">Checkout</th><th scope="col">Login</th></tr></thead>
<tbody>
${rows}
</tbody>
</table>
<footer>✓ erwartet und in Ordnung · ✗ erwartet und fehlgeschlagen · – nicht erwartet (nur informativ). Quelle: <code>live-targets.json</code>, Script: <code>scripts/live-checklist.js</code>.</footer>
</body>
</html>
`;
}

// Agent bus intake: GET hands out a short-lived bus_cursor, POST writes a row.
async function postSignal(busUrl, report, reportUrl) {
  if (!busUrl) return { posted: false, reason: 'BUS_URL not set' };
  try {
    const state = await fetch(busUrl, { headers: { 'user-agent': UA, accept: 'application/json' }, signal: AbortSignal.timeout(TIMEOUT_MS) });
    let cursor = '';
    try {
      const json = await state.json();
      cursor = json.bus_cursor || json.cursor || (json.bus && json.bus.bus_cursor) || '';
    } catch { /* fall through */ }
    if (!cursor) return { posted: false, reason: `bus GET ${state.status} returned no bus_cursor` };
    const what = report.regressions
      .slice(0, 6)
      .map((r) => `${r.target} ${r.check}: ${r.reason}`)
      .join(' | ');
    const res = await fetch(busUrl, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'user-agent': UA },
      body: JSON.stringify({
        team: 'ops',
        project: 'live-checklist',
        type: 'SIGNAL',
        what: `${report.regressions.length} regression(s) on the LIVE checklist: ${what}`,
        next: 'Fix the failing check(s), then rerun the live-checklist workflow.',
        link: reportUrl || '',
        bus_cursor: cursor,
      }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    return { posted: res.ok, reason: `bus POST ${res.status}` };
  } catch (err) {
    return { posted: false, reason: `bus error: ${err.message}` };
  }
}

async function loadPrevious(source) {
  if (!source) return null;
  try {
    if (/^https?:\/\//.test(source)) {
      const res = await fetch(source, { headers: { 'user-agent': UA }, signal: AbortSignal.timeout(TIMEOUT_MS) });
      if (!res.ok) return null;
      return await res.json();
    }
    return JSON.parse(fs.readFileSync(source, 'utf8'));
  } catch {
    return null;
  }
}

async function runChecklist(targets, { previous = null, busUrl = '', reportUrl = '' } = {}) {
  const results = [];
  for (const target of targets) results.push(await checkTarget(target));
  const regressions = detectRegressions(previous, results);
  const report = {
    generatedAt: new Date().toISOString(),
    imprint: IMPRINT,
    summary: {
      targets: results.length,
      passing: results.filter((t) => t.ok).length,
      failing: results.filter((t) => !t.ok).length,
      regressions: regressions.length,
    },
    regressions,
    targets: results,
    bus: null,
  };
  if (regressions.length) report.bus = await postSignal(busUrl, report, reportUrl);
  return report;
}

function parseArgs(argv) {
  const args = { targets: 'live-targets.json', out: 'reports/live', previous: '', reportUrl: process.env.REPORT_URL || '' };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--targets') args.targets = argv[++i];
    else if (a === '--out') args.out = argv[++i];
    else if (a === '--previous') args.previous = argv[++i];
    else if (a === '--report-url') args.reportUrl = argv[++i];
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const root = path.join(__dirname, '..');
  const targetsPath = path.resolve(root, args.targets);
  const outDir = path.resolve(root, args.out);
  const { targets } = JSON.parse(fs.readFileSync(targetsPath, 'utf8'));
  const previous = (await loadPrevious(args.previous)) || (await loadPrevious(path.join(outDir, 'latest.json')));

  const report = await runChecklist(targets, { previous, busUrl: process.env.BUS_URL || '', reportUrl: args.reportUrl });

  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'latest.json'), JSON.stringify(report, null, 2) + '\n');
  fs.writeFileSync(path.join(outDir, 'index.html'), renderBoard(report));

  for (const t of report.targets) {
    console.log(`${t.ok ? '✓' : '✗'} ${t.name.padEnd(28)} ${t.failing.length ? t.failing.map((c) => `${c}: ${t.checks[c].reason}`).join('; ') : 'ok'}`);
  }
  const s = report.summary;
  console.log(`\n${s.passing}/${s.targets} targets ok, ${s.regressions} regression(s).${report.bus ? ` Bus: ${report.bus.reason}` : ''}`);
  // Findings are reported, not fatal: the run is green when the checklist ran.
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err.stack || err.message);
    process.exit(1);
  });
}

module.exports = { checkTarget, detectRegressions, renderBoard, runChecklist, postSignal, findCheckoutLink, CHECKS };
