(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const $$ = selector => Array.from(document.querySelectorAll(selector));
  const properties = JSON.parse($('#property-data').textContent);
  const byId = Object.fromEntries(properties.map(p => [p.id, p]));
  const cards = Object.fromEntries($$('.property-card').map(card => [card.dataset.property, card]));
  const initial = JSON.parse($('#discovery-state').textContent);
  const state = { query: initial.query || '', budget: Number(initial.budget) || 0, type: '', market: '', sort: 'featured', saved: false, bounds: null };
  // Camera extents for shortcuts, not country boundaries or a claim of listing coverage.
  const regions = {
    'China': [[18, 73], [54, 135]], 'Thailand': [[5.5, 97], [20.5, 106]],
    'United States': [[24, -126], [50, -66]], 'Portugal': [[36.8, -9.6], [42.2, -6.1]],
    'Spain': [[35.8, -10], [44, 4.5]], 'Switzerland': [[45.7, 5.8], [47.9, 10.6]],
    'United Arab Emirates': [[22.6, 51.4], [26.1, 56.5]], 'Indonesia': [[-11.5, 94.5], [6, 141.5]]
  };
  const money = value => new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value);
  const shortMoney = value => value >= 1000000 ? `€${(value / 1000000).toFixed(2).replace(/0$/, '')}m` : `€${Math.round(value / 1000)}k`;
  const icon = name => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  let saved = [];
  try { const value = JSON.parse(localStorage.getItem('zorbeck-shortlist-v1') || '[]'); if (Array.isArray(value)) saved = value.filter(id => Object.hasOwn(byId, id)); } catch (_) { /* Device storage is optional. */ }
  let map = null, markers = {}, selectedId = '', current = properties, toastTimer, movingMap = false, mapNeedsFit = false;

  function toast(message) { $('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 2800); }
  function syncSaved() {
    $('#saved-count').textContent = saved.length;
    $$('[data-save]').forEach(button => {
      const isSaved = saved.includes(button.dataset.save);
      button.setAttribute('aria-pressed', String(isSaved));
      button.setAttribute('aria-label', `${isSaved ? 'Remove saved' : 'Save'} ${byId[button.dataset.save].city} example`);
      if (button.classList.contains('detail-save')) button.innerHTML = icon('heart') + (isSaved ? 'Saved on this device' : 'Save example');
    });
  }
  function toggleSaved(id) {
    if (!byId[id]) return;
    const removing = saved.includes(id);
    saved = removing ? saved.filter(value => value !== id) : [...saved, id];
    let persistent = true;
    try { localStorage.setItem('zorbeck-shortlist-v1', JSON.stringify(saved)); } catch (_) { persistent = false; }
    syncSaved();
    toast(removing ? 'Removed from your shortlist' : persistent ? 'Saved to your shortlist on this device' : 'Saved for this visit; device storage is unavailable');
    if (state.saved) render();
  }
  function openDialog(id) {
    const dialog = document.getElementById(id);
    $$('dialog[open]').forEach(open => open.close());
    dialog.showModal();
  }
  function register(property) {
    ZorbeckRegistration.prepare({ propertyId: property?.id || '', location: property ? property.city : state.query || state.market || '', budget: state.budget });
    openDialog('register-dialog');
    setTimeout(() => $('#register-email').focus(), 50);
  }
  function detail(id) {
    const property = byId[id];
    if (!property) return;
    select(id, false);
    $('#detail-content').innerHTML = `<img class="detail-image" src="/static/discovery/${property.image}" alt="${property.imageAlt}" width="800" height="600"><div class="detail-inner"><p class="eyebrow">${property.city.toUpperCase()} · ${property.country.toUpperCase()}</p><h2 id="detail-title">${property.title}</h2><div class="detail-facts"><span>${property.type}</span><span>${property.beds} bedrooms</span><span>${property.area} m²</span></div><div class="detail-price">${money(property.price)}<span>Illustrative price<br>Not an active listing</span></div><p>${property.description}</p><p class="detail-disclosure">Sample property · Illustrative photograph · City-level map location. No availability, ownership rights or investment return has been verified.</p><div class="detail-actions"><button type="button" class="button button-outline detail-save" data-save="${property.id}">${icon('heart')}Save example</button><button type="button" class="button button-dark" data-register-property="${property.id}">Continue to property${icon('arrow')}</button></div></div>`;
    syncSaved(); openDialog('detail-dialog');
  }
  function select(id, pan = true) {
    selectedId = id;
    Object.entries(cards).forEach(([key, card]) => card.classList.toggle('is-selected', key === id));
    Object.entries(markers).forEach(([key, marker]) => {
      marker.getElement()?.querySelector('.map-price-pin')?.classList.toggle('selected', key === id);
      marker.setZIndexOffset(key === id ? 1000 : 0);
    });
    if (pan && map && markers[id]) { moveMap(() => map.panTo(markers[id].getLatLng(), { animate: false })); markers[id].openPopup(); }
  }
  function moveMap(action) {
    movingMap = true;
    try { map.stop(); action(); } finally { movingMap = false; }
  }
  function viewport() {
    const bounds = map.getBounds();
    return { south: bounds.getSouth(), west: bounds.getWest(), north: bounds.getNorth(), east: bounds.getEast() };
  }
  function searchMapArea() {
    if (!map) return;
    state.bounds = viewport(); state.query = ''; state.market = ''; $('#search-input').value = '';
    $('#search-map-area').hidden = true;
    render();
  }
  function onMapMove() {
    if (movingMap) return;
    if ($('#map-auto-search').checked) searchMapArea();
    else {
      $('#search-map-area').hidden = false;
      $('#map-area-status').textContent = 'Map moved. Search this area to update the examples.';
    }
  }
  function fitMap() {
    if (!map) return;
    if (!$('#property-map').clientWidth || !$('#property-map').clientHeight) { mapNeedsFit = true; return; }
    mapNeedsFit = false;
    const region = Object.keys(regions).find(name => ZorbeckDiscovery.normalize(name) === ZorbeckDiscovery.normalize(state.market || state.query));
    moveMap(() => {
      map.invalidateSize({ pan: false });
      if (region) map.fitBounds(regions[region], { padding: [28, 60], animate: false });
      else if (!state.query && !state.saved) map.fitWorld({ animate: false });
      else if (current.length === 1) map.setView([current[0].lat, current[0].lng], 9, { animate: false });
      else if (current.length) map.fitBounds(L.latLngBounds(current.map(p => [p.lat, p.lng])), { padding: [55, 65], maxZoom: 7, animate: false });
    });
    syncMap();
  }
  function syncMap() {
    if (!map) return;
    Object.values(markers).forEach(marker => marker.remove()); markers = {};
    current.forEach(property => {
      const lng = ZorbeckDiscovery.longitudeNear(property.lng, map.getCenter().lng);
      const marker = L.marker([property.lat, lng], {
        icon: L.divIcon({ className: 'map-pin-wrap', html: `<div class="map-price-pin${property.id === selectedId ? ' selected' : ''}">${shortMoney(property.price)}</div>`, iconSize: [72, 32], iconAnchor: [36, 32] }),
        title: `${property.city}: ${money(property.price)}, illustrative example`, keyboard: true
      }).addTo(map);
      const popup = document.createElement('div');
      const heading = document.createElement('strong'); heading.textContent = property.city; popup.append(heading);
      const caption = document.createElement('div'); caption.className = 'map-popup-location'; caption.textContent = `${property.type} · ${money(property.price)} · Example`; popup.append(caption);
      const button = document.createElement('button'); button.type = 'button'; button.className = 'map-popup-button'; button.textContent = 'Explore this example'; button.addEventListener('click', () => detail(property.id)); popup.append(button);
      marker.bindPopup(popup, { closeButton: false, offset: [0, -26], autoPan: false });
      marker.on('click', () => { select(property.id, false); if (window.innerWidth > 680) cards[property.id]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); });
      markers[property.id] = marker;
    });
  }
  function render({ fit = false } = {}) {
    current = ZorbeckDiscovery.filterProperties(properties, state, saved);
    const ids = current.map(p => p.id);
    Object.entries(cards).forEach(([id, card]) => { card.hidden = !ids.includes(id); });
    current.forEach(p => $('#property-grid').append(cards[p.id]));
    $('#empty-state').hidden = current.length > 0;
    $('#results-heading').firstChild.textContent = state.saved ? 'Your saved places' : 'Places worth exploring';
    $('#results-count').textContent = `${current.length} ${current.length === 1 ? 'example' : 'examples'}`;
    const filters = [state.bounds ? 'this map area' : '', state.query, state.market, state.budget ? `up to ${money(state.budget)}` : '', state.type].filter(Boolean);
    $('#results-context').textContent = state.saved ? 'Your shortlist, saved only on this device.' : filters.length ? `Showing examples for ${filters.join(' · ')}` : 'Illustrative properties and prices, not active listings.';
    const area = state.market || (state.bounds ? 'this map area' : 'this search');
    $('#empty-state h3').textContent = state.saved ? 'No saved examples match.' : `No examples in ${area} yet.`;
    $('#empty-state p').textContent = state.saved ? 'Widen the map or filters to find your saved examples.' : 'Live listings are not connected. This preview has eight examples; an empty area does not mean there are no properties for sale.';
    $$('.market-chip').forEach(button => { const active = !state.bounds && !state.query && button.dataset.market === state.market; button.classList.toggle('is-active', active); button.setAttribute('aria-pressed', String(active)); });
    $('#mobile-saved').setAttribute('aria-pressed', String(state.saved)); $('#saved-view').classList.toggle('is-active', state.saved); $('#discover-view').classList.toggle('is-active', !state.saved);
    const count = `${current.length} ${current.length === 1 ? 'example' : 'examples'}`;
    $('#map-area-status').textContent = `${count}${state.bounds ? ' in this area' : state.market ? ' in ' + state.market : ''} · Live listings not connected`;
    if (fit) fitMap(); else syncMap();
  }
  function reset() { Object.assign(state, { query: '', budget: 0, type: '', market: '', saved: false, bounds: null }); $('#search-input').value = ''; $('#budget-filter').value = '0'; $('#type-filter').value = ''; $('#search-map-area').hidden = true; render({ fit: true }); }
  function initializeMap() {
    if (typeof L === 'undefined') { $('#map-unavailable').hidden = false; return; }
    map = L.map('property-map', { zoomControl: false, scrollWheelZoom: true, minZoom: 0, maxZoom: 18, worldCopyJump: true, trackResize: false }).setView([20, 0], 1);
    L.control.zoom({ position: 'bottomleft' }).addTo(map);
    let failures = 0;
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors', maxZoom: 19
    }).addTo(map);
    tiles.on('tileerror', () => { failures++; if (failures > 4) $('#map-unavailable').hidden = false; });
    tiles.on('tileload', () => { failures = 0; $('#map-unavailable').hidden = true; });
    fitMap();
    map.on('moveend', onMapMove);
    L.DomEvent.disableClickPropagation($('.map-topline'));
    L.DomEvent.disableScrollPropagation($('.map-topline'));
    L.DomEvent.disableClickPropagation($('#search-map-area'));
    new ResizeObserver(() => {
      if (!$('#property-map').clientWidth || !$('#property-map').clientHeight) return;
      if (mapNeedsFit) { fitMap(); return; }
      moveMap(() => map.invalidateSize({ pan: false }));
      if (state.bounds && $('#map-auto-search').checked) { state.bounds = viewport(); render(); }
    }).observe($('#map-column'));
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('button'); if (!button) return;
    if (button.hasAttribute('data-save')) toggleSaved(button.dataset.save);
    else if (button.hasAttribute('data-detail')) detail(button.dataset.detail);
    else if (button.hasAttribute('data-register-property')) register(byId[button.dataset.registerProperty]);
    else if (button.hasAttribute('data-register')) register();
    else if (button.hasAttribute('data-open')) openDialog(button.dataset.open);
    else if (button.hasAttribute('data-close')) button.closest('dialog').close();
  });
  $$('dialog').forEach(dialog => dialog.addEventListener('click', event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } }));
  $('#search-form').addEventListener('submit', event => { event.preventDefault(); state.query = $('#search-input').value.trim(); state.budget = Number($('#budget-filter').value); state.type = $('#type-filter').value; state.bounds = null; state.market = ''; $('#search-map-area').hidden = true; render({ fit: true }); });
  ['budget-filter', 'type-filter'].forEach(id => document.getElementById(id).addEventListener('change', () => { state.budget = Number($('#budget-filter').value); state.type = $('#type-filter').value; render(); }));
  $('#sort-filter').addEventListener('change', event => { state.sort = event.target.value; render(); });
  $$('.market-chip').forEach(button => button.addEventListener('click', () => { state.market = button.dataset.market; state.query = ''; state.bounds = null; $('#search-input').value = ''; $('#search-map-area').hidden = true; render({ fit: true }); }));
  $('#reset-filters').addEventListener('click', reset); $('#empty-reset').addEventListener('click', reset);
  $('#mobile-saved').addEventListener('click', () => { const next = !state.saved; reset(); state.saved = next; render({ fit: true }); });
  $('#saved-view').addEventListener('click', () => { reset(); state.saved = true; render({ fit: true }); }); $('#discover-view').addEventListener('click', reset);
  $('#reset-map').addEventListener('click', () => { state.query = ''; state.market = ''; state.bounds = null; $('#search-input').value = ''; $('#search-map-area').hidden = true; render({ fit: true }); });
  $('#search-map-area').addEventListener('click', searchMapArea);
  $('#map-auto-search').addEventListener('change', event => { if (event.target.checked) searchMapArea(); });
  $$('[data-layout]').forEach(button => button.addEventListener('click', () => {
    $('#discovery-split').classList.toggle('list-layout', button.dataset.layout === 'list');
    $$('[data-layout]').forEach(item => item.classList.toggle('is-active', item === button));
    if (map) setTimeout(() => { if ($('#property-map').clientWidth) moveMap(() => map.invalidateSize({ pan: false })); }, 30);
  }));
  $('#mobile-map-toggle').addEventListener('click', () => {
    const mapVisible = $('#discovery-split').classList.toggle('mobile-map');
    $('#discovery-split').classList.remove('list-layout');
    $('#mobile-map-toggle span').textContent = mapVisible ? 'Show properties' : 'Show map';
    if (mapVisible && !map) initializeMap();
    if (mapVisible) setTimeout(() => { if (map) { if (mapNeedsFit) fitMap(); else moveMap(() => map.invalidateSize({ pan: false })); } $('#discovery-split').scrollIntoView({block: 'start', behavior: 'smooth'}); }, 50);
  });
  fetch('/static/discovery/photo-credits.json').then(response => response.json()).then(credits => {
    credits.forEach(credit => {
      const p = document.createElement('p'), link = document.createElement('a');
      link.href = credit.source; link.target = '_blank'; link.rel = 'noopener'; link.textContent = credit.photographer;
      p.append(link, document.createTextNode(` · ${credit.subject} · ${credit.license}`)); $('#photo-credits').append(p);
    });
  }).catch(() => { $('#photo-credits').textContent = 'Photo attribution is temporarily unavailable.'; });
  syncSaved();
  const hasInitialSearch = Boolean(state.query || state.budget);
  if (hasInitialSearch) render();
  if (window.innerWidth > 680) initializeMap();
})();
