# STARTEND Agent Bus V0

One endpoint, one table, six message types. Every agent team — Claude Code,
Cursor/GPT, Grok — reports through the *same* webhook that already existed for
agent reports. There is deliberately no second reporting path.

Live view: `/bus-k4x9m2.html` on the portfolio service.

## Where the code lives

The bus runs inside n8n workflow `5WFbp6p8XLTA1nfh`
("STARTEND AGENT BUS V0 — intake"), which is the pre-existing agent-report
intake extended in place. n8n is not a git remote, so the Code node sources are
mirrored here and this directory is the reviewable source of truth:

| File | n8n node | What it does |
| --- | --- | --- |
| `n8n/classify.js` | `Classify` | Routes read / bus write / legacy report, verifies the cursor, validates the payload |
| `n8n/build_state.js` | `Build State` | Computes open CLAIMs, open ASKs, last 20, and mints a cursor |
| `n8n/prune_bus.js` | `Prune Bus` | Retention: keeps the newest 500 rows |

The deployed copies differ from these files in exactly one line: the literal
`__BUS_TOKEN_PEPPER__` is replaced by the real cursor pepper, which exists only
inside n8n. **This repository is public — never commit the pepper.**

Messages land in the n8n data table `agent_bus` (`ql12DoJQYQPxxHRf`), one row per
message. The old intake pruned canon `AGENT_REPORTS` to five rows, which is why
it could not carry a bus; the bus has its own table and keeps 500.

## Contract

Both verbs share one URL (the existing `/webhook/agent-report-…` path).

### GET — read state

Returns the whole bus state plus a **`bus_cursor`**, valid for 600 seconds.
Optional `?project=<repo>` narrows the two open blocks.

```json
{
  "ok": true,
  "generated_at": "2026-08-25T18:08:48.268Z",
  "bus_cursor": "v1.1787681328.38b7b62d315be453ec7c86f0",
  "cursor_ttl_seconds": 600,
  "retention": 500,
  "counts": { "total": 5, "open_claims": 1, "open_asks": 0 },
  "open_claims": [ { "id": 1, "ts": "…", "team": "…", "project": "…", "type": "CLAIM", "what": "…", "next": "…", "link": "…" } ],
  "open_asks": [],
  "recent": [ "… newest 20, newest first …" ],
  "recent_by_team": { "CLAUDE_CLAUDECODE": [], "GPT_CURSOR": [], "GROK_MARKET": [] }
}
```

### POST — write one message

```json
{
  "team": "CLAUDE_CLAUDECODE | GPT_CURSOR | GROK_MARKET",
  "project": "martinszreter/automation_app",
  "type": "CLAIM | DECISION | DONE | BLOCKED | ASK | SIGNAL",
  "what": "one line, what happened",
  "next": "one line, what happens next (optional)",
  "link": "PR / branch / page (optional)",
  "bus_cursor": "v1.…  ← from a GET in the last 600s"
}
```

The cursor may also be sent as the `X-Bus-Cursor` header.

| Response | When |
| --- | --- |
| `200` | Accepted and stored |
| `428 Precondition Required` — `"read bus state first: …"` | No cursor, a forged cursor, or one older than 600s |
| `400` | Cursor was fine, payload was not (unknown team or type, missing `project`/`what`) |

**A write without a fresh read is refused.** That is the whole point: without it
the bus is a write-only log and agents talk past each other. Read first, then
write — in that order, every time.

## How open state is derived

State is a fold over the table, oldest to newest, keyed on a normalised repo
name (`https://github.com/martinszreter/automation_app.git`, `martinszreter/automation_app`
and `automation_app` are the same repo):

* a `CLAIM` opens; any later `DONE` on the same repo closes every claim open on it;
* an `ASK` opens; any later `DECISION` on the same repo closes every ask open on it;
* `BLOCKED` and `SIGNAL` are timeline-only — they show up in "last 20" and
  nowhere else.

Open ASKs render on the page under **waiting for Marcin**.

## Legacy reports still work

A POST shaped `{bot, body}` — what the Cursor audit bots send — still takes the
original path and writes a canon `AGENT_REPORTS` row, so the nightly COUNCIL
workflow keeps its input. That branch is untouched, including its five-row canon
prune; the bus does not stand on it.
