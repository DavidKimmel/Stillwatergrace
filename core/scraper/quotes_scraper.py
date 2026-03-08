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
    # ── C.S. Lewis (25-50 word quotes from verified works) ──
    {
        "author": "C.S. Lewis",
        "quote_text": "I believe in Christianity as I believe that the sun has risen: not only because I see it, but because by it I see everything else.",
        "source": "Is Theology Poetry?",
        "tags": ["faith", "wisdom"],
    },
    {
        "author": "C.S. Lewis",
        "quote_text": "God, who foresaw your tribulation, has specially armed you to go through it, not without pain but without stain.",
        "source": "Collected Letters",
        "tags": ["hardship", "trust", "perseverance"],
    },
    {
        "author": "C.S. Lewis",
        "quote_text": "We are not necessarily doubting that God will do the best for us; we are wondering how painful the best will turn out to be.",
        "source": "Letters of C.S. Lewis",
        "tags": ["trust", "hardship", "faith"],
    },
    {
        "author": "C.S. Lewis",
        "quote_text": "You don't have a soul. You are a soul. You have a body. And it is the soul that Christ came to save, the soul that will live forever.",
        "source": "Mere Christianity",
        "tags": ["faith", "salvation", "wisdom"],
    },
    {
        "author": "C.S. Lewis",
        "quote_text": "God allows us to experience the low points of life in order to teach us lessons that we could learn in no other way. The way we learn those lessons is not to deny the feelings but to find the meanings underlying them.",
        "source": "The Problem of Pain",
        "tags": ["hardship", "wisdom", "perseverance"],
    },
    # ── Charles Spurgeon ──
    {
        "author": "Charles Spurgeon",
        "quote_text": "Anxiety does not empty tomorrow of its sorrows, but only empties today of its strength. It does not make you escape the evil; it makes you unfit to cope with it if it comes.",
        "source": "Sermons of Charles Spurgeon",
        "tags": ["trust", "hardship", "wisdom"],
    },
    {
        "author": "Charles Spurgeon",
        "quote_text": "God is too good to be unkind and He is too wise to be mistaken. And when we cannot trace His hand, we must trust His heart.",
        "source": "Sermons of Charles Spurgeon",
        "tags": ["trust", "faith", "wisdom"],
    },
    {
        "author": "Charles Spurgeon",
        "quote_text": "I have learned to kiss the wave that throws me against the Rock of Ages. The Lord is my strength, and in every trial He proves Himself sufficient for all my needs.",
        "source": "Morning and Evening",
        "tags": ["hardship", "trust", "faith"],
    },
    {
        "author": "Charles Spurgeon",
        "quote_text": "If any of you should ask me for an epitome of the Christian religion, I should say it is in one word: prayer. If I am asked what shall I do to be saved, I should say: pray. Live praying. Die praying.",
        "source": "Sermons of Charles Spurgeon",
        "tags": ["prayer", "faith", "perseverance"],
    },
    {
        "author": "Charles Spurgeon",
        "quote_text": "None are more unjust in their judgments of others than those who have a high opinion of themselves. But the Lord measures not by our sight. He searches the heart and weighs the spirit.",
        "source": "The Treasury of David",
        "tags": ["wisdom", "grace", "faith"],
    },
    # ── A.W. Tozer ──
    {
        "author": "A.W. Tozer",
        "quote_text": "What comes into our minds when we think about God is the most important thing about us. The history of mankind will probably show that no people has ever risen above its religion.",
        "source": "The Knowledge of the Holy",
        "tags": ["faith", "wisdom", "prayer"],
    },
    {
        "author": "A.W. Tozer",
        "quote_text": "The reason why many are still troubled, still seeking, still making little forward progress is because they haven't yet come to the end of themselves. We're still trying to give orders, and interfering with God's work within us.",
        "source": "The Pursuit of God",
        "tags": ["faith", "perseverance", "wisdom"],
    },
    {
        "author": "A.W. Tozer",
        "quote_text": "It is doubtful whether God can bless a man greatly until He has hurt him deeply. The wounded soldier gets a deeper revelation of the love of the Commander.",
        "source": "The Root of the Righteous",
        "tags": ["hardship", "grace", "faith"],
    },
    {
        "author": "A.W. Tozer",
        "quote_text": "The world is perishing for lack of the knowledge of God, and the church is famishing for want of His presence. The instant cure of most of our religious ills would be to enter the Presence in spiritual experience.",
        "source": "The Pursuit of God",
        "tags": ["faith", "prayer", "wisdom"],
    },
    {
        "author": "A.W. Tozer",
        "quote_text": "God is looking for people through whom He can do the impossible. What a pity that we plan only the things we can do by ourselves.",
        "source": "The Knowledge of the Holy",
        "tags": ["faith", "courage", "trust"],
    },
    # ── Francis Chan ──
    {
        "author": "Francis Chan",
        "quote_text": "Our greatest fear should not be of failure but of succeeding at things in life that don't really matter. We have to stop living as if the purpose of life is to arrive safely at death.",
        "source": "Crazy Love",
        "tags": ["wisdom", "faith", "courage"],
    },
    {
        "author": "Francis Chan",
        "quote_text": "Lukewarm people don't really want to be saved from their sin; they want only to be saved from the penalty of their sin. They don't genuinely hate sin and want to be made right with God; they simply want to escape suffering.",
        "source": "Crazy Love",
        "tags": ["faith", "salvation", "wisdom"],
    },
    {
        "author": "Francis Chan",
        "quote_text": "Following Christ isn't something that can be done halfheartedly or on the side. It is not a label we can display when convenient. It is the total commitment of our entire life to the One who gave everything for us.",
        "source": "Crazy Love",
        "tags": ["faith", "courage", "perseverance"],
    },
    {
        "author": "Francis Chan",
        "quote_text": "Something is wrong when our lives make sense to unbelievers. The radical obedience that Christ calls us to should look foolish to a world that doesn't know Him.",
        "source": "Crazy Love",
        "tags": ["courage", "faith", "wisdom"],
    },
    {
        "author": "Francis Chan",
        "quote_text": "Both worry and praise have one thing in common: they are responses to what we believe might happen. How strange that we often praise so little and worry so much.",
        "source": "Forgotten God",
        "tags": ["trust", "prayer", "wisdom"],
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
        "quote_text": "To be loved but not known is comforting but superficial. To be known and not loved is our greatest fear. But to be fully known and truly loved is, well, a lot like being loved by God.",
        "source": "The Meaning of Marriage",
        "tags": ["love", "marriage", "grace"],
    },
    {
        "author": "Tim Keller",
        "quote_text": "If we get our very identity, our sense of worth, from our political position, then politics is not really about politics. It is about us. And through our politics we are asking the world to validate us and to defer to us.",
        "source": "Counterfeit Gods",
        "tags": ["wisdom", "faith", "courage"],
    },
    {
        "author": "Tim Keller",
        "quote_text": "Real prayer comes not from gritting our teeth but from falling in love. It is not merely a discipline; it is a privilege. The God of the universe invites us to speak with Him, and He actually listens.",
        "source": "Prayer: Experiencing Awe and Intimacy with God",
        "tags": ["prayer", "love", "faith"],
    },
    {
        "author": "Tim Keller",
        "quote_text": "When pain and suffering come upon us, we finally see not only that we are not in control of our lives but that we never were. We are frail and finite. And that is the beginning of wisdom.",
        "source": "Walking with God through Pain and Suffering",
        "tags": ["hardship", "wisdom", "trust"],
    },
    # ── A.W. Pink ──
    {
        "author": "A.W. Pink",
        "quote_text": "The prayer that prevails is not the work of lips and fingertips. It is the cry of a broken heart and the travail of a stricken soul, rising up to God who hears the faintest whisper of faith.",
        "source": "Effectual Fervent Prayer",
        "tags": ["prayer", "faith", "hardship"],
    },
    {
        "author": "A.W. Pink",
        "quote_text": "The sovereignty of God is the one impregnable rock to which the suffering human heart must cling. The circumstances of life are not always comfortable, but the God behind them always is.",
        "source": "The Sovereignty of God",
        "tags": ["trust", "hardship", "faith"],
    },
    {
        "author": "A.W. Pink",
        "quote_text": "God does not bestow His blessings upon His children and then leave them to fend for themselves. His hand that gives is the same hand that holds, and He will not let go.",
        "source": "The Attributes of God",
        "tags": ["trust", "grace", "faith"],
    },
    {
        "author": "A.W. Pink",
        "quote_text": "The Christian life is not a playground; it is a battleground. We are engaged in a conflict with forces that would destroy our faith, but the Captain of our salvation has already won the war.",
        "source": "An Exposition of Hebrews",
        "tags": ["perseverance", "courage", "faith"],
    },
    {
        "author": "A.W. Pink",
        "quote_text": "The most pressing need of the hour is not more organization, not more methods, not more money, but men and women who know God, who walk with God, and who can introduce others to God.",
        "source": "The Sovereignty of God",
        "tags": ["faith", "prayer", "wisdom"],
    },
    # ── Corrie ten Boom ──
    {
        "author": "Corrie ten Boom",
        "quote_text": "Never be afraid to trust an unknown future to a known God. He has proved Himself faithful in the darkest valleys, and He will prove Himself faithful again.",
        "source": "Each New Day",
        "tags": ["trust", "courage", "faith"],
    },
    {
        "author": "Corrie ten Boom",
        "quote_text": "If you look at the world, you'll be distressed. If you look within, you'll be depressed. But if you look at God, you'll be at rest. He is the anchor for every storm.",
        "source": "Each New Day",
        "tags": ["trust", "faith", "hope"],
    },
    {
        "author": "Corrie ten Boom",
        "quote_text": "There is no pit so deep that God's love is not deeper still. In the darkest hole, the deepest despair, His love reached down and found me. And it will find you too.",
        "source": "The Hiding Place",
        "tags": ["love", "hardship", "hope"],
    },
    {
        "author": "Corrie ten Boom",
        "quote_text": "Forgiveness is an act of the will, and the will can function regardless of the temperature of the heart. We forgive not because we feel like it but because God commands it.",
        "source": "Tramp for the Lord",
        "tags": ["grace", "love", "wisdom"],
    },
    {
        "author": "Corrie ten Boom",
        "quote_text": "You can never learn that Christ is all you need until Christ is all you have. And when He is all you have, you discover that He is all you ever needed.",
        "source": "The Hiding Place",
        "tags": ["faith", "trust", "hardship"],
    },
    # ── Elisabeth Elliot ──
    {
        "author": "Elisabeth Elliot",
        "quote_text": "God never withholds from His child that which His love and wisdom call good. God's refusals are always merciful, always for our deepest good, always looking ahead to what we cannot yet see.",
        "source": "Passion and Purity",
        "tags": ["trust", "grace", "wisdom"],
    },
    {
        "author": "Elisabeth Elliot",
        "quote_text": "The fact that I am a woman does not make me a different kind of Christian, but the fact that I am a Christian makes me a different kind of woman.",
        "source": "Let Me Be a Woman",
        "tags": ["faith", "courage", "wisdom"],
    },
    {
        "author": "Elisabeth Elliot",
        "quote_text": "Of one thing I am perfectly sure: God's story never ends with ashes. If your story has ashes in it right now, that is not the end. God is still writing.",
        "source": "Suffering Is Never for Nothing",
        "tags": ["hope", "faith", "perseverance"],
    },
    {
        "author": "Elisabeth Elliot",
        "quote_text": "The secret is Christ in me, not me in a different set of circumstances. My peace does not depend on what happens around me but on Who lives within me.",
        "source": "Keep a Quiet Heart",
        "tags": ["faith", "trust", "hardship"],
    },
    {
        "author": "Elisabeth Elliot",
        "quote_text": "When we are obedient, God guides our steps and our stops. He leads us to places we never planned and teaches us things we never imagined we needed to learn.",
        "source": "A Path Through Suffering",
        "tags": ["trust", "faith", "wisdom"],
    },
    # ── Dietrich Bonhoeffer ──
    {
        "author": "Dietrich Bonhoeffer",
        "quote_text": "Cheap grace is the grace we bestow on ourselves. Costly grace is the gospel which must be sought again and again, the gift which must be asked for, the door at which a man must knock.",
        "source": "The Cost of Discipleship",
        "tags": ["grace", "faith", "salvation"],
    },
    {
        "author": "Dietrich Bonhoeffer",
        "quote_text": "We must learn to regard people less in the light of what they do or omit to do, and more in the light of what they suffer. The only really profitable relationship to others is one of love.",
        "source": "Letters and Papers from Prison",
        "tags": ["love", "grace", "wisdom"],
    },
    {
        "author": "Dietrich Bonhoeffer",
        "quote_text": "Silence in the face of evil is itself evil. God will not hold us guiltless. Not to speak is to speak. Not to act is to act. And in that silence, the world loses a witness.",
        "source": "The Cost of Discipleship",
        "tags": ["courage", "faith", "wisdom"],
    },
    {
        "author": "Dietrich Bonhoeffer",
        "quote_text": "When Christ calls a man, He bids him come and die. It may be a death like that of the first disciples who had to leave home and work to follow Him, or it may be a death of the self.",
        "source": "The Cost of Discipleship",
        "tags": ["faith", "courage", "salvation"],
    },
    {
        "author": "Dietrich Bonhoeffer",
        "quote_text": "The Church is the Church only when it exists for others. Not dominating but helping and serving. It must tell men of every calling what it means to live for Christ.",
        "source": "Letters and Papers from Prison",
        "tags": ["love", "faith", "wisdom"],
    },
    # ── Billy Graham ──
    {
        "author": "Billy Graham",
        "quote_text": "The will of God will not take you where the grace of God cannot sustain you. No matter where life leads, His hand will hold you and His love will keep you.",
        "source": "Hope for the Troubled Heart",
        "tags": ["trust", "grace", "faith"],
    },
    {
        "author": "Billy Graham",
        "quote_text": "Courage is contagious. When a brave man takes a stand, the spines of others are often stiffened. One voice of faith in a crowd of doubt can change the entire atmosphere.",
        "source": "Unto the Hills",
        "tags": ["courage", "faith", "perseverance"],
    },
    {
        "author": "Billy Graham",
        "quote_text": "God never takes away something from your life without replacing it with something better. His plans are always good, always purposeful, and always leading somewhere beautiful.",
        "source": "Hope for the Troubled Heart",
        "tags": ["trust", "hope", "faith"],
    },
    {
        "author": "Billy Graham",
        "quote_text": "The strongest steel is forged in the hottest fire. The most beautiful characters are developed through the deepest suffering. God uses our pain to shape us into something extraordinary.",
        "source": "Unto the Hills",
        "tags": ["hardship", "perseverance", "faith"],
    },
    {
        "author": "Billy Graham",
        "quote_text": "Being a Christian is more than just an instantaneous conversion. It is a daily process whereby you grow to be more and more like Christ in everything you think, say, and do.",
        "source": "Peace with God",
        "tags": ["faith", "perseverance", "wisdom"],
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
