const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const vm = require('node:vm');
const { destination } = require('../static/registration.js');

const origin = 'https://zorbeck.example';
const source = readFileSync(require.resolve('../static/registration.js'), 'utf8');

test('registration accepts only local search and property destinations', () => {
  assert.equal(destination('/properties/lisbon-01', origin).href, origin + '/properties/lisbon-01');
  assert.equal(destination('/search?location=Lisbon&budget=400000', origin).search, '?location=Lisbon&budget=400000');
  for (const path of [undefined, '', 'https://external.invalid/search', '//external.invalid/search',
    'javascript:alert(1)', '/checkout', '/properties/../checkout', '/properties/',
    'https://user:pass@zorbeck.example/search']) assert.throws(() => destination(path, origin));
});

// Unit harness for the submission handler; no browser or network calls.
function registration({ response, storageUnavailable = false, path = '/', receipt = null } = {}) {
  const values = { property_id: '', city: '', budget_max: '', email: 'example@example.com', consent: true };
  const elements = Object.fromEntries(Object.entries(values).map(([name, value]) => [name, { value, checked: value === true }]));
  const button = { disabled: false };
  const nodes = Object.fromEntries(['register-submit-label', 'registration-status', 'register-intro', 'registration-confirmation']
    .map(id => [id, { textContent: '', hidden: true }]));
  let submit;
  const form = {
    elements, reportValidity: () => true, querySelector: () => button,
    addEventListener: (name, handler) => { if (name === 'submit') submit = handler; }
  };
  nodes['register-form'] = form;
  const calls = [], navigations = [], stored = [];
  const context = {
    URL, AbortController, Date, setTimeout, clearTimeout,
    document: { getElementById: id => nodes[id] },
    location: { origin, pathname: path.split('?')[0], search: path.includes('?') ? '?' + path.split('?')[1] : '', assign: url => navigations.push(url) },
    sessionStorage: {
      getItem: () => { if (storageUnavailable) throw new Error('blocked'); return receipt && JSON.stringify(receipt); },
      removeItem: () => { receipt = null; },
      setItem: (key, value) => { if (storageUnavailable) throw new Error('blocked'); stored.push(JSON.parse(value)); }
    },
    FormData: class { constructor() { return Object.entries(elements).map(([name, field]) => [name, field.value]); } },
    fetch: async (url, options) => { calls.push({ url, data: JSON.parse(options.body) }); return await response; }
  };
  context.window = context;
  vm.runInNewContext(source, context);
  return { prepare: context.ZorbeckRegistration.prepare, submit: () => submit({ preventDefault() {} }),
    button, nodes, calls, navigations, stored, currentReceipt: () => receipt };
}

test('selected property waits for successful persistence before navigation', async () => {
  let complete;
  const response = new Promise(resolve => { complete = resolve; });
  const run = registration({ response });
  run.prepare({ propertyId: 'marbella-01', location: 'Marbella', budget: 600000 });
  const pending = run.submit();
  assert.equal(run.button.disabled, true);
  assert.deepEqual(run.navigations, []);
  assert.equal(run.calls[0].data.property_id, 'marbella-01');
  assert.equal(run.calls[0].data.city, 'Marbella');
  assert.equal(run.calls[0].data.consent, true);
  complete({ ok: true, json: async () => ({ ok: true, next_url: '/properties/marbella-01' }) });
  await pending;
  assert.deepEqual(run.navigations, [origin + '/properties/marbella-01']);
  assert.equal(run.stored[0].path, '/properties/marbella-01');
  assert.deepEqual(Object.keys(run.stored[0]).sort(), ['createdAt', 'path']);
});

test('general registration clears property interest and works without session storage', async () => {
  const run = registration({ storageUnavailable: true, response: {
    ok: true, json: async () => ({ ok: true, next_url: '/search?location=Lisbon&budget=400000' })
  } });
  run.prepare({ propertyId: 'marbella-01', location: 'Marbella' });
  run.prepare({ location: 'Lisbon', budget: 400000 });
  await run.submit();
  assert.equal(run.calls[0].data.property_id, '');
  assert.equal(run.calls[0].data.budget_max, 400000);
  assert.deepEqual(run.navigations, [origin + '/search?location=Lisbon&budget=400000']);
});

test('failed saves and unsafe destinations keep the visitor on the form', async () => {
  for (const response of [
    { ok: false, json: async () => ({ ok: false, error: 'Please retry.' }) },
    { ok: true, json: async () => ({ ok: false }) },
    { ok: true, json: async () => ({ ok: true, next_url: 'https://external.invalid/search' }) },
    { ok: true, json: async () => { throw new Error('Not JSON'); } }
  ]) {
    const run = registration({ response });
    await run.submit();
    assert.deepEqual(run.navigations, []);
    assert.deepEqual(run.stored, []);
    assert.equal(run.button.disabled, false);
    assert.equal(run.nodes['registration-status'].className, 'form-status error');
  }
});

test('confirmation is used once and only for the matching recent destination', () => {
  for (const [receipt, visible] of [
    [{ path: '/properties/lisbon-01', createdAt: Date.now() }, true],
    [{ path: '/properties/marbella-01', createdAt: Date.now() }, false],
    [{ path: '/properties/lisbon-01', createdAt: Date.now() - 360000 }, false]
  ]) {
    const run = registration({ path: '/properties/lisbon-01', receipt });
    assert.equal(run.nodes['registration-confirmation'].hidden, !visible);
    assert.equal(run.currentReceipt(), null);
  }
});
