(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  // Owner setup uses a fragment, so the private one-time key is not sent in a
  // URL query, server access log or Referer. It lasts only in this browser tab.
  try {
    const setup = new URLSearchParams(location.hash.slice(1)).get('owner-setup');
    if (setup && /^[A-Za-z0-9_-]{43}$/.test(setup)) {
      sessionStorage.setItem('zorbeck-owner-setup', setup);
      history.replaceState(null,'',location.pathname+location.search);
    }
    if ($('#owner-setup-key')) $('#owner-setup-key').value = sessionStorage.getItem('zorbeck-owner-setup') || '';
  } catch (_) { /* Owner can paste the key if tab storage is unavailable. */ }
  let mePromise;
  function me() {
    if (!mePromise) mePromise = fetch('/api/me', {cache:'no-store'}).then(async response => {
      if (!response.ok) throw new Error('Account services are temporarily unavailable.');
      return response.json();
    });
    return mePromise;
  }
  async function api(path, data, csrf) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 25000);
    try {
      const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body:JSON.stringify(data), signal:controller.signal});
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.ok === false) throw new Error(typeof result.detail === 'string' ? result.detail : result.error || 'We could not save this change. Please try again.');
      return result;
    } catch(error) {
      if (error.name === 'AbortError') throw new Error('The request timed out. Check your account before trying again.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  function internal(path) {
    const url = new URL(path, location.origin);
    if (url.origin !== location.origin || url.username || url.password) throw new Error('The next page could not be opened. Return to your account.');
    return url.href;
  }
  window.ZorbeckAccount = {
    me,
    async saved() { const response = await fetch('/api/saved', {cache:'no-store'}); if (!response.ok) throw new Error('Your account shortlist could not be loaded.'); return response.json(); },
    async save(ids) { const account = await me(); return api('/api/saved', {ids}, account.csrf); }
  };
  document.querySelectorAll('[data-market-form]').forEach(form => form.addEventListener('submit', async event => {
    event.preventDefault();
    if (form.dataset.busy === 'true' || !form.reportValidity()) return;
    const status = form.querySelector('.market-status');
    const button = form.querySelector('button[type="submit"]');
    const data = Object.fromEntries(new FormData(form));
    form.dataset.busy = 'true'; button.disabled = true; status.textContent = 'Saving…'; status.classList.remove('error','success');
    try {
      const result = await api(form.getAttribute('action'), data, data.csrf);
      if (result.recovery_key) {
        $('#recovery-key').textContent = result.recovery_key;
        $('#account-continue').href = internal(result.next_url);
        form.hidden = true; $('#recovery-result').hidden = false;
        mePromise = null;
      } else if (result.checkout_url) {
        const url = new URL(result.checkout_url);
        if (url.protocol !== 'https:' || url.hostname !== 'buy.stripe.com') throw new Error('The secure checkout could not be opened.');
        status.textContent = 'Opening Stripe…'; location.assign(url.href);
      } else if (result.next_url) {
        if (form.getAttribute('action') === '/api/admin/claim') {
          try { sessionStorage.removeItem('zorbeck-owner-setup'); } catch (_) { /* Optional storage. */ }
        }
        status.textContent = 'Saved. Opening…'; location.assign(internal(result.next_url));
      } else {
        status.textContent = result.message || 'Saved.'; status.classList.add('success');
      }
    } catch(error) { status.textContent = error.message; status.classList.add('error'); }
    finally { form.dataset.busy = 'false'; button.disabled = false; }
  }));
  $('#copy-recovery')?.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText($('#recovery-key').textContent); $('#copy-recovery').textContent = 'Copied — store it privately'; }
    catch (_) { $('#copy-recovery').textContent = 'Select and copy the key above'; }
  });
  document.querySelector('[data-account-save]')?.addEventListener('click', async event => {
    const status = $('#property-action-status'), button = event.currentTarget;
    try {
      const account = await me();
      if (!account.user) { location.assign('/login?next='+encodeURIComponent(location.pathname)); return; }
      const saved = await window.ZorbeckAccount.saved();
      const ids = [...new Set([...saved.ids, button.dataset.accountSave])];
      await window.ZorbeckAccount.save(ids);
      button.textContent = 'Saved to your account'; status.textContent = 'You can find this property in your account shortlist.';
    } catch(error) { status.textContent = error.message; }
  });
  document.querySelector('[data-share-property]')?.addEventListener('click', async () => {
    try {
      if (navigator.share) await navigator.share({title:document.title,url:location.origin+location.pathname});
      else { await navigator.clipboard.writeText(location.origin+location.pathname); $('#property-action-status').textContent = 'Property link copied.'; }
    } catch(error) { if (error.name !== 'AbortError') $('#property-action-status').textContent = 'Copy the property address from your browser to share it.'; }
  });

  const upload = $('#photo-upload');
  if (upload) {
    const ids = () => JSON.parse($('#photo-ids').value || '[]');
    function addPreview(id, url) {
      const wrapper = document.createElement('div'); wrapper.className = 'upload-preview'; wrapper.dataset.photo = id;
      const img = document.createElement('img'); img.src = url; img.alt = 'Your property photograph';
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×'; remove.dataset.removePhoto = id; remove.setAttribute('aria-label','Remove photograph');
      wrapper.append(img, remove); $('#upload-previews').append(wrapper);
    }
    async function preparePhoto(file) {
      if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 20*1024*1024) throw new Error('Choose a JPEG, PNG or WebP photo under 20 MB.');
      const bitmap = await createImageBitmap(file);
      const scale = Math.min(1,1600/Math.max(bitmap.width,bitmap.height));
      const canvas = document.createElement('canvas'); canvas.width = Math.round(bitmap.width*scale); canvas.height = Math.round(bitmap.height*scale);
      canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height); bitmap.close();
      return canvas.toDataURL('image/jpeg',0.85).split(',')[1];
    }
    upload.addEventListener('change', async () => {
      const files = Array.from(upload.files || []), status = $('#upload-status');
      if (ids().length + files.length > 3) { status.textContent = 'Choose up to three photographs in total.'; upload.value=''; return; }
      upload.disabled = true; $('#listing-form button[type="submit"]').disabled = true;
      try {
        for (const file of files) {
          status.textContent = 'Preparing and saving your photograph…';
          const content = await preparePhoto(file);
          const result = await api('/api/photos', {content}, $('#listing-form input[name="csrf"]').value);
          $('#photo-ids').value = JSON.stringify([...ids(),result.id]); addPreview(result.id,result.url);
        }
        status.textContent = 'Photographs saved. Preview your property when you’re ready.';
      } catch(error) { status.textContent = error.message; }
      finally { upload.value=''; upload.disabled=false; $('#listing-form button[type="submit"]').disabled=false; }
    });
    $('#upload-previews').addEventListener('click', event => {
      const button = event.target.closest('[data-remove-photo]'); if (!button) return;
      $('#photo-ids').value = JSON.stringify(ids().filter(id=>id!==button.dataset.removePhoto));
      button.closest('.upload-preview').remove();
    });
  }
  const payment = document.querySelector('[data-payment-session]');
  if (payment?.dataset.paymentSession) {
    let tries = 0;
    async function poll() {
      tries++;
      try {
        const response = await fetch('/api/payments/status?session_id='+encodeURIComponent(payment.dataset.paymentSession),{cache:'no-store'});
        if (!response.ok) throw new Error('Sign in to check your payment status in your account.');
        const result = await response.json();
        if (result.status === 'paid') {
          $('#payment-heading').textContent = 'Payment confirmed.';
          $('#payment-message').textContent = result.order.kind === 'smoke' ? 'Your CHF 1 payment check is recorded in your account.' : 'Your property is now featured for 30 days. You can see the placement in your account.';
          return;
        }
        if (result.status !== 'pending') {
          $('#payment-heading').textContent = 'Your payment needs attention.';
          $('#payment-message').textContent = 'Recorded status: '+result.status.replaceAll('_',' ')+'. Check your account or contact support.'; return;
        }
        if (tries < 15) setTimeout(poll,2000);
        else $('#payment-message').textContent = 'Confirmation is taking longer than usual. You can return to your account; the status updates when Stripe confirms the payment. Please check before paying again.';
      } catch(error) { $('#payment-message').textContent=error.message; }
    }
    poll();
  }
})();
