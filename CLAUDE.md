# StillWaterGrace

Automated faith-and-family social media content platform.
Python/FastAPI backend, React/Tailwind dashboard, Celery workers, PostgreSQL, Redis.

## Running the Stack

```bash
docker compose up -d        # Start all 6 services
docker compose down          # Stop everything
docker compose down -v       # Stop and wipe database
docker compose logs api -f   # Tail API logs
docker compose exec api python manage.py show-calendar  # Run CLI commands
```

Services: db (Postgres 16), redis, api (:8000), celery-worker, celery-beat, dashboard (:5175)

## Project Structure

```
api/                  FastAPI routes (content, analytics, monetization, dashboard)
core/
  config.py           Pydantic settings from .env
  content/            Claude API generator, Jinja2 prompts, series manager, calendar
  images/             Leonardo.ai, Unsplash, PIL processor (4 branded layouts)
  posting/            Instagram, Facebook, TikTok clients
  scraper/            Bible API, Google Trends, Reddit, hashtags, competitors
database/
  models.py           SQLAlchemy ORM — 13 tables, 9 enums, Base class
  session.py          Engine, SessionLocal, get_db/get_db_dependency
  migrations/         Alembic (env.py, versions/)
dashboard/            React 18 + Vite + Tailwind (port 5175 in Docker)
prompts/              8 Jinja2 prompt templates
workers/              Celery app, daily_tasks, posting_tasks
scripts/              entrypoint.sh (Docker startup)
tests/                pytest (64 tests)
docs/                 Branded HTML documentation
manage.py             CLI: init-db, seed, generate-verse, generate-content, show-calendar, etc.
```

## Key Technical Details

- Config: `core/config.py` — Pydantic BaseSettings reads from `.env`
- DB models: `database/models.py` — all tables use `Base` from `DeclarativeBase`
- Migrations: Alembic runs automatically on container start (API only)
- API proxy: Dashboard Vite config proxies `/api` to the backend
- Mock fallback: `dashboard/src/lib/api.js` falls back to mock data when backend is down

## Brand Design

- Colors: cream `#FFF8F0`, gold `#D4A853`, green `#2D4A3E`, white `#FAFAFA`
- Fonts: Georgia (heading), Calibri (body), Georgia Italic (accent)
- Watermark: `@stillwatergrace`
- PIL layouts: verse_card, minimal_quote, series_banner, bold_statement

## Testing

```bash
pytest                       # Run all 64 tests
pytest --cov=core            # With coverage
```

## Environment

- `.env` has all API keys — never commit secrets
- Docker overrides DATABASE_URL and REDIS_URL to use service names (db, redis)
- Local dev uses localhost defaults from .env
