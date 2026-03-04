"""Unsplash API client for fallback stock photos.

Used when Leonardo.ai quota is low or generation fails.
Free tier: 50 requests/hour.
"""

import logging
from pathlib import Path
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.unsplash.com"
IMAGES_RAW_DIR = Path(__file__).parent.parent.parent / "images" / "raw"

# Search term mapping from content type to Unsplash keywords
CONTENT_TYPE_KEYWORDS = {
    "daily_verse": "bible open book morning light",
    "marriage_monday": "couple hands wedding rings love",
    "parenting_wednesday": "parent child family hands",
    "faith_friday": "sunrise hope light clouds storm",
    "encouragement": "nature sunrise peaceful golden hour",
    "prayer_prompt": "candle prayer hands peaceful",
    "gratitude": "sunset nature golden light thankful",
    "fill_in_blank": "nature sky clouds scenic",
    "this_or_that": "coffee morning nature calm",
    "conviction_quote": "mountain landscape powerful nature",
    "reel": "cinematic landscape golden hour",
    "carousel": "nature collage scenic peaceful",
}


class UnsplashClient:
    """Fallback image client using Unsplash API."""

    def __init__(self):
        if not settings.unsplash_access_key:
            raise ValueError("Unsplash access key not configured")

        self.client = httpx.Client(
            timeout=15.0,
            headers={
                "Authorization": f"Client-ID {settings.unsplash_access_key}",
                "Accept-Version": "v1",
            },
        )
        IMAGES_RAW_DIR.mkdir(parents=True, exist_ok=True)

    def search_and_download(
        self,
        content_type: str,
        custom_query: Optional[str] = None,
        orientation: str = "portrait",
    ) -> Optional[dict]:
        """Search for a relevant photo and download it.

        Args:
            content_type: Content type for keyword mapping
            custom_query: Override search query
            orientation: 'portrait', 'landscape', or 'squarish'

        Returns:
            Dict with photo metadata and local path, or None.
        """
        query = custom_query or CONTENT_TYPE_KEYWORDS.get(content_type, "nature peaceful")

        # Search
        try:
            response = self.client.get(
                f"{BASE_URL}/search/photos",
                params={
                    "query": query,
                    "per_page": 5,
                    "orientation": orientation,
                    "content_filter": "high",  # Safe content only
                },
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Unsplash search failed: {e}")
            return None

        results = data.get("results", [])
        if not results:
            logger.warning(f"No Unsplash results for query: {query}")
            return None

        # Pick the first result
        photo = results[0]
        photo_id = photo["id"]

        # Download the regular size (good quality without being huge)
        download_url = photo["urls"].get("regular")
        if not download_url:
            return None

        local_path = self._download(download_url, photo_id)

        # Build attribution (required by Unsplash TOS)
        photographer = photo.get("user", {}).get("name", "Unknown")
        photo_url = photo.get("links", {}).get("html", "")
        attribution = f"Photo by {photographer} on Unsplash ({photo_url})"

        # Trigger download tracking (required by Unsplash TOS)
        self._track_download(photo)

        return {
            "photo_id": photo_id,
            "image_url": download_url,
            "local_path": str(local_path) if local_path else None,
            "width": photo.get("width"),
            "height": photo.get("height"),
            "attribution": attribution,
            "photographer": photographer,
            "color": photo.get("color"),
        }

    def _download(self, url: str, photo_id: str) -> Optional[Path]:
        """Download photo to local storage."""
        try:
            response = self.client.get(url, follow_redirects=True)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to download Unsplash photo: {e}")
            return None

        path = IMAGES_RAW_DIR / f"unsplash_{photo_id}.jpg"
        path.write_bytes(response.content)
        logger.info(f"Downloaded Unsplash photo to {path}")
        return path

    def _track_download(self, photo: dict) -> None:
        """Trigger download event (required by Unsplash API guidelines)."""
        download_location = photo.get("links", {}).get("download_location")
        if download_location:
            try:
                self.client.get(download_location)
            except Exception:
                pass  # Non-critical
