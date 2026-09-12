import { expect, test, type Page } from '@playwright/test';

async function openDiscovery(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto('/');
  return errors;
}

test('world map follows the chosen area and keeps price/type filters', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const errors = await openDiscovery(page);
  const cards = page.locator('.property-card:visible');
  await expect(cards).toHaveCount(8);
  await expect(page.locator('#property-map')).toHaveAttribute('data-globe-ready', 'true');
  await expect(page.locator('#property-map canvas')).toHaveCount(1);
  await expect(page.locator('.leaflet-container')).toHaveCount(0);
  await page.locator('[data-market="China"]').click();
  await expect(cards).toHaveCount(0);
  await expect(page.locator('#empty-state')).toContainText('No examples in China yet.');
  await expect(page.locator('#map-area-status')).toContainText('Live listings not connected');
  await page.locator('[data-market="Thailand"]').click();
  await expect(cards).toHaveCount(0);
  await expect(page.locator('#empty-state')).toContainText('No examples in Thailand yet.');
  await page.locator('[data-market="United States"]').click();
  await expect(cards).toHaveCount(1);
  await expect(cards.first()).toContainText('Miami');

  await page.locator('#property-map').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#results-context')).toContainText('this map area');
  await expect(page.locator('[data-market="United States"]')).toHaveAttribute('aria-pressed', 'false');

  await page.locator('#map-auto-search').uncheck();
  await page.locator('#property-map').focus();
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('#search-map-area')).toBeVisible();
  await page.locator('#search-map-area').click();
  await expect(page.locator('#search-map-area')).toBeHidden();
  await expect(page.locator('#map-area-status')).toContainText('in this area');
  await page.locator('#type-filter').selectOption('Apartment');
  // The globe's visible Atlantic edge includes Lisbon and London.
  await expect(cards).toHaveCount(2);
  await expect(cards.filter({ hasText: 'Miami' })).toHaveCount(0);
  await page.locator('#reset-map').click();
  await expect(cards).toHaveCount(4);
  await expect(page.locator('#type-filter')).toHaveValue('Apartment');
  await page.locator('#budget-filter').selectOption('600000');
  await expect(cards).toHaveCount(3);
  expect(errors).toEqual([]);
});

test('mobile map and list retain the chosen area and show missing coverage honestly', async ({ page }) => {
  const errors = await openDiscovery(page);
  await page.locator('[data-market="Thailand"]').click();
  await expect(page.locator('#empty-state')).toContainText('No examples in Thailand yet.');
  await page.locator('#mobile-map-toggle').click();
  await expect(page.locator('#property-map')).toBeVisible();
  await expect(page.locator('#map-area-status')).toContainText('0 examples in Thailand');
  await page.locator('#property-map').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#map-area-status')).toContainText('in this area');
  const areaStatus = await page.locator('#map-area-status').textContent();
  await page.locator('#mobile-map-toggle').click();
  await expect(page.locator('#empty-state')).toContainText('an empty area does not mean');
  await page.locator('#mobile-map-toggle').click();
  await expect(page.locator('#map-area-status')).toHaveText(areaStatus!);
  await page.locator('#mobile-map-toggle').click();
  await page.locator('[data-market="United States"]').click();
  await page.locator('#mobile-map-toggle').click();
  await expect(page.locator('#map-area-status')).toContainText('1 example in United States');
  await expect(page.locator('.map-price-pin:visible')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('one globe rotates by dragging and themes persist into property details', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const errors = await openDiscovery(page);
  const globe = page.locator('#property-map');
  await expect(globe).toHaveAttribute('data-globe-ready', 'true');
  const before = await globe.getAttribute('data-longitude');
  const box = (await globe.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height * 0.7);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 - 140, box.y + box.height * 0.7, { steps: 12 });
  await page.mouse.up();
  await expect(globe).not.toHaveAttribute('data-longitude', before!);
  await expect(page.locator('#results-context')).toContainText('this map area');
  for (const appearance of ['dusk', 'midnight', 'ivory']) {
    await page.locator('#theme-select').selectOption(appearance);
    await expect(page.locator('html')).toHaveAttribute('data-appearance', appearance);
  }
  await page.locator('#theme-select').selectOption('midnight');
  await page.goto('/properties/lisbon-01');
  await expect(page.locator('html')).toHaveAttribute('data-appearance', 'midnight');
  await expect(page.locator('#theme-select')).toHaveValue('midnight');
  await expect(page.locator('body')).toContainText('Not an active listing');
  expect(errors).toEqual([]);
});
