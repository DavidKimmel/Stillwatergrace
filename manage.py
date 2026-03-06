"""Management CLI for StillWaterGrace platform.

Usage:
    python manage.py init-db          Create all database tables
    python manage.py seed             Seed hashtags and brand prospects
    python manage.py generate-verse   Test: fetch a daily Bible verse
    python manage.py generate-content Test: generate content for today
    python manage.py generate-week    Generate content for the full week (Mon-Sun)
    python manage.py show-calendar    Show this week's content calendar
    python manage.py test-render      Render 1 test reel + feed images (no posting/DB)
    python manage.py generate-audio   Generate background music tracks (--ambient for sound effects)
    python manage.py weekly-report    Generate weekly report
    python manage.py rate-card        Show sponsorship rate card
    python manage.py clear-content    Clear all generated content from database
    python manage.py purge-local      Delete local media files already uploaded to R2
    python manage.py token-status     Check Instagram token health (--refresh to renew)
    python manage.py tiktok-auth      Start TikTok OAuth flow to get access token
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


def generate_week():
    """Generate content for all 7 days of the current week."""
    from datetime import datetime, timedelta
    from database.session import get_db
    from core.content.generator import ContentGenerator
    from core.content.calendar_logic import ContentCalendar, WEEKLY_SCHEDULE, POSTING_TIMES
    from core.images.image_processor import ImagePipeline

    with get_db() as db:
        gen = ContentGenerator(db)
        img_pipeline = ImagePipeline(db)
        cal = ContentCalendar(db)

        # Start from Monday of this week
        today = datetime.utcnow()
        monday = today - timedelta(days=today.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        total = 0
        for day_offset in range(7):
            day = monday + timedelta(days=day_offset)
            day_of_week = day.weekday()
            day_name = day.strftime("%A")
            day_schedule = WEEKLY_SCHEDULE.get(day_of_week, {})

            day_count = 0
            for time_slot, config in day_schedule.items():
                if config is None:
                    continue

                posting_time = POSTING_TIMES[time_slot]
                scheduled_at = day.replace(
                    hour=posting_time.hour,
                    minute=posting_time.minute,
                )

                slot = {
                    "date": day.date().isoformat(),
                    "time_slot": time_slot,
                    "content_type": config["type"].value,
                    "emotional_tone": config["tone"].value,
                    "scheduled_at": scheduled_at,
                    "theme": "",
                    "age_group": "general",
                }

                # Add themes
                from database.models import ContentType
                content_type = config["type"]
                if content_type == ContentType.marriage_monday:
                    slot["theme"] = cal.series.get_marriage_theme()
                elif content_type == ContentType.parenting_wednesday:
                    age_group, theme = cal.series.get_parenting_theme()
                    slot["theme"] = theme
                    slot["age_group"] = age_group
                elif content_type == ContentType.faith_friday:
                    slot["theme"] = cal.series.get_hardship_topic()

                try:
                    content = gen._generate_for_slot(slot)
                    if content:
                        day_count += 1
                        total += 1
                        # Generate images + reel for this content
                        try:
                            imgs = img_pipeline.generate_images_for_content(content)
                            img_count = len(imgs)
                        except Exception as img_e:
                            print(f"    (image generation failed: {img_e})")
                            img_count = 0
                        print(f"  {day_name} {time_slot:8s} | {slot['content_type']:25s} | #{content.id} ({img_count} images)")
                except Exception as e:
                    print(f"  {day_name} {time_slot:8s} | {slot['content_type']:25s} | FAILED: {e}")
                    continue

            if day_count:
                print(f"  --- {day_name}: {day_count} pieces ---")

        print(f"\nTotal: {total} content pieces generated for the week")


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


def test_render():
    """Render 1 test reel + feed images from a fresh verse. No posting, no approval."""
    import time
    from pathlib import Path
    from database.session import get_db
    from core.scraper.bible_api import BibleAPIClient
    from core.config import settings

    # Use timestamp-based ID so each test render gets unique files
    test_id = int(time.time()) % 100000

    with get_db() as db:
        # 1. Fetch a verse
        print("\n== Test Render ==\n")
        print("1. Fetching verse...")
        bible = BibleAPIClient(db)
        verse = bible.fetch_daily_verse()
        if not verse:
            print("   FAILED: Could not fetch verse")
            return
        print(f"   {verse.reference}: {verse.text[:80]}...")

        # 2. Download background image
        print("\n2. Downloading background image...")
        raw_path = None

        if settings.unsplash_access_key:
            from core.images.unsplash_client import UnsplashClient
            try:
                unsplash = UnsplashClient()
                result = unsplash.search_and_download(
                    content_type="daily_verse",
                    high_res=True,
                )
                if result and result.get("local_path"):
                    raw_path = result["local_path"]
                    print(f"   Unsplash: {raw_path}")
                    print(f"   Photo: {result.get('attribution', 'N/A')}")
            except Exception as e:
                print(f"   Unsplash failed: {e}")

        if not raw_path:
            print("   FAILED: No background image available")
            return

        # 3. Generate feed overlay images
        print("\n3. Generating feed overlays...")
        from core.images.image_processor import (
            TARGET_SIZES,
            IMAGES_PROCESSED_DIR,
            ImagePipeline,
            _apply_feed_overlay,
        )

        IMAGES_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        feed_paths = []

        from PIL import Image as PILImage

        hook_text = verse.text[:60] + "..."

        for img_format, target_size in TARGET_SIZES.items():
            try:
                img = PILImage.open(raw_path)
                img = ImagePipeline._resize_and_crop(img, target_size)
                img = _apply_feed_overlay(
                    img=img,
                    text=hook_text,
                    content_id=0,
                    content_type="daily_verse",
                    verse_text=verse.text,
                    verse_ref=verse.reference,
                    verse_translation=verse.translation or "WEB",
                )
                out_path = IMAGES_PROCESSED_DIR / f"test_{img_format.value}.jpg"
                img.save(str(out_path), "JPEG", quality=92)
                feed_paths.append(str(out_path))
                print(f"   {img_format.value}: {out_path}")
            except Exception as e:
                print(f"   {img_format.value}: FAILED — {e}")

        # 4. Generate reel
        print(f"\n4. Generating reel (motion: {settings.reel_motion_style})...")
        from core.images.reel_generator import generate_reel

        reel_path = generate_reel(
            background_path=raw_path,
            verse_text=verse.text,
            verse_ref=verse.reference,
            content_id=test_id,
            translation=verse.translation or "WEB",
            content_type="daily_verse",
        )

        if reel_path:
            reel_size_mb = Path(reel_path).stat().st_size / (1024 * 1024)
            print(f"   Reel: {reel_path} ({reel_size_mb:.1f} MB)")
        else:
            print("   Reel: FAILED")

        # Summary
        print("\n== Output Files ==\n")
        for p in feed_paths:
            print(f"  {p}")
        if reel_path:
            print(f"  {reel_path}")
        print(f"\nOpen these files in Explorer to inspect quality.")


def generate_audio():
    """Download/generate background music tracks.

    Sources (auto-selected, best available):
      1. ElevenLabs Music API (paid plan)
      2. Mixkit free stock music (default — real royalty-free tracks)
      3. FFmpeg sine waves (last resort)

    Pass --source=mixkit|elevenlabs|sine to force a specific source.
    Pass --overwrite to re-download existing tracks.
    Pass --ambient to also generate ambient sound effects.
    """
    from core.audio.elevenlabs_music import generate_tracks

    # Parse optional flags
    source = None
    overwrite = False
    gen_ambient = False
    for arg in sys.argv[2:]:
        if arg.startswith("--source="):
            source = arg.split("=", 1)[1]
        elif arg == "--overwrite":
            overwrite = True
        elif arg == "--ambient":
            gen_ambient = True

    print("\n== Generate Background Audio ==\n")

    if source:
        print(f"Source: {source}")
    else:
        print("Auto-selecting best available source (Mixkit free tracks)")

    tracks = generate_tracks(source=source, overwrite=overwrite)

    if tracks:
        print(f"\nDownloaded/generated {len(tracks)} audio tracks:")
        for t in tracks:
            size_kb = t.stat().st_size / 1024
            print(f"  {t.name} ({size_kb:.0f} KB)")
    else:
        print("\nNo tracks generated. Check logs for errors.")

    if gen_ambient:
        from core.audio.elevenlabs_music import generate_ambient_sounds
        print("\n== Generate Ambient Sound Effects ==\n")
        ambient = generate_ambient_sounds(overwrite=overwrite)
        if ambient:
            print(f"\nGenerated {len(ambient)} ambient sounds:")
            for a in ambient:
                size_kb = a.stat().st_size / 1024
                print(f"  {a.name} ({size_kb:.0f} KB)")
        else:
            print("No ambient sounds generated (requires ElevenLabs API key).")


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


def clear_content():
    """Clear all generated content, images, posting logs, and verses."""
    from database.session import get_db
    from database.models import (
        GeneratedContent, GeneratedImage, PostingLog,
        BibleVerse, ContentCalendarSlot,
    )

    with get_db() as db:
        logs = db.query(PostingLog).delete()
        images = db.query(GeneratedImage).delete()
        content = db.query(GeneratedContent).delete()
        verses = db.query(BibleVerse).delete()
        slots = db.query(ContentCalendarSlot).delete()

        print(f"Cleared: {content} content, {images} images, {logs} posting logs, {verses} verses, {slots} calendar slots")


def token_status():
    """Check Instagram token health and optionally refresh."""
    from core.posting.instagram_client import check_token_health, refresh_instagram_token

    print("\nChecking Instagram token...")
    health = check_token_health()

    print(f"  Valid:          {health.get('valid')}")
    print(f"  Expires at:     {health.get('expires_at', 'unknown')}")
    print(f"  Days remaining: {health.get('days_remaining', 'unknown')}")
    print(f"  Scopes:         {', '.join(health.get('scopes', []))}")

    if len(sys.argv) > 2 and sys.argv[2] == "--refresh":
        print("\nRefreshing token...")
        new_token = refresh_instagram_token()
        if new_token:
            print(f"  New token: {new_token[:20]}...")
            print("  .env updated successfully")
        else:
            print("  Refresh FAILED")
    elif health.get("days_remaining", 0) < 14:
        print(f"\n  Token expiring soon! Run: python manage.py token-status --refresh")


def purge_local_media():
    """Delete local image/video/narration files that have been uploaded to R2.

    Keeps: audio music tracks (reused), test renders, files not yet on R2.
    """
    from pathlib import Path
    from database.session import get_db
    from database.models import GeneratedImage

    raw_dir = Path("images/raw")
    processed_dir = Path("images/processed")
    narration_dir = Path("audio/narration")

    deleted = 0
    freed_bytes = 0

    # Delete processed files that have R2 URLs (not file:// URLs)
    with get_db() as db:
        uploaded = (
            db.query(GeneratedImage)
            .filter(GeneratedImage.final_url.like("https://%"))
            .all()
        )
        r2_content_ids = {img.content_id for img in uploaded}
        print(f"Found {len(uploaded)} images/reels on R2 across {len(r2_content_ids)} content pieces")

    # Clean processed files
    if processed_dir.exists():
        for f in processed_dir.iterdir():
            if f.name.startswith("test_"):
                continue  # Keep test renders
            try:
                # Extract content_id from filename like "29_feed_4x5.jpg"
                content_id = int(f.stem.split("_")[0])
                if content_id in r2_content_ids:
                    size = f.stat().st_size
                    f.unlink()
                    deleted += 1
                    freed_bytes += size
            except (ValueError, IndexError):
                continue

    # Clean raw Unsplash downloads
    if raw_dir.exists():
        for f in raw_dir.iterdir():
            size = f.stat().st_size
            f.unlink()
            deleted += 1
            freed_bytes += size

    # Clean narration cache
    if narration_dir.exists():
        for f in narration_dir.iterdir():
            if f.suffix == ".mp3":
                size = f.stat().st_size
                f.unlink()
                deleted += 1
                freed_bytes += size

    freed_mb = freed_bytes / (1024 * 1024)
    print(f"\nDeleted {deleted} files, freed {freed_mb:.1f} MB")


def tiktok_auth():
    """Start TikTok OAuth flow to get an access token.

    Opens the TikTok authorization page in your browser. After authorizing,
    TikTok redirects to our callback page with an auth code. Paste the code
    here to exchange it for an access token.
    """
    from core.posting.tiktok_client import get_auth_url, exchange_code_for_token
    from core.config import settings

    if not settings.tiktok_client_key:
        print("Error: TIKTOK_CLIENT_KEY not set in .env")
        return

    redirect_uri = "https://davidkimmel.github.io/Stillwatergrace/callback.html"
    auth_url = get_auth_url(redirect_uri)

    print("\n== TikTok Authorization ==\n")
    print("1. Open this URL in your browser:\n")
    print(f"   {auth_url}\n")
    print("2. Log in to TikTok and authorize the app")
    print("3. You'll be redirected to a page with an auth code")
    print("4. Copy the code and paste it below\n")

    # Try to open browser automatically
    try:
        import webbrowser
        webbrowser.open(auth_url)
        print("(Browser should have opened automatically)\n")
    except Exception:
        pass

    code = input("Paste the authorization code: ").strip()
    if not code:
        print("No code provided. Aborting.")
        return

    print("\nExchanging code for access token...")
    result = exchange_code_for_token(code, redirect_uri)

    if result and result.get("access_token"):
        print(f"\n  Access token:  {result['access_token'][:20]}...")
        print(f"  Refresh token: {result.get('refresh_token', 'none')[:20]}...")
        print(f"  Expires in:    {result.get('expires_in', 'unknown')} seconds")
        print(f"  Open ID:       {result.get('open_id', 'unknown')}")
        print("\n  Saved to .env successfully!")
    else:
        print("\n  Token exchange FAILED. Check logs for details.")


COMMANDS = {
    "init-db": init_db,
    "seed": seed,
    "generate-verse": generate_verse,
    "generate-content": generate_content,
    "generate-week": generate_week,
    "show-calendar": show_calendar,
    "test-render": test_render,
    "generate-audio": generate_audio,
    "weekly-report": weekly_report,
    "rate-card": rate_card,
    "clear-content": clear_content,
    "token-status": token_status,
    "purge-local": purge_local_media,
    "tiktok-auth": tiktok_auth,
}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    COMMANDS[command]()
