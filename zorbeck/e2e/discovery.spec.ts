import { expect, test, type Page } from '@playwright/test';

async function openDiscovery(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(String(error)));
  // The interaction test uses local Leaflet and does not depend on a tile provider.
  await page.route('https://tile.openstreetmap.org/**', route => route.fulfill({
    contentType: 'image/png',
    body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64'),
  }));
  await page.goto('/');
  return errors;
}

test('world map follows the chosen area and keeps price/type filters', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const errors = await openDiscovery(page);
  const cards = page.locator('.property-card:visible');
  await expect(cards).toHaveCount(8);
  await expect(page.locator('#property-map')).toHaveClass(/leaflet-container/);
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
  await expect(cards).toHaveCount(0);
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
  await expect(page.locator('.map-price-pin')).toHaveCount(1);
  expect(errors).toEqual([]);
});
