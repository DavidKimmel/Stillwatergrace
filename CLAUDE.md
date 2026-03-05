# StillWaterGrace

Automated faith-and-family social media content platform.
Python/FastAPI backend, React/Tailwind dashboard, Celery workers, PostgreSQL, Redis.

## Current Status (2026-03-05)

**LIVE** — First week of content generated, approved, and auto-posting via Celery beat.
Content #29 (Jeremiah 29:11) posted as reel to Instagram. Next post: #34 Thu 7 AM EST.

### What's Working
- Full content pipeline: Claude API generates text, Unsplash images, Ken Burns reels, ElevenLabs TTS narration
- 10 rotating male narration voices (George, Daniel, James, Barry, Hardwood, Sakky Ford, Connery, Matthew, Oliver Silk, Cillian)
- Narration-aware reel duration: auto-extends up to 30s, drops narration for very long verses
- 3 reel presentation styles (classic, quick, cinematic) rotating for feed variety
- Audio mixing: narration full volume, music ducked to 8%, fade at last 0.5s
- Images + reels upload to Cloudflare R2
- Dashboard at :5175 for approve/reject workflow (AUTO_APPROVE=false)
- Celery beat posts approved content at scheduled EST times
- Instagram posting verified working
- Facebook cross-posting: auto-posts alongside Instagram with Facebook-optimized captions
- Instagram token auto-refresh: weekly Celery task, CLI `python manage.py token-status`
- All 18 weekly content slots generate (carousel + viral formats fixed)

### Known Issues to Fix
- **R2 public dev URL** is rate-limited — need custom domain for production (low priority at current volume)

### Next Steps (Priority Order)
1. TikTok cross-posting (need account + API setup)
2. Devotional PDF generator
3. Email list setup (ConvertKit/SendGrid)
4. Custom R2 domain (when scaling)

## Running the Stack

```bash
docker compose up -d        # Start all 6 services
docker compose down          # Stop everything
docker compose down -v       # Stop and wipe database
docker compose logs api -f   # Tail API logs
docker compose exec api python manage.py show-calendar  # Run CLI commands
docker compose exec api python manage.py generate-week  # Generate week (text + images + reels)
docker compose exec api python manage.py test-render    # Quick test reel render
```

Services: db (Postgres 16), redis, api (:8000), celery-worker, celery-beat, dashboard (:5175)

## Project Structure

```
api/                  FastAPI routes (content, analytics, monetization, dashboard)
core/
  config.py           Pydantic settings from .env (extra="ignore")
  content/            Claude API generator, Jinja2 prompts, series manager, calendar
  audio/              ElevenLabs TTS narration + Mixkit music + FFmpeg fallback
  images/             Unsplash client, PIL processor (6 overlay styles), reel generator (Ken Burns)
  posting/            Instagram (publish_reel, publish_photo, publish_carousel), Facebook, TikTok
  scraper/            Bible API (~100 curated verses), Google Trends, Reddit, hashtags
database/
  models.py           SQLAlchemy ORM — 13 tables, 9 enums, Base class
  session.py          Engine, SessionLocal, get_db/get_db_dependency
  migrations/         Alembic (env.py, versions/)
dashboard/            React 18 + Vite + Tailwind (port 5175 in Docker)
prompts/              8 Jinja2 prompt templates
workers/              Celery app, daily_tasks, posting_tasks
audio/                Mixkit royalty-free tracks (gitignored), narration cache (gitignored)
manage.py             CLI: generate-week, test-render, generate-audio, show-calendar, etc.
```

## Key Technical Details

- Config: `core/config.py` — Pydantic BaseSettings, `extra="ignore"` for leftover env vars
- DB models: `database/models.py` — all tables use `Base` from `DeclarativeBase`
- Migrations: Alembic runs automatically on container start (API only)
- API proxy: Dashboard Vite config proxies `/api` to the backend
- Mock fallback: `dashboard/src/lib/api.js` falls back to mock data when backend is down
- Leonardo removed — enum kept in DB for compat, all code deleted
- Reel pipeline: Unsplash bg -> Ken Burns zoompan -> transparent PNG overlay composite -> TTS + music mix
- FFmpeg: eof_action=repeat (overlay), amix duration=longest (audio), -t for duration cap
- Deleting content requires deleting GeneratedImage rows first (FK constraint)

## Brand Design

- Colors: cream `#FFF8F0`, gold `#D4A853`, green `#2D4A3E`, white `#FAFAFA`
- Fonts: Georgia (heading), Calibri (body), Georgia Italic (accent)
- Watermark: `@stillwatergrace`
- Feed overlay styles: bold_text (primary), dark_hero (alternate), bible_page (daily_verse)
- Unsplash stock photos: people allowed, dedup by tracking used photo IDs

## Testing

```bash
pytest                       # Run all 64 tests
pytest --cov=core            # With coverage
```

## Environment

- `.env` has all API keys — never commit secrets
- Docker overrides DATABASE_URL and REDIS_URL to use service names (db, redis)
- Local dev uses localhost defaults from .env
- Active APIs: Anthropic, ElevenLabs ($5/mo), Unsplash, Instagram/Meta, Cloudflare R2
- Cancelled: Leonardo.ai (removed from codebase)

## Meta/Facebook Setup (IMPORTANT)

See `docs/meta-setup-guide.html` for full walkthrough. Key gotchas:

- **FACEBOOK_PAGE_ID must be the API Page ID from Business Manager**, NOT the profile ID in the URL
  - URL `profile.php?id=61552254632726` is WRONG — that's the NPE profile ID
  - Business Manager > Settings > Pages shows the correct ID (e.g., `1071328066057500`)
- Page must be in a Meta Business Portfolio or `me/accounts` returns empty
- "Manage everything on your Page" use case needed for `pages_manage_posts` permission
- Token auto-refresh: Celery beat task runs weekly, CLI: `manage.py token-status [--refresh]`
