"""Tests for competitor tracker."""

import pytest

from core.scraper.competitor_tracker import CompetitorTracker, COMPETITOR_HANDLES, _parse_count


class TestCompetitorTracker:
    """Tests for CompetitorTracker."""

    def test_competitor_handles_defined(self):
        assert len(COMPETITOR_HANDLES) >= 5

    def test_parse_count_simple(self):
        assert _parse_count("1234") == 1234

    def test_parse_count_with_commas(self):
        assert _parse_count("1,234,567") == 1234567

    def test_parse_count_k_suffix(self):
        assert _parse_count("123K") == 123000
        assert _parse_count("1.5K") == 1500
        assert _parse_count("45.2k") == 45200

    def test_parse_count_m_suffix(self):
        assert _parse_count("1.5M") == 1500000
        assert _parse_count("2M") == 2000000
        assert _parse_count("0.5m") == 500000

    def test_parse_count_none(self):
        assert _parse_count(None) is None
        assert _parse_count("") is None

    def test_parse_count_invalid(self):
        assert _parse_count("abc") is None
