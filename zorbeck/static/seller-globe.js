(() => {
  'use strict';
  const element = document.getElementById('property-map');
  if (!element) return;
  const globe = window.ZorbeckGlobe?.create({element, onMove: () => {}, onSelect: () => {}});
  if (!globe) document.getElementById('map-unavailable').hidden = false;
})();
