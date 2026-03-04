"""Reddit scraper for Christian/family trending discussions.

Uses PRAW (Python Reddit API Wrapper) to monitor target subreddits
for hot posts and discussions that can inspire content.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import TrendingContent, TrendSource
from core.config import settings

logger = logging.getLogger(__name__)

# Target subreddits for faith and family content
TARGET_SUBREDDITS = [
    "Christianity",
    "TrueChristian",
    "Reformed",
    "marriage",
    "Parenting",
    "Christian",
]

# Max posts to fetch per subreddit per run
POSTS_PER_SUBREDDIT = 15


class RedditScraper:
    """Scrapes Reddit for trending faith/family discussions."""

    def __init__(self, db: Session):
        self.db = db
        self.reddit = self._create_client()

    def _create_client(self):
        """Create PRAW Reddit client."""
        try:
            import praw
        except ImportError:
            logger.error("praw not installed")
            return None

        if not settings.has_reddit:
            logger.warning("Reddit credentials not configured")
            return None

        return praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )

    def fetch_hot_posts(self) -> int:
        """Fetch hot posts from all target subreddits.

        Returns the number of posts stored.
        """
        if not self.reddit:
            logger.warning("Reddit client not available")
            return 0

        total_stored = 0

        for subreddit_name in TARGET_SUBREDDITS:
            try:
                count = self._fetch_subreddit(subreddit_name)
                total_stored += count
                logger.info(f"r/{subreddit_name}: {count} posts stored")
            except Exception as e:
                logger.warning(f"Failed to scrape r/{subreddit_name}: {e}")
                continue

        return total_stored

    def _fetch_subreddit(self, subreddit_name: str) -> int:
        """Fetch hot posts from a single subreddit."""
        subreddit = self.reddit.subreddit(subreddit_name)
        stored = 0

        for post in subreddit.hot(limit=POSTS_PER_SUBREDDIT):
            # Skip stickied/pinned posts
            if post.stickied:
                continue

            # Skip low-quality posts
            if post.score < 10:
                continue

            # Check for relevance (applies mainly to broader subs like r/marriage)
            if not self._is_relevant(post.title, subreddit_name):
                continue

            # Calculate virality score based on engagement signals
            score = self._calculate_score(post)

            # Get top comments for context
            post.comments.replace_more(limit=0)
            top_comments = [
                {"body": c.body[:500], "score": c.score}
                for c in sorted(post.comments[:5], key=lambda c: c.score, reverse=True)
                if c.score > 5
            ]

            trend = TrendingContent(
                source=TrendSource.reddit,
                topic=post.title,
                score=score,
                url=f"https://reddit.com{post.permalink}",
                subreddit=subreddit_name,
                raw_data={
                    "post_id": post.id,
                    "title": post.title,
                    "selftext": post.selftext[:1000] if post.selftext else "",
                    "flair": post.link_flair_text,
                    "author": str(post.author),
                    "created_utc": post.created_utc,
                    "top_comments": top_comments,
                },
                engagement_signals={
                    "score": post.score,
                    "upvote_ratio": post.upvote_ratio,
                    "num_comments": post.num_comments,
                    "awards": post.total_awards_received,
                },
            )
            self.db.add(trend)
            stored += 1

        self.db.flush()
        return stored

    @staticmethod
    def _calculate_score(post) -> float:
        """Calculate a 0-100 virality score based on Reddit engagement.

        Weights:
        - Post score (upvotes): 40%
        - Comment count: 30%
        - Upvote ratio: 20%
        - Awards: 10%
        """
        # Normalize each signal to roughly 0-100
        score_norm = min(post.score / 500 * 100, 100)
        comments_norm = min(post.num_comments / 100 * 100, 100)
        ratio_norm = post.upvote_ratio * 100
        awards_norm = min(post.total_awards_received / 5 * 100, 100)

        return round(
            score_norm * 0.4
            + comments_norm * 0.3
            + ratio_norm * 0.2
            + awards_norm * 0.1,
            1,
        )

    @staticmethod
    def _is_relevant(title: str, subreddit: str) -> bool:
        """Check if a post is relevant to our content niche.

        For faith-specific subreddits (Christianity, TrueChristian, Reformed, Christian),
        most content is relevant. For broader subs (marriage, Parenting), we filter.
        """
        faith_subs = {"Christianity", "TrueChristian", "Reformed", "Christian"}
        if subreddit in faith_subs:
            # Still filter out meta/political posts
            title_lower = title.lower()
            blocked = ["politics", "election", "trump", "biden", "democrat", "republican"]
            return not any(term in title_lower for term in blocked)

        # For r/marriage and r/Parenting, require some faith/family signal
        title_lower = title.lower()
        relevant_terms = [
            "faith", "god", "pray", "church", "christian", "bible",
            "spiritual", "grace", "blessing", "hope", "encourage",
            "marriage", "husband", "wife", "love", "family", "parent",
            "child", "kid", "mom", "dad", "grateful", "forgive",
        ]
        return any(term in title_lower for term in relevant_terms)
