"""Tests for hashtag research module."""

import pytest
from unittest.mock import MagicMock

from core.scraper.hashtag_research import (
    HashtagResearcher,
    HASHTAGS_LARGE,
    HASHTAGS_MEDIUM,
    HASHTAGS_NICHE,
)


class TestHashtags:
    """Tests for hashtag data integrity."""

    def test_large_hashtags_count(self):
        assert len(HASHTAGS_LARGE) == 30

    def test_medium_hashtags_count(self):
        assert len(HASHTAGS_MEDIUM) == 30

    def test_niche_hashtags_count(self):
        assert len(HASHTAGS_NICHE) == 30

    def test_all_hashtags_start_with_hash(self):
        all_tags = HASHTAGS_LARGE + HASHTAGS_MEDIUM + HASHTAGS_NICHE
        for tag in all_tags:
            assert tag.startswith("#"), f"Hashtag missing #: {tag}"

    def test_no_duplicate_hashtags_within_tier(self):
        assert len(HASHTAGS_LARGE) == len(set(HASHTAGS_LARGE))
        assert len(HASHTAGS_MEDIUM) == len(set(HASHTAGS_MEDIUM))
        assert len(HASHTAGS_NICHE) == len(set(HASHTAGS_NICHE))

    def test_no_spaces_in_hashtags(self):
        all_tags = HASHTAGS_LARGE + HASHTAGS_MEDIUM + HASHTAGS_NICHE
        for tag in all_tags:
            assert " " not in tag, f"Space in hashtag: {tag}"

    def test_all_hashtags_lowercase(self):
        """Hashtags should be lowercase for consistency."""
        all_tags = HASHTAGS_LARGE + HASHTAGS_MEDIUM + HASHTAGS_NICHE
        for tag in all_tags:
            assert tag == tag.lower(), f"Non-lowercase hashtag: {tag}"


class TestHashtagResearcher:
    """Tests for HashtagResearcher."""

    def test_get_hashtag_set_returns_three_tiers(self):
        db = MagicMock()
        # Mock DB to return hashtag objects
        mock_tags = [MagicMock(hashtag=f"#test{i}") for i in range(10)]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_tags

        researcher = HashtagResearcher(db)
        result = researcher.get_hashtag_set()

        assert "large" in result
        assert "medium" in result
        assert "niche" in result

    def test_seed_hashtags_idempotent(self):
        db = MagicMock()
        # First call: nothing exists
        db.query.return_value.filter.return_value.first.return_value = None

        researcher = HashtagResearcher(db)
        count = researcher.seed_hashtags()

        assert count == 90  # 30 per tier
        assert db.add.call_count == 90
