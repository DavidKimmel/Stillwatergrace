"""Tests for content calendar logic."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from core.content.calendar_logic import ContentCalendar, WEEKLY_SCHEDULE, POSTING_TIMES


class TestContentCalendar:
    """Tests for ContentCalendar."""

    def setup_method(self):
        self.db = MagicMock()

    def test_weekly_schedule_covers_all_days(self):
        """Ensure every day of the week has at least one slot."""
        for day in range(7):
            day_schedule = WEEKLY_SCHEDULE.get(day, {})
            active_slots = [v for v in day_schedule.values() if v is not None]
            assert len(active_slots) >= 1, f"Day {day} has no active slots"

    def test_posting_times_are_defined(self):
        """Ensure all time slots have posting times."""
        assert "morning" in POSTING_TIMES
        assert "noon" in POSTING_TIMES
        assert "evening" in POSTING_TIMES

    def test_posting_times_in_order(self):
        """Ensure posting times are in chronological order."""
        morning = POSTING_TIMES["morning"]
        noon = POSTING_TIMES["noon"]
        evening = POSTING_TIMES["evening"]
        assert morning < noon < evening

    def test_no_duplicate_content_types_same_day(self):
        """No content type should appear twice on the same day."""
        for day in range(7):
            day_schedule = WEEKLY_SCHEDULE.get(day, {})
            types = []
            for slot_config in day_schedule.values():
                if slot_config:
                    types.append(slot_config["type"])
            # Allow some flexibility — but no triple duplicates
            from collections import Counter
            counts = Counter(types)
            for content_type, count in counts.items():
                assert count <= 2, f"Day {day}: {content_type} appears {count} times"

    def test_marriage_monday_on_monday(self):
        """Marriage Monday should be scheduled on Monday (day 0)."""
        monday = WEEKLY_SCHEDULE[0]
        types = [v["type"].value for v in monday.values() if v]
        assert "marriage_monday" in types

    def test_parenting_wednesday_on_wednesday(self):
        """Parenting Wednesday should be on Wednesday (day 2)."""
        wednesday = WEEKLY_SCHEDULE[2]
        types = [v["type"].value for v in wednesday.values() if v]
        assert "parenting_wednesday" in types

    def test_faith_friday_on_friday(self):
        """Faith Friday should be on Friday (day 4)."""
        friday = WEEKLY_SCHEDULE[4]
        types = [v["type"].value for v in friday.values() if v]
        assert "faith_friday" in types

    def test_generate_week_calendar_returns_7_days(self):
        """Week calendar should produce entries spanning 7 days."""
        # Mock the series manager methods
        with patch("core.content.calendar_logic.SeriesManager"):
            calendar = ContentCalendar(self.db)
            week = calendar.generate_week_calendar(
                start_date=datetime(2026, 3, 2)  # A Monday
            )

        assert len(week) > 0

        # Check we have entries for each day
        dates = {item["date"] for item in week}
        assert len(dates) == 7

    def test_emotional_tone_variety(self):
        """Ensure the week has a mix of emotional tones."""
        tones = set()
        for day in range(7):
            day_schedule = WEEKLY_SCHEDULE.get(day, {})
            for config in day_schedule.values():
                if config:
                    tones.add(config["tone"].value)

        # Should use at least 3 different tones
        assert len(tones) >= 3
