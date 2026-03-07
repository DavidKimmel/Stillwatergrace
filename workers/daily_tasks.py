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

        days = health.get("days_remaining", -1)

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
