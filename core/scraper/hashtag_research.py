"""Hashtag research and management for Instagram content.

Maintains a curated database of hashtags organized by tier (large/medium/niche)
and tracks their performance over time.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import HashtagPerformance

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Curated Hashtag Database
# ──────────────────────────────────────────────

HASHTAGS_LARGE = [
    # Over 1M posts — broad reach
    "#faith", "#christian", "#bible", "#jesus", "#god",
    "#prayer", "#love", "#blessed", "#church", "#worship",
    "#family", "#marriage", "#parenting", "#motivation", "#hope",
    "#scripture", "#godisgood", "#grace", "#christianlife", "#believe",
    "#amen", "#praise", "#grateful", "#thankful", "#inspiration",
    "#godislove", "#jesuschrist", "#faithful", "#bibleverse", "#holybible",
]

HASHTAGS_MEDIUM = [
    # 100K-1M posts — targeted reach
    "#christianmom", "#faithfamily", "#christianmarriage", "#prayerwarrior", "#dailydevotional",
    "#christianliving", "#bibleversedaily", "#faithjourney", "#marriagegoals", "#christianparenting",
    "#godsgrace", "#faithoverfear", "#prayerworks", "#scriptureoftheday", "#walkbyfaith",
    "#christiancouples", "#familyfaith", "#motherofgrace", "#proverbs31woman", "#godsplan",
    "#christcentered", "#worshipmusic", "#sundayservice", "#bibletime", "#faithbased",
    "#christianwomen", "#christianmen", "#godlymarriage", "#parentingwithgrace", "#spiritfilled",
]

HASHTAGS_NICHE = [
    # Under 100K posts — discoverability, less competition
    "#faithandfamily", "#marriagedevo", "#familydevotional", "#christianmomlife", "#prayingwife",
    "#prayinghusband", "#raisingkidsinfaith", "#christiandad", "#godlyparenting", "#bibleforparents",
    "#marriagemonday", "#faithfriday", "#dailybibleverse", "#morningdevotional", "#eveningprayer",
    "#christiancommunity", "#faithwalk", "#marriageencouragement", "#parentingwisdom", "#godlywoman",
    "#faithinhardtimes", "#scripturemeditation", "#christianinspiration", "#faithfulmarriage", "#prayingparents",
    "#godlyfamily", "#wifeylife", "#husbandgoals", "#toddlermom", "#christianteenmom",
]


class HashtagResearcher:
    """Manages hashtag database and provides optimized sets for content."""

    def __init__(self, db: Session):
        self.db = db

    def seed_hashtags(self) -> int:
        """Seed the hashtag database with curated hashtags.

        Call once during initial setup. Idempotent — won't duplicate.
        """
        seeded = 0
        for tier, hashtags in [
            ("large", HASHTAGS_LARGE),
            ("medium", HASHTAGS_MEDIUM),
            ("niche", HASHTAGS_NICHE),
        ]:
            for tag in hashtags:
                existing = (
                    self.db.query(HashtagPerformance)
                    .filter(HashtagPerformance.hashtag == tag)
                    .first()
                )
                if not existing:
                    self.db.add(HashtagPerformance(
                        hashtag=tag,
                        tier=tier,
                        performance_score=50.0,  # Neutral starting score
                        active=True,
                    ))
                    seeded += 1

        self.db.flush()
        logger.info(f"Seeded {seeded} new hashtags")
        return seeded

    def get_hashtag_set(
        self,
        content_type: Optional[str] = None,
        count_per_tier: int = 10,
    ) -> dict[str, list[str]]:
        """Get an optimized hashtag set with tags from each tier.

        Returns dict with keys: 'large', 'medium', 'niche'.
        Prioritizes higher-performing hashtags.
        """
        result = {}

        for tier in ["large", "medium", "niche"]:
            tags = (
                self.db.query(HashtagPerformance)
                .filter(
                    HashtagPerformance.tier == tier,
                    HashtagPerformance.active == True,
                )
                .order_by(HashtagPerformance.performance_score.desc())
                .limit(count_per_tier)
                .all()
            )
            result[tier] = [t.hashtag for t in tags]

        return result

    def update_performance(self, hashtag: str, reach: float, engagement: float) -> None:
        """Update hashtag performance based on post results.

        Called by the analytics module after collecting post data.
        Uses exponential moving average to smooth scores.
        """
        tag = (
            self.db.query(HashtagPerformance)
            .filter(HashtagPerformance.hashtag == hashtag)
            .first()
        )
        if not tag:
            return

        tag.times_used = (tag.times_used or 0) + 1
        tag.last_used_at = datetime.utcnow()

        # Exponential moving average (alpha=0.3 = weight recent results more)
        alpha = 0.3
        if tag.avg_reach_when_used:
            tag.avg_reach_when_used = alpha * reach + (1 - alpha) * tag.avg_reach_when_used
        else:
            tag.avg_reach_when_used = reach

        if tag.avg_engagement_when_used:
            tag.avg_engagement_when_used = alpha * engagement + (1 - alpha) * tag.avg_engagement_when_used
        else:
            tag.avg_engagement_when_used = engagement

        # Update composite score (reach weighted 60%, engagement 40%)
        if tag.avg_reach_when_used and tag.avg_engagement_when_used:
            # Normalize to 0-100 scale (assume 10K reach is 100, 10% engagement is 100)
            reach_score = min(tag.avg_reach_when_used / 10000 * 100, 100)
            engagement_score = min(tag.avg_engagement_when_used / 0.10 * 100, 100)
            tag.performance_score = reach_score * 0.6 + engagement_score * 0.4

        self.db.flush()
