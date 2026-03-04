# StillWaterGrace

Automated faith-and-family social media content platform. Generates Bible-based posts with branded images, animated reels, and multi-platform captions — then posts them on a schedule.

Built with Python/FastAPI, React/Tailwind, Celery, PostgreSQL, Redis, and Docker.

## What It Does

1. **Generates content** — Claude AI writes hooks, captions (short/medium/long), hashtags, story text, reel scripts, and Facebook variations from Bible verses and trending topics
2. **Creates images** — Leonardo.ai or Unsplash backgrounds with 5 branded PIL overlay styles (bible page, dark hero, bottom band, center box, story)
3. **Produces reels** — FFmpeg assembles animated verse-reveal videos (1080x1920, 30fps)
4. **Stores in the cloud** — All images and videos upload to Cloudflare R2 with public URLs
5. **Manages a calendar** — 18 posts/week across 7 content types with morning/noon/evening slots
6. **Dashboard for review** — Approve or reject content, preview images in a lightbox, copy captions
7. **Posts automatically** — Instagram, Facebook, and TikTok clients (Instagram API connected)

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- API keys (see Environment Setup below)

### 1. Clone and configure

```bash
git clone https://github.com/DavidKimmel/Stillwatergrace.git
cd Stillwatergrace
cp .env.example .env
```

Edit `.env` and add your API keys. At minimum you need:

| Key | Required For | How to Get |
|-----|-------------|------------|
| `ANTHROPIC_API_KEY` | Content generation | [console.anthropic.com](https://console.anthropic.com/) |
| `UNSPLASH_ACCESS_KEY` | Background images | [unsplash.com/developers](https://unsplash.com/developers) |

Optional but recommended:

| Key | Required For | How to Get |
|-----|-------------|------------|
| `LEONARDO_API_KEY` | AI-generated images | [leonardo.ai](https://leonardo.ai/) |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram posting | Meta Developer Dashboard |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Instagram posting | Meta Developer Dashboard |
| `CLOUDFLARE_R2_ACCESS_KEY` | Cloud image storage | [cloudflare.com/r2](https://www.cloudflare.com/developer-platform/r2/) |
| `CLOUDFLARE_R2_SECRET_KEY` | Cloud image storage | Same as above |
| `CLOUDFLARE_R2_ENDPOINT` | Cloud image storage | R2 dashboard → S3 API |
| `CLOUDFLARE_R2_PUBLIC_URL` | Public image URLs | R2 bucket → Public Dev URL |

### 2. Launch the stack

```bash
docker compose up -d
```

This starts 6 services:

| Service | Port | Description |
|---------|------|-------------|
| `db` | 5432 | PostgreSQL 16 |
| `redis` | 6379 | Redis 7 |
| `api` | 8000 | FastAPI backend |
| `celery-worker` | — | Async task processing |
| `celery-beat` | — | Scheduled task runner |
| `dashboard` | 5175 | React admin UI |

The database schema is created automatically on first start via Alembic migrations.

### 3. Generate your first content

```bash
# Generate a daily verse post with images and reel
docker compose exec api python manage.py generate-content --type daily_verse

# View the weekly content calendar
docker compose exec api python manage.py show-calendar
```

### 4. Open the dashboard

Go to [http://localhost:5175](http://localhost:5175) to:

- Review generated content in the **Queue** page
- Preview images and reels in the lightbox
- Copy captions and hashtags
- Approve or reject posts
- View the content calendar

## Project Structure

```
api/                  FastAPI routes (content, analytics, monetization, dashboard)
core/
  config.py           Pydantic settings from .env
  content/            Claude AI generator, Jinja2 prompts, series manager, calendar
  images/             Leonardo.ai, Unsplash, PIL overlays, FFmpeg reel generator
  posting/            Instagram, Facebook, TikTok clients
  scraper/            Bible API, Google Trends, Reddit, hashtags, competitors
database/
  models.py           SQLAlchemy ORM — 13 tables, 9 enums
  session.py          Engine, SessionLocal, get_db
  migrations/         Alembic migrations
dashboard/            React 18 + Vite + Tailwind
prompts/              8 Jinja2 prompt templates
workers/              Celery tasks (daily content, posting, analytics)
scripts/              Docker entrypoint
tests/                64 unit tests (pytest)
docs/                 Branded HTML documentation
manage.py             CLI tool
```

## CLI Commands

All commands run inside the API container:

```bash
docker compose exec api python manage.py <command>
```

| Command | Description |
|---------|-------------|
| `init-db` | Create database tables |
| `seed` | Seed hashtags and brand prospects |
| `generate-verse` | Fetch and cache a Bible verse |
| `generate-content --type <type>` | Generate content (daily_verse, marriage_monday, etc.) |
| `show-calendar` | Display this week's content schedule |
| `test-leonardo` | Test Leonardo.ai API connection |
| `weekly-report` | Generate engagement report |
| `rate-card` | Show sponsorship rate card |

## Content Types

| Type | Day | Description |
|------|-----|-------------|
| `daily_verse` | Daily | Bible verse with branded image + reel |
| `marriage_monday` | Monday | Marriage tips and encouragement |
| `parenting_wednesday` | Wednesday | Age-specific parenting advice |
| `faith_friday` | Friday | Faith through hardship topics |
| `encouragement` | Mon/Thu | General encouragement posts |
| `this_or_that` | Tuesday | Interactive engagement polls |
| `fill_in_blank` | Thursday | Fill-in-the-blank engagement |
| `conviction_quote` | Saturday | Bold faith statements |
| `carousel` | Saturday | Multi-slide carousel posts |
| `gratitude` | Sunday | Gratitude-themed content |
| `prayer_prompt` | Sunday | Prayer starters |

## Common Operations

```bash
# View logs
docker compose logs api -f
docker compose logs celery-worker -f

# Stop everything
docker compose down

# Stop and wipe database (fresh start)
docker compose down -v

# Run tests
docker compose exec api pytest

# Restart a single service after .env changes
docker compose down api && docker compose up -d api
```

## Brand Design

- **Colors:** Cream `#FFF8F0` / Gold `#D4A853` / Green `#2D4A3E` / White `#FAFAFA`
- **Fonts:** Georgia (headings), Calibri (body)
- **Watermark:** @stillwatergrace
- **Image styles:** bible_page, dark_hero, bottom_band, center_box, story overlay

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Alembic, Celery
- **Frontend:** React 18, Vite, Tailwind CSS
- **Database:** PostgreSQL 16, Redis 7
- **AI:** Anthropic Claude API, Leonardo.ai
- **Images:** Pillow (PIL), FFmpeg, Unsplash API
- **Storage:** Cloudflare R2 (S3-compatible)
- **Posting:** Instagram Graph API, Facebook, TikTok
- **Infrastructure:** Docker Compose (6 services)
