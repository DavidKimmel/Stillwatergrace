"""Management CLI for StillWaterGrace platform.

Usage:
    python manage.py init-db          Create all database tables
    python manage.py seed             Seed hashtags and brand prospects
    python manage.py generate-verse   Test: fetch a daily Bible verse
    python manage.py generate-content Test: generate content for today
    python manage.py show-calendar    Show this week's content calendar
    python manage.py test-leonardo    Test Leonardo.ai API connection
    python manage.py weekly-report    Generate weekly report
    python manage.py rate-card        Show sponsorship rate card
"""

import sys
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("manage")


def init_db():
    """Create all database tables."""
    from database.models import Base
    from database.session import engine

    logger.info("Creating all database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Done. All tables created.")


def seed():
    """Seed initial data (hashtags, brand prospects)."""
    from database.session import get_db
    from core.scraper.hashtag_research import HashtagResearcher
    from monetization.brand_crm import BrandCRM

    with get_db() as db:
        hr = HashtagResearcher(db)
        hashtag_count = hr.seed_hashtags()
        logger.info(f"Seeded {hashtag_count} hashtags")

        crm = BrandCRM(db)
        brand_count = crm.seed_prospects()
        logger.info(f"Seeded {brand_count} brand prospects")


def generate_verse():
    """Test: fetch and display a daily Bible verse."""
    from database.session import get_db
    from core.scraper.bible_api import BibleAPIClient

    with get_db() as db:
        client = BibleAPIClient(db)
        verse = client.fetch_daily_verse()
        if verse:
            print(f"\n{verse.reference}")
            print(f"{verse.text}")
            print(f"(Book: {verse.book}, Chapter: {verse.chapter})")
        else:
            print("Failed to fetch verse")


def generate_content():
    """Test: generate content for today's calendar slots."""
    from database.session import get_db
    from core.content.generator import ContentGenerator

    with get_db() as db:
        gen = ContentGenerator(db)
        count = gen.generate_daily_content()
        print(f"\nGenerated {count} content pieces")


def show_calendar():
    """Show this week's content calendar."""
    from database.session import get_db
    from core.content.calendar_logic import ContentCalendar

    with get_db() as db:
        cal = ContentCalendar(db)
        week = cal.generate_week_calendar()

        print("\n== This Week's Content Calendar ==\n")
        current_day = ""
        for slot in week:
            day = slot["day_name"]
            if day != current_day:
                print(f"\n  {day} ({slot['date']})")
                print(f"  {'─' * 40}")
                current_day = day

            print(f"    {slot['time_slot']:8s} | {slot['content_type']:25s} | {slot['emotional_tone']}")


def test_leonardo():
    """Test Leonardo.ai API connection."""
    from core.images.leonardo_client import LeonardoClient

    try:
        client = LeonardoClient()
        info = client.get_user_info()
        if info:
            print(f"\nLeonardo.ai connected successfully")
            print(json.dumps(info, indent=2))
        else:
            print("Failed to connect")
    except ValueError as e:
        print(f"Error: {e}")


def weekly_report():
    """Generate and save weekly report."""
    from database.session import get_db
    from core.analytics.report_generator import ReportGenerator

    with get_db() as db:
        report = ReportGenerator(db)
        report.generate_and_send()
        print("Report generated")


def rate_card():
    """Show sponsorship rate card for various follower counts."""
    from monetization.brand_crm import BrandCRM

    print("\n== Sponsorship Rate Card ==\n")

    milestones = [
        (5000, 0.05),
        (10000, 0.04),
        (25000, 0.035),
        (40000, 0.03),
        (50000, 0.03),
    ]

    for followers, engagement in milestones:
        rates = BrandCRM.calculate_rate_card(followers, engagement)
        print(f"  {followers:,} followers ({engagement*100:.1f}% engagement):")
        for rate_type, amount in rates["rates"].items():
            print(f"    {rate_type:30s} ${amount}")
        print()


COMMANDS = {
    "init-db": init_db,
    "seed": seed,
    "generate-verse": generate_verse,
    "generate-content": generate_content,
    "show-calendar": show_calendar,
    "test-leonardo": test_leonardo,
    "weekly-report": weekly_report,
    "rate-card": rate_card,
}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    COMMANDS[command]()
