"""Competitor Instagram page tracker.

Scrapes public data from competitor pages to benchmark our performance
and identify content strategies that work in the niche.
"""

import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from database.models import CompetitorSnapshot, Platform

logger = logging.getLogger(__name__)

# Target competitor pages to track
COMPETITOR_HANDLES = [
    "biblesociety",
    "dailyverses.net",
    "proverbs31ministries",
    "womenoffaith",
    "faithward_org",
]


class CompetitorTracker:
    """Tracks competitor Instagram pages using public web data."""

    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.Client(
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    def scrape_all_competitors(self) -> int:
        """Scrape all competitor pages. Returns number successfully scraped."""
        scraped = 0

        for handle in COMPETITOR_HANDLES:
            try:
                snapshot = self._scrape_profile(handle)
                if snapshot:
                    self.db.add(snapshot)
                    scraped += 1
                    logger.info(f"Scraped @{handle}: {snapshot.followers} followers")
            except Exception as e:
                logger.warning(f"Failed to scrape @{handle}: {e}")
                continue

        self.db.flush()
        return scraped

    def _scrape_profile(self, handle: str) -> Optional[CompetitorSnapshot]:
        """Scrape a single Instagram profile's public data.

        Note: Instagram aggressively blocks scraping. This uses a basic
        approach that may need updating. For production, consider using
        the Instagram Graph API with instagram_basic permission on
        business/creator accounts, or a third-party service.
        """
        # Attempt to fetch the profile page
        try:
            response = self.client.get(
                f"https://www.instagram.com/{handle}/",
                follow_redirects=True,
            )
            if response.status_code != 200:
                logger.warning(f"@{handle} returned status {response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch @{handle}: {e}")
            return None

        # Try to extract data from the page
        # Instagram embeds JSON-LD or meta tags we can parse
        html = response.text

        followers = self._extract_meta_followers(html)
        post_count = self._extract_meta_posts(html)
        description = self._extract_meta_description(html)

        # Create snapshot even with partial data
        snapshot = CompetitorSnapshot(
            page_handle=handle,
            platform=Platform.instagram,
            followers=followers,
            post_count=post_count,
            captured_at=datetime.utcnow(),
        )

        return snapshot

    @staticmethod
    def _extract_meta_followers(html: str) -> Optional[int]:
        """Extract follower count from Instagram page HTML meta tags."""
        import re

        # Instagram puts follower count in meta description:
        # "123K Followers, 45 Following, 678 Posts"
        patterns = [
            r'([\d,.]+[KkMm]?)\s*Followers',
            r'"edge_followed_by":\{"count":(\d+)\}',
            r'"follower_count":(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return _parse_count(match.group(1))

        return None

    @staticmethod
    def _extract_meta_posts(html: str) -> Optional[int]:
        """Extract post count from page HTML."""
        import re

        patterns = [
            r'([\d,.]+)\s*Posts',
            r'"edge_owner_to_timeline_media":\{"count":(\d+)\}',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return _parse_count(match.group(1))

        return None

    @staticmethod
    def _extract_meta_description(html: str) -> Optional[str]:
        """Extract meta description from page HTML."""
        import re

        match = re.search(r'<meta\s+(?:name|property)="description"\s+content="([^"]*)"', html)
        if match:
            return match.group(1)

        return None


def _parse_count(value: str) -> Optional[int]:
    """Parse '1.5M', '123K', '1,234' to int."""
    if not value:
        return None

    value = value.strip().replace(",", "")

    multiplier = 1
    if value.upper().endswith("K"):
        multiplier = 1000
        value = value[:-1]
    elif value.upper().endswith("M"):
        multiplier = 1000000
        value = value[:-1]

    try:
        return int(float(value) * multiplier)
    except ValueError:
        return None
