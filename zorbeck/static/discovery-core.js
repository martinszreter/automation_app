(function (root) {
  'use strict';
  function normalize(value) { return String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
  function filterProperties(properties, state, saved) {
    const words = normalize(state.query).split(/\s+/).filter(Boolean);
    const output = properties.filter(p => {
      const text = normalize([p.city, p.country, p.type, p.region, p.tag].join(' '));
      return (!state.saved || saved.includes(p.id)) && (!state.market || p.country === state.market)
        && (!state.budget || p.price <= Number(state.budget)) && (!state.type || p.type === state.type)
        && words.every(word => text.includes(word));
    });
    if (state.sort === 'price-asc') output.sort((a, b) => a.price - b.price);
    if (state.sort === 'price-desc') output.sort((a, b) => b.price - a.price);
    return output;
  }
  root.ZorbeckDiscovery = { filterProperties, normalize };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.ZorbeckDiscovery;
})(typeof window !== 'undefined' ? window : globalThis);
