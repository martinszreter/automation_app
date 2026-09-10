(() => {
  'use strict';
  const property = JSON.parse(document.getElementById('property-page-data').textContent);
  const dialog = document.getElementById('register-dialog');
  document.querySelectorAll('[data-register]').forEach(button => button.addEventListener('click', () => {
    ZorbeckRegistration.prepare({ propertyId: property.id, location: property.city });
    dialog.showModal();
    document.getElementById('register-email').focus();
  }));
  dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const r = dialog.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();
  });
})();
