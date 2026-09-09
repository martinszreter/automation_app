# Execution tasks — martinszreter/automation_app

Planning owner HQ_GPT; execution GPT_CURSOR. Maximum 60 minutes per selected Cxx range. All boxes start unticked: existing behavior may be verified and accepted without rebuilding it. Record actual command/URL, result, timestamp and commit as evidence below each box. Read docs/SPEC.md for bus, ownership, payment and seed-branch rules.

## C02 — 3.5a X Autopilot

Existing reservation #401. Dependency: none beyond the single-writer rule.

- [ ] C02-01 — Repair the canonical post-payment redirect and plan entitlement.

  Acceptance: `python -m pytest tests/test_x_autopilot.py tests/test_xautopilot_panel.py -q` exits 0; paid checkout returns to the correct panel/sign-in path, cancellation grants nothing, and the selected tier survives the redirect.

- [ ] C02-02 — Finish Google sign-in ownership and session error handling.

  Acceptance: `python -m pytest tests/test_xautopilot_panel.py -q` exits 0 with state replay, wrong-account, signed-out and expired-session cases.

- [ ] C02-03 — Reconnect Sheets through the existing OAuth path and persist the refresh token securely.

  Acceptance: Open the existing `/x-autopilot/sheets/reconnect` flow using its secret parameter privately; after owner consent, an authenticated read of the configured spreadsheet/range returns the expected header row. Never post the secret-bearing reconnect URL to the bus.

- [ ] C02-04 — Make missing/revoked Sheets authorization show a recoverable panel state.

  Acceptance: `python -m pytest tests/test_xautopilot_panel.py -q` exits 0 with revoked token and provider timeout cases; the panel explains reconnection without disclosing token values.

- [ ] C02-05 — Prove the shared webhook handles settlement and refund without duplicate order delivery.

  Acceptance: `python -m pytest tests/test_stripe_webhook.py tests/test_x_autopilot.py tests/test_xautopilot_panel.py -q` exits 0; duplicate events produce one state change and unpaid sessions cannot activate a plan.

- [ ] C02-06 — Record a stranger-flow smoke and the exact remaining human click.

  Acceptance: `curl -fsSL https://www.startend.ch/x-autopilot/` returns the offer with imprint; record the actual checkout→Google→panel and Sheets result in docs/HANDOVER.md, with timestamp and commit. Mark an unperformed consent/payment as BLOCKED.

## C03 — 3.5b Restaurant app

Existing reservation #402. Dependency: C02 in automation_app.

- [ ] C03-01 — Repair one complete restaurant demo journey using the existing mock messaging adapter.

  Acceptance: `python -m pytest tests/test_apps.py tests/test_booking_actions.py tests/test_mock_adapter.py -q` exits 0; a demo booking/order reaches confirmation exactly once.

- [ ] C03-02 — Complete checkout and tenant-safe fulfillment for the approved offer.

  Acceptance: `python -m pytest tests/test_apps.py tests/test_stripe_webhook.py -q` exits 0 for valid, cancelled, duplicate and wrong-tenant requests; no WhatsApp/customer message is sent during fixtures.

- [ ] C03-03 — Verify the public offer and imprint on the actual deployed origin.

  Acceptance: `curl -fsSL https://www.startend.ch/apps/` returns the correct restaurant offer and legal links; record HTTPS and checkout results without calling a mock live.

- [ ] C03-04 — Prepare ten distinct Zürich restaurant email drafts from verified public business contacts.

  Acceptance: Validate docs/outreach/restaurants-zrh.csv with `python -c "import csv; r=list(csv.DictReader(open('docs/outreach/restaurants-zrh.csv'))); assert len(r)==10 and len({x['business'] for x in r})==10; assert all(x['source_url'].startswith('https://') and x['sent']=='false' for x in r)"`; Marcin reviews and sends individually only after LIVE.

- [ ] C03-05 — Record the exact source extraction and deployment gap for strict LIVE.

  Acceptance: `test -s docs/RESTAURANT_DEPLOY.md` exits 0; it lists current repo/service/domain ownership, the proposed destination and a source-to-target file manifest; no infrastructure is deleted or silently moved.

## C05 — 8 Security — five X OAuth sets

Existing reservation #404. Dependency: C02 and C03 in automation_app.

- [ ] C05-01 — Map all five credential sets to their current accounts and consumers without exporting values.

  Acceptance: `test -s docs/X_ROTATION.md` exits 0; the inventory contains exactly five distinct set IDs and each required n8n/Railway consumer, with names and account IDs only.

- [ ] C05-02 — Rotate and securely distribute the first credential set using the supported provider flow.

  Acceptance: Authenticated `GET https://api.x.com/2/users/me` with the replacement returns the expected account ID, and the existing consumer dry run succeeds. Use the existing signed client for the credential type; do not expose credentials. Revoke the old set after replacement verification when overlap is supported.

- [ ] C05-03 — Rotate and verify the remaining four credential sets one at a time.

  Acceptance: Authenticated `GET https://api.x.com/2/users/me` and the existing consumer dry run pass for all five inventoried sets; record the expected account IDs and old-credential invalid/revoked results. For an immediately invalidating provider rotation, prepare consumers first and record any exact consent/outage dependency.

- [ ] C05-04 — Remove secret-bearing diagnostic output from affected paths.

  Acceptance: `python -m pytest tests/test_x_autopilot.py tests/test_xautopilot_panel.py -q` exits 0 and the rotation evidence contains only names, account IDs and status; no token or secret-bearing callback URL is committed.

- [ ] C05-05 — Record the rotation result and any remaining consent by credential-set ID.

  Acceptance: `test -s docs/X_ROTATION_PROOF.md` exits 0; exactly five results say verified/revoked or name an exact BLOCKED action. Never report all rotated from a runbook alone.

## C06 — 1.1 LIESNICHT

Existing reservation #405. Dependency: C05.

- [ ] C06-01 — Reconcile the current locale/host fix with PR #43.

  Acceptance: `cd nieczytaj && npm test && npm run validate` exits 0; DE/CH host fixtures choose the expected tenant and canonical URL.

- [ ] C06-02 — Wire the configured advertiser slot/duration to the approved Stripe purchase path.

  Acceptance: `cd nieczytaj && npm test` exits 0 for valid slot, missing config and forged price; unset payment configuration remains explicitly unavailable.

- [ ] C06-03 — Verify the live German advertiser page and legal footer.

  Acceptance: `curl -fsSL https://www.liesnicht.ch/werbung` renders the intended tenant, approved CHF offer and imprint; an authenticated Stripe lookup verifies the destination link.

- [ ] C06-04 — Record the tenant’s remaining own-repo/Railway/domain and self-pay gaps.

  Acceptance: `test -s docs/LIESNICHT_LIVE.md` exits 0 with observed URL results, timestamps and the exact first missing gate.

## C08 — 1 nieczytaj.pl

Existing reservation #407. Dependency: C06.

- [ ] C08-01 — Make the Railway service build the committed nieczytaj source using the existing app configuration.

  Acceptance: `cd nieczytaj && npm test && npm run validate` exits 0 and the Railway deployment references the pushed commit/root directory; preserve the prior source for rollback.

- [ ] C08-02 — Complete the Polish advertiser purchase links and unavailable-state copy.

  Acceptance: `cd nieczytaj && npm test` exits 0 for tenant isolation, valid ad package and missing Stripe configuration.

- [ ] C08-03 — Verify the live Polish advertiser page and canonical redirects.

  Acceptance: `curl -fsSL https://nieczytaj.pl/reklama` renders Polish offer text, correct active Stripe destination and imprint; record final URL and deployment revision.

- [ ] C08-04 — Record the exact own-repo/own-project and self-pay gaps.

  Acceptance: `test -s docs/NIECZYTAJ_LIVE.md` exits 0; each gate is backed by a current observation or marked pending.

## C09 — 3.5d Custom AI Agents

Existing reservation #408. Dependency: C08.

- [ ] C09-01 — Reconcile the existing agent offer with its pricing PR and actual fulfillment.

  Acceptance: `python -m pytest tests/test_public.py tests/test_stripe_webhook.py -q` exits 0; the displayed approved offer matches server-selected checkout configuration.

- [ ] C09-02 — Connect one paid order to the existing intake and fulfillment workflow.

  Acceptance: `python -m pytest tests/test_stripe_webhook.py -q` exits 0 with duplicate/unpaid events and one fixture order creating exactly one intake record; use no live email or paid model call.

- [ ] C09-03 — Verify the public offer and first-value instructions.

  Acceptance: `curl -fsSL https://www.startend.ch/agents/` returns a concrete current offer, working CTA and imprint; docs/HANDOVER.md states the deliverable, timing and real external blockers.

## C12 — 3.9 Zorbeck

Existing reservation #411. Dependency: C09.

- [ ] C12-01 — Prove the existing Zorbeck source before extraction.

  Acceptance: `cd zorbeck && python -m pytest -q` exits 0 for checkout, intake, pages and webhook tests.

- [ ] C12-02 — Extract the existing app and its tests to the destination with source provenance.

  Acceptance: `gh repo view martinszreter/zorbeck --json nameWithOwner,defaultBranchRef` succeeds and docs/EXTRACTION.md maps source paths/hashes; if access/create is blocked, push the preparation in the source repo without growing product scope.

- [ ] C12-03 — Bind the extracted app to its own Railway project and valid domain.

  Acceptance: `curl -fsSL https://www.zorbeck.com/` returns the intended property-finder page with valid TLS; record service/project/revision and preserve the prior service for rollback.

- [ ] C12-04 — Record the real checkout/intake journey and remaining LIVE gates.

  Acceptance: Run the extracted `python -m pytest -q` successfully and verify the public intake response; no LIVE label until own repo/project, active approved checkout, auth if applicable and owner self-pay are all evidenced.

## C14 — 3 Life Matrix

Existing reservation #413. Dependency: C12.

- [ ] C14-01 — Locate and preserve the existing Life Matrix surface and implement one complete planning loop.

  Acceptance: `python -m pytest tests/test_views_boot.py tests/test_public.py -q` exits 0, plus `python -m pytest tests/test_life_matrix.py -q` after adding the focused test for create goal→save next action→reload progress in the recovered route.

- [ ] C14-02 — Handle empty, invalid and missing-storage states without losing user work.

  Acceptance: Run `python -m pytest tests/test_life_matrix.py -q` after adding the focused planning-loop test in the previous item; blank/oversized input and storage failure produce validation/recovery without cross-user disclosure.

- [ ] C14-03 — Record the actual preview URL, imprint and remaining product/LIVE decisions.

  Acceptance: `test -s docs/LIFE_MATRIX.md` exits 0 with the concrete deployed/preview route and successful journey; an undefined buyer/price remains an explicit product gate.

## C15 — 1.8 Personal brand offer

Existing reservation #414. Dependency: C14.

- [ ] C15-01 — Connect the existing offer page to the approved purchase or inquiry path.

  Acceptance: `python -m pytest tests/test_public.py tests/test_views_boot.py -q` exits 0 with the resolved page and its CTA; record the actual URL in docs/PERSONAL_BRAND.md.

- [ ] C15-02 — Make copy and legal details match what the service can deliver today.

  Acceptance: Run `curl -fsSL "$PERSONAL_BRAND_URL"` using the exact route recorded in docs/PERSONAL_BRAND.md; expect one current offer, price if approved, fulfillment expectation and imprint, with no employment disclosure or invented proof.

- [ ] C15-03 — Prepare a truthful owner preview and the next concrete conversion step.

  Acceptance: `test -s docs/PERSONAL_BRAND.md` exits 0 with URL, screenshot/result and remaining buyer/payment decisions; do not send outreach.

## C16 — 1.3 English/global news, ungelesen and skimthenews

Existing reservation #415. Dependency: C15.

- [ ] C16-01 — Add or repair the next canon-defined tenant’s host/locale/feed mapping.

  Acceptance: `cd nieczytaj && npm test && npm run validate` exits 0 with fixtures for the new host and regression checks for PL/DE hosts.

- [ ] C16-02 — Render a useful empty/feed-error state and correct tenant legal/advertiser links.

  Acceptance: `cd nieczytaj && npm test` exits 0 with empty feed, unavailable feed and cross-host canonical cases.

- [ ] C16-03 — Record domain ownership, source reuse and the next publishable tenant.

  Acceptance: `test -s docs/NEWS_TENANTS.md` exits 0; every touched alias names its tenant/source and preview URL, and unowned/unattached domains remain pending.

## C19 — 3.10 Founder Test

Existing reservation #418. Dependency: C16.

- [ ] C19-01 — Recover and version the existing assessment source with provenance.

  Acceptance: `test -s docs/FOUNDER_TEST_EXTRACTION.md` exits 0 with source/service and hash comparison; do not print PAGE_GZ_B64 or unrelated environment values.

- [ ] C19-02 — Complete the recovered assessment→result→restart journey.

  Acceptance: Add the focused recovered-flow test and run `python -m pytest tests/test_founder_test.py -q`; valid outcomes, incomplete answers and restart pass deterministically against the recovered application route.

- [ ] C19-03 — Verify its public HTTPS/health/legal path and record the price decision.

  Acceptance: `curl -fsSL https://founder.startend.ch/` returns the assessment with valid TLS and imprint, or record the exact domain/service blocker. Do not delete the service or activate an undefined price.

## C20 — 2.3b ORIGICAST

Existing reservation #419. Dependency: C19.

- [ ] C20-01 — Reconcile the ORIGICAST door from PR #56 with current main.

  Acceptance: `python -m pytest tests/test_views_boot.py tests/test_public.py -q` exits 0 and the existing door renders at the recorded route.

- [ ] C20-02 — Connect the approved offer to a CHF 1 smoke purchase and useful original sample.

  Acceptance: `python -m pytest tests/test_stripe_webhook.py -q` exits 0 with unpaid/duplicate handling; active Stripe smoke link has currency CHF and the correct door/fulfillment destination.

- [ ] C20-03 — Verify public copy, sample availability and the owner-payment handoff.

  Acceptance: Run `curl -fsSL "$ORIGICAST_DOOR_URL"` and `curl -fIL "$ORIGICAST_SAMPLE_URL"` using the exact public URLs recorded in docs/ORIGICAST.md; expect the offer with imprint and an available original sample. The document lists remaining owner payment/domain/account gates without fabricated evidence.

## C22 — 3.5b Restaurant verticals

Existing reservation #421. Dependency: C03 and C20.

- [ ] C22-01 — Implement one vertical as configuration plus existing guest-message templates.

  Acceptance: `python -m pytest tests/test_apps.py tests/test_booking_actions.py -q` exits 0 for both restaurant and the new demo tenant.

- [ ] C22-02 — Prove tenant separation and the demo booking/confirmation loop.

  Acceptance: `python -m pytest tests/test_booking_actions.py tests/test_mock_adapter.py -q` exits 0 with cross-tenant denial and no live messages.

- [ ] C22-03 — Record the demo URL, supported behavior and rollout prerequisite.

  Acceptance: `test -s docs/RESTAURANT_VERTICALS.md` exits 0 with one working demo and the first real-customer/product ownership gate; no duplicate repo/engine is created for every vertical.

## C26 — 1 X distribution and news engines

Existing reservation #425. Dependency: C22.

- [ ] C26-01 — Repair the first existing distribution-to-metrics roundtrip with recorded fixture IDs.

  Acceptance: `python -m pytest tests/test_x_autopilot.py tests/test_xautopilot_panel.py -q` exits 0 and the existing n8n dry run reads the expected account/post/metric records without publishing.

- [ ] C26-02 — Make duplicate events and missing/revoked account credentials fail safely.

  Acceptance: Add focused consumer fixtures and run `python -m pytest tests/test_x_distribution.py -q`; duplicates produce one output, missing credentials skip/reconnect, and no fallback account or live publish is used.

- [ ] C26-03 — Prepare the remaining canon-defined channel rows on the same engine.

  Acceptance: `test -s docs/X_CHANNELS.md` exits 0 with one row per requested channel/alias, existing engine ID, account status and next action; uncreated handles/consents remain owner actions.

- [ ] C26-04 — Record one end-to-end proof and the exact remaining channel blockers.

  Acceptance: Run `python -m pytest tests/test_x_distribution.py tests/test_xautopilot_panel.py -q`; recorded fixture post/metric IDs read back consistently. docs/HANDOVER.md identifies the existing workflow and does not call a dry run a live publication.

## C29 — 0/7 Halted automation_app work and HQ support

Existing reservation #428. Dependency: C26.

- [ ] C29-01 — Reconcile and finish the actual remaining interrupted PR delta.

  Acceptance: `gh pr list --repo martinszreter/automation_app --state open --json number,title,headRefName` identifies the current PR; `python -m pytest tests/test_views_boot.py tests/test_public.py tests/test_stripe_webhook.py -q` exits 0 after only necessary fixes.

- [ ] C29-02 — Verify touched views and product regressions through existing CI.

  Acceptance: Run `python -m pytest tests/test_views_boot.py tests/test_public.py tests/test_stripe_webhook.py -q` and the current CI checks for the changed paths; required checks pass and no duplicate view/consumer is introduced.

- [ ] C29-03 — Make the handover identify merged, preserved and still-blocked work.

  Acceptance: `test -s docs/HANDOVER.md` exits 0 with concrete PR/commit URLs, one first unticked item per lane and exact runtime-secret/click blockers. Do not resume @claude dispatch or schedule a check-in.


## C06-COUNTRY — separate Switzerland, Germany and Austria (09 Sep amendment)

- [x] C06-COUNTRY-01 — Resolve exact country hosts and country-specific mastheads/locales/canonical/advertising currency. Acceptance: `cd nieczytaj && npm test && npm run validate`; CH/DE/AT and preview fixtures pass, Polish regression passes, DE/AT cannot inherit CH checkout links.
- [x] C06-COUNTRY-02 — Isolate news pools, categories, latest articles, API and RSS by country. Acceptance: country regression test seeds one unique story per country's publisher; each host's HTML, API and RSS contain only its own story; failed/empty pools do not fall back across editions.
- [ ] C06-COUNTRY-03 — Verify production editions and Austria domain routing. Acceptance: HTTPS GET `/`, `/health`, `/api/top`, `/rss.xml` and `/werbung` for CH/DE/AT selects expected country/source pool/currency/canonical. Record status, deployment and exact outstanding DNS if any in docs/LIESNICHT_COUNTRIES.md. A DNS blocker leaves this item unticked.

  Evidence 2026-09-09: `npm test && npm run validate` passed. 220 country assertions plus existing Polish/Swiss regressions and TENANT validation. Request fixtures exercise the actual HTTP handler with seeded publisher articles; no outgoing feed or payment requests. C06-COUNTRY-03 remains open until public AT DNS and production checks pass.

