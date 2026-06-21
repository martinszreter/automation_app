# STARTEND — WhatsApp Booking & No-Show Prevention

## Stack
- **Backend:** Python 3.12 + FastAPI
- **Database:** PostgreSQL 15 (via Docker)
- **Dashboard:** Server-rendered with Jinja2 + HTMX
- **WhatsApp:** Meta Cloud API behind a swappable adapter interface (mock adapter for development)
- **Migrations:** Alembic

## Folder Structure
```
app/
  api/          # FastAPI route modules
  core/         # Config, settings, dependencies
  db/           # SQLAlchemy models, session management
  messaging/    # WhatsApp adapter interface + implementations
  templates/
    messages/   # Guest-facing message templates (German-first)
tests/          # pytest test suite
alembic/        # Database migrations
```

## Conventions

### Message Language Rule (CRITICAL)
ALL guest-facing messages MUST be German-first. Messages are loaded from the
`app/templates/messages/` layer — never hard-code message text inline in Python code.
English will be added later as a second language pass.

### Code Style
- Type hints on all function signatures
- Pydantic models for request/response schemas
- async endpoints throughout
- One router per domain (bookings, tenants, guests)

## Run Commands
```bash
# Start everything
docker compose up --build

# Run tests
docker compose exec app pytest

# Create a migration
docker compose exec app alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec app alembic upgrade head
```

## Environment Variables
See `.env.example` for required variables. Copy to `.env` before running.
