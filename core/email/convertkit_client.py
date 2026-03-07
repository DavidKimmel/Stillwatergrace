"""Kit (ConvertKit) API client — subscriber count and basic stats.

All heavy lifting (landing pages, email sequences, PDF delivery)
is handled in Kit's UI. This client just pulls stats for our dashboard.
Uses the v4 API at api.kit.com.
"""

import logging
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.kit.com/v4"


class ConvertKitClient:
    """Thin wrapper for Kit (ConvertKit) API v4."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or settings.convertkit_api_key

    def _headers(self) -> dict[str, str]:
        return {"X-Kit-Api-Key": self.api_key}

    def get_subscriber_count(self) -> int:
        """Get total subscriber count."""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{BASE_URL}/subscribers",
                    headers=self._headers(),
                    params={"per_page": 1},
                )
                resp.raise_for_status()
                data = resp.json()
                subs = data.get("subscribers", [])
                pagination = data.get("pagination", {})
                if pagination.get("has_next_page"):
                    # Has more than 1 — need total count from a different endpoint
                    return self._get_total_subscribers()
                return len(subs)
        except Exception as e:
            logger.error(f"Kit API error: {e}")
            return 0

    def _get_total_subscribers(self) -> int:
        """Count all subscribers by paginating."""
        total = 0
        cursor = None
        try:
            with httpx.Client(timeout=10) as client:
                while True:
                    params: dict = {"per_page": 500}
                    if cursor:
                        params["after"] = cursor
                    resp = client.get(
                        f"{BASE_URL}/subscribers",
                        headers=self._headers(),
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    total += len(data.get("subscribers", []))
                    pagination = data.get("pagination", {})
                    if not pagination.get("has_next_page"):
                        break
                    cursor = pagination.get("end_cursor")
        except Exception as e:
            logger.error(f"Kit API pagination error: {e}")
        return total

    def get_form_subscribers(self, form_id: str | None = None) -> int:
        """Get subscriber count for a specific form (landing page)."""
        fid = form_id or settings.convertkit_form_id
        if not fid:
            return 0

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{BASE_URL}/forms/{fid}/subscribers",
                    headers=self._headers(),
                    params={"per_page": 1},
                )
                resp.raise_for_status()
                data = resp.json()
                subs = data.get("subscribers", [])
                if data.get("pagination", {}).get("has_next_page"):
                    return self._get_form_total(fid)
                return len(subs)
        except Exception as e:
            logger.error(f"Kit form API error: {e}")
            return 0

    def _get_form_total(self, form_id: str) -> int:
        """Count form subscribers by paginating."""
        total = 0
        cursor = None
        try:
            with httpx.Client(timeout=10) as client:
                while True:
                    params: dict = {"per_page": 500}
                    if cursor:
                        params["after"] = cursor
                    resp = client.get(
                        f"{BASE_URL}/forms/{form_id}/subscribers",
                        headers=self._headers(),
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    total += len(data.get("subscribers", []))
                    pagination = data.get("pagination", {})
                    if not pagination.get("has_next_page"):
                        break
                    cursor = pagination.get("end_cursor")
        except Exception as e:
            logger.error(f"Kit form pagination error: {e}")
        return total
