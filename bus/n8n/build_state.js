// STARTEND AGENT BUS V0 — n8n Code node "Build State" (runOnceForAllItems).
//
// Input: every row of the agent_bus data table (ql12DoJQYQPxxHRf).
// Output: one item, JSON-stringified by "Respond State", containing the three
// blocks the bus page renders plus a short-lived bus_cursor. Reading is what
// mints the write token — that is the whole point of the bus.
//
// The repo copy is the reviewable source of truth. The deployed copy differs in
// exactly one line: __BUS_TOKEN_PEPPER__ is replaced by the real pepper, which
// lives only inside n8n. Never commit the pepper — this repo is public.

const PEPPER = '__BUS_TOKEN_PEPPER__';
const TTL_SECONDS = 600;
const RECENT_LIMIT = 20;
const RETENTION = 500; // rows kept in agent_bus; the brief's floor is 300
const TEAMS = ['CLAUDE_CLAUDECODE', 'GPT_CURSOR', 'GROK_MARKET'];
const TYPES = ['CLAIM', 'DECISION', 'DONE', 'BLOCKED', 'ASK', 'SIGNAL'];

const crypto = require('crypto');

// Keep in sync with classify.js.
const projectKey = (value) => {
  let s = String(value == null ? '' : value).trim().toLowerCase();
  s = s.replace(/^[a-z][a-z0-9+.-]*:\/\//, '').replace(/^www\./, '');
  s = s.replace(/[?#].*$/, '').replace(/\.git$/, '').replace(/\/+$/, '');
  if (s.includes('/')) s = s.split('/').filter(Boolean).pop() || s;
  return s.slice(0, 120);
};

const view = (row) => ({
  id: row.id,
  ts: row.ts || row.createdAt || '',
  team: String(row.team || ''),
  project: String(row.project || ''),
  project_key: String(row.project_key || ''),
  type: String(row.msg_type || '').toUpperCase(),
  what: String(row.what || ''),
  next: String(row.next_step || ''),
  link: String(row.link || ''),
});

const rows = $input.all()
  .map((item) => item.json)
  .filter((row) => row && row.id != null && row.msg_type)
  .sort((a, b) => (parseInt(a.id, 10) || 0) - (parseInt(b.id, 10) || 0));

// Walk oldest -> newest. A DONE closes every earlier open CLAIM on the same
// repo; a DECISION closes every earlier open ASK on the same repo.
const openClaims = [];
const openAsks = [];
for (const row of rows) {
  const type = String(row.msg_type || '').toUpperCase();
  const key = String(row.project_key || projectKey(row.project));
  if (type === 'CLAIM') {
    openClaims.push(row);
  } else if (type === 'DONE') {
    for (let i = openClaims.length - 1; i >= 0; i -= 1) {
      if (String(openClaims[i].project_key || '') === key) openClaims.splice(i, 1);
    }
  } else if (type === 'ASK') {
    openAsks.push(row);
  } else if (type === 'DECISION') {
    for (let i = openAsks.length - 1; i >= 0; i -= 1) {
      if (String(openAsks[i].project_key || '') === key) openAsks.splice(i, 1);
    }
  }
}

// Optional scoping: GET ...?project=automation_app narrows the two open blocks.
const query = ($('Agent Report In').first().json || {}).query || {};
const scope = projectKey(query.project || '');
const scoped = (list) => (scope ? list.filter((row) => String(row.project_key || '') === scope) : list);

const recent = rows.slice(-RECENT_LIMIT).reverse().map(view);
const recentByTeam = {};
for (const message of recent) {
  const team = message.team || 'UNKNOWN';
  if (!recentByTeam[team]) recentByTeam[team] = [];
  recentByTeam[team].push(message);
}

const issuedAt = Math.floor(Date.now() / 1000);
const signature = crypto.createHash('sha256').update(String(issuedAt) + '.' + PEPPER).digest('hex').slice(0, 24);

return [{
  json: {
    ok: true,
    bus: 'STARTEND AGENT BUS V0',
    generated_at: new Date().toISOString(),
    bus_cursor: 'v1.' + issuedAt + '.' + signature,
    cursor_ttl_seconds: TTL_SECONDS,
    scope: scope || null,
    teams: TEAMS,
    types: TYPES,
    retention: RETENTION,
    counts: {
      total: rows.length,
      open_claims: scoped(openClaims).length,
      open_asks: scoped(openAsks).length,
    },
    open_claims: scoped(openClaims).map(view).reverse(),
    open_asks: scoped(openAsks).map(view).reverse(),
    recent: recent,
    recent_by_team: recentByTeam,
  },
}];
