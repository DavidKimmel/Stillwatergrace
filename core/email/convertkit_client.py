"""ConvertKit API client — subscriber count and basic stats.

All heavy lifting (landing pages, email sequences, PDF delivery)
is handled in ConvertKit's UI. This client just pulls stats
for our dashboard.
"""

import logging
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.convertkit.com/v3"


class ConvertKitClient:
    """Thin wrapper for ConvertKit API v3."""

    def __init__(self, api_secret: Optional[str] = None) -> None:
        self.api_secret = api_secret or settings.convertkit_api_secret

    def get_subscriber_count(self) -> int:
        """Get total subscriber count."""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{BASE_URL}/subscribers",
                    params={"api_secret": self.api_secret},
                )
                resp.raise_for_status()
                return resp.json().get("total_subscribers", 0)
        except Exception as e:
            logger.error(f"ConvertKit API error: {e}")
            return 0

    def get_form_subscribers(self, form_id: str | None = None) -> int:
        """Get subscriber count for a specific form (landing page)."""
        fid = form_id or settings.convertkit_form_id
        if not fid:
            return 0

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{BASE_URL}/forms/{fid}/subscriptions",
                    params={"api_secret": self.api_secret},
                )
                resp.raise_for_status()
                return resp.json().get("total_subscriptions", 0)
        except Exception as e:
            logger.error(f"ConvertKit form API error: {e}")
            return 0
