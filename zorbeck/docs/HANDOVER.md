# Zorbeck redesign handover — 2026-09-09

Root is now the global investment discovery preview. Use the existing Railway service and source branch main; all changed product code stays within /zorbeck. The old paid offer is preserved at /deal-alarm, with cancelled checkout handling retained on /?abgebrochen=1. There is no enabled Stripe checkout or live AI/listings provider in this release. All sample data, prices and images are labelled illustrative.

Implemented: linked interactive OSM/Leaflet map and property cards; location, country, price, type, saved and sort controls; responsive map/list switching; accessible dialogs; locally saved shortlist; early-access request via existing configured SIGNUP_WEBHOOK_URL, with explicit error on failed persistence and input/consent validation. No new account login is claimed. No real customer or test email was sent.

Validation: ruff clean, 99 Python tests pass, JS syntax and six filter checks pass, rendered HTML select options/IDs/local assets verified. Photographs inspected and attributed. No browser/visual QA was run in this session. Existing CI continues its preserved-offer browser checks.

Deployment status: prepared for publication; verify root data-zorbeck-discovery=2026-09-09 and /healthz on the actual runtime. Do not confuse the working generated URL with the currently unresolved custom-domain routing. Exact domain DNS target is not confirmed in this work; do not use guessed values.

First remaining task: ZD-04 publish and verify. C12 repository extraction and live property-feed/AI/report fulfillment remain separate unfinished work. Do not label this release commercially LIVE from visual completion or mock tests.

Release gate follow-up: the first hosted run passed all 99 Python tests, all eight preserved-offer browser checks and the other repository checks. Homepage mobile Lighthouse performance was 76 (accessibility 96, best practices/SEO 100, CLS 0, no console errors). Added image-provider WebP renditions, response compression and deferred initialization of the hidden mobile map; rerun the unchanged release gate before merge.
