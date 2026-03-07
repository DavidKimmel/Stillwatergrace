from core.devotional.themes import get_theme, list_themes, DevotionalTheme
import pytest


def test_get_theme_returns_theme():
    theme = get_theme("finding_peace")
    assert isinstance(theme, DevotionalTheme)
    assert theme.title == "Finding Peace in Every Season"
    assert len(theme.days) == 7
    assert theme.days[0].verse_ref
    assert theme.days[0].mood_keywords


def test_get_theme_unknown_raises():
    with pytest.raises(KeyError):
        get_theme("nonexistent_theme")


def test_list_themes():
    themes = list_themes()
    assert "finding_peace" in themes
    assert len(themes) >= 1
