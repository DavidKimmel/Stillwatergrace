"""Content management API routes."""

import os
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.session import get_db_dependency
from database.models import (
    GeneratedContent,
    ContentStatus,
    ContentType,
    EmotionalTone,
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


@router.post("/generate")
def generate_content_on_demand(
    body: dict = Body(...),
    db: Session = Depends(get_db_dependency),
):
    """Generate content for the next N days (1-7). Dispatches generation for each empty slot."""
    days = min(max(body.get("days", 1), 1), 7)

    import logging

    logger = logging.getLogger(__name__)

    from core.content.calendar_logic import ContentCalendar, WEEKLY_SCHEDULE, POSTING_TIMES
    from core.content.generator import ContentGenerator
    from core.images.image_processor import ImagePipeline

    cal = ContentCalendar(db)
    gen = ContentGenerator(db)
    img_pipeline = ImagePipeline(db)

    # Use EST for date calculation (container runs UTC but schedule is EST)
    from zoneinfo import ZoneInfo
    est_now = datetime.now(ZoneInfo("America/New_York"))
    start = est_now.date() + timedelta(days=1)  # Start from tomorrow EST
    slots_created = 0
    slots_skipped = 0
    image_errors: list[str] = []

    for day_offset in range(days):
        target_date = start + timedelta(days=day_offset)
        weekday = target_date.weekday()  # 0=Monday

        day_schedule = WEEKLY_SCHEDULE.get(weekday, {})
        if not day_schedule:
            continue

        for time_slot, config in day_schedule.items():
            if config is None:
                continue

            content_type = config["type"]
            posting_time = POSTING_TIMES[time_slot]
            scheduled_at = datetime.combine(target_date, posting_time)

            # Build slot dict matching the format _generate_for_slot expects
            slot = {
                "date": target_date.isoformat(),
                "time_slot": time_slot,
                "content_type": content_type.value,
                "emotional_tone": config["tone"].value,
                "scheduled_at": scheduled_at,
                "theme": "",
                "age_group": "general",
            }

            # Add themes based on content type
            if content_type == ContentType.marriage_monday:
                slot["theme"] = cal.series.get_marriage_theme()
            elif content_type == ContentType.faith_friday:
                slot["theme"] = cal.series.get_hardship_topic()

            try:
                content = gen._generate_for_slot(slot)
                if content:
                    slots_created += 1
                    try:
                        img_pipeline.generate_images_for_content(content)
                        db.commit()
                    except Exception as img_err:
                        logger.error(
                            f"Image/reel pipeline failed for content #{content.id}: {img_err}",
                            exc_info=True,
                        )
                        image_errors.append(f"#{content.id}: {img_err}")
                else:
                    slots_skipped += 1  # Dedup: slot already has content
            except Exception as gen_err:
                logger.error(f"Content generation failed for slot {slot}: {gen_err}", exc_info=True)
                slots_skipped += 1

    db.commit()

    return {
        "success": True,
        "days": days,
        "slots_created": slots_created,
        "slots_skipped": slots_skipped,
        "image_errors": image_errors,
    }


@router.post("/generate-text")
def generate_text(
    body: dict = Body(...),
    db: Session = Depends(get_db_dependency),
) -> dict:
    """Generate text content using Claude API for the creator sandbox.

    Accepts a content_type and returns AI-generated text suitable for that type.
    """
    import anthropic as _anthropic

    from core.config import settings

    content_type = body.get("content_type", "daily_verse")

    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="Anthropic API key not configured")

    # Content-type-specific prompts for the creator sandbox
    type_prompts: dict[str, str] = {
        "daily_verse": (
            "Generate a short, powerful Bible verse with its reference. "
            "Format: the verse text followed by ' - ' and the reference (e.g. Book Chapter:Verse). "
            "Choose an uplifting or reflective verse. Return ONLY the verse and reference, nothing else."
        ),
        "encouragement": (
            "Write a short, heartfelt Christian encouragement message (2-3 sentences). "
            "It should feel personal and uplifting, like a friend speaking hope into someone's day. "
            "Return ONLY the message text, nothing else."
        ),
        "marriage_monday": (
            "Write a short, warm message about marriage and faith (2-3 sentences). "
            "Focus on love, partnership, and God's design for marriage. "
            "Return ONLY the message text, nothing else."
        ),
        "faith_friday": (
            "Write a short, powerful message about persevering through hardship with faith (2-3 sentences). "
            "It should acknowledge real struggle while pointing to hope in God. "
            "Return ONLY the message text, nothing else."
        ),
        "christian_quote": (
            "Share a famous Christian quote from a well-known theologian, pastor, or Christian author. "
            "Format: the quote in quotation marks, followed by ' - ' and the author's name. "
            "Return ONLY the quote and attribution, nothing else."
        ),
        "carousel": (
            "Write a short, insightful Bible teaching point (2-3 sentences) suitable for a carousel post. "
            "Include a relevant Bible verse reference at the end. "
            "Return ONLY the text, nothing else."
        ),
    }

    prompt = type_prompts.get(content_type, type_prompts["daily_verse"])

    try:
        client = _anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        generated_text = ""
        for block in response.content:
            if block.type == "text":
                generated_text += block.text
        generated_text = generated_text.strip()
    except _anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {e}")

    if not generated_text:
        raise HTTPException(status_code=502, detail="Claude returned empty response")

    return {"text": generated_text, "content_type": content_type}


@router.post("/create")
def create_custom_content(
    body: dict = Body(...),
    db: Session = Depends(get_db_dependency),
):
    """Creator sandbox: create a custom post with user-provided text and image.

    Creates a GeneratedContent record with status=pending and no scheduled_at,
    so it sits in the sandbox until the user assigns it to a calendar slot via /move.
    """
    content_type = body.get("content_type", "daily_verse")
    text = body.get("text", "")
    image_source = body.get("image_source", "library")  # library, ai, unsplash
    image_id = body.get("image_id")  # catalog image ID or None
    narration = body.get("narration", True)
    reel_style = body.get("reel_style", "classic")
    ai_prompt = body.get("ai_prompt")  # for AI image generation
    overlay_style = body.get("overlay_style", "creator")  # creator (no card) or card
    font_size = body.get("font_size")  # optional explicit font size (24-80)
    font_family = body.get("font_family")  # optional: georgia, playfair, lato, calibri
    text_color = body.get("text_color")  # optional hex color e.g. "#FFFFFF"

    if not text:
        raise HTTPException(status_code=400, detail="Text content is required")

    # Resolve content_type string to enum
    try:
        resolved_type = ContentType[content_type] if isinstance(content_type, str) else content_type
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content_type: {content_type}. "
                   f"Valid values: {[t.name for t in ContentType]}",
        )

    # Build posting caption: text + CTA + hashtags
    from random import sample
    from core.scraper.hashtag_research import HASHTAGS_LARGE, HASHTAGS_MEDIUM, HASHTAGS_NICHE

    CREATOR_CTAS = [
        "Double-tap if this speaks to you.",
        "Tag someone who needs this today.",
        "Save this for when you need a reminder.",
        "Share this with someone who needs encouragement.",
        "Comment 'Amen' if you believe this.",
        "Follow @stillwatergrace for daily faith.",
    ]

    cta = CREATOR_CTAS[hash(text) % len(CREATOR_CTAS)]
    caption_long = f"{text}\n\n{cta}"

    # Select hashtags: 3 large + 4 medium + 4 niche + branded
    ht_large = sample(HASHTAGS_LARGE, min(3, len(HASHTAGS_LARGE)))
    ht_medium = sample(HASHTAGS_MEDIUM, min(4, len(HASHTAGS_MEDIUM)))
    ht_niche = sample(HASHTAGS_NICHE, min(4, len(HASHTAGS_NICHE)))

    content = GeneratedContent(
        content_type=resolved_type,
        status=ContentStatus.pending,
        hook=text[:80],
        caption_short=text if len(text) <= 150 else text[:150],
        caption_medium=text if len(text) <= 300 else text[:300],
        caption_long=caption_long,
        reel_script_15=text if len(text) <= 200 else text[:200],
        reel_script_30=text,
        emotional_tone=EmotionalTone.reflective,
        image_prompt=ai_prompt,
        is_selected=False,
        hashtags_large=ht_large,
        hashtags_medium=ht_medium,
        hashtags_niche=ht_niche,
    )
    db.add(content)
    db.commit()
    db.refresh(content)

    import logging
    from pathlib import Path

    logger = logging.getLogger(__name__)

    # Resolve the background image path based on source
    reel_url = None
    image_url = None
    raw_path = None

    if image_source == "library" and image_id:
        # Use the selected library image directly
        try:
            from core.images.catalog import ImageCatalog
            catalog = ImageCatalog()
            entry = catalog.find_by_id(image_id)
            if entry:
                lib_path = Path("images/raw") / entry["filename"]
                if lib_path.exists():
                    raw_path = str(lib_path)
                    # Create a GeneratedImage record for the library image
                    lib_record = GeneratedImage(
                        content_id=content.id,
                        provider=ImageProvider.fal if entry.get("provider") == "fal" else ImageProvider.unsplash,
                        format=ImageFormat.feed_4x5,
                        raw_url=raw_path,
                        final_url=f"/static/library/{entry['filename']}",
                        width=1080,
                        height=1350,
                    )
                    db.add(lib_record)
                    db.commit()
                    image_url = lib_record.final_url
        except Exception as e:
            logger.error(f"Creator library image failed: {e}")

    elif image_source == "ai" and ai_prompt:
        # Generate AI image via fal.ai
        try:
            ai_result = generate_ai_image(content.id, prompt=ai_prompt, preset=None, db=db)
            if ai_result.get("images"):
                image_url = ai_result["images"][0].get("url")
            # Find the raw image for reel rendering
            fal_img = (
                db.query(GeneratedImage)
                .filter_by(content_id=content.id, provider=ImageProvider.fal)
                .filter(GeneratedImage.raw_url.isnot(None))
                .first()
            )
            if fal_img:
                raw_path = fal_img.raw_url
        except Exception as e:
            logger.error(f"Creator AI image generation failed: {e}")

    else:
        # Default (unsplash or no image selected): use Unsplash image pipeline
        try:
            # Set image_prompt so Unsplash pipeline has something to search
            if not content.image_prompt:
                content.image_prompt = f"{content_type} faith background"
                db.flush()
            from core.images.image_processor import ImagePipeline
            pipeline = ImagePipeline(db)
            pipeline.generate_images_for_content(content)
            db.commit()
            # Find the raw image
            unsplash_img = (
                db.query(GeneratedImage)
                .filter_by(content_id=content.id)
                .filter(GeneratedImage.raw_url.isnot(None))
                .first()
            )
            if unsplash_img:
                raw_path = unsplash_img.raw_url
        except Exception as e:
            logger.error(f"Creator image pipeline failed: {e}")

    db.refresh(content)
    return {
        "success": True,
        "content_id": content.id,
        "id": content.id,
        "status": "pending",
        "image_source": image_source,
        "reel_url": reel_url,
        "image_url": image_url,
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


@router.post("/{content_id}/select")
def select_post(content_id: int, db: Session = Depends(get_db_dependency)):
    """Select this post as the active one for its time slot.

    Deselects all other posts in the same 1-hour window and marks this one as selected.
    """
    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    if not content.scheduled_at:
        raise HTTPException(status_code=400, detail="Content has no scheduled time")

    # Deselect all other posts in the same time slot (same date + same hour)
    slot_start = content.scheduled_at.replace(minute=0, second=0, microsecond=0)
    slot_end = slot_start + timedelta(hours=1)

    db.query(GeneratedContent).filter(
        GeneratedContent.scheduled_at >= slot_start,
        GeneratedContent.scheduled_at < slot_end,
        GeneratedContent.id != content_id,
    ).update({"is_selected": False})

    content.is_selected = True
    db.commit()
    return {"success": True, "selected_id": content_id}


SLOT_TIMES = {"morning": (6, 30), "noon": (12, 0)}


@router.post("/{content_id}/move")
def move_post(content_id: int, body: dict = Body(...), db: Session = Depends(get_db_dependency)):
    """Move a post to a different day/time (for drag-and-drop in the calendar).

    Accepts either:
      - ``time``: explicit HH:MM string (e.g. "16:00") -- preferred
      - ``time_slot``: legacy slot name ("morning" or "noon") -- backward compat
    """
    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    target_date = date.fromisoformat(body["date"])

    # Prefer explicit time, fall back to legacy time_slot
    time_str: Optional[str] = body.get("time")
    if time_str:
        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("out of range")
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid time format: '{time_str}'. Use HH:MM (e.g. '16:00').",
            )
    else:
        time_slot = body.get("time_slot", "morning")
        hour, minute = SLOT_TIMES.get(time_slot, (6, 30))

    content.scheduled_at = datetime.combine(target_date, time(hour, minute))
    content.is_selected = False  # Reset selection when moved
    db.commit()
    return {"success": True, "new_scheduled_at": content.scheduled_at.isoformat()}


@router.delete("/{content_id}")
def delete_post(content_id: int, db: Session = Depends(get_db_dependency)):
    """Delete a post, its associated images, R2 files, and posting logs."""
    content = db.query(GeneratedContent).filter(GeneratedContent.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    if content.status == ContentStatus.posted:
        raise HTTPException(status_code=400, detail="Cannot delete posted content")

    # Delete R2 objects for all images
    images = db.query(GeneratedImage).filter(GeneratedImage.content_id == content_id).all()
    _delete_r2_objects([img.r2_key for img in images if img.r2_key])

    # Delete in FK order: posting_log → images → content
    from database.models import PostingLog
    db.query(PostingLog).filter(PostingLog.content_id == content_id).delete()
    db.query(GeneratedImage).filter(GeneratedImage.content_id == content_id).delete()
    db.delete(content)
    db.commit()
    return {"success": True, "deleted_id": content_id}


def _delete_r2_objects(r2_keys: list[str]) -> int:
    """Delete objects from Cloudflare R2. Returns count of deleted objects."""
    from core.config import settings
    if not settings.has_r2 or not r2_keys:
        return 0

    import logging
    logger = logging.getLogger(__name__)

    try:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.cloudflare_r2_endpoint,
            aws_access_key_id=settings.cloudflare_r2_access_key,
            aws_secret_access_key=settings.cloudflare_r2_secret_key,
        )
        deleted = 0
        for key in r2_keys:
            try:
                s3.delete_object(Bucket=settings.cloudflare_r2_bucket, Key=key)
                deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete R2 object {key}: {e}")
        logger.info(f"Deleted {deleted}/{len(r2_keys)} R2 objects")
        return deleted
    except Exception as e:
        logger.error(f"R2 cleanup failed: {e}")
        return 0


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
        "is_selected": content.is_selected,
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
