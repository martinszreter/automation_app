import { expect, test } from "@playwright/test";

// W2-A2 acceptance: a paid test user sees a calendar with 7 scheduled posts and can pause.
// XA_E2E_KEY lets CI sign a synthetic buyer in without Google; the route is 404 otherwise.
const KEY = process.env.XA_E2E_KEY || "e2e-key";
const EMAIL = `e2e-buyer-${process.env.GITHUB_RUN_ID || "local"}@example.com`;

test("paid user sees 7 scheduled posts and can pause / resume", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(String(err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  await page.goto(`/x-autopilot/e2e/login?key=${encodeURIComponent(KEY)}&email=${encodeURIComponent(EMAIL)}`);
  await expect(page).toHaveURL(/\/x-autopilot\/panel$/);
  await expect(page.getByTestId("plan-active")).toBeVisible();
  await expect(page.getByTestId("scheduled-post")).toHaveCount(7);

  await page.getByTestId("pause-button").click();
  await expect(page).toHaveURL(/\/x-autopilot\/panel$/);
  await expect(page.getByTestId("plan-paused")).toBeVisible();
  await expect(page.getByTestId("scheduled-post")).toHaveCount(7);
  await expect(page.locator('[data-testid="scheduled-post"][data-status="paused"]')).toHaveCount(7);

  await page.getByTestId("resume-button").click();
  await expect(page.getByTestId("plan-active")).toBeVisible();

  // Legal + language bar on the panel itself.
  await expect(page.locator("footer")).toContainText("STARTEND GmbH");
  await expect(page.locator("footer")).toContainText("Impressum");
  expect(errors, "no console errors").toEqual([]);
});

test("unauthenticated panel goes to Google sign-in", async ({ page }) => {
  await page.goto("/x-autopilot/panel");
  await expect(page).toHaveURL(/\/x-autopilot\/panel\/login$/);
});
