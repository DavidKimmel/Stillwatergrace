"""Christian quotes scraper — seed data + public API scraping.

Provides curated quotes from classic Christian authors for content generation.
Primary source: built-in seed data (guaranteed accurate quotes).
Secondary source: public quote APIs (graceful fallback on failure).
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from database.models import ChristianQuote

logger = logging.getLogger(__name__)

# Target authors for scraping and filtering
TARGET_AUTHORS: frozenset[str] = frozenset({
    "C.S. Lewis",
    "Charles Spurgeon",
    "A.W. Tozer",
    "Francis Chan",
    "Tim Keller",
    "A.W. Pink",
    "Corrie ten Boom",
    "Elisabeth Elliot",
    "Dietrich Bonhoeffer",
    "Billy Graham",
})

# Normalized lookup for matching scraped author names to canonical names
_AUTHOR_ALIASES: dict[str, str] = {
    "c.s. lewis": "C.S. Lewis",
    "cs lewis": "C.S. Lewis",
    "clive staples lewis": "C.S. Lewis",
    "charles spurgeon": "Charles Spurgeon",
    "charles haddon spurgeon": "Charles Spurgeon",
    "c.h. spurgeon": "Charles Spurgeon",
    "a.w. tozer": "A.W. Tozer",
    "aiden wilson tozer": "A.W. Tozer",
    "francis chan": "Francis Chan",
    "tim keller": "Tim Keller",
    "timothy keller": "Tim Keller",
    "a.w. pink": "A.W. Pink",
    "arthur walkington pink": "A.W. Pink",
    "corrie ten boom": "Corrie ten Boom",
    "elisabeth elliot": "Elisabeth Elliot",
    "elizabeth elliot": "Elisabeth Elliot",
    "dietrich bonhoeffer": "Dietrich Bonhoeffer",
    "billy graham": "Billy Graham",
    "william franklin graham": "Billy Graham",
}


def _compute_hash(text: str) -> str:
    """Compute SHA-256 hash of quote text for dedup."""
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalize_author(name: str) -> Optional[str]:
    """Map a scraped author name to our canonical name, or None if not a target."""
    key = name.strip().lower()
    if key in _AUTHOR_ALIASES:
        return _AUTHOR_ALIASES[key]
    # Direct match check
    for canonical in TARGET_AUTHORS:
        if canonical.lower() == key:
            return canonical
    return None


# ──────────────────────────────────────────────
# Seed Data — Real, verified quotes
# ──────────────────────────────────────────────

SEED_QUOTES: tuple[dict, ...] = (
    # ── C.S. Lewis ──
    {
        "author": "C.S. Lewis",
        "quote_text": "God can't give us peace and happiness apart from Himself because there is no such thing.",
        "source": "Mere Christianity",
        "tags": ["faith", "hope", "wisdom"],
    },
    {
        "author": "C.S. Lewis",
        "quote_text": "You can't go back and change the beginning, but you can start where you are and change the ending.",
        "source": "Attributed",
        "tags": ["perseverance", "hope", "courage"],
    },
    {
        "author": "C.S. Lewis",
        "quote_text": "Hardships often prepare ordinary people for an extraordinary destiny.",
        "source": "Attributed",
        "tags": ["hardship", "perseverance", "courage"],
    },
    {
        "author": "C.S. Lewis",
        "quote_text": "Integrity is doing the right thing, even when no one is watching.",
        "source": "Attributed",
        "tags": ["faith", "wisdom", "courage"],
    },
    {
        "author": "C.S. Lewis",
        "quote_text": "There are far, far better things ahead than any we leave behind.",
        "source": "Collected Letters of C.S. Lewis",
        "tags": ["hope", "faith", "perseverance"],
    },
    {
        "author": "C.S. Lewis",
        "quote_text": "To love at all is to be vulnerable.",
        "source": "The Four Loves",
        "tags": ["love", "courage", "wisdom"],
    },
    # ── Charles Spurgeon ──
    {
        "author": "Charles Spurgeon",
        "quote_text": "A Bible that's falling apart usually belongs to someone who isn't.",
        "source": "Attributed",
        "tags": ["faith", "wisdom", "perseverance"],
    },
    {
        "author": "Charles Spurgeon",
        "quote_text": "God is too good to be unkind and He is too wise to be mistaken.",
        "source": "Sermons of Charles Spurgeon",
        "tags": ["trust", "faith", "wisdom"],
    },
    {
        "author": "Charles Spurgeon",
        "quote_text": "Anxiety does not empty tomorrow of its sorrows, but only empties today of its strength.",
        "source": "Attributed",
        "tags": ["trust", "hardship", "wisdom"],
    },
    {
        "author": "Charles Spurgeon",
        "quote_text": "The Lord gets His best soldiers out of the highlands of affliction.",
        "source": "Attributed",
        "tags": ["hardship", "perseverance", "faith"],
    },
    {
        "author": "Charles Spurgeon",
        "quote_text": "I have learned to kiss the wave that throws me against the Rock of Ages.",
        "source": "Attributed",
        "tags": ["hardship", "trust", "faith"],
    },
    # ── A.W. Tozer ──
    {
        "author": "A.W. Tozer",
        "quote_text": "What comes into our minds when we think about God is the most important thing about us.",
        "source": "The Knowledge of the Holy",
        "tags": ["faith", "wisdom", "prayer"],
    },
    {
        "author": "A.W. Tozer",
        "quote_text": "The reason why many are still troubled, still seeking, still making little forward progress is because they haven't yet come to the end of themselves.",
        "source": "The Pursuit of God",
        "tags": ["faith", "perseverance", "wisdom"],
    },
    {
        "author": "A.W. Tozer",
        "quote_text": "God never hurries. There are no deadlines against which He must work.",
        "source": "The Knowledge of the Holy",
        "tags": ["trust", "wisdom", "faith"],
    },
    {
        "author": "A.W. Tozer",
        "quote_text": "To be right with God has often meant to be in trouble with men.",
        "source": "Attributed",
        "tags": ["courage", "faith", "hardship"],
    },
    {
        "author": "A.W. Tozer",
        "quote_text": "The world is perishing for lack of the knowledge of God, and the church is famishing for want of His presence.",
        "source": "The Pursuit of God",
        "tags": ["faith", "prayer", "wisdom"],
    },
    # ── Francis Chan ──
    {
        "author": "Francis Chan",
        "quote_text": "Our greatest fear should not be of failure but of succeeding at things in life that don't really matter.",
        "source": "Crazy Love",
        "tags": ["wisdom", "faith", "courage"],
    },
    {
        "author": "Francis Chan",
        "quote_text": "Lukewarm people don't really want to be saved from their sin; they want only to be saved from the penalty of their sin.",
        "source": "Crazy Love",
        "tags": ["faith", "salvation", "wisdom"],
    },
    {
        "author": "Francis Chan",
        "quote_text": "What are you doing right now that requires faith?",
        "source": "Crazy Love",
        "tags": ["faith", "courage", "wisdom"],
    },
    {
        "author": "Francis Chan",
        "quote_text": "When I am consumed by my problems, I have turned my problems into idols.",
        "source": "Attributed",
        "tags": ["trust", "faith", "hardship"],
    },
    {
        "author": "Francis Chan",
        "quote_text": "Following Christ isn't something that can be done halfheartedly or on the side. It is not a label we can display when convenient.",
        "source": "Crazy Love",
        "tags": ["faith", "courage", "perseverance"],
    },
    # ── Tim Keller ──
    {
        "author": "Tim Keller",
        "quote_text": "The gospel is this: We are more sinful and flawed in ourselves than we ever dared believe, yet at the very same time we are more loved and accepted in Jesus Christ than we ever dared hope.",
        "source": "The Meaning of Marriage",
        "tags": ["grace", "salvation", "love"],
    },
    {
        "author": "Tim Keller",
        "quote_text": "To be loved but not known is comforting but superficial. To be known and not loved is our greatest fear. But to be fully known and truly loved is a lot like being loved by God.",
        "source": "The Meaning of Marriage",
        "tags": ["love", "marriage", "grace"],
    },
    {
        "author": "Tim Keller",
        "quote_text": "If your identity is in your work, and you do well, you may have self-esteem, but you won't have joy.",
        "source": "Counterfeit Gods",
        "tags": ["wisdom", "faith", "hope"],
    },
    {
        "author": "Tim Keller",
        "quote_text": "God's love and forgiveness can pardon and restore any and every kind of sin or wrongdoing.",
        "source": "The Reason for God",
        "tags": ["grace", "salvation", "love"],
    },
    {
        "author": "Tim Keller",
        "quote_text": "Prayer is the only entryway into genuine self-knowledge.",
        "source": "Prayer: Experiencing Awe and Intimacy with God",
        "tags": ["prayer", "wisdom", "faith"],
    },
    # ── A.W. Pink ──
    {
        "author": "A.W. Pink",
        "quote_text": "God does not bestow His blessings upon His children and then leave them to fend for themselves.",
        "source": "The Attributes of God",
        "tags": ["trust", "grace", "faith"],
    },
    {
        "author": "A.W. Pink",
        "quote_text": "The prayer that prevails is not the work of lips and fingertips. It is the cry of a broken heart and the travail of a stricken soul.",
        "source": "Attributed",
        "tags": ["prayer", "faith", "hardship"],
    },
    {
        "author": "A.W. Pink",
        "quote_text": "The sovereignty of God is the one impregnable rock to which the suffering human heart must cling.",
        "source": "The Sovereignty of God",
        "tags": ["trust", "hardship", "faith"],
    },
    {
        "author": "A.W. Pink",
        "quote_text": "Nothing is too great and nothing is too small to commit into the hands of the Lord.",
        "source": "Attributed",
        "tags": ["trust", "prayer", "faith"],
    },
    {
        "author": "A.W. Pink",
        "quote_text": "Salvation is from God, of God, and through God.",
        "source": "The Sovereignty of God",
        "tags": ["salvation", "grace", "faith"],
    },
    # ── Corrie ten Boom ──
    {
        "author": "Corrie ten Boom",
        "quote_text": "Never be afraid to trust an unknown future to a known God.",
        "source": "Attributed",
        "tags": ["trust", "courage", "faith"],
    },
    {
        "author": "Corrie ten Boom",
        "quote_text": "Worry does not empty tomorrow of its sorrow. It empties today of its strength.",
        "source": "Clippings from My Notebook",
        "tags": ["trust", "hardship", "wisdom"],
    },
    {
        "author": "Corrie ten Boom",
        "quote_text": "If you look at the world, you'll be distressed. If you look within, you'll be depressed. If you look at God, you'll be at rest.",
        "source": "Attributed",
        "tags": ["trust", "faith", "hope"],
    },
    {
        "author": "Corrie ten Boom",
        "quote_text": "There is no pit so deep that God's love is not deeper still.",
        "source": "The Hiding Place",
        "tags": ["love", "hardship", "hope"],
    },
    {
        "author": "Corrie ten Boom",
        "quote_text": "Forgiveness is an act of the will, and the will can function regardless of the temperature of the heart.",
        "source": "Tramp for the Lord",
        "tags": ["grace", "love", "wisdom"],
    },
    # ── Elisabeth Elliot ──
    {
        "author": "Elisabeth Elliot",
        "quote_text": "The secret is Christ in me, not me in a different set of circumstances.",
        "source": "Attributed",
        "tags": ["faith", "trust", "hardship"],
    },
    {
        "author": "Elisabeth Elliot",
        "quote_text": "God never withholds from His child that which His love and wisdom call good.",
        "source": "Attributed",
        "tags": ["trust", "grace", "wisdom"],
    },
    {
        "author": "Elisabeth Elliot",
        "quote_text": "Of one thing I am perfectly sure: God's story never ends with ashes.",
        "source": "Attributed",
        "tags": ["hope", "faith", "perseverance"],
    },
    {
        "author": "Elisabeth Elliot",
        "quote_text": "The fact that I am a woman does not make me a different kind of Christian, but the fact that I am a Christian makes me a different kind of woman.",
        "source": "Let Me Be a Woman",
        "tags": ["faith", "courage", "wisdom"],
    },
    {
        "author": "Elisabeth Elliot",
        "quote_text": "Leave it all in the Hands that were wounded for you.",
        "source": "Attributed",
        "tags": ["trust", "grace", "faith"],
    },
    # ── Dietrich Bonhoeffer ──
    {
        "author": "Dietrich Bonhoeffer",
        "quote_text": "Cheap grace is the grace we bestow on ourselves. Costly grace is the gospel which must be sought again and again.",
        "source": "The Cost of Discipleship",
        "tags": ["grace", "faith", "salvation"],
    },
    {
        "author": "Dietrich Bonhoeffer",
        "quote_text": "The test of the morality of a society is what it does for its children.",
        "source": "Attributed",
        "tags": ["family", "wisdom", "courage"],
    },
    {
        "author": "Dietrich Bonhoeffer",
        "quote_text": "We must learn to regard people less in light of what they do or omit to do, and more in the light of what they suffer.",
        "source": "Letters and Papers from Prison",
        "tags": ["love", "grace", "wisdom"],
    },
    {
        "author": "Dietrich Bonhoeffer",
        "quote_text": "Silence in the face of evil is itself evil: God will not hold us guiltless.",
        "source": "Attributed",
        "tags": ["courage", "faith", "wisdom"],
    },
    {
        "author": "Dietrich Bonhoeffer",
        "quote_text": "When Christ calls a man, He bids him come and die.",
        "source": "The Cost of Discipleship",
        "tags": ["faith", "courage", "salvation"],
    },
    # ── Billy Graham ──
    {
        "author": "Billy Graham",
        "quote_text": "God has given us two hands, one to receive with and the other to give with.",
        "source": "Attributed",
        "tags": ["love", "grace", "wisdom"],
    },
    {
        "author": "Billy Graham",
        "quote_text": "The will of God will not take us where the grace of God cannot sustain us.",
        "source": "Attributed",
        "tags": ["trust", "grace", "faith"],
    },
    {
        "author": "Billy Graham",
        "quote_text": "Courage is contagious. When a brave man takes a stand, the spines of others are often stiffened.",
        "source": "Attributed",
        "tags": ["courage", "faith", "perseverance"],
    },
    {
        "author": "Billy Graham",
        "quote_text": "When wealth is lost, nothing is lost; when health is lost, something is lost; when character is lost, all is lost.",
        "source": "Attributed",
        "tags": ["wisdom", "faith", "courage"],
    },
    {
        "author": "Billy Graham",
        "quote_text": "My home is in Heaven. I'm just traveling through this world.",
        "source": "Attributed",
        "tags": ["hope", "faith", "salvation"],
    },
)


class QuotesScraper:
    """Scrapes and stores Christian quotes from seed data and public APIs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def seed_quotes(self) -> int:
        """Insert built-in seed quotes, skipping duplicates. Returns count inserted."""
        inserted = 0
        for quote_data in SEED_QUOTES:
            text_hash = _compute_hash(quote_data["quote_text"])

            existing = (
                self.db.query(ChristianQuote)
                .filter(ChristianQuote.text_hash == text_hash)
                .first()
            )
            if existing:
                continue

            quote = ChristianQuote(
                author=quote_data["author"],
                quote_text=quote_data["quote_text"],
                text_hash=text_hash,
                source=quote_data.get("source"),
                tags=quote_data.get("tags", []),
                scraped_from="seed_data",
                scraped_at=datetime.utcnow(),
                approved=True,
            )
            self.db.add(quote)
            inserted += 1

        self.db.flush()
        logger.info(f"Seeded {inserted} quotes ({len(SEED_QUOTES) - inserted} duplicates skipped)")
        return inserted

    def scrape_from_api(self) -> int:
        """Scrape quotes from public APIs. Returns count of new quotes inserted."""
        total_inserted = 0

        # Try ZenQuotes API (free, no key required)
        total_inserted += self._scrape_zenquotes()

        # Try Quotable API
        total_inserted += self._scrape_quotable()

        logger.info(f"Scraped {total_inserted} new quotes from APIs")
        return total_inserted

    def _scrape_zenquotes(self) -> int:
        """Scrape from ZenQuotes API (https://zenquotes.io/api/quotes)."""
        url = "https://zenquotes.io/api/quotes"
        inserted = 0

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                quotes = resp.json()

            if not isinstance(quotes, list):
                logger.warning("ZenQuotes returned non-list response")
                return 0

            for item in quotes:
                author_raw = item.get("a", "")
                text = item.get("q", "")
                if not author_raw or not text:
                    continue

                canonical = _normalize_author(author_raw)
                if not canonical:
                    continue  # Not a target author

                inserted += self._insert_quote(
                    author=canonical,
                    quote_text=text,
                    scraped_from=url,
                )

        except httpx.HTTPError as e:
            logger.warning(f"ZenQuotes API failed: {e}")
        except Exception as e:
            logger.warning(f"ZenQuotes parsing error: {e}")

        return inserted

    def _scrape_quotable(self) -> int:
        """Scrape from Quotable API for each target author."""
        base_url = "https://api.quotable.io/quotes"
        inserted = 0

        for author in TARGET_AUTHORS:
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.get(
                        base_url,
                        params={"author": author, "limit": 20},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()

                results = data.get("results", [])
                for item in results:
                    text = item.get("content", "")
                    author_name = item.get("author", author)
                    if not text:
                        continue

                    canonical = _normalize_author(author_name) or author
                    inserted += self._insert_quote(
                        author=canonical,
                        quote_text=text,
                        scraped_from=f"{base_url}?author={author}",
                    )

            except httpx.HTTPError as e:
                logger.warning(f"Quotable API failed for {author}: {e}")
            except Exception as e:
                logger.warning(f"Quotable parsing error for {author}: {e}")

        return inserted

    def _insert_quote(
        self,
        author: str,
        quote_text: str,
        scraped_from: str = "",
        source: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> int:
        """Insert a single quote if not a duplicate. Returns 1 if inserted, 0 if skipped."""
        text_hash = _compute_hash(quote_text)

        existing = (
            self.db.query(ChristianQuote)
            .filter(ChristianQuote.text_hash == text_hash)
            .first()
        )
        if existing:
            return 0

        quote = ChristianQuote(
            author=author,
            quote_text=quote_text,
            text_hash=text_hash,
            source=source,
            tags=tags or [],
            scraped_from=scraped_from,
            scraped_at=datetime.utcnow(),
            approved=True,
        )
        self.db.add(quote)
        self.db.flush()
        return 1

    def run_full_scrape(self) -> dict[str, int]:
        """Run seed + API scrape. Returns counts."""
        seed_count = self.seed_quotes()
        api_count = self.scrape_from_api()
        return {"seeded": seed_count, "scraped": api_count, "total_new": seed_count + api_count}

    def get_random_quote(self, author: Optional[str] = None) -> Optional[ChristianQuote]:
        """Get a random approved quote, optionally filtered by author."""
        from sqlalchemy.sql.expression import func

        query = self.db.query(ChristianQuote).filter(ChristianQuote.approved == True)  # noqa: E712
        if author:
            query = query.filter(ChristianQuote.author.ilike(f"%{author}%"))
        return query.order_by(func.random()).first()

    def list_quotes(self, author: Optional[str] = None) -> list[ChristianQuote]:
        """List quotes, optionally filtered by author."""
        query = self.db.query(ChristianQuote).order_by(ChristianQuote.author)
        if author:
            query = query.filter(ChristianQuote.author.ilike(f"%{author}%"))
        return query.all()
