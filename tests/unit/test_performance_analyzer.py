import pytest
from unittest.mock import MagicMock
from core.analytics.performance_analyzer import PerformanceAnalyzer


def _make_type_row(content_type, avg_engagement, avg_reach, avg_saves, post_count):
    row = MagicMock()
    row.content_type = content_type
    row.avg_engagement = avg_engagement
    row.avg_reach = avg_reach
    row.avg_saves = avg_saves
    row.avg_shares = 0.0
    row.avg_likes = 0.0
    row.post_count = post_count
    return row


def _make_format_row(media_format, avg_engagement, avg_reach, avg_saves, post_count):
    row = MagicMock()
    row.media_format = media_format
    row.avg_engagement = avg_engagement
    row.avg_reach = avg_reach
    row.avg_saves = avg_saves
    row.avg_shares = 0.0
    row.post_count = post_count
    return row


def _make_time_row(hour, avg_engagement, avg_reach, post_count):
    row = MagicMock()
    row.hour = hour
    row.avg_engagement = avg_engagement
    row.avg_reach = avg_reach
    row.post_count = post_count
    return row


class TestRecommendationRules:

    def test_top_content_type_recommendation(self):
        analyzer = PerformanceAnalyzer.__new__(PerformanceAnalyzer)
        # avg engagement = (0.12 + 0.02 + 0.03) / 3 = 0.0567
        # OUTPERFORM_RATIO = 2.0, so threshold = 0.1133
        # faith_friday at 0.12 >= 0.1133 -> triggers "Double down"
        type_data = [
            _make_type_row("faith_friday", 0.12, 50.0, 2.0, 4),
            _make_type_row("daily_verse", 0.02, 100.0, 0.5, 10),
            _make_type_row("encouragement", 0.03, 60.0, 1.0, 5),
        ]
        recs = analyzer._content_type_recommendations(type_data)
        assert len(recs) >= 1
        assert any("faith friday" in r["title"].lower() or "faith friday" in r["why"].lower() for r in recs)

    def test_underperformer_recommendation(self):
        analyzer = PerformanceAnalyzer.__new__(PerformanceAnalyzer)
        # avg engagement = (0.08 + 0.01 + 0.06) / 3 = 0.05
        # UNDERPERFORM_RATIO = 0.5, so threshold = 0.025
        # daily_verse at 0.01 <= 0.025 and count=10 >= 3 -> triggers "Rethink"
        type_data = [
            _make_type_row("faith_friday", 0.08, 50.0, 2.0, 4),
            _make_type_row("daily_verse", 0.01, 30.0, 0.0, 10),
            _make_type_row("encouragement", 0.06, 60.0, 1.0, 5),
        ]
        recs = analyzer._content_type_recommendations(type_data)
        assert any("daily verse" in r["why"].lower() for r in recs)

    def test_format_recommendation(self):
        analyzer = PerformanceAnalyzer.__new__(PerformanceAnalyzer)
        # avg reach = (600 + 50) / 2 = 325
        # OUTPERFORM_RATIO = 2.0, so threshold = 650
        # reel at 600 < 650... need bigger gap
        # avg reach = (800 + 50) / 2 = 425, threshold = 850
        # Use extreme values: avg = (900+100)/2=500, threshold=1000
        # reel at 900 < 1000... The formula checks reach >= avg*2
        # With only 2 items: avg = (X + Y)/2, need X >= (X+Y)/2 * 2 = X+Y
        # So X >= X+Y means Y <= 0. Need 3+ items or small Y.
        # Use 3 formats: avg = (500+50+50)/3=200, threshold=400, reel at 500 >= 400
        format_data = [
            _make_format_row("reel", 0.05, 500.0, 3.0, 5),
            _make_format_row("image", 0.03, 50.0, 1.0, 8),
            _make_format_row("carousel", 0.04, 50.0, 2.0, 3),
        ]
        recs = analyzer._format_recommendations(format_data)
        assert len(recs) >= 1

    def test_time_slot_recommendation(self):
        analyzer = PerformanceAnalyzer.__new__(PerformanceAnalyzer)
        time_data = [
            _make_time_row(6, 0.06, 120.0, 10),
            _make_time_row(12, 0.03, 60.0, 10),
        ]
        recs = analyzer._time_recommendations(time_data)
        assert len(recs) >= 1
        assert any("morning" in r["title"].lower() or "6" in r["why"] for r in recs)

    def test_no_recommendation_when_similar(self):
        analyzer = PerformanceAnalyzer.__new__(PerformanceAnalyzer)
        time_data = [
            _make_time_row(6, 0.05, 100.0, 10),
            _make_time_row(12, 0.045, 95.0, 10),
        ]
        recs = analyzer._time_recommendations(time_data)
        assert len(recs) == 0

    def test_competitor_format_shift_recommendation(self):
        analyzer = PerformanceAnalyzer.__new__(PerformanceAnalyzer)
        current = {"biblesociety": {"VIDEO": 60.0, "IMAGE": 20.0, "CAROUSEL_ALBUM": 20.0}}
        previous = {"biblesociety": {"VIDEO": 30.0, "IMAGE": 50.0, "CAROUSEL_ALBUM": 20.0}}
        recs = analyzer._competitor_recommendations(current, previous)
        assert len(recs) >= 1
        assert any("biblesociety" in r["why"].lower() or "video" in r["why"].lower() for r in recs)

    def test_recommendation_confidence(self):
        analyzer = PerformanceAnalyzer.__new__(PerformanceAnalyzer)
        assert analyzer._confidence(15) == "high"
        assert analyzer._confidence(7) == "medium"
        assert analyzer._confidence(3) == "low"

    def test_minimum_data_threshold(self):
        analyzer = PerformanceAnalyzer.__new__(PerformanceAnalyzer)
        type_data = [
            _make_type_row("daily_verse", 0.08, 100.0, 2.0, 2),
        ]
        recs = analyzer._content_type_recommendations(type_data)
        assert len(recs) == 0
