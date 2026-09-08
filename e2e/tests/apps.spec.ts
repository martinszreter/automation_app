import { expect, test } from "@playwright/test";

// W2-A4 acceptance: the simulated WhatsApp thread completes on /apps, and a
// demo booking made on /apps/demo shows up in the admin list.
const KEY = process.env.XA_E2E_KEY || "e2e-key";
const ADMIN = process.env.E2E_ADMIN_EMAIL || "e2e-admin@example.com";
const RUN = process.env.GITHUB_RUN_ID || "local";

test("interactive WhatsApp demo: reserve → confirm → reminder", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(String(err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  await page.goto("/apps/");
  await expect(page.getByTestId("wa-demo")).toBeVisible();
  await page.getByTestId("demo-guests-4").click();
  await page.getByTestId("demo-when-1").click();
  await expect(page.getByTestId("demo-confirmed")).toContainText("4 Personen");
  await page.getByTestId("demo-reply-yes").click();
  await expect(page.getByTestId("demo-done")).toContainText("Bestätigt");
  await expect(page.getByTestId("demo-book")).toHaveAttribute("href", "/apps/demo");

  await expect(page.locator("footer")).toContainText("STARTEND GmbH");
  await expect(page.locator("footer")).toContainText("Impressum");
  expect(errors, "no console errors").toEqual([]);
});

test("a demo booking is visible in the admin list", async ({ page }) => {
  const restaurant = `E2E Beiz ${RUN}`;
  const day = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);

  await page.goto("/apps/demo");
  await page.fill("#restaurant_name", restaurant);
  await page.fill("#contact", "wirt@beiz.ch");
  await page.fill("#date", day);
  await page.fill("#guests", "4");
  await page.getByRole("button", { name: "Demo bestätigen" }).click();
  await expect(page.getByRole("heading", { name: "Demo gebucht." })).toBeVisible();

  // Unauthenticated admin → Google sign-in; the e2e key signs the allow-listed admin in.
  await page.goto("/apps/admin");
  await expect(page).toHaveURL(/\/apps\/admin\/login$/);
  await page.goto(`/apps/e2e/login?key=${encodeURIComponent(KEY)}&email=${encodeURIComponent(ADMIN)}`);
  await expect(page).toHaveURL(/\/apps\/admin$/);
  await expect(page.getByTestId("booking-row").filter({ hasText: restaurant })).toHaveCount(1);
});
