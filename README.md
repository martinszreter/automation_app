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

