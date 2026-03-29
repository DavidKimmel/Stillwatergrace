"""Daily Celery tasks for the content pipeline."""

import logging

from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def run_trend_discovery(self):
    """
    Run all trend discovery scrapers:
    1. Bible verse of the day
    2. Google Trends for faith/family keywords
    3. Reddit hot posts from target subreddits
    4. Pinterest trending pins
    5. Aggregate and score all trends
    """
    from database.session import get_db
    from core.scraper.bible_api import BibleAPIClient
    from core.scraper.google_trends import GoogleTrendsClient
    from core.scraper.hashtag_research import HashtagResearcher

    logger.info("Starting daily trend discovery...")
    results = {}

    with get_db() as db:
        # 1. Daily Bible verse
        try:
            bible_client = BibleAPIClient(db)
            verse = bible_client.fetch_daily_verse()
            results["bible_verse"] = verse.reference if verse else "failed"
            logger.info(f"Bible verse: {results['bible_verse']}")
        except Exception as e:
            logger.error(f"Bible API error: {e}")
            results["bible_verse"] = f"error: {e}"

        # 2. Google Trends
        try:
            trends_client = GoogleTrendsClient(db)
            trend_count = trends_client.fetch_trending_topics()
            results["google_trends"] = trend_count
            logger.info(f"Google Trends: {trend_count} topics found")
        except Exception as e:
            logger.error(f"Google Trends error: {e}")
            results["google_trends"] = f"error: {e}"

        # 3. Reddit (only if credentials configured)
        from core.config import settings
        if settings.has_reddit:
            try:
                from core.scraper.reddit_scraper import RedditScraper
                reddit = RedditScraper(db)
                post_count = reddit.fetch_hot_posts()
                results["reddit"] = post_count
                logger.info(f"Reddit: {post_count} posts scraped")
            except Exception as e:
                logger.error(f"Reddit error: {e}")
                results["reddit"] = f"error: {e}"
        else:
            results["reddit"] = "skipped (no credentials)"

    logger.info(f"Trend discovery complete: {results}")
    return results


@app.task(bind=True, max_retries=2, default_retry_delay=600)
def run_content_generation(self):
    """
    Generate content for today's calendar slots using Claude API.
    Depends on trend discovery having run first.
    """
    from database.session import get_db
    from core.config import settings

    if not settings.has_anthropic:
        logger.warning("Anthropic API key not configured, skipping content generation")
        return {"status": "skipped", "reason": "no API key"}

    logger.info("Starting daily content generation...")

    with get_db() as db:
        try:
            from core.content.generator import ContentGenerator
            generator = ContentGenerator(db)
            generated = generator.generate_daily_content()
            logger.info(f"Generated {generated} content pieces")
            return {"status": "success", "generated": generated}
        except Exception as e:
            logger.error(f"Content generation error: {e}")
            raise self.retry(exc=e)


@app.task(bind=True, max_retries=2, default_retry_delay=600)
def run_image_generation(self):
    """
    Generate images for pending content that has been generated but lacks images.
    """
    from database.session import get_db
    from core.config import settings

    logger.info("Starting image generation pipeline...")

    with get_db() as db:
        try:
            from core.images.image_processor import ImagePipeline
            pipeline = ImagePipeline(db)
            processed = pipeline.process_pending_content()
            logger.info(f"Processed images for {processed} content pieces")
            return {"status": "success", "processed": processed}
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            raise self.retry(exc=e)


@app.task
def collect_analytics(hours_after: int):
    """Collect analytics for posts that are N hours old."""
    from database.session import get_db
    from core.config import settings

    if not settings.has_instagram:
        return {"status": "skipped", "reason": "Instagram not configured"}

    logger.info(f"Collecting {hours_after}hr analytics...")

    with get_db() as db:
        try:
            from core.analytics.instagram_insights import InsightsCollector
            collector = InsightsCollector(db)
            collected = collector.collect_for_age(hours_after)
            return {"status": "success", "collected": collected}
        except Exception as e:
            logger.error(f"Analytics collection error: {e}")
            return {"status": "error", "error": str(e)}


@app.task
def backfill_analytics():
    """One-time backfill of analytics for posts missing snapshots."""
    from database.session import get_db
    from core.config import settings

    if not settings.has_instagram:
        return {"status": "skipped", "reason": "Instagram not configured"}

    logger.info("Running analytics backfill...")

    with get_db() as db:
        try:
            from core.analytics.instagram_insights import InsightsCollector
            collector = InsightsCollector(db)
            collected = collector.backfill_all()
            return {"status": "success", "collected": collected}
        except Exception as e:
            logger.error(f"Analytics backfill error: {e}")
            return {"status": "error", "error": str(e)}


@app.task
def refresh_recent_analytics():
    """Refresh analytics for all posts from the last 7 days.

    Runs daily to catch posts missed during Docker downtime and to
    keep engagement metrics up to date. Unlike collect_for_age (which
    targets a specific post age window), this collects fresh data for
    ALL recent posts regardless of existing snapshots.
    """
    from database.session import get_db
    from core.config import settings

    if not settings.has_instagram:
        return {"status": "skipped", "reason": "Instagram not configured"}

    logger.info("Refreshing analytics for recent posts...")

    with get_db() as db:
        try:
            from core.analytics.instagram_insights import InsightsCollector
            collector = InsightsCollector(db)
            collected = collector.refresh_recent(days=7)
            return {"status": "success", "refreshed": collected}
        except Exception as e:
            logger.error(f"Analytics refresh error: {e}")
            return {"status": "error", "error": str(e)}


@app.task
def run_competitor_scrape():
    """Weekly competitor data collection."""
    from database.session import get_db

    logger.info("Running weekly competitor scrape...")

    with get_db() as db:
        try:
            from core.scraper.competitor_tracker import CompetitorTracker
            tracker = CompetitorTracker(db)
            scraped = tracker.scrape_all_competitors()
            return {"status": "success", "competitors_scraped": scraped}
        except Exception as e:
            logger.error(f"Competitor scrape error: {e}")
            return {"status": "error", "error": str(e)}


@app.task
def scrape_competitor_content():
    """Scrape recent posts from competitor accounts.

    Runs Mon + Thu at 5:00 AM EST. Uses Instagram Business Discovery API
    to fetch last 10 posts per competitor (captions, media types, hashtags).
    """
    from database.session import get_db
    from core.config import settings

    if not settings.has_instagram:
        return {"status": "skipped", "reason": "Instagram not configured"}

    logger.info("Scraping competitor content...")

    with get_db() as db:
        try:
            from core.scraper.competitor_content import CompetitorContentScraper
            scraper = CompetitorContentScraper(db)
            total = scraper.scrape_all(limit=10)
            return {"status": "success", "posts_scraped": total}
        except Exception as e:
            logger.error(f"Competitor content scrape error: {e}")
            return {"status": "error", "error": str(e)}


@app.task(bind=True, max_retries=1, default_retry_delay=900)
def run_weekly_content_generation(self):
    """Generate content + images for the entire upcoming week (Mon-Sun).

    Runs Sunday morning so the user can review and approve throughout the day.
    Uses dedup check to skip any slots that already have content.
    """
    from datetime import datetime, timedelta
    from database.session import get_db
    from core.config import settings

    if not settings.has_anthropic:
        logger.warning("Anthropic API key not configured, skipping weekly generation")
        return {"status": "skipped", "reason": "no API key"}

    logger.info("Starting weekly content generation for upcoming week...")

    with get_db() as db:
        try:
            from core.content.generator import ContentGenerator
            from core.content.calendar_logic import ContentCalendar, WEEKLY_SCHEDULE, POSTING_TIMES
            from core.images.image_processor import ImagePipeline

            gen = ContentGenerator(db)
            img_pipeline = ImagePipeline(db)
            cal = ContentCalendar(db)

            # Generate for the upcoming Monday through Sunday
            today = datetime.utcnow()
            # Nearest upcoming Monday (0 if today is Monday)
            days_until_monday = (7 - today.weekday()) % 7
            monday = today + timedelta(days=days_until_monday)
            monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

            total = 0
            for day_offset in range(7):
                day = monday + timedelta(days=day_offset)
                day_of_week = day.weekday()
                day_schedule = WEEKLY_SCHEDULE.get(day_of_week, {})

                for time_slot, config in day_schedule.items():
                    if config is None:
                        continue

                    from database.models import ContentType
                    posting_time = POSTING_TIMES[time_slot]
                    scheduled_at = day.replace(
                        hour=posting_time.hour,
                        minute=posting_time.minute,
                    )

                    slot = {
                        "date": day.date().isoformat(),
                        "time_slot": time_slot,
                        "content_type": config["type"].value,
                        "emotional_tone": config["tone"].value,
                        "scheduled_at": scheduled_at,
                        "theme": "",
                        "age_group": "general",
                    }

                    # Add themes
                    content_type = config["type"]
                    if content_type == ContentType.marriage_monday:
                        slot["theme"] = cal.series.get_marriage_theme()
                    elif content_type == ContentType.faith_friday:
                        slot["theme"] = cal.series.get_hardship_topic()

                    try:
                        content = gen._generate_for_slot(slot)
                        if content:
                            total += 1
                            try:
                                img_pipeline.generate_images_for_content(content)
                            except Exception as img_e:
                                logger.warning(f"Image gen failed for #{content.id}: {img_e}")
                            logger.info(
                                f"Generated {slot['content_type']} for "
                                f"{day.strftime('%A')} {time_slot} (#{content.id})"
                            )
                    except Exception as e:
                        logger.error(f"Failed to generate {slot['content_type']}: {e}")

            logger.info(f"Weekly generation complete: {total} pieces for week of {monday.date()}")
            return {"status": "success", "generated": total, "week_of": monday.date().isoformat()}
        except Exception as e:
            logger.error(f"Weekly content generation error: {e}")
            raise self.retry(exc=e)


@app.task
def generate_weekly_report():
    """Generate and email the weekly performance report."""
    from database.session import get_db

    logger.info("Generating weekly report...")

    with get_db() as db:
        try:
            from core.analytics.report_generator import ReportGenerator
            report = ReportGenerator(db)
            report.generate_and_send()
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Report generation error: {e}")
            return {"status": "error", "error": str(e)}


@app.task
@app.task(name="workers.daily_tasks.run_weekly_cleanup")
def run_weekly_cleanup():
    """Clean up local temp files — processed images, reel videos, old narration.

    Preserves music library and recent narration cache (<30 days).
    Runs weekly via Celery beat.
    """
    import subprocess
    logger.info("Running weekly local file cleanup...")
    try:
        result = subprocess.run(
            ["python", "manage.py", "purge-local"],
            capture_output=True, text=True, timeout=60,
        )
        logger.info(f"Cleanup output: {result.stdout.strip()}")
        if result.returncode != 0:
            logger.error(f"Cleanup stderr: {result.stderr.strip()}")
        return {"status": "completed", "output": result.stdout.strip()}
    except Exception as e:
        logger.error(f"Weekly cleanup failed: {e}")
        return {"status": "error", "error": str(e)}


@app.task(name="workers.daily_tasks.refresh_instagram_token_task")
def refresh_instagram_token_task():
    """Check Instagram token health and refresh if needed.

    Runs weekly. Refreshes if token has < 14 days remaining.
    """
    from core.config import settings

    if not settings.has_instagram:
        return {"status": "skipped", "reason": "Instagram not configured"}

    logger.info("Checking Instagram token health...")

    try:
        from core.posting.instagram_client import check_token_health, refresh_instagram_token

        health = check_token_health()
        if not health.get("valid"):
            logger.error("Instagram token is invalid!")
            return {"status": "error", "health": health}

        days = health.get("days_remaining")

        if days is None:
            logger.info("Token is never-expiring, no refresh needed")
            return {"status": "healthy", "days_remaining": "never"}

        if days < 14:
            logger.info(f"Token expires in {days} days, refreshing...")
            new_token = refresh_instagram_token()
            if new_token:
                return {"status": "refreshed", "days_remaining_before": days}
            else:
                return {"status": "refresh_failed", "days_remaining": days}
        else:
            logger.info(f"Token healthy ({days} days remaining), no refresh needed")
            return {"status": "healthy", "days_remaining": days}

    except Exception as e:
        logger.error(f"Token refresh task error: {e}")
        return {"status": "error", "error": str(e)}

    # Also refresh the insights token (IGAA) if configured
    try:
        from core.posting.instagram_client import refresh_insights_token
        insights_result = refresh_insights_token()
        if insights_result:
            logger.info("Insights token refreshed successfully")
    except Exception as e:
        logger.error(f"Insights token refresh error: {e}")
