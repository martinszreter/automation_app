import { defineConfig, devices } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

// One source of truth for the stub environment: stub.env (also loaded by CI).
function stubEnv(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of readFileSync(resolve(here, 'stub.env'), 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const idx = trimmed.indexOf('=');
    out[trimmed.slice(0, idx)] = trimmed.slice(idx + 1);
  }
  return out;
}

const env = stubEnv();
const baseURL = process.env.ZORBECK_BASE_URL || env.PUBLIC_BASE_URL;
const python = process.env.ZORBECK_PYTHON || 'python';

export default defineConfig({
  testDir: '.',
  testMatch: /.*\.spec\.ts/,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'de-CH',
  },
  projects: [
    // A stranger on a phone: the offer has to work at mobile size first.
    { name: 'mobile-chromium', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: `${python} -m uvicorn app:app --host 127.0.0.1 --port 8765`,
    cwd: resolve(here, '..'),
    url: `${baseURL}/healthz`,
    reuseExistingServer: true,
    timeout: 60_000,
    env: { ...process.env, ...env },
  },
});
