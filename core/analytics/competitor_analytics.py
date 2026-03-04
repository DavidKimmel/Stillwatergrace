"""Competitor analytics and benchmarking.

Aggregates competitor data from snapshots and provides comparative analysis.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import CompetitorSnapshot

logger = logging.getLogger(__name__)


class CompetitorAnalytics:
    """Analyzes competitor data for benchmarking and strategy insights."""

    def __init__(self, db: Session):
        self.db = db

    def get_weekly_comparison(self) -> list[dict]:
        """Get week-over-week comparison for all competitors."""
        now = datetime.utcnow()
        one_week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        results = []
        handles = (
            self.db.query(CompetitorSnapshot.page_handle)
            .distinct()
            .all()
        )

        for (handle,) in handles:
            current = self._get_latest_snapshot(handle, since=one_week_ago)
            previous = self._get_latest_snapshot(handle, since=two_weeks_ago, before=one_week_ago)

            if not current:
                continue

            follower_delta = 0
            if previous and previous.followers and current.followers:
                follower_delta = current.followers - previous.followers

            results.append({
                "handle": handle,
                "followers": current.followers,
                "follower_delta": follower_delta,
                "avg_engagement_rate": current.avg_engagement_rate,
                "posting_frequency": current.posting_frequency_per_week,
                "avg_likes": current.avg_likes_recent,
                "captured_at": current.captured_at.isoformat() if current.captured_at else None,
            })

        return sorted(results, key=lambda x: x.get("followers") or 0, reverse=True)

    def get_growth_trends(self, handle: str, weeks: int = 12) -> list[dict]:
        """Get follower growth trend for a specific competitor."""
        since = datetime.utcnow() - timedelta(weeks=weeks)

        snapshots = (
            self.db.query(CompetitorSnapshot)
            .filter(
                CompetitorSnapshot.page_handle == handle,
                CompetitorSnapshot.captured_at >= since,
            )
            .order_by(CompetitorSnapshot.captured_at.asc())
            .all()
        )

        return [
            {
                "date": s.captured_at.isoformat() if s.captured_at else None,
                "followers": s.followers,
                "engagement_rate": s.avg_engagement_rate,
            }
            for s in snapshots
        ]

    def _get_latest_snapshot(
        self,
        handle: str,
        since: datetime,
        before: Optional[datetime] = None,
    ) -> Optional[CompetitorSnapshot]:
        """Get the most recent snapshot for a handle within a time range."""
        query = (
            self.db.query(CompetitorSnapshot)
            .filter(
                CompetitorSnapshot.page_handle == handle,
                CompetitorSnapshot.captured_at >= since,
            )
        )
        if before:
            query = query.filter(CompetitorSnapshot.captured_at < before)

        return query.order_by(CompetitorSnapshot.captured_at.desc()).first()
