"""Tests for the Christian quotes scraper and model."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from database.models import ChristianQuote
from core.scraper.quotes_scraper import (
    QuotesScraper,
    SEED_QUOTES,
    TARGET_AUTHORS,
    _compute_hash,
    _normalize_author,
)


# ──────────────────────────────────────────────
# Unit tests for helper functions
# ──────────────────────────────────────────────


class TestComputeHash:
    def test_consistent_hash(self) -> None:
        h1 = _compute_hash("Hello world")
        h2 = _compute_hash("Hello world")
        assert h1 == h2

    def test_case_insensitive(self) -> None:
        h1 = _compute_hash("Hello World")
        h2 = _compute_hash("hello world")
        assert h1 == h2

    def test_strips_whitespace(self) -> None:
        h1 = _compute_hash("  Hello  ")
        h2 = _compute_hash("Hello")
        assert h1 == h2

    def test_different_text_different_hash(self) -> None:
        h1 = _compute_hash("Quote one")
        h2 = _compute_hash("Quote two")
        assert h1 != h2

    def test_returns_64_char_hex(self) -> None:
        h = _compute_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestNormalizeAuthor:
    def test_canonical_name(self) -> None:
        assert _normalize_author("C.S. Lewis") == "C.S. Lewis"

    def test_alias(self) -> None:
        assert _normalize_author("cs lewis") == "C.S. Lewis"
        assert _normalize_author("Timothy Keller") == "Tim Keller"

    def test_case_insensitive(self) -> None:
        assert _normalize_author("BILLY GRAHAM") == "Billy Graham"
        assert _normalize_author("corrie ten boom") == "Corrie ten Boom"

    def test_unknown_author_returns_none(self) -> None:
        assert _normalize_author("Unknown Author") is None
        assert _normalize_author("") is None

    def test_all_target_authors_normalize(self) -> None:
        for author in TARGET_AUTHORS:
            result = _normalize_author(author)
            assert result == author, f"{author} should normalize to itself"


# ──────────────────────────────────────────────
# Seed data validation
# ──────────────────────────────────────────────


class TestSeedData:
    def test_minimum_quote_count(self) -> None:
        assert len(SEED_QUOTES) >= 50

    def test_all_authors_represented(self) -> None:
        seed_authors = {q["author"] for q in SEED_QUOTES}
        for author in TARGET_AUTHORS:
            assert author in seed_authors, f"Missing seed quotes for {author}"

    def test_minimum_per_author(self) -> None:
        from collections import Counter
        counts = Counter(q["author"] for q in SEED_QUOTES)
        for author in TARGET_AUTHORS:
            assert counts[author] >= 5, f"{author} has only {counts[author]} quotes (need 5+)"

    def test_all_quotes_have_required_fields(self) -> None:
        for i, q in enumerate(SEED_QUOTES):
            assert q.get("author"), f"Quote {i} missing author"
            assert q.get("quote_text"), f"Quote {i} missing quote_text"
            assert isinstance(q.get("tags"), list), f"Quote {i} tags should be a list"
            assert len(q["tags"]) > 0, f"Quote {i} has no tags"

    def test_no_duplicate_quotes_in_seed(self) -> None:
        hashes = [_compute_hash(q["quote_text"]) for q in SEED_QUOTES]
        assert len(hashes) == len(set(hashes)), "Duplicate quotes found in seed data"

    def test_tags_are_valid(self) -> None:
        valid_tags = {
            "faith", "hope", "love", "prayer", "hardship", "marriage",
            "family", "courage", "wisdom", "grace", "salvation", "trust",
            "perseverance",
        }
        for q in SEED_QUOTES:
            for tag in q["tags"]:
                assert tag in valid_tags, f"Invalid tag '{tag}' in quote by {q['author']}"


# ──────────────────────────────────────────────
# Model tests
# ──────────────────────────────────────────────


class TestChristianQuoteModel:
    def test_model_creation(self) -> None:
        quote = ChristianQuote(
            author="C.S. Lewis",
            quote_text="Test quote text.",
            text_hash=_compute_hash("Test quote text."),
            source="Test Source",
            tags=["faith", "hope"],
            approved=True,
        )
        assert quote.author == "C.S. Lewis"
        assert quote.quote_text == "Test quote text."
        assert quote.approved is True
        assert quote.tags == ["faith", "hope"]

    def test_model_defaults(self) -> None:
        quote = ChristianQuote(
            author="Test",
            quote_text="Test text",
            text_hash="abc123",
        )
        assert quote.approved is None or quote.approved is True  # default in DB
        assert quote.source is None
        assert quote.scraped_from is None


# ──────────────────────────────────────────────
# Scraper tests (with mocked DB)
# ──────────────────────────────────────────────


class TestQuotesScraperSeed:
    def test_seed_inserts_all_quotes(self) -> None:
        mock_db = MagicMock()
        # No existing quotes
        mock_db.query.return_value.filter.return_value.first.return_value = None

        scraper = QuotesScraper(mock_db)
        count = scraper.seed_quotes()

        assert count == len(SEED_QUOTES)
        assert mock_db.add.call_count == len(SEED_QUOTES)

    def test_seed_skips_existing(self) -> None:
        mock_db = MagicMock()
        # All quotes already exist
        mock_db.query.return_value.filter.return_value.first.return_value = ChristianQuote(
            author="Test", quote_text="Test", text_hash="exists"
        )

        scraper = QuotesScraper(mock_db)
        count = scraper.seed_quotes()

        assert count == 0
        assert mock_db.add.call_count == 0


class TestQuotesScraperAPI:
    @patch("core.scraper.quotes_scraper.httpx.Client")
    def test_zenquotes_success(self, mock_client_cls: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"a": "C.S. Lewis", "q": "A new CS Lewis quote from the API."},
            {"a": "Unknown Person", "q": "This should be skipped."},
        ]
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        scraper = QuotesScraper(mock_db)
        count = scraper._scrape_zenquotes()

        # Only C.S. Lewis quote should be inserted (Unknown Person is not a target)
        assert count == 1

    @patch("core.scraper.quotes_scraper.httpx.Client")
    def test_api_failure_graceful(self, mock_client_cls: MagicMock) -> None:
        import httpx
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client_cls.return_value = mock_client

        mock_db = MagicMock()
        scraper = QuotesScraper(mock_db)
        count = scraper._scrape_zenquotes()

        assert count == 0  # Should not raise, just return 0


class TestQuotesScraperGetRandom:
    def test_get_random_returns_quote(self) -> None:
        expected = ChristianQuote(
            author="C.S. Lewis",
            quote_text="Test",
            text_hash="abc",
        )
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = expected

        scraper = QuotesScraper(mock_db)
        result = scraper.get_random_quote()
        assert result == expected

    def test_get_random_with_author_filter(self) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.first.return_value = None

        scraper = QuotesScraper(mock_db)
        result = scraper.get_random_quote(author="Lewis")
        assert result is None
