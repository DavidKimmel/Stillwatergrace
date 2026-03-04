"""Tests for the Bible API client."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from core.scraper.bible_api import BibleAPIClient, VERSE_POOL


class TestBibleAPIClient:
    """Tests for BibleAPIClient."""

    def setup_method(self):
        self.db = MagicMock()

    def test_parse_reference_simple(self):
        """Test parsing a simple verse reference."""
        book, chapter, start, end = BibleAPIClient._parse_reference("John 3:16")
        assert book == "John"
        assert chapter == 3
        assert start == 16
        assert end is None

    def test_parse_reference_range(self):
        """Test parsing a verse range."""
        book, chapter, start, end = BibleAPIClient._parse_reference("Psalm 23:1-6")
        assert book == "Psalm"
        assert chapter == 23
        assert start == 1
        assert end == 6

    def test_parse_reference_numbered_book(self):
        """Test parsing a numbered book reference."""
        book, chapter, start, end = BibleAPIClient._parse_reference("1 Corinthians 13:4-7")
        assert book == "1 Corinthians"
        assert chapter == 13
        assert start == 4
        assert end == 7

    def test_parse_reference_second_book(self):
        """Test parsing 2 Corinthians reference."""
        book, chapter, start, end = BibleAPIClient._parse_reference("2 Corinthians 5:7")
        assert book == "2 Corinthians"
        assert chapter == 5
        assert start == 7
        assert end is None

    def test_verse_pool_not_empty(self):
        """Ensure the verse pool has enough variety."""
        assert len(VERSE_POOL) >= 80
        # Check no duplicates
        assert len(VERSE_POOL) == len(set(VERSE_POOL))

    def test_verse_pool_has_variety_of_books(self):
        """Ensure the verse pool covers multiple books of the Bible."""
        books = set()
        for ref in VERSE_POOL:
            book, _, _, _ = BibleAPIClient._parse_reference(ref)
            books.add(book)
        # Should have at least 15 different books
        assert len(books) >= 15

    @patch("core.scraper.bible_api.httpx.Client")
    def test_fetch_verse_returns_cached(self, mock_client_cls):
        """Test that cached verses are returned without API call."""
        # Set up mock DB to return a cached verse
        mock_verse = MagicMock()
        mock_verse.reference = "John 3:16"
        self.db.query.return_value.filter.return_value.first.return_value = mock_verse

        client = BibleAPIClient(self.db)
        result = client.fetch_verse("John 3:16")

        assert result == mock_verse
        # Should NOT have made an HTTP request
        mock_client_cls.return_value.get.assert_not_called()

    @patch("core.scraper.bible_api.httpx.Client")
    def test_fetch_verse_from_api(self, mock_client_cls):
        """Test fetching a verse from the API when not cached."""
        # DB returns no cached verse
        self.db.query.return_value.filter.return_value.first.return_value = None

        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "reference": "John 3:16",
            "text": "For God so loved the world...",
        }
        mock_response.raise_for_status = MagicMock()
        mock_client_cls.return_value.get.return_value = mock_response

        client = BibleAPIClient(self.db)
        result = client.fetch_verse("John 3:16")

        assert result is not None
        self.db.add.assert_called_once()
        self.db.flush.assert_called_once()
