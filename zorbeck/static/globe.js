/* A single orthographic globe, using self-hosted D3 and Natural Earth geography. */
(() => {
  'use strict';
  function create({ element, onMove, onSelect }) {
    const unavailable = document.getElementById('map-unavailable');
    const canvas = document.getElementById('globe-canvas');
    const context = canvas.getContext('2d');
    if (!context || !window.d3?.geoOrthographic) { unavailable.hidden = false; return null; }
    const markers = document.getElementById('globe-markers');
    const coordinate = document.getElementById('globe-coordinate');
    const place = document.getElementById('globe-place');
    const projection = d3.geoOrthographic().clipAngle(90).precision(0.6);
    const path = d3.geoPath(projection, context), graticule = d3.geoGraticule10();
    let lng = 18, lat = 26, zoom = 1, width = 0, height = 0, scale = 0;
    let geography = null, hover = null, selectedId = '', properties = [], markerNodes = [];
    let frame = 0, wheelTimer = 0, activePointers = new Map(), gesture = null;
    const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
    const wrap = n => ((n + 180) % 360 + 360) % 360 - 180;
    const camera = () => ({ lng, lat, scale, width, height });
    function paintPath(object, fill, stroke, lineWidth = 0.5) {
      context.beginPath(); path(object);
      if (fill) { context.fillStyle = fill; context.fill(); }
      if (stroke) { context.strokeStyle = stroke; context.lineWidth = lineWidth; context.stroke(); }
    }
    function draw() {
      frame = 0;
      if (!width || !height) return;
      context.clearRect(0, 0, width, height);
      scale = Math.min(width - 34, height - 50) / 2 * zoom;
      projection.rotate([-lng, -lat]).translate([width / 2, height / 2]).scale(scale);
      const x = width / 2, y = height / 2;
      const dusk = document.documentElement.dataset.appearance === 'dusk';
      const glow = context.createRadialGradient(x, y, scale * 0.94, x, y, scale * 1.08);
      glow.addColorStop(0, '#bfa97b20'); glow.addColorStop(0.45, '#7eaba823'); glow.addColorStop(1, '#7eaba800');
      context.fillStyle = glow; context.beginPath(); context.arc(x, y, scale * 1.08, 0, Math.PI * 2); context.fill();
      const ocean = context.createRadialGradient(x - scale * 0.45, y - scale * 0.55, 0, x, y, scale * 1.2);
      ocean.addColorStop(0, dusk ? '#55564f' : '#354c51'); ocean.addColorStop(0.65, '#243336'); ocean.addColorStop(1, '#0b1316');
      paintPath({ type: 'Sphere' }, ocean, '#bfc9bd65', 0.8);
      paintPath(graticule, null, '#b5c8be20', 0.55);
      if (geography) {
        const land = context.createLinearGradient(x - scale, y - scale, x + scale, y + scale);
        land.addColorStop(0, '#dfd7bd'); land.addColorStop(0.48, '#b5bba6'); land.addColorStop(1, '#748d83');
        geography.features.forEach(feature => paintPath(feature, land, '#3e56554f', 0.6));
        if (hover) paintPath(hover, '#e5c78c66', '#e8ce9b', 0.85);
      }
      const shade = context.createRadialGradient(x - scale * 0.5, y - scale * 0.5, scale * 0.15, x, y, scale);
      shade.addColorStop(0, '#ffffff10'); shade.addColorStop(0.65, '#03101300'); shade.addColorStop(1, '#020a10b3');
      paintPath({ type: 'Sphere' }, shade, '#d5dbc333', 0.8);
      const occupied = [];
      markerNodes.forEach(({ property, node }) => {
        const point = ZorbeckDiscovery.projectOnGlobe(property, camera());
        node.hidden = !point.visible;
        if (!point.visible) return;
        const offsets = [0, -34, 34, -68, 68, -102, 102, -136, 136];
        const offset = offsets.find(dy => point.y + dy > 16 && point.y + dy < height - 16 && !occupied.some(p => Math.abs(p.x - point.x) < 68 && Math.abs(p.y - point.y - dy) < 31)) || 0;
        const yPin = point.y + offset;
        occupied.push({ x: point.x, y: yPin });
        if (offset) {
          context.strokeStyle = '#e2cea57a'; context.lineWidth = 0.8;
          context.beginPath(); context.moveTo(point.x, point.y); context.lineTo(point.x, yPin); context.stroke();
          context.fillStyle = '#efdbb3'; context.beginPath(); context.arc(point.x, point.y, 2, 0, Math.PI * 2); context.fill();
        }
        node.style.transform = `translate(${point.x}px, ${yPin}px) translate(-50%, -50%)`;
      });
      coordinate.textContent = `${Math.abs(lat).toFixed(0)}° ${lat < 0 ? 'S' : 'N'} / ${Math.abs(lng).toFixed(0)}° ${lng < 0 ? 'W' : 'E'}`;
      element.dataset.longitude = lng.toFixed(2);
      element.dataset.latitude = lat.toFixed(2);
      element.dataset.zoom = zoom.toFixed(2);
    }
    function schedule() { if (!frame) frame = requestAnimationFrame(draw); }
    function resize() {
      const nextWidth = element.clientWidth, nextHeight = element.clientHeight;
      if (!nextWidth || !nextHeight) return;
      width = nextWidth; height = nextHeight;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      draw();
    }
    function moved() { hover = null; place.textContent = 'Exploring this side of the world'; draw(); onMove(); }
    function rotate(deltaLng, deltaLat = 0) { lng = wrap(lng + deltaLng); lat = clamp(lat + deltaLat, -80, 80); moved(); }
    function changeZoom(delta) { zoom = clamp(zoom * delta, 0.8, 4); moved(); }
    function focus(nextLng, nextLat, nextZoom = 1, label = 'Worldwide') {
      lng = wrap(nextLng); lat = clamp(nextLat, -80, 80); zoom = clamp(nextZoom, 0.8, 4); hover = null;
      place.textContent = label; resize();
    }
    function setProperties(next, selected, format) {
      properties = next; selectedId = selected;
      const focused = document.activeElement?.dataset.globeProperty;
      markers.replaceChildren();
      markerNodes = properties.map(property => {
        const node = document.createElement('button');
        node.type = 'button'; node.className = 'map-price-pin globe-pin';
        node.dataset.globeProperty = property.id;
        node.classList.toggle('selected', property.id === selectedId);
        node.setAttribute('aria-label', `${property.city}, ${format(property.price)}, illustrative example. Open details.`);
        node.textContent = format(property.price);
        node.addEventListener('click', () => onSelect(property.id));
        markers.append(node);
        return { property, node };
      });
      draw();
      if (focused) markerNodes.find(item => item.property.id === focused && !item.node.hidden)?.node.focus({ preventScroll: true });
    }
    function select(id, pan) {
      selectedId = id;
      markerNodes.forEach(({ property, node }) => node.classList.toggle('selected', property.id === id));
      const property = properties.find(p => p.id === id);
      if (pan && property) focus(property.lng, property.lat, zoom, property.city);
    }
    function startGesture() {
      const points = Array.from(activePointers.values());
      gesture = { points, lng, lat, zoom, moved: false };
    }
    element.addEventListener('pointerdown', event => {
      if (event.target.closest('button') || event.button !== 0) return;
      clearTimeout(wheelTimer);
      activePointers.set(event.pointerId, [event.clientX, event.clientY]);
      element.setPointerCapture(event.pointerId); startGesture();
      element.classList.add('is-dragging'); element.focus({ preventScroll: true });
    });
    element.addEventListener('pointermove', event => {
      if (!activePointers.has(event.pointerId)) {
        if (!geography || event.pointerType === 'touch') return;
        const rect = element.getBoundingClientRect();
        const point = [event.clientX - rect.left, event.clientY - rect.top];
        if (Math.hypot(point[0] - width / 2, point[1] - height / 2) > scale) { if (hover) { hover = null; schedule(); } return; }
        const location = projection.invert(point);
        const next = geography.features.find(feature => d3.geoContains(feature, location));
        if (next !== hover) { hover = next; if (hover) place.textContent = hover.properties.name; schedule(); }
        return;
      }
      activePointers.set(event.pointerId, [event.clientX, event.clientY]);
      const points = Array.from(activePointers.values());
      if (points.length === 2 && gesture.points.length === 2) {
        const distance = p => Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]);
        zoom = clamp(gesture.zoom * distance(points) / Math.max(1, distance(gesture.points)), 0.8, 4);
      } else {
        const dx = points[0][0] - gesture.points[0][0], dy = points[0][1] - gesture.points[0][1];
        const speed = 90 / Math.max(80, scale);
        lng = wrap(gesture.lng - dx * speed); lat = clamp(gesture.lat + dy * speed, -80, 80);
      }
      gesture.moved = true; hover = null; schedule();
    });
    function endGesture(event) {
      if (!activePointers.has(event.pointerId)) return;
      const didMove = gesture?.moved;
      activePointers.delete(event.pointerId);
      if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId);
      if (activePointers.size) startGesture();
      else { gesture = null; element.classList.remove('is-dragging'); if (didMove) moved(); }
    }
    element.addEventListener('pointerup', endGesture);
    element.addEventListener('pointercancel', endGesture);
    element.addEventListener('lostpointercapture', endGesture);
    element.addEventListener('pointerleave', () => { hover = null; schedule(); });
    element.addEventListener('wheel', event => {
      event.preventDefault();
      zoom = clamp(zoom * Math.exp(-event.deltaY * 0.0015), 0.8, 4); schedule();
      clearTimeout(wheelTimer); wheelTimer = setTimeout(moved, 140);
    }, { passive: false });
    element.addEventListener('keydown', event => {
      if (event.target !== element) return;
      const actions = { ArrowLeft: () => rotate(-12), ArrowRight: () => rotate(12), ArrowUp: () => rotate(0, 10), ArrowDown: () => rotate(0, -10), '+': () => changeZoom(1.25), '=': () => changeZoom(1.25), '-': () => changeZoom(0.8) };
      if (actions[event.key]) { event.preventDefault(); actions[event.key](); }
    });
    document.getElementById('globe-left').addEventListener('click', () => rotate(-20));
    document.getElementById('globe-right').addEventListener('click', () => rotate(20));
    document.getElementById('globe-zoom-in').addEventListener('click', () => changeZoom(1.25));
    document.getElementById('globe-zoom-out').addEventListener('click', () => changeZoom(0.8));
    document.addEventListener('zorbeck:appearance', schedule);
    fetch('/static/discovery/world-countries.json').then(response => {
      if (!response.ok) throw Error('Geography unavailable');
      return response.json();
    }).then(data => { geography = data; element.dataset.globeReady = 'true'; schedule(); }).catch(() => { unavailable.hidden = false; });
    resize();
    return { camera, focus, reset: () => focus(18, 26), resize, setProperties, select };
  }
  window.ZorbeckGlobe = { create };
})();
