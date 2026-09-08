// Shared helpers for the e2e suite.
const SRV_BASE = process.env.SRV_BASE || 'http://127.0.0.1:8098';
const APP_BASE = process.env.APP_BASE || 'http://127.0.0.1:8000';

/** Collect console errors and page errors; the quality bar is zero. */
function watchConsole(page) {
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  return errors;
}

/** Cumulative Layout Shift as the browser measured it since navigation. */
async function layoutShift(page) {
  return page.evaluate(() => new Promise((resolve) => {
    let total = 0;
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) if (!entry.hadRecentInput) total += entry.value;
    });
    observer.observe({ type: 'layout-shift', buffered: true });
    setTimeout(() => { observer.disconnect(); resolve(total); }, 300);
  }));
}

module.exports = { SRV_BASE, APP_BASE, watchConsole, layoutShift };
