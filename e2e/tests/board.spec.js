// W2-P1 — the HQ board: live counter from the checklist JSON, one row per
// initiative, last-updated stamp, no external requests, loads in under 1 s.
const { test, expect } = require('@playwright/test');
const { SRV_BASE, watchConsole, layoutShift } = require('./helpers');

test.describe('board ptf-k4x9m2', () => {
  test('counter, rows and stamp render from the checklist JSON', async ({ page, request }) => {
    const errors = watchConsole(page);
    const external = [];
    page.on('request', (r) => { if (!r.url().startsWith(SRV_BASE)) external.push(r.url()); });

    const started = Date.now();
    await page.goto(`${SRV_BASE}/ptf-k4x9m2.html`, { waitUntil: 'load' });
    expect(Date.now() - started).toBeLessThan(1000);

    const checklist = await (await request.get(`${SRV_BASE}/checklist-k4x9m2.json`)).json();
    const live = checklist.initiatives.filter((i) => i.live === true).length;
    await expect(page.locator('#lb-live')).toHaveText(`${live}/${checklist.target}`);
    await expect(page.locator('#lb-updated')).toHaveText(checklist.updated);
    await expect(page.locator('li.lb-row')).toHaveCount(checklist.initiatives.length);

    // Every row carries stage / next / owner / blocker.
    const first = page.locator('li.lb-row').first();
    for (const label of ['Stage', 'Next', 'Owner', 'Blocker']) {
      await expect(first.locator(`[data-l="${label}"]`)).toHaveCount(1);
    }

    // The canon board follows the live layer, unchanged.
    await expect(page.locator('body')).toContainText('Views registry');

    expect(external).toEqual([]);
    expect(errors).toEqual([]);
    expect(await layoutShift(page)).toBe(0);
  });

  test('has no external fonts', async ({ page }) => {
    await page.goto(`${SRV_BASE}/ptf-k4x9m2.html`);
    const html = await page.content();
    expect(html).not.toMatch(/fonts\.googleapis|fonts\.gstatic/);
    expect(await page.locator('link[rel="stylesheet"]').count()).toBe(0);
  });
});
