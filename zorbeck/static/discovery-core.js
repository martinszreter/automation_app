(function (root) {
  'use strict';
  function normalize(value) { return String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
  function longitudeNear(lng, center) { return lng + 360 * Math.round((center - lng) / 360); }
  function inBounds(property, bounds) {
    if (!bounds) return true;
    const { south, west, north, east } = bounds;
    if (![south, west, north, east, property.lat, property.lng].every(Number.isFinite) || south > north) return false;
    if (property.lat < south || property.lat > north) return false;
    // Leaflet may return wrapped longitudes or a viewport spanning several world copies.
    const span = east - west;
    if (Math.abs(span) >= 360) return true;
    const width = (span + 360) % 360;
    const offset = ((property.lng - west) % 360 + 360) % 360;
    return offset <= width;
  }
  function filterProperties(properties, state, saved) {
    const words = normalize(state.query).split(/\s+/).filter(Boolean);
    const output = properties.filter(p => {
      const text = normalize([p.city, p.country, p.type, p.region, p.tag].join(' '));
      return (!state.saved || saved.includes(p.id)) && (!state.market || p.country === state.market)
        && (!state.budget || p.price <= Number(state.budget)) && (!state.type || p.type === state.type)
        && inBounds(p, state.bounds)
        && words.every(word => text.includes(word));
    });
    if (state.sort === 'price-asc') output.sort((a, b) => a.price - b.price);
    if (state.sort === 'price-desc') output.sort((a, b) => b.price - a.price);
    return output;
  }
  root.ZorbeckDiscovery = { filterProperties, normalize, inBounds, longitudeNear };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.ZorbeckDiscovery;
})(typeof window !== 'undefined' ? window : globalThis);
