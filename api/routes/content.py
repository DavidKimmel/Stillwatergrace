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
