# STARTEND Codex execution specification — 2026-09-09

Owner: HQ_GPT. Execution team: GPT_CURSOR. This is a planning handover, not evidence that a Codex session or a production smoke test has run.

## Goal and authority

Marcin reopened ALL initiatives for building. First priority: C01 Leadmine, C02 X Autopilot, C03 Restaurant, C04 Grokywood bios, C05 five X OAuth sets. Every selected initiative gets a maximum 60-minute execution session, or ends earlier when its selected items pass or a real blocker prevents progress. This replaces the default two-hour budget and the blanket non-sales pause; it does not remove product ownership, privacy, paper-trading, no-new-subscription or human-only transaction gates. A prompt cannot guarantee a runtime longer than the host permits: checkpoint early and never add busywork to fill an hour.

One active writer per repository. Different repositories can run concurrently, preferably at most three initially to control cost. Queued bus CLAIMs are reservations, not proof that workers are running. Resume the matching reservation and inspect current PR/ref state before writing. Do not start or resume Claude actions, add dispatch labels, mention @claude on issues, schedule check-ins or poll idle PRs.

## Read and reuse

Read AGENTS.md if present, the repository README/HANDOVER, this SPEC and TASKS. Read canon _PROTOCOL, 00_INITIATIVES, 02_ASSETS and NEXT with top_only=true; use the newest current entry and current user override, not archived priorities. Fetch canon once and extract only the selected lane’s current sections; do not dump complete historical payloads into model context. Resolve existing code/PRs before creating code. Existing components and workflows are the implementation path; do not create a third engine. Preserve unrelated work and source deployments.

Canon endpoint: https://startend.app.n8n.cloud/webhook/canon-rw-9k2x7m4q
Read body: {"action":"read","keyValue":"02_ASSETS","top_only":true}. An empty canonical response is an access/protocol blocker, not authority to invent state. Values never belong in code or reports. If a canon write is necessary, updated_by=HQ_GPT and use its read→insert full prior+new change→verify→prune protocol; do not overwrite another writer.

## Session, git and bus contract

The planning brain commits docs/SPEC.md and docs/TASKS.md before implementation. Each code session executes only its selected Cxx item range. Read the latest code and preserve already-ticked items with their evidence. Tick only after its executable acceptance passes; append evidence/result/commit under the item. Commit per completed item and push main with required checks; do not force-push or bypass branch protection. Where an enforced PR gate prevents a direct push, use the existing PR/CI path and record the precise gate if it needs an external action. Product seed code must never be merged into deploy-template main.

https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k is the bus. GET it for a fresh bus_cursor (TTL 600 seconds); POST {team:"GPT_CURSOR",project:<exact project field of adopted reservation>,type:"CLAIM",what:"resume Cxx / existing reservation #ID; execute item range",next:"build",bus_cursor:<fresh cursor>}. The existing C01..C32 reservations are #400..#431. Reuse the reservation’s exact project field for CLAIM and DONE/BLOCKED so the report resolves the same lane; do not create a new project alias. A CLAIM does not replace the repo's single-writer check. Refresh the cursor before the final write, never paste an expired cursor from this document.

On all selected items passing: POST DONE with the commit URL, actual validation/deployment result and first unticked item as next (or the exact owner smoke action). On budget: push the checkpoint, keep incomplete boxes unticked and POST DONE with what:"PARTIAL — budget reached" and the first unticked item as next. DONE describes delivered work, never automatically LIVE. On real BLOCKED: finish independent in-scope preparation, push it, then POST BLOCKED with the exact missing capability/secret NAME or external click, commit URL and next item. Do not ask “shall I continue”. Never claim a push, deployment, consent, payment or account change without a successful result.

## Verification conventions

Commands run from the relevant repo/worktree root after its documented install and CI setup, with secrets injected privately. Exit 0 alone is sufficient only when the described behavior is actually asserted; do not replace behavioral checks with empty tests. Add focused tests only for money, auth, persistence, privacy or a concrete regression; preserve existing meaningful gates. For a task specifying a new script/test, creating it is part of that task. Do not assume npm scripts from one repository exist in another. Operator acceptance variables such as WORDBLAST_BASE_URL are not production secrets. URLs in historical notes are candidates to verify, not assertions of current health. A lack of access is recorded precisely rather than repeatedly probed.

## Payments, auth and LIVE

Reuse the existing Stripe integration, approved CHF offers and shared webhook/fulfillment architecture. Server selects price and return URL; validate signatures on raw webhook bodies, process events idempotently and handle pending/failed/refunded/cancelled payments. A success URL or client flag never establishes entitlement. Test fixtures/mocks and test-login doors stay off in production. Google uses the existing authorization-code flow, state verification, exact owned callback and verified identity; require customer/workspace ownership for paid data. Never expose refresh tokens, keys or secret-bearing URLs.

AI owns supported Stripe configuration, products, prices and public payment links, with credential VALUES only in Railway variables. Use a separate CHF 1 live-mode smoke price compatible with the existing purchase and entitlement type, without replacing commercial prices or adding a parallel access system. A subscription product must exercise its existing subscription gate; disable any free trial for that dedicated smoke purchase so CHF 1 is actually paid, and cancel the smoke subscription after verification to prevent renewal. A one-time product uses a one-time smoke price. Marcin makes the actual self-payment/3DS click. Verify Stripe payment and useful fulfillment, then perform the authorized refund and any smoke-subscription cancellation; deactivate/archive the used smoke price/link. A used Stripe Price is archived rather than deleted. Posting a payment link is not proof of payment.

LIVE requires evidence for all: own GitHub repo, own Railway project, own owned domain over valid HTTPS, a stranger-payable live Stripe checkout with useful fulfillment, Google Sign-In if accounts, imprint on every page, and Marcin's successful self-pay smoke. Shared source/host prototypes, mock payments and health-only checks do not pass. Foundations and paper trading have their own acceptance and are not counted as paid LIVE products.

Imprint and legal links belong on public, account, purchase, error and game screens. Reuse the verified STARTEND GmbH legal identity and existing legal components; no invented address/legal assurances. No new subscriptions. No customer/client charge, outreach send, new social account, irreversible data deletion or live-capital action is implicit in a coding handover. Marcin reviews/sends the manual emails; prepare drafts only after the relevant scope allows, and do not send before LIVE.

## Missing destination repositories

The current connector could inspect ten repositories. Proposed 39thfloor, optimizeyourkid, zorbeck, aikompetenz, restaurant-app, proposal-generator and swisseasy returned 404; that is an access/existence uncertainty, not proof they can be selected in Codex. Begin in the verified source repo and existing seed branch specified below. Use an authenticated authorized create/extraction capability if available, preserving history and current data. Copy the relevant SPEC/TASKS section into the destination and commit it before product code there. If destination creation/access is unavailable, preserve useful tested extraction work on a clearly labelled source seed branch/PR and report the exact blocker. Never merge product seeds into template main or delete a source service to make the handover look complete.

## Repository snapshot: martinszreter/automation_app

Inspected 2026-09-09; main/source revision `80cbf23044b8ef85b8364c4c177c6305d16ba6f3`. Re-check before implementing: other agents can push after this snapshot. Existing open PRs:

- #56: WAVE 2: board quality, NEXT/SOP views, ORIGICAST door, self-review (W2-P1…P4) — claude/new-session-8zo4p2 (008e295), draft.
- #52: Review pass: unified Stripe webhook covers refunds and async payments, shared helpers, hardening — claude/new-session-r36bgi (56c2194), draft.
- #43: LIESNICHT CH: locales, snap geo, canonical/sitemap — cursor/liesnicht-ch-locale-geo-0a47 (7820a7b), draft.
- #39: HQ: add initiative-level revenue geometry — hq-gpt-initiative-revenue-geometry-20260830 (6ec60e0), open.
- #38: HQ: extend hard revenue targets to 2031 — hq-gpt/revenue-ladder-2031 (22d0473), open.
- #23: Remove employment disclosure from X Autopilot sales page — claude/remove-employment-disclosure-50hvoq (5b6326c), draft.
- #17: Stripe checkout on offer pages: investigation result + x-autopilot guard — claude/stripe-checkout-product-pages-sn2lxp (28d4a41), draft.
- #14: Publish Lead-Gen pilot pricing on /agents/ (CHF 490, Stripe checkout) — claude/lead-gen-pilot-pricing-r7plpt (6ba4d3c), draft.

Execution order within this repository: C02 → C03 → C05 → C06 → C08 → C09 → C12 → C14 → C15 → C16 → C19 → C20 → C22 → C26 → C29. Budget is per selected initiative/session, not a promise to finish the entire queue in one hour.

Existing environment variable names observed in .env.example: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`, `WHATSAPP_ADAPTER`, `META_WHATSAPP_TOKEN`, `META_PHONE_NUMBER_ID`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `CONTACT_TO`, `PUBLIC_BASE_URL`, `SESSION_SECRET`, `SESSION_HTTPS_ONLY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_XAUTOPILOT_AMOUNT_CENTS`, `STRIPE_XAUTOPILOT_MODE`, `STRIPE_XAUTOPILOT_PRICE_ID`, `PRICE_ID_XA_149`, `PRICE_ID_XA_330`, `PRICE_ID_XA_990`, `STRIPE_XA_TIER_MODE`, `N8N_XAUTOPILOT_ORDER_URL`, `XAUTOPILOT_JUDGE_KEY`, `N8N_XA_VETO_LOG_URL`, `ANTHROPIC_API_KEY`, `XAUTOPILOT_GENERATE_MODEL`, `N8N_XA_PANEL_URL`, `XA_E2E_KEY`, `X_OAUTH_ONBOARDING_URL`, `PRICE_ID_APPS_SETUP`, `PRICE_ID_APPS_MONTHLY`, `N8N_APPS_ORDER_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_SHEETS_REFRESH_TOKEN`, `GOOGLE_SHEETS_SPREADSHEET_ID`, `GOOGLE_SHEETS_RANGE`, `GOOGLE_SHEETS_RECONNECT_KEY`, `HQ_MAIL_WEBHOOK_URL`, `ERROR_ALERT_WEBHOOK_URL`, `ADMIN_EMAILS`

## C02 — 3.5a X Autopilot

Goal: Finish the Stripe-to-Google-to-panel journey and reconnect the existing Google Sheets integration.

Current source and reuse: Reuse app/api/x_autopilot.py, existing panel/services/templates, tests/test_x_autopilot.py, tests/test_xautopilot_panel.py and the shared Stripe webhook. Inspect PR #52 for unmerged refund/async-payment fixes and PR #17 for checkout guard context. HANDOVER documents the three CHF 149/330/990 tiers and the existing n8n panel workflow.

Data model: Existing Stripe order/subscription references, signed user session, customer email and plan entitlement; panel profile/recent-post state remains in the existing n8n/Sheets stores. Refresh tokens are runtime credentials, not database display fields.

Routes: /x-autopilot/, /x-autopilot/panel/login, /x-autopilot/auth/google/callback, /x-autopilot/panel, /x-autopilot/sheets/reconnect, /x-autopilot/panel/refund; reuse the existing checkout/webhook routes.

Environment names only: PUBLIC_BASE_URL, SESSION_SECRET, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, PRICE_ID_XA_149, PRICE_ID_XA_330, PRICE_ID_XA_990, GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_SHEETS_REFRESH_TOKEN, GOOGLE_SHEETS_SPREADSHEET_ID, GOOGLE_SHEETS_RANGE, GOOGLE_SHEETS_RECONNECT_KEY, N8N_XA_PANEL_URL; XA_E2E_KEY only in CI.

Scope: execute the 6 actions under C02 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: No earlier same-repo product dependency; reconcile current open work first.

Edge cases and non-goals: Do not start Claude generation to test this funnel; use existing fixtures/n8n data. Successful OAuth redirect alone does not prove spreadsheet access.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C03 — 3.5b Restaurant app

Goal: Make the existing restaurant booking/ordering offer demonstrable and payment-ready, then prepare ten manual Zürich outreach drafts.

Current source and reuse: Reuse app/api/apps.py, app/services/apps_* and existing booking/message adapters; use PR #52 where it fixes the same shared payment flow. Preserve approved CHF 1,990 setup + CHF 249/month pricing. A product-specific repo/domain is still needed for strict LIVE; do not claim startend.ch/apps alone satisfies it.

Data model: Existing tenant, guest, booking/order, payment and message-delivery records; tenant boundaries and idempotent delivery are mandatory. Outreach records are drafts only and keep source URL, business contact, reason and sent=false.

Routes: /apps/ plus existing booking/demo/checkout routes in app/api/apps.py; existing /health and /healthz. Preserve German-first guest messages in the template layer.

Environment names only: PRICE_ID_APPS_SETUP, PRICE_ID_APPS_MONTHLY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, N8N_APPS_ORDER_URL, PUBLIC_BASE_URL, DATABASE_URL, WHATSAPP_ADAPTER, META_WHATSAPP_TOKEN, META_PHONE_NUMBER_ID

Scope: execute the 5 actions under C03 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C02 in automation_app

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C05 — 8 Security — five X OAuth sets

Goal: Rotate the five inventoried X OAuth credential sets without losing the correct account bindings.

Current source and reuse: Reuse the existing X onboarding workflow, credential store and consumers named in 02_ASSETS. This is an operational rotation, not a new auth system or another monitoring service.

Data model: Five logical credential-set IDs, associated app/account ID, consumer references, rotation timestamp and verification result; values never appear in reports. Separate OAuth consumer keys, access tokens and OAuth2 refresh tokens where the existing integration does.

Routes: Existing X onboarding/callback routes and the provider’s authenticated current-account endpoint for the credential type; no new public credential-management route.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 5 actions under C05 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C02 and C03 in automation_app

Edge cases and non-goals: Do not revoke an unknown/shared key blindly. If consent is required, finish the independent preparation and report the specific account and click; do not retry continuously.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C06 — 1.1 LIESNICHT

Goal: Finish the existing German news tenant’s advertiser purchase path and domain/locale behavior.

Current source and reuse: Reuse nieczytaj/server.js and PR #43 locale/canonical work; LIESNICHT is a tenant of the existing engine. Do not create another news engine.

Data model: Existing article/feed and advertising-slot configuration; preserve tenant ownership, language and geography. Stripe references belong to the selected slot and duration.

Routes: /werbung, existing article/home routes, canonical/sitemap and legal routes under the verified liesnicht.ch/de hosts.

Environment names only: TENANT, STRIPE_BANER7, STRIPE_BANER30, STRIPE_KAF7, STRIPE_KAF30, STRIPE_BOX7, STRIPE_BOX30; use existing tenant host settings.

Scope: execute the 4 actions under C06 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C05

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C08 — 1 nieczytaj.pl

Goal: Ship the existing Polish advertiser page from git and prove the correct Polish tenant serves it.

Current source and reuse: Reuse the same nieczytaj/ engine and its tests. HANDOVER says the old Railway service reads APP_SRC and does not track current git; verify this and prepare a reversible deployment of the same source.

Data model: Same news/advertiser model as C06, with Polish tenant configuration and existing PLN/approved price settings; do not copy German amounts blindly.

Routes: https://nieczytaj.pl/reklama, Polish home/articles and existing legal routes.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 4 actions under C08 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C06

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C09 — 3.5d Custom AI Agents

Goal: Complete one existing paid lead-generation agent offer and its customer intake/fulfillment path.

Current source and reuse: Reuse /agents/, the existing onboarding tables/webhooks and PR #14 pricing work. Do not start a generic agent platform or duplicate Leadmine’s lead engine.

Data model: Existing offer, order, customer intake and fulfillment status; use the existing leadmine/onboarding stores and customer ownership boundary.

Routes: /agents/ and its existing checkout/onboarding routes; retain shared legal and webhook routes.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 3 actions under C09 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C08

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C12 — 3.9 Zorbeck

Goal: Extract the existing property-finder app into its own repository and repair its deploy/domain binding.

Current source and reuse: Reuse automation_app/zorbeck, its existing tests and intake webhook. Source already works as a separate rootDirectory app; destination zorbeck returned 404 to this connector. Preserve the original deployment until the extracted app passes.

Data model: Existing subscriber/intake/search preferences and fulfillment state in the Zorbeck store; preserve data and external IDs. No new scraper, new property database or fabricated listings.

Routes: Existing zorbeck app routes, /healthz where implemented, checkout/intake/legal endpoints; www.zorbeck.com is the destination to verify.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 4 actions under C12 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C09

Edge cases and non-goals: Do not blindly remove/re-add domains from old advice; inspect actual ownership and certificate failure first.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C14 — 3 Life Matrix

Goal: Turn the existing Life Matrix concept/page into one usable save-and-return planning loop.

Current source and reuse: Recover the named Life Matrix source from 00_INITIATIVES and the existing portfolio routes/view registry; reuse that surface. Do not create another HQ board or import Unfair Start data by assumption.

Data model: A user-owned goal, next action and progress/check-in record, reusing an existing store if present. For an unpriced prototype without accounts, use local-only storage and describe its persistence limits.

Routes: Preserve the actual existing route found in the app/view registry; record it in docs/LIFE_MATRIX.md. New route names are implementation choices, not claimed pre-existing endpoints.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 3 actions under C14 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C12

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C15 — 1.8 Personal brand offer

Goal: Publish a concrete existing personal-brand service offer and a clear purchase or qualified inquiry path.

Current source and reuse: Reuse the existing startend/portfolio personal-brand surface and approved offer in canon. No corporate-background copy and no new personal website engine.

Data model: Existing service offer plus intake/order reference; only collect the information required for the stated service.

Routes: Existing personal-brand route and its CTA destination, as resolved from the route/view registry; preserve shared legal routes.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 3 actions under C15 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C14

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C16 — 1.3 English/global news, ungelesen and skimthenews

Goal: Implement the next reusable news-tenant configuration using the existing engine.

Current source and reuse: Reuse nieczytaj and its host/locale map after C06/C08; preserve EN/DE/PL tenant separation. Alias/domain concepts are not permission to spawn duplicate engines.

Data model: Tenant ID, host, locale, feed selection and ad-package configuration; existing article/slot structures remain authoritative.

Routes: Existing news home/article/ad routes resolved by tenant host; preview host must be recorded before calling it deployed.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 3 actions under C16 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C15

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C19 — 3.10 Founder Test

Goal: Recover the existing Founder Test page into git and make one useful assessment/result loop.

Current source and reuse: Reuse the founder-test service’s PAGE_GZ_B64 source on adaptable-strength as identified in 02_ASSETS, and the existing portfolio routing. Preserve the recovered UI rather than starting a second quiz engine.

Data model: Existing assessment answers/result logic; anonymous answers stay local unless a consented existing store is used. Do not invent psychometric or predictive validity.

Routes: Preserve recovered assessment/results routes; candidate public host founder.startend.ch must be verified, not assumed healthy.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 3 actions under C19 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C16

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C20 — 2.3b ORIGICAST

Goal: Finish the existing ORIGICAST door and the approved CHF 1 smoke-to-sample journey.

Current source and reuse: Resume automation_app PR #56 (WAVE 2 board/NEXT/SOP/ORIGICAST). Keep ORIGICAST work scoped to that existing door; no new portfolio board. Use canon’s locked offer and original permitted sample assets.

Data model: Existing offer, public sample and Stripe order reference. If paid accounts are added, reuse verified Google and customer entitlement; no invented paid content library.

Routes: Actual ORIGICAST route in PR #56 and the existing portfolio view registry; record the route and checkout return URL in docs/ORIGICAST.md.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 3 actions under C20 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C19

Edge cases and non-goals: Use SFW original material for this commerce smoke. No new account, paid media generation, impersonation or unsupported content claim.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C22 — 3.5b Restaurant verticals

Goal: Make one clinic/salon/garage configuration work on the existing booking engine without cloning the application.

Current source and reuse: Reuse the restaurant booking engine after C03; user reopened building, but no customer install, paid rollout or outreach is implied. Use one isolated demo tenant.

Data model: Existing tenant config, booking/service catalogue and message templates. Keep vertical copy/config separate from core booking and isolate fixtures from real customers.

Routes: Existing /apps/ demo/booking routes with an explicit demo tenant; proposed restaurant-app extraction remains a separate ownership gate.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 3 actions under C22 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C03 and C20

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C26 — 1 X distribution and news engines

Goal: Finish one useful existing distribution/metrics loop and prepare the remaining configured channels without duplicate workers.

Current source and reuse: Covers 1/1.1/1.2/1.4/1.6/1.7/1.9, including Metrics Loop, Stats Reporter, city fleet and Elon ecosystem configurations. Reuse current n8n structured engine, agent rows and publisher; C02/C05 unblock Sheets and credential consumers.

Data model: Existing agents/channels, content queue, post IDs, metrics and dedup records. Separate account IDs and disabled/draft states; a missing account never defaults to another channel.

Routes: Existing X onboarding and panel routes plus the existing n8n workflow interfaces; no new orchestration/status board.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 4 actions under C26 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C22

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.

## C29 — 0/7 Halted automation_app work and HQ support

Goal: Finish the concrete interrupted quality work, preserve the relay, and keep Claude automation halted.

Current source and reuse: Inspect PR #56 (WAVE 2 board/NEXT/SOP/ORIGICAST) and PR #52 (payment review) against current main; prior claimed PR #62 is not in the inspected open list and must be verified before referring to it. Reuse already merged WAVE 2 components. No new monitoring or agent layer.

Data model: Existing view registry/canon view IDs, application settings and regression fixtures; bus reports contain commit/next references and no secrets.

Routes: Existing portfolio views, /healthz, /health and product routes touched by the interrupted PR only.

Environment names only: Use the existing names for the reused component, as documented above/in README; invent no replacement credential store.

Scope: execute the 3 actions under C29 in TASKS.md. This is one bounded session; do not expand it into a rewrite.

Dependencies: C26

Edge cases and non-goals: Preserve existing customer data, tenant isolation and unrelated source. Missing credentials, provider errors and unavailable domains remain explicit; no fake success, new orchestration layer or unsolicited outreach.

Acceptance: the executable behavior attached to each selected checkbox, plus the shared payment/auth/LIVE requirements when applicable.
