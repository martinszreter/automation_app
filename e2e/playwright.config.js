// Playwright config for the stranger e2e suite.
//
// Two origins are exercised:
//   SRV_BASE  the static HQ views (/srv served by python -m http.server)
//   APP_BASE  the FastAPI app (uvicorn app.main:app)
// Both default to the ports .github/workflows/quality.yml starts them on.
// @ts-check
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.APP_BASE || 'http://127.0.0.1:8000',
    trace: 'retain-on-failure',
    ...(process.env.CHROMIUM_PATH ? { launchOptions: { executablePath: process.env.CHROMIUM_PATH } } : {}),
  },
  projects: [
    // Mobile first: the quality bar is judged on a phone.
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
  ],
});
