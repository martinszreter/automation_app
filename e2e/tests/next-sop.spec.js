// W2-P2 — NEXT and SOP: Marcin's click queue at the top, collapsible
// sections, a search box that filters what is on the page.
const { test, expect } = require('@playwright/test');
const { SRV_BASE, watchConsole } = require('./helpers');

for (const view of ['next', 'sop']) {
  test.describe(`${view}-k4x9m2`, () => {
    test('answers 200 with the click queue first', async ({ page, request }) => {
      const errors = watchConsole(page);
      const response = await request.get(`${SRV_BASE}/${view}-k4x9m2.html`);
      expect(response.status()).toBe(200);

      await page.goto(`${SRV_BASE}/${view}-k4x9m2.html`);
      const queue = page.locator('#click-queue');
      await expect(queue).toBeVisible();
      await expect(queue.locator('summary')).toContainText('Marcin');

      // The queue is the first section on the page.
      const firstSection = page.locator('details.lb-sec').first();
      await expect(firstSection).toHaveAttribute('id', 'click-queue');

      const items = queue.locator('li.lb-qi');
      expect(await items.count()).toBeGreaterThan(0);
      await expect(items.first().locator('a.lb-go')).toBeVisible();
      expect(errors).toEqual([]);
    });

    test('sections collapse and the search box filters', async ({ page }) => {
      await page.goto(`${SRV_BASE}/${view}-k4x9m2.html`);
      const sections = page.locator('details.lb-sec');
      expect(await sections.count()).toBeGreaterThan(1);

      // Collapsible: toggling the first summary closes the section.
      const first = sections.first();
      await expect(first).toHaveAttribute('open', '');
      await first.locator('summary').click();
      await expect(first).not.toHaveAttribute('open', '');
      await first.locator('summary').click();

      // Search: a term that matches a few items hides the others. Open every
      // section first so "visible" means "not filtered out".
      const search = page.locator('#lb-search');
      await expect(search).toBeVisible();
      await page.$$eval('details.lb-sec', (all) => all.forEach((d) => { d.open = true; }));
      const before = await page.locator('[data-s]:visible').count();
      await search.fill('zzzz-no-such-term');
      await expect(page.locator('#lb-search-count')).toHaveText('0');
      await search.fill('CHF 1');
      const after = await page.locator('[data-s]:visible').count();
      expect(after).toBeGreaterThan(0);
      expect(after).toBeLessThan(before);
      await search.fill('');
      expect(await page.locator('[data-s]:visible').count()).toBe(before);
    });
  });
}

test('next keeps the canon NEXT content unchanged below the live layer', async ({ page }) => {
  await page.goto(`${SRV_BASE}/next-k4x9m2.html`);
  await expect(page.locator('body')).toContainText('product-quality gate');
  expect(await page.content()).toContain('<!-- FIXTURE_NEXT_CANON -->');
});
