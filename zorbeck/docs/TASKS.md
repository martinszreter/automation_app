# Zorbeck discovery redesign tasks

- [x] ZD-01 Implement the global map and property discovery homepage, responsive styling, source-labelled sample data, detail views, filters and device-local shortlist. Acceptance: root returns 200 with discovery marker and sample disclosure; JS parses with node --check; local image and vendor asset paths exist; filter unit checks cover city, budget, type and empty results.
- [x] ZD-02 Implement honest early-access registration through the existing lead sink. Acceptance: tests cover invalid input, missing consent/configuration, upstream rejection/failure and acknowledged success; no real emails or payment calls during tests.
- [x] ZD-03 Preserve the existing paid-offer/checkouts and legal behavior. Acceptance: existing unit suite passes with homepage-specific legacy assertions moved to /deal-alarm; factual map/local-storage privacy text present.
- [ ] ZD-04 Commit, publish and verify the redesign. Acceptance: exact committed revision deployed; homepage 200 with new discovery marker, assets 200, health healthy; report any remaining custom-domain error without calling the broken domain fixed.

Validation 2026-09-09: 99 Python tests passed; ruff passed; JS syntax and six filter scenarios passed; rendered HTML IDs/select options and all local assets verified. Existing offer has its own /deal-alarm URL. Upstream registration is mocked in tests; no live sample registration or payment was sent.
