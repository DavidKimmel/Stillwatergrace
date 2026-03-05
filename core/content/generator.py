"""Claude API content generation engine.

Core of the platform — generates all content using Claude with structured
prompt templates and validates output format.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import anthropic
from sqlalchemy.orm import Session

from core.config import settings
from core.content.prompt_templates import get_template_engine
from database.models import (
    GeneratedContent,
    ContentType,
    ContentStatus,
    EmotionalTone,
    BibleVerse,
    TrendingContent,
    TrendSource,
)

logger = logging.getLogger(__name__)

# Claude model to use — Sonnet for cost-effective high quality
MODEL = "claude-sonnet-4-6"

# Cost per token (approximate, for tracking)
COST_PER_INPUT_TOKEN = 3.0 / 1_000_000   # $3 per 1M input tokens
COST_PER_OUTPUT_TOKEN = 15.0 / 1_000_000  # $15 per 1M output tokens

# Required keys in generated content JSON
REQUIRED_KEYS = {
    "hook", "caption_short", "caption_medium", "caption_long",
    "story_text", "reel_script_15", "reel_script_30",
    "hashtags_large", "hashtags_medium", "hashtags_niche",
    "pinterest_description", "facebook_variation",
    "image_prompt", "alt_text",
    "emotional_tone",
}

# Content type choices for daily verse
CONTENT_TYPE_CHOICES = ["encouragement", "challenge", "reflection", "prayer prompt", "devotional"]


class ContentGenerator:
    """Generates content using Claude API with structured prompts."""

    def __init__(self, db: Session):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.templates = get_template_engine()
        self.system_prompt = self.templates.get_system_prompt()

    def generate_daily_content(self) -> int:
        """Generate content for all of today's calendar slots.

        Called by the daily Celery task. Returns number of pieces generated.
        """
        from core.content.calendar_logic import ContentCalendar

        calendar = ContentCalendar(self.db)
        today_slots = calendar.get_todays_slots()
        generated = 0

        for slot in today_slots:
            try:
                content = self._generate_for_slot(slot)
                if content:
                    generated += 1
                    logger.info(f"Generated {slot['content_type']} for {slot['time_slot']}")
            except Exception as e:
                logger.error(f"Failed to generate for slot {slot}: {e}")
                continue

        return generated

    def generate_single(
        self,
        content_type: ContentType,
        verse: Optional[BibleVerse] = None,
        trending_topic: str = "",
        theme: str = "",
        **kwargs,
    ) -> Optional[GeneratedContent]:
        """Generate a single content piece.

        This is the main generation method that other methods delegate to.
        """
        # Build the prompt based on content type
        prompt = self._build_prompt(content_type, verse, trending_topic, theme, **kwargs)
        if not prompt:
            logger.error(f"Failed to build prompt for {content_type}")
            return None

        # Call Claude API
        response_data, usage = self._call_claude(prompt)
        if not response_data:
            return None

        # Create content record
        content = self._store_content(
            content_type=content_type,
            data=response_data,
            verse=verse,
            trending_topic=trending_topic,
            theme=theme,
            usage=usage,
            scheduled_at=kwargs.get("scheduled_at"),
        )

        return content

    def _generate_for_slot(self, slot: dict) -> Optional[GeneratedContent]:
        """Generate content for a specific calendar slot."""
        content_type_str = slot["content_type"]
        content_type = ContentType(content_type_str)

        # Get a verse for verse-based content
        verse = None
        if content_type in {ContentType.daily_verse, ContentType.encouragement, ContentType.gratitude, ContentType.prayer_prompt}:
            from core.scraper.bible_api import BibleAPIClient
            bible = BibleAPIClient(self.db)
            verse = bible.fetch_daily_verse()

        # Get the top trending topic
        trending_topic = self._get_top_trend()

        # Get theme from slot
        theme = slot.get("theme", "")

        return self.generate_single(
            content_type=content_type,
            verse=verse,
            trending_topic=trending_topic,
            theme=theme,
            age_group=slot.get("age_group", "general"),
            scheduled_at=slot.get("scheduled_at"),
        )

    def _build_prompt(
        self,
        content_type: ContentType,
        verse: Optional[BibleVerse],
        trending_topic: str,
        theme: str,
        **kwargs,
    ) -> Optional[str]:
        """Build the generation prompt based on content type."""
        if content_type in {ContentType.daily_verse, ContentType.encouragement, ContentType.gratitude, ContentType.prayer_prompt}:
            if not verse:
                logger.warning(f"No verse available for {content_type}")
                return None
            import random
            ct = random.choice(CONTENT_TYPE_CHOICES)
            return self.templates.render_daily_verse(
                verse_text=verse.text,
                verse_reference=verse.reference,
                content_type=ct,
                trending_topic=trending_topic,
            )

        elif content_type == ContentType.marriage_monday:
            return self.templates.render_marriage_monday(
                weekly_marriage_theme=theme or "communication",
                trending_topic=trending_topic,
            )

        elif content_type == ContentType.parenting_wednesday:
            return self.templates.render_parenting_wednesday(
                age_group=kwargs.get("age_group", "general"),
                parenting_theme=theme or "patience",
                trending_topic=trending_topic,
            )

        elif content_type == ContentType.faith_friday:
            return self.templates.render_faith_friday(
                hardship_topic=theme or "waiting seasons",
                trending_topic=trending_topic,
            )

        elif content_type in {
            ContentType.fill_in_blank, ContentType.this_or_that,
            ContentType.conviction_quote, ContentType.parenting_list,
            ContentType.marriage_challenge,
        }:
            return self.templates.render_viral_formats(trending_topic=trending_topic)

        else:
            # Default: use daily verse prompt
            if verse:
                return self.templates.render_daily_verse(
                    verse_text=verse.text,
                    verse_reference=verse.reference,
                    trending_topic=trending_topic,
                )
            return None

    def _call_claude(self, user_prompt: str) -> tuple[Optional[dict], Optional[dict]]:
        """Call Claude API and parse JSON response.

        Returns (parsed_data, usage_dict) or (None, None) on failure.
        """
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return None, None

        # Extract text from response
        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        # Parse JSON
        try:
            # Strip any markdown code fences
            clean = text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()

            data = json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.debug(f"Raw response: {text[:500]}")
            return None, None

        # Usage tracking
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": MODEL,
        }

        return data, usage

    def _store_content(
        self,
        content_type: ContentType,
        data: dict,
        verse: Optional[BibleVerse],
        trending_topic: str,
        theme: str,
        usage: Optional[dict],
        scheduled_at: Optional[datetime] = None,
    ) -> GeneratedContent:
        """Validate and store generated content in the database."""
        # Handle viral format (returns array)
        if isinstance(data, list):
            # Store first item, queue rest
            if data:
                data = data[0]
            else:
                data = {}

        # Map emotional tone
        tone_str = data.get("emotional_tone", "hopeful")
        try:
            tone = EmotionalTone(tone_str)
        except ValueError:
            tone = EmotionalTone.hopeful

        # Calculate cost
        cost = 0.0
        if usage:
            cost = (
                usage.get("input_tokens", 0) * COST_PER_INPUT_TOKEN
                + usage.get("output_tokens", 0) * COST_PER_OUTPUT_TOKEN
            )

        content = GeneratedContent(
            verse_id=verse.id if verse else None,
            content_type=content_type,
            series_type=self._get_series_type(content_type),
            emotional_tone=tone,
            weekly_theme=theme,
            hook=data.get("hook", ""),
            caption_short=data.get("caption_short", ""),
            caption_medium=data.get("caption_medium", ""),
            caption_long=data.get("caption_long", ""),
            story_text=data.get("story_text", ""),
            reel_script_15=data.get("reel_script_15", ""),
            reel_script_30=data.get("reel_script_30", ""),
            pinterest_description=data.get("pinterest_description", ""),
            facebook_variation=data.get("facebook_variation", ""),
            alt_text=data.get("alt_text", ""),
            content_series_fit=data.get("content_series_fit", ""),
            hashtags_large=data.get("hashtags_large", []),
            hashtags_medium=data.get("hashtags_medium", []),
            hashtags_niche=data.get("hashtags_niche", []),
            image_prompt=data.get("image_prompt", ""),
            scheduled_at=scheduled_at,
            status=ContentStatus.pending,
            model_used=usage.get("model", MODEL) if usage else MODEL,
            prompt_template_version=self.templates.version,
            input_tokens=usage.get("input_tokens") if usage else None,
            output_tokens=usage.get("output_tokens") if usage else None,
            generation_cost_usd=round(cost, 6),
        )

        self.db.add(content)
        self.db.flush()

        # Auto-approve if enabled
        if settings.auto_approve_content:
            content.status = ContentStatus.approved
            content.approved_at = datetime.utcnow()
            self.db.flush()
            logger.info(f"Auto-approved content #{content.id}")

        logger.info(
            f"Stored content #{content.id} ({content_type.value}) "
            f"— {usage.get('input_tokens', 0)}+{usage.get('output_tokens', 0)} tokens, "
            f"${cost:.4f}"
        )

        return content

    def _get_top_trend(self) -> str:
        """Get the highest-scoring unused trend topic."""
        trend = (
            self.db.query(TrendingContent)
            .filter(TrendingContent.used == False)
            .order_by(TrendingContent.score.desc())
            .first()
        )
        if trend:
            trend.used = True
            self.db.flush()
            return trend.topic
        return ""

    @staticmethod
    def _get_series_type(content_type: ContentType) -> Optional[str]:
        """Map content type to series name."""
        mapping = {
            ContentType.marriage_monday: "marriage_monday",
            ContentType.parenting_wednesday: "parenting_wednesday",
            ContentType.faith_friday: "faith_friday",
        }
        return mapping.get(content_type)
