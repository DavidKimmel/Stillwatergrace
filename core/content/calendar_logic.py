"""Content calendar logic — scheduling, variety, and rotation rules.

Manages the weekly content calendar ensuring proper variety of content types,
emotional tones, and posting times.
"""

import logging
from datetime import datetime, timedelta, time
from typing import Optional

from sqlalchemy.orm import Session

from database.models import (
    ContentCalendarSlot,
    ContentType,
    EmotionalTone,
    GeneratedContent,
)
from core.content.series_manager import SeriesManager

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Weekly Schedule Template
# ──────────────────────────────────────────────

# Day of week (0=Monday) → content type mapping
# 12 slots/week: morning + noon only. Reels and carousels determined by content type.
# Reels auto-generate for any verse-backed content via FFmpeg pipeline.
WEEKLY_SCHEDULE = {
    0: {  # Monday
        "morning": {"type": ContentType.marriage_monday, "tone": EmotionalTone.hopeful},
        "noon": {"type": ContentType.encouragement, "tone": EmotionalTone.hopeful},
    },
    1: {  # Tuesday
        "morning": {"type": ContentType.daily_verse, "tone": EmotionalTone.reflective},
        "noon": {"type": ContentType.this_or_that, "tone": EmotionalTone.celebratory},
    },
    2: {  # Wednesday
        "morning": {"type": ContentType.parenting_wednesday, "tone": EmotionalTone.hopeful},
        "noon": {"type": ContentType.daily_verse, "tone": EmotionalTone.reflective},
    },
    3: {  # Thursday
        "morning": {"type": ContentType.fill_in_blank, "tone": EmotionalTone.celebratory},
        "noon": {"type": ContentType.encouragement, "tone": EmotionalTone.hopeful},
    },
    4: {  # Friday
        "morning": {"type": ContentType.faith_friday, "tone": EmotionalTone.reflective},
        "noon": {"type": ContentType.daily_verse, "tone": EmotionalTone.hopeful},
    },
    5: {  # Saturday
        "morning": {"type": ContentType.carousel, "tone": EmotionalTone.hopeful},
        "noon": {"type": ContentType.conviction_quote, "tone": EmotionalTone.challenging},
    },
    6: {  # Sunday
        "morning": {"type": ContentType.gratitude, "tone": EmotionalTone.celebratory},
        "noon": {"type": ContentType.prayer_prompt, "tone": EmotionalTone.reflective},
    },
}

# Posting times (EST)
POSTING_TIMES = {
    "morning": time(6, 30),
    "noon": time(12, 0),
}

# Posts per day ramp — increase over time
# Week 1-2: 1/day, Week 3-4: 2/day, Week 5+: 3/day
POSTS_PER_DAY_BY_WEEK = {
    1: 1, 2: 1,
    3: 2, 4: 2,
    5: 3, 6: 3,
}


class ContentCalendar:
    """Manages content scheduling and calendar slot generation."""

    def __init__(self, db: Session):
        self.db = db
        self.series = SeriesManager(db)

    def get_todays_slots(self) -> list[dict]:
        """Get content generation slots for today.

        Returns a list of slot dicts with content_type, time_slot, theme, etc.
        """
        today = datetime.utcnow()
        day_of_week = today.weekday()
        day_schedule = WEEKLY_SCHEDULE.get(day_of_week, {})

        slots = []
        for time_slot, config in day_schedule.items():
            if config is None:
                continue

            # Calculate scheduled_at from today's date + posting time
            posting_time = POSTING_TIMES[time_slot]
            scheduled_at = today.replace(
                hour=posting_time.hour,
                minute=posting_time.minute,
                second=0,
                microsecond=0,
            )

            slot = {
                "date": today.date().isoformat(),
                "time_slot": time_slot,
                "content_type": config["type"].value,
                "emotional_tone": config["tone"].value,
                "scheduled_at": scheduled_at,
                "theme": "",
                "age_group": "general",
            }

            # Add theme based on content type
            content_type = config["type"]
            if content_type == ContentType.marriage_monday:
                slot["theme"] = self.series.get_marriage_theme()

            elif content_type == ContentType.parenting_wednesday:
                age_group, theme = self.series.get_parenting_theme()
                slot["theme"] = theme
                slot["age_group"] = age_group

            elif content_type == ContentType.faith_friday:
                slot["theme"] = self.series.get_hardship_topic()

            elif content_type in {
                ContentType.fill_in_blank,
                ContentType.this_or_that,
                ContentType.conviction_quote,
                ContentType.parenting_list,
                ContentType.marriage_challenge,
            }:
                # Override with this week's viral format
                viral_format = self.series.get_viral_format()
                slot["content_type"] = viral_format

            slots.append(slot)

        logger.info(f"Generated {len(slots)} slots for {today.date()} (day {day_of_week})")
        return slots

    def generate_week_calendar(self, start_date: Optional[datetime] = None) -> list[dict]:
        """Generate a full 7-day calendar lookahead.

        Used by the dashboard to show upcoming content plan.
        """
        if not start_date:
            start_date = datetime.utcnow()
            # Align to start of current week (Monday)
            start_date -= timedelta(days=start_date.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        week = []
        for day_offset in range(7):
            day = start_date + timedelta(days=day_offset)
            day_of_week = day.weekday()
            day_schedule = WEEKLY_SCHEDULE.get(day_of_week, {})

            for time_slot, config in day_schedule.items():
                if config is None:
                    continue

                posting_time = POSTING_TIMES[time_slot]
                scheduled_at = day.replace(
                    hour=posting_time.hour,
                    minute=posting_time.minute,
                    second=0,
                    microsecond=0,
                )

                week.append({
                    "date": day.date().isoformat(),
                    "day_name": day.strftime("%A"),
                    "time_slot": time_slot,
                    "scheduled_at": scheduled_at.isoformat(),
                    "content_type": config["type"].value,
                    "emotional_tone": config["tone"].value,
                })

        return week

    def create_calendar_slots(self, start_date: Optional[datetime] = None) -> int:
        """Create calendar slot records in the database for the upcoming week.

        Returns the number of slots created.
        """
        week = self.generate_week_calendar(start_date)
        created = 0

        for slot_data in week:
            # Check if slot already exists
            scheduled_at = datetime.fromisoformat(slot_data["scheduled_at"])
            existing = (
                self.db.query(ContentCalendarSlot)
                .filter(
                    ContentCalendarSlot.date == scheduled_at,
                    ContentCalendarSlot.time_slot == slot_data["time_slot"],
                )
                .first()
            )

            if existing:
                continue

            slot = ContentCalendarSlot(
                date=scheduled_at,
                time_slot=slot_data["time_slot"],
                content_type=ContentType(slot_data["content_type"]),
                emotional_tone=EmotionalTone(slot_data["emotional_tone"]),
                filled=False,
            )
            self.db.add(slot)
            created += 1

        self.db.flush()
        logger.info(f"Created {created} calendar slots")
        return created
