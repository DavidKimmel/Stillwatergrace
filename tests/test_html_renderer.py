"""Tests for the Playwright HTML-to-image renderer."""
import pytest
from pathlib import Path

from core.rendering.html_renderer import (
    apply_highlights,
    TEMPLATES_DIR,
)


class TestApplyHighlights:
    def test_wraps_matching_phrase(self) -> None:
        text = "Be still, and know that I am God."
        highlights = ["I am God"]
        result = apply_highlights(text, highlights)
        assert '<span class="highlight">I am God</span>' in result

    def test_multiple_highlights(self) -> None:
        text = "His divine power has given us everything we need for a godly life."
        highlights = ["divine power", "a godly life"]
        result = apply_highlights(text, highlights)
        assert '<span class="highlight">divine power</span>' in result
        assert '<span class="highlight">a godly life</span>' in result

    def test_no_highlights_returns_original(self) -> None:
        text = "Be still."
        result = apply_highlights(text, [])
        assert result == "Be still."

    def test_unmatched_highlight_ignored(self) -> None:
        text = "Be still."
        result = apply_highlights(text, ["not found"])
        assert result == "Be still."

    def test_templates_dir_exists(self) -> None:
        assert TEMPLATES_DIR.exists()
        assert (TEMPLATES_DIR / "scripture_single.html").exists()
