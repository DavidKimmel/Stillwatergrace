"""Google Trends scraper for faith and family trending topics.

Uses pytrends (unofficial Google Trends API) to discover what people are
searching for in the Christian/family space. Results feed into the content
generation pipeline.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import TrendingContent, TrendSource

logger = logging.getLogger(__name__)

# Keyword groups to track — rotated across calls to avoid rate limits
KEYWORD_GROUPS = [
    # Faith & Bible
    ["christian", "faith", "prayer", "bible verse", "scripture"],
    ["god's love", "jesus", "holy spirit", "grace", "forgiveness"],
    ["church", "worship", "devotional", "spiritual growth", "hope"],
    # Marriage
    ["christian marriage", "marriage advice", "husband wife", "marriage prayer", "love languages"],
    ["marriage counseling", "date night ideas", "strengthen marriage", "marriage goals", "healthy marriage tips"],
    # Parenting
    ["christian parenting", "raise kids faith", "family devotion", "parenting tips", "mom prayer"],
    ["teaching kids bible", "family prayer", "christian mom", "bedtime prayer kids", "faith based family"],
    # Life challenges
    ["faith in hard times", "trusting god", "overcoming anxiety", "grief and faith", "waiting on god"],
]


class GoogleTrendsClient:
    """Fetches trending topics from Google Trends related to faith/family."""

    def __init__(self, db: Session):
        self.db = db

    def fetch_trending_topics(self) -> int:
        """Fetch trending topics for all keyword groups.

        Returns the number of trending topics found and stored.
        """
        try:
            from pytrends.request import TrendReq
        except ImportError:
            logger.error("pytrends not installed")
            return 0

        pytrends = TrendReq(hl="en-US", tz=300)  # EST timezone offset
        total_stored = 0

        for group in KEYWORD_GROUPS:
            try:
                count = self._fetch_group(pytrends, group)
                total_stored += count
            except Exception as e:
                logger.warning(f"Failed to fetch trends for group {group}: {e}")
                continue

        return total_stored

    def _fetch_group(self, pytrends, keywords: list[str]) -> int:
        """Fetch trends for a single keyword group."""
        try:
            pytrends.build_payload(keywords, timeframe="now 7-d", geo="US")
        except Exception as e:
            logger.warning(f"Failed to build payload for {keywords}: {e}")
            return 0

        stored = 0

        # Get related queries (rising = newly popular)
        try:
            related = pytrends.related_queries()
            for keyword, data in related.items():
                if data and data.get("rising") is not None:
                    rising_df = data["rising"]
                    if rising_df is not None and not rising_df.empty:
                        for _, row in rising_df.head(5).iterrows():
                            query = row.get("query", "")
                            value = row.get("value", 0)

                            if not query or not self._is_relevant(query):
                                continue

                            # Score: normalize value to 0-100
                            score = min(float(value) / 5000 * 100, 100.0) if value else 0

                            trend = TrendingContent(
                                source=TrendSource.google_trends,
                                topic=query,
                                score=score,
                                raw_data={
                                    "keyword_group": keywords,
                                    "parent_keyword": keyword,
                                    "rising_value": int(value) if value else 0,
                                    "type": "rising_query",
                                },
                                engagement_signals={"rising_value": int(value) if value else 0},
                            )
                            self.db.add(trend)
                            stored += 1
        except Exception as e:
            logger.warning(f"Failed to get related queries: {e}")

        # Get interest over time to identify which keywords are peaking
        try:
            interest = pytrends.interest_over_time()
            if interest is not None and not interest.empty:
                # Check if any keyword is at a recent peak (last value > 80% of max)
                for keyword in keywords:
                    if keyword in interest.columns:
                        series = interest[keyword]
                        if len(series) > 0:
                            recent = series.iloc[-1]
                            peak = series.max()
                            if peak > 0 and (recent / peak) > 0.8:
                                trend = TrendingContent(
                                    source=TrendSource.google_trends,
                                    topic=f"{keyword} (trending peak)",
                                    score=float(recent),
                                    raw_data={
                                        "keyword": keyword,
                                        "recent_interest": int(recent),
                                        "peak_interest": int(peak),
                                        "type": "interest_peak",
                                    },
                                    engagement_signals={
                                        "interest": int(recent),
                                        "peak_ratio": round(recent / peak, 2),
                                    },
                                )
                                self.db.add(trend)
                                stored += 1
        except Exception as e:
            logger.warning(f"Failed to get interest over time: {e}")

        self.db.flush()
        return stored

    @staticmethod
    def _is_relevant(query: str) -> bool:
        """Filter out irrelevant queries that slipped through.

        Keeps faith/family related content, filters out political,
        controversial, or off-topic results.
        """
        query_lower = query.lower()

        # Block political, controversial, or off-topic content
        blocked_terms = [
            "trump", "biden", "election", "democrat", "republican", "liberal",
            "conservative", "abortion", "gun", "immigration", "vaccine",
            "conspiracy", "scandal", "lawsuit", "arrested", "charged",
        ]
        if any(term in query_lower for term in blocked_terms):
            return False

        # Require at least some faith/family signal
        relevant_terms = [
            "god", "jesus", "christ", "faith", "pray", "bible", "scripture",
            "church", "worship", "spirit", "grace", "hope", "love",
            "marriage", "husband", "wife", "family", "parent", "child",
            "mom", "dad", "mother", "father", "kid", "devotion",
            "christian", "blessing", "grateful", "thankful", "forgive",
        ]
        return any(term in query_lower for term in relevant_terms)
