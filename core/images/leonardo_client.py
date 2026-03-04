"""Leonardo.ai image generation client.

Integrates with Leonardo.ai REST API for generating images from prompts.
Handles async generation polling, image download, and quota tracking.

API docs: https://docs.leonardo.ai
"""

import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"
IMAGES_RAW_DIR = Path(__file__).parent.parent.parent / "images" / "raw"

# Model IDs — update if Leonardo changes these
MODELS = {
    "photorealistic": "ac614f96-1082-45bf-be9d-757f2d31c174",  # Leonardo Diffusion XL
    "photorealistic_alt": "2067ae52-33fd-4a82-bb92-c2c55e7d2786",  # AlbedoBase XL
    "illustration": "5c232a9e-9061-4777-980a-ddc8e65647c6",  # Leonardo Creative
}

# Aspect ratio presets
DIMENSIONS = {
    "feed_4x5": {"width": 1024, "height": 1280},
    "feed_1x1": {"width": 1024, "height": 1024},
    "story_9x16": {"width": 768, "height": 1344},
}

# Polling config
MAX_POLL_ATTEMPTS = 60
POLL_INTERVAL_SECONDS = 5


class LeonardoClient:
    """Client for Leonardo.ai image generation API."""

    def __init__(self):
        if not settings.has_leonardo:
            raise ValueError("Leonardo API key not configured")

        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {settings.leonardo_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        IMAGES_RAW_DIR.mkdir(parents=True, exist_ok=True)

    def generate_image(
        self,
        prompt: str,
        style: str = "photorealistic",
        aspect_ratio: str = "feed_4x5",
        negative_prompt: str = "text, words, letters, watermark, logo, blurry, distorted faces, stock photo, posed, artificial",
    ) -> Optional[dict]:
        """Generate an image from a prompt.

        Args:
            prompt: Image description
            style: 'photorealistic', 'photorealistic_alt', or 'illustration'
            aspect_ratio: 'feed_4x5', 'feed_1x1', or 'story_9x16'
            negative_prompt: Things to avoid in the image

        Returns:
            Dict with 'generation_id', 'image_url', 'local_path' or None on failure.
        """
        model_id = MODELS.get(style, MODELS["photorealistic"])
        dims = DIMENSIONS.get(aspect_ratio, DIMENSIONS["feed_4x5"])

        # Submit generation request
        payload = {
            "prompt": prompt,
            "modelId": model_id,
            "width": dims["width"],
            "height": dims["height"],
            "num_images": 1,
            "guidance_scale": 7,
            "num_inference_steps": 30,
            "negative_prompt": negative_prompt,
            "public": False,
        }

        try:
            response = self.client.post(f"{BASE_URL}/generations", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Leonardo API error: {e.response.status_code} — {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Leonardo request failed: {e}")
            return None

        generation_id = data.get("sdGenerationJob", {}).get("generationId")
        if not generation_id:
            logger.error(f"No generation ID in response: {data}")
            return None

        logger.info(f"Leonardo generation started: {generation_id}")

        # Poll for completion
        image_url = self._poll_generation(generation_id)
        if not image_url:
            return None

        # Download image
        local_path = self._download_image(image_url, generation_id)

        return {
            "generation_id": generation_id,
            "image_url": image_url,
            "local_path": str(local_path) if local_path else None,
            "width": dims["width"],
            "height": dims["height"],
            "model": style,
        }

    def _poll_generation(self, generation_id: str) -> Optional[str]:
        """Poll generation status until complete. Returns image URL."""
        for attempt in range(MAX_POLL_ATTEMPTS):
            try:
                response = self.client.get(f"{BASE_URL}/generations/{generation_id}")
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.warning(f"Poll attempt {attempt + 1} failed: {e}")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            generation = data.get("generations_by_pk", {})
            status = generation.get("status")

            if status == "COMPLETE":
                images = generation.get("generated_images", [])
                if images:
                    url = images[0].get("url")
                    logger.info(f"Generation {generation_id} complete: {url}")
                    return url
                else:
                    logger.error(f"Generation complete but no images: {data}")
                    return None

            elif status == "FAILED":
                logger.error(f"Generation {generation_id} failed")
                return None

            # Still pending
            logger.debug(f"Generation {generation_id} status: {status} (attempt {attempt + 1})")
            time.sleep(POLL_INTERVAL_SECONDS)

        logger.error(f"Generation {generation_id} timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s")
        return None

    def _download_image(self, url: str, generation_id: str) -> Optional[Path]:
        """Download generated image to local storage."""
        try:
            response = self.client.get(url, follow_redirects=True)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            return None

        # Determine extension from content type
        content_type = response.headers.get("content-type", "image/jpeg")
        ext = "jpg" if "jpeg" in content_type else "png"

        path = IMAGES_RAW_DIR / f"{generation_id}.{ext}"
        path.write_bytes(response.content)

        logger.info(f"Downloaded image to {path} ({len(response.content)} bytes)")
        return path

    def get_user_info(self) -> Optional[dict]:
        """Get current user info including token/credit balance."""
        try:
            response = self.client.get(f"{BASE_URL}/me")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None
