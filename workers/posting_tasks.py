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

            # Cross-post to TikTok (reels only)
            if settings.has_tiktok:
                tk_result = _post_to_tiktok(db, content)
                results.append(tk_result)

            # Mark content as posted
            content.status = ContentStatus.posted

        return {"status": "success", "time_slot": time_slot, "posted": results}


@app.task(bind=True, max_retries=2, default_retry_delay=300)
def post_missed_content(self):
    """
    Catch-up task: find approved content whose scheduled_at is in the past
    but was never posted. Posts them in chronological order.
    Runs every 30 minutes so missed posts get picked up on next boot.
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

    logger.info("Checking for missed posts...")

    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(settings.timezone)
        now = datetime.now(tz).replace(tzinfo=None)
    except Exception:
        now = datetime.utcnow()

    # Only catch up posts from the last 7 days (don't post ancient content)
    cutoff = now - timedelta(days=7)

    with get_db() as db:
        missed = (
            db.query(GeneratedContent)
            .filter(
                GeneratedContent.status == ContentStatus.approved,
                GeneratedContent.scheduled_at < now - timedelta(minutes=30),
                GeneratedContent.scheduled_at >= cutoff,
            )
            .order_by(GeneratedContent.scheduled_at.asc())
            .all()
        )

        if not missed:
            logger.info("No missed posts found")
            return {"status": "no_missed_content"}

        logger.info(f"Found {len(missed)} missed post(s), catching up...")

        results = []
        for content in missed:
            logger.info(
                f"Catching up content #{content.id} "
                f"(was scheduled for {content.scheduled_at})"
            )

            if settings.has_instagram:
                result = _post_to_instagram(db, content)
                results.append(result)

            if settings.has_facebook:
                fb_result = _post_to_facebook(db, content)
                results.append(fb_result)

            content.status = ContentStatus.posted

        return {"status": "caught_up", "posted": results}


def post_content_immediately(content_id: int) -> dict:
    """Post a single content piece to all platforms right now.

    Called directly from the API endpoint (not as a Celery task).
    Returns dict with per-platform results.
    """
    from database.session import get_db
    from database.models import (
        GeneratedContent,
        ContentStatus,
    )
    from core.config import settings

    with get_db() as db:
        content = db.query(GeneratedContent).filter(
            GeneratedContent.id == content_id
        ).first()

        if not content:
            return {"error": f"Content #{content_id} not found"}

        if content.status == ContentStatus.posted:
            return {"error": f"Content #{content_id} already posted"}

        if content.status == ContentStatus.pending:
            content.status = ContentStatus.approved
            content.approved_at = datetime.utcnow()

        results = []

        if settings.has_instagram:
            results.append(_post_to_instagram(db, content))

        if settings.has_facebook:
            results.append(_post_to_facebook(db, content))

        if settings.has_tiktok:
            results.append(_post_to_tiktok(db, content))

        # Mark as posted if at least one platform succeeded
        any_success = any(r.get("status") == "success" for r in results)
        if any_success:
            content.status = ContentStatus.posted

        return {"content_id": content_id, "platforms": results}


def _post_to_instagram(db, content):
    """Post a single content piece to Instagram (photo, carousel, or reel)."""
    from database.models import PostingLog, PostingStatus, Platform, GeneratedImage, ImageFormat, ContentType

    logger.info(f"Posting content #{content.id} to Instagram...")

    try:
        from core.posting.instagram_client import InstagramClient
        client = InstagramClient()

        # Carousel content type → use publish_carousel with slide images
        if content.content_type == ContentType.carousel:
            return _publish_carousel(db, client, content)

        # Non-carousel: check for reel first
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


def _publish_carousel(db, client, content):
    """Publish a carousel post to Instagram using slide images."""
    from database.models import PostingLog, PostingStatus, Platform, GeneratedImage, ImageFormat

    caption = _build_caption(content)

    # Find carousel slide images (stored as feed_4x5 with r2_key like carousel_N.jpg)
    all_feed = (
        db.query(GeneratedImage)
        .filter(
            GeneratedImage.content_id == content.id,
            GeneratedImage.format == ImageFormat.feed_4x5,
        )
        .order_by(GeneratedImage.id)
        .all()
    )

    # Separate carousel slides from the main feed image
    slides = [img for img in all_feed if img.r2_key and "carousel_" in img.r2_key]

    if len(slides) >= 2:
        image_urls = [s.final_url for s in slides if s.final_url]
    elif len(all_feed) >= 2:
        # Fallback: use all feed_4x5 images as carousel items
        image_urls = [img.final_url for img in all_feed if img.final_url]
    else:
        # Not enough slides for carousel — prefer reel if available, else single photo
        reel = (
            db.query(GeneratedImage)
            .filter(
                GeneratedImage.content_id == content.id,
                GeneratedImage.format == ImageFormat.reel_9x16,
            )
            .first()
        )
        if reel and reel.final_url:
            logger.info(f"Carousel #{content.id} has no slides, falling back to reel")
            return _publish_reel(db, client, content, reel)

        image = all_feed[0] if all_feed else None
        if not image or not image.final_url:
            raise ValueError(f"No images found for carousel content #{content.id}")

        logger.info(f"Only 1 image for carousel #{content.id}, posting as photo instead")
        result = client.publish_photo(image_url=image.final_url, caption=caption)
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
        return {"content_id": content.id, "platform": "instagram", "status": "success", "type": "photo"}

    result = client.publish_carousel(image_urls=image_urls, caption=caption)

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

    logger.info(f"Successfully posted content #{content.id} as carousel ({len(image_urls)} slides) to Instagram")
    return {"content_id": content.id, "platform": "instagram", "status": "success", "type": "carousel"}


def _post_to_facebook(db, content):
    """Cross-post a content piece to Facebook Page."""
    from database.models import PostingLog, PostingStatus, Platform, GeneratedImage, ImageFormat, ContentType

    logger.info(f"Cross-posting content #{content.id} to Facebook...")

    try:
        from core.posting.facebook_client import FacebookClient
        client = FacebookClient()

        # Use Facebook-adapted caption (more conversational)
        caption = _build_facebook_caption(content)

        # Carousel with real slides → post as photo on Facebook
        # Carousel without slides or non-carousel → check for reel first
        has_carousel_slides = False
        if content.content_type == ContentType.carousel:
            slide_count = (
                db.query(GeneratedImage)
                .filter(
                    GeneratedImage.content_id == content.id,
                    GeneratedImage.format == ImageFormat.feed_4x5,
                    GeneratedImage.r2_key.contains("carousel_"),
                )
                .count()
            )
            has_carousel_slides = slide_count >= 2

        if has_carousel_slides:
            reel = None
        else:
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


def _post_to_tiktok(db, content):
    """Cross-post a reel to TikTok. Skips non-reel content."""
    from database.models import PostingLog, PostingStatus, Platform, GeneratedImage, ImageFormat

    # Only post reels to TikTok
    reel = (
        db.query(GeneratedImage)
        .filter(
            GeneratedImage.content_id == content.id,
            GeneratedImage.format == ImageFormat.reel_9x16,
        )
        .first()
    )

    if not reel or not reel.final_url:
        logger.info(f"No reel for content #{content.id} — skipping TikTok")
        return {"content_id": content.id, "platform": "tiktok", "status": "skipped", "reason": "no_reel"}

    logger.info(f"Cross-posting content #{content.id} to TikTok...")

    try:
        from core.posting.tiktok_client import TikTokClient
        client = TikTokClient()

        caption = _build_tiktok_caption(content)

        result = client.publish_video(
            video_url=reel.final_url,
            caption=caption,
        )

        if not result:
            raise RuntimeError("TikTok API returned no result")

        log = PostingLog(
            content_id=content.id,
            platform=Platform.tiktok,
            platform_post_id=str(result.get("publish_id", "")),
            status=PostingStatus.success,
            caption_used=caption,
            posted_at=datetime.utcnow(),
            scheduled_for=content.scheduled_at,
        )
        db.add(log)

        logger.info(f"Successfully cross-posted content #{content.id} to TikTok")
        return {"content_id": content.id, "platform": "tiktok", "status": "success"}

    except Exception as e:
        logger.error(f"TikTok cross-post failed for #{content.id}: {e}")

        log = PostingLog(
            content_id=content.id,
            platform=Platform.tiktok,
            status=PostingStatus.failed,
            error_message=str(e),
            scheduled_for=content.scheduled_at,
        )
        db.add(log)

        return {"content_id": content.id, "platform": "tiktok", "status": "failed", "error": str(e)}


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
        caption += "\n\n" + " ".join(hashtags)

    return caption


def _get_hashtags(content) -> list[str]:
    """Extract hashtags — 5 max (2 large + 2 niche + 1 branded)."""
    hashtags = []
    if content.hashtags_large:
        hashtags.extend(content.hashtags_large[:2])
    if content.hashtags_niche:
        hashtags.extend(content.hashtags_niche[:2])
    hashtags.append("#stillwatergrace")
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

    # Facebook: 3 hashtags max (algorithm prefers fewer)
    hashtags = ["#stillwatergrace"]
    if content.hashtags_large:
        hashtags.append(content.hashtags_large[0])
    if content.hashtags_niche:
        hashtags.append(content.hashtags_niche[0])
    caption += "\n\n" + " ".join(hashtags)

    return caption


def _build_tiktok_caption(content) -> str:
    """Build a TikTok-optimized caption.

    TikTok captions max 2200 chars but shorter performs better.
    Uses 3-5 hashtags, no dot separators. Includes verse reference.
    """
    caption = content.caption_short or content.caption_medium or ""

    # Include verse reference
    if content.verse and content.verse.reference:
        if content.verse.reference not in caption:
            caption += f" ({content.verse.reference})"

    # TikTok-style hashtags: 4 max
    hashtags = ["#faith", "#christian", "#stillwatergrace"]
    if content.hashtags_niche:
        hashtags.append(content.hashtags_niche[0])
    caption += "\n\n" + " ".join(hashtags)

    return caption[:2200]
