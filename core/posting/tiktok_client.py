"""TikTok Content Posting API client.

Cross-posts reel content to TikTok. The TikTok Content API requires
app review — this client includes a mock mode for development.

API docs: https://developers.tiktok.com/doc/content-posting-api-get-started
"""

import logging
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokClient:
    """Client for posting videos to TikTok."""

    def __init__(self):
        self.access_token = settings.tiktok_access_token
        self.mock_mode = not bool(self.access_token)

        if self.mock_mode:
            logger.warning("TikTok client running in mock mode (no access token)")

        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.access_token}" if self.access_token else "",
                "Content-Type": "application/json",
            },
        )

    def publish_video(
        self,
        video_url: str,
        caption: str,
        disable_comment: bool = False,
    ) -> Optional[dict]:
        """Publish a video to TikTok.

        Uses the 'pull from URL' method for video upload.
        """
        if self.mock_mode:
            logger.info(f"[MOCK TikTok] Would post video: {caption[:50]}...")
            return {"mock": True, "status": "would_post"}

        # Step 1: Initialize upload
        try:
            init_response = self.client.post(
                f"{TIKTOK_API_BASE}/post/publish/video/init/",
                json={
                    "post_info": {
                        "title": caption[:150],  # TikTok max title length
                        "privacy_level": "PUBLIC_TO_EVERYONE",
                        "disable_comment": disable_comment,
                    },
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "video_url": video_url,
                    },
                },
            )
            data = init_response.json()

            if data.get("error", {}).get("code") != "ok":
                logger.error(f"TikTok init error: {data}")
                return None

            publish_id = data.get("data", {}).get("publish_id")
            logger.info(f"TikTok publish initiated: {publish_id}")
            return {"publish_id": publish_id, "status": "processing"}

        except Exception as e:
            logger.error(f"TikTok publish failed: {e}")
            return None

    def check_publish_status(self, publish_id: str) -> Optional[dict]:
        """Check the status of a pending publish."""
        if self.mock_mode:
            return {"status": "mock_complete"}

        try:
            response = self.client.post(
                f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
                json={"publish_id": publish_id},
            )
            return response.json()
        except Exception as e:
            logger.error(f"TikTok status check failed: {e}")
            return None
