"""Tests for core.images.phrase_reel_generator — FFmpeg drawtext escaping and filter building."""

import pytest

from core.audio.timestamps import Phrase, WordTimestamp
from core.images.phrase_reel_generator import (
    _build_audio_filters,
    _build_drawtext_filters,
    _escape_drawtext,
    _find_font_path,
)


# ── _escape_drawtext tests ──


class TestEscapeDrawtext:
    def test_plain_text(self) -> None:
        assert _escape_drawtext("Be still") == "Be still"

    def test_colon(self) -> None:
        assert _escape_drawtext("Psalms 23:1") == "Psalms 23\\:1"

    def test_apostrophe(self) -> None:
        """Apostrophes replaced with right single quotation mark."""
        result = _escape_drawtext("God's love")
        assert "'" not in result
        assert "\u2019" in result

    def test_backslash(self) -> None:
        assert _escape_drawtext("a\\b") == "a\\\\b"

    def test_percent(self) -> None:
        assert _escape_drawtext("100%") == "100%%"

    def test_semicolon(self) -> None:
        assert _escape_drawtext("faith; hope") == "faith\\; hope"

    def test_combined(self) -> None:
        """Multiple special chars in one string."""
        result = _escape_drawtext("John 3:16 — God's 100%")
        assert "\\:" in result
        assert "\u2019" in result
        assert "%%" in result


# ── _build_drawtext_filters tests ──


def _make_phrase(text: str, start: float, end: float) -> Phrase:
    """Helper to create a Phrase with minimal word data."""
    words = tuple(
        WordTimestamp(word=w, start_time=start, end_time=end)
        for w in text.split()
    )
    return Phrase(text=text, start_time=start, end_time=end, words=words)


class TestBuildDrawtextFilters:
    def test_empty_phrases(self) -> None:
        assert _build_drawtext_filters([], phrase_offset=0.5, font_path=None) == []

    def test_single_phrase(self) -> None:
        phrases = [_make_phrase("Be still", 0.5, 1.5)]
        filters = _build_drawtext_filters(phrases, phrase_offset=0.8, font_path=None)
        assert len(filters) == 1
        # Should contain drawbox, shadow drawtext, and main drawtext
        assert "drawbox" in filters[0]
        assert "drawtext" in filters[0]
        assert "Be still" in filters[0]
        # Should end with [vout] label
        assert filters[0].endswith("[vout]")

    def test_multiple_phrases(self) -> None:
        phrases = [
            _make_phrase("Be still", 0.5, 1.5),
            _make_phrase("and know", 1.6, 2.5),
            _make_phrase("that I am God", 2.6, 3.8),
        ]
        filters = _build_drawtext_filters(phrases, phrase_offset=0.8, font_path=None)
        assert len(filters) == 3
        # Last filter should end with [vout]
        assert filters[-1].endswith("[vout]")
        # Intermediate filters should have [dtN] labels
        assert "[dt0]" in filters[0]
        assert "[dt1]" in filters[1]

    def test_font_path_included(self) -> None:
        phrases = [_make_phrase("Test", 0.0, 1.0)]
        filters = _build_drawtext_filters(
            phrases, phrase_offset=0.0, font_path="C:/Windows/Fonts/georgia.ttf"
        )
        assert "fontfile=" in filters[0]

    def test_enable_between(self) -> None:
        """Each phrase should have enable='between(t,...)' for timing."""
        phrases = [_make_phrase("Hello world", 1.0, 2.0)]
        filters = _build_drawtext_filters(phrases, phrase_offset=0.5, font_path=None)
        assert "enable=" in filters[0]
        assert "between(t," in filters[0]

    def test_special_chars_escaped(self) -> None:
        """Colons in text should be escaped for FFmpeg."""
        phrases = [_make_phrase("John 3:16", 0.0, 1.0)]
        filters = _build_drawtext_filters(phrases, phrase_offset=0.0, font_path=None)
        assert "3\\:16" in filters[0]


# ── _build_audio_filters tests ──


class TestBuildAudioFilters:
    def test_no_audio(self) -> None:
        filters, audio_map = _build_audio_filters(
            has_narration=False, has_music=False, has_ambient=False,
            narr_idx=-1, music_idx=-1, ambient_idx=-1,
            narr_fade_start=10.0, music_fade_start=8.0,
        )
        assert filters == []
        assert audio_map == ""

    def test_narration_only(self) -> None:
        filters, audio_map = _build_audio_filters(
            has_narration=True, has_music=False, has_ambient=False,
            narr_idx=1, music_idx=-1, ambient_idx=-1,
            narr_fade_start=10.0, music_fade_start=8.0,
        )
        assert len(filters) == 1
        assert "[1:a]" in filters[0]
        assert audio_map == "[a]"

    def test_narration_plus_music(self) -> None:
        filters, audio_map = _build_audio_filters(
            has_narration=True, has_music=True, has_ambient=False,
            narr_idx=1, music_idx=2, ambient_idx=-1,
            narr_fade_start=10.0, music_fade_start=8.0,
        )
        # narration filter + music filter + amix
        assert len(filters) == 3
        assert "amix=inputs=2" in filters[2]
        assert audio_map == "[a]"
        # Music should be ducked to 0.08 when narration present
        assert "volume=0.08" in filters[1]

    def test_music_only_louder(self) -> None:
        """Music without narration should be at 0.20 volume."""
        filters, audio_map = _build_audio_filters(
            has_narration=False, has_music=True, has_ambient=False,
            narr_idx=-1, music_idx=1, ambient_idx=-1,
            narr_fade_start=10.0, music_fade_start=8.0,
        )
        assert "volume=0.20" in filters[0]

    def test_all_three_audio_sources(self) -> None:
        filters, audio_map = _build_audio_filters(
            has_narration=True, has_music=True, has_ambient=True,
            narr_idx=1, music_idx=2, ambient_idx=3,
            narr_fade_start=10.0, music_fade_start=8.0,
        )
        assert len(filters) == 4  # narr + music + ambient + amix
        assert "amix=inputs=3" in filters[3]
        assert audio_map == "[a]"
