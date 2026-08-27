# Which pages live here, and which only look like they do

`app/static/` is served by `app/api/public.py`. Some of these files are the
real thing; others are placeholders that the Railway start command replaces
before uvicorn boots.

The service that serves `www.startend.ch` starts with:

```sh
printf "%s" "$HOME_PY" > /tmp/home.py; python3 /tmp/home.py || echo "canon fetch failed - serving repo homepage"
alembic upgrade head && exec uvicorn app.main:app ...
```

`$HOME_PY` ("canon boot") writes page HTML from canon into `app/static/`,
overwriting whatever the repo shipped. Editing a canon-owned file here has
**no effect in production** — the boot overwrites it on the next deploy.

| Route         | Source           | Canon key        |
| ------------- | ---------------- | ---------------- |
| `/`           | canon boot       | `HOMEPAGE_HTML`  |
| `/apps/`      | canon boot       | `APPS_HTML`      |
| `/agents/`    | canon boot       | `AGENTS_HTML`    |
| `/grokywood/` | canon boot       | `GROKYWOOD_HTML` |
| `/terms/`     | canon boot       | `TERMS_HTML`     |
| `/privacy/`   | canon boot       | `PRIVACY_HTML`   |
| `/impressum/` | canon boot       | `IMPRESSUM_HTML` |
| `/x-autopilot/` | **this repo**  | —                |
| `/thanks.html`  | **this repo**  | —                |

Only `x-autopilot/` and `thanks.html` are edited here. `index.html` and
`grokywood/index.html` are kept as fallbacks for the `canon fetch failed`
branch of the start command; `apps/`, `agents/`, `terms/`, `privacy/` and
`impressum/` have no repo fallback at all and exist only after boot (the
generic `/{page}/` route in `public.py` picks them up).

To change a canon-owned page, change the canon entry — not the file here.
