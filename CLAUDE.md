# StillWaterGrace

Automated faith-and-family social media content platform.
Python/FastAPI backend, React/Tailwind dashboard, Celery workers, PostgreSQL (Supabase), Redis.

## Current Status (2026-03-29)

**LIVE** — Content auto-generating and posting via Celery beat.
14 posts/week (2/day), morning feed posts + evening branded reels.

### What's Working
- Full content pipeline: Claude API generates text, Unsplash images, branded HTML reels, ElevenLabs TTS narration
- **Branded reel pipeline**: 3 visual styles (scripture, bold, story) auto-selected by content type
  - HTML templates rendered via Playwright → FFmpeg concat → MP4 with TTS + mood-matched music
  - All reels use brand design system (cream/gold/green, Georgia font, linen texture)
  - Narration delayed to start on verse frame (hook plays with music only)
- **2 posts/day schedule**:
  - Morning 10 AM: Feed post (4 scripture singles + 3 carousels per week)
  - Evening 7 PM: Reel (marriage monday, daily verse, parenting, conviction quotes, faith friday, encouragement)
- Bible verses via API.Bible NIV translation (BIBLE_API_KEY in .env)
- Pixabay mood-matched background music (8 tracks, mood-tagged by content type)
- 9 rotating narration voices via ElevenLabs TTS
- Audio mixing: narration full volume, music ducked to 8%, fade at last 0.5s
- Images + reels upload to Cloudflare R2
- Dashboard at :5175 for approve/reject workflow with reel video preview
- Instagram posting verified working (photo, carousel, reel)
- Facebook cross-posting with Facebook-optimized captions
- Instagram token auto-refresh: weekly Celery task
- Devotional PDF generator: themed 7-day branded PDFs
- ConvertKit email integration
- TikTok cross-posting (sandbox tested, production app pending review)
- Insights dashboard: recommendations, performance breakdown, competitor activity
- Competitor content scraper: Mon/Wed/Fri Celery tasks
- Analytics recovery: daily refresh at 2 PM EST
- Content dedup: prevents duplicate generation
- **Cleanup system**: weekly Celery task + `manage.py purge-local` cleans temp files, preserves music library
- **R2 cleanup on delete**: content deletion now removes R2 objects + posting logs

### Known Issues to Fix
- **R2 public dev URL** is rate-limited — need custom domain for production
- **WeasyPrint on Windows** requires MSYS2 GTK DLLs on PATH (`C:\msys64\mingw64\bin`)
- **WeasyPrint in Docker** needs `libpango-1.0-0 libgdk-pixbuf2.0-0 libffi-dev` system packages

### Next Steps (Priority Order)
1. Add `instagram_basic` permission in Meta Business Manager (enables competitor scraping)
2. TikTok production app approval (submitted 2026-03-06)
3. ManyChat setup at 100 followers
4. Style 4: Cinematic reels (Unsplash bg + branded overlay) for special occasions
5. Instagram Stories posting (story_text already generated)
6. Custom R2 domain (when scaling)

## Running the Stack

```bash
docker compose up -d        # Start all services
docker compose down          # Stop everything
docker compose down -v       # Stop and wipe database
docker compose logs api -f   # Tail API logs
docker compose exec api python manage.py show-calendar  # View calendar
docker compose exec api python manage.py generate-week  # Generate week
docker compose exec api python manage.py purge-local    # Clean temp files
```

Services: redis, api (:8000), celery-worker, celery-beat, dashboard (:5175)
Database: Supabase cloud Postgres (no local db container)

## Project Structure

```
api/                  FastAPI routes (content, analytics, insights, monetization, dashboard)
core/
  config.py           Pydantic settings from .env (extra="ignore")
  content/            Claude API generator, Jinja2 prompts, series manager, calendar
  rendering/          Playwright HTML-to-image renderer, branded reel video renderer
  devotional/         Themed devotional PDF generator
  email/              ConvertKit API client
  audio/              ElevenLabs TTS narration + Pixabay/ElevenLabs music + FFmpeg mixing
  images/             Unsplash client, PIL processor, image pipeline (orchestrates rendering + R2 upload)
  posting/            Instagram (publish_reel, publish_photo, publish_carousel), Facebook, TikTok
  analytics/          Performance analyzer (rules engine), Instagram insights collector
  scraper/            Bible API (API.Bible NIV), Google Trends, Reddit, hashtags, competitor content
database/
  models.py           SQLAlchemy ORM — 14 tables, 9 enums, Base class
  session.py          Engine, SessionLocal, get_db/get_db_dependency
  migrations/         Alembic (env.py, versions/)
dashboard/            React 18 + Vite + Tailwind (port 5175 in Docker)
prompts/              9 Jinja2 prompt templates
templates/images/     HTML/CSS templates for scripture singles, carousels, and reels (3 reel styles)
templates/devotional/ WeasyPrint HTML/CSS for devotional PDF
workers/              Celery app, daily_tasks, posting_tasks
audio/                Pixabay + ElevenLabs music (reusable), narration cache (per-content)
output/               Temp reels, mixed audio (cleaned weekly)
manage.py             CLI: generate-week, purge-local, token-status, etc.
```

## Reel Pipeline (NEW)

Three branded reel styles, auto-selected by content type:

| Style | Look | Content Types |
|-------|------|--------------|
| **scripture** | Green bg, verse highlights, cream reflection | daily_verse, daily_devotional, prayer_prompt, gratitude |
| **bold** | Cream bg, massive text, green CTA | conviction_quote, fill_in_blank, this_or_that, christian_quote |
| **story** | Cream hook → green narrative → verse → CTA | faith_friday, encouragement, marriage_monday, parenting_wednesday |

Pipeline: `reel_renderer.py` → Playwright renders HTML frames → FFmpeg concat with TTS narration + music → MP4 → R2 upload

- Frame templates: `templates/images/reel_*.html` + `base.css`
- Music: Pixabay tracks in `audio/px_*.mp3` (mood-matched), ElevenLabs fallback
- Narration: ElevenLabs TTS, cached in `audio/narration/`, delayed by 3s for hook frame
- Style routing: `STYLE_MAP` in `core/rendering/reel_renderer.py`

## Weekly Schedule

| Day | 10 AM (Feed) | 7 PM (Reel) |
|-----|-------------|-------------|
| Mon | Scripture single (hopeful) | Marriage Monday (story) |
| Tue | Carousel (reflective) | Daily verse (scripture) |
| Wed | Scripture single (reflective) | Parenting Wednesday (story) |
| Thu | Carousel (hopeful) | Conviction quote (bold) |
| Fri | Scripture single (challenging) | Faith Friday (story) |
| Sat | Carousel (celebratory) | Encouragement (story) |
| Sun | Scripture single (reflective) | Daily verse (scripture) |

## Key Technical Details

- Config: `core/config.py` — Pydantic BaseSettings, `extra="ignore"` for leftover env vars
- DB: Supabase cloud Postgres — DATABASE_URL has URL-encoded password (% must be doubled for Alembic)
- Migrations: Alembic runs automatically on container start (API only)
- API proxy: Dashboard Vite config proxies `/api` to the backend
- Mock fallback: `dashboard/src/lib/api.js` falls back to mock data when backend is down
- Bible API: API.Bible NIV (BIBLE_API_KEY in .env), falls back to bible-api.com WEB
- Content deletion: deletes PostingLog → GeneratedImage → R2 objects → GeneratedContent
- Reel pipeline: HTML templates → Playwright PNG → FFmpeg concat + TTS + music → MP4
- Cleanup: weekly Celery task (Sun 4 AM) purges temp files, preserves music + recent narration (<30d)
- **imagegen integration**: `C:\imagegen\src` mounted at `/imagegen-src` in Docker API container
  - `POST /content/{id}/ai-image` — generates fal.ai images alongside Unsplash
  - `POST /content/{id}/swap-reel` — re-renders reel with AI background

## Brand Design

- Colors: cream `#FFF8F0`, gold `#D4A853`, green `#2D4A3E`, white `#FAFAFA`
- Fonts: Georgia/Caladea (heading), Calibri (body), Georgia Italic (accent)
- Watermark: `@stillwatergrace`
- Linen texture overlay on all branded frames
- Feed: scripture singles (1080x1080) + carousels (3 slides)
- Reels: 1080x1920, 3 styles (scripture/bold/story), all using brand CSS

## Testing

```bash
pytest                       # Run all 131 tests
pytest --cov=core            # With coverage
```

## Environment

- `.env` has all API keys — never commit secrets
- Docker overrides DATABASE_URL and REDIS_URL to use service names
- Active APIs: Anthropic, ElevenLabs, Unsplash, API.Bible, Instagram/Meta, Cloudflare R2, fal.ai
- Cancelled: Leonardo.ai (removed from codebase)

## Meta/Facebook Setup (IMPORTANT)

See `docs/meta-setup-guide.html` for full walkthrough. Key gotchas:

- **FACEBOOK_PAGE_ID must be the API Page ID from Business Manager**, NOT the profile ID in the URL
- Page must be in a Meta Business Portfolio or `me/accounts` returns empty
- Token auto-refresh: Celery beat task runs weekly, CLI: `manage.py token-status [--refresh]`
