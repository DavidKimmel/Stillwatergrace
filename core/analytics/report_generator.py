"""Weekly performance report generator.

Generates an HTML report with key metrics, top posts, and recommendations.
Sent via SendGrid every Monday morning.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import settings
from database.models import (
    PostingLog,
    PostingStatus,
    AnalyticsSnapshot,
    GeneratedContent,
    ContentType,
    Platform,
    CompetitorSnapshot,
    RevenueLog,
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates weekly performance reports."""

    def __init__(self, db: Session):
        self.db = db

    def generate_and_send(self) -> None:
        """Generate the weekly report and email it."""
        report_data = self._gather_data()
        html = self._render_html(report_data)
        self._send_email(html)

    def _gather_data(self) -> dict:
        """Gather all data needed for the weekly report."""
        week_ago = datetime.utcnow() - timedelta(days=7)

        # Posts this week
        posts_count = (
            self.db.query(func.count(PostingLog.id))
            .filter(
                PostingLog.posted_at >= week_ago,
                PostingLog.status == PostingStatus.success,
            )
            .scalar()
        ) or 0

        # Engagement totals (24hr snapshots only)
        engagement = (
            self.db.query(
                func.sum(AnalyticsSnapshot.likes).label("likes"),
                func.sum(AnalyticsSnapshot.comments).label("comments"),
                func.sum(AnalyticsSnapshot.saves).label("saves"),
                func.sum(AnalyticsSnapshot.shares).label("shares"),
                func.sum(AnalyticsSnapshot.reach).label("reach"),
                func.avg(AnalyticsSnapshot.engagement_rate).label("avg_engagement"),
            )
            .filter(
                AnalyticsSnapshot.captured_at >= week_ago,
                AnalyticsSnapshot.hours_after_post == 24,
            )
            .first()
        )

        # Top 5 posts by saves
        top_posts = (
            self.db.query(AnalyticsSnapshot)
            .filter(
                AnalyticsSnapshot.captured_at >= week_ago,
                AnalyticsSnapshot.hours_after_post == 24,
            )
            .order_by(AnalyticsSnapshot.saves.desc())
            .limit(5)
            .all()
        )

        # Content type performance
        type_performance = (
            self.db.query(
                GeneratedContent.content_type,
                func.avg(AnalyticsSnapshot.saves).label("avg_saves"),
                func.avg(AnalyticsSnapshot.engagement_rate).label("avg_engagement"),
                func.count(AnalyticsSnapshot.id).label("count"),
            )
            .join(AnalyticsSnapshot, AnalyticsSnapshot.content_id == GeneratedContent.id)
            .filter(
                AnalyticsSnapshot.captured_at >= week_ago,
                AnalyticsSnapshot.hours_after_post == 24,
            )
            .group_by(GeneratedContent.content_type)
            .order_by(func.avg(AnalyticsSnapshot.saves).desc())
            .all()
        )

        # Revenue this week
        revenue = (
            self.db.query(func.sum(RevenueLog.amount))
            .filter(RevenueLog.recorded_at >= week_ago)
            .scalar()
        ) or 0

        return {
            "period": f"{week_ago.strftime('%b %d')} — {datetime.utcnow().strftime('%b %d, %Y')}",
            "posts_count": posts_count,
            "total_likes": engagement.likes or 0 if engagement else 0,
            "total_comments": engagement.comments or 0 if engagement else 0,
            "total_saves": engagement.saves or 0 if engagement else 0,
            "total_shares": engagement.shares or 0 if engagement else 0,
            "total_reach": engagement.reach or 0 if engagement else 0,
            "avg_engagement": round(engagement.avg_engagement or 0, 4) if engagement else 0,
            "top_posts": top_posts,
            "type_performance": type_performance,
            "revenue": round(revenue, 2),
        }

    def _render_html(self, data: dict) -> str:
        """Render the report as HTML email."""
        top_posts_html = ""
        for i, post in enumerate(data["top_posts"], 1):
            top_posts_html += f"""
            <tr>
                <td>{i}</td>
                <td>#{post.content_id}</td>
                <td>{post.saves}</td>
                <td>{post.shares}</td>
                <td>{post.reach}</td>
                <td>{round(post.engagement_rate * 100, 2) if post.engagement_rate else 0}%</td>
            </tr>"""

        type_perf_html = ""
        for tp in data["type_performance"]:
            type_perf_html += f"""
            <tr>
                <td>{tp.content_type.value if tp.content_type else 'N/A'}</td>
                <td>{round(tp.avg_saves or 0, 1)}</td>
                <td>{round((tp.avg_engagement or 0) * 100, 2)}%</td>
                <td>{tp.count}</td>
            </tr>"""

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #2D4A3E; max-width: 640px; margin: 0 auto; padding: 20px; }}
                h1 {{ color: #D4A853; }}
                h2 {{ color: #2D4A3E; border-bottom: 2px solid #D4A853; padding-bottom: 8px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
                th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }}
                th {{ background: #FFF8F0; color: #2D4A3E; }}
                .metric {{ display: inline-block; width: 30%; text-align: center; padding: 16px; background: #FFF8F0; border-radius: 8px; margin: 4px; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #D4A853; }}
                .metric-label {{ font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <h1>StillWaterGrace Weekly Report</h1>
            <p>{data['period']}</p>

            <h2>Key Metrics</h2>
            <div>
                <div class="metric">
                    <div class="metric-value">{data['posts_count']}</div>
                    <div class="metric-label">Posts Published</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{data['total_reach']:,}</div>
                    <div class="metric-label">Total Reach</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{round(data['avg_engagement'] * 100, 2)}%</div>
                    <div class="metric-label">Avg Engagement Rate</div>
                </div>
            </div>
            <div>
                <div class="metric">
                    <div class="metric-value">{data['total_saves']:,}</div>
                    <div class="metric-label">Total Saves</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{data['total_shares']:,}</div>
                    <div class="metric-label">Total Shares</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${data['revenue']}</div>
                    <div class="metric-label">Revenue</div>
                </div>
            </div>

            <h2>Top 5 Posts (by Saves)</h2>
            <table>
                <tr><th>#</th><th>Content</th><th>Saves</th><th>Shares</th><th>Reach</th><th>Engagement</th></tr>
                {top_posts_html}
            </table>

            <h2>Content Type Performance</h2>
            <table>
                <tr><th>Type</th><th>Avg Saves</th><th>Avg Engagement</th><th>Posts</th></tr>
                {type_perf_html}
            </table>

            <p style="color: #999; font-size: 12px; margin-top: 40px;">
                Generated automatically by StillWaterGrace Content Platform
            </p>
        </body>
        </html>
        """

    def _send_email(self, html: str) -> None:
        """Send the report via SendGrid."""
        if not settings.sendgrid_api_key or not settings.alert_email_to:
            logger.warning("SendGrid not configured, saving report to file instead")
            # Save locally as fallback
            from pathlib import Path
            report_path = Path("reports")
            report_path.mkdir(exist_ok=True)
            filename = f"weekly_report_{datetime.utcnow().strftime('%Y%m%d')}.html"
            (report_path / filename).write_text(html)
            logger.info(f"Report saved to reports/{filename}")
            return

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=settings.alert_email_from,
                to_emails=settings.alert_email_to,
                subject=f"StillWaterGrace Weekly Report — {datetime.utcnow().strftime('%b %d')}",
                html_content=html,
            )

            sg = SendGridAPIClient(settings.sendgrid_api_key)
            response = sg.send(message)
            logger.info(f"Weekly report sent (status: {response.status_code})")

        except Exception as e:
            logger.error(f"Failed to send weekly report: {e}")
