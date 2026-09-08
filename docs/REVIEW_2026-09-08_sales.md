# Self-review — sales surfaces, 2026-09-08

Scope: everything a stranger can reach and pay on — `/`, `/x-autopilot/`,
`/x-autopilot/panel`, `/apps/`, `/apps/demo`, `/apps/admin`, `/impressum/`,
liesnicht.ch / nieczytaj.pl — plus the Stripe webhook and the ops surface.
Reviewed against the Wave 2 quality bar (stranger e2e in CI, Lighthouse
mobile ≥ 90, zero console errors, no layout shift, de-CH copy, imprint on
every page, cookie-free analytics, `/healthz`, error alerts, handover docs).

## Verdict

Sellable with the operator to-dos below done. No secret in code; Stripe
prices are referenced by env var only; outbound mail goes only through the
HQ Mail Lane and is never triggered towards a stranger's address from a
public form; trading is not part of this app.

## What was checked and what changed

| Area | Finding | Action |
| --- | --- | --- |
| Stripe webhook | Already one endpoint (`POST /stripe/webhook`) shared by both ventures since #50; the per-venture paths stay as aliases with the same handlers. | Kept. Documented in HANDOVER. |
| Dead routes | `/x-autopilot/event`, `/x-autopilot/stats.json` are live (landing beacon + counter, `noindex`). `/grokywood/` is a waiting-list page that the home page links to. `/dashboard` is the internal booking table for the WhatsApp engine. `/x-autopilot/onboarding.html` is the fallback when `X_OAUTH_ONBOARDING_URL` is unset. | Nothing removed: every route has a caller. |
| Imprint | Missing the `Impressum` link on `/`, `/grokywood/`, `/thanks.html`; the onboarding footer said "startend.ch" instead of the company. | Fixed. Every public page now names STARTEND GmbH and links `/impressum/`. |
| de-CH copy | No `ß` in any guest-facing text (the only hits are a comment and an HTML-entity table). Thousands use `CHF 1'390` style via `format_chf`. Panel, demo, admin, digest use "Sie". | Kept. Style guide for DE headlines: `nieczytaj/STYLE_DE.md`. |
| Claims | No comparative claims against named competitors; nothing about the founder's corporate background on the sales pages. | Kept. |
| Analytics | Cookie-free: in-process counters (`/x-autopilot/stats.json`, nieczytaj `pv`) and the n8n page-view beacon. The only cookie is the signed session cookie after Google sign-in. | Kept. |
| Ops | `/healthz` (process only) and `/health` (database) exist; unhandled exceptions now go to the n8n *Engine Error Alerts* webhook. | Added `app/core/alerts.py`, `ERROR_ALERT_WEBHOOK_URL`. |
| Tests | 261 pytest tests (judge fixtures, panel, apps demo/admin, alerts, webhook), Node tests + validator for both tenants, two Playwright jobs, Lighthouse gate. | Up from 219 before Wave 2. |

## Known gaps (operator)

1. Set in Railway: `ERROR_ALERT_WEBHOOK_URL`, `N8N_XA_PANEL_URL`,
   `XAUTOPILOT_JUDGE_KEY`, `HQ_MAIL_WEBHOOK_URL`, `ADMIN_EMAILS`; optional
   `ANTHROPIC_API_KEY`. Never set `XA_E2E_KEY` in production.
2. Schedule the weekly digest in n8n (`POST /x-autopilot/digest/run`, header
   `X-Judge-Key`, Monday 08:00 Zurich).
3. Repoint the `nieczytaj` Railway service to this repository (root
   directory `nieczytaj`) so PL gets the SEO layer and `/reklama` changes.
4. Migrate off `railway.json` / `railway.toml` before 2026-12-01.
5. Setup-fee refunds and CHF 1 smoke-test refunds stay manual in the Stripe
   dashboard by design.
