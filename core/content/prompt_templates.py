"""Prompt template engine using Jinja2.

Loads and renders all prompt templates for content generation.
Handles variable injection and template versioning.
"""

import logging
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
TEMPLATE_VERSION = "1.0"


class PromptTemplateEngine:
    """Manages loading and rendering of all prompt templates."""

    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.version = TEMPLATE_VERSION

    def render(self, template_name: str, **kwargs: Any) -> str:
        """Render a prompt template with the given variables.

        Args:
            template_name: Template filename without extension (e.g., 'daily_verse')
            **kwargs: Template variables to inject

        Returns:
            Rendered prompt string
        """
        try:
            template = self.env.get_template(f"{template_name}.jinja2")
        except TemplateNotFound:
            raise ValueError(f"Prompt template '{template_name}' not found in {self.prompts_dir}")

        rendered = template.render(**kwargs)
        return rendered.strip()

    def get_system_prompt(self) -> str:
        """Get the system prompt for Claude API calls."""
        return self.render("system_prompt")

    def render_daily_verse(
        self,
        verse_text: str,
        verse_reference: str,
        content_type: str = "encouragement",
        trending_topic: str = "",
    ) -> str:
        """Render the daily verse generation prompt."""
        return self.render(
            "daily_verse",
            verse_text=verse_text,
            verse_reference=verse_reference,
            content_type=content_type,
            trending_topic=trending_topic,
        )

    def render_marriage_monday(
        self,
        weekly_marriage_theme: str,
        trending_topic: str = "",
    ) -> str:
        """Render the Marriage Monday generation prompt."""
        return self.render(
            "marriage_monday",
            weekly_marriage_theme=weekly_marriage_theme,
            trending_topic=trending_topic,
        )

    def render_parenting_wednesday(
        self,
        age_group: str,
        parenting_theme: str,
        trending_topic: str = "",
    ) -> str:
        """Render the Parenting Wednesday generation prompt."""
        return self.render(
            "parenting_wednesday",
            age_group=age_group,
            parenting_theme=parenting_theme,
            trending_topic=trending_topic,
        )

    def render_faith_friday(
        self,
        hardship_topic: str,
        trending_topic: str = "",
    ) -> str:
        """Render the Faith & Hardship Friday generation prompt."""
        return self.render(
            "faith_friday",
            hardship_topic=hardship_topic,
            trending_topic=trending_topic,
        )

    def render_viral_formats(self, trending_topic: str = "") -> str:
        """Render the viral formats generation prompt."""
        return self.render(
            "viral_formats",
            trending_topic=trending_topic,
        )

    def render_devotional_book(self) -> str:
        """Render the 30-day devotional generation prompt."""
        return self.render("devotional_book")

    def render_image_prompt(
        self,
        content_type: str,
        emotional_tone: str,
        hook: str,
        verse_reference: str = "",
    ) -> str:
        """Render the image prompt guidelines for Leonardo.ai."""
        return self.render(
            "image_prompt_guidelines",
            content_type=content_type,
            emotional_tone=emotional_tone,
            hook=hook,
            verse_reference=verse_reference,
        )


# Module-level singleton for convenience
_engine: Optional[PromptTemplateEngine] = None


def get_template_engine() -> PromptTemplateEngine:
    """Get or create the global template engine instance."""
    global _engine
    if _engine is None:
        _engine = PromptTemplateEngine()
    return _engine
