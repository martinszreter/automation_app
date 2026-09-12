# Zorbeck investment discovery — 2026-09-09

User direction: redesign and deploy the existing Zorbeck site as a clean, premium global real estate investment discovery platform with a map and registration.

Scope: reuse the existing FastAPI service, expose an English global discovery homepage, interactive world map, synchronized property cards, location/budget/type filters, sample detail views, device-local shortlist, and a real early-access registration using the existing n8n lead sink. Preserve existing checkout, webhook and legal routes; move the original paid-offer homepage to /deal-alarm and retain all legacy form error behavior there.

Truthful boundary: all initial property data and prices are explicitly illustrative. Photographs are illustrative licensed architecture photos, never claimed to depict a sample property's address. No fake active listings, investment returns, AI outputs, verified deals or completed account sign-in. Search is a local filter of the labelled sample catalog. Registration means early access, not a working authenticated account. If the lead sink is unavailable, return an error instead of claiming registration succeeded. No payment activation or live test charge in this redesign.

Visual direction: architectural photography and a precise map workspace; warm ivory surfaces, charcoal navigation and actions, restrained champagne accents, large clean typography, rounded cards and a map/list split. Discovery controls and results appear immediately. Mobile has map/list switching, accessible modals and horizontal market chips.

Data: embedded immutable sample property records (id, city/country, coordinates at city level, illustrative EUR price, property type, bedrooms, area, photo and description). Images served locally with attribution. localStorage stores only device-local property IDs. POST /api/early-access validates email, city, budget and explicit consent, applies input size and rate limits, awaits the configured existing signup webhook and acknowledges only successful persistence requests. Never logs full payloads or secret URLs.

Map: pinned self-hosted Leaflet 1.9.4, OSM HTTPS tiles, visible attribution, no prefetch/offline loading, provider outage state. No new paid service or key. Update factual privacy text for map provider, local shortlist and registration.

Deployment: existing martinszreter/automation_app /zorbeck Railway deployment. No Sites replacement or parallel engine. Update and deploy exact reviewed commit, preserve other work, verify actual homepage marker, JS/CSS/images and health. C12 repository extraction and full live listings/report pipeline remain separate open work; this redesign is not a LIVE/commercial certification.

## Registration continuation — 2026-09-10

User direction: a successful email registration must continue to the chosen property's details instead of leaving the visitor at a disabled form. Keep the approved discovery layout, collect opt-in interest for free, and plan monetization.

Selected example: card preview → registration → acknowledged save → /properties/{id}. The API validates the catalog ID, includes the selected illustrative property in the existing signup payload, and returns a server-generated same-origin destination. General registration continues to /search with location and optional EUR budget. This route renders the matching catalog subset on the server and initializes the existing browser filters and map to the same search. Empty searches show an honest empty state. Failures keep the form available and never redirect.

Dedicated property pages are public previews with architecture photography and attribution, sample facts and price, availability status, and a return to the filtered map. No live seller link exists in this catalog, so none is invented. The temporary sessionStorage confirmation contains only the destination path (which may include location and budget) and timestamp, never email. Early-access signup remains separate from account authentication.

Revenue proposal, not activated: keep discovery and opt-in registration free while establishing licensed, current listings in a small number of markets. Validate demand for a paid alert and analysis subscription, with CHF 29/month as an initial test-price hypothesis. Its value must come from original source links, freshness checks, comparable-property evidence, explainable opportunity flags and personalized alerts. Do not sell current illustrative examples as investment opportunities. Expand coverage only as source access and evidence become available. No payment collection or automated marketing is introduced by this release.

## Worldwide map discovery — 2026-09-11

User priority: moving the map to China, Thailand, the USA or another area should show properties in that area. The map now starts at world scale, and moving or zooming it filters cards and pins by the visible geographic bounds. Budget, property type and saved-only filters continue to apply. Moving the map replaces the previous text/country location filter; an explicit new text search or market shortcut clears the map-area constraint and repositions the map. Sorting does not move the map. Automatic map search is on by default and can be paused in favor of a Search this area button. China and Thailand camera shortcuts join the existing markets. The world control clears location constraints while retaining other filters.

Geographic filtering handles the date line and wrapped world copies. Programmatic camera changes and window resizing do not start a new user search. Mobile list/map switching retains the selected area, and a newly selected market is applied when a hidden map becomes visible.

Coverage limitation: this release changes map behavior only. The production catalog remains the same eight illustrative records. There is no connected live listing feed, including for China or Thailand. Empty areas explicitly distinguish missing preview inventory from the absence of real properties for sale. No additional fictional properties, seller links, alleged deals or geographic coverage claims are added.

Live-data dependency: connect authorized inventory with location, original source URL, currency, update time and status before describing results as live offers. Access must be established with data owners/providers; the existing service has only PORT and SIGNUP_WEBHOOK_URL configured. Provider research starting points are https://www.reso.org/reso-web-api/ (MLS access comes from the data provider), https://developers.idealista.com/access-request (application-based search API), and https://www.fazwaz.com/partner-agent-program (Thailand partnership, not proof of an available redistribution feed). China listing access and a suitable multi-country feed still need to be confirmed. No provider contract, account, purchase or outbound request is made in this release.

## Globe and appearance choices - 2026-09-12

Replace the repeating flat map with one draggable orthographic globe. The shaded sphere uses local D3 and public-domain Natural Earth country geometry, with no runtime tile service, token or music. Mouse/touch drag rotates it, wheel/pinch and labelled controls zoom, arrow keys rotate. Results follow the visible hemisphere and screen extent when Search as I move is enabled; manual Search this area remains available. Pins on the hidden hemisphere are not actionable. Country shortcuts still filter exact catalog countries; Japan and Italy shortcuts are included with honest missing-coverage states. Worldwide clears the geographic filter while retaining budget/type. Price labels separate where possible with leader lines back to their city-level points.

Keep property cards beside the globe, the search immediately above results, and compact explanatory copy below. Offer Ivory, Dusk and Midnight appearance choices in the top-right header, including property details pages. Store only the chosen allowlisted appearance locally. Keep server-rendered cards, registration continuation, shortlist, legacy routes and release gates intact. Remove Leaflet's flag by replacing its map integration; visible Natural Earth text credit and upstream license files remain. Update the factual privacy explanation for locally served geography and appearance storage.

Current inventory remains eight illustrative examples. A worldwide interface is not a worldwide licensed listing feed. Research and commercial recommendations do not activate subscriptions, broker referrals, payments or external listing contracts.
