"""Devotional content generator using Claude API.

Generates reflections, prayers, and questions for each day of a devotional,
given a theme configuration and Bible verses.
"""

import json
import logging
from typing import Any

import anthropic
import httpx

from core.config import settings
from core.content.prompt_templates import PromptTemplateEngine
from core.devotional.themes import DevotionalTheme

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
BIBLE_API_URL = "https://bible-api.com"


class DevotionalGenerator:
    """Generates devotional text content via Claude API."""

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.templates = PromptTemplateEngine()

    def _fetch_verse_text(self, verse_ref: str) -> str:
        """Fetch verse text from bible-api.com."""
        ref_encoded = verse_ref.replace(" ", "%20")
        resp = httpx.get(f"{BIBLE_API_URL}/{ref_encoded}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("text", "").strip()

    def generate_day_content(
        self,
        verse_ref: str,
        verse_text: str,
        day_title: str,
        reflection_focus: str,
        theme_title: str,
        day_number: int = 1,
    ) -> dict[str, Any]:
        """Generate devotional content for a single day.

        Args:
            verse_ref: Bible verse reference (e.g. "Philippians 4:6-7").
            verse_text: Full text of the verse.
            day_title: Title for this day's devotional.
            reflection_focus: Thematic focus hint for the reflection.
            theme_title: Overall devotional theme title.
            day_number: Day number within the series (1-7).

        Returns:
            Dict with keys: reflection, prayer, questions.

        Raises:
            json.JSONDecodeError: If Claude returns unparseable JSON.
            anthropic.APIError: If the Claude API call fails.
        """
        prompt = self.templates.render(
            "devotional_reflection",
            verse_ref=verse_ref,
            verse_text=verse_text,
            day_title=day_title,
            reflection_focus=reflection_focus,
            theme_title=theme_title,
            day_number=day_number,
        )

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)
        logger.info(
            "Generated Day %d reflection (%d+%d tokens)",
            day_number,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return result

    def generate_all_days(
        self, theme: DevotionalTheme
    ) -> list[dict[str, Any]]:
        """Generate devotional content for all 7 days of a theme.

        Fetches verse text from bible-api.com for each day, then calls
        the Claude API to generate the reflection, prayer, and questions.

        Args:
            theme: A DevotionalTheme with 7 DayConfig entries.

        Returns:
            List of 7 dicts, each containing: reflection, prayer, questions,
            verse_ref, verse_text, day_title, day_number.
        """
        results: list[dict[str, Any]] = []

        for day in theme.days:
            verse_text = self._fetch_verse_text(day.verse_ref)
            content = self.generate_day_content(
                verse_ref=day.verse_ref,
                verse_text=verse_text,
                day_title=day.day_title,
                reflection_focus=day.reflection_focus,
                theme_title=theme.title,
                day_number=day.day_number,
            )
            content["verse_ref"] = day.verse_ref
            content["verse_text"] = verse_text
            content["day_title"] = day.day_title
            content["day_number"] = day.day_number
            results.append(content)

        return results
