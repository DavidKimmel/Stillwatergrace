"""Analytics API routes."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.session import get_db_dependency
from database.models import (
    AnalyticsSnapshot,
    PostingLog,
    CompetitorSnapshot,
    GeneratedContent,
    ContentType,
    Platform,
    PostingStatus,
)

router = APIRouter()


@router.get("/overview")
def get_analytics_overview(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db_dependency),
):
    """Get high-level analytics overview."""
    since = datetime.utcnow() - timedelta(days=days)

    # Total posts in period
    total_posts = (
        db.query(PostingLog)
        .filter(PostingLog.posted_at >= since, PostingLog.status == PostingStatus.success)
        .count()
    )

    # Aggregate engagement
    engagement = (
        db.query(
            func.sum(AnalyticsSnapshot.likes).label("total_likes"),
            func.sum(AnalyticsSnapshot.comments).label("total_comments"),
            func.sum(AnalyticsSnapshot.saves).label("total_saves"),
            func.sum(AnalyticsSnapshot.shares).label("total_shares"),
            func.sum(AnalyticsSnapshot.reach).label("total_reach"),
            func.avg(AnalyticsSnapshot.engagement_rate).label("avg_engagement_rate"),
        )
        .filter(
            AnalyticsSnapshot.captured_at >= since,
            AnalyticsSnapshot.hours_after_post == 24,  # Use 24hr snapshot
        )
        .first()
    )

    return {
        "period_days": days,
        "total_posts": total_posts,
        "total_likes": engagement.total_likes or 0,
        "total_comments": engagement.total_comments or 0,
        "total_saves": engagement.total_saves or 0,
        "total_shares": engagement.total_shares or 0,
        "total_reach": engagement.total_reach or 0,
        "avg_engagement_rate": round(engagement.avg_engagement_rate or 0, 4),
    }


@router.get("/top-posts")
def get_top_posts(
    days: int = Query(default=30, le=90),
    metric: str = Query(default="saves", regex="^(saves|shares|reach|likes|engagement_rate)$"),
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db_dependency),
):
    """Get top performing posts by a given metric."""
    since = datetime.utcnow() - timedelta(days=days)
    order_col = getattr(AnalyticsSnapshot, metric)

    snapshots = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.captured_at >= since,
            AnalyticsSnapshot.hours_after_post == 24,
        )
        .order_by(order_col.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "content_id": s.content_id,
            "platform": s.platform.value if s.platform else None,
            "likes": s.likes,
            "comments": s.comments,
            "saves": s.saves,
            "shares": s.shares,
            "reach": s.reach,
            "engagement_rate": s.engagement_rate,
            "captured_at": s.captured_at.isoformat() if s.captured_at else None,
        }
        for s in snapshots
    ]


@router.get("/content-type-performance")
def get_content_type_performance(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db_dependency),
):
    """Get average performance by content type."""
    since = datetime.utcnow() - timedelta(days=days)

    results = (
        db.query(
            GeneratedContent.content_type,
            func.count(AnalyticsSnapshot.id).label("post_count"),
            func.avg(AnalyticsSnapshot.saves).label("avg_saves"),
            func.avg(AnalyticsSnapshot.shares).label("avg_shares"),
            func.avg(AnalyticsSnapshot.reach).label("avg_reach"),
            func.avg(AnalyticsSnapshot.engagement_rate).label("avg_engagement"),
        )
        .join(AnalyticsSnapshot, AnalyticsSnapshot.content_id == GeneratedContent.id)
        .filter(
            AnalyticsSnapshot.captured_at >= since,
            AnalyticsSnapshot.hours_after_post == 24,
        )
        .group_by(GeneratedContent.content_type)
        .all()
    )

    return [
        {
            "content_type": r.content_type.value if r.content_type else None,
            "post_count": r.post_count,
            "avg_saves": round(r.avg_saves or 0, 1),
            "avg_shares": round(r.avg_shares or 0, 1),
            "avg_reach": round(r.avg_reach or 0, 1),
            "avg_engagement": round(r.avg_engagement or 0, 4),
        }
        for r in results
    ]


@router.get("/competitors")
def get_competitor_data(
    db: Session = Depends(get_db_dependency),
):
    """Get latest competitor snapshots."""
    # Get most recent snapshot for each competitor
    subq = (
        db.query(
            CompetitorSnapshot.page_handle,
            func.max(CompetitorSnapshot.captured_at).label("latest"),
        )
        .group_by(CompetitorSnapshot.page_handle)
        .subquery()
    )

    snapshots = (
        db.query(CompetitorSnapshot)
        .join(
            subq,
            (CompetitorSnapshot.page_handle == subq.c.page_handle)
            & (CompetitorSnapshot.captured_at == subq.c.latest),
        )
        .all()
    )

    return [
        {
            "handle": s.page_handle,
            "followers": s.followers,
            "post_count": s.post_count,
            "avg_engagement_rate": s.avg_engagement_rate,
            "posting_frequency_per_week": s.posting_frequency_per_week,
            "captured_at": s.captured_at.isoformat() if s.captured_at else None,
        }
        for s in snapshots
    ]
