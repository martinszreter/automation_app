# STARTEND

Multi-tenant WhatsApp booking and no-show prevention for restaurants.

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Start services
docker compose up --build

# 3. Run migrations (in a second terminal)
docker compose exec app alembic upgrade head

# 4. Verify
curl http://localhost:8000/health
# → {"status": "healthy"}
```

## Development

```bash
# Run tests
docker compose exec app pytest -v

# Create a new migration after changing models
docker compose exec app alembic revision --autogenerate -m "describe change"
```

## Architecture

- **FastAPI** backend with async PostgreSQL via SQLAlchemy
- **WhatsApp integration** via swappable adapter (mock adapter for development, Meta Cloud API for production)
- **Server-rendered dashboard** with Jinja2 + HTMX (coming soon)
- All guest-facing messages are **German-first** via a template layer

## Agent bus

`bus/` holds the STARTEND Agent Bus V0: one endpoint, one table, six message
types, shared by Claude Code, Cursor/GPT and Grok. It runs inside the existing
n8n agent-report intake rather than as a second reporting path, and a write is
refused with `428` unless the caller read bus state in the last ten minutes.
Contract and node-by-node sources: [`bus/README.md`](bus/README.md). Live view:
`/bus-k4x9m2.html`.

## Portfolio boot scripts

The Railway `portfolio` service is a bare `python:3.12-alpine` image whose start
command writes each internal view into `/srv` and then serves the directory. The
boot scripts used to exist **only** as environment variables (`BOOT_PY`,
`SALES_BOOT_PY`, `TRADEOPS_BOOT_PY`, `NHT_BOOT_PY`, `VIEWS_BOOT_PY`), so they
could not be reviewed, diffed or rolled back.

`boot/views_boot.py` ends that for the views script (`boot5`). **Railway reads it
from this repository**, over raw.githubusercontent.com, on every boot:

```sh
python3 -c "import urllib.request as u; open('/boot5.py','wb').write(
  u.urlopen('https://raw.githubusercontent.com/martinszreter/automation_app/main/boot/views_boot.py').read())" \
  && python3 /boot5.py \
  || { printf "%s" "$VIEWS_BOOT_PY" > /boot5_fallback.py; python3 /boot5_fallback.py || true; }
```

`VIEWS_BOOT_PY` is kept only as that fallback: if the fetch fails, or this file
exits non-zero, the previous script still writes the canon-backed views. Delete
it once a few deploys have run green.

The script writes two kinds of view and logs one `boot5 ok <KEY> <FILE> <BYTES>`
line each:

* **canon-backed** — `STRAT_HTML`, `X_OPS_HTML`, `GROKYWOOD_OPS_HTML`,
  `MOBILE_OPS_HTML`. Read over the canon RW webhook, highest `version` wins.
* **repo-backed** — `BUS_HTML` → `boot/pages/bus-k4x9m2.html`. Static shells that
  fetch their own data client-side, so they belong in git.

Required variables on the service (no endpoint URL is hard-coded — the canon
webhook accepts unauthenticated writes and this repo is public):

| Variable | Purpose |
| --- | --- |
| `CANON_RW_URL` | Canon RW webhook, used to read the canon-backed views |
| `BUS_STATE_URL` | Bus read-state URL, substituted into the bus page at boot |
| `SRV_DIR` | Optional, defaults to `/srv` |
| `REPO_RAW_BASE` | Optional, raw base for `boot/` when pages are not on disk |

Adding a view is a pull request: append to `CANON_VIEWS` or `REPO_VIEWS` in
`boot/views_boot.py`, and for a repo-backed view drop the page in `boot/pages/`.
