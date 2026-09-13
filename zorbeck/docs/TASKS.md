# Zorbeck discovery redesign tasks

- [x] ZD-01 Implement the global map and property discovery homepage, responsive styling, source-labelled sample data, detail views, filters and device-local shortlist. Acceptance: root returns 200 with discovery marker and sample disclosure; JS parses with node --check; local image and vendor asset paths exist; filter unit checks cover city, budget, type and empty results.
- [x] ZD-02 Implement honest early-access registration through the existing lead sink. Acceptance: tests cover invalid input, missing consent/configuration, upstream rejection/failure and acknowledged success; no real emails or payment calls during tests.
- [x] ZD-03 Preserve the existing paid-offer/checkouts and legal behavior. Acceptance: existing unit suite passes with homepage-specific legacy assertions moved to /deal-alarm; factual map/local-storage privacy text present.
- [x] ZD-04 Commit, publish and verify the redesign. Acceptance: exact committed revision deployed; homepage 200 with new discovery marker, assets 200, health healthy; report any remaining custom-domain error without calling the broken domain fixed.

Validation 2026-09-09: 99 Python tests passed; ruff passed; JS syntax and six filter scenarios passed; rendered HTML IDs/select options and all local assets verified. Existing offer has its own /deal-alarm URL. Upstream registration is mocked in tests; no live sample registration or payment was sent.

Publication verified 2026-09-09: PR #67, merge 36e3efa62f77615c0aad1ecdc929dbf966883d6b, Railway deployment 1595ec2b-be5b-4c5e-b941-512f5bdc831f SUCCESS. Root discovery marker, health, CSS/JS, WebP photos and preserved offer all verified at the generated public URL. Custom-domain routing remains unresolved. Hosted release checks passed; homepage mobile Lighthouse 94/96/100/100 with CLS 0.

## Marketplace release — 2026-09-13

- [x] ZM-01 Real source catalogue and dedicated property pages, original currency and source-check dates; same globe and themes.
- [x] ZM-02 Persistent accounts, password/recovery protection, private shortlists, seller drafts/photos, enquiries and owner moderation.
- [x] ZM-03 Fixed-price featured placement and owner payment check, signed idempotent fulfilment, refund/dispute revocation and payment exception queue.
- [ ] ZM-04 Review exact commit, pass release checks, activate persistent Railway volume, configure dedicated Stripe links/webhook, deploy and verify. Record outcomes in the release PR.

Future growth: seller-provided inventory, written agency/photo permissions and agreed data feeds; verified email and delivery provider; externally backed-up storage; source freshness checks and a measured community distribution workflow. No bulk scraping or unsolicited outreach is enabled.
