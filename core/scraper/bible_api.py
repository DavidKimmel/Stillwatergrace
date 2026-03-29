"""Bible API client — fetches verses from API.Bible (rest.api.bible).

Uses NIV 2011 translation by default via direct HTTP calls.
Falls back to bible-api.com (WEB) if API.Bible key is unavailable.
"""

import logging
import re
import random
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from core.config import settings
from database.models import BibleVerse

logger = logging.getLogger(__name__)

# Legacy fallback URL (WEB translation)
BASE_URL = "https://bible-api.com"

# Curated list of books and chapters with strong encouragement/family content.
# Weighted toward Psalms, Proverbs, and NT letters for variety.
VERSE_POOL = [
    # Psalms — encouragement, praise, trust
    "Psalm 23:1-6", "Psalm 27:1", "Psalm 34:8", "Psalm 37:4-5", "Psalm 46:1-2",
    "Psalm 55:22", "Psalm 56:3-4", "Psalm 62:1-2", "Psalm 91:1-2", "Psalm 103:1-5",
    "Psalm 119:105", "Psalm 121:1-2", "Psalm 127:3-5", "Psalm 139:13-14", "Psalm 145:18",
    # Proverbs — wisdom, family, marriage
    "Proverbs 3:5-6", "Proverbs 4:23", "Proverbs 11:25", "Proverbs 12:4", "Proverbs 14:26",
    "Proverbs 15:1", "Proverbs 16:3", "Proverbs 16:9", "Proverbs 17:6", "Proverbs 18:22",
    "Proverbs 22:6", "Proverbs 27:17", "Proverbs 31:25-26", "Proverbs 31:28-29", "Proverbs 31:30",
    # Isaiah — comfort, hope
    "Isaiah 26:3", "Isaiah 40:29-31", "Isaiah 41:10", "Isaiah 43:2", "Isaiah 43:18-19",
    "Isaiah 54:10", "Isaiah 55:8-9", "Isaiah 58:11", "Isaiah 61:1-3",
    # Jeremiah
    "Jeremiah 29:11", "Jeremiah 31:3", "Jeremiah 33:3",
    # Lamentations
    "Lamentations 3:22-23",
    # Romans
    "Romans 5:3-5", "Romans 8:1", "Romans 8:18", "Romans 8:26", "Romans 8:28",
    "Romans 8:31", "Romans 8:37-39", "Romans 12:2", "Romans 12:10-12", "Romans 15:13",
    # 1 Corinthians
    "1 Corinthians 10:13", "1 Corinthians 13:4-7", "1 Corinthians 13:13", "1 Corinthians 16:13-14",
    # 2 Corinthians
    "2 Corinthians 1:3-4", "2 Corinthians 4:16-18", "2 Corinthians 5:7", "2 Corinthians 12:9-10",
    # Galatians
    "Galatians 5:22-23", "Galatians 6:9",
    # Ephesians
    "Ephesians 2:8-9", "Ephesians 3:16-19", "Ephesians 4:2-3", "Ephesians 4:32",
    "Ephesians 5:25", "Ephesians 6:1-3", "Ephesians 6:10-11",
    # Philippians
    "Philippians 1:6", "Philippians 2:3-4", "Philippians 4:6-7", "Philippians 4:8",
    "Philippians 4:13", "Philippians 4:19",
    # Colossians
    "Colossians 3:12-14", "Colossians 3:23-24",
    # 1 Thessalonians
    "1 Thessalonians 5:11", "1 Thessalonians 5:16-18",
    # 2 Timothy
    "2 Timothy 1:7",
    # Hebrews
    "Hebrews 4:16", "Hebrews 10:23-25", "Hebrews 11:1", "Hebrews 12:1-2", "Hebrews 13:5-6",
    # James
    "James 1:2-4", "James 1:5", "James 1:17", "James 4:8",
    # 1 Peter
    "1 Peter 3:3-4", "1 Peter 4:8", "1 Peter 5:6-7",
    # 1 John
    "1 John 3:1", "1 John 4:7-8", "1 John 4:18-19",
    # Matthew
    "Matthew 5:14-16", "Matthew 6:33-34", "Matthew 7:7-8", "Matthew 11:28-30",
    "Matthew 18:20", "Matthew 19:4-6",
    # John
    "John 3:16", "John 8:32", "John 10:10", "John 13:34-35", "John 14:27",
    "John 15:5", "John 15:12-13", "John 16:33",
    # Joshua
    "Joshua 1:9",
    # Deuteronomy
    "Deuteronomy 6:5-7", "Deuteronomy 31:6",
    # Genesis
    "Genesis 2:24",
    # Ecclesiastes
    "Ecclesiastes 4:9-12",
]

# API.Bible NIV 2011 bible ID
_NIV_BIBLE_ID = "78a9f6124f344018-01"
_API_BIBLE_BASE = "https://rest.api.bible/v1"

# Mapping from human-readable book names to API.Bible abbreviations
_BOOK_ABBREVS: dict[str, str] = {
    "Genesis": "GEN", "Exodus": "EXO", "Leviticus": "LEV", "Numbers": "NUM",
    "Deuteronomy": "DEU", "Joshua": "JOS", "Judges": "JDG", "Ruth": "RUT",
    "1 Samuel": "1SA", "2 Samuel": "2SA", "1 Kings": "1KI", "2 Kings": "2KI",
    "1 Chronicles": "1CH", "2 Chronicles": "2CH", "Ezra": "EZR", "Nehemiah": "NEH",
    "Esther": "EST", "Job": "JOB", "Psalm": "PSA", "Psalms": "PSA",
    "Proverbs": "PRO", "Ecclesiastes": "ECC", "Song of Solomon": "SNG",
    "Isaiah": "ISA", "Jeremiah": "JER", "Lamentations": "LAM", "Ezekiel": "EZK",
    "Daniel": "DAN", "Hosea": "HOS", "Joel": "JOL", "Amos": "AMO",
    "Obadiah": "OBA", "Jonah": "JON", "Micah": "MIC", "Nahum": "NAM",
    "Habakkuk": "HAB", "Zephaniah": "ZEP", "Haggai": "HAG", "Zechariah": "ZEC",
    "Malachi": "MAL", "Matthew": "MAT", "Mark": "MRK", "Luke": "LUK",
    "John": "JHN", "Acts": "ACT", "Romans": "ROM",
    "1 Corinthians": "1CO", "2 Corinthians": "2CO",
    "Galatians": "GAL", "Ephesians": "EPH", "Philippians": "PHP",
    "Colossians": "COL", "1 Thessalonians": "1TH", "2 Thessalonians": "2TH",
    "1 Timothy": "1TI", "2 Timothy": "2TI", "Titus": "TIT", "Philemon": "PHM",
    "Hebrews": "HEB", "James": "JAS", "1 Peter": "1PE", "2 Peter": "2PE",
    "1 John": "1JN", "2 John": "2JN", "3 John": "3JN", "Jude": "JUD",
    "Revelation": "REV",
}


def _reference_to_api_format(reference: str) -> Optional[str]:
    """Convert 'Psalm 23:1-6' to 'PSA.23.1-PSA.23.6' for API.Bible.

    Single verse: 'John 3:16' -> 'JHN.3.16'
    Range: 'Psalm 23:1-6' -> 'PSA.23.1-PSA.23.6'
    """
    parts = reference.rsplit(":", 1)
    if len(parts) != 2:
        return None

    book_chapter = parts[0].strip()
    verse_part = parts[1].strip()

    # Split book from chapter
    tokens = book_chapter.rsplit(" ", 1)
    if len(tokens) != 2:
        return None
    book_name = tokens[0]
    chapter = tokens[1]

    abbrev = _BOOK_ABBREVS.get(book_name)
    if not abbrev:
        return None

    if "-" in verse_part:
        start, end = verse_part.split("-", 1)
        return f"{abbrev}.{chapter}.{start}-{abbrev}.{chapter}.{end}"
    return f"{abbrev}.{chapter}.{verse_part}"


class BibleAPIClient:
    """Client for bible-api.com — fetches and caches Bible verses."""

    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.Client(timeout=15.0)

    def fetch_verse(self, reference: str) -> Optional[BibleVerse]:
        """Fetch a specific verse by reference (e.g., 'John 3:16').

        Returns cached version if available, otherwise fetches from API.
        Uses API.Bible (NIV) when key is available, falls back to bible-api.com (WEB).
        """
        # Check cache first
        cached = (
            self.db.query(BibleVerse)
            .filter(BibleVerse.reference == reference)
            .first()
        )
        if cached and cached.translation == "NIV":
            return cached

        # Try API.Bible (NIV) first
        api_key = settings.bible_api_key

        if api_key:
            try:
                verse_ref = _reference_to_api_format(reference)
                if not verse_ref:
                    raise ValueError(f"Cannot convert '{reference}' to API.Bible format")

                url = f"{_API_BIBLE_BASE}/bibles/{_NIV_BIBLE_ID}/verses/{verse_ref}"
                resp = self.client.get(
                    url,
                    headers={"api-key": api_key},
                    params={
                        "content-type": "text",
                        "include-notes": "false",
                        "include-verse-numbers": "false",
                    },
                )
                resp.raise_for_status()
                api_data = resp.json()["data"]

                raw_text = api_data["content"]
                # Strip [10] verse number markers and clean whitespace
                text = re.sub(r"\[\d+\]\s*", "", raw_text).strip()
                text = re.sub(r"\s+", " ", text)

                ref = reference  # keep our canonical reference format
                translation = "NIV"

                book, chapter, verse_start, verse_end = self._parse_reference(ref)

                # Update existing row to NIV or create new
                existing = (
                    self.db.query(BibleVerse)
                    .filter(BibleVerse.reference == ref)
                    .first()
                )
                if existing:
                    existing.text = text
                    existing.translation = translation
                    self.db.flush()
                    logger.info(f"Updated verse to NIV: {ref}")
                    return existing

                verse = BibleVerse(
                    reference=ref,
                    text=text,
                    book=book,
                    chapter=chapter,
                    verse_start=verse_start,
                    verse_end=verse_end,
                    translation=translation,
                )
                self.db.add(verse)
                self.db.flush()

                logger.info(f"Cached new NIV verse: {ref}")
                return verse

            except Exception as e:
                logger.warning(f"API.Bible (NIV) failed for '{reference}': {e}, falling back to WEB")

        # Fallback: bible-api.com (WEB translation)
        try:
            response = self.client.get(f"{BASE_URL}/{reference}")
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch verse '{reference}': {e}")
            return None

        if "error" in data:
            logger.error(f"Bible API error for '{reference}': {data['error']}")
            return None

        text = data.get("text", "").strip()
        ref = data.get("reference", reference)

        book, chapter, verse_start, verse_end = self._parse_reference(ref)

        existing = (
            self.db.query(BibleVerse)
            .filter(BibleVerse.reference == ref)
            .first()
        )
        if existing:
            return existing

        verse = BibleVerse(
            reference=ref,
            text=text,
            book=book,
            chapter=chapter,
            verse_start=verse_start,
            verse_end=verse_end,
            translation="web",
        )
        self.db.add(verse)
        self.db.flush()

        logger.info(f"Cached new WEB verse: {ref}")
        return verse

    def fetch_daily_verse(self) -> Optional[BibleVerse]:
        """Fetch a verse for today, avoiding repeats within 90 days.

        Selects from the curated VERSE_POOL, skipping any used in the last 90 days.
        """
        cutoff = datetime.utcnow() - timedelta(days=90)

        # Get recently used references
        recent_refs = {
            row.reference
            for row in self.db.query(BibleVerse.reference)
            .filter(BibleVerse.last_used_at >= cutoff)
            .all()
        }

        # Find unused verses from pool
        available = [v for v in VERSE_POOL if v not in recent_refs]

        if not available:
            # All verses used in last 90 days — pick least recently used
            logger.warning("All verses in pool used recently, picking least recent")
            oldest = (
                self.db.query(BibleVerse)
                .filter(BibleVerse.reference.in_(VERSE_POOL))
                .order_by(BibleVerse.last_used_at.asc().nullsfirst())
                .first()
            )
            if oldest:
                reference = oldest.reference
            else:
                reference = random.choice(VERSE_POOL)
        else:
            reference = random.choice(available)

        verse = self.fetch_verse(reference)
        if verse:
            verse.last_used_at = datetime.utcnow()
            verse.use_count = (verse.use_count or 0) + 1
            self.db.flush()

        return verse

    def fetch_random_verse(self, book: Optional[str] = None) -> Optional[BibleVerse]:
        """Fetch a random verse, optionally filtered by book."""
        if book:
            pool = [v for v in VERSE_POOL if v.startswith(book)]
        else:
            pool = VERSE_POOL

        if not pool:
            return None

        reference = random.choice(pool)
        return self.fetch_verse(reference)

    @staticmethod
    def _parse_reference(reference: str) -> tuple[str, int, int, Optional[int]]:
        """Parse 'Book Chapter:Verse-End' into components.

        Examples:
            'John 3:16' -> ('John', 3, 16, None)
            'Psalm 23:1-6' -> ('Psalm', 23, 1, 6)
            '1 Corinthians 13:4-7' -> ('1 Corinthians', 13, 4, 7)
        """
        # Split off the verse part (after last colon)
        parts = reference.rsplit(":", 1)
        if len(parts) != 2:
            return reference, 1, 1, None

        book_chapter = parts[0].strip()
        verse_part = parts[1].strip()

        # Split book from chapter (chapter is last number in book_chapter)
        tokens = book_chapter.rsplit(" ", 1)
        if len(tokens) == 2:
            book = tokens[0]
            try:
                chapter = int(tokens[1])
            except ValueError:
                book = book_chapter
                chapter = 1
        else:
            book = book_chapter
            chapter = 1

        # Parse verse range
        if "-" in verse_part:
            start_str, end_str = verse_part.split("-", 1)
            try:
                verse_start = int(start_str)
                verse_end = int(end_str)
            except ValueError:
                verse_start = 1
                verse_end = None
        else:
            try:
                verse_start = int(verse_part)
            except ValueError:
                verse_start = 1
            verse_end = None

        return book, chapter, verse_start, verse_end
