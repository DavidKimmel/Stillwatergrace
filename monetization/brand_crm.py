"""Brand partnership CRM.

Manages outreach to potential brand partners, tracks deal stages,
and generates rate cards based on current account metrics.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from database.models import BrandContact, DealStage, RevenueLog

logger = logging.getLogger(__name__)

# Seed brand prospects by category
SEED_PROSPECTS = [
    {"brand_name": "DaySpring", "category": "gifts", "website": "dayspring.com"},
    {"brand_name": "Crossway Books", "category": "publisher", "website": "crossway.org"},
    {"brand_name": "Bible Gateway", "category": "digital", "website": "biblegateway.com"},
    {"brand_name": "Samaritan's Purse", "category": "nonprofit", "website": "samaritanspurse.org"},
    {"brand_name": "Hobby Lobby", "category": "retail", "website": "hobbylobby.com"},
    {"brand_name": "Christianbook.com", "category": "retail", "website": "christianbook.com"},
    {"brand_name": "LifeWay", "category": "publisher", "website": "lifeway.com"},
    {"brand_name": "Mardel", "category": "retail", "website": "mardel.com"},
    {"brand_name": "The Chosen", "category": "media", "website": "thechosen.tv"},
    {"brand_name": "She Reads Truth", "category": "devotional", "website": "shereadstruth.com"},
    {"brand_name": "Illustrated Faith", "category": "journaling", "website": "illustratedfaith.com"},
    {"brand_name": "Anchored Press", "category": "apparel", "website": "anchoredpress.com"},
    {"brand_name": "Grace & Lace", "category": "apparel", "website": "graceandlace.com"},
    {"brand_name": "Eden Book Club", "category": "subscription", "website": "edenbookclub.com"},
    {"brand_name": "Tyndale House", "category": "publisher", "website": "tyndale.com"},
]


class BrandCRM:
    """Manages brand partner outreach and deal tracking."""

    def __init__(self, db: Session):
        self.db = db

    def seed_prospects(self) -> int:
        """Seed the database with initial brand prospects. Idempotent."""
        seeded = 0
        for prospect in SEED_PROSPECTS:
            existing = (
                self.db.query(BrandContact)
                .filter(BrandContact.brand_name == prospect["brand_name"])
                .first()
            )
            if not existing:
                contact = BrandContact(
                    brand_name=prospect["brand_name"],
                    category=prospect["category"],
                    website=prospect["website"],
                    deal_stage=DealStage.prospect,
                )
                self.db.add(contact)
                seeded += 1

        self.db.flush()
        return seeded

    def get_pipeline(self, stage: Optional[DealStage] = None) -> list[BrandContact]:
        """Get brand deal pipeline, optionally filtered by stage."""
        query = self.db.query(BrandContact)
        if stage:
            query = query.filter(BrandContact.deal_stage == stage)
        return query.order_by(BrandContact.updated_at.desc()).all()

    def advance_stage(self, contact_id: int, new_stage: DealStage) -> None:
        """Move a brand contact to the next deal stage."""
        contact = self.db.query(BrandContact).filter(BrandContact.id == contact_id).first()
        if contact:
            contact.deal_stage = new_stage
            contact.updated_at = datetime.utcnow()
            self.db.flush()

    def record_deal(self, contact_id: int, amount: float) -> None:
        """Record a closed brand deal and log revenue."""
        contact = self.db.query(BrandContact).filter(BrandContact.id == contact_id).first()
        if not contact:
            return

        contact.deal_stage = DealStage.closed_won
        contact.deal_value = amount

        revenue = RevenueLog(
            source_type="sponsorship",
            source_detail=f"Brand: {contact.brand_name}",
            amount=amount,
        )
        self.db.add(revenue)
        self.db.flush()

    @staticmethod
    def calculate_rate_card(followers: int, engagement_rate: float) -> dict:
        """Calculate suggested sponsorship rates based on account metrics.

        Industry standard for faith/lifestyle niche:
        - Story mention: $50-100 per 10K followers
        - Feed post: $100-200 per 10K followers
        - Reel: $150-300 per 10K followers
        - Bundle (post + story + reel): 2.5x single post rate

        Premium multiplier for high engagement (>5%): 1.5x
        """
        base_per_10k = followers / 10000

        premium = 1.5 if engagement_rate > 0.05 else 1.0

        return {
            "followers": followers,
            "engagement_rate": round(engagement_rate * 100, 2),
            "premium_multiplier": premium,
            "rates": {
                "story_mention": round(75 * base_per_10k * premium),
                "feed_post": round(150 * base_per_10k * premium),
                "reel": round(225 * base_per_10k * premium),
                "carousel": round(175 * base_per_10k * premium),
                "bundle_post_story_reel": round(375 * base_per_10k * premium),
                "monthly_ambassador": round(500 * base_per_10k * premium),
            },
            "note": "Rates are suggested starting points. Adjust based on brand budget, exclusivity, and content requirements.",
        }

    def get_outreach_candidates(self, count: int = 10) -> list[BrandContact]:
        """Get prospects that haven't been contacted yet or need follow-up."""
        # Prospects never contacted
        never_contacted = (
            self.db.query(BrandContact)
            .filter(
                BrandContact.deal_stage == DealStage.prospect,
                BrandContact.last_contacted_at.is_(None),
            )
            .limit(count)
            .all()
        )

        if len(never_contacted) >= count:
            return never_contacted

        # Add contacts due for follow-up
        remaining = count - len(never_contacted)
        followup_due = (
            self.db.query(BrandContact)
            .filter(
                BrandContact.deal_stage == DealStage.contacted,
                BrandContact.next_followup_at <= datetime.utcnow(),
            )
            .limit(remaining)
            .all()
        )

        return never_contacted + followup_due
