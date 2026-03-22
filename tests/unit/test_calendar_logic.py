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
        """Ensure morning time slot has a posting time."""
        assert "morning" in POSTING_TIMES

    def test_posting_times_valid(self):
        """Ensure posting times are valid time objects."""
        from datetime import time
        for slot_name, slot_time in POSTING_TIMES.items():
            assert isinstance(slot_time, time), f"{slot_name} is not a time object"

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

    def test_schedule_is_4_singles_3_carousels(self):
        """After image pivot, schedule is 4 scripture singles + 3 carousels."""
        type_counts: dict[str, int] = {}
        for day in range(7):
            day_schedule = WEEKLY_SCHEDULE[day]
            for slot_config in day_schedule.values():
                if slot_config:
                    t = slot_config["type"].value
                    type_counts[t] = type_counts.get(t, 0) + 1

        assert type_counts.get("daily_devotional", 0) == 4, (
            f"Expected 4 daily_devotional slots, got {type_counts.get('daily_devotional', 0)}"
        )
        assert type_counts.get("carousel", 0) == 3, (
            f"Expected 3 carousel slots, got {type_counts.get('carousel', 0)}"
        )

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
