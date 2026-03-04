"""Dashboard overview API routes."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.session import get_db_dependency
from database.models import (
    GeneratedContent,
    PostingLog,
    ContentStatus,
    PostingStatus,
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

    # Revenue this month
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = (
        db.query(func.sum(RevenueLog.amount))
        .filter(RevenueLog.recorded_at >= month_start)
        .scalar()
    ) or 0

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
        "revenue_this_month": round(monthly_revenue, 2),
        "generated_at": now.isoformat(),
    }
