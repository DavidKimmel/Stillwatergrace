"""Tests for the series manager theme rotation."""

import pytest
from unittest.mock import MagicMock

from core.content.series_manager import (
    SeriesManager,
    MARRIAGE_THEMES,
    PARENTING_THEMES,
    PARENTING_AGE_ROTATION,
    HARDSHIP_TOPICS,
    VIRAL_FORMAT_ROTATION,
)


class TestSeriesManager:
    """Tests for SeriesManager."""

    def test_marriage_themes_not_empty(self):
        assert len(MARRIAGE_THEMES) >= 10

    def test_parenting_themes_cover_all_ages(self):
        for age in PARENTING_AGE_ROTATION:
            assert age in PARENTING_THEMES
            assert len(PARENTING_THEMES[age]) >= 5

    def test_hardship_topics_not_empty(self):
        assert len(HARDSHIP_TOPICS) >= 8

    def test_viral_formats_not_empty(self):
        assert len(VIRAL_FORMAT_ROTATION) == 5

    def test_no_duplicate_marriage_themes(self):
        assert len(MARRIAGE_THEMES) == len(set(MARRIAGE_THEMES))

    def test_no_duplicate_hardship_topics(self):
        assert len(HARDSHIP_TOPICS) == len(set(HARDSHIP_TOPICS))

    def test_get_marriage_theme_returns_string(self):
        db = MagicMock()
        # Mock: no recent themes used
        db.query.return_value.filter.return_value.all.return_value = []

        manager = SeriesManager(db)
        theme = manager.get_marriage_theme()

        assert isinstance(theme, str)
        assert theme in MARRIAGE_THEMES

    def test_get_parenting_theme_returns_tuple(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        manager = SeriesManager(db)
        result = manager.get_parenting_theme()

        assert isinstance(result, tuple)
        assert len(result) == 2
        age_group, theme = result
        assert age_group in PARENTING_AGE_ROTATION

    def test_get_hardship_topic_returns_string(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        manager = SeriesManager(db)
        topic = manager.get_hardship_topic()

        assert isinstance(topic, str)
        assert topic in HARDSHIP_TOPICS
