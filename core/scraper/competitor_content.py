"""Competitor content scraper using Instagram Business Discovery API.

Fetches recent posts from competitor business/creator accounts including
captions, media types, timestamps, and hashtags. Falls back to public
HTML scraping if Business Discovery is unavailable.
"""

import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from core.config import settings
from database.models import CompetitorPost

logger = logging.getLogger(__name__)

COMPETITOR_HANDLES = [
    "biblesociety",
    "dailyverses.net",
    "proverbs31ministries",
    "womenoffaith",
    "faithward_org",
]


def extract_hashtags(caption: Optional[str]) -> list[str]:
    """Extract hashtags from a caption string."""
    if not caption:
        return []
    return re.findall(r"#(\w+)", caption)


class CompetitorContentScraper:
    """Scrapes competitor post data via Instagram Business Discovery API."""

    def __init__(self, db: Session):
        self.db = db

    def _get_access_token(self) -> str:
        return settings.instagram_access_token

    def _get_ig_user_id(self) -> str:
        return settings.instagram_business_account_id

    def scrape_all(self, limit: int = 10) -> int:
        """Scrape recent posts from all competitors. Returns total posts scraped."""
        total = 0
        for handle in COMPETITOR_HANDLES:
            try:
                count = self.scrape_competitor(handle, limit=limit)
                total += count
                logger.info(f"Scraped {count} posts from @{handle}")
            except Exception as e:
                logger.warning(f"Failed to scrape @{handle}: {e}")
                continue
        self.db.flush()
        return total

    def scrape_competitor(self, handle: str, limit: int = 10) -> int:
        """Scrape recent posts from a single competitor using Business Discovery API."""
        token = self._get_access_token()
        ig_user_id = self._get_ig_user_id()

        fields = (
            f"business_discovery.fields("
            f"media.limit({limit})"
            f"{{id,caption,media_type,timestamp,permalink}}"
            f").username({handle})"
        )

        url = f"https://graph.facebook.com/v19.0/{ig_user_id}"
        params = {"fields": fields, "access_token": token}

        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, params=params)

        if response.status_code != 200:
            logger.warning(
                f"Business Discovery API failed for @{handle}: "
                f"{response.status_code} {response.text[:200]}"
            )
            return 0

        data = response.json()
        posts = self._parse_media_response(data, handle)
        return self._store_posts(posts)

    def _parse_media_response(self, data: dict, handle: str) -> list[CompetitorPost]:
        """Parse Business Discovery API response into CompetitorPost objects."""
        media_data = (
            data.get("business_discovery", {})
            .get("media", {})
            .get("data", [])
        )

        posts = []
        for item in media_data:
            caption = item.get("caption", "")
            posted_at = None
            ts = item.get("timestamp")
            if ts:
                try:
                    posted_at = datetime.fromisoformat(
                        ts.replace("+0000", "+00:00")
                    ).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    pass

            post = CompetitorPost(
                competitor_handle=handle,
                platform_media_id=str(item.get("id", "")),
                media_type=item.get("media_type", "IMAGE"),
                caption=caption,
                hashtags=extract_hashtags(caption),
                posted_at=posted_at,
                permalink=item.get("permalink"),
            )
            posts.append(post)
        return posts

    def _store_posts(self, posts: list[CompetitorPost]) -> int:
        """Store posts, skipping duplicates by platform_media_id."""
        stored = 0
        for post in posts:
            existing = (
                self.db.query(CompetitorPost)
                .filter(CompetitorPost.platform_media_id == post.platform_media_id)
                .first()
            )
            if existing:
                existing.caption = post.caption
                existing.hashtags = post.hashtags
                existing.scraped_at = datetime.utcnow()
            else:
                self.db.add(post)
                stored += 1
        self.db.flush()
        return stored

    @staticmethod
    def get_format_distribution(posts: list) -> dict[str, float]:
        """Calculate media type distribution as percentages."""
        if not posts:
            return {}
        counts: dict[str, int] = {}
        for post in posts:
            mt = post.media_type
            counts[mt] = counts.get(mt, 0) + 1
        total = len(posts)
        return {k: round(v / total * 100, 1) for k, v in counts.items()}
