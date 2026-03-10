"""Content management API routes."""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.session import get_db_dependency
from database.models import (
    GeneratedContent,
    ContentStatus,
    ContentType,
    GeneratedImage,
    ImageFormat,
    ImageProvider,
)

router = APIRouter()


@router.get("/queue")
def get_content_queue(
    status: Optional[ContentStatus] = None,
    content_type: Optional[ContentType] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db_dependency),
):
    """Get content in the approval queue."""
    query = db.query(GeneratedContent)

    if status:
        query = query.filter(GeneratedContent.status == status)
    else:
        # Default: show pending and approved
        query = query.filter(
            GeneratedContent.status.in_([ContentStatus.pending, ContentStatus.approved])
        )

    if content_type:
        query = query.filter(GeneratedContent.content_type == content_type)

    total = query.count()
    items = (
        query.order_by(GeneratedContent.scheduled_at.asc().nullsfirst())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "items": [_serialize_content(item, include_images=True) for item in items],
    }


@router.get("/{content_id}")
def get_content_detail(content_id: int, db: Session = Depends(get_db_dependency)):
    """Get full content detail including images."""
    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return _serialize_content(content, include_images=True)


@router.post("/{content_id}/approve")
def approve_content(
    content_id: int,
    scheduled_at: Optional[datetime] = None,
    db: Session = Depends(get_db_dependency),
):
    """Approve content for posting."""
    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    content.status = ContentStatus.approved
    content.approved_at = datetime.utcnow()
    if scheduled_at:
        content.scheduled_at = scheduled_at

    return {"status": "approved", "id": content_id}


@router.post("/{content_id}/reject")
def reject_content(
    content_id: int,
    reason: str = "",
    db: Session = Depends(get_db_dependency),
):
    """Reject content."""
    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    content.status = ContentStatus.rejected
    content.rejected_reason = reason

    return {"status": "rejected", "id": content_id}


@router.post("/bulk-approve")
def bulk_approve(
    content_ids: list[int],
    db: Session = Depends(get_db_dependency),
):
    """Bulk approve multiple content pieces."""
    updated = 0
    for cid in content_ids:
        content = db.query(GeneratedContent).filter(GeneratedContent.id == cid).first()
        if content and content.status == ContentStatus.pending:
            content.status = ContentStatus.approved
            content.approved_at = datetime.utcnow()
            updated += 1

    return {"approved": updated}


@router.post("/{content_id}/post-now")
def post_content_now(
    content_id: int,
    db: Session = Depends(get_db_dependency),
):
    """Immediately post content to all configured platforms."""
    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if content.status == ContentStatus.posted:
        raise HTTPException(status_code=400, detail="Content already posted")

    from workers.posting_tasks import post_content_immediately
    result = post_content_immediately(content_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{content_id}/regenerate")
def regenerate_content(
    content_id: int,
    db: Session = Depends(get_db_dependency),
):
    """Reject the current content and generate a fresh replacement for the same slot.

    Generates new text via Claude API + new images, keeping the same
    content_type and scheduled_at as the original.
    """
    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if content.status == ContentStatus.posted:
        raise HTTPException(status_code=400, detail="Cannot regenerate already-posted content")

    # Reject the old content
    content.status = ContentStatus.rejected
    content.rejected_reason = "Replaced by regeneration"
    db.flush()

    # Generate new content for the same slot
    from core.content.generator import ContentGenerator

    generator = ContentGenerator(db)

    # Build kwargs matching the original slot
    kwargs = {"scheduled_at": content.scheduled_at}
    if content.quote_id:
        from database.models import ChristianQuote
        kwargs["quote"] = db.query(ChristianQuote).get(content.quote_id)

    verse = None
    if content.verse_id:
        from database.models import BibleVerse
        verse = db.query(BibleVerse).get(content.verse_id)
    elif content.content_type in {
        ContentType.daily_verse, ContentType.encouragement,
    }:
        # Fetch a fresh verse if the original used one
        from core.scraper.bible_api import BibleAPIClient
        bible = BibleAPIClient(db)
        verse = bible.fetch_daily_verse()

    new_content = generator.generate_single(
        content_type=content.content_type,
        verse=verse,
        theme=content.weekly_theme or "",
        **kwargs,
    )

    if not new_content:
        raise HTTPException(status_code=500, detail="Content generation failed — Claude API error")

    db.commit()

    # Generate images for the new content
    try:
        from core.images.image_processor import ImagePipeline
        pipeline = ImagePipeline(db)
        pipeline.generate_images_for_content(new_content)
        db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Image generation failed for #{new_content.id}: {e}")
        # Content still created, images can be generated later

    return {
        "old_id": content_id,
        "new_id": new_content.id,
        "status": new_content.status.value,
        "hook": new_content.hook,
    }


def _upload_ai_image(local_path: str, r2_key: str) -> str:
    """Upload an AI-generated image to R2 with a custom key, or return local path."""
    from core.config import settings as _settings
    import logging as _logging

    if not _settings.has_r2:
        return f"file://{local_path}"

    try:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url=_settings.cloudflare_r2_endpoint,
            aws_access_key_id=_settings.cloudflare_r2_access_key,
            aws_secret_access_key=_settings.cloudflare_r2_secret_key,
        )
        s3.upload_file(
            local_path,
            _settings.cloudflare_r2_bucket,
            r2_key,
            ExtraArgs={"ContentType": "image/jpeg"},
        )
        public_base = _settings.cloudflare_r2_public_url.rstrip("/")
        return f"{public_base}/{r2_key}"
    except Exception as e:
        _logging.getLogger(__name__).error(f"R2 upload failed for AI image: {e}")
        return f"file://{local_path}"


@router.post("/{content_id}/ai-image")
def generate_ai_image(
    content_id: int,
    prompt: Optional[str] = Query(None),
    preset: Optional[str] = Query(None),
    db: Session = Depends(get_db_dependency),
):
    """Generate AI images for content using fal.ai/FLUX, keeping existing images for comparison.

    Adds new AI-generated images alongside existing Unsplash/PIL images so
    both versions are visible in the dashboard side-by-side.
    """
    import sys
    import logging
    from pathlib import Path
    from core.config import settings
    from core.images.image_processor import (
        ImagePipeline,
        TARGET_SIZES,
    )

    logger = logging.getLogger(__name__)

    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if not settings.fal_api_key:
        raise HTTPException(status_code=503, detail="FAL_API_KEY not configured")

    # Map content types to imagegen presets
    CONTENT_TYPE_PRESETS = {
        "daily_verse": "feed",
        "marriage_monday": "feed",
        "parenting_wednesday": "feed",
        "faith_friday": "feed",
        "encouragement": "feed",
        "prayer_prompt": "feed",
        "gratitude": "feed",
        "fill_in_blank": "square",
        "this_or_that": "square",
        "conviction_quote": "feed",
        "christian_quote": "feed",
        "carousel": "square",
        "reel": "reel-bg",
    }

    content_type = content.content_type.value
    prompt_text = prompt or content.image_prompt or f"{content_type} background"
    preset_name = preset or CONTENT_TYPE_PRESETS.get(content_type, "feed")

    # Remove any previous AI images for this content (keep Unsplash originals)
    old_ai = (
        db.query(GeneratedImage)
        .filter_by(content_id=content_id, provider=ImageProvider.fal)
        .all()
    )
    for img in old_ai:
        db.delete(img)
    db.flush()

    # Import imagegen — mounted at /imagegen-src in Docker, or C:\imagegen\src on host
    import os
    imagegen_path = "/imagegen-src" if os.path.isdir("/imagegen-src") else r"C:\imagegen\src"
    if imagegen_path not in sys.path:
        sys.path.insert(0, imagegen_path)
    from imagegen import generate_image

    raw_dir = Path("images/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)

    result = generate_image(
        prompt=prompt_text,
        preset=preset_name,
        brand="stillwatergrace",
        background_only=True,
        output_path=str(raw_dir),
        provider="fal",
    )

    if not result["success"]:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {result['error']}")

    raw_path = result["image_paths"][0]

    # Move into themed folder and register in catalog
    import shutil
    from core.images.catalog import ImageCatalog, theme_for_content_type

    catalog = ImageCatalog()
    theme = theme_for_content_type(content_type)
    raw_filename = Path(raw_path).name
    themed_filename = f"ai_{raw_filename}"
    dest_path = catalog.get_save_path(theme, themed_filename)
    shutil.move(raw_path, str(dest_path))
    raw_path = str(dest_path)

    catalog.register(
        image_id=f"fal_{Path(raw_filename).stem}",
        provider="fal",
        theme=theme,
        filename=f"{theme}/{themed_filename}",
        content_type=content_type,
        content_id=content_id,
        prompt_or_query=prompt_text,
    )

    # Process AI image through PIL overlay pipeline with separate output filenames
    # (normal pipeline saves to {id}_{format}.jpg — we use ai_{id}_{format}.jpg to avoid overwriting)
    from PIL import Image as PILImage
    from core.images.image_processor import (
        IMAGES_PROCESSED_DIR,
        _apply_feed_overlay,
    )

    IMAGES_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    pipeline = ImagePipeline(db)
    new_images = []

    try:
        raw_img = PILImage.open(raw_path)
        if raw_img.mode != "RGB":
            raw_img = raw_img.convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to open AI image: {e}")

    for img_format, target_size in TARGET_SIZES.items():
        try:
            img = ImagePipeline._resize_and_crop(raw_img.copy(), target_size)

            # Apply text overlay (same as normal pipeline)
            content_type_val = content.content_type.value if content.content_type else "encouragement"
            if img_format == ImageFormat.story_9x16 and content.story_text:
                img = pipeline._add_text_overlay(img, content.story_text)
            elif img_format in (ImageFormat.feed_4x5, ImageFormat.feed_1x1):
                hook_text = content.hook or content.caption_short or ""
                words = hook_text.split()
                if len(words) > 15:
                    hook_text = " ".join(words[:15]) + "..."

                verse_text = ""
                verse_ref = ""
                verse_translation = ""
                if content.verse:
                    verse_text = content.verse.text or ""
                    verse_ref = content.verse.reference or ""
                    verse_translation = content.verse.translation or "WEB"

                if hook_text or verse_text:
                    img = _apply_feed_overlay(
                        img, hook_text, content.id, content_type_val,
                        verse_text=verse_text,
                        verse_ref=verse_ref,
                        verse_translation=verse_translation,
                    )

            # Save with ai_ prefix to avoid overwriting Unsplash versions
            output_path = IMAGES_PROCESSED_DIR / f"ai_{content.id}_{img_format.value}.jpg"
            img.save(str(output_path), "JPEG", quality=92, optimize=True)

            # Upload to R2 with ai_ prefix key (bypass _upload_to_storage which uses fixed keys)
            r2_key = f"content/{content.id}/ai_{img_format.value}.jpg"
            final_url = _upload_ai_image(str(output_path), r2_key)

            image_record = GeneratedImage(
                content_id=content.id,
                provider=ImageProvider.fal,
                format=img_format,
                raw_url=raw_path,
                final_url=final_url,
                r2_key=r2_key,
                width=target_size[0],
                height=target_size[1],
            )
            db.add(image_record)
            new_images.append({
                "format": img_format.value,
                "url": final_url,
                "provider": "fal",
            })
        except Exception as e:
            logger.error(f"AI image processing failed for {img_format.value}: {e}")

    db.commit()

    return {
        "content_id": content_id,
        "images_generated": len(new_images),
        "images": new_images,
        "prompt_used": prompt_text,
        "preset": preset_name,
    }


@router.post("/{content_id}/swap-reel")
def swap_reel_image(
    content_id: int,
    db: Session = Depends(get_db_dependency),
):
    """Re-render the reel using the AI-generated background image.

    Finds the fal.ai raw image for this content, regenerates the reel video
    using the same text/verse, and replaces the existing reel record.
    """
    import logging

    logger = logging.getLogger(__name__)

    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Find the AI raw image
    fal_image = (
        db.query(GeneratedImage)
        .filter_by(content_id=content_id, provider=ImageProvider.fal)
        .first()
    )
    if not fal_image or not fal_image.raw_url:
        raise HTTPException(status_code=404, detail="No AI image found. Generate one first with AI Image.")

    raw_path = fal_image.raw_url
    from pathlib import Path as _Path
    if not _Path(raw_path).exists():
        raise HTTPException(status_code=404, detail=f"AI raw image file not found on disk: {raw_path}")

    # Determine reel type and generate
    reel_path = None
    content_type_val = content.content_type.value if content.content_type else ""

    if content.content_type == ContentType.christian_quote and content.quote:
        from core.images.phrase_reel_generator import generate_phrase_reel
        reel_path = generate_phrase_reel(
            background_path=raw_path,
            text=content.quote.quote_text,
            content_id=content.id,
            content_type="christian_quote",
            author=content.quote.author,
        )
    elif content.verse and content.verse.text:
        from core.images.reel_generator import generate_reel
        reel_path = generate_reel(
            background_path=raw_path,
            verse_text=content.verse.text,
            verse_ref=content.verse.reference,
            content_id=content.id,
            translation=content.verse.translation or "WEB",
            content_type=content_type_val,
        )
    else:
        raise HTTPException(status_code=400, detail="Content has no verse or quote text for reel generation")

    if not reel_path:
        raise HTTPException(status_code=502, detail="Reel generation failed")

    # Upload with ai_ prefix key
    r2_key = f"content/{content.id}/ai_reel_9x16.mp4"
    final_url = _upload_ai_reel(reel_path, r2_key)

    # Remove any previous AI reel (keep original unsplash reel for comparison)
    old_ai_reel = (
        db.query(GeneratedImage)
        .filter_by(content_id=content_id, format=ImageFormat.reel_9x16, provider=ImageProvider.fal)
        .all()
    )
    for r in old_ai_reel:
        db.delete(r)
    db.flush()

    reel_record = GeneratedImage(
        content_id=content.id,
        provider=ImageProvider.fal,
        format=ImageFormat.reel_9x16,
        raw_url=raw_path,
        final_url=final_url,
        r2_key=r2_key,
        width=1080,
        height=1920,
    )
    db.add(reel_record)
    db.commit()

    logger.info(f"Reel swapped to AI background for content #{content_id}")

    return {
        "content_id": content_id,
        "reel_url": final_url,
        "provider": "fal",
    }


def _upload_ai_reel(local_path: str, r2_key: str) -> str:
    """Upload an AI reel to R2 with a custom key, or return local path."""
    from core.config import settings as _settings
    import logging as _logging

    if not _settings.has_r2:
        return f"file://{local_path}"

    try:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url=_settings.cloudflare_r2_endpoint,
            aws_access_key_id=_settings.cloudflare_r2_access_key,
            aws_secret_access_key=_settings.cloudflare_r2_secret_key,
        )
        s3.upload_file(
            local_path,
            _settings.cloudflare_r2_bucket,
            r2_key,
            ExtraArgs={"ContentType": "video/mp4"},
        )
        public_base = _settings.cloudflare_r2_public_url.rstrip("/")
        return f"{public_base}/{r2_key}"
    except Exception as e:
        _logging.getLogger(__name__).error(f"R2 reel upload failed: {e}")
        return f"file://{local_path}"


@router.post("/{content_id}/reschedule")
def reschedule_content(
    content_id: int,
    scheduled_at: datetime = Query(...),
    db: Session = Depends(get_db_dependency),
):
    """Reschedule approved content to a new time."""
    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    if content.status == ContentStatus.posted:
        raise HTTPException(status_code=400, detail="Cannot reschedule posted content")

    content.scheduled_at = scheduled_at

    return {
        "id": content_id,
        "scheduled_at": content.scheduled_at.isoformat(),
    }


@router.get("/calendar/week")
def get_weekly_calendar(
    start_date: Optional[str] = None,
    db: Session = Depends(get_db_dependency),
):
    """Get 7-day content calendar view."""
    if start_date:
        start = datetime.fromisoformat(start_date)
    else:
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    end = start + timedelta(days=7)

    items = (
        db.query(GeneratedContent)
        .filter(
            GeneratedContent.scheduled_at >= start,
            GeneratedContent.scheduled_at < end,
            GeneratedContent.status.in_([ContentStatus.approved, ContentStatus.pending, ContentStatus.posted]),
        )
        .order_by(GeneratedContent.scheduled_at.asc())
        .all()
    )

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "items": [_serialize_calendar_item(item, db) for item in items],
    }


def _serialize_content(content: GeneratedContent, include_images: bool = False) -> dict:
    """Serialize a GeneratedContent object to dict."""
    result = {
        "id": content.id,
        "content_type": content.content_type.value if content.content_type else None,
        "series_type": content.series_type,
        "emotional_tone": content.emotional_tone.value if content.emotional_tone else None,
        "weekly_theme": content.weekly_theme,
        "hook": content.hook,
        "caption_short": content.caption_short,
        "caption_medium": content.caption_medium,
        "caption_long": content.caption_long,
        "story_text": content.story_text,
        "reel_script_15": content.reel_script_15,
        "reel_script_30": content.reel_script_30,
        "facebook_variation": content.facebook_variation,
        "pinterest_description": content.pinterest_description,
        "alt_text": content.alt_text,
        "hashtags_large": content.hashtags_large,
        "hashtags_medium": content.hashtags_medium,
        "hashtags_niche": content.hashtags_niche,
        "image_prompt": content.image_prompt,
        "status": content.status.value if content.status else None,
        "scheduled_at": content.scheduled_at.isoformat() if content.scheduled_at else None,
        "created_at": content.created_at.isoformat() if content.created_at else None,
    }

    if include_images:
        result["images"] = [
            _serialize_image(img) for img in content.images
        ] if content.images else []
        # Include posting status per platform
        result["posting_status"] = {}
        for log in (content.posting_logs or []):
            result["posting_status"][log.platform.value] = {
                "status": log.status.value,
                "posted_at": log.posted_at.isoformat() if log.posted_at else None,
                "error": log.error_message,
            }

    return result


def _serialize_calendar_item(content: GeneratedContent, db: Session) -> dict:
    """Serialize content for calendar view with images and posting status."""
    result = _serialize_content(content, include_images=True)

    from database.models import PostingLog
    logs = (
        db.query(PostingLog)
        .filter(PostingLog.content_id == content.id)
        .all()
    )
    result["posting_status"] = {
        log.platform.value: {
            "status": log.status.value,
            "posted_at": log.posted_at.isoformat() if log.posted_at else None,
            "error": log.error_message,
        }
        for log in logs
    }

    return result


def _serialize_image(img: GeneratedImage) -> dict:
    """Serialize a GeneratedImage, converting local paths to static URLs."""
    final_url = img.final_url
    if final_url and not final_url.startswith("http"):
        # Convert local path like "images/processed/1_feed_4x5.jpg" to "/static/images/1_feed_4x5.jpg"
        basename = os.path.basename(final_url)
        final_url = f"/static/images/{basename}"

    return {
        "id": img.id,
        "provider": img.provider.value if img.provider else None,
        "format": img.format.value if img.format else None,
        "final_url": final_url,
        "raw_url": img.raw_url,
    }
