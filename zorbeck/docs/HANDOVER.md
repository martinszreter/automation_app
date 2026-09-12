# Zorbeck redesign handover — 2026-09-09

Root is now the global investment discovery preview. Use the existing Railway service and source branch main; all changed product code stays within /zorbeck. The old paid offer is preserved at /deal-alarm, with cancelled checkout handling retained on /?abgebrochen=1. There is no enabled Stripe checkout or live AI/listings provider in this release. All sample data, prices and images are labelled illustrative.

Implemented: linked interactive OSM/Leaflet map and property cards; location, country, price, type, saved and sort controls; responsive map/list switching; accessible dialogs; locally saved shortlist; early-access request via existing configured SIGNUP_WEBHOOK_URL, with explicit error on failed persistence and input/consent validation. No new account login is claimed. No real customer or test email was sent.

Validation: ruff clean, 99 Python tests pass, JS syntax and six filter checks pass, rendered HTML select options/IDs/local assets verified. Photographs inspected and attributed. No browser/visual QA was run in this session. Existing CI continues its preserved-offer browser checks.

Deployment verified: PR #67 merged as 36e3efa62f77615c0aad1ecdc929dbf966883d6b. Railway deployment 1595ec2b-be5b-4c5e-b941-512f5bdc831f reached SUCCESS at 2026-09-09 20:34 UTC. https://automationapp-production.up.railway.app/ returns 200 with data-zorbeck-discovery=2026-09-09 and the sample disclosure; /healthz reports ok=true; CSS, JS, all three optimized photographs and /deal-alarm return 200. zorbeck.com redirects to www.zorbeck.com; the public checking proxy rejects its certificate with a hostname mismatch (502). Public DNS currently uses Infomaniak nameservers and www CNAME 4dl8f4q9.up.railway.app. This existing CNAME is an observation, not a verified required Railway target. The required domain target is not confirmed; do not use guessed values or accept pre-existing staged Railway changes.

ZD-04 is complete for the published discovery preview. Next: resolve custom-domain routing with verified DNS records, then connect licensed live property feeds and sourced AI analysis. C12 repository extraction and paid-report fulfillment remain separate unfinished work. Do not label this preview commercially LIVE or claim real listings, AI results, authenticated accounts or completed purchase flows.

Release gate follow-up: the first hosted run passed all 99 Python tests, all eight preserved-offer browser checks and the other repository checks. Homepage mobile Lighthouse performance was 76 (accessibility 96, best practices/SEO 100, CLS 0, no console errors). Added image-provider WebP renditions, response compression and deferred initialization of the hidden mobile map. The unchanged gate then passed: homepage mobile performance 94 on all three runs, accessibility 96, best practices/SEO 100, CLS 0 and no console errors. All five repository checks passed on 4926a24817ba6f6de3f135472245f78b8b9d86e5 before merge.

## Palette refinement — 2026-09-10

Founder requested a more luxurious color palette while keeping the approved layout. Discovery now uses charcoal navigation and primary actions, warm ivory surfaces, and muted champagne accents for the brand, selected controls and map pins. Shared color tokens replace the green palette; the favicon and browser theme color match. The stylesheet and favicon URLs have new cache versions. Layout, typography, catalog, filters, forms and application behavior are preserved. No new dependencies, image assets or data integrations were introduced.

## Search and results placement — 2026-09-10

Founder requested the property cards and map higher on the page, with search directly above the results. The workspace now starts with compact market shortcuts, then the search form, the “Places worth exploring” title and the existing cards-left/map-right view. The large introductory section is merged into one compact note below the results. Sample disclosure remains next to the results title; preview details remain available. The results title is now the page h1, the luxury palette is preserved, and the CSS/JS URLs are versioned. Submitting search retains the selected market so the reordered controls compose correctly.

## Registration continuation — 2026-09-10

Successful early-access registration now returns a server-generated next_url. A selected catalog example opens /properties/{id}; a general signup opens /search with the saved location and optional EUR budget. Invalid property IDs are rejected before forwarding to the signup sink. Failed saves do not return a destination. The browser checks the same-origin destination, then navigates after acknowledgement. No email enters the URL or browser storage. A short-lived sessionStorage receipt shows a one-time confirmation on the destination page; the privacy copy describes its path, search parameters and timestamp.

The property page uses the existing charcoal, ivory and champagne design and photographs, with photo attribution, facts, illustrative price, truthful listing status and a link back to the map. Shared SVG icons and the registration form avoid drift between pages. Existing search, local shortlist, checkout and webhook routes remain available. All eight properties remain fictional, with no live seller links or verified investment assessment. Selected property interest is forwarded with the existing registration payload; downstream storage of the additional optional fields has not been independently audited.

Validation added for acknowledgement-dependent navigation, property selection, safe destinations, rejected registrations, all eight detail routes, missing-property 404, filtered/empty/escaped server search, custom budgets, and optional one-time browser confirmation storage. Unit checks use mocks only and do not send real registration requests or emails. The existing CI browser and Lighthouse gates are preserved; discovery/registration Node unit checks are added to the gate. Publish and live verification are tracked in the release PR.

Business proposal: retain free discovery and opt-in search capture first; acquire authorized current listings in a limited set of markets, then test paid sourced comparisons and personalized deal alerts. CHF 29/month is a proposed test price, not an active product or validated willingness to pay. No new billing, seller commission or email campaign is enabled.

## Worldwide map behavior — 2026-09-11

The discovery map opens at world scale and filters the example cards on pan/zoom. Search as I move is enabled by default; visitors can pause it and choose Search this area. China and Thailand shortcuts position the camera and show the honest no-inventory state. Existing market shortcuts, budget/type filters, saved examples, registration and property-detail pages remain available. Manual map movement replaces a previous location search, while retaining budget/type/saved filters. The world control removes location constraints. Mobile view switching preserves the area and applies any pending country camera change after the map becomes visible.

The pure geographic filter handles ordinary bounds, boundaries, the date line and repeated world copies. Markers are placed in the world copy nearest the map center. Camera fitting and resizing are kept separate from user pan/zoom to avoid resetting filters or bouncing the map back. Tests use synthetic country coordinates only within the test file; the production catalog is unchanged.

No live listing provider is connected. The current Railway configuration exposes only PORT and SIGNUP_WEBHOOK_URL. Real China, Thailand and worldwide offers remain dependent on approved source access, appropriate coordinates, freshness/status checks and original seller links. The interface says Live listings not connected and does not treat a lack of preview records as zero real homes for sale. No data-provider outreach, contract or purchase was performed.

## Single globe and luxury appearances - 2026-09-12

Discovery now uses `globe.js`, self-hosted D3 3.1.1 / d3-array 3.2.4, and local Natural Earth 5.1.2 country geometry. `discovery-core.js` adds the same orthographic camera math used for pin visibility and result filtering, including rear-hemisphere exclusion and screen clipping at zoom. No external map tile requests or Leaflet flag remain on discovery. Dependencies and geography provenance are recorded under `static/vendor/d3/README.md`.

Rotation is available by mouse, touch, arrow keys and labelled buttons; wheel, pinch and controls zoom. It updates results on gesture completion, or waits for Search this area when automatic search is off. Mobile list/globe switching retains camera and filters. No perpetual animation. Price labels use leader lines to reduce overlaps. All amounts and photographs remain clearly illustrative; Japan and Italy market shortcuts do not invent stock.

`theme.js` restores the allowlisted Ivory/Dusk/Midnight choice before styling and provides a shared selector on discovery and property pages. Only this preference is added to localStorage. Registration, consent, redirect validation and paid legacy routes are unchanged. Privacy text reflects local geography and theme preference. Python and browser checks cover the preserved flow, rotation, visibility and cross-page theme persistence; hosted CI remains the release gate.
