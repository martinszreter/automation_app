(function (root) {
  'use strict';
  function destination(path, origin) {
    if (typeof path !== 'string' || !path) throw new Error('Your search was saved, but we could not open the next page. Return to the map to continue.');
    const url = new URL(path, origin);
    const allowed = url.pathname === '/search' || /^\/properties\/[a-z0-9]+(?:-[a-z0-9]+)*$/.test(url.pathname);
    if (url.origin !== origin || url.username || url.password || !allowed) throw new Error('Your search was saved, but we could not open the next page. Return to the map to continue.');
    return url;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { destination };
  if (!root.document) return;
  const form = document.getElementById('register-form');
  if (!form) return;
  const button = form.querySelector('button[type="submit"]');
  const label = document.getElementById('register-submit-label');
  const status = document.getElementById('registration-status');
  const receiptKey = 'zorbeck-registration-receipt-v1';
  function prepare(options = {}) {
    form.elements.property_id.value = options.propertyId || '';
    form.elements.city.value = options.location || '';
    form.elements.budget_max.value = options.budget || '';
    status.textContent = ''; status.className = 'form-status'; button.disabled = false;
    label.textContent = options.propertyId ? 'Continue to property' : 'Save search and continue';
    document.getElementById('register-intro').textContent = options.propertyId
      ? 'Register your interest, then continue to this property’s dedicated example page. It is free to explore.'
      : 'Join Zorbeck early access, then continue to property examples for your location and budget.';
  }
  root.ZorbeckRegistration = { prepare, destination };
  try {
    const receipt = JSON.parse(sessionStorage.getItem(receiptKey) || 'null');
    sessionStorage.removeItem(receiptKey);
    if (receipt && receipt.path === location.pathname + location.search && Date.now() - receipt.createdAt < 300000) {
      const confirmation = document.getElementById('registration-confirmation');
      if (confirmation) confirmation.hidden = false;
    }
  } catch (_) { /* Navigation works when optional session storage is unavailable. */ }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (button.disabled || !form.reportValidity()) return;
    const data = Object.fromEntries(new FormData(form)); data.consent = form.elements.consent.checked;
    button.disabled = true; label.textContent = 'Saving…'; status.className = 'form-status'; status.textContent = 'Saving your search…';
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 18000);
    try {
      const response = await fetch('/api/early-access', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data), signal: controller.signal });
      const result = await response.json().catch(() => null);
      if (!response.ok || result?.ok !== true) throw new Error(result?.error || 'We could not save your search. Please try again.');
      const next = destination(result.next_url, location.origin);
      try { sessionStorage.setItem(receiptKey, JSON.stringify({ path: next.pathname + next.search, createdAt: Date.now() })); } catch (_) { /* Confirmation storage is optional and never contains the email. */ }
      status.className = 'form-status success'; status.textContent = data.property_id ? 'Saved. Opening your property details…' : 'Saved. Opening your matching examples…';
      label.textContent = 'Opening…';
      location.assign(next.href);
    } catch (error) {
      status.className = 'form-status error';
      status.textContent = error.name === 'AbortError' ? 'The request timed out. Please try again.' : error.message;
      label.textContent = form.elements.property_id.value ? 'Continue to property' : 'Save search and continue'; button.disabled = false;
    } finally { clearTimeout(timer); }
  });
})(typeof window !== 'undefined' ? window : globalThis);
