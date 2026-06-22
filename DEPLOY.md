# Deployment

## Deploy on Railway

1. Create a new project on [Railway](https://railway.app) and connect this repo.
2. Add a **PostgreSQL** plugin — Railway will set `DATABASE_URL` automatically.
3. In the service settings, set the **Custom Build Command** or point the **Dockerfile Path** to `Dockerfile.prod`.
4. Add the remaining environment variables (see `.env.example`):
   - `WHATSAPP_ADAPTER` — `mock` or `meta`
   - `META_WHATSAPP_TOKEN` / `META_PHONE_NUMBER_ID` (only when using `meta` adapter)
5. Deploy. Railway sets `PORT`; the app binds to it automatically. Alembic migrations run on every container start.
