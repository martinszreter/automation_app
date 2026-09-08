# STARTEND

Multi-tenant WhatsApp booking and no-show prevention for restaurants.

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Start services
docker compose up --build

# 3. Run migrations (in a second terminal)
docker compose exec app alembic upgrade head

# 4. Verify
curl http://localhost:8000/health
# → {"status": "healthy"}
```

## Development

```bash
# Run tests
docker compose exec app pytest -v

# Create a new migration after changing models
docker compose exec app alembic revision --autogenerate -m "describe change"
```

## Architecture

- **FastAPI** backend with async PostgreSQL via SQLAlchemy
- **WhatsApp integration** via swappable adapter (mock adapter for development, Meta Cloud API for production)
- **Server-rendered dashboard** with Jinja2 + HTMX (coming soon)
- All guest-facing messages are **German-first** via a template layer

## X Autopilot checkout

`/x-autopilot/` sells three tiers. Each one is a Stripe Price created in the
dashboard and handed to the app through the environment:

| Tier | Variable | Button target |
| --- | --- | --- |
| CHF 149 / month | `PRICE_ID_XA_149` | `/x-autopilot/checkout/149` |
| CHF 330 / month | `PRICE_ID_XA_330` | `/x-autopilot/checkout/330` |
| CHF 990 / month | `PRICE_ID_XA_990` | `/x-autopilot/checkout/990` |

The landing page ships every button **disabled**, carrying
`data-missing-env="PRICE_ID_XA_…"`. The server turns a button into a link only
for the tiers whose Price id is set, so an unset tier can never render a broken
checkout link. After payment Stripe returns the buyer to
`/x-autopilot/success?session_id=…`, which confirms the order and links to the X
authorization step (`X_OAUTH_ONBOARDING_URL`, falling back to
`/x-autopilot/onboarding.html`).

`checkout.session.completed` on `/x-autopilot/stripe/webhook` writes one
`xautopilot_orders` row to the n8n webhook in `N8N_XAUTOPILOT_ORDER_URL`. If that
write fails the endpoint answers `503` so Stripe retries; if the variable is
unset the order is only logged, and the plan row in Postgres is still written.

## X Autopilot post quality judge

The n8n engines (Two Agents — Reactive/Structured, Recap, Longform) draft the
posts; before posting they call this app, which vetoes **hard fails only** and
names the best variant. Both endpoints need the shared header
`X-Judge-Key: $XAUTOPILOT_JUDGE_KEY`.

| Endpoint | Body | Answer |
| --- | --- | --- |
| `POST /x-autopilot/judge` | `{profile, candidates[], recent_posts[]}` | `{best, reports[], vetoes_recorded}` |
| `POST /x-autopilot/compose` | `{profile, brief, recent_posts[], variants}` | same, after Claude drafted `variants` posts (needs `ANTHROPIC_API_KEY`) |

`profile` is the customer's tone profile — `{customer, language, banned_terms[],
topics[], voice, max_hashtags}` — built by the engine from the `agents` row and
the onboarding answers. `recent_posts` are `{text, posted_at}` from `post_log`.

Veto codes: `too_long` (X count: a link is 23, emoji 2), `spam` (hashtag /
mention / link floods, shouting, `!!!`, emoji floods, follow-me / link-in-bio /
giveaway phrases), `banned_claim` (guarantees, comparisons against competitors,
cures, get-rich promises, the customer's own terms), `wrong_language`,
`duplicate` (same as a post from the last 30 days). Every veto is one
`xa_judge_veto {...}` JSON log line and, with `N8N_XA_VETO_LOG_URL` set, a row
posted to that webhook. Among the survivors the pick is a soft score (length
near 200, a concrete number, structure, few hashtags) — never a veto.

## X Autopilot panel

`/x-autopilot/panel` (Google Sign-In, German) shows the paid customer their
plan, the **calendar of the next 7 days' scheduled posts**, the published posts
with impressions / likes, the **next Stripe invoice**, and a **pause / resume**
switch. The posts themselves live in n8n; the panel reads them through the
panel lane — the n8n workflow *XA Panel Lane* — whose webhook URL is env-only:

| Variable | Purpose |
| --- | --- |
| `N8N_XA_PANEL_URL` | Panel lane webhook. Actions: `profile` (agents row by customer email, credential columns never returned), `recent_posts` (post_log + post_metrics), `set_status` (pause/resume the agent) |
| `XA_E2E_KEY` | CI only: `/x-autopilot/e2e/login?key=…&email=…` signs a synthetic paid buyer in so Playwright can drive the panel. Unset in production — the route is then 404 |

Without the lane the panel still renders: the calendar falls back to one post
a day at 09:00 Zurich, metrics show "not reachable", the plan keeps running.
Pause writes `paused_at` on the plan **and** sets the agent's `status` to
`paused` through the lane, so the engines stop; resume reverses both.

**Weekly digest:** `POST /x-autopilot/digest/run` (header `X-Judge-Key`) mails
every active plan its week — posts, impressions, likes, what is scheduled —
through HQ Mail to the plan's e-mail. Schedule it from n8n (Schedule trigger →
HTTP Request, e.g. Monday 08:00 Zurich); it is idempotent per run.

**Stranger e2e (CI):** `e2e/` holds the Playwright checks; the `e2e` job applies
migrations, starts uvicorn and runs them on every push and PR.

## Stripe webhook

One endpoint serves both ventures: **`POST /stripe/webhook`**, signature-verified
with `STRIPE_WEBHOOK_SECRET`. It dispatches `checkout.session.completed` and
`customer.subscription.deleted` to the venture the event belongs to, decided by

1. the line item Price ids — `PRICE_ID_XA_*` → x-autopilot, `PRICE_ID_APPS_*` →
   apps, so a new tier routes itself the day its Price id reaches the
   environment; then
2. `metadata.venture` (or the older `metadata.product`), for events whose line
   items Stripe did not expand.

An event that matches neither is acknowledged with `200` and stored nowhere —
guessing would write an order row into the wrong table. A request without a
valid signature is `400`.

The older `/apps/stripe/webhook` and `/x-autopilot/stripe/webhook` still work and
call the same handlers, so an endpoint already configured against either URL
keeps behaving as before.

## Agent bus

`bus/` holds the STARTEND Agent Bus V0: one endpoint, one table, six message
types, shared by Claude Code, Cursor/GPT and Grok. It runs inside the existing
n8n agent-report intake rather than as a second reporting path, and a write is
refused with `428` unless the caller read bus state in the last ten minutes.
Contract and node-by-node sources: [`bus/README.md`](bus/README.md). Live view:
`/bus-k4x9m2.html`.

## Portfolio boot scripts

The Railway `portfolio` service is a bare `python:3.12-alpine` image whose start
command writes each internal view into `/srv` and then serves the directory. The
boot scripts used to exist **only** as environment variables (`BOOT_PY`,
`SALES_BOOT_PY`, `TRADEOPS_BOOT_PY`, `NHT_BOOT_PY`, `VIEWS_BOOT_PY`), so they
could not be reviewed, diffed or rolled back.

`boot/views_boot.py` ends that for the views script (`boot5`). **Railway reads it
from this repository**, over raw.githubusercontent.com, on every boot:

```sh
if python3 -c "import urllib.request as u;open(\"/boot5.py\",\"wb\").write(
     u.urlopen(\"https://raw.githubusercontent.com/martinszreter/automation_app/main/boot/views_boot.py\").read())" \
   && python3 /boot5.py
then echo "boot5 source=repo"
else echo "boot5 source=env-fallback"; printf "%s" "$VIEWS_BOOT_PY" > /boot5f.py; python3 /boot5f.py || true
fi
```

(The deployed start command has it on one line; `BOOT5_SOURCE` on the service
records where boot5 is meant to come from.)

`VIEWS_BOOT_PY` is kept only as that fallback: if the fetch fails, or this file
exits non-zero, the previous script still writes the canon-backed views. Delete
it once a few deploys have run green.

The script writes two kinds of view and logs one `boot5 ok <KEY> <FILE> <BYTES>`
line each:

* **canon-backed** — `STRAT_HTML`, `X_OPS_HTML`, `GROKYWOOD_OPS_HTML`,
  `MOBILE_OPS_HTML`. Read over the canon RW webhook, highest `version` wins.
* **repo-backed** — `BUS_HTML` → `boot/pages/bus-k4x9m2.html`. Static shells that
  fetch their own data client-side, so they belong in git.

Required variables on the service (no endpoint URL is hard-coded — the canon
webhook accepts unauthenticated writes and this repo is public):

| Variable | Purpose |
| --- | --- |
| `CANON_RW_URL` | Canon RW webhook, used to read the canon-backed views |
| `BUS_STATE_URL` | Bus read-state URL, substituted into the bus page at boot |
| `SRV_DIR` | Optional, defaults to `/srv` |
| `REPO_RAW_BASE` | Optional, raw base for `boot/` when pages are not on disk |

Adding a view is a pull request: append to `CANON_VIEWS` or `REPO_VIEWS` in
`boot/views_boot.py`, and for a repo-backed view drop the page in `boot/pages/`.

## HANDOVER

What a stranger needs to run, sell and refund the product without asking
anyone. Env var **names** only — values live exclusively in Railway service
variables (see `.env.example` for the full list and meaning).

### What it is

STARTEND GmbH's product app: one FastAPI service (`app/`, Python 3.12,
PostgreSQL via SQLAlchemy + Alembic) that serves the public site and sells two
things by card through Stripe Checkout:

- **X Autopilot** (`/x-autopilot/`) — autonomous posting on X, three monthly
  subscription tiers: CHF 149 / 330 / 990 (one Stripe Price each, see
  [X Autopilot checkout](#x-autopilot-checkout)).
- **WhatsApp reservation setup** (`/apps/`) — CHF 1990 one-time setup plus
  CHF 249 / month, one Checkout Session carrying both prices.

Underneath sits the multi-tenant WhatsApp booking and no-show prevention
engine (Meta Cloud API behind a swappable adapter, `mock` in development).
Stripe is the source of truth for who paid; Postgres keeps the plan rows and
contact requests; the n8n data tables (`xautopilot_orders`, `apps_orders`)
mirror every order.

### URLs

| What | URL |
|---|---|
| Public site | `https://www.zorbeck.com` |
| Railway service | `https://automationapp-production.up.railway.app` |
| Liveness (ops bar, live checklist) | `/healthz` → `{"ok":true,"app":"STARTEND"}` — no database call |
| Health (Railway healthcheck, DB-backed) | `/health` → `{"status":"healthy"}` |
| Legal | `/impressum/` |
| X Autopilot | `/x-autopilot/` → `/x-autopilot/checkout/{149,330,990}` → `/x-autopilot/success` |
| X Autopilot customer panel | `/x-autopilot/panel` (Google sign-in via `/x-autopilot/auth/google`) |
| WhatsApp setup | `/apps/` → `/apps/checkout` → `/apps/success` |
| Stripe webhook (the one endpoint Stripe is configured against) | `POST /stripe/webhook` |
| Agent bus live view | `/bus-k4x9m2.html` |
| Repo | `https://github.com/martinszreter/automation_app` — push to `main` deploys on Railway |

### Env vars

Railway → service → **Variables**. Railway sets `PORT` and, with the Postgres
plugin, `DATABASE_URL`. Minimum for a live instance:

- App: `DATABASE_URL`, `SESSION_SECRET`, `SESSION_HTTPS_ONLY=true`,
  `PUBLIC_BASE_URL`, `WHATSAPP_ADAPTER` (`mock` or `meta`; `meta` needs
  `META_WHATSAPP_TOKEN`, `META_PHONE_NUMBER_ID`).
- Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `PRICE_ID_XA_149`,
  `PRICE_ID_XA_330`, `PRICE_ID_XA_990` (a tier without its Price id renders a
  disabled button, never a broken link), `STRIPE_XA_TIER_MODE`,
  `PRICE_ID_APPS_SETUP`, `PRICE_ID_APPS_MONTHLY`. Legacy single-price path:
  `STRIPE_XAUTOPILOT_AMOUNT_CENTS`, `STRIPE_XAUTOPILOT_MODE`,
  `STRIPE_XAUTOPILOT_PRICE_ID`.
- Order mirroring (n8n): `N8N_XAUTOPILOT_ORDER_URL`, `N8N_APPS_ORDER_URL`.
- Onboarding after payment: `X_OAUTH_ONBOARDING_URL` (empty falls back to
  `/x-autopilot/onboarding.html`).
- Google sign-in and Sheets: `GOOGLE_OAUTH_CLIENT_ID`,
  `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_SHEETS_REFRESH_TOKEN`,
  `GOOGLE_SHEETS_SPREADSHEET_ID`, `GOOGLE_SHEETS_RANGE`,
  `GOOGLE_SHEETS_RECONNECT_KEY`.
- Internal notifications: `HQ_MAIL_WEBHOOK_URL`; contact form mail (optional):
  `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `CONTACT_TO`.
- Error alerts: `ERROR_ALERT_WEBHOOK_URL` — the n8n *Engine Error Alerts*
  webhook; every unhandled exception is POSTed there once.
- X Autopilot engines and panel: `XAUTOPILOT_JUDGE_KEY`, `N8N_XA_PANEL_URL`,
  optional `N8N_XA_VETO_LOG_URL`, `ANTHROPIC_API_KEY`.
- `/apps/admin`: `ADMIN_EMAILS` (comma-separated Google accounts).
- CI only, never in production: `XA_E2E_KEY` (enables the e2e sign-in routes).
- GitHub Actions variable (not Railway): `BUS_URL` — the agent bus intake the
  live checklist posts regressions to.

### How a stranger buys

1. Opens `https://www.zorbeck.com`, reads the name and the one-liner, taps
   **See the product** → `/x-autopilot/`.
2. Picks a tier and taps **Start**. Only tiers whose `PRICE_ID_XA_*` is set are
   links; the button leads to `/x-autopilot/checkout/<tier>`, which creates a
   Stripe Checkout Session (subscription mode, billing address required) and
   redirects to Stripe's hosted page.
3. Pays by card on Stripe → returns to `/x-autopilot/success?session_id=…`,
   which confirms the order and links to the X authorization step
   (`X_OAUTH_ONBOARDING_URL`, or the on-site form).
4. Stripe sends `checkout.session.completed` to `/stripe/webhook`; the app
   writes the plan row in Postgres and the `xautopilot_orders` row via n8n
   (answers `503` if that write fails, so Stripe retries).
5. The buyer can later sign in with Google on `/x-autopilot/panel` using the
   email used at checkout.

The `/apps/` flow is the same shape with one Checkout Session for setup fee
plus subscription, returning to `/apps/success`.

### How to refund or cancel

- **Refund**: Stripe Dashboard → **Payments** → open the payment → **Refund** →
  full amount. Stripe emits `charge.refunded`, which the webhook maps to the
  plan (`mark_plan_refunded`). A signed-in customer can also refund their own
  active plan on `/x-autopilot/panel` (`POST /x-autopilot/panel/refund`, built
  for the CHF 1 smoke test: set `STRIPE_XAUTOPILOT_AMOUNT_CENTS=100`, buy,
  refund, set it back).
- **Cancel a subscription**: Stripe Dashboard → **Customers** → the customer →
  the subscription → **Cancel subscription** (immediately or at period end).
  `customer.subscription.deleted` reaches `/stripe/webhook` and writes the
  `canceled` row to the venture's n8n order table. No deploy needed.
- **Rotate a secret**: change it in Railway Variables; the save redeploys.
  Register the webhook endpoint again if `STRIPE_WEBHOOK_SECRET` changes.

### Alerts and checks

- **Agent bus**: `bus/` is the STARTEND Agent Bus V0 (see
  [Agent bus](#agent-bus) and `bus/README.md`). Regressions found by the live
  checklist are posted there as one `SIGNAL` when the Actions variable
  `BUS_URL` is set.
- **HQ mail lane**: `HQ_MAIL_WEBHOOK_URL` mails the Sheets reconnect link when
  `GOOGLE_SHEETS_REFRESH_TOKEN` is missing or invalid.
- **CI on every PR** (`.github/workflows/ci.yml`): `python` — ruff + pytest
  against a Postgres service container; `node` — nieczytaj/liesnicht tests;
  `e2e` — the Playwright stranger journey (`npm run e2e`) on a bare checkout
  with dummy env: landing heading within 10 s, X Autopilot checkout entry
  point present, imprint page, `/healthz`, zero console errors, layout shift
  < 0.1. It never pays and needs no secret. `e2e_products` — the journeys
  behind sign-in (`e2e/tests/*.spec.ts`) against a real Postgres with
  migrations applied: a paid test user sees 7 scheduled posts on the panel and
  can pause, the `/apps` WhatsApp demo completes and the booking shows up in
  `/apps/admin`; then Lighthouse (mobile) on `/`, `/x-autopilot/` and `/apps/`
  must score ≥ 90 in every category (`e2e/lighthouse-check.mjs`).
- **Error alerts**: `app/core/alerts.py` reports every unhandled exception
  to `ERROR_ALERT_WEBHOOK_URL` (n8n *Engine Error Alerts*) with path, method
  and a bounded stack, and answers the visitor with a plain German 500. A dead
  webhook is logged, never raised.
- **Per-venture handover** (URLs, env vars, refunds, lanes, Railway services,
  known gaps): `docs/HANDOVER.md`. Self-review of the sales surfaces:
  `docs/REVIEW_2026-09-08_sales.md`.
- **Live** (`.github/workflows/live-checklist.yml`, every 4 h and on demand):
  `scripts/live-checklist.js` GETs every URL in `live-targets.json`
  (HTTPS, `/healthz`, imprint, checkout, login), writes `reports/live/` (board
  on GitHub Pages, last result on the `live-status` branch) and posts a bus
  `SIGNAL` on regression. Run it locally with `npm run live-checklist`.
- **Railway**: healthcheck on `/health` (DB-backed); `alembic upgrade head`
  runs on every container start.

### Copy rules

Guest-facing WhatsApp messages are German-first and live only in
`app/templates/messages/` — never inline in Python. Site copy: de-CH "Sie",
ss not ß, thousands as `CHF 1'390`, plain words, no buzzwords, no comparisons
with competitors, nothing about the founder's corporate past. The landing page
carries EN and DE side by side (`data-lang` toggle); keep both in step.
