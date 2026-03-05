"""Instagram Graph API client for publishing content.

Handles photo posts, carousel posts, and reels via the Instagram Graph API.
Includes rate limiting, token management, retry logic, and token auto-refresh.

Requires: instagram_content_publish, instagram_basic permissions.
"""

import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
ENV_FILE = Path(__file__).parent.parent.parent / ".env"

# Rate limits
MAX_POSTS_PER_DAY = 25
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 60


class InstagramClient:
    """Client for posting content to Instagram via Graph API."""

    def __init__(self):
        if not settings.has_instagram:
            raise ValueError("Instagram credentials not configured")

        self.account_id = settings.instagram_business_account_id
        self.access_token = settings.instagram_access_token
        self.client = httpx.Client(timeout=30.0)

        # Track daily post count
        self._daily_post_count = 0
        self._daily_reset_date = datetime.utcnow().date()

    def publish_photo(self, image_url: str, caption: str) -> dict:
        """Publish a single photo post.

        Two-step process:
        1. Create media container with image URL and caption
        2. Publish the container

        Args:
            image_url: Public URL of the image (must be accessible by Instagram)
            caption: Post caption including hashtags

        Returns:
            Dict with 'id' (creation ID) and 'media_id' (published media ID)
        """
        self._check_rate_limit()

        # Step 1: Create media container
        container = self._create_media_container(
            image_url=image_url,
            caption=caption,
        )
        if not container:
            raise RuntimeError("Failed to create media container")

        creation_id = container.get("id")
        logger.info(f"Created media container: {creation_id}")

        # Step 2: Wait for processing (photos usually instant, but can take a few seconds)
        self._wait_for_processing(creation_id, max_wait=60)

        # Step 3: Publish
        result = self._publish_container(creation_id)
        self._daily_post_count += 1

        return {"id": creation_id, "media_id": result.get("id")}

    def publish_carousel(self, image_urls: list[str], caption: str) -> dict:
        """Publish a carousel (multi-image) post.

        Three-step process:
        1. Create child containers for each image
        2. Create carousel container referencing children
        3. Publish the carousel container
        """
        self._check_rate_limit()

        if len(image_urls) < 2:
            raise ValueError("Carousel requires at least 2 images")
        if len(image_urls) > 10:
            raise ValueError("Carousel maximum is 10 images")

        # Step 1: Create child containers
        children_ids = []
        for url in image_urls:
            child = self._api_post(
                f"{self.account_id}/media",
                params={
                    "image_url": url,
                    "is_carousel_item": "true",
                },
            )
            if child and child.get("id"):
                children_ids.append(child["id"])
            else:
                raise RuntimeError(f"Failed to create carousel child for {url}")

        # Step 2: Create carousel container
        container = self._api_post(
            f"{self.account_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(children_ids),
                "caption": caption,
            },
        )
        if not container:
            raise RuntimeError("Failed to create carousel container")

        creation_id = container.get("id")

        # Step 3: Publish
        result = self._publish_container(creation_id)
        self._daily_post_count += 1

        return {"id": creation_id, "media_id": result.get("id")}

    def publish_reel(
        self,
        video_url: str,
        caption: str,
        thumb_offset_ms: Optional[int] = None,
    ) -> dict:
        """Publish a reel (short video).

        Three-step process:
        1. Create video container
        2. Wait for video processing
        3. Publish

        Args:
            video_url: Public URL of the video.
            caption: Post caption.
            thumb_offset_ms: Thumbnail offset in milliseconds from start.
                             If set, Instagram uses this frame as the cover image.
        """
        self._check_rate_limit()

        # Step 1: Create reel container
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
        }
        if thumb_offset_ms is not None:
            params["thumb_offset"] = str(thumb_offset_ms)

        container = self._api_post(f"{self.account_id}/media", params=params)
        if not container:
            raise RuntimeError("Failed to create reel container")

        creation_id = container.get("id")
        logger.info(f"Created reel container: {creation_id}, waiting for processing...")

        # Step 2: Poll for video processing completion
        self._wait_for_processing(creation_id)

        # Step 3: Publish
        result = self._publish_container(creation_id)
        self._daily_post_count += 1

        return {"id": creation_id, "media_id": result.get("id")}

    def get_media_insights(self, media_id: str) -> Optional[dict]:
        """Get insights for a published media item."""
        metrics = "impressions,reach,saved,shares,likes,comments,plays"
        result = self._api_get(
            f"{media_id}/insights",
            params={"metric": metrics},
        )
        if not result:
            return None

        insights = {}
        for item in result.get("data", []):
            name = item.get("name")
            values = item.get("values", [{}])
            insights[name] = values[0].get("value", 0) if values else 0

        return insights

    # ── Private Methods ──

    def _create_media_container(self, image_url: str, caption: str) -> Optional[dict]:
        """Create a media container for a photo post."""
        return self._api_post(
            f"{self.account_id}/media",
            params={
                "image_url": image_url,
                "caption": caption,
            },
        )

    def _publish_container(self, creation_id: str) -> dict:
        """Publish a media container."""
        result = self._api_post(
            f"{self.account_id}/media_publish",
            params={"creation_id": creation_id},
        )
        if not result:
            raise RuntimeError(f"Failed to publish container {creation_id}")

        logger.info(f"Published media: {result.get('id')}")
        return result

    def _wait_for_processing(self, container_id: str, max_wait: int = 300) -> None:
        """Wait for video/reel processing to complete."""
        start = time.time()

        while time.time() - start < max_wait:
            status = self._api_get(
                container_id,
                params={"fields": "status_code,status"},
            )
            if not status:
                time.sleep(10)
                continue

            code = status.get("status_code")
            if code == "FINISHED":
                return
            elif code == "ERROR":
                raise RuntimeError(f"Media processing failed: {status.get('status')}")

            time.sleep(10)

        raise RuntimeError(f"Media processing timed out after {max_wait}s")

    def _check_rate_limit(self) -> None:
        """Check if we've hit the daily posting limit."""
        today = datetime.utcnow().date()
        if today != self._daily_reset_date:
            self._daily_post_count = 0
            self._daily_reset_date = today

        if self._daily_post_count >= MAX_POSTS_PER_DAY:
            raise RuntimeError(
                f"Daily post limit reached ({MAX_POSTS_PER_DAY}). "
                f"Resets at midnight UTC."
            )

    def _api_post(self, endpoint: str, params: dict) -> Optional[dict]:
        """Make a POST request to the Graph API with retry logic."""
        params["access_token"] = self.access_token
        url = f"{GRAPH_API_BASE}/{endpoint}"

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.post(url, params=params)
                data = response.json()

                if "error" in data:
                    error = data["error"]
                    logger.error(f"Graph API error: {error.get('message')} (code: {error.get('code')})")

                    # Retry on rate limit or transient errors
                    if error.get("code") in (4, 17, 32, 190):
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                            continue
                    return None

                return data

            except Exception as e:
                logger.error(f"Graph API request failed (attempt {attempt + 1}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS)

        return None

    def _api_get(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
        """Make a GET request to the Graph API."""
        if params is None:
            params = {}
        params["access_token"] = self.access_token
        url = f"{GRAPH_API_BASE}/{endpoint}"

        try:
            response = self.client.get(url, params=params)
            data = response.json()

            if "error" in data:
                logger.error(f"Graph API error: {data['error'].get('message')}")
                return None

            return data

        except Exception as e:
            logger.error(f"Graph API GET failed: {e}")
            return None


def refresh_instagram_token() -> Optional[str]:
    """Exchange the current long-lived token for a new 60-day token.

    Updates the .env file with the new token so it persists across restarts.
    Returns the new token on success, None on failure.
    """
    if not settings.instagram_access_token:
        logger.error("No Instagram access token to refresh")
        return None

    # Step 1: Exchange token via Graph API
    url = f"{GRAPH_API_BASE}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "fb_exchange_token": settings.instagram_access_token,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            data = response.json()
    except Exception as e:
        logger.error(f"Token refresh request failed: {e}")
        return None

    if "error" in data:
        logger.error(f"Token refresh error: {data['error'].get('message')}")
        return None

    new_token = data.get("access_token")
    expires_in = data.get("expires_in", 0)  # seconds

    if not new_token:
        logger.error("No access_token in refresh response")
        return None

    expires_days = expires_in // 86400
    logger.info(f"Got new Instagram token (expires in {expires_days} days)")

    # Step 2: Update .env file
    if _update_env_token(new_token):
        logger.info("Updated .env with new Instagram token")
    else:
        logger.warning("Failed to update .env — token will be lost on restart")

    # Step 3: Update the live settings object so the running process uses the new token
    settings.instagram_access_token = new_token

    return new_token


def _update_env_token(new_token: str) -> bool:
    """Replace INSTAGRAM_ACCESS_TOKEN in the .env file."""
    try:
        content = ENV_FILE.read_text(encoding="utf-8")
        updated = re.sub(
            r"^INSTAGRAM_ACCESS_TOKEN=.*$",
            f"INSTAGRAM_ACCESS_TOKEN={new_token}",
            content,
            flags=re.MULTILINE,
        )
        if updated == content:
            logger.warning("INSTAGRAM_ACCESS_TOKEN line not found in .env")
            return False
        ENV_FILE.write_text(updated, encoding="utf-8")
        return True
    except Exception as e:
        logger.error(f"Failed to update .env file: {e}")
        return False


def check_token_health() -> dict:
    """Check the current token's validity and expiration.

    Returns dict with 'valid', 'expires_at', 'days_remaining'.
    """
    url = f"{GRAPH_API_BASE}/debug_token"
    params = {
        "input_token": settings.instagram_access_token,
        "access_token": f"{settings.meta_app_id}|{settings.meta_app_secret}",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, params=params)
            data = response.json()
    except Exception as e:
        logger.error(f"Token health check failed: {e}")
        return {"valid": False, "error": str(e)}

    token_data = data.get("data", {})
    is_valid = token_data.get("is_valid", False)
    expires_at = token_data.get("expires_at", 0)

    if expires_at:
        expires_dt = datetime.utcfromtimestamp(expires_at)
        days_remaining = (expires_dt - datetime.utcnow()).days
    else:
        expires_dt = None
        days_remaining = -1

    result = {
        "valid": is_valid,
        "expires_at": expires_dt.isoformat() if expires_dt else None,
        "days_remaining": days_remaining,
        "app_id": token_data.get("app_id"),
        "scopes": token_data.get("scopes", []),
    }

    if days_remaining <= 7:
        logger.warning(f"Instagram token expires in {days_remaining} days!")
    else:
        logger.info(f"Instagram token valid, {days_remaining} days remaining")

    return result
