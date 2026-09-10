(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const $$ = selector => Array.from(document.querySelectorAll(selector));
  const properties = JSON.parse($('#property-data').textContent);
  const byId = Object.fromEntries(properties.map(p => [p.id, p]));
  const cards = Object.fromEntries($$('.property-card').map(card => [card.dataset.property, card]));
  const state = { query: '', budget: 0, type: '', market: '', sort: 'featured', saved: false };
  const money = value => new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value);
  const shortMoney = value => value >= 1000000 ? `€${(value / 1000000).toFixed(2).replace(/0$/, '')}m` : `€${Math.round(value / 1000)}k`;
  const icon = name => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  let saved = [];
  try { const value = JSON.parse(localStorage.getItem('zorbeck-shortlist-v1') || '[]'); if (Array.isArray(value)) saved = value.filter(id => Object.hasOwn(byId, id)); } catch (_) { /* Device storage is optional. */ }
  let map = null, markers = {}, selectedId = '', current = properties, toastTimer;

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
    $('#register-city').value = property ? property.city : state.query || state.market || '';
    $('#register-budget').value = state.budget || '';
    openDialog('register-dialog');
    setTimeout(() => $('#register-email').focus(), 50);
  }
  function detail(id) {
    const property = byId[id];
    if (!property) return;
    select(id, false);
    $('#detail-content').innerHTML = `<img class="detail-image" src="/static/discovery/${property.image}" alt="${property.imageAlt}" width="800" height="600"><div class="detail-inner"><p class="eyebrow">${property.city.toUpperCase()} · ${property.country.toUpperCase()}</p><h2 id="detail-title">${property.title}</h2><div class="detail-facts"><span>${property.type}</span><span>${property.beds} bedrooms</span><span>${property.area} m²</span></div><div class="detail-price">${money(property.price)}<span>Illustrative price<br>Not an active listing</span></div><p>${property.description}</p><p class="detail-disclosure">Sample property · Illustrative photograph · City-level map location. No availability, ownership rights or investment return has been verified.</p><div class="detail-actions"><button type="button" class="button button-outline detail-save" data-save="${property.id}">${icon('heart')}Save example</button><button type="button" class="button button-dark" data-register-property="${property.id}">Register this search${icon('arrow')}</button></div></div>`;
    syncSaved(); openDialog('detail-dialog');
  }
  function select(id, pan = true) {
    selectedId = id;
    Object.entries(cards).forEach(([key, card]) => card.classList.toggle('is-selected', key === id));
    Object.entries(markers).forEach(([key, marker]) => {
      marker.getElement()?.querySelector('.map-price-pin')?.classList.toggle('selected', key === id);
      marker.setZIndexOffset(key === id ? 1000 : 0);
    });
    if (pan && map && markers[id]) { map.panTo(markers[id].getLatLng()); markers[id].openPopup(); }
  }
  function fitMap() {
    if (!map) return;
    map.invalidateSize();
    if (!current.length) { map.setView([30, 5], 2); return; }
    if (current.length === 1) { map.setView([current[0].lat, current[0].lng], 9); return; }
    map.fitBounds(L.latLngBounds(current.map(p => [p.lat, p.lng])), { padding: [55, 65], maxZoom: 7 });
  }
  function syncMap() {
    if (!map) return;
    Object.values(markers).forEach(marker => marker.remove()); markers = {};
    current.forEach(property => {
      const marker = L.marker([property.lat, property.lng], {
        icon: L.divIcon({ className: 'map-pin-wrap', html: `<div class="map-price-pin${property.id === selectedId ? ' selected' : ''}">${shortMoney(property.price)}</div>`, iconSize: [72, 32], iconAnchor: [36, 32] }),
        title: `${property.city}: ${money(property.price)}, illustrative example`, keyboard: true
      }).addTo(map);
      const popup = document.createElement('div');
      const heading = document.createElement('strong'); heading.textContent = property.city; popup.append(heading);
      const caption = document.createElement('div'); caption.className = 'map-popup-location'; caption.textContent = `${property.type} · ${money(property.price)} · Example`; popup.append(caption);
      const button = document.createElement('button'); button.type = 'button'; button.className = 'map-popup-button'; button.textContent = 'Explore this example'; button.addEventListener('click', () => detail(property.id)); popup.append(button);
      marker.bindPopup(popup, { closeButton: false, offset: [0, -26] });
      marker.on('click', () => { select(property.id, false); if (window.innerWidth > 680) cards[property.id]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); });
      markers[property.id] = marker;
    });
  }
  function render() {
    current = ZorbeckDiscovery.filterProperties(properties, state, saved);
    const ids = current.map(p => p.id);
    Object.entries(cards).forEach(([id, card]) => { card.hidden = !ids.includes(id); });
    current.forEach(p => $('#property-grid').append(cards[p.id]));
    $('#empty-state').hidden = current.length > 0;
    $('#results-heading').firstChild.textContent = state.saved ? 'Your saved places' : 'Places worth exploring';
    $('#results-count').textContent = `${current.length} ${current.length === 1 ? 'example' : 'examples'}`;
    const filters = [state.query, state.market, state.budget ? `up to ${money(state.budget)}` : '', state.type].filter(Boolean);
    $('#results-context').textContent = state.saved ? 'Your shortlist, saved only on this device.' : filters.length ? `Showing examples for ${filters.join(' · ')}` : 'Illustrative properties and prices, not active listings.';
    $('#empty-state h3').textContent = state.saved ? 'Your shortlist starts here.' : 'No examples match yet.';
    $('#empty-state p').textContent = state.saved ? 'Tap the heart on a property to save it on this device.' : 'Try another location or widen your budget. This preview contains eight illustrative properties.';
    $$('.market-chip').forEach(button => { const active = button.dataset.market === state.market; button.classList.toggle('is-active', active); button.setAttribute('aria-pressed', String(active)); });
    $('#mobile-saved').setAttribute('aria-pressed', String(state.saved)); $('#saved-view').classList.toggle('is-active', state.saved); $('#discover-view').classList.toggle('is-active', !state.saved);
    syncMap(); fitMap();
  }
  function reset() { Object.assign(state, { query: '', budget: 0, type: '', market: '', saved: false }); $('#search-input').value = ''; $('#budget-filter').value = '0'; $('#type-filter').value = ''; render(); }
  function initializeMap() {
    if (typeof L === 'undefined') { $('#map-unavailable').hidden = false; return; }
    map = L.map('property-map', { zoomControl: false, scrollWheelZoom: false, minZoom: 2, maxZoom: 18, worldCopyJump: true }).setView([37.5, 12], 3);
    L.control.zoom({ position: 'bottomleft' }).addTo(map);
    let failures = 0;
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors', maxZoom: 19
    }).addTo(map);
    tiles.on('tileerror', () => { failures++; if (failures > 4) $('#map-unavailable').hidden = false; });
    tiles.on('tileload', () => { failures = 0; $('#map-unavailable').hidden = true; });
    syncMap();
    // The initial European view makes the local detail legible. Fit-all is explicit.
    if (window.innerWidth > 680) map.setView([43, 1], 4);
    new ResizeObserver(() => map.invalidateSize()).observe($('#map-column'));
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
  $('#search-form').addEventListener('submit', event => { event.preventDefault(); state.query = $('#search-input').value.trim(); state.budget = Number($('#budget-filter').value); state.type = $('#type-filter').value; render(); });
  ['budget-filter', 'type-filter'].forEach(id => document.getElementById(id).addEventListener('change', () => { state.budget = Number($('#budget-filter').value); state.type = $('#type-filter').value; render(); }));
  $('#sort-filter').addEventListener('change', event => { state.sort = event.target.value; render(); });
  $$('.market-chip').forEach(button => button.addEventListener('click', () => { state.market = button.dataset.market; state.query = ''; $('#search-input').value = ''; render(); }));
  $('#reset-filters').addEventListener('click', reset); $('#empty-reset').addEventListener('click', reset);
  $('#mobile-saved').addEventListener('click', () => { const next = !state.saved; reset(); state.saved = next; render(); });
  $('#saved-view').addEventListener('click', () => { reset(); state.saved = true; render(); }); $('#discover-view').addEventListener('click', reset);
  $('#reset-map').addEventListener('click', fitMap);
  $$('[data-layout]').forEach(button => button.addEventListener('click', () => {
    $('#discovery-split').classList.toggle('list-layout', button.dataset.layout === 'list');
    $$('[data-layout]').forEach(item => item.classList.toggle('is-active', item === button));
    if (map) setTimeout(() => map.invalidateSize(), 30);
  }));
  $('#mobile-map-toggle').addEventListener('click', () => {
    const mapVisible = $('#discovery-split').classList.toggle('mobile-map');
    $('#discovery-split').classList.remove('list-layout');
    $('#mobile-map-toggle span').textContent = mapVisible ? 'Show properties' : 'Show map';
    if (mapVisible && !map) initializeMap();
    if (mapVisible) setTimeout(() => { fitMap(); $('#discovery-split').scrollIntoView({block: 'start', behavior: 'smooth'}); }, 50);
  });
  $('#register-form').addEventListener('submit', async event => {
    event.preventDefault(); const form = event.target; if (!form.reportValidity()) return;
    const button = form.querySelector('button[type=submit]'), status = $('#registration-status');
    const data = Object.fromEntries(new FormData(form)); data.consent = form.elements.consent.checked;
    button.disabled = true; status.className = 'form-status'; status.textContent = 'Saving your registration…';
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 18000);
    try {
      const response = await fetch('/api/early-access', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data), signal: controller.signal });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'We could not save your registration. Please try again.');
      status.className = 'form-status success'; status.textContent = result.message;
      button.textContent = 'Registration saved'; form.reset();
    } catch (error) { status.className = 'form-status error'; status.textContent = error.name === 'AbortError' ? 'The request timed out. Please try again.' : error.message; button.disabled = false; }
    finally { clearTimeout(timer); }
  });
  fetch('/static/discovery/photo-credits.json').then(response => response.json()).then(credits => {
    credits.forEach(credit => {
      const p = document.createElement('p'), link = document.createElement('a');
      link.href = credit.source; link.target = '_blank'; link.rel = 'noopener'; link.textContent = credit.photographer;
      p.append(link, document.createTextNode(` · ${credit.subject} · ${credit.license}`)); $('#photo-credits').append(p);
    });
  }).catch(() => { $('#photo-credits').textContent = 'Photo attribution is temporarily unavailable.'; });
  syncSaved(); if (window.innerWidth > 680) initializeMap();
})();
