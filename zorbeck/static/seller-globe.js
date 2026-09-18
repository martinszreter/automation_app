(() => {
  'use strict';
  const element = document.getElementById('property-map');
  if (!element) return;
  const globe = window.ZorbeckGlobe?.create({element, onMove: () => {}, onSelect: () => {}});
  if (!globe) {
    document.getElementById('map-unavailable').hidden = false;
    return;
  }
  if (window.ResizeObserver) {
    const observer = new ResizeObserver(() => globe.resize());
    observer.observe(element);
  } else {
    window.addEventListener('resize', () => globe.resize());
  }
})();
