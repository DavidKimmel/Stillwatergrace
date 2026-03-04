"""Tests for the prompt template engine."""

import pytest
from pathlib import Path

from core.content.prompt_templates import PromptTemplateEngine


class TestPromptTemplateEngine:
    """Tests for PromptTemplateEngine."""

    def setup_method(self):
        self.engine = PromptTemplateEngine()

    def test_system_prompt_loads(self):
        prompt = self.engine.get_system_prompt()
        assert len(prompt) > 100
        assert "Christian" in prompt
        assert "Instagram" in prompt

    def test_daily_verse_renders(self):
        prompt = self.engine.render_daily_verse(
            verse_text="For God so loved the world...",
            verse_reference="John 3:16",
            content_type="encouragement",
            trending_topic="faith in hard times",
        )
        assert "John 3:16" in prompt
        assert "For God so loved" in prompt
        assert "encouragement" in prompt
        assert "faith in hard times" in prompt

    def test_daily_verse_without_trending(self):
        prompt = self.engine.render_daily_verse(
            verse_text="The Lord is my shepherd.",
            verse_reference="Psalm 23:1",
        )
        assert "Psalm 23:1" in prompt
        # Should not have empty trending section
        assert "Trending topic context:" not in prompt or "Trending topic context: \n" not in prompt

    def test_marriage_monday_renders(self):
        prompt = self.engine.render_marriage_monday(
            weekly_marriage_theme="communication",
        )
        assert "communication" in prompt
        assert "Marriage Monday" in prompt

    def test_parenting_wednesday_renders(self):
        prompt = self.engine.render_parenting_wednesday(
            age_group="toddlers",
            parenting_theme="patience in the chaos",
        )
        assert "toddlers" in prompt
        assert "patience" in prompt

    def test_faith_friday_renders(self):
        prompt = self.engine.render_faith_friday(
            hardship_topic="grief and loss",
        )
        assert "grief" in prompt
        assert "honest" in prompt.lower() or "pain" in prompt.lower()

    def test_viral_formats_renders(self):
        prompt = self.engine.render_viral_formats()
        assert "FILL_IN_THE_BLANK" in prompt
        assert "THIS_OR_THAT" in prompt
        assert "CONVICTION_QUOTE" in prompt

    def test_devotional_book_renders(self):
        prompt = self.engine.render_devotional_book()
        assert "30-Day" in prompt or "30 days" in prompt.lower()
        assert "Week 1" in prompt

    def test_all_templates_exist(self):
        """Verify all expected template files are present."""
        expected = [
            "system_prompt",
            "daily_verse",
            "marriage_monday",
            "parenting_wednesday",
            "faith_friday",
            "viral_formats",
            "devotional_book",
            "image_prompt_guidelines",
        ]
        for name in expected:
            # Should not raise
            prompt = self.engine.render(name, **self._get_test_vars(name))
            assert len(prompt) > 50, f"Template {name} rendered too short"

    def _get_test_vars(self, template_name):
        """Get test variables for each template."""
        if template_name == "system_prompt":
            return {}
        elif template_name == "daily_verse":
            return {"verse_text": "Test verse", "verse_reference": "Test 1:1", "content_type": "test"}
        elif template_name == "marriage_monday":
            return {"weekly_marriage_theme": "test"}
        elif template_name == "parenting_wednesday":
            return {"age_group": "general", "parenting_theme": "test"}
        elif template_name == "faith_friday":
            return {"hardship_topic": "test"}
        elif template_name == "viral_formats":
            return {}
        elif template_name == "devotional_book":
            return {}
        elif template_name == "image_prompt_guidelines":
            return {"content_type": "test", "emotional_tone": "hopeful", "hook": "Test hook"}
        return {}
