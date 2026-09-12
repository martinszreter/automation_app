(() => {
  'use strict';
  const allowed = ['ivory', 'dusk', 'midnight'];
  let theme = 'ivory';
  try { const stored = localStorage.getItem('zorbeck-appearance-v1'); if (allowed.includes(stored)) theme = stored; } catch (_) { /* Appearance works without storage. */ }
  document.documentElement.dataset.appearance = theme;
  document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('theme-select');
    if (!select) return;
    select.value = theme;
    select.addEventListener('change', () => {
      if (!allowed.includes(select.value)) return;
      document.documentElement.dataset.appearance = select.value;
      try { localStorage.setItem('zorbeck-appearance-v1', select.value); } catch (_) { /* Visit-only preference. */ }
      document.dispatchEvent(new Event('zorbeck:appearance'));
    });
  });
})();
