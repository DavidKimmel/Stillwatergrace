"""Dashboard overview API routes."""

import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.session import get_db_dependency
from database.models import (
    GeneratedContent,
    GeneratedImage,
    PostingLog,
    ContentStatus,
    PostingStatus,
    Platform,
    AnalyticsSnapshot,
    RevenueLog,
)

router = APIRouter()


@router.get("/overview")
def get_dashboard_overview(db: Session = Depends(get_db_dependency)):
    """Get dashboard overview with key metrics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Content queue stats
    pending_count = (
        db.query(func.count(GeneratedContent.id))
        .filter(GeneratedContent.status == ContentStatus.pending)
        .scalar()
    )
    approved_count = (
        db.query(func.count(GeneratedContent.id))
        .filter(GeneratedContent.status == ContentStatus.approved)
        .scalar()
    )
    scheduled_today = (
        db.query(func.count(GeneratedContent.id))
        .filter(
            GeneratedContent.scheduled_at >= today_start,
            GeneratedContent.scheduled_at < today_start + timedelta(days=1),
            GeneratedContent.status == ContentStatus.approved,
        )
        .scalar()
    )

    # Posting stats this week
    posts_this_week = (
        db.query(func.count(PostingLog.id))
        .filter(
            PostingLog.posted_at >= week_ago,
            PostingLog.status == PostingStatus.success,
        )
        .scalar()
    )
    failed_this_week = (
        db.query(func.count(PostingLog.id))
        .filter(
            PostingLog.posted_at >= week_ago,
            PostingLog.status == PostingStatus.failed,
        )
        .scalar()
    )

    # Per-platform posting stats
    platform_stats = {}
    for platform in [Platform.instagram, Platform.facebook, Platform.tiktok]:
        success_count = (
            db.query(func.count(PostingLog.id))
            .filter(
                PostingLog.posted_at >= week_ago,
                PostingLog.platform == platform,
                PostingLog.status == PostingStatus.success,
            )
            .scalar()
        )
        failed_count = (
            db.query(func.count(PostingLog.id))
            .filter(
                PostingLog.posted_at >= week_ago,
                PostingLog.platform == platform,
                PostingLog.status == PostingStatus.failed,
            )
            .scalar()
        )
        platform_stats[platform.value] = {
            "successful": success_count,
            "failed": failed_count,
        }

    # Revenue this month
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = (
        db.query(func.sum(RevenueLog.amount))
        .filter(RevenueLog.recorded_at >= month_start)
        .scalar()
    ) or 0

    # Top performer — most recent successfully posted content
    top_performer = None
    recent_posted = (
        db.query(GeneratedContent)
        .join(PostingLog, PostingLog.content_id == GeneratedContent.id)
        .filter(
            PostingLog.posted_at >= week_ago,
            PostingLog.status == PostingStatus.success,
        )
        .order_by(PostingLog.posted_at.desc())
        .first()
    )
    if recent_posted:
        # Get posting platforms for this content
        platforms_posted = (
            db.query(PostingLog.platform)
            .filter(
                PostingLog.content_id == recent_posted.id,
                PostingLog.status == PostingStatus.success,
            )
            .all()
        )
        # Get image URL if available
        image = (
            db.query(GeneratedImage)
            .filter(GeneratedImage.content_id == recent_posted.id)
            .first()
        )
        image_url = None
        if image and image.final_url:
            url = image.final_url
            if url and not url.startswith("http"):
                image_url = f"/static/images/{os.path.basename(url)}"
            else:
                image_url = url

        posted_at = max(
            (log.posted_at for log in recent_posted.posting_logs if log.posted_at),
            default=None,
        )
        top_performer = {
            "id": recent_posted.id,
            "content_type": recent_posted.content_type.value if recent_posted.content_type else None,
            "hook": recent_posted.hook,
            "posted_at": posted_at.isoformat() if posted_at else None,
            "platforms": [p[0].value for p in platforms_posted],
            "image_url": image_url,
        }

    return {
        "content_queue": {
            "pending": pending_count,
            "approved": approved_count,
            "scheduled_today": scheduled_today,
        },
        "posting_this_week": {
            "successful": posts_this_week,
            "failed": failed_this_week,
        },
        "posting_by_platform": platform_stats,
        "revenue_this_month": round(monthly_revenue, 2),
        "top_performer": top_performer,
        "generated_at": now.isoformat(),
    }


@router.get("/email-stats")
def get_email_stats():
    """Get email subscriber stats from ConvertKit."""
    from core.email.convertkit_client import ConvertKitClient

    client = ConvertKitClient()
    return {
        "total_subscribers": client.get_subscriber_count(),
        "form_subscribers": client.get_form_subscribers(),
    }
