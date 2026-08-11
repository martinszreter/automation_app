# nieczytaj.pl

Single-file, dependency-free Node 22 app: agreguje polskie RSS-y, klastruje tematy między serwisami, ranguje HOT (liczba źródeł × świeżość) i renderuje polską stronę. Poprzednio źródło żyło w env varach Railway (`APP_SRC`..`APP_SRC4`) sklejanych w start command — teraz jest tutaj.

Endpointy: `GET /` (strona główna), `GET /{city}` (warszawa, krakow, wroclaw, trojmiasto, poznan, slask), `GET /health`, `GET /api/top`, `POST /api/summaries` (wymaga nagłówka `x-push-token`), plus `GET /reklama` i `/regulamin`.

Env vary (wszystkie opcjonalne, ustawiane w Railway): `PUSH_TOKEN`, `REFRESH_MIN`, `STRIPE_BANER7`, `STRIPE_BANER30`, `STRIPE_BOX7`, `STRIPE_BOX30`, `STRIPE_KAF7`, `STRIPE_KAF30`.

Deploy: Railway project **startend** / service **nieczytaj** — w ustawieniach serwisu Root Directory musi być ustawione na `nieczytaj`, start: `node server.js`.

## Known issues

- Pętla przekierowań dla `HEAD /`: handler `/` sprawdza `req.method === 'GET'`, więc żądanie `HEAD /` spada do domyślnego `302 Location: /` — klient podążający za redirectami (np. uptime-monitor używający HEAD) wpada w nieskończoną pętlę HEAD → 302 → HEAD. Dotyczy też HEAD na `/{city}` i `/reklama`. Do naprawy osobno.
- Cennik jest nadpisywany dwukrotnie na końcu pliku (`[ads] cennik` i `[ads] cennik (tail)`) — obowiązuje wartość z ostatniego bloku (tail).
