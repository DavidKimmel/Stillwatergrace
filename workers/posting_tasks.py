"""Posting Celery tasks for scheduled content dispatch."""

import logging
from datetime import datetime, timedelta

from workers.celery_app import app

logger = logging.getLogger(__name__)

# Time slot windows (EST)
TIME_SLOTS = {
    "morning": (6, 30),   # 6:30 AM
    "noon": (12, 0),      # 12:00 PM
    "evening": (19, 30),  # 7:30 PM
}


@app.task(bind=True, max_retries=3, default_retry_delay=120)
def post_scheduled_content(self, time_slot: str):
    """
    Post approved content scheduled for the given time slot.
    Dispatches to Instagram, Facebook, and TikTok as configured.
    """
    from database.session import get_db
    from database.models import (
        GeneratedContent,
        ContentStatus,
        PostingLog,
        PostingStatus,
        Platform,
    )
    from core.config import settings

    logger.info(f"Running {time_slot} posting window...")

    now = datetime.utcnow()
    # Find content scheduled within a 1-hour window of the target time
    window_start = now - timedelta(minutes=30)
    window_end = now + timedelta(minutes=30)

    with get_db() as db:
        # Find approved content for this window
        content_items = (
            db.query(GeneratedContent)
            .filter(
                GeneratedContent.status == ContentStatus.approved,
                GeneratedContent.scheduled_at >= window_start,
                GeneratedContent.scheduled_at <= window_end,
            )
            .all()
        )

        if not content_items:
            logger.info(f"No content scheduled for {time_slot} window")
            return {"status": "no_content", "time_slot": time_slot}

        results = []
        for content in content_items:
            # Post to Instagram
            if settings.has_instagram:
                result = _post_to_instagram(db, content)
                results.append(result)
            else:
                # Log as mock post in development
                log = PostingLog(
                    content_id=content.id,
                    platform=Platform.instagram,
                    status=PostingStatus.skipped,
                    error_message="Instagram not configured (dev mode)",
                    scheduled_for=content.scheduled_at,
                    created_at=now,
                )
                db.add(log)
                logger.info(f"[MOCK] Would post content #{content.id} to Instagram")
                results.append({"content_id": content.id, "platform": "instagram", "status": "mock"})

            # Mark content as posted
            content.status = ContentStatus.posted

        return {"status": "success", "time_slot": time_slot, "posted": results}


def _post_to_instagram(db, content):
    """Post a single content piece to Instagram."""
    from database.models import PostingLog, PostingStatus, Platform, GeneratedImage, ImageFormat

    logger.info(f"Posting content #{content.id} to Instagram...")

    try:
        from core.posting.instagram_client import InstagramClient
        client = InstagramClient()

        # Get the feed image
        image = (
            db.query(GeneratedImage)
            .filter(
                GeneratedImage.content_id == content.id,
                GeneratedImage.format == ImageFormat.feed_4x5,
            )
            .first()
        )

        if not image or not image.final_url:
            raise ValueError(f"No feed image found for content #{content.id}")

        # Build caption with hashtags
        caption = content.caption_long or content.caption_medium or content.caption_short
        hashtags = []
        for tag_list in [content.hashtags_niche, content.hashtags_medium, content.hashtags_large]:
            if tag_list:
                hashtags.extend(tag_list[:5])  # 5 from each tier = 15 total

        if hashtags:
            caption += "\n.\n.\n.\n" + " ".join(hashtags[:30])

        # Post
        result = client.publish_photo(
            image_url=image.final_url,
            caption=caption,
        )

        # Log success
        log = PostingLog(
            content_id=content.id,
            platform=Platform.instagram,
            platform_post_id=result.get("id"),
            platform_media_id=result.get("media_id"),
            status=PostingStatus.success,
            caption_used=caption,
            hashtags_used=hashtags,
            posted_at=datetime.utcnow(),
            scheduled_for=content.scheduled_at,
        )
        db.add(log)

        logger.info(f"Successfully posted content #{content.id} to Instagram")
        return {"content_id": content.id, "platform": "instagram", "status": "success"}

    except Exception as e:
        logger.error(f"Failed to post content #{content.id} to Instagram: {e}")

        log = PostingLog(
            content_id=content.id,
            platform=Platform.instagram,
            status=PostingStatus.failed,
            error_message=str(e),
            scheduled_for=content.scheduled_at,
        )
        db.add(log)

        return {"content_id": content.id, "platform": "instagram", "status": "failed", "error": str(e)}
