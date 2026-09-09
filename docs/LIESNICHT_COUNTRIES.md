# LIESNICHT country separation — 2026-09-09

Marcin request: separate Switzerland, Germany and Austria on the existing Liesnicht websites.

Cause verified from deployed source: all Liesnicht hosts selected id=de, one FEEDS_DACH pool/state.de, CHF prices, de-CH/Europe-Zurich and a hard-coded www.liesnicht.ch canonical. Railway had only www.liesnicht.ch and www.liesnicht.de attached; Austria returned 502.

Implemented: exact domain mapping; distinct country mastheads and accents; explicit country navigation; separate publisher pools, clusters/categories/latest/API/RSS and summary key namespaces; regional metadata/currency/time zones; isolated country advertising settings and pageview counts; honest empty source state. Same maintained news engine; Polish feeds/routes/prices preserved. Country-specific Stripe variables take precedence; legacy German-product variables fall back only for CH. No checkout payment was made or claimed.

Verification: Node syntax check; npm test plus npm run validate passed, including 220 country checks. The tests invoke the actual server request handler without opening sockets; they seed publisher stories and verify own-country inclusion, cross-country exclusion, empty Austria behavior, exact hosts with TENANT pinned, metadata, currency, ad targeting and checkout selection. Existing Polish and Swiss regression checks pass. ORF's official https://rss.orf.at/news.xml returned HTTP 200 with 24 RSS/RDF items on 09 Sep; the existing parser supports its item/link/dc:date structure.

Deployment target remains martinszreter/automation_app main → Railway startend / liesnicht, source root nieczytaj, node server.js. Production verification is pending merge and deployment at this checkpoint.

Austria: www.liesnicht.at was added to the existing service on port 8080. Railway requires CNAME www.liesnicht.at → vtu61v3l.up.railway.app; current value was empty and certificate status VALIDATING_OWNERSHIP. No Infomaniak connection is available (plugin search returned no match). Apex liesnicht.at should redirect to https://www.liesnicht.at after that record resolves. Do not mark Austria public-ready until HTTPS succeeds.

HQ bus update: attempted takeover report was rejected by automatic approval review because it classified project/repository information going to n8n as unapproved disclosure. No successful bus post is claimed; no alternate delivery to that webhook was attempted.

Next action: complete AT DNS and verify all three country domains against the deployed revision. Commercial LIVE remains a separate payment/fulfillment gate.

