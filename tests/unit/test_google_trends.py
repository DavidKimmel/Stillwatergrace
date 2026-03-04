"""Tests for Google Trends scraper."""

import pytest

from core.scraper.google_trends import GoogleTrendsClient, KEYWORD_GROUPS


class TestGoogleTrends:
    """Tests for GoogleTrendsClient."""

    def test_keyword_groups_not_empty(self):
        assert len(KEYWORD_GROUPS) >= 5

    def test_keyword_groups_have_five_keywords(self):
        for group in KEYWORD_GROUPS:
            assert len(group) == 5, f"Group should have 5 keywords: {group}"

    def test_relevance_filter_allows_faith_topics(self):
        assert GoogleTrendsClient._is_relevant("christian marriage advice") is True
        assert GoogleTrendsClient._is_relevant("bible verse for hope") is True
        assert GoogleTrendsClient._is_relevant("prayer for family") is True
        assert GoogleTrendsClient._is_relevant("parenting with god's grace") is True

    def test_relevance_filter_blocks_political(self):
        assert GoogleTrendsClient._is_relevant("trump christian values") is False
        assert GoogleTrendsClient._is_relevant("biden church policy") is False
        assert GoogleTrendsClient._is_relevant("election and faith") is False

    def test_relevance_filter_blocks_controversial(self):
        assert GoogleTrendsClient._is_relevant("abortion debate church") is False
        assert GoogleTrendsClient._is_relevant("gun rights christian") is False
        assert GoogleTrendsClient._is_relevant("vaccine conspiracy church") is False

    def test_relevance_filter_blocks_irrelevant(self):
        assert GoogleTrendsClient._is_relevant("best pizza near me") is False
        assert GoogleTrendsClient._is_relevant("stock market today") is False

    def test_no_duplicate_keywords_across_groups(self):
        all_keywords = []
        for group in KEYWORD_GROUPS:
            all_keywords.extend(group)
        assert len(all_keywords) == len(set(all_keywords)), "Duplicate keywords found"
