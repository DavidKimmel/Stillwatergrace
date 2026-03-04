"""Gumroad API client for digital product sales.

Manages product listings, processes sale webhooks, and tracks revenue.
"""

import logging
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from core.config import settings
from database.models import RevenueLog

logger = logging.getLogger(__name__)

GUMROAD_API_BASE = "https://api.gumroad.com/v2"


class GumroadClient:
    """Client for Gumroad digital product management."""

    def __init__(self, db: Session):
        self.db = db
        self.access_token = settings.gumroad_access_token
        self.client = httpx.Client(timeout=15.0)

    def list_products(self) -> list[dict]:
        """List all products on the Gumroad account."""
        if not self.access_token:
            return []

        try:
            response = self.client.get(
                f"{GUMROAD_API_BASE}/products",
                params={"access_token": self.access_token},
            )
            data = response.json()

            if not data.get("success"):
                logger.error(f"Gumroad API error: {data}")
                return []

            return data.get("products", [])

        except Exception as e:
            logger.error(f"Failed to list Gumroad products: {e}")
            return []

    def get_sales(self, product_id: Optional[str] = None) -> list[dict]:
        """Get recent sales, optionally filtered by product."""
        if not self.access_token:
            return []

        params = {"access_token": self.access_token}
        if product_id:
            params["product_id"] = product_id

        try:
            response = self.client.get(
                f"{GUMROAD_API_BASE}/sales",
                params=params,
            )
            data = response.json()
            return data.get("sales", [])

        except Exception as e:
            logger.error(f"Failed to get Gumroad sales: {e}")
            return []

    def process_sale_webhook(self, payload: dict) -> None:
        """Process a Gumroad sale webhook and record revenue.

        Gumroad sends webhooks to a URL you configure in your product settings.
        Webhook payload includes: email, price, product_name, etc.
        """
        amount = float(payload.get("price", 0)) / 100  # Gumroad sends cents
        product_name = payload.get("product_name", "Unknown Product")
        email = payload.get("email", "")

        revenue = RevenueLog(
            source_type="product",
            source_detail=f"Gumroad: {product_name}",
            amount=amount,
            notes=f"Buyer: {email}",
        )
        self.db.add(revenue)
        self.db.flush()

        logger.info(f"Recorded Gumroad sale: {product_name} — ${amount:.2f}")
