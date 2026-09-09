# LIESNICHT CH / DE / AT — 09 Sep 2026 country amendment

Country split is implemented and locally verified: `npm test && npm run validate` passes, including 220 country assertions and existing tenant/Polish regressions. See docs/LIESNICHT_COUNTRIES.md for the cause, exact behavior, publisher pools, production evidence and outstanding Austria CNAME. Preserve other Cxx handovers and checkboxes. Do not treat this source patch as commercial LIVE or proof of Stripe payment. Bus sync was blocked by automatic approval review.

---

# HANDOVER — what runs where, how a stranger buys, how to refund

One page per venture in this repository. Every value below is an environment
variable name or a public URL; no secret appears here. Where a step needs a
human (Stripe dashboard, Google consent, DNS), it says so.

## Common to every product

| Item | Where |
| --- | --- |
| Code | `martinszreter/automation_app`, branch `main`; every PR runs `ci.yml` (ruff + pytest with Postgres, Node tests + validator, Playwright e2e) |
| Liveness / readiness | `GET /healthz` (process only), `GET /health` (database answers) — FastAPI app; nieczytaj/liesnicht: `GET /health` (feeds, hot count, prices, tenant) |
| Error alerts | Unhandled exceptions in the FastAPI app are POSTed to `ERROR_ALERT_WEBHOOK_URL` = the n8n *Engine Error Alerts* webhook (`N6gYXlzZUn6OXOs4`), which classifies, dedups for 24h and mails info@startend.ch |
| Outbound mail | Only through the n8n *HQ Mail Lane* (`dZxIRfBaU89PFpYU`), URL in `HQ_MAIL_WEBHOOK_URL`. The app never picks a recipient from a public form |
| Legal | Imprint STARTEND GmbH, CHE-223.488.613, Bahnhofstrasse 7, 6330 Cham on every public page; `/impressum/` (FastAPI), `/impressum` + `/datenschutz` (liesnicht), `/regulamin` (nieczytaj) |
| Analytics | Cookie-free page-view beacon only (`page_views` data table via the *Page PV* workflow) |
| Stripe | One live account (STARTEND GMBH). The shared **CHF 1 smoke-test Payment Link** (`plink_1UAZsUK9ZAF4KiDu3dyOi4yM`, hosted confirmation says "TEST OK — refund") is on every sales page; refund it in the Stripe dashboard afterwards. Live prices are Stripe Prices referenced by env var, never hard-coded |

## X Autopilot (`/x-autopilot`) — FastAPI app

**What a stranger does:** lands on `/x-autopilot/` → picks a tier (CHF 149 / 330 / 990 per month, buttons only live when `PRICE_ID_XA_149/330/990` are set) → Stripe Checkout → back to `/x-autopilot/panel/login` → Google Sign-In → the plan attaches to the Google e-mail → `/x-autopilot/panel` (German) shows plan, next invoice, the 7-day calendar of scheduled posts, published posts with impressions/likes, pause/resume, Sheets status.

**Refund:** a CHF 1 plan shows a "CHF 1 Testzahlung erstatten" button in the panel (`POST /x-autopilot/panel/refund`, Stripe refund + plan → REFUNDED). Anything larger: Stripe dashboard → refund the PaymentIntent; the `charge.refunded`/`customer.subscription.deleted` webhooks update the plan.

**Where the posts come from:** the n8n engines (*Two Agents — Reactive/Structured Engine*, *Daily Recap*, *Longform*, *Reply*, *Comment Responder*, *Metrics Loop*) read the `agents` data table and write `post_log` / `post_metrics`. This app only judges and displays.

| Variable | Purpose |
| --- | --- |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Stripe API + `POST /stripe/webhook` signature |
| `PRICE_ID_XA_149/330/990`, `STRIPE_XA_TIER_MODE` | Tier Prices (subscription mode) |
| `N8N_XAUTOPILOT_ORDER_URL` | Order rows → `xautopilot_orders` (n8n) |
| `GOOGLE_OAUTH_CLIENT_ID/SECRET` | Google Sign-In; redirect URI `{PUBLIC_BASE_URL}/x-autopilot/auth/google/callback` |
| `GOOGLE_SHEETS_REFRESH_TOKEN`, `GOOGLE_SHEETS_SPREADSHEET_ID`, `GOOGLE_SHEETS_RANGE`, `GOOGLE_SHEETS_RECONNECT_KEY` | Env-only Sheets access; when the token dies the panel e-mails Marcin the reconnect link (`/x-autopilot/sheets/reconnect?key=…`, human clicks Google consent, pastes the new token into Railway) |
| `XAUTOPILOT_JUDGE_KEY` | Header `X-Judge-Key` for `POST /x-autopilot/judge`, `/compose`, `/digest/run` |
| `N8N_XA_VETO_LOG_URL` | Optional: every veto also lands in n8n |
| `ANTHROPIC_API_KEY`, `XAUTOPILOT_GENERATE_MODEL` | Optional: `/compose` drafts 3 variants itself (Opus 5); unset → engines keep drafting in n8n |
| `N8N_XA_PANEL_URL` | *XA Panel Lane* (`5YjrQoXSBlzeFmOw`) — `https://startend.app.n8n.cloud/webhook/xa-panel-7h3k9q2w`: `profile`, `recent_posts`, `set_status` |
| `HQ_MAIL_WEBHOOK_URL` | Weekly digest + reconnect mails |
| `XA_E2E_KEY` | **CI only.** Enables `/x-autopilot/e2e/login`; never set in production |

**Weekly digest:** schedule in n8n — Schedule trigger (Monday 08:00 Zurich) → HTTP Request `POST {PUBLIC_BASE_URL}/x-autopilot/digest/run` with header `X-Judge-Key`. One mail per active plan to the plan's e-mail.

**Pause/resume:** panel button → `paused_at` on the plan **and** `agents.status = paused|active` through the panel lane, so the engines stop/continue.

## /apps — WhatsApp reservation setup for restaurants — FastAPI app

**What a stranger does:** `/apps/` (German, interactive WhatsApp demo on the page) → "Einrichtung starten" → Stripe Checkout with the one-time setup (`PRICE_ID_APPS_SETUP`, CHF 1'990) and the monthly subscription (`PRICE_ID_APPS_MONTHLY`, CHF 249) in one session → `/apps/success` collects restaurant name, Swiss number (E.164), opening hours → row `details` in `apps_orders` (n8n) and in the local `apps_bookings` table → "Danke". No human needed until the WhatsApp number is provisioned.

**Demo without paying:** `/apps/demo` (date, time, guests, contact) → stored in `apps_bookings` and mailed to the HQ inbox via HQ Mail → operator confirms by hand.

**Admin:** `/apps/admin` (Google Sign-In, e-mail must be in `ADMIN_EMAILS`) lists demo requests and setup details, newest first.

**Refund:** setup fee is non-refundable by the terms; the subscription is cancelled in Stripe (dashboard) → `customer.subscription.deleted` writes the `canceled` row. CHF 1 smoke tests: refund in the dashboard.

| Variable | Purpose |
| --- | --- |
| `PRICE_ID_APPS_SETUP`, `PRICE_ID_APPS_MONTHLY` | The two Stripe Prices |
| `N8N_APPS_ORDER_URL` | `apps_orders` rows (paid / details / canceled) |
| `HQ_MAIL_WEBHOOK_URL` | Demo-booking confirmation to the HQ inbox |
| `ADMIN_EMAILS` | Comma-separated Google e-mails allowed on `/apps/admin` |
| `XA_E2E_KEY` | **CI only.** Also enables `/apps/e2e/login` |

## nieczytaj.pl (PL) and liesnicht.ch (DE) — Node app `nieczytaj/`

One `server.js`, two tenants: the `Host` header selects PL or DE; `TENANT=liesnicht` pins DE (set on the liesnicht Railway service). Self-contained for Railway (own `Dockerfile`, `railway.json`; root directory `nieczytaj`).

| Service (Railway project `startend`) | Domain | Notes |
| --- | --- | --- |
| `liesnicht` (2c76978b) | `liesnicht-production.up.railway.app`, `www.liesnicht.ch`, `www.liesnicht.de` (CNAME + certificate verified) | Deploys on every push to `main` |
| `nieczytaj` (7beff2f4) | nieczytaj.pl | **Does not track this repo** — last deployed 2026-08-09 from the old `APP_SRC` env source. Repoint it to the repo (root directory `nieczytaj`) to ship `/reklama` changes |

**What an advertiser does:** `/werbung` (DE) or `/reklama` (PL) → picks a format (banner 970×170, tile 16:10, box 1:1; 7 or 30 days) → Stripe Payment Link from `STRIPE_BANER7/30`, `STRIPE_KAF7/30`, `STRIPE_BOX7/30` (per service; unset → mailto reservation) → sends the creative by mail → operator publishes (`ADS` config). Prices: PL tail block in `server.js`, DE `PRICE_DE_LOCKED`.

**Refund:** Payment Links → Stripe dashboard.

**SEO layer:** canonical + OG per tenant, `/sitemap.xml`, `/rss.xml` (alias `/feed`), `robots.txt` names the sitemap. DE copy rules: `nieczytaj/STYLE_DE.md`.

| Variable | Purpose |
| --- | --- |
| `TENANT` | `liesnicht` pins the DE tenant |
| `STRIPE_BANER7`, `STRIPE_BANER30`, `STRIPE_KAF7`, `STRIPE_KAF30`, `STRIPE_BOX7`, `STRIPE_BOX30` | Payment Links per format and run |
| `PUSH_TOKEN` | `POST /api/summaries` from the n8n summariser |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Optional self-summaries |
| `REFRESH_MIN` | Feed refresh interval |

**Local check:** `cd nieczytaj && npm test && npm run validate`.

## Known gaps (as of 2026-09-08)

- Railway has deprecated `railway.json`/`railway.toml` (hard cutoff 2026-12-01); migrate to `.railway/railway.ts`.
- The `nieczytaj` service must be repointed to the repository (see above).
- X Autopilot post generation inside this app needs `ANTHROPIC_API_KEY`; until then the engines draft in n8n and only the judge runs here.
- Google Sign-In for `/apps/admin` reuses the X Autopilot OAuth client and callback; the same redirect URI covers both.

