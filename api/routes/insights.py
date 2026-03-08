"""Insights API routes — performance analysis + competitor activity."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.analytics.performance_analyzer import PerformanceAnalyzer
from database.session import get_db_dependency

router = APIRouter()


@router.get("/recommendations")
def get_recommendations(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db_dependency),
):
    """Get top 3-5 actionable recommendations."""
    analyzer = PerformanceAnalyzer(db)
    return analyzer.generate_recommendations(days)


@router.get("/content-type-performance")
def get_content_type_performance(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db_dependency),
):
    """Get performance breakdown by content type."""
    analyzer = PerformanceAnalyzer(db)
    return analyzer.get_content_type_performance(days)


@router.get("/format-performance")
def get_format_performance(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db_dependency),
):
    """Get performance breakdown by media format."""
    analyzer = PerformanceAnalyzer(db)
    return analyzer.get_format_performance(days)


@router.get("/time-performance")
def get_time_performance(
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db_dependency),
):
    """Get performance breakdown by posting time."""
    analyzer = PerformanceAnalyzer(db)
    return analyzer.get_time_slot_performance(days)


@router.get("/competitor-activity")
def get_competitor_activity(
    days: int = Query(default=14, le=90),
    db: Session = Depends(get_db_dependency),
):
    """Get competitor posting activity summary."""
    analyzer = PerformanceAnalyzer(db)
    return analyzer.get_competitor_activity(days)
