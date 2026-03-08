"""Performance analysis engine.

Pure Python rules engine — no LLM calls. Analyzes own content performance
and competitor activity to generate actionable recommendations.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from database.models import (
    AnalyticsSnapshot,
    GeneratedContent,
    GeneratedImage,
    PostingLog,
    CompetitorPost,
    Platform,
    PostingStatus,
    ImageFormat,
)

logger = logging.getLogger(__name__)

MIN_POSTS_FOR_RECS = 3
OUTPERFORM_RATIO = 2.0
UNDERPERFORM_RATIO = 0.5
TIME_ADVANTAGE_RATIO = 1.3
FORMAT_SHIFT_THRESHOLD = 20.0


class PerformanceAnalyzer:
    """Generates data-driven content recommendations."""

    def __init__(self, db: Session):
        self.db = db

    def get_content_type_performance(self, days: int = 30) -> list[dict]:
        """Average metrics grouped by content type."""
        since = datetime.utcnow() - timedelta(days=days)
        latest_snap = self._latest_snapshots_subquery(since)

        results = (
            self.db.query(
                GeneratedContent.content_type,
                func.count(AnalyticsSnapshot.id).label("post_count"),
                func.avg(AnalyticsSnapshot.engagement_rate).label("avg_engagement"),
                func.avg(AnalyticsSnapshot.reach).label("avg_reach"),
                func.avg(AnalyticsSnapshot.saves).label("avg_saves"),
                func.avg(AnalyticsSnapshot.shares).label("avg_shares"),
                func.avg(AnalyticsSnapshot.likes).label("avg_likes"),
            )
            .join(latest_snap, AnalyticsSnapshot.id == latest_snap.c.max_id)
            .join(GeneratedContent, GeneratedContent.id == AnalyticsSnapshot.content_id)
            .group_by(GeneratedContent.content_type)
            .all()
        )

        return [
            {
                "content_type": r.content_type.value if hasattr(r.content_type, 'value') else str(r.content_type),
                "post_count": r.post_count,
                "avg_engagement": round(float(r.avg_engagement or 0), 4),
                "avg_reach": round(float(r.avg_reach or 0), 1),
                "avg_saves": round(float(r.avg_saves or 0), 1),
                "avg_shares": round(float(r.avg_shares or 0), 1),
                "avg_likes": round(float(r.avg_likes or 0), 1),
            }
            for r in results
        ]

    def get_format_performance(self, days: int = 30) -> list[dict]:
        """Average metrics grouped by media format (reel/carousel/image)."""
        since = datetime.utcnow() - timedelta(days=days)
        latest_snap = self._latest_snapshots_subquery(since)

        results = []
        for fmt_label, fmt_filter in [
            ("reel", ImageFormat.reel_9x16),
            ("image", ImageFormat.feed_4x5),
        ]:
            content_ids = (
                self.db.query(GeneratedImage.content_id)
                .filter(GeneratedImage.format == fmt_filter)
                .distinct()
                .subquery()
            )

            row = (
                self.db.query(
                    func.count(AnalyticsSnapshot.id).label("post_count"),
                    func.avg(AnalyticsSnapshot.engagement_rate).label("avg_engagement"),
                    func.avg(AnalyticsSnapshot.reach).label("avg_reach"),
                    func.avg(AnalyticsSnapshot.saves).label("avg_saves"),
                    func.avg(AnalyticsSnapshot.shares).label("avg_shares"),
                )
                .join(latest_snap, AnalyticsSnapshot.id == latest_snap.c.max_id)
                .filter(AnalyticsSnapshot.content_id.in_(content_ids))
                .first()
            )

            if row and row.post_count:
                results.append({
                    "media_format": fmt_label,
                    "post_count": row.post_count,
                    "avg_engagement": round(float(row.avg_engagement or 0), 4),
                    "avg_reach": round(float(row.avg_reach or 0), 1),
                    "avg_saves": round(float(row.avg_saves or 0), 1),
                    "avg_shares": round(float(row.avg_shares or 0), 1),
                })

        return results

    def get_time_slot_performance(self, days: int = 30) -> list[dict]:
        """Average metrics grouped by scheduled hour."""
        since = datetime.utcnow() - timedelta(days=days)
        latest_snap = self._latest_snapshots_subquery(since)

        results = (
            self.db.query(
                extract("hour", GeneratedContent.scheduled_at).label("hour"),
                func.count(AnalyticsSnapshot.id).label("post_count"),
                func.avg(AnalyticsSnapshot.engagement_rate).label("avg_engagement"),
                func.avg(AnalyticsSnapshot.reach).label("avg_reach"),
            )
            .join(latest_snap, AnalyticsSnapshot.id == latest_snap.c.max_id)
            .join(GeneratedContent, GeneratedContent.id == AnalyticsSnapshot.content_id)
            .filter(GeneratedContent.scheduled_at.isnot(None))
            .group_by(extract("hour", GeneratedContent.scheduled_at))
            .all()
        )

        return [
            {
                "hour": int(r.hour),
                "label": "Morning (6:30 AM)" if int(r.hour) < 10 else "Noon (12:00 PM)",
                "post_count": r.post_count,
                "avg_engagement": round(float(r.avg_engagement or 0), 4),
                "avg_reach": round(float(r.avg_reach or 0), 1),
            }
            for r in results
        ]

    def get_competitor_activity(self, days: int = 14) -> list[dict]:
        """Summarize competitor posting activity."""
        since = datetime.utcnow() - timedelta(days=days)

        competitors = {}
        posts = (
            self.db.query(CompetitorPost)
            .filter(CompetitorPost.scraped_at >= since)
            .order_by(CompetitorPost.posted_at.desc())
            .all()
        )

        for post in posts:
            handle = post.competitor_handle
            if handle not in competitors:
                competitors[handle] = {"posts": [], "format_counts": {}}
            competitors[handle]["posts"].append({
                "media_type": post.media_type,
                "caption_preview": (post.caption or "")[:100],
                "hashtag_count": len(post.hashtags or []),
                "posted_at": post.posted_at.isoformat() if post.posted_at else None,
                "permalink": post.permalink,
            })
            mt = post.media_type
            competitors[handle]["format_counts"][mt] = (
                competitors[handle]["format_counts"].get(mt, 0) + 1
            )

        result = []
        for handle, data in competitors.items():
            total = sum(data["format_counts"].values())
            format_distribution = {
                k: round(v / total * 100, 1) for k, v in data["format_counts"].items()
            } if total > 0 else {}

            posts_per_week = len(data["posts"]) / max(days / 7, 1)

            result.append({
                "handle": handle,
                "post_count": len(data["posts"]),
                "posts_per_week": round(posts_per_week, 1),
                "format_distribution": format_distribution,
                "recent_posts": data["posts"][:10],
            })

        return result

    def generate_recommendations(self, days: int = 30) -> list[dict]:
        """Generate ranked list of 3-5 actionable recommendations."""
        all_recs = []

        type_data = self.get_content_type_performance(days)
        type_rows = [_dict_to_row(d) for d in type_data]
        all_recs.extend(self._content_type_recommendations(type_rows))

        format_data = self.get_format_performance(days)
        format_rows = [_dict_to_row(d) for d in format_data]
        all_recs.extend(self._format_recommendations(format_rows))

        time_data = self.get_time_slot_performance(days)
        time_rows = [_dict_to_row(d) for d in time_data]
        all_recs.extend(self._time_recommendations(time_rows))

        comp_data = self.get_competitor_activity(days)
        current_dist = {c["handle"]: c["format_distribution"] for c in comp_data}
        older_data = self.get_competitor_activity(days * 2)
        previous_dist = {c["handle"]: c["format_distribution"] for c in older_data}
        all_recs.extend(self._competitor_recommendations(current_dist, previous_dist))

        priority = {"high": 0, "medium": 1, "low": 2}
        all_recs.sort(key=lambda r: priority.get(r.get("confidence", "low"), 2))

        return all_recs[:5]

    def _content_type_recommendations(self, type_data: list) -> list[dict]:
        recs = []
        total_posts = sum(getattr(r, "post_count", 0) for r in type_data)
        if total_posts < MIN_POSTS_FOR_RECS:
            return recs

        avg_engagement = (
            sum(getattr(r, "avg_engagement", 0) for r in type_data) / len(type_data)
            if type_data else 0
        )

        for r in type_data:
            eng = getattr(r, "avg_engagement", 0)
            ct = getattr(r, "content_type", "unknown")
            ct_label = str(ct).replace("_", " ").title()
            count = getattr(r, "post_count", 0)

            if eng >= avg_engagement * OUTPERFORM_RATIO and count >= 2:
                recs.append({
                    "title": f"Double down on {ct_label}",
                    "why": (
                        f"{ct_label} averages {eng:.1%} engagement vs "
                        f"{avg_engagement:.1%} overall — {eng/avg_engagement:.1f}x above average."
                    ),
                    "confidence": self._confidence(count),
                    "source": "performance",
                })

            if eng <= avg_engagement * UNDERPERFORM_RATIO and count >= 3:
                recs.append({
                    "title": f"Rethink {ct_label} approach",
                    "why": (
                        f"{ct_label} averages only {eng:.1%} engagement "
                        f"({avg_engagement:.1%} overall). Consider refreshing the format or reducing frequency."
                    ),
                    "confidence": self._confidence(count),
                    "source": "performance",
                })

        return recs

    def _format_recommendations(self, format_data: list) -> list[dict]:
        recs = []
        if not format_data:
            return recs

        total_posts = sum(getattr(r, "post_count", 0) for r in format_data)
        if total_posts < MIN_POSTS_FOR_RECS:
            return recs

        avg_reach = (
            sum(getattr(r, "avg_reach", 0) for r in format_data) / len(format_data)
            if format_data else 0
        )

        for r in format_data:
            reach = getattr(r, "avg_reach", 0)
            fmt = getattr(r, "media_format", "unknown")
            fmt_label = str(fmt).title()
            count = getattr(r, "post_count", 0)
            saves = getattr(r, "avg_saves", 0)

            if reach >= avg_reach * OUTPERFORM_RATIO and count >= 2:
                recs.append({
                    "title": f"Produce more {fmt_label}s",
                    "why": (
                        f"{fmt_label}s average {reach:.0f} reach vs {avg_reach:.0f} overall "
                        f"({reach/avg_reach:.1f}x). Also averaging {saves:.1f} saves per post."
                    ),
                    "confidence": self._confidence(count),
                    "source": "performance",
                })

        return recs

    def _time_recommendations(self, time_data: list) -> list[dict]:
        recs = []
        if len(time_data) < 2:
            return recs

        total_posts = sum(getattr(r, "post_count", 0) for r in time_data)
        if total_posts < MIN_POSTS_FOR_RECS:
            return recs

        sorted_by_eng = sorted(time_data, key=lambda r: getattr(r, "avg_engagement", 0), reverse=True)
        best = sorted_by_eng[0]
        worst = sorted_by_eng[-1]

        best_eng = getattr(best, "avg_engagement", 0)
        worst_eng = getattr(worst, "avg_engagement", 0)
        best_hour = getattr(best, "hour", 0)
        worst_hour = getattr(worst, "hour", 0)

        if worst_eng > 0 and best_eng / worst_eng >= TIME_ADVANTAGE_RATIO:
            best_label = "Morning" if int(best_hour) < 10 else "Noon"
            recs.append({
                "title": f"{best_label} posts outperform",
                "why": (
                    f"Posts at {int(best_hour)}:00 average {best_eng:.1%} engagement vs "
                    f"{worst_eng:.1%} at {int(worst_hour)}:00 — "
                    f"{best_eng/worst_eng:.1f}x better."
                ),
                "confidence": self._confidence(
                    min(getattr(best, "post_count", 0), getattr(worst, "post_count", 0))
                ),
                "source": "performance",
            })

        return recs

    def _competitor_recommendations(self, current: dict[str, dict], previous: dict[str, dict]) -> list[dict]:
        recs = []
        format_labels = {"VIDEO": "Reels", "IMAGE": "Images", "CAROUSEL_ALBUM": "Carousels"}

        for handle, curr_dist in current.items():
            prev_dist = previous.get(handle, {})
            if not prev_dist:
                continue

            for fmt, curr_pct in curr_dist.items():
                prev_pct = prev_dist.get(fmt, 0)
                shift = curr_pct - prev_pct
                fmt_label = format_labels.get(fmt, fmt)

                if shift >= FORMAT_SHIFT_THRESHOLD:
                    recs.append({
                        "title": f"Competitor shifting to {fmt_label}",
                        "why": (
                            f"@{handle} increased {fmt_label} from {prev_pct:.0f}% to "
                            f"{curr_pct:.0f}% of posts (+{shift:.0f}pp)."
                        ),
                        "confidence": "medium",
                        "source": "competitor",
                    })

        return recs

    @staticmethod
    def _confidence(post_count: int) -> str:
        if post_count >= 10:
            return "high"
        elif post_count >= 5:
            return "medium"
        return "low"

    def _latest_snapshots_subquery(self, since: datetime):
        return (
            self.db.query(
                AnalyticsSnapshot.content_id,
                func.max(AnalyticsSnapshot.id).label("max_id"),
            )
            .filter(AnalyticsSnapshot.captured_at >= since)
            .group_by(AnalyticsSnapshot.content_id)
            .subquery()
        )


def _dict_to_row(d: dict):
    """Convert dict to object with attribute access for rule methods."""
    class Row:
        pass
    row = Row()
    for k, v in d.items():
        setattr(row, k, v)
    return row
