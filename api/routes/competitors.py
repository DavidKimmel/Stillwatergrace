"""Competitor analysis API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.models import CompetitorPost
from database.session import get_db_dependency

router = APIRouter(prefix="/competitors", tags=["competitors"])


@router.get("/top-posts")
def get_top_competitor_posts(
    limit: int = Query(10, ge=1, le=50),
    handle: Optional[str] = Query(None),
    media_type: Optional[str] = Query(None),
    db: Session = Depends(get_db_dependency),
) -> dict:
    """Get top competitor posts sorted by most recent.

    Note: CompetitorPost has no engagement metrics (likes/comments),
    so results are sorted by posted_at descending (newest first).
    """
    query = db.query(CompetitorPost)

    if handle:
        query = query.filter(CompetitorPost.competitor_handle == handle)
    if media_type:
        query = query.filter(CompetitorPost.media_type == media_type)

    posts = (
        query
        .order_by(CompetitorPost.posted_at.desc().nullslast())
        .limit(limit)
        .all()
    )

    return {
        "posts": [
            {
                "id": p.id,
                "handle": p.competitor_handle,
                "platform_media_id": p.platform_media_id,
                "media_type": p.media_type,
                "caption": p.caption,
                "hashtags": p.hashtags or [],
                "hashtag_count": len(p.hashtags) if p.hashtags else 0,
                "posted_at": p.posted_at.isoformat() if p.posted_at else None,
                "permalink": p.permalink,
                "scraped_at": p.scraped_at.isoformat() if p.scraped_at else None,
            }
            for p in posts
        ],
        "total": len(posts),
    }
