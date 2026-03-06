"""Celery application configuration with Beat schedule."""

from celery import Celery
from celery.schedules import crontab

from core.config import settings

app = Celery(
    "stillwatergrace",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "workers.daily_tasks",
        "workers.posting_tasks",
    ],
)

app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="America/New_York",
    enable_utc=True,

    # Task settings
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,

    # Result expiry (7 days)
    result_expires=604800,

    # Beat schedule — all times in EST
    beat_schedule={
        # ── Daily Content Pipeline (6:00 AM) ──
        "daily-trend-discovery": {
            "task": "workers.daily_tasks.run_trend_discovery",
            "schedule": crontab(hour=6, minute=0),
        },
        "daily-content-generation": {
            "task": "workers.daily_tasks.run_content_generation",
            "schedule": crontab(hour=6, minute=30),
        },
        "daily-image-generation": {
            "task": "workers.daily_tasks.run_image_generation",
            "schedule": crontab(hour=7, minute=0),
        },

        # ── Posting Windows ──
        "morning-post": {
            "task": "workers.posting_tasks.post_scheduled_content",
            "schedule": crontab(hour=6, minute=30),
            "args": ("morning",),
        },
        "noon-post": {
            "task": "workers.posting_tasks.post_scheduled_content",
            "schedule": crontab(hour=12, minute=0),
            "args": ("noon",),
        },
        "evening-post": {
            "task": "workers.posting_tasks.post_scheduled_content",
            "schedule": crontab(hour=19, minute=30),
            "args": ("evening",),
        },

        # ── Catch-up (posts missed while offline) ──
        "catchup-missed-posts": {
            "task": "workers.posting_tasks.post_missed_content",
            "schedule": crontab(minute="*/30"),
        },

        # ── Analytics Collection ──
        "analytics-1hr": {
            "task": "workers.daily_tasks.collect_analytics",
            "schedule": crontab(minute=0),  # Every hour, checks for 1hr-old posts
            "args": (1,),
        },
        "analytics-24hr": {
            "task": "workers.daily_tasks.collect_analytics",
            "schedule": crontab(hour=8, minute=0),
            "args": (24,),
        },
        "analytics-7day": {
            "task": "workers.daily_tasks.collect_analytics",
            "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
            "args": (168,),
        },

        # ── Weekly Tasks ──
        "weekly-competitor-scrape": {
            "task": "workers.daily_tasks.run_competitor_scrape",
            "schedule": crontab(hour=5, minute=0, day_of_week="sunday"),
        },
        "weekly-report": {
            "task": "workers.daily_tasks.generate_weekly_report",
            "schedule": crontab(hour=7, minute=0, day_of_week="monday"),
        },

        # ── Token Maintenance ──
        "weekly-instagram-token-refresh": {
            "task": "workers.daily_tasks.refresh_instagram_token_task",
            "schedule": crontab(hour=3, minute=0, day_of_week="wednesday"),
        },
    },
)
