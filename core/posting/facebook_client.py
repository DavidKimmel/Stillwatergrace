"""Facebook Page posting client via Graph API.

Cross-posts content to a linked Facebook Page with adapted captions.
Uses the same Meta app credentials as Instagram.
"""

import logging
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class FacebookClient:
    """Client for posting to a Facebook Page via Graph API."""

    def __init__(self):
        if not settings.facebook_page_id or not settings.instagram_access_token:
            raise ValueError("Facebook Page credentials not configured")

        self.page_id = settings.facebook_page_id
        self.access_token = settings.instagram_access_token  # Same token for linked accounts
        self.client = httpx.Client(timeout=30.0)

    def publish_photo(self, image_url: str, caption: str) -> Optional[dict]:
        """Publish a photo post to the Facebook Page."""
        try:
            response = self.client.post(
                f"{GRAPH_API_BASE}/{self.page_id}/photos",
                params={
                    "url": image_url,
                    "message": caption,
                    "access_token": self.access_token,
                },
            )
            data = response.json()

            if "error" in data:
                logger.error(f"Facebook API error: {data['error'].get('message')}")
                return None

            logger.info(f"Published to Facebook: {data.get('id')}")
            return data

        except Exception as e:
            logger.error(f"Facebook post failed: {e}")
            return None

    def publish_link(self, url: str, message: str) -> Optional[dict]:
        """Publish a link post (for affiliate/product content)."""
        try:
            response = self.client.post(
                f"{GRAPH_API_BASE}/{self.page_id}/feed",
                params={
                    "link": url,
                    "message": message,
                    "access_token": self.access_token,
                },
            )
            data = response.json()

            if "error" in data:
                logger.error(f"Facebook API error: {data['error'].get('message')}")
                return None

            return data

        except Exception as e:
            logger.error(f"Facebook link post failed: {e}")
            return None
