# HANDOVER — STARTEND portfolio service and public doors

For whoever runs this next: what is deployed, where, which variables it
needs, how a stranger buys, how to refund, how to know it is healthy. No
secret values appear here; every variable is named, its value lives in the
Railway or n8n environment only.

## Services and URLs

| Service | Railway | URL | What it serves |
| --- | --- | --- | --- |
| `portfolio` (HQ views) | project `startend`, service `portfolio` | https://hq.startend.ch (alias `portfolio-production-f01d.up.railway.app`) | Static `/srv` written at boot: board `ptf-k4x9m2.html`, `next-k4x9m2.html`, `sop-k4x9m2.html`, `bus-k4x9m2.html`, `checklist-k4x9m2.json`, per-initiative SPEC pages |
| `app` (this FastAPI app) | see `railway.toml`; health check `/health` | https://www.startend.ch | Home, `/apps/`, `/x-autopilot/`, `/origicast/`, `/impressum/`, `/agb/`, `/datenschutz/`, Stripe webhook |
| `liesnicht` / `nieczytaj` | own services from `nieczytaj/` | liesnicht.ch, nieczytaj.pl | Node tenants, own README |

The HQ views are **rebuilt on every boot** of the `portfolio` service. Its
start command fetches `boot/views_boot.py` from `main` on
raw.githubusercontent.com, so a merge to `main` plus a redeploy is a publish.
There is no build step and no CDN; `python -m http.server` serves `/srv`.

## Environment variables

### `portfolio` service (HQ views)

| Variable | Required | Purpose |
| --- | --- | --- |
| `CANON_RW_URL` | yes | Canon RW webhook (n8n). Read at boot for `BOARD_HTML`, `NEXT_HTML`, `STRAT_HTML`, `*_OPS_HTML`, `INIT_*_HTML`. A write key: never in git. |
| `BUS_STATE_URL` | yes | Bus read-state URL, substituted into the bus page. |
| `SRV_DIR` | no | Defaults to `/srv`. |
| `REPO_RAW_BASE` | no | Raw base for `boot/` when the pages are not on disk. |
| `VIEWS_BOOT_PY` | legacy | Env-only fallback of the boot script; used only if the fetch from the repo fails. Delete once a few deploys ran green. |
| `BOOT_PY`, `PAGE_B64`, `SALES_BOOT_PY`, `TRADEOPS_BOOT_PY`, `NHT_BOOT_PY`, `STRAT_B64`, `EXEC_B64` | legacy | Earlier boot steps still in the start command. `BOOT_PY` writes the raw canon board first; `views_boot.py` then overwrites it with the composed board and falls back to that raw file if canon is unreachable. |

### `app` service (FastAPI)

Full list with comments: `.env.example`. The ones that decide whether money
and alerts flow:

| Variable | Purpose |
| --- | --- |
| `STRIPE_SECRET_KEY` | `sk_test_…` until told otherwise. Test mode is the default for every door. |
| `STRIPE_WEBHOOK_SECRET` | Signing secret of the one endpoint `POST /stripe/webhook`. |
| `STRIPE_API_BASE` | Leave empty in production. CI sets it to `ci/stub_stripe.py`. |
| `PUBLIC_BASE_URL` | `https://www.startend.ch` — success/cancel URLs are built from it. |
| `SESSION_SECRET`, `SESSION_HTTPS_ONLY=true` | Signed session cookie (ORIGICAST age gate, X Autopilot panel). |
| `PRICE_ID_XA_149/330/990`, `PRICE_ID_APPS_SETUP/MONTHLY` | Stripe Price ids; an unset tier renders a disabled button, never a broken link. |
| `ORIGICAST_LIVE` | `0` (default) hides Season / Hour / Keep; `1` renders them. |
| `ORIGICAST_TEST_AMOUNT_CENTS` | `100` = CHF 1.00 test. |
| `HQ_MAIL_WEBHOOK_URL` | HQ Mail lane (n8n). Receives the ORIGICAST refund reminder and the Sheets reconnect mail. |
| `ERROR_ALERT_WEBHOOK_URL` | Webhook of n8n workflow **Engine Error Alerts** (`N6gYXlzZUn6OXOs4`). Every unhandled 5xx posts `{service, path, method, status, error, ts}`. |
| `SERVICE_NAME` | Label in the alert, default `automation_app`. |
| `N8N_APPS_ORDER_URL`, `N8N_XAUTOPILOT_ORDER_URL` | Order rows into the n8n data tables. |
| `DATABASE_URL` | Postgres (Railway plugin). `/health` checks it; `/healthz` does not. |

## How a stranger buys

1. **ORIGICAST** — https://www.startend.ch/origicast/ → answer the 21+ gate
   → `/origicast/door` → «CHF 1 Test bezahlen» → Stripe Checkout (CHF 1.00,
   test card `4242 4242 4242 4242`) → `/origicast/success?session_id=…` with
   the reference. Stripe emails the receipt; HQ receives the refund reminder.
2. **/apps** — https://www.startend.ch/apps/ → «Jetzt einrichten» → one
   Checkout Session with the setup fee and the monthly subscription →
   `/apps/success` form (restaurant, number, hours) → row in `apps_orders`.
3. **/x-autopilot** — https://www.startend.ch/x-autopilot/ → tier button →
   Checkout → `/x-autopilot/panel/login?session_id=…` → plan row in Postgres
   and `xautopilot_orders`.

The same three flows are what CI runs as the stranger e2e (`e2e/tests/`),
against `ci/stub_stripe.py` for ORIGICAST.

## How to refund

1. Stripe dashboard → **Payments** → find the payment (search the session id
   from the success page or the HQ mail) → **Refund** → full amount. Takes
   under a minute; the buyer sees it in 5–10 days on the card.
2. For a subscription (`/apps`, `/x-autopilot`): **Customers** → subscription
   → **Cancel** (immediately or at period end), then refund the last invoice
   if owed. `customer.subscription.deleted` reaches the webhook and writes the
   cancellation row.
3. The CHF 1 tests are refunded within one working day, every time — the
   AGB promise it (`/agb/`, section 3).

## How to know it is healthy

| Check | Green looks like |
| --- | --- |
| `GET https://www.startend.ch/healthz` | `{"status":"ok"}` — the process serves. |
| `GET https://www.startend.ch/health` | `{"status":"healthy"}` — Postgres answers too. Railway's health check. |
| Portfolio deploy log | One `boot5 ok <KEY> <FILE> <BYTES>` per view; `boot5 ok BOARD_HTML ptf-k4x9m2.html … source=canon`. `source=disk` means canon was unreachable and the previous board was reused. |
| `python3 scripts/publish_verify.py --live https://hq.startend.ch` | `PASS 0 mismatch(es)`. Run from `main` after every redeploy. |
| CI `quality` workflow | pytest green, Lighthouse ≥ 90 on every gated page, Playwright green. Reports are uploaded as the `quality-reports` artifact. |
| Engine Error Alerts | An email per unhandled 5xx with the classified cause. Silence plus green `/healthz` is the normal state. |

## Runbooks

`https://hq.startend.ch/sop-k4x9m2.html` — rendered from `boot/data/sop.json`:
redeploy the HQ views, move an initiative on the checklist, add a view,
canon write protocol, the CHF 1 test and refund, error alerts, Sheets
reconnect, manual outreach.

## Rules that do not change

- No secrets in code or chat; env-only. The canon and bus webhooks are write keys.
- Stripe test mode unless stated otherwise. Manual outbound only. Trading paper only.
- Guest-facing copy is de-CH (`ss`, `CHF 1'390`, «Sie»), from `app/templates/messages/`.
- Governance (canon, decisions) stays in claude.ai; this repository holds code and operational state (`boot/data/*.json`) only.
