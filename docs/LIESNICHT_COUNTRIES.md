# LIESNICHT country separation — 2026-09-09

## Published result — 09 Sep 2026, 19:40 UTC

PR #66 merged as 89ab146991744947bfd42245b4c26a6646d624ec after all four GitHub checks passed (Node, Python, stranger E2E, product E2E). Railway deployment b14abc1a-b8c7-4cf6-9b31-409af78ca45e reports SUCCESS on that revision.

Public HTTPS verification: www.liesnicht.ch and www.liesnicht.de return 200 for homepage, /health, /api/top, /rss.xml and /werbung. CH reports country ch/de-CH/CHF with 4 of 4 publisher feeds healthy; DE reports country de/de-DE/EUR with 14 of 14 feeds healthy. Home titles are LIESNICHT.CH — Nachrichten aus der Schweiz and LIESNICHT.DE — Nachrichten aus Deutschland; canonical and RSS locale match each domain. CH API/RSS had 3 top clusters from Swiss sources; DE had 12 from German sources. German advertising shows EUR and no Swiss checkout/test link. These counts are observations at verification time, not traffic claims.

Public www.liesnicht.at still returns 502. Its country code is implemented and routing attached, but C06-COUNTRY-03 remains unticked until the documented DNS record resolves and public HTTPS is verified. This is the single remaining action for this country-separation request.

Marcin request: separate Switzerland, Germany and Austria on the existing Liesnicht websites.

Cause verified from deployed source: all Liesnicht hosts selected id=de, one FEEDS_DACH pool/state.de, CHF prices, de-CH/Europe-Zurich and a hard-coded www.liesnicht.ch canonical. Railway had only www.liesnicht.ch and www.liesnicht.de attached; Austria returned 502.

Implemented: exact domain mapping; distinct country mastheads and accents; explicit country navigation; separate publisher pools, clusters/categories/latest/API/RSS and summary key namespaces; regional metadata/currency/time zones; isolated country advertising settings and pageview counts; honest empty source state. Same maintained news engine; Polish feeds/routes/prices preserved. Country-specific Stripe variables take precedence; legacy German-product variables fall back only for CH. No checkout payment was made or claimed.

Verification: Node syntax check; npm test plus npm run validate passed, including 220 country checks. The tests invoke the actual server request handler without opening sockets; they seed publisher stories and verify own-country inclusion, cross-country exclusion, empty Austria behavior, exact hosts with TENANT pinned, metadata, currency, ad targeting and checkout selection. Existing Polish and Swiss regression checks pass. ORF's official https://rss.orf.at/news.xml returned HTTP 200 with 24 RSS/RDF items on 09 Sep; the existing parser supports its item/link/dc:date structure.

Deployment target remains martinszreter/automation_app main → Railway startend / liesnicht, source root nieczytaj, node server.js. CH and DE publication is verified below; AT public verification is blocked by DNS.

Austria: www.liesnicht.at was added to the existing service on port 8080. Railway requires CNAME www.liesnicht.at → vtu61v3l.up.railway.app; current value was empty and certificate status VALIDATING_OWNERSHIP. No Infomaniak connection is available (plugin search returned no match). Apex liesnicht.at should redirect to https://www.liesnicht.at after that record resolves. Do not mark Austria public-ready until HTTPS succeeds.

HQ bus update: attempted takeover report was rejected by automatic approval review because it classified project/repository information going to n8n as unapproved disclosure. No successful bus post is claimed; no alternate delivery to that webhook was attempted.

Next action: complete AT DNS and verify all three country domains against the deployed revision. Commercial LIVE remains a separate payment/fulfillment gate.

