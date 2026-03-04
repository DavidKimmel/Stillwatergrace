"""Instagram Insights collector.

Pulls engagement metrics for posted content at configured intervals
(1hr, 24hr, 7 days) and stores snapshots for trend analysis.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.posting.instagram_client import InstagramClient
from database.models import (
    PostingLog,
    PostingStatus,
    Platform,
    AnalyticsSnapshot,
)

logger = logging.getLogger(__name__)


class InsightsCollector:
    """Collects Instagram insights for posted content."""

    def __init__(self, db: Session):
        self.db = db
        self.client = InstagramClient() if settings.has_instagram else None

    def collect_for_age(self, hours_after: int) -> int:
        """Collect analytics for posts that are approximately N hours old.

        Args:
            hours_after: Target age of posts (1, 24, or 168 for 7 days)

        Returns:
            Number of posts collected.
        """
        if not self.client:
            logger.warning("Instagram not configured, skipping insights collection")
            return 0

        # Find posts from the target time window (±30 min tolerance)
        target_time = datetime.utcnow() - timedelta(hours=hours_after)
        window_start = target_time - timedelta(minutes=30)
        window_end = target_time + timedelta(minutes=30)

        posts = (
            self.db.query(PostingLog)
            .filter(
                PostingLog.platform == Platform.instagram,
                PostingLog.status == PostingStatus.success,
                PostingLog.posted_at >= window_start,
                PostingLog.posted_at <= window_end,
                PostingLog.platform_media_id.isnot(None),
            )
            .all()
        )

        collected = 0
        for post in posts:
            # Check if we already have a snapshot at this interval
            existing = (
                self.db.query(AnalyticsSnapshot)
                .filter(
                    AnalyticsSnapshot.content_id == post.content_id,
                    AnalyticsSnapshot.hours_after_post == hours_after,
                )
                .first()
            )
            if existing:
                continue

            try:
                insights = self.client.get_media_insights(post.platform_media_id)
                if insights:
                    snapshot = self._create_snapshot(post, insights, hours_after)
                    self.db.add(snapshot)
                    collected += 1
            except Exception as e:
                logger.error(f"Failed to collect insights for post {post.id}: {e}")

        self.db.flush()
        logger.info(f"Collected {hours_after}hr insights for {collected} posts")
        return collected

    def _create_snapshot(
        self,
        post: PostingLog,
        insights: dict,
        hours_after: int,
    ) -> AnalyticsSnapshot:
        """Create an analytics snapshot from raw insights data."""
        likes = insights.get("likes", 0)
        comments = insights.get("comments", 0)
        saves = insights.get("saved", 0)
        shares = insights.get("shares", 0)
        reach = insights.get("reach", 0)
        impressions = insights.get("impressions", 0)

        # Calculate engagement rate
        engagement_rate = 0.0
        if reach > 0:
            engagement_rate = (likes + comments + saves + shares) / reach

        return AnalyticsSnapshot(
            content_id=post.content_id,
            posting_log_id=post.id,
            platform=Platform.instagram,
            hours_after_post=hours_after,
            likes=likes,
            comments=comments,
            shares=shares,
            saves=saves,
            reach=reach,
            impressions=impressions,
            engagement_rate=round(engagement_rate, 6),
        )
