'use strict';

// Shared by playwright.config.js (which boots uvicorn) and the specs (which
// decide what to expect). Everything here is a harmless dummy: the suite runs
// on a bare checkout with no Postgres, no Stripe key and no OAuth client, and
// never pays. A deployed instance can be tested in place with E2E_BASE_URL.

const port = Number(process.env.E2E_PORT || 4951);

module.exports = {
  baseURL: process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`,
  local: !process.env.E2E_BASE_URL,
  port,
  // FastAPI(title=...) in app/main.py — what /healthz reports as "app".
  appName: 'STARTEND',
  imprintCompany: process.env.LEGAL_COMPANY || 'STARTEND GmbH',
  // The interpreter that has requirements.txt installed. CI's setup-python
  // provides `python3`; a local run points this at its venv.
  python: process.env.E2E_PYTHON || 'python3',
  // Env for the app under test. The database URL points at a closed port on
  // purpose: the engine is created lazily, so only the DB-backed routes
  // (/health, /contact) would ever try to connect, and none of them is part
  // of the stranger journey. PRICE_ID_XA_149 is a dummy Price id so the
  // CHF 149 tier renders its checkout link (the entry point the journey
  // asserts on) — the link is never followed.
  serverEnv: {
    DATABASE_URL: 'postgresql+asyncpg://e2e:e2e@127.0.0.1:1/e2e',
    SESSION_SECRET: 'e2e-only-session-secret',
    SESSION_HTTPS_ONLY: 'false',
    WHATSAPP_ADAPTER: 'mock',
    PRICE_ID_XA_149: 'price_e2e_dummy_149',
    PRICE_ID_XA_330: '',
    PRICE_ID_XA_990: '',
    STRIPE_SECRET_KEY: '',
    STRIPE_WEBHOOK_SECRET: '',
    PUBLIC_BASE_URL: `http://127.0.0.1:${port}`,
  },
};
