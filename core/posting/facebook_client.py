"""Facebook Page posting client via Graph API.

Cross-posts content to a linked Facebook Page with adapted captions.
Uses the same Meta app credentials as Instagram — derives a Page access token
from the user access token.
"""

import logging
import time
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
        self.user_token = settings.instagram_access_token
        self.client = httpx.Client(timeout=60.0)

        # Get Page-specific access token
        self.page_token = self._get_page_token()

    def _get_page_token(self) -> str:
        """Exchange user token for a Page access token."""
        try:
            response = self.client.get(
                f"{GRAPH_API_BASE}/{self.page_id}",
                params={
                    "fields": "access_token",
                    "access_token": self.user_token,
                },
            )
            data = response.json()

            if "error" in data:
                logger.warning(
                    f"Could not get Page token: {data['error'].get('message')}. "
                    f"Falling back to user token."
                )
                return self.user_token

            token = data.get("access_token")
            if token:
                logger.info("Obtained Facebook Page access token")
                return token

        except Exception as e:
            logger.warning(f"Page token request failed: {e}")

        return self.user_token

    def publish_photo(self, image_url: str, caption: str) -> Optional[dict]:
        """Publish a photo post to the Facebook Page."""
        try:
            response = self.client.post(
                f"{GRAPH_API_BASE}/{self.page_id}/photos",
                params={
                    "url": image_url,
                    "message": caption,
                    "access_token": self.page_token,
                },
            )
            data = response.json()

            if "error" in data:
                logger.error(f"Facebook photo error: {data['error'].get('message')}")
                return None

            logger.info(f"Published photo to Facebook: {data.get('id')}")
            return data

        except Exception as e:
            logger.error(f"Facebook photo post failed: {e}")
            return None

    def publish_video(self, video_url: str, caption: str) -> Optional[dict]:
        """Publish a video (reel) to the Facebook Page.

        Uses the resumable upload flow:
        1. Initialize upload session
        2. Upload video file
        3. Publish with description
        """
        try:
            # For public URLs, use the direct URL approach
            response = self.client.post(
                f"{GRAPH_API_BASE}/{self.page_id}/videos",
                params={
                    "file_url": video_url,
                    "description": caption,
                    "access_token": self.page_token,
                },
            )
            data = response.json()

            if "error" in data:
                logger.error(f"Facebook video error: {data['error'].get('message')}")
                return None

            video_id = data.get("id")
            logger.info(f"Published video to Facebook: {video_id}")
            return data

        except Exception as e:
            logger.error(f"Facebook video post failed: {e}")
            return None

    def publish_link(self, url: str, message: str) -> Optional[dict]:
        """Publish a link post (for affiliate/product content)."""
        try:
            response = self.client.post(
                f"{GRAPH_API_BASE}/{self.page_id}/feed",
                params={
                    "link": url,
                    "message": message,
                    "access_token": self.page_token,
                },
            )
            data = response.json()

            if "error" in data:
                logger.error(f"Facebook link error: {data['error'].get('message')}")
                return None

            return data

        except Exception as e:
            logger.error(f"Facebook link post failed: {e}")
            return None
