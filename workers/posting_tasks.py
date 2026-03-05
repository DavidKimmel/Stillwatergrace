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

            # Cross-post to Facebook
            if settings.has_facebook:
                fb_result = _post_to_facebook(db, content)
                results.append(fb_result)

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


def _get_reel_thumb_offset(video_url: str) -> int:
    """Calculate thumb_offset_ms to show the full-verse frame as thumbnail.

    The full verse is displayed near the end of the reel, during the "final hold"
    phase where all lines are visible. We probe the video duration and target
    4 seconds before the end.

    Returns offset in milliseconds.
    """
    import subprocess
    import shutil

    duration_s = None

    # Try ffprobe on the URL (works for both local and R2 URLs)
    if shutil.which("ffprobe"):
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    video_url,
                ],
                capture_output=True, text=True, timeout=15,
            )
            duration_s = float(result.stdout.strip())
        except Exception:
            pass

    if duration_s and duration_s > 6:
        # Target 4 seconds before end (in the "full verse" final hold phase)
        offset_s = max(1.0, duration_s - 4.0)
        return int(offset_s * 1000)

    # Fallback: 10 seconds (works for typical 14-25s reels)
    return 10_000


def _publish_reel(db, client, content, reel):
    """Publish a reel to Instagram."""
    from database.models import PostingLog, PostingStatus, Platform

    caption = _build_caption(content)

    # Set thumbnail to the full-verse frame (near end of reel)
    # Reels are typically 15-25s; the full verse is visible ~4s before end.
    # thumb_offset in ms — we aim for 75% through the video.
    thumb_offset_ms = _get_reel_thumb_offset(reel.final_url)

    result = client.publish_reel(
        video_url=reel.final_url,
        caption=caption,
        thumb_offset_ms=thumb_offset_ms,
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


def _post_to_facebook(db, content):
    """Cross-post a content piece to Facebook Page."""
    from database.models import PostingLog, PostingStatus, Platform, GeneratedImage, ImageFormat

    logger.info(f"Cross-posting content #{content.id} to Facebook...")

    try:
        from core.posting.facebook_client import FacebookClient
        client = FacebookClient()

        # Use Facebook-adapted caption (more conversational)
        caption = _build_facebook_caption(content)

        # Check for reel/video first
        reel = (
            db.query(GeneratedImage)
            .filter(
                GeneratedImage.content_id == content.id,
                GeneratedImage.format == ImageFormat.reel_9x16,
            )
            .first()
        )

        if reel and reel.final_url:
            result = client.publish_video(
                video_url=reel.final_url,
                caption=caption,
            )
        else:
            # Fall back to photo
            image = (
                db.query(GeneratedImage)
                .filter(
                    GeneratedImage.content_id == content.id,
                    GeneratedImage.format == ImageFormat.feed_4x5,
                )
                .first()
            )
            if not image or not image.final_url:
                raise ValueError(f"No image found for content #{content.id}")
            result = client.publish_photo(
                image_url=image.final_url,
                caption=caption,
            )

        if not result:
            raise RuntimeError("Facebook API returned no result")

        log = PostingLog(
            content_id=content.id,
            platform=Platform.facebook,
            platform_post_id=str(result.get("id", "")),
            status=PostingStatus.success,
            caption_used=caption,
            posted_at=datetime.utcnow(),
            scheduled_for=content.scheduled_at,
        )
        db.add(log)

        logger.info(f"Successfully cross-posted content #{content.id} to Facebook")
        return {"content_id": content.id, "platform": "facebook", "status": "success"}

    except Exception as e:
        logger.error(f"Facebook cross-post failed for #{content.id}: {e}")

        log = PostingLog(
            content_id=content.id,
            platform=Platform.facebook,
            status=PostingStatus.failed,
            error_message=str(e),
            scheduled_for=content.scheduled_at,
        )
        db.add(log)

        return {"content_id": content.id, "platform": "facebook", "status": "failed", "error": str(e)}


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


def _build_facebook_caption(content) -> str:
    """Build a Facebook-optimized caption.

    Uses the facebook_variation field (more conversational, ends with a question).
    Fewer hashtags than Instagram — Facebook penalizes hashtag spam.
    """
    # Prefer Facebook-specific variation, fall back to regular caption
    caption = content.facebook_variation or content.caption_long or content.caption_medium or ""

    # Include verse if available
    if content.verse and content.verse.text:
        verse_ref = content.verse.reference or ""
        if verse_ref not in caption:
            caption += f'\n\n"{content.verse.text}" — {verse_ref}'

    # Facebook: only 3-5 hashtags max (algorithm prefers fewer)
    hashtags = []
    if content.hashtags_large:
        hashtags.extend(content.hashtags_large[:2])
    if content.hashtags_niche:
        hashtags.extend(content.hashtags_niche[:2])
    if hashtags:
        caption += "\n\n" + " ".join(hashtags)

    return caption
