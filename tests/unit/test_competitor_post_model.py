from database.models import CompetitorPost
from datetime import datetime

def test_competitor_post_creation():
    post = CompetitorPost(
        competitor_handle="biblesociety",
        platform_media_id="17890012345678",
        media_type="VIDEO",
        caption="Trust in the Lord #faith",
        hashtags=["faith", "bible"],
        posted_at=datetime(2026, 3, 7, 12, 0),
        permalink="https://www.instagram.com/p/abc123/",
    )
    assert post.competitor_handle == "biblesociety"
    assert post.media_type == "VIDEO"
    assert post.hashtags == ["faith", "bible"]

def test_competitor_post_defaults():
    post = CompetitorPost(
        competitor_handle="test",
        platform_media_id="123",
        media_type="IMAGE",
    )
    assert post.caption is None
    assert post.permalink is None
