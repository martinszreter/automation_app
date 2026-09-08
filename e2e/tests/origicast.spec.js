// W2-P3 — ORIGICAST: 21+ gate -> door -> CHF 1 test paid (Stripe stand-in
// in CI, so no key is needed), Season/Hour/Keep hidden while ORIGICAST_LIVE
// is off, imprint on every page, zero console errors, no layout shift.
const { test, expect } = require('@playwright/test');
const { APP_BASE, watchConsole, layoutShift } = require('./helpers');

const LEGAL = ['/impressum/', '/agb/', '/datenschutz/'];

async function expectLegalFooter(page) {
  await expect(page.locator('footer')).toContainText('STARTEND GmbH');
  for (const href of LEGAL) await expect(page.locator(`footer a[href="${href}"]`)).toHaveCount(1);
}

test.describe('origicast door', () => {
  test('stranger: gate -> door -> CHF 1 test paid', async ({ page }) => {
    const errors = watchConsole(page);

    // 1. Land on the gate. Under 10 s to understand: one question, two buttons.
    await page.goto(`${APP_BASE}/origicast/`);
    await expect(page.locator('h1')).toContainText('21');
    await expect(page.locator('#gate-yes')).toBeVisible();
    await expectLegalFooter(page);
    expect(await layoutShift(page)).toBe(0);

    // 2. Door and checkout are locked before the answer.
    const locked = await page.request.get(`${APP_BASE}/origicast/door`, { maxRedirects: 0 });
    expect(locked.status()).toBe(303);

    // 3. Confirm 21+.
    await page.locator('#gate-yes').click();
    await expect(page).toHaveURL(/\/origicast\/door$/);
    await expect(page.locator('#pay-test')).toBeVisible();
    await expect(page.locator('#test')).toContainText('CHF 1');
    await expectLegalFooter(page);

    // Season / Hour / Keep stay hidden behind ORIGICAST_LIVE.
    for (const id of ['offer-season', 'offer-hour', 'offer-keep']) {
      await expect(page.locator(`#${id}`)).toHaveCount(0);
    }
    expect(await page.content()).not.toMatch(/fonts\.googleapis|fonts\.gstatic/);

    // 4. Pay the CHF 1 test on the Stripe stand-in.
    await page.locator('#pay-test').click();
    await expect(page.locator('#pay')).toBeVisible();
    await expect(page.locator('body')).toContainText('1.00 CHF');
    await page.locator('#pay').click();

    // 5. Back on the success page with the reference.
    await expect(page).toHaveURL(/\/origicast\/success\?session_id=cs_test_stub_\d+/);
    await expect(page.locator('#reference')).toContainText('cs_test_stub_');
    await expectLegalFooter(page);

    expect(errors).toEqual([]);
  });

  test('under 21 is sent away and stays locked out', async ({ page }) => {
    await page.goto(`${APP_BASE}/origicast/`);
    await page.locator('#gate-no').click();
    await expect(page).toHaveURL(/\/origicast\/leave$/);
    await expect(page.locator('h1')).toContainText('Kein Zugang');
    await page.goto(`${APP_BASE}/origicast/door`);
    await expect(page).toHaveURL(/\/origicast\/$/);
  });

  test('legal pages answer and /healthz is green', async ({ request }) => {
    for (const path of LEGAL) expect((await request.get(`${APP_BASE}${path}`)).status()).toBe(200);
    const health = await request.get(`${APP_BASE}/healthz`);
    expect(health.status()).toBe(200);
    expect(await health.json()).toEqual({ status: 'ok' });
  });
});
