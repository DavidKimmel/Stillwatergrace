"""SQLAlchemy ORM models for the StillWaterGrace platform."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SAEnum,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class ContentStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    posted = "posted"
    failed = "failed"


class ContentType(str, enum.Enum):
    daily_verse = "daily_verse"
    marriage_monday = "marriage_monday"
    parenting_wednesday = "parenting_wednesday"
    faith_friday = "faith_friday"
    encouragement = "encouragement"
    prayer_prompt = "prayer_prompt"
    gratitude = "gratitude"
    fill_in_blank = "fill_in_blank"
    this_or_that = "this_or_that"
    conviction_quote = "conviction_quote"
    parenting_list = "parenting_list"
    marriage_challenge = "marriage_challenge"
    carousel = "carousel"
    reel = "reel"


class Platform(str, enum.Enum):
    instagram = "instagram"
    facebook = "facebook"
    tiktok = "tiktok"
    pinterest = "pinterest"


class ImageProvider(str, enum.Enum):
    leonardo = "leonardo"
    unsplash = "unsplash"
    canva = "canva"
    pil_fallback = "pil_fallback"


class ImageFormat(str, enum.Enum):
    feed_4x5 = "feed_4x5"
    feed_1x1 = "feed_1x1"
    story_9x16 = "story_9x16"
    reel_9x16 = "reel_9x16"


class PostingStatus(str, enum.Enum):
    scheduled = "scheduled"
    posting = "posting"
    success = "success"
    failed = "failed"
    skipped = "skipped"


class TrendSource(str, enum.Enum):
    google_trends = "google_trends"
    reddit = "reddit"
    pinterest = "pinterest"
    competitor = "competitor"
    manual = "manual"


class EmotionalTone(str, enum.Enum):
    hopeful = "hopeful"
    challenging = "challenging"
    reflective = "reflective"
    celebratory = "celebratory"


class DealStage(str, enum.Enum):
    prospect = "prospect"
    contacted = "contacted"
    negotiating = "negotiating"
    closed_won = "closed_won"
    closed_lost = "closed_lost"


# ──────────────────────────────────────────────
# Trend & Research Tables
# ──────────────────────────────────────────────

class TrendingContent(Base):
    """Scraped trending content from all sources."""
    __tablename__ = "trending_content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(SAEnum(TrendSource), nullable=False, index=True)
    topic = Column(String(500), nullable=False)
    score = Column(Float, default=0.0)  # Normalized 0-100 virality score
    raw_data = Column(JSON)  # Source-specific raw data
    url = Column(String(2000))
    subreddit = Column(String(100))  # For Reddit source
    engagement_signals = Column(JSON)  # likes, comments, shares, etc.
    used = Column(Boolean, default=False)  # Has this been used for content gen?
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_trending_source_date", "source", "created_at"),
    )


class BibleVerse(Base):
    """Cached Bible verses from bible-api.com."""
    __tablename__ = "bible_verses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference = Column(String(100), nullable=False, unique=True)  # e.g. "John 3:16"
    text = Column(Text, nullable=False)
    book = Column(String(50), nullable=False)
    chapter = Column(Integer, nullable=False)
    verse_start = Column(Integer, nullable=False)
    verse_end = Column(Integer)  # For ranges like "Romans 8:28-29"
    translation = Column(String(20), default="web")  # World English Bible (public domain)
    last_used_at = Column(DateTime)  # Track to avoid repeats within 90 days
    use_count = Column(Integer, default=0)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    generated_content = relationship("GeneratedContent", back_populates="verse")


# ──────────────────────────────────────────────
# Content Generation Tables
# ──────────────────────────────────────────────

class GeneratedContent(Base):
    """AI-generated content pieces ready for review and posting."""
    __tablename__ = "generated_content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    verse_id = Column(Integer, ForeignKey("bible_verses.id"), nullable=True)
    trend_id = Column(Integer, ForeignKey("trending_content.id"), nullable=True)

    # Content metadata
    content_type = Column(SAEnum(ContentType), nullable=False, index=True)
    series_type = Column(String(50))  # e.g. "marriage_monday", "faith_friday"
    emotional_tone = Column(SAEnum(EmotionalTone))
    weekly_theme = Column(String(200))

    # All generated text (stored as JSON for flexibility)
    hook = Column(Text)
    caption_short = Column(Text)  # Under 150 chars
    caption_medium = Column(Text)  # 150-300 chars
    caption_long = Column(Text)  # 300-500 chars
    story_text = Column(Text)  # Instagram story overlay
    reel_script_15 = Column(Text)  # 15-sec reel script
    reel_script_30 = Column(Text)  # 30-sec reel script
    pinterest_description = Column(Text)
    facebook_variation = Column(Text)
    alt_text = Column(Text)
    content_series_fit = Column(Text)

    # Hashtags (JSON arrays)
    hashtags_large = Column(JSON)  # 10 hashtags >1M posts
    hashtags_medium = Column(JSON)  # 10 hashtags 100K-1M
    hashtags_niche = Column(JSON)  # 10 hashtags <100K

    # Image generation
    image_prompt = Column(Text)  # Leonardo.ai prompt

    # Workflow
    status = Column(SAEnum(ContentStatus), default=ContentStatus.pending, index=True)
    scheduled_at = Column(DateTime, index=True)
    approved_at = Column(DateTime)
    rejected_reason = Column(Text)

    # Generation metadata
    model_used = Column(String(50))  # e.g. "claude-sonnet-4-6"
    prompt_template_version = Column(String(20))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    generation_cost_usd = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    verse = relationship("BibleVerse", back_populates="generated_content")
    trend = relationship("TrendingContent")
    images = relationship("GeneratedImage", back_populates="content")
    posting_logs = relationship("PostingLog", back_populates="content")
    analytics = relationship("AnalyticsSnapshot", back_populates="content")


class GeneratedImage(Base):
    """Generated or sourced images linked to content."""
    __tablename__ = "generated_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("generated_content.id"), nullable=False)

    provider = Column(SAEnum(ImageProvider), nullable=False)
    format = Column(SAEnum(ImageFormat), nullable=False)

    # URLs
    raw_url = Column(String(2000))  # Original from provider
    final_url = Column(String(2000))  # After Canva/PIL overlay, stored in R2
    r2_key = Column(String(500))  # Cloudflare R2 object key

    # Metadata
    width = Column(Integer)
    height = Column(Integer)
    file_size_bytes = Column(Integer)
    leonardo_generation_id = Column(String(100))
    unsplash_photo_id = Column(String(100))
    unsplash_attribution = Column(Text)  # Required by Unsplash TOS
    canva_design_id = Column(String(100))
    canva_template_id = Column(String(100))

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    content = relationship("GeneratedContent", back_populates="images")


# ──────────────────────────────────────────────
# Posting & Distribution Tables
# ──────────────────────────────────────────────

class PostingLog(Base):
    """Record of every post attempt across platforms."""
    __tablename__ = "posting_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("generated_content.id"), nullable=False)
    platform = Column(SAEnum(Platform), nullable=False)

    # Platform-specific post ID (for analytics retrieval)
    platform_post_id = Column(String(100))
    platform_media_id = Column(String(100))

    status = Column(SAEnum(PostingStatus), nullable=False, index=True)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    # Caption actually used (may differ from generated if manually edited)
    caption_used = Column(Text)
    hashtags_used = Column(JSON)

    posted_at = Column(DateTime)
    scheduled_for = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    content = relationship("GeneratedContent", back_populates="posting_logs")

    __table_args__ = (
        Index("ix_posting_platform_date", "platform", "posted_at"),
    )


# ──────────────────────────────────────────────
# Analytics Tables
# ──────────────────────────────────────────────

class AnalyticsSnapshot(Base):
    """Time-series engagement data captured at intervals after posting."""
    __tablename__ = "analytics_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("generated_content.id"), nullable=False)
    posting_log_id = Column(Integer, ForeignKey("posting_log.id"))
    platform = Column(SAEnum(Platform), nullable=False)

    # Timing
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    hours_after_post = Column(Integer)  # 1, 24, 168 (7 days)

    # Engagement metrics
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    reach = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    profile_visits = Column(Integer, default=0)
    website_clicks = Column(Integer, default=0)

    # Calculated
    engagement_rate = Column(Float)  # (likes+comments+saves+shares) / reach

    # Relationships
    content = relationship("GeneratedContent", back_populates="analytics")

    __table_args__ = (
        Index("ix_analytics_content_time", "content_id", "captured_at"),
    )


class CompetitorSnapshot(Base):
    """Weekly competitor page metrics."""
    __tablename__ = "competitor_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_handle = Column(String(100), nullable=False, index=True)
    platform = Column(SAEnum(Platform), default=Platform.instagram)

    followers = Column(Integer)
    following = Column(Integer)
    post_count = Column(Integer)
    avg_engagement_rate = Column(Float)

    # Recent post analysis
    recent_post_types = Column(JSON)  # Distribution of content types
    top_hashtags = Column(JSON)  # Most used hashtags
    posting_frequency_per_week = Column(Float)
    avg_likes_recent = Column(Integer)
    avg_comments_recent = Column(Integer)

    captured_at = Column(DateTime, default=datetime.utcnow, index=True)


# ──────────────────────────────────────────────
# Content Calendar
# ──────────────────────────────────────────────

class ContentCalendarSlot(Base):
    """Pre-planned content calendar slots."""
    __tablename__ = "content_calendar_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False)
    time_slot = Column(String(10), nullable=False)  # "morning", "noon", "evening"
    content_type = Column(SAEnum(ContentType), nullable=False)
    series_type = Column(String(50))
    emotional_tone = Column(SAEnum(EmotionalTone))
    theme = Column(String(200))
    content_id = Column(Integer, ForeignKey("generated_content.id"))  # Linked when generated
    filled = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("date", "time_slot", name="uq_calendar_date_slot"),
    )


# ──────────────────────────────────────────────
# Hashtag Tracking
# ──────────────────────────────────────────────

class HashtagPerformance(Base):
    """Track hashtag effectiveness over time."""
    __tablename__ = "hashtag_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hashtag = Column(String(100), nullable=False, index=True)
    tier = Column(String(20), nullable=False)  # "large", "medium", "niche"
    estimated_posts = Column(Integer)  # Total posts using this hashtag

    # Performance when we use this hashtag
    times_used = Column(Integer, default=0)
    avg_reach_when_used = Column(Float)
    avg_engagement_when_used = Column(Float)

    # Scoring
    performance_score = Column(Float, default=50.0)  # 0-100
    active = Column(Boolean, default=True)  # False = rotated out

    last_used_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────────────────────────────────────
# Monetization Tables
# ──────────────────────────────────────────────

class AffiliateLink(Base):
    """Managed affiliate links with UTM tracking."""
    __tablename__ = "affiliate_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    program = Column(String(100), nullable=False)  # "amazon", "christianbook", etc.
    product_name = Column(String(300), nullable=False)
    original_url = Column(String(2000), nullable=False)
    tracked_url = Column(String(2000), nullable=False)  # With UTM params
    commission_rate = Column(Float)  # Percentage or fixed amount
    commission_type = Column(String(20))  # "percentage" or "fixed"

    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AffiliateClick(Base):
    """Click tracking for affiliate links."""
    __tablename__ = "affiliate_clicks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    link_id = Column(Integer, ForeignKey("affiliate_links.id"), nullable=False)
    clicked_at = Column(DateTime, default=datetime.utcnow, index=True)
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(100))
    converted = Column(Boolean, default=False)
    commission_earned = Column(Float)

    link = relationship("AffiliateLink")


class EmailSubscriber(Base):
    """Mirror of email marketing subscribers."""
    __tablename__ = "email_subscribers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(320), nullable=False, unique=True)
    source = Column(String(100))  # "link_in_bio", "gumroad_purchase", etc.
    tags = Column(JSON)  # ConvertKit tags
    convertkit_subscriber_id = Column(String(50))
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    unsubscribed_at = Column(DateTime)
    active = Column(Boolean, default=True)


class RevenueLog(Base):
    """All revenue entries across all sources."""
    __tablename__ = "revenue_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(50), nullable=False)  # "affiliate", "product", "sponsorship", "creator_bonus"
    source_detail = Column(String(200))  # Specific product or program
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    notes = Column(Text)


class BrandContact(Base):
    """CRM for potential brand partners."""
    __tablename__ = "brand_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_name = Column(String(200), nullable=False)
    contact_name = Column(String(200))
    contact_email = Column(String(320))
    website = Column(String(2000))
    category = Column(String(100))  # "publisher", "apparel", "family_product", etc.
    notes = Column(Text)

    # Deal tracking
    deal_stage = Column(SAEnum(DealStage), default=DealStage.prospect)
    deal_value = Column(Float)
    last_contacted_at = Column(DateTime)
    next_followup_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
