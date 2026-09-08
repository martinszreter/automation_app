# nieczytaj.pl

Single-file, dependency-free Node 22 app: agreguje polskie RSS-y, klastruje tematy między serwisami, ranguje HOT (liczba źródeł × świeżość) i renderuje polską stronę. Poprzednio źródło żyło w env varach Railway (`APP_SRC`..`APP_SRC4`) sklejanych w start command — teraz jest tutaj.

Endpointy: `GET /` (strona główna), `GET /{city}` (warszawa, krakow, wroclaw, trojmiasto, poznan, slask), `GET /health`, `GET /api/top`, `POST /api/summaries` (wymaga nagłówka `x-push-token`), plus `GET /reklama` i `/regulamin`.

Env vary (wszystkie opcjonalne, ustawiane w Railway): `PUSH_TOKEN`, `REFRESH_MIN`, `STRIPE_BANER7`, `STRIPE_BANER30`, `STRIPE_BOX7`, `STRIPE_BOX30`, `STRIPE_KAF7`, `STRIPE_KAF30`.

Deploy: Railway project **startend** / service **nieczytaj** — w ustawieniach serwisu Root Directory musi być ustawione na `nieczytaj`, start: `node server.js`. Build/start/healthcheck dla tego katalogu pinuje `railway.json` (RAILPACK, `node server.js`, `/health`) — bez niego Railway bierze `railway.toml` z korzenia repo i próbuje zbudować pythonowy `Dockerfile`, co kończy się `requirements.txt: not found`.

## LIESNICHT (tenant DE)

Ten sam `server.js` obsługuje drugi tenant: **LIESNICHT** (niemiecka kopia, ceny w CHF, `/werbung`, `/impressum`, `/datenschutz`). Tenant wybiera nagłówek `Host` (`*liesnicht*`), a env `TENANT=liesnicht` przypina DE dla każdego żądania — tak działa osobny serwis Railway **liesnicht** (Root Directory `nieczytaj`, ten sam `railway.json`, własny zestaw `STRIPE_*`).

- Lokalnie: `TENANT=liesnicht PORT=8080 node server.js` → `/` z niemieckimi stringami.
- Walidator: `npm run validate` (uruchamia serwer z `TENANT=liesnicht`, sprawdza DE home, `/werbung` ze `STRIPE_*`, `/impressum`, `/health`; „validator passes" = OK). Testy host-tenant: `npm test`.
- DNS: `www.liesnicht.ch` (i `www.liesnicht.de`) są dodane jako custom domains serwisu **liesnicht** w Railway; rekord **CNAME `www.liesnicht.ch` → domena serwisu Railway** ustawia Marcin u rejestratora (Railway pokazuje target w Settings → Domains). Adres serwisowy: `liesnicht-production.up.railway.app`.

## Known issues

- Pętla przekierowań dla `HEAD /`: handler `/` sprawdza `req.method === 'GET'`, więc żądanie `HEAD /` spada do domyślnego `302 Location: /` — klient podążający za redirectami (np. uptime-monitor używający HEAD) wpada w nieskończoną pętlę HEAD → 302 → HEAD. Dotyczy też HEAD na `/{city}` i `/reklama`. Do naprawy osobno.
- Cennik jest nadpisywany dwukrotnie na końcu pliku (`[ads] cennik` i `[ads] cennik (tail)`) — obowiązuje wartość z ostatniego bloku (tail).
