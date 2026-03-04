"""Monetization tracking API routes."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.session import get_db_dependency
from database.models import (
    RevenueLog,
    AffiliateLink,
    AffiliateClick,
    BrandContact,
    DealStage,
    EmailSubscriber,
)

router = APIRouter()


@router.get("/revenue/summary")
def get_revenue_summary(
    months: int = Query(default=6, le=12),
    db: Session = Depends(get_db_dependency),
):
    """Get revenue summary by source type."""
    since = datetime.utcnow() - timedelta(days=months * 30)

    by_source = (
        db.query(
            RevenueLog.source_type,
            func.sum(RevenueLog.amount).label("total"),
            func.count(RevenueLog.id).label("transactions"),
        )
        .filter(RevenueLog.recorded_at >= since)
        .group_by(RevenueLog.source_type)
        .all()
    )

    total = sum(r.total or 0 for r in by_source)

    return {
        "period_months": months,
        "total_revenue": round(total, 2),
        "by_source": [
            {
                "source": r.source_type,
                "total": round(r.total or 0, 2),
                "transactions": r.transactions,
            }
            for r in by_source
        ],
    }


@router.get("/affiliates")
def get_affiliate_links(db: Session = Depends(get_db_dependency)):
    """Get all affiliate links with click stats."""
    links = db.query(AffiliateLink).filter(AffiliateLink.active == True).all()

    result = []
    for link in links:
        click_count = (
            db.query(func.count(AffiliateClick.id))
            .filter(AffiliateClick.link_id == link.id)
            .scalar()
        )
        conversions = (
            db.query(func.count(AffiliateClick.id))
            .filter(AffiliateClick.link_id == link.id, AffiliateClick.converted == True)
            .scalar()
        )
        result.append({
            "id": link.id,
            "program": link.program,
            "product_name": link.product_name,
            "tracked_url": link.tracked_url,
            "commission_rate": link.commission_rate,
            "clicks": click_count,
            "conversions": conversions,
        })

    return result


@router.get("/brand-deals")
def get_brand_deals(
    stage: Optional[DealStage] = None,
    db: Session = Depends(get_db_dependency),
):
    """Get brand deal pipeline."""
    query = db.query(BrandContact)
    if stage:
        query = query.filter(BrandContact.deal_stage == stage)

    contacts = query.order_by(BrandContact.updated_at.desc()).all()

    return [
        {
            "id": c.id,
            "brand_name": c.brand_name,
            "contact_name": c.contact_name,
            "category": c.category,
            "deal_stage": c.deal_stage.value if c.deal_stage else None,
            "deal_value": c.deal_value,
            "last_contacted_at": c.last_contacted_at.isoformat() if c.last_contacted_at else None,
            "next_followup_at": c.next_followup_at.isoformat() if c.next_followup_at else None,
        }
        for c in contacts
    ]


@router.get("/subscribers")
def get_subscriber_stats(db: Session = Depends(get_db_dependency)):
    """Get email subscriber statistics."""
    total = db.query(func.count(EmailSubscriber.id)).filter(EmailSubscriber.active == True).scalar()

    by_source = (
        db.query(
            EmailSubscriber.source,
            func.count(EmailSubscriber.id).label("count"),
        )
        .filter(EmailSubscriber.active == True)
        .group_by(EmailSubscriber.source)
        .all()
    )

    return {
        "total_active": total,
        "by_source": [{"source": s.source, "count": s.count} for s in by_source],
    }
