"""Initial migration - all 13 tables and 9 enums.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enums ---
    trendsource = sa.Enum(
        "google_trends", "reddit", "pinterest", "competitor", "manual",
        name="trendsource",
    )
    contenttype = sa.Enum(
        "daily_verse", "marriage_monday", "parenting_wednesday", "faith_friday",
        "encouragement", "prayer_prompt", "gratitude", "fill_in_blank",
        "this_or_that", "conviction_quote", "parenting_list",
        "marriage_challenge", "carousel", "reel",
        name="contenttype",
    )
    contentstatus = sa.Enum(
        "pending", "approved", "rejected", "posted", "failed",
        name="contentstatus",
    )
    emotionaltone = sa.Enum(
        "hopeful", "challenging", "reflective", "celebratory",
        name="emotionaltone",
    )
    imageprovider = sa.Enum(
        "leonardo", "unsplash", "canva", "pil_fallback",
        name="imageprovider",
    )
    imageformat = sa.Enum(
        "feed_4x5", "feed_1x1", "story_9x16",
        name="imageformat",
    )
    platform = sa.Enum(
        "instagram", "facebook", "tiktok", "pinterest",
        name="platform",
    )
    postingstatus = sa.Enum(
        "scheduled", "posting", "success", "failed", "skipped",
        name="postingstatus",
    )
    dealstage = sa.Enum(
        "prospect", "contacted", "negotiating", "closed_won", "closed_lost",
        name="dealstage",
    )

    # --- Tables ---

    op.create_table(
        "trending_content",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", trendsource, nullable=False),
        sa.Column("topic", sa.String(500), nullable=False),
        sa.Column("score", sa.Float, default=0.0),
        sa.Column("raw_data", sa.JSON),
        sa.Column("url", sa.String(2000)),
        sa.Column("subreddit", sa.String(100)),
        sa.Column("engagement_signals", sa.JSON),
        sa.Column("used", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_trending_content_source", "trending_content", ["source"])
    op.create_index("ix_trending_content_created_at", "trending_content", ["created_at"])
    op.create_index("ix_trending_source_date", "trending_content", ["source", "created_at"])

    op.create_table(
        "bible_verses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("reference", sa.String(100), nullable=False, unique=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("book", sa.String(50), nullable=False),
        sa.Column("chapter", sa.Integer, nullable=False),
        sa.Column("verse_start", sa.Integer, nullable=False),
        sa.Column("verse_end", sa.Integer),
        sa.Column("translation", sa.String(20), server_default="web"),
        sa.Column("last_used_at", sa.DateTime),
        sa.Column("use_count", sa.Integer, server_default="0"),
        sa.Column("fetched_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "generated_content",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("verse_id", sa.Integer, sa.ForeignKey("bible_verses.id")),
        sa.Column("trend_id", sa.Integer, sa.ForeignKey("trending_content.id")),
        sa.Column("content_type", contenttype, nullable=False),
        sa.Column("series_type", sa.String(50)),
        sa.Column("emotional_tone", emotionaltone),
        sa.Column("weekly_theme", sa.String(200)),
        sa.Column("hook", sa.Text),
        sa.Column("caption_short", sa.Text),
        sa.Column("caption_medium", sa.Text),
        sa.Column("caption_long", sa.Text),
        sa.Column("story_text", sa.Text),
        sa.Column("reel_script_15", sa.Text),
        sa.Column("reel_script_30", sa.Text),
        sa.Column("pinterest_description", sa.Text),
        sa.Column("facebook_variation", sa.Text),
        sa.Column("alt_text", sa.Text),
        sa.Column("content_series_fit", sa.Text),
        sa.Column("hashtags_large", sa.JSON),
        sa.Column("hashtags_medium", sa.JSON),
        sa.Column("hashtags_niche", sa.JSON),
        sa.Column("image_prompt", sa.Text),
        sa.Column("status", contentstatus, server_default="pending"),
        sa.Column("scheduled_at", sa.DateTime),
        sa.Column("approved_at", sa.DateTime),
        sa.Column("rejected_reason", sa.Text),
        sa.Column("model_used", sa.String(50)),
        sa.Column("prompt_template_version", sa.String(20)),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("generation_cost_usd", sa.Float),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_generated_content_content_type", "generated_content", ["content_type"])
    op.create_index("ix_generated_content_status", "generated_content", ["status"])
    op.create_index("ix_generated_content_scheduled_at", "generated_content", ["scheduled_at"])
    op.create_index("ix_generated_content_created_at", "generated_content", ["created_at"])

    op.create_table(
        "generated_images",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("content_id", sa.Integer, sa.ForeignKey("generated_content.id"), nullable=False),
        sa.Column("provider", imageprovider, nullable=False),
        sa.Column("format", imageformat, nullable=False),
        sa.Column("raw_url", sa.String(2000)),
        sa.Column("final_url", sa.String(2000)),
        sa.Column("r2_key", sa.String(500)),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("file_size_bytes", sa.Integer),
        sa.Column("leonardo_generation_id", sa.String(100)),
        sa.Column("unsplash_photo_id", sa.String(100)),
        sa.Column("unsplash_attribution", sa.Text),
        sa.Column("canva_design_id", sa.String(100)),
        sa.Column("canva_template_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "posting_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("content_id", sa.Integer, sa.ForeignKey("generated_content.id"), nullable=False),
        sa.Column("platform", platform, nullable=False),
        sa.Column("platform_post_id", sa.String(100)),
        sa.Column("platform_media_id", sa.String(100)),
        sa.Column("status", postingstatus, nullable=False),
        sa.Column("error_message", sa.Text),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("caption_used", sa.Text),
        sa.Column("hashtags_used", sa.JSON),
        sa.Column("posted_at", sa.DateTime),
        sa.Column("scheduled_for", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_posting_log_status", "posting_log", ["status"])
    op.create_index("ix_posting_platform_date", "posting_log", ["platform", "posted_at"])

    op.create_table(
        "analytics_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("content_id", sa.Integer, sa.ForeignKey("generated_content.id"), nullable=False),
        sa.Column("posting_log_id", sa.Integer, sa.ForeignKey("posting_log.id")),
        sa.Column("platform", platform, nullable=False),
        sa.Column("captured_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("hours_after_post", sa.Integer),
        sa.Column("likes", sa.Integer, server_default="0"),
        sa.Column("comments", sa.Integer, server_default="0"),
        sa.Column("shares", sa.Integer, server_default="0"),
        sa.Column("saves", sa.Integer, server_default="0"),
        sa.Column("reach", sa.Integer, server_default="0"),
        sa.Column("impressions", sa.Integer, server_default="0"),
        sa.Column("profile_visits", sa.Integer, server_default="0"),
        sa.Column("website_clicks", sa.Integer, server_default="0"),
        sa.Column("engagement_rate", sa.Float),
    )
    op.create_index("ix_analytics_content_time", "analytics_snapshots", ["content_id", "captured_at"])

    op.create_table(
        "competitor_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("page_handle", sa.String(100), nullable=False),
        sa.Column("platform", platform, server_default="instagram"),
        sa.Column("followers", sa.Integer),
        sa.Column("following", sa.Integer),
        sa.Column("post_count", sa.Integer),
        sa.Column("avg_engagement_rate", sa.Float),
        sa.Column("recent_post_types", sa.JSON),
        sa.Column("top_hashtags", sa.JSON),
        sa.Column("posting_frequency_per_week", sa.Float),
        sa.Column("avg_likes_recent", sa.Integer),
        sa.Column("avg_comments_recent", sa.Integer),
        sa.Column("captured_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_competitor_snapshots_page_handle", "competitor_snapshots", ["page_handle"])
    op.create_index("ix_competitor_snapshots_captured_at", "competitor_snapshots", ["captured_at"])

    op.create_table(
        "content_calendar_slots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.DateTime, nullable=False),
        sa.Column("time_slot", sa.String(10), nullable=False),
        sa.Column("content_type", contenttype, nullable=False),
        sa.Column("series_type", sa.String(50)),
        sa.Column("emotional_tone", emotionaltone),
        sa.Column("theme", sa.String(200)),
        sa.Column("content_id", sa.Integer, sa.ForeignKey("generated_content.id")),
        sa.Column("filled", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("date", "time_slot", name="uq_calendar_date_slot"),
    )

    op.create_table(
        "hashtag_performance",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("hashtag", sa.String(100), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("estimated_posts", sa.Integer),
        sa.Column("times_used", sa.Integer, server_default="0"),
        sa.Column("avg_reach_when_used", sa.Float),
        sa.Column("avg_engagement_when_used", sa.Float),
        sa.Column("performance_score", sa.Float, server_default="50.0"),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("last_used_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_hashtag_performance_hashtag", "hashtag_performance", ["hashtag"])

    op.create_table(
        "affiliate_links",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("program", sa.String(100), nullable=False),
        sa.Column("product_name", sa.String(300), nullable=False),
        sa.Column("original_url", sa.String(2000), nullable=False),
        sa.Column("tracked_url", sa.String(2000), nullable=False),
        sa.Column("commission_rate", sa.Float),
        sa.Column("commission_type", sa.String(20)),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "affiliate_clicks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("link_id", sa.Integer, sa.ForeignKey("affiliate_links.id"), nullable=False),
        sa.Column("clicked_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("utm_source", sa.String(100)),
        sa.Column("utm_medium", sa.String(100)),
        sa.Column("utm_campaign", sa.String(100)),
        sa.Column("converted", sa.Boolean, server_default="false"),
        sa.Column("commission_earned", sa.Float),
    )
    op.create_index("ix_affiliate_clicks_clicked_at", "affiliate_clicks", ["clicked_at"])

    op.create_table(
        "email_subscribers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("source", sa.String(100)),
        sa.Column("tags", sa.JSON),
        sa.Column("convertkit_subscriber_id", sa.String(50)),
        sa.Column("subscribed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("unsubscribed_at", sa.DateTime),
        sa.Column("active", sa.Boolean, server_default="true"),
    )

    op.create_table(
        "revenue_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_detail", sa.String(200)),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("recorded_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_revenue_log_recorded_at", "revenue_log", ["recorded_at"])

    op.create_table(
        "brand_contacts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("brand_name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(200)),
        sa.Column("contact_email", sa.String(320)),
        sa.Column("website", sa.String(2000)),
        sa.Column("category", sa.String(100)),
        sa.Column("notes", sa.Text),
        sa.Column("deal_stage", dealstage, server_default="prospect"),
        sa.Column("deal_value", sa.Float),
        sa.Column("last_contacted_at", sa.DateTime),
        sa.Column("next_followup_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("brand_contacts")
    op.drop_table("revenue_log")
    op.drop_table("email_subscribers")
    op.drop_table("affiliate_clicks")
    op.drop_table("affiliate_links")
    op.drop_table("hashtag_performance")
    op.drop_table("content_calendar_slots")
    op.drop_table("competitor_snapshots")
    op.drop_table("analytics_snapshots")
    op.drop_table("posting_log")
    op.drop_table("generated_images")
    op.drop_table("generated_content")
    op.drop_table("bible_verses")
    op.drop_table("trending_content")

    for name in ["dealstage", "postingstatus", "platform", "imageformat",
                 "imageprovider", "emotionaltone", "contentstatus",
                 "contenttype", "trendsource"]:
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
