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
