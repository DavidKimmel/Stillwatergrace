"""Tests for the image catalog module."""

from core.images.catalog import (
    ImageCatalog,
    theme_for_content_type,
    THEME_FOLDERS,
)


def test_theme_for_content_type_known():
    assert theme_for_content_type("daily_verse") == "nature"
    assert theme_for_content_type("marriage_monday") == "people"
    assert theme_for_content_type("faith_friday") == "faith"
    assert theme_for_content_type("conviction_quote") == "dramatic"
    assert theme_for_content_type("this_or_that") == "interactive"
    assert theme_for_content_type("carousel") == "botanical"


def test_theme_for_content_type_unknown_defaults():
    assert theme_for_content_type("unknown_type") == "nature"


def test_catalog_register_and_lookup(tmp_path):
    catalog = ImageCatalog(base_dir=tmp_path)
    catalog.register(
        image_id="unsplash_abc123",
        provider="unsplash",
        theme="nature",
        filename="nature/unsplash_abc123.jpg",
        content_type="daily_verse",
        content_id=42,
        prompt_or_query="sunrise meadow",
    )

    entries = catalog.find_by_theme("nature")
    assert len(entries) == 1
    assert entries[0]["id"] == "unsplash_abc123"
    assert 42 in entries[0]["used_by"]


def test_catalog_register_reuse_tracks_content_id(tmp_path):
    catalog = ImageCatalog(base_dir=tmp_path)
    catalog.register(
        image_id="unsplash_abc123",
        provider="unsplash",
        theme="nature",
        filename="nature/unsplash_abc123.jpg",
        content_type="daily_verse",
        content_id=42,
    )
    catalog.register(
        image_id="unsplash_abc123",
        provider="unsplash",
        theme="nature",
        filename="nature/unsplash_abc123.jpg",
        content_type="encouragement",
        content_id=67,
    )

    entries = catalog.find_by_theme("nature")
    assert len(entries) == 1
    assert set(entries[0]["used_by"]) == {42, 67}


def test_catalog_find_unused(tmp_path):
    catalog = ImageCatalog(base_dir=tmp_path)
    catalog.register(
        image_id="img1", provider="unsplash", theme="nature",
        filename="nature/img1.jpg", content_type="daily_verse", content_id=1,
    )
    catalog.register(
        image_id="img2", provider="unsplash", theme="nature",
        filename="nature/img2.jpg", content_type="daily_verse",
    )

    unused = catalog.find_unused("nature")
    assert len(unused) == 1
    assert unused[0]["id"] == "img2"


def test_catalog_get_save_path(tmp_path):
    catalog = ImageCatalog(base_dir=tmp_path)
    path = catalog.get_save_path("nature", "unsplash_xyz.jpg")
    assert path == tmp_path / "raw" / "nature" / "unsplash_xyz.jpg"
    assert path.parent.exists()


def test_catalog_persists_to_disk(tmp_path):
    catalog = ImageCatalog(base_dir=tmp_path)
    catalog.register(
        image_id="img1", provider="fal", theme="faith",
        filename="faith/img1.jpg", content_type="prayer_prompt",
    )

    catalog2 = ImageCatalog(base_dir=tmp_path)
    assert len(catalog2.find_by_theme("faith")) == 1


def test_theme_dirs_created(tmp_path):
    ImageCatalog(base_dir=tmp_path)
    for theme in THEME_FOLDERS:
        assert (tmp_path / "raw" / theme).is_dir()
