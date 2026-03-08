import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from core.scraper.competitor_content import CompetitorContentScraper, extract_hashtags


def test_extract_hashtags():
    caption = "Trust the Lord with all your heart #faith #bible #christian"
    result = extract_hashtags(caption)
    assert result == ["faith", "bible", "christian"]

def test_extract_hashtags_empty():
    assert extract_hashtags("No hashtags here") == []
    assert extract_hashtags(None) == []
    assert extract_hashtags("") == []

def test_parse_business_discovery_response():
    mock_response = {
        "business_discovery": {
            "media": {
                "data": [
                    {
                        "id": "17890012345678",
                        "caption": "Morning verse #faith #bible",
                        "media_type": "VIDEO",
                        "timestamp": "2026-03-07T12:00:00+0000",
                        "permalink": "https://www.instagram.com/p/abc123/",
                    },
                    {
                        "id": "17890012345679",
                        "caption": "Marriage tip #marriage",
                        "media_type": "CAROUSEL_ALBUM",
                        "timestamp": "2026-03-06T08:00:00+0000",
                        "permalink": "https://www.instagram.com/p/def456/",
                    },
                ]
            }
        }
    }
    db = MagicMock()
    scraper = CompetitorContentScraper(db)
    posts = scraper._parse_media_response(mock_response, "biblesociety")
    assert len(posts) == 2
    assert posts[0].competitor_handle == "biblesociety"
    assert posts[0].media_type == "VIDEO"
    assert posts[0].hashtags == ["faith", "bible"]
    assert posts[1].media_type == "CAROUSEL_ALBUM"
    assert posts[1].hashtags == ["marriage"]

def test_parse_empty_response():
    db = MagicMock()
    scraper = CompetitorContentScraper(db)
    posts = scraper._parse_media_response({}, "test")
    assert posts == []

def test_get_format_distribution():
    db = MagicMock()
    scraper = CompetitorContentScraper(db)
    posts = [
        MagicMock(media_type="VIDEO"),
        MagicMock(media_type="VIDEO"),
        MagicMock(media_type="VIDEO"),
        MagicMock(media_type="IMAGE"),
        MagicMock(media_type="CAROUSEL_ALBUM"),
    ]
    dist = scraper.get_format_distribution(posts)
    assert dist == {"VIDEO": 60.0, "IMAGE": 20.0, "CAROUSEL_ALBUM": 20.0}

def test_get_format_distribution_empty():
    db = MagicMock()
    scraper = CompetitorContentScraper(db)
    assert scraper.get_format_distribution([]) == {}
