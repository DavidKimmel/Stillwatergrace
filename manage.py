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
    python manage.py generate-devotional  Generate a branded devotional PDF (--theme=finding_peace [--upload])
    python manage.py list-devotionals     List available devotional themes
    python manage.py scrape-quotes        Scrape Christian quotes (seed + APIs)
    python manage.py list-quotes          Browse stored quotes (--author=lewis)
    python manage.py generate-quote-content  Generate Instagram caption from a random quote
    python manage.py test-phrase-reel     Generate a phrase-pop reel (--content-id=N or --text="...")
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
    days = health.get("days_remaining")
    print(f"  Days remaining: {'never expires' if days is None else days}")
    print(f"  Scopes:         {', '.join(health.get('scopes', []))}")

    if len(sys.argv) > 2 and sys.argv[2] == "--refresh":
        print("\nRefreshing token...")
        new_token = refresh_instagram_token()
        if new_token:
            print(f"  New token: {new_token[:20]}...")
            print("  .env updated successfully")
        else:
            print("  Refresh FAILED")
    elif days is not None and days < 14:
        print(f"\n  Token expiring soon! Run: python manage.py token-status --refresh")
    elif days is None:
        print("\n  Token is never-expiring. No refresh needed.")


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


def generate_devotional():
    """Generate a branded devotional PDF from a theme."""
    from core.devotional.orchestrator import DevotionalOrchestrator
    from core.devotional.themes import list_themes

    # Parse --theme arg
    theme_slug = None
    upload = False
    for arg in sys.argv[2:]:
        if arg.startswith("--theme="):
            theme_slug = arg.split("=", 1)[1].lower().replace(" ", "_")
        elif arg == "--upload":
            upload = True

    if not theme_slug:
        print("Usage: python manage.py generate-devotional --theme=finding_peace [--upload]")
        print(f"\nAvailable themes: {', '.join(list_themes())}")
        return

    print(f"\n== Generating Devotional: {theme_slug} ==\n")
    orch = DevotionalOrchestrator()

    if upload:
        result = orch.generate_and_upload(theme_slug)
    else:
        result = orch.generate(theme_slug)

    print(f"\nDone! Output: {result}")


def list_devotionals_cmd():
    """List available devotional themes."""
    from core.devotional.themes import THEMES

    print("\n== Available Devotional Themes ==\n")
    for slug, theme in THEMES.items():
        print(f"  {slug}")
        print(f"    Title: {theme.title}")
        print(f"    Subtitle: {theme.subtitle}")
        print(f"    Days: {len(theme.days)}")
        print()


def scrape_quotes():
    """Run the Christian quotes scraper (seed data + public APIs)."""
    from database.session import get_db
    from core.scraper.quotes_scraper import QuotesScraper

    with get_db() as db:
        scraper = QuotesScraper(db)
        result = scraper.run_full_scrape()
        print(f"\nQuotes scrape complete:")
        print(f"  Seeded:      {result['seeded']}")
        print(f"  From APIs:   {result['scraped']}")
        print(f"  Total new:   {result['total_new']}")

        from database.models import ChristianQuote
        total_in_db = db.query(ChristianQuote).count()
        print(f"  Total in DB: {total_in_db}")


def list_quotes_cmd():
    """Browse stored Christian quotes. Use --author=lewis to filter."""
    from database.session import get_db
    from core.scraper.quotes_scraper import QuotesScraper

    # Parse --author flag
    author_filter = None
    for arg in sys.argv[2:]:
        if arg.startswith("--author="):
            author_filter = arg.split("=", 1)[1]

    with get_db() as db:
        scraper = QuotesScraper(db)
        quotes = scraper.list_quotes(author=author_filter)

        if not quotes:
            print("\nNo quotes found. Run 'python manage.py scrape-quotes' first.")
            return

        print(f"\n== Christian Quotes ({len(quotes)} total) ==\n")
        current_author = ""
        for q in quotes:
            if q.author != current_author:
                print(f"\n  {q.author}")
                print(f"  {'─' * 50}")
                current_author = q.author
            source_str = f" — {q.source}" if q.source else ""
            tags_str = ", ".join(q.tags) if q.tags else ""
            print(f'    "{q.quote_text}"{source_str}')
            if tags_str:
                print(f"      [{tags_str}]")


def generate_quote_content():
    """Pick a random quote and generate Instagram caption text via Claude API."""
    from database.session import get_db
    from core.scraper.quotes_scraper import QuotesScraper
    from core.config import settings

    import anthropic

    with get_db() as db:
        scraper = QuotesScraper(db)
        quote = scraper.get_random_quote()

        if not quote:
            print("\nNo quotes in database. Run 'python manage.py scrape-quotes' first.")
            return

        print(f'\nSelected quote by {quote.author}:')
        print(f'  "{quote.quote_text}"')
        if quote.source:
            print(f"  Source: {quote.source}")
        print()

        if not settings.anthropic_api_key:
            print("Error: ANTHROPIC_API_KEY not set in .env")
            return

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        system_prompt = (
            "You are the social media manager for @stillwatergrace, a Christian faith-and-family "
            "Instagram page. Your captions are warm, relatable, and encourage engagement. "
            "Write for a broad Christian audience — married couples, parents, young adults seeking faith."
        )

        user_prompt = (
            f'Generate an Instagram caption for this Christian quote:\n\n'
            f'Quote: "{quote.quote_text}"\n'
            f'Author: {quote.author}\n'
            f'Source: {quote.source or "Unknown"}\n'
            f'Tags: {", ".join(quote.tags) if quote.tags else "general"}\n\n'
            f'Requirements:\n'
            f'1. A short hook line (under 15 words) to stop the scroll\n'
            f'2. The quote itself, properly attributed\n'
            f'3. A 2-3 sentence reflection connecting the quote to daily life\n'
            f'4. A call-to-action question for engagement\n'
            f'5. 5-8 relevant hashtags\n\n'
            f'Format: Plain text, not JSON. Use line breaks for readability.'
        )

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=800,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text

            print("== Generated Caption ==\n")
            print(text)
            print(f"\n(Tokens: {response.usage.input_tokens} in / {response.usage.output_tokens} out)")

        except anthropic.APIError as e:
            print(f"Claude API error: {e}")


def test_phrase_reel():
    """Generate a phrase-pop reel from DB content or arbitrary text.

    Usage:
        python manage.py test-phrase-reel --content-id=63
        python manage.py test-phrase-reel --text="Be still and know that I am God." --voice=0
    """
    from core.images.phrase_reel_generator import generate_phrase_reel

    # Parse args
    content_id_arg = None
    text_arg = None
    voice_arg = None
    author_arg = None
    for arg in sys.argv[2:]:
        if arg.startswith("--content-id="):
            content_id_arg = int(arg.split("=", 1)[1])
        elif arg.startswith("--text="):
            text_arg = arg.split("=", 1)[1]
        elif arg.startswith("--voice="):
            voice_arg = int(arg.split("=", 1)[1])
        elif arg.startswith("--author="):
            author_arg = arg.split("=", 1)[1]

    if content_id_arg is None and text_arg is None:
        print("Usage:")
        print("  python manage.py test-phrase-reel --content-id=63")
        print('  python manage.py test-phrase-reel --text="Be still and know." --voice=0')
        return

    background_path = None
    text = text_arg or ""
    content_id = content_id_arg or 0
    content_type = "christian_quote" if author_arg else "daily_verse"

    if content_id_arg is not None:
        # Load from database
        from database.session import get_db
        from database.models import GeneratedContent, GeneratedImage, ImageFormat

        with get_db() as db:
            content = db.query(GeneratedContent).filter_by(id=content_id_arg).first()
            if not content:
                print(f"Content #{content_id_arg} not found in database")
                return

            # Get text from content
            if content.verse_text:
                text = content.verse_text
                if content.verse_ref:
                    text = f"{text} -- {content.verse_ref}"
            elif content.caption_short:
                text = content.caption_short
            elif content.hook:
                text = content.hook
            else:
                print(f"Content #{content_id_arg} has no text to narrate")
                return

            content_type = content.content_type.value if content.content_type else "daily_verse"
            content_id = content.id

            # Try to find an existing background image
            image = (
                db.query(GeneratedImage)
                .filter_by(content_id=content_id_arg, image_format=ImageFormat.story_9x16)
                .first()
            )
            if image and image.local_path:
                from pathlib import Path as P
                local = P(image.local_path)
                if local.exists():
                    background_path = str(local)

    print(f"\n== Phrase Pop Reel Generator ==\n")
    print(f"  Content ID: {content_id}")
    print(f"  Text: {text[:80]}{'...' if len(text) > 80 else ''}")
    if voice_arg is not None:
        print(f"  Voice: {voice_arg}")
    print(f"  Content type: {content_type}")

    # If no background image, fetch one from Unsplash
    if not background_path:
        print("\n  Downloading background image from Unsplash...")
        from core.config import settings as _settings
        if _settings.unsplash_access_key:
            try:
                from core.images.unsplash_client import UnsplashClient
                unsplash = UnsplashClient()
                result = unsplash.search_and_download(
                    content_type=content_type,
                    high_res=True,
                )
                if result and result.get("local_path"):
                    background_path = result["local_path"]
                    print(f"  Background: {background_path}")
            except Exception as e:
                print(f"  Unsplash failed: {e}")

    if not background_path:
        print("\n  ERROR: No background image available")
        return

    if author_arg:
        print(f"  Author: {author_arg}")

    print(f"\n  Generating phrase-pop reel...")
    reel_path = generate_phrase_reel(
        background_path=background_path,
        text=text,
        content_id=content_id,
        voice_index=voice_arg,
        content_type=content_type,
        author=author_arg,
    )

    if reel_path:
        from pathlib import Path as P
        size_mb = P(reel_path).stat().st_size / (1024 * 1024)
        print(f"\n  Reel saved: {reel_path} ({size_mb:.1f} MB)")
        print(f"\n  Open the file to preview the phrase-pop effect.")
    else:
        print("\n  Reel generation FAILED. Check logs above.")


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
    "generate-devotional": generate_devotional,
    "list-devotionals": list_devotionals_cmd,
    "scrape-quotes": scrape_quotes,
    "list-quotes": list_quotes_cmd,
    "generate-quote-content": generate_quote_content,
    "test-phrase-reel": test_phrase_reel,
}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    COMMANDS[command]()
