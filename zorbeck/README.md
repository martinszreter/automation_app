# Zorbeck — Deal-Alarm für Immobilien

Ein Angebot, ein Preis, ein Klick: der Besucher nennt Stadt und Budget, zahlt
einmalig über Stripe und bekommt sofort die Bestätigung seiner Angaben — per
Seite und per E-Mail. Kein Konto, kein Abo, keine Cookies.

Separate Railway service in this repo (Root Directory = `zorbeck`), independent
of the repo-root `app/` package. Entry point `app:app` (`zorbeck/app.py` is a
shim over `zorbeck_app/`).

```
zorbeck/
  app.py                 # uvicorn app:app — shim
  zorbeck_app/
    main.py              # routes: / , /checkout, /danke, /stripe/webhook, legal, health
    config.py            # env-only settings (nothing outbound by default)
    stripe_api.py        # Checkout Session + webhook signature (httpx, no SDK)
    intake.py            # form validation, Stripe metadata <-> intake, confirmation mail
    mail.py              # HQ Mail Lane (n8n) client
    alerts.py            # Engine Error Alerts (n8n N6gYXlzZUn6OXOs4) client
    stub.py              # CI-only Stripe / mail / alert / lead stand-in (/_stub)
    messages/de.py       # every guest-facing text (de-CH, "Sie", ss not ß)
  templates/             # base, index, danke, impressum, agb, datenschutz, error
  static/style.css
  tests/                 # pytest (67 tests, no network, no stub)
  e2e/                   # Playwright stranger test + Lighthouse gate (CI)
```

## HANDOVER

### URLs

| What | Where |
| --- | --- |
| Landing (one offer, one price, one CTA) | `/` |
| Checkout (POST from the form) → Stripe | `/checkout` |
| Success / first value | `/danke?session_id=…` (noindex) |
| Stripe webhook to register in the dashboard | `{PUBLIC_BASE_URL}/stripe/webhook`, event `checkout.session.completed` |
| Legal (linked from every page) | `/impressum`, `/agb`, `/datenschutz` |
| Health (Railway healthcheck + monitors) | `/health`, `/healthz` — `{"ok": true, "stripe": bool, "mail": bool, "alerts": bool, "stub": false}` |

### Environment variables (Railway service `zorbeck`)

No URL or key is in the code. Everything below is empty by default and the
service degrades explicitly when something is missing (503 on checkout, alert
on a missing mail lane).

| Variable | Purpose |
| --- | --- |
| `PUBLIC_BASE_URL` | Public origin, e.g. `https://zorbeck.ch`. Stripe success/cancel URLs and the links in the mail. Falls back to the forwarded host. |
| `STRIPE_SECRET_KEY` | Stripe **test** key until stated otherwise. Unset → checkout answers 503 «Zahlung im Moment nicht möglich». |
| `STRIPE_WEBHOOK_SECRET` | Signing secret of the endpoint above. Unset → every webhook is rejected with 400. |
| `ZORBECK_PRICE_CENTS` | The one price, in Rappen. Default `4900` (CHF 49). **CHF 1 test: set `100`**, buy, refund, set back. |
| `STRIPE_PRICE_ID` | Optional. A dashboard Price id; when set, `ZORBECK_PRICE_CENTS` is ignored for the line item (the page still shows `ZORBECK_PRICE_CENTS`, keep them equal). |
| `HQ_MAIL_WEBHOOK_URL` | HQ Mail Lane webhook (n8n), `POST {subject, body, to}`. Sends the buyer's confirmation. Unset → the webhook answers 200 with `mailed:false` and raises an alert. |
| `ALERT_WEBHOOK_URL` | External entry of the n8n workflow **Engine Error Alerts** (`N6gYXlzZUn6OXOs4`). Every unhandled error, failed checkout, failed mail and lost lead row posts `{app:"zorbeck", node, message, description, stack, url, mode}` there; n8n classifies it and e-mails the diagnosis (24 h dedup per fault). |
| `SIGNUP_WEBHOOK_URL` | Lead sink (n8n `zorbeck-lead`). One JSON row per intake: `status` = `checkout_started` / `paid` / `signup`. Unset → rows are only logged. |
| `STRIPE_API_BASE` | Leave unset (defaults to `https://api.stripe.com/v1`). CI points it at the stub. |
| `ZORBECK_STUB` | **Never set on Railway.** Mounts `/_stub`, which "pays" anything. `/healthz` shows `"stub": true` when it is on. |

### How a stranger buys

1. Opens `/`, reads one headline and one price, types e-mail, city, budget.
2. Clicks **Deal-Alarm starten · CHF …** → `POST /checkout` validates (German
   errors, typed values kept), writes a `checkout_started` lead row, creates a
   one-time CHF Checkout Session (locale `de`, intake in `metadata`) and
   redirects to Stripe.
3. Pays on Stripe (card, TWINT). Stripe sends `checkout.session.completed` to
   `/stripe/webhook`; the signature is verified, a `paid` lead row is written and
   the confirmation mail (city, budget, amount) goes out through HQ Mail.
   If the mail lane fails the endpoint answers 503 so Stripe retries.
4. Stripe returns the buyer to `/danke?session_id=…`, which reads the session
   from Stripe and shows the confirmed intake. Unpaid → «Zahlung wird geprüft»
   (202); unknown → soft 404 with the contact address.

### First value (within 2 minutes, no human)

What the buyer gets, and from where:

- **On the success page**: the confirmed intake (city, budget, amount) and
  «Was jetzt passiert» — four steps: now (this confirmation), within 24 hours
  (first report), 30 days (alerts), then (ends by itself) — plus the refund
  promise.
- **By e-mail**: the same confirmation and timeline, through the HQ Mail Lane.

The mail goes out from **whichever arrives first**: Stripe's
`checkout.session.completed` webhook or the buyer landing on `/danke`. The
success page never waits for the webhook (Stripe delivers it asynchronously,
sometimes minutes later). It is sent **once**: the process remembers the
session, and `metadata[confirmation_sent]` is written onto the Checkout
Session so a retry, a reload or another instance does not mail again. If the
mail lane is down the page still shows the timeline, says the mail follows,
raises an alert and leaves the flag unset — Stripe's retried webhook (503)
then sends it. Both paths are in the stranger e2e, including the
«webhook late, mailed once» case.

### CHF 1 test (real Stripe, test mode)

Set `ZORBECK_PRICE_CENTS=100` on the service, redeploy, buy with Stripe's test
card `4242 4242 4242 4242`, check the mail arrived, refund (below), set the
price back. The stranger test in CI does the same path against the stub on
every push, so a broken checkout never reaches `main`.

### How to refund

Stripe Dashboard → Payments → the payment (search the buyer's e-mail) →
**Refund** → full amount. The buyer sees the refund on their card within
5–10 days. There is no subscription to cancel. The AGB promise a full refund
when no first report arrives within 24 hours.

### CI (`.github/workflows/zorbeck.yml`)

Runs on every push and PR that touches `zorbeck/`:

1. `ruff check .` and `pytest` (67 tests, without the stub environment — proves
   nothing goes outbound by default).
2. The service starts with `e2e/stub.env` (Stripe, mail lane, alert handler
   and lead sink all point at the in-process `/_stub` router).
3. **Stranger e2e** (Playwright, Pixel 7): land → offer understood in 10 s (one
   h1, one price, one button) → pay CHF 1 on the stub checkout → `/danke` shows
   the intake → the signed webhook was accepted → the confirmation mail is in
   the outbox → both lead rows exist → zero console errors. Plus: German
   validation, legal pages with imprint, `/healthz`, and a deliberate 500 that
   must reach the alert handler.
4. **Lighthouse gate** (mobile): performance, accessibility, best practices and
   SEO each ≥ 90, CLS = 0 and no console errors on `/`, `/impressum`, `/agb`,
   `/datenschutz` and a paid `/danke` — median of 3 runs per page (a single run on a cold CI
   runner swings by 20+ points without any change to the page).

Locally:

```bash
cd zorbeck
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && python -m pytest -q
cd e2e && npm ci && npx playwright install chromium
npx playwright test          # starts uvicorn with stub.env itself
node lighthouse.mjs          # against the same server (CHROME_PATH optional)
```

### Deploy

Railway: Root Directory `zorbeck`, start command from the Procfile
(`uvicorn app:app --host 0.0.0.0 --port $PORT`), healthcheck `/health`.
After the first deploy register the Stripe webhook endpoint and set the
variables above.
