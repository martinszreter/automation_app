import { expect, test, type Page } from '@playwright/test';

// The stranger test: someone who has never heard of Zorbeck lands on the page,
// understands the offer within ten seconds, pays CHF 1 (test), gets the first
// value and receives an e-mail — all without a human. Stripe, the mail lane and
// the alert handler are the in-process stub (see stub.env / zorbeck_app/stub.py).

const LEGAL_PATHS = ['/impressum', '/agb', '/datenschutz'];
const IMPRINT = ['STARTEND GmbH', 'CHE-223.488.613', 'Bahnhofstrasse 7', '6330 Cham'];

function watchConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(String(error)));
  return errors;
}

async function expectTimeline(page: Page, city: string): Promise<void> {
  const timeline = page.getByTestId('timeline');
  await expect(timeline).toBeVisible();
  expect(await timeline.locator('li').count()).toBe(4);
  await expect(timeline).toContainText('Sofort');
  await expect(timeline).toContainText('Innerhalb von 24 Stunden');
  await expect(timeline).toContainText('30 Tage lang');
  await expect(timeline).toContainText(city);
}

async function expectImprint(page: Page): Promise<void> {
  const footer = page.locator('footer');
  for (const fragment of IMPRINT) await expect(footer).toContainText(fragment);
  for (const path of LEGAL_PATHS) await expect(footer.locator(`a[href="${path}"]`)).toBeVisible();
}

test.beforeEach(async ({ request }) => {
  await request.post('/_stub/reset');
});

test('stranger: land → understand the offer in 10 s → pay CHF 1 → first value → e-mail received', async ({
  page,
  request,
}) => {
  const errors = watchConsole(page);
  const started = Date.now();

  await page.goto('/');

  // Understand the offer: one headline, one price, one call to action — all above the fold on a phone.
  const headline = page.getByRole('heading', { level: 1 });
  await expect(headline).toBeVisible();
  await expect(headline).toContainText('Inserate');
  const cta = page.getByTestId('cta');
  await expect(cta).toBeVisible();
  await expect(cta).toContainText('CHF 1');
  expect(await page.getByRole('button').count()).toBe(1);
  expect(await page.getByTestId('offer').count()).toBe(1);
  await expect(page.getByTestId('price')).toContainText('CHF 1');
  await expect(page.getByTestId('price')).toContainText('einmalig');
  expect(await page.getByTestId('includes').locator('li').count()).toBe(3);
  expect(Date.now() - started).toBeLessThan(10_000);

  // Five questions, five answers, further down.
  const faq = page.getByTestId('faq');
  expect(await faq.locator('dt').count()).toBe(5);
  expect(await faq.locator('dd').count()).toBe(5);
  await expect(faq).toContainText('Was kostet es');
  await expect(faq).toContainText('CHF 1');
  await expectImprint(page);

  // Intake.
  const email = `stranger+${Date.now()}@example.ch`;
  await page.fill('#email', email);
  await page.fill('#city', 'Zug');
  await page.fill('#budget_max', "1'200'000");
  await cta.click();

  // CTA → CHF 1 test paid: the Checkout Session carries exactly the price shown.
  await expect(page).toHaveURL(/\/_stub\/checkout\//);
  await expect(page.getByTestId('stub-amount')).toContainText('CHF 1');
  await expect(page.getByTestId('stub-email')).toHaveText(email);
  const paidAt = Date.now();
  await page.getByTestId('stub-pay').click();

  // First value: the paid intake is confirmed on the success page, with the
  // timeline of what happens next — no human anywhere in it.
  await expect(page).toHaveURL(/\/danke\?session_id=cs_test_stub_/);
  await expect(page.getByTestId('success-title')).toBeVisible();
  await expect(page.getByTestId('success-email')).toHaveText(email);
  await expect(page.getByTestId('intake-city')).toHaveText('Zug');
  await expect(page.getByTestId('intake-budget')).toContainText("1'200'000");
  await expect(page.getByTestId('intake-amount')).toHaveText('CHF 1');
  await expectTimeline(page, 'Zug');
  await expectImprint(page);

  // E-mail received: the webhook (signed, verified) mailed the confirmation.
  const deliveries = await (await request.get('/_stub/webhooks')).json();
  expect(deliveries).toHaveLength(1);
  expect(deliveries[0].status).toBe(200);
  const sessionId = new URL(page.url()).searchParams.get('session_id')!;
  const session = await (await request.get(`/_stub/v1/checkout/sessions/${sessionId}`)).json();
  expect(session.payment_status).toBe('paid');
  expect(session.amount_total).toBe(100);
  expect(session.currency).toBe('chf');

  await expect
    .poll(async () => (await (await request.get('/_stub/mail/outbox')).json()).length, { timeout: 20_000 })
    .toBeGreaterThan(0);
  const outbox: Array<{ to: string; subject: string; body: string }> = await (
    await request.get('/_stub/mail/outbox')
  ).json();
  const mail = outbox.find((m) => m.to === email);
  expect(mail).toBeTruthy();
  expect(mail!.subject).toContain('Zug');
  expect(mail!.body).toContain('CHF 1');
  expect(mail!.body).toContain("bis CHF 1'200'000");
  expect(mail!.body).toContain('Was jetzt passiert');
  expect(mail!.body).toContain('Innerhalb von 24 Stunden');
  expect(mail!.body).not.toContain('ß');
  // Within 2 minutes of paying — in practice within seconds.
  expect(Date.now() - paidAt).toBeLessThan(120_000);
  expect(outbox).toHaveLength(1);

  // The lead reached the sink twice: checkout started, then paid.
  const leads: Array<{ status: string; email: string }> = await (await request.get('/_stub/leads')).json();
  expect(leads.map((l) => l.status)).toEqual(['checkout_started', 'paid']);

  expect(errors).toEqual([]);
});

test('first value within 2 minutes even when Stripe delivers the webhook late — and never twice', async ({
  page,
  request,
}) => {
  const errors = watchConsole(page);
  // Stripe's webhook is asynchronous; simulate it arriving after the buyer
  // already reached the success page.
  await request.post('/_stub/config', { data: { deliver_webhook: false } });

  const email = `late+${Date.now()}@example.ch`;
  await page.goto('/');
  await page.fill('#email', email);
  await page.fill('#city', 'Basel');
  await page.getByTestId('cta').click();
  await expect(page).toHaveURL(/\/_stub\/checkout\//);
  const paidAt = Date.now();
  await page.getByTestId('stub-pay').click();

  // No webhook so far …
  expect(await (await request.get('/_stub/webhooks')).json()).toEqual([]);
  // … yet the buyer has the first value on the page and in the inbox.
  await expect(page).toHaveURL(/\/danke\?session_id=/);
  await expect(page.getByTestId('success-title')).toBeVisible();
  await expect(page.getByTestId('mail-note')).toHaveAttribute('data-outcome', 'mailed');
  await expectTimeline(page, 'Basel');
  const outbox = await (await request.get('/_stub/mail/outbox')).json();
  expect(outbox).toHaveLength(1);
  expect(outbox[0].to).toBe(email);
  expect(Date.now() - paidAt).toBeLessThan(120_000);

  // A reload does not mail again.
  await page.reload();
  await expect(page.getByTestId('mail-note')).toHaveAttribute('data-outcome', 'already');

  // The late webhook arrives: accepted, but no second mail.
  const sessionId = new URL(page.url()).searchParams.get('session_id')!;
  const delivery = await (await request.post(`/_stub/checkout/${sessionId}/deliver-webhook`)).json();
  expect(delivery.status).toBe(200);
  expect(await (await request.get('/_stub/mail/outbox')).json()).toHaveLength(1);
  // The Checkout Session carries the flag, so even another instance would not mail.
  const session = await (await request.get(`/_stub/v1/checkout/sessions/${sessionId}`)).json();
  expect(session.metadata.confirmation_sent).toContain('danke');
  expect(errors).toEqual([]);
});

test('a typo is answered in German and nothing is charged', async ({ page, request }) => {
  const errors = watchConsole(page);
  await page.goto('/');
  await page.fill('#email', 'kein-mail');
  await page.fill('#city', 'Zug');
  await page.getByTestId('cta').click();
  await expect(page.getByTestId('form-error')).toContainText('E-Mail-Adresse');
  await expect(page.locator('#city')).toHaveValue('Zug');
  expect(await (await request.get('/_stub/leads')).json()).toEqual([]);
  expect(errors).toEqual([]);
});

for (const path of LEGAL_PATHS) {
  test(`${path} carries the imprint and renders without console errors`, async ({ page }) => {
    const errors = watchConsole(page);
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expectImprint(page);
    expect(errors).toEqual([]);
  });
}

test('/healthz answers and shows the stub is on (CI only)', async ({ request }) => {
  const response = await request.get('/healthz');
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.ok).toBe(true);
  expect(body.service).toBe('zorbeck');
  expect(body.stub).toBe(true);
});

test('a server error reaches the alert handler and the visitor gets a German page', async ({ page, request }) => {
  const response = await page.goto('/_stub/boom');
  expect(response?.status()).toBe(500);
  await expect(page.locator('main')).toContainText('schiefgelaufen');
  await expectImprint(page);
  const alerts: Array<{ app: string; node: string; message: string }> = await (
    await request.get('/_stub/alerts')
  ).json();
  expect(alerts).toHaveLength(1);
  expect(alerts[0].app).toBe('zorbeck');
  expect(alerts[0].node).toBe('/_stub/boom');
  expect(alerts[0].message).toContain('deliberate failure');
});
