"""Posting Celery tasks for scheduled content dispatch."""

import logging
import random
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

    # Use app timezone for window matching (scheduled_at is stored in EST)
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(settings.timezone)
        now = datetime.now(tz).replace(tzinfo=None)
    except Exception:
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
    """Post a single content piece to Instagram (photo or reel)."""
    from database.models import PostingLog, PostingStatus, Platform, GeneratedImage, ImageFormat

    logger.info(f"Posting content #{content.id} to Instagram...")

    try:
        from core.posting.instagram_client import InstagramClient
        client = InstagramClient()

        # Check for reel first
        reel = (
            db.query(GeneratedImage)
            .filter(
                GeneratedImage.content_id == content.id,
                GeneratedImage.format == ImageFormat.reel_9x16,
            )
            .first()
        )

        if reel and reel.final_url:
            # Post as reel
            return _publish_reel(db, client, content, reel)

        # Fall back to photo post
        image = (
            db.query(GeneratedImage)
            .filter(
                GeneratedImage.content_id == content.id,
                GeneratedImage.format == ImageFormat.feed_4x5,
            )
            .first()
        )

        if not image or not image.final_url:
            raise ValueError(f"No feed image or reel found for content #{content.id}")

        # Build caption with hashtags
        caption = _build_caption(content)

        # Post photo
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
            hashtags_used=_get_hashtags(content),
            posted_at=datetime.utcnow(),
            scheduled_for=content.scheduled_at,
        )
        db.add(log)

        logger.info(f"Successfully posted content #{content.id} as photo to Instagram")
        return {"content_id": content.id, "platform": "instagram", "status": "success", "type": "photo"}

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


def _publish_reel(db, client, content, reel):
    """Publish a reel to Instagram."""
    from database.models import PostingLog, PostingStatus, Platform

    caption = _build_caption(content)

    result = client.publish_reel(
        video_url=reel.final_url,
        caption=caption,
    )

    log = PostingLog(
        content_id=content.id,
        platform=Platform.instagram,
        platform_post_id=result.get("id"),
        platform_media_id=result.get("media_id"),
        status=PostingStatus.success,
        caption_used=caption,
        hashtags_used=_get_hashtags(content),
        posted_at=datetime.utcnow(),
        scheduled_for=content.scheduled_at,
    )
    db.add(log)

    logger.info(f"Successfully posted content #{content.id} as reel to Instagram")
    return {"content_id": content.id, "platform": "instagram", "status": "success", "type": "reel"}


# Engagement CTAs — appended to captions that don't already contain one
ENGAGEMENT_CTAS = [
    "Type 'Amen' if you needed this today.",
    "Share this with someone who needs to hear it.",
    "Save this for when you need a reminder.",
    "Tag someone who needs this word today.",
    "Double tap if this spoke to your heart.",
    "Drop a heart if this hit home.",
    "Comment 'Yes' if you're claiming this.",
    "Share this with your prayer partner.",
]

# Phrases that indicate a CTA is already present
CTA_INDICATORS = [
    "type amen", "share with", "save this", "tag someone", "double tap",
    "drop a", "comment", "let me know", "tell me", "what do you think",
    "do you agree",
]


def _build_caption(content) -> str:
    """Build caption with engagement CTA and hashtags."""
    caption = content.caption_long or content.caption_medium or content.caption_short or ""

    # Include full verse text in caption if available (hook-on-image strategy)
    verse_text = ""
    if content.verse and content.verse.text:
        verse_ref = content.verse.reference or ""
        verse_text = f'\n\n"{content.verse.text}" — {verse_ref}'

    # Append CTA if caption doesn't already have one
    caption_lower = caption.lower()
    has_cta = any(indicator in caption_lower for indicator in CTA_INDICATORS)
    if not has_cta:
        cta = random.choice(ENGAGEMENT_CTAS)
        caption += f"\n\n{cta}"

    # Add verse to caption if not already included
    if verse_text and content.verse.reference not in caption:
        caption += verse_text

    hashtags = _get_hashtags(content)
    if hashtags:
        caption += "\n.\n.\n.\n" + " ".join(hashtags[:30])

    return caption


def _get_hashtags(content) -> list[str]:
    """Extract hashtags from content, 5 from each tier."""
    hashtags = []
    for tag_list in [content.hashtags_niche, content.hashtags_medium, content.hashtags_large]:
        if tag_list:
            hashtags.extend(tag_list[:5])
    return hashtags
