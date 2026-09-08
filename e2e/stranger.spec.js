'use strict';

// The stranger journey on a bare checkout: land → understand the offer in
// 10 s → find the X Autopilot checkout entry point → imprint → /healthz.
// Nothing is paid and nothing external is called: the app runs with dummy env
// (see e2e/env.js), so the journey stops at the checkout link on purpose.

const { test, expect } = require('@playwright/test');
const env = require('./env.js');

const ownUrl = (url) => url.startsWith(env.baseURL);

// Console errors, uncaught exceptions and cumulative layout shift are
// collected on every page so the quality bar (zero console errors, no
// layout shift) is asserted, not eyeballed.
test.beforeEach(async ({ page }) => {
  page.__errors = [];
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    // A resource that failed to load from a third-party host (the web font
    // on /x-autopilot/) is not our code failing; errors raised by our own
    // pages and scripts always count.
    const at = msg.location() && msg.location().url;
    if (at && !ownUrl(at)) return;
    page.__errors.push(`console: ${msg.text()}`);
  });
  page.on('pageerror', (err) => page.__errors.push(`pageerror: ${err.message}`));
  await page.addInitScript(() => {
    window.__cls = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) window.__cls += entry.value;
      }
    }).observe({ type: 'layout-shift', buffered: true });
  });
});

test.afterEach(async ({ page }) => {
  if (!ownUrl(page.url())) return; // third-party pages are not ours to grade
  expect(page.__errors, 'zero console errors on our pages').toEqual([]);
  const cls = await page.evaluate(() => window.__cls);
  test.info().annotations.push({ type: 'cls', description: `${page.url()} → ${cls.toFixed(4)}` });
  expect(cls, 'cumulative layout shift').toBeLessThan(0.1);
});

test('land: a stranger sees the main heading within 10 seconds', async ({ page }) => {
  const started = Date.now();
  const res = await page.goto('/');
  expect(res.status()).toBe(200);

  const heading = page.getByRole('heading', { level: 1 }).first();
  await expect(heading).toBeVisible();
  await expect(heading).not.toBeEmpty();

  // The landing page hands the stranger to the product it sells.
  await expect(page.locator('a[href="/x-autopilot/"]').first()).toBeVisible();

  expect(Date.now() - started, 'time to the main heading (ms)').toBeLessThan(10_000);

  // Imprint company on the landing page — the same string the LIVE checklist
  // looks for.
  await expect(page.locator('body')).toContainText(env.imprintCompany);
});

test('buy: the X Autopilot checkout entry point exists (never followed)', async ({ page }) => {
  await page.goto('/x-autopilot/');
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();

  // The tier whose Price id is set became a real link to the server-side
  // checkout route; the tiers without one stay disabled and say which
  // variable is missing — never a broken link.
  const start = page.locator('#startBtn149');
  await expect(start).toBeVisible();
  await expect(start).toHaveAttribute('href', '/x-autopilot/checkout/149');
  for (const tier of ['330', '990']) {
    const btn = page.locator(`#startBtn${tier}`);
    await expect(btn).toBeDisabled();
    await expect(btn).toHaveAttribute('data-missing-env', `PRICE_ID_XA_${tier}`);
  }
  // Not clicked: following the link would call Stripe, and the e2e never pays.
});

test('ops: /healthz answers 200 with ok:true and the app name', async ({ request }) => {
  const res = await request.get('/healthz');
  expect(res.status()).toBe(200);
  expect(await res.json()).toEqual({ ok: true, app: env.appName });
});

test('legal: the imprint page names the company', async ({ page }) => {
  const res = await page.goto('/impressum/');
  expect(res.status()).toBe(200);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Impressum');
  await expect(page.locator('body')).toContainText(env.imprintCompany);
});
