# Marketplace operations — 13 September 2026

The existing globe, filters and Ivory / Dusk / Midnight design are preserved. The current product is free property discovery and seller publication, plus optional paid placement. The historical `/deal-alarm` offer is separate and remains dependent on its older configuration; do not advertise a paid report pipeline as working.

## Routes and user journey

| Route | Purpose |
| --- | --- |
| `/`, `/search` | Source advertisements and reviewed seller listings on one globe |
| `/properties/{id}` | Public facts and date; free sign-in opens external source or seller enquiry |
| `/register`, `/login`, `/recover` | Account and single-use recovery-key flow |
| `/account` | Own listings, enquiry inbox, shortlist, payment status, marketing preference |
| `/sell`, `/sell/new` | Free owner / authorised-agent intake with photos |
| `/seller/properties/{id}` | Private draft preview and submission |
| `/promote/{id}` | Approved, available property: CHF 49 for 30 days, one payment |
| `/admin` | Owner moderation, account email list, source rechecks, payment exceptions |
| `/admin/claim` | One-time owner setup using an environment-configured token hash |
| `/api/marketplace/stripe` | Dedicated, signed Stripe event receiver |
| `/payments/return` | Confirmation from stored paid event; URL alone proves nothing |

The browser shows the recovery key once after registration/recovery. Store it privately. The current service does not verify email ownership or send password-reset, seller-inbox or registration emails. Enquiries appear in the seller account and explicitly share the buyer's email. Support and data requests go to `info@startend.ch`.

## Required deployment configuration

Keep one Railway replica. A SQLite database with transactions and WAL lives on a persistent volume, including the small initial photo collection. This is an initial-scale implementation; move database and photos to managed storage before scaling replicas or volume use.

| Variable | Value / source |
| --- | --- |
| `ZORBECK_DATABASE_PATH` | `/data/zorbeck.sqlite3`; mount must exist before app startup |
| `ZORBECK_COOKIE_SECURE` | `true` on production |
| `PUBLIC_BASE_URL` | Verified HTTPS Railway public origin |
| `ZORBECK_ADMIN_BOOTSTRAP_HASH` | SHA-256 of a random 32-byte URL-safe setup token; never store the raw key in git |
| `ZORBECK_PROMOTION_LINK` / `_ID` | Dedicated Stripe Payment Link URL and `plink_` ID, CHF 49 |
| `ZORBECK_SMOKE_LINK` / `_ID` | Separate owner-only real CHF 1 check, no featured entitlement |
| `ZORBECK_MARKETPLACE_WEBHOOK_SECRET` | Dedicated webhook's signing secret; never the legacy secret |
| `SIGNUP_WEBHOOK_URL` | Existing n8n lead sink; preserve its current private value |

No Stripe runtime API key is required for Payment Links. Never set `ZORBECK_STUB` in production. The public health response includes `accounts`, `marketplace_payments` and `stub`; `stripe` refers to the separate legacy offer.

Activate only the reviewed volume/configuration patch; do not accept unrelated staged Railway changes. Deploy the exact CI-passing commit. Verify accounts and payments health, source pages, media rules and `stub:false`. An unset database path disables accounts; a configured missing directory fails startup rather than silently losing accounts on temporary storage.

The first owner signs up and claims the one-time private setup token. Its hash must be configured before deployment. The fragment-based onboarding link keeps the token out of request URLs and referrers. Once claimed, the database rejects subsequent claims, even with the same token. Never derive admin access from an email address alone. Remove the bootstrap variable after the owner has claimed it.

## Payments and fulfilment

Create two fixed Payment Links in STARTEND's connected Stripe account. Each has `metadata.venture=zorbeck` and `metadata.offering=promotion` or `smoke`, quantity one, currency CHF and total 4900 or 100 cents. No recurring price, adjustment, discount, seller payout or property deposit. The smoke item is an owner operational check and is excluded from product revenue metrics. Do not charge it automatically.

The app generates an opaque order ID and uses Stripe's `client_reference_id`. The Payment Link redirects to `/payments/return?session_id={CHECKOUT_SESSION_ID}`. Required webhook events are `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `charge.refunded`, and `charge.dispute.created`.

Only a valid signed live event with matching order, link ID, venture/offering metadata, currency, exact total, payment mode and `payment_status=paid` activates placement. The seller reconfirms availability before checkout. The 30 days start at confirmation; payment does not auto-publish a draft. Refunds/disputes revoke the paid benefit, including events received before checkout completion. A repeated webhook does not extend placement. A second payment against a reused link/order goes into the owner exception list for refund review, not another entitlement. Unsupported or unavailable purchases never silently grant placement.

Stripe handles card details. Automatic tax is not enabled by this implementation; the connected account had no active Stripe Tax registrations when checked. The fixed total must match the fulfillment rule. Assess registrations and invoicing requirements before introducing automatic tax or changing commercial terms; update validation alongside any pricing change.

In Stripe Dashboard, review the payment IDs in the owner exception queue and perform agreed refunds. Automated tests simulate Stripe locally; they do not prove a real checkout charge and webhook delivery. Use the separate owner CHF 1 control for that explicit user test after deployment.

## Inventory and growth

`data/sourced-properties.json` contains four independently written factual source summaries checked on 2026-09-13: Naka municipal 1-33 (JPY 100,000), Ikata municipal S038 (JPY 100,000), VeroAffare Mussomeli V004360 (EUR 1, apartment needing work), and Spiaggia Mussomeli V000401 (EUR 16,000). Links are in each record. A listed price is not the total purchase/renovation cost or confirmation of current availability. No external photos, agency representation, guaranteed returns or negotiated discounts are implied. Source records have approximate city pins and dated ECB EUR comparisons (2026-09-11 snapshot).

Source records over 30 days old are labelled for recheck. An owner may hide a withdrawn source or reconfirm the source date after actually inspecting it. Seller properties expire from public discovery after 90 days without an update. Direct submissions need rights declarations, at least one photo, usable map coordinates and human review before publication. Review is editorial, not proof of title or legal due diligence. Edits return to draft/review; active paid content needs support assistance to avoid changing an advertised paid record without review. Sellers may mark sold/withdraw immediately.

Build inventory in this order:

1. Maintain a small useful collection of current, source-linked offers and their limitations.
2. Invite owners and agencies to use `/sell`, providing their own content and permission; no automated outreach is included.
3. Agree written photo/text and feed access with agencies. Import only agreed fields, retain provenance and source IDs, deduplicate, check availability and remove withdrawals.
4. Add country feeds incrementally. RESO is a technical standard, not an MLS licence; public portal access is not an automatic worldwide redistribution right.
5. Publish measured, consented newsletter/social features through real channels when they exist. The optional seller permission is recorded now. It does not promise traffic, an AI audience, a social post or a sale.

Initial revenue is the clearly labelled CHF 49 featured placement. Free discovery and publication build useful inventory. Buyer subscriptions, referral commissions and agency plans remain future experiments; do not charge for a deal score or coverage that has not been built and validated.

## Data, maintenance and backup

Passwords use salted scrypt; sessions and recovery tokens are stored as hashes. Production cookies are Secure, HttpOnly and SameSite. State-changing routes enforce CSRF, body limits and ownership. Photos are re-encoded with Pillow, limited and stripped of metadata; drafts/photos are private to owner/admin until publication. Payment and moderation writes use durable transactions.

Accounts, listings, consent preferences and payment events queue minimal records into the existing n8n lead sink with retry. Local owner administration displays stored account emails. A downstream 2xx acknowledges delivery but does not independently prove Leadmine field mapping. Passwords, session/recovery keys and photos are never forwarded. Email ownership is explicitly unverified and marketing is optional.

Enable Railway volume backups and verify restores. Use SQLite's online backup API for a consistent application snapshot; never copy only the main DB file while WAL writes are in flight. Keep an encrypted copy outside the service volume according to the operator's retention policy. A persistent volume by itself is not an offsite backup. Monitor disk capacity, queued lead deliveries, failed logins, source age and payment exceptions. Before multiple replicas or large inventory, migrate to managed Postgres and object storage.

Automated verification covers authentication/recovery, private data access, moderation, CSRF, source provenance, price/status/mode mismatches, paid fulfilment, duplicate events, refunds/disputes, account shortlists and the full mobile seller flow. Existing discovery, legacy offer and Lighthouse release gates remain required.
