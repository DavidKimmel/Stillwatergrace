"""Weekly series theme management.

Manages rotating themes for Marriage Monday, Parenting Wednesday,
and Faith Friday series to ensure variety and relevance.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import GeneratedContent, ContentType

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Theme Libraries
# ──────────────────────────────────────────────

MARRIAGE_THEMES = [
    "communication",
    "conflict resolution",
    "date nights and intentional time",
    "spiritual leadership in marriage",
    "intimacy and emotional connection",
    "forgiveness in marriage",
    "seasons of change together",
    "gratitude for your spouse",
    "praying together as a couple",
    "serving each other sacrificially",
    "financial unity and stewardship",
    "supporting each other's dreams",
    "keeping romance alive with kids",
    "handling in-law relationships",
    "rebuilding trust",
    "celebrating differences",
]

PARENTING_THEMES = {
    "toddlers": [
        "patience in the chaos",
        "teaching first obedience with grace",
        "bedtime routines and prayer",
        "handling tantrums with calm",
        "building security through consistency",
        "teaching kindness to little ones",
    ],
    "elementary": [
        "building confidence and identity in Christ",
        "navigating friendships",
        "homework and responsibility",
        "teaching kids to pray",
        "handling screen time wisely",
        "teaching generosity",
    ],
    "teens": [
        "keeping communication open",
        "faith during doubt seasons",
        "social media and identity",
        "dating and purity conversations",
        "letting go while holding on",
        "preparing for independence",
    ],
    "general": [
        "patience as a spiritual discipline",
        "apologizing to your kids",
        "creating family traditions",
        "discipline vs punishment",
        "teaching kids about money",
        "sibling conflict resolution",
        "building a praying family",
        "modeling faith in everyday moments",
    ],
}

PARENTING_AGE_ROTATION = ["toddlers", "elementary", "teens", "general"]

HARDSHIP_TOPICS = [
    "grief and loss",
    "financial stress",
    "health struggles",
    "relational conflict",
    "doubt and spiritual dryness",
    "waiting seasons",
    "anxiety and worry",
    "loneliness in a crowd",
    "burnout and exhaustion",
    "disappointment with God's timing",
    "miscarriage and infertility",
    "career uncertainty",
]

VIRAL_FORMAT_ROTATION = [
    "fill_in_blank",
    "this_or_that",
    "conviction_quote",
    "parenting_list",
    "marriage_challenge",
]


class SeriesManager:
    """Manages weekly theme selection and rotation for content series."""

    def __init__(self, db: Session):
        self.db = db

    def get_marriage_theme(self) -> str:
        """Get this week's Marriage Monday theme, avoiding recent repeats."""
        return self._pick_next_theme(
            themes=MARRIAGE_THEMES,
            content_type=ContentType.marriage_monday,
            lookback_weeks=8,
        )

    def get_parenting_theme(self) -> tuple[str, str]:
        """Get this week's Parenting Wednesday age group and theme.

        Returns (age_group, theme).
        """
        # Rotate through age groups
        age_group = self._get_current_age_group()
        themes = PARENTING_THEMES.get(age_group, PARENTING_THEMES["general"])

        theme = self._pick_next_theme(
            themes=themes,
            content_type=ContentType.parenting_wednesday,
            lookback_weeks=6,
        )

        return age_group, theme

    def get_hardship_topic(self) -> str:
        """Get this week's Faith Friday hardship topic."""
        return self._pick_next_theme(
            themes=HARDSHIP_TOPICS,
            content_type=ContentType.faith_friday,
            lookback_weeks=8,
        )

    def get_viral_format(self) -> str:
        """Get this week's viral content format."""
        # Simple weekly rotation
        week_number = datetime.now(timezone.utc).isocalendar()[1]
        index = week_number % len(VIRAL_FORMAT_ROTATION)
        return VIRAL_FORMAT_ROTATION[index]

    def _pick_next_theme(
        self,
        themes: list[str],
        content_type: ContentType,
        lookback_weeks: int = 8,
    ) -> str:
        """Pick the next theme from a list, avoiding recently used ones.

        Looks at the last N weeks of generated content to find which
        themes have been used, and picks one that hasn't.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(weeks=lookback_weeks)

        # Get recently used themes
        recent = (
            self.db.query(GeneratedContent.weekly_theme)
            .filter(
                GeneratedContent.content_type == content_type,
                GeneratedContent.created_at >= cutoff,
                GeneratedContent.weekly_theme.isnot(None),
            )
            .all()
        )
        recent_themes = {r.weekly_theme for r in recent if r.weekly_theme}

        # Find unused themes
        available = [t for t in themes if t not in recent_themes]

        if not available:
            # All used recently — pick least recently used
            logger.info(f"All {content_type.value} themes used in last {lookback_weeks} weeks, recycling")
            oldest = (
                self.db.query(GeneratedContent.weekly_theme)
                .filter(
                    GeneratedContent.content_type == content_type,
                    GeneratedContent.weekly_theme.isnot(None),
                )
                .order_by(GeneratedContent.created_at.asc())
                .first()
            )
            return oldest.weekly_theme if oldest else themes[0]

        # Pick the first available (maintains a consistent rotation order)
        return available[0]

    def _get_current_age_group(self) -> str:
        """Get the current week's parenting age group based on weekly rotation."""
        week_number = datetime.now(timezone.utc).isocalendar()[1]
        index = week_number % len(PARENTING_AGE_ROTATION)
        return PARENTING_AGE_ROTATION[index]
