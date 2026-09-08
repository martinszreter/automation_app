'use strict';

const { defineConfig, devices } = require('@playwright/test');
const env = require('./e2e/env.js');

module.exports = defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.js',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: env.baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // Local runs on a machine that cannot download browsers can point this at
    // an existing Chromium; CI installs its own and leaves it unset.
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
  },
  // A stranger arrives on a phone: mobile viewport is the default project.
  projects: [{ name: 'mobile-chromium', use: { ...devices['Pixel 7'] } }],
  // Boots the FastAPI app with dummy env only — no Postgres, no Stripe key.
  // No `alembic upgrade head` here: migrations need a database, the journey
  // does not.
  webServer: env.local
    ? {
        command: `${env.python} -m uvicorn app.main:app --host 127.0.0.1 --port ${env.port}`,
        url: `${env.baseURL}/healthz`,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
        env: { ...process.env, ...env.serverEnv },
      }
    : undefined,
});
