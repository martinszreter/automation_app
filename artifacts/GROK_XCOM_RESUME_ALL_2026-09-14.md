# GROK / X.COM — RESUME ALL + R1-R3 FIRE

Date: 2026-09-14
Decision: Marcin GO, 14 Sep 2026 (issue #76)
Lane: 1 X.COM — Reply Engine `HNUpMDQaYREs3HOl`
Code: `app/services/xautopilot_reply.py`, `app/api/x_autopilot.py`, `tests/test_xautopilot_reply.py`

## What was ratified

1. **Resume Alex / Filip / NYC origins.** All three flagship origins draft again.
2. **Kill the experiment footer.** No post and no reply carries it any more.
3. **R1-R3 under every flagship root.** The Reply Engine owes exactly three
   replies under each flagship root — no more, no fewer.
4. **Grokywood Imagine only.** No other image or video source may be attached.
5. **Stranger replies BAN.** The engine replies only under our own accounts.

## How each rule is enforced

The policy is deterministic — no model call — so the engine runs it on every
root and every candidate before anything reaches X. Reply vetoes use the same
shape as the post judge and land in the same veto ledger, so the reason sits
next to the reply in one place.

| Rule | Mechanism | Veto code |
| --- | --- | --- |
| Origins resumed | `ORIGINS` = ALEX, FILIP, NYC, all active unless `XA_PAUSED_ORIGINS` names one | `origin_paused` |
| Footer killed | `strip_experiment_footer()` removes it; carrying one is a hard fail | `experiment_footer` |
| R1-R3 | `plan_reply_pack()` / `coverage()`; a fourth reply is refused | `pack_complete` |
| Grokywood Imagine only | `check_media_source()` — only Grok(ywood) Imagine passes | `media_source` |
| Stranger BAN | `check_stranger_reply()` against `XA_FLAGSHIP_HANDLES` | `stranger_reply` |

### Origins

ALEX and FILIP are persona origins, NYC is a place origin. They are **resumed in
code**: the default state is drafting, and holding one back is an operator lever
(`XA_PAUSED_ORIGINS=filip`), not a code change. Account handles are deployment
config (`XA_FLAGSHIP_HANDLES`) and never enter this public repository.

### The experiment footer

Stripped in every shape it was posted in: its own trailing line
(`— Experiment 7/30`, `#experiment`, `-- Experiment, Tag 4`), a dash/pipe tail
on the last line (`… | experiment 12/30`), and a trailing parenthetical
(`… (experiment)`). A post that discusses an experiment in its body is
untouched — only a short trailing segment counts as a footer.

Both happen: the footer is stripped from the text **and** the candidate is
vetoed, so the ledger records that a drafting engine is still appending it.

### The R1-R3 pack

`plan_reply_pack(root, existing)` returns the slots still owed and the id each
one hangs under. The pack reads as one thread: **R1 answers the root, R2 answers
R1, R3 answers R2** (`CHAIN_UNDER_PREVIOUS`). A reply's id only exists after it
is posted, so the engine re-plans between replies to get a true chain; a slot
whose parent id is not known yet falls back to the root, which still satisfies
"under the flagship root".

Slots already posted are read oldest-first when the engine did not label them,
so a pack that was interrupted mid-way resumes at the right slot instead of
restarting at R1.

`coverage(roots, replies)` is the fire-everywhere view: how many roots are
complete, how many are blocked, and how many replies the resume still owes.

### Stranger replies

The ban **fails closed**. A reply is vetoed when the root has no author handle,
when the author is not in `XA_FLAGSHIP_HANDLES`, *and* when that variable is
unset at all — an unconfigured engine replies to nobody rather than to anybody.
An unknown origin is treated the same way: not a flagship root, no reply.

## Endpoints (all behind `X-Judge-Key`, as the post judge is)

| Endpoint | Purpose |
| --- | --- |
| `POST /x-autopilot/replies/plan` | Which of R1-R3 each root owes; which roots are blocked |
| `POST /x-autopilot/replies/judge` | Pick the reply to post under one root, or name the veto |
| `GET /x-autopilot/replies/origins` | The origins drafting right now |

`/replies/plan` request: `{"roots": [{id, author, origin, text, posted_at}], "replies": [{id, root_id, slot, posted_at}]}`
→ `{engine, slots, active_origins, roots: [{root_id, origin, posted, missing: [{slot, in_reply_to}], blocked, complete}], roots_total, roots_complete, roots_blocked, missing_total}`

`/replies/judge` request: `{root, profile, candidates, recent_posts, existing_replies, media}`
→ `{engine, slots, best: {text, slot, in_reply_to, score}, reports, vetoes_recorded}`

The `best.text` is already footer-free, so the engine posts what it is given.

## Environment

Two new variables, both env-only and neither a secret:

| Variable | Meaning |
| --- | --- |
| `XA_FLAGSHIP_HANDLES` | Our own X handles, comma-separated. Unset = every reply vetoed. |
| `XA_PAUSED_ORIGINS` | Origins to hold back (`alex`, `filip`, `nyc`). Empty = all three draft. |

**Action for the operator:** set `XA_FLAGSHIP_HANDLES` on the Railway service to
the three flagship accounts. Until it is set, the Reply Engine posts nothing —
that is the ban working, not a bug.

## Verification

`tests/test_xautopilot_reply.py` — 44 tests, all green, covering every footer
shape, the fail-closed ban, the media allow-list, pack planning and resumption,
the fourth-reply refusal, and the three endpoints including their key check.
Full suite: 440 passed (`test_migrations` needs the CI Postgres service).

## Still owned by the n8n side

This repository holds the policy and the lane the engine calls. Scheduling,
the X credentials, and the actual posting stay in workflow `HNUpMDQaYREs3HOl`;
this pack is the contract that workflow has to satisfy.
