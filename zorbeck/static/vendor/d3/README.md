# Globe dependencies

Self-hosted, pinned upstream distributions:
- d3-geo 3.1.1: https://cdn.jsdelivr.net/npm/d3-geo@3.1.1/dist/d3-geo.min.js
- d3-array 3.2.4: https://cdn.jsdelivr.net/npm/d3-array@3.2.4/dist/d3-array.min.js

ISC license texts accompany both files. Only geographic projection and array utilities are used; no runtime CDN requests or API keys.

`/static/discovery/world-countries.json` is derived from Natural Earth 5.1.2 `ne_110m_admin_0_countries.geojson`:
https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_110m_admin_0_countries.geojson

Coordinates rounded to 3 decimal places; properties reduced to English name and country. Geometry is unchanged otherwise. This low-resolution layer provides geographic orientation, not property boundaries or street navigation. Natural Earth data is public domain: https://www.naturalearthdata.com/about/terms-of-use/. A visible text credit remains in the product. The sphere never wraps into repeated world copies.
