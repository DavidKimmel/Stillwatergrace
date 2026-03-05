"""Unsplash API client for stock background photos.

Free tier: 50 requests/hour.
"""

import logging
import random
from pathlib import Path
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.unsplash.com"
IMAGES_RAW_DIR = Path(__file__).parent.parent.parent / "images" / "raw"

# Search term mapping — varied queries per content type for background variety
# Multiple varied queries per content type + shared pool for maximum variety
CONTENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "daily_verse": [
        "bible open book morning light",
        "sunlit pages journal wooden table",
        "sunrise meadow peaceful golden light",
        "calm lake reflection dawn",
        "old bible leather desk warm",
        "autumn leaves open notebook",
        "coffee cup bible morning window",
        "vintage book candlelight warm",
    ],
    "marriage_monday": [
        "couple walking beach golden hour",
        "couple hands sunset romantic",
        "two coffee cups cozy morning",
        "sunset beach warm golden hour",
        "cozy fireplace warm blanket evening",
        "couple silhouette sunset",
        "vintage love letters desk roses",
        "romantic dinner candles evening",
    ],
    "parenting_wednesday": [
        "parent child walking nature sunset",
        "family silhouette golden hour",
        "mother child garden sunlight",
        "father daughter walking park",
        "tree growing strong sunlight",
        "child running field golden hour",
        "family beach sunset walking",
        "seeds sprouting soil spring",
    ],
    "faith_friday": [
        "sunrise hope light clouds storm",
        "mountain summit sunrise inspiring",
        "light breaking through dark clouds",
        "cross silhouette sunset dramatic sky",
        "path through forest morning light",
        "lighthouse rocky coast stormy sea",
        "rainbow after storm landscape",
        "ancient stone church countryside",
    ],
    "encouragement": [
        "nature sunrise peaceful golden hour",
        "wildflowers meadow soft sunlight",
        "ocean waves gentle sunset calm",
        "mountain vista panoramic golden light",
        "river flowing through autumn forest",
        "warm sunset clouds orange purple",
        "lavender field soft golden light",
        "misty morning forest rays",
    ],
    "prayer_prompt": [
        "candle warm glow dark background",
        "quiet chapel soft window light",
        "morning mist serene landscape",
        "candlelight reflection still water",
        "incense smoke dark peaceful",
        "old church stained glass window",
        "sunrise through trees forest",
        "still pond morning reflection",
    ],
    "gratitude": [
        "sunset nature golden light",
        "harvest table warm autumn glow",
        "blooming garden morning dew",
        "golden wheat field sunset",
        "starry night clear sky wonder",
        "autumn maple tree vibrant colors",
        "sunflower field golden hour",
        "fruit basket wooden table warm",
    ],
    "fill_in_blank": [
        "nature sky clouds scenic",
        "minimalist landscape soft tones",
        "abstract nature light bokeh",
        "rolling hills green peaceful",
        "desert landscape vast open sky",
        "sand dunes soft light",
        "calm sea horizon pastel sky",
        "simple stone texture natural",
    ],
    "this_or_that": [
        "coffee morning nature calm",
        "two paths fork road nature",
        "sunrise sky colorful dramatic",
        "mountain ocean landscape scenic",
        "forest trail morning light",
        "tea cup rainy window cozy",
        "desert oasis contrast landscape",
        "winter frost morning ice",
    ],
    "conviction_quote": [
        "mountain landscape powerful nature",
        "stormy sky dramatic clouds",
        "lone tree standing strong wind",
        "rocky coastline crashing waves",
        "deep forest towering ancient trees",
        "volcano dramatic sky powerful",
        "thunderstorm dark sky dramatic",
        "canyon deep dramatic landscape",
    ],
    "reel": [
        "cinematic landscape golden hour",
        "dramatic sky clouds colorful sunset",
        "misty mountain valley morning",
        "ocean horizon sunset cinematic",
        "northern lights aurora landscape",
        "waterfall forest dramatic scenic",
        "desert sunset dramatic colors",
        "snow mountain sunrise golden",
    ],
    "carousel": [
        "botanical garden flowers colorful",
        "seasonal landscape beautiful nature",
        "waterfall forest lush green",
        "autumn leaves colorful pathway",
        "cherry blossom spring garden",
        "tropical plants lush green",
        "coastal cliff ocean view",
        "meadow wildflowers summer",
    ],
}

_DEFAULT_QUERIES = [
    "nature peaceful golden hour",
    "scenic landscape calm serene",
    "beautiful sky clouds sunlight",
]


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
        high_res: bool = False,
    ) -> Optional[dict]:
        """Search for a relevant photo and download it.

        Args:
            content_type: Content type for keyword mapping
            custom_query: Override search query
            orientation: 'portrait', 'landscape', or 'squarish'
            high_res: If True, use full-res URL (for reel backgrounds needing zoompan headroom)

        Returns:
            Dict with photo metadata and local path, or None.
        """
        if custom_query:
            query = custom_query
        else:
            queries = CONTENT_TYPE_KEYWORDS.get(content_type, _DEFAULT_QUERIES)
            query = random.choice(queries)

        # Search — randomize page to get different results across runs
        page = random.randint(1, 5)
        try:
            response = self.client.get(
                f"{BASE_URL}/search/photos",
                params={
                    "query": query,
                    "per_page": 15,
                    "page": page,
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

        # Filter out photos we've already downloaded to avoid repetition
        used_ids = {
            p.stem.replace("unsplash_", "")
            for p in IMAGES_RAW_DIR.glob("unsplash_*.jpg")
        }
        fresh = [r for r in results if r["id"] not in used_ids]
        pool = fresh if fresh else results  # fall back to all if everything used

        # Pick a random result from the fresh pool
        photo = random.choice(pool)
        if photo["id"] in used_ids:
            logger.info(f"All {len(results)} Unsplash results already used, reusing one")
        photo_id = photo["id"]

        # Use full-res for reel backgrounds (zoompan needs headroom), regular otherwise
        url_key = "full" if high_res else "regular"
        download_url = photo["urls"].get(url_key) or photo["urls"].get("regular")
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
