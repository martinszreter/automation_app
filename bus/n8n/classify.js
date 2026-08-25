// STARTEND AGENT BUS V0 — n8n Code node "Classify" (runOnceForAllItems).
//
// Lives in the existing intake workflow "AGENT REPORTS — intake"
// (n8n 5WFbp6p8XLTA1nfh), first node after the webhook. It is the single
// router for the one and only reporting endpoint:
//
//   mode=read    no body            -> read-state branch (GET)
//   mode=bus     bus-shaped body    -> bus write branch (needs a fresh cursor)
//   mode=legacy  {bot, body}        -> the pre-existing AGENT_REPORTS canon write
//
// The repo copy is the reviewable source of truth. The deployed copy differs in
// exactly one line: __BUS_TOKEN_PEPPER__ is replaced by the real pepper, which
// lives only inside n8n. Never commit the pepper — this repo is public.

const PEPPER = '__BUS_TOKEN_PEPPER__';
const TTL_SECONDS = 600;
const FUTURE_SKEW_SECONDS = 60;
const TEAMS = ['CLAUDE_CLAUDECODE', 'GPT_CURSOR', 'GROK_MARKET'];
const TYPES = ['CLAIM', 'DECISION', 'DONE', 'BLOCKED', 'ASK', 'SIGNAL'];

const crypto = require('crypto');
const sign = (iat) => crypto.createHash('sha256').update(String(iat) + '.' + PEPPER).digest('hex').slice(0, 24);

// Normalises a project reference to a comparable repo key, so that
// "automation_app", "martinszreter/automation_app" and
// "https://github.com/martinszreter/automation_app.git" all close each other's
// CLAIMs. Keep in sync with build_state.js.
const projectKey = (value) => {
  let s = String(value == null ? '' : value).trim().toLowerCase();
  s = s.replace(/^[a-z][a-z0-9+.-]*:\/\//, '').replace(/^www\./, '');
  s = s.replace(/[?#].*$/, '').replace(/\.git$/, '').replace(/\/+$/, '');
  if (s.includes('/')) s = s.split('/').filter(Boolean).pop() || s;
  return s.slice(0, 120);
};

const clean = (value, max) => String(value == null ? '' : value).replace(/\s+/g, ' ').trim().slice(0, max);

const req = $input.first().json || {};
const body = req.body && typeof req.body === 'object' ? req.body : {};
const query = req.query && typeof req.query === 'object' ? req.query : {};
const headers = req.headers && typeof req.headers === 'object' ? req.headers : {};

const filled = (key) => body[key] !== undefined && body[key] !== null && String(body[key]).trim() !== '';
const busShape = ['team', 'project', 'type', 'what', 'next', 'link', 'bus_cursor'].some(filled);
const legacyShape = filled('bot') || filled('body');

if (!busShape && !legacyShape) {
  return [{ json: { mode: 'read' } }];
}
if (!busShape) {
  return [{ json: { mode: 'legacy' } }];
}

// ---- bus write: a fresh cursor is non-negotiable -------------------------
const nowSec = Math.floor(Date.now() / 1000);
const token = clean(body.bus_cursor || headers['x-bus-cursor'] || query.bus_cursor, 120);
const parsed = /^v1\.(\d{10,})\.([a-f0-9]{24})$/.exec(token);

let tokenOk = false;
let tokenError = '';
if (!token) {
  tokenError = 'read bus state first: no bus_cursor supplied';
} else if (!parsed) {
  tokenError = 'read bus state first: malformed bus_cursor';
} else if (sign(parsed[1]) !== parsed[2]) {
  tokenError = 'read bus state first: bus_cursor is not a cursor this bus issued';
} else if (parseInt(parsed[1], 10) - nowSec > FUTURE_SKEW_SECONDS) {
  tokenError = 'read bus state first: bus_cursor issued in the future';
} else if (nowSec - parseInt(parsed[1], 10) > TTL_SECONDS) {
  tokenError = 'read bus state first: bus_cursor expired after ' + TTL_SECONDS + 's';
} else {
  tokenOk = true;
}

const team = clean(body.team, 40).toUpperCase();
const type = clean(body.type, 20).toUpperCase();
const project = clean(body.project, 120);
const what = clean(body.what, 600);
const nextStep = clean(body.next, 600);
const link = clean(body.link, 400);

const fieldErrors = [];
if (TEAMS.indexOf(team) === -1) fieldErrors.push('team must be one of ' + TEAMS.join(' | '));
if (TYPES.indexOf(type) === -1) fieldErrors.push('type must be one of ' + TYPES.join(' | '));
if (!project) fieldErrors.push('project is required');
if (!what) fieldErrors.push('what is required');

// A stale cursor outranks field errors: the caller has to go read the bus
// before it can learn anything useful about its own payload anyway.
if (!tokenOk) {
  return [{ json: { mode: 'bus', accept: 'no', status: 428, error: tokenError } }];
}
if (fieldErrors.length) {
  return [{ json: { mode: 'bus', accept: 'no', status: 400, error: fieldErrors.join('; ') } }];
}

return [{
  json: {
    mode: 'bus',
    accept: 'yes',
    status: 200,
    bus: 'v1',
    ts: new Date().toISOString(),
    team: team,
    project: project,
    project_key: projectKey(project),
    msg_type: type,
    what: what,
    next_step: nextStep,
    link: link,
  },
}];
