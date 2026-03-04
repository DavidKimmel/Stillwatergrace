"""Affiliate link management and tracking.

Manages affiliate links across programs (Amazon Associates, ChristianBook, etc.),
generates UTM-tracked URLs, and logs click/conversion events.
"""

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from sqlalchemy.orm import Session

from database.models import AffiliateLink, AffiliateClick, RevenueLog

logger = logging.getLogger(__name__)


class AffiliateManager:
    """Manages affiliate links and tracks performance."""

    def __init__(self, db: Session):
        self.db = db

    def create_link(
        self,
        program: str,
        product_name: str,
        original_url: str,
        commission_rate: float = 0.0,
        commission_type: str = "percentage",
        utm_campaign: Optional[str] = None,
    ) -> AffiliateLink:
        """Create a new tracked affiliate link with UTM parameters."""
        tracked_url = self._add_utm_params(
            original_url,
            utm_source="stillwatergrace",
            utm_medium="instagram",
            utm_campaign=utm_campaign or program,
        )

        link = AffiliateLink(
            program=program,
            product_name=product_name,
            original_url=original_url,
            tracked_url=tracked_url,
            commission_rate=commission_rate,
            commission_type=commission_type,
        )
        self.db.add(link)
        self.db.flush()

        logger.info(f"Created affiliate link #{link.id}: {product_name} ({program})")
        return link

    def record_click(
        self,
        link_id: int,
        utm_source: str = "",
        utm_medium: str = "",
        utm_campaign: str = "",
    ) -> AffiliateClick:
        """Record a click on an affiliate link."""
        click = AffiliateClick(
            link_id=link_id,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
        )
        self.db.add(click)
        self.db.flush()
        return click

    def record_conversion(
        self,
        click_id: int,
        commission_earned: float,
    ) -> None:
        """Record a conversion (sale) from a click."""
        click = self.db.query(AffiliateClick).filter(AffiliateClick.id == click_id).first()
        if click:
            click.converted = True
            click.commission_earned = commission_earned

            # Log revenue
            link = self.db.query(AffiliateLink).filter(AffiliateLink.id == click.link_id).first()
            revenue = RevenueLog(
                source_type="affiliate",
                source_detail=link.program if link else "unknown",
                amount=commission_earned,
            )
            self.db.add(revenue)
            self.db.flush()

    def get_all_active_links(self) -> list[AffiliateLink]:
        """Get all active affiliate links."""
        return (
            self.db.query(AffiliateLink)
            .filter(AffiliateLink.active == True)
            .order_by(AffiliateLink.program, AffiliateLink.product_name)
            .all()
        )

    @staticmethod
    def _add_utm_params(url: str, **utm_params) -> str:
        """Add UTM tracking parameters to a URL."""
        parsed = urlparse(url)
        existing_params = parse_qs(parsed.query)

        for key, value in utm_params.items():
            existing_params[key] = [value]

        new_query = urlencode(existing_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
