import { defineConfig, devices } from "@playwright/test";

// The app under test is started by CI (uvicorn on :8000, migrations applied).
// Locally: uvicorn app.main:app --port 8000, then `E2E_BASE_URL=... npm test`.
export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:8000",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
