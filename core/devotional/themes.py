"""Devotional theme configurations.

Each theme defines 7 days of content: verse references, mood keywords
for Unsplash image search, and thematic context for Claude API reflections.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DayConfig:
    """Configuration for one day of a devotional."""
    day_number: int
    day_title: str
    verse_ref: str
    mood_keywords: list[str]
    reflection_focus: str  # Hint for Claude API


@dataclass(frozen=True)
class DevotionalTheme:
    """Complete theme configuration for a 7-day devotional."""
    slug: str
    title: str
    subtitle: str
    description: str  # Welcome page text
    cover_keywords: list[str]  # Unsplash search for cover image
    days: tuple[DayConfig, ...]


THEMES: dict[str, DevotionalTheme] = {
    "finding_peace": DevotionalTheme(
        slug="finding_peace",
        title="Finding Peace in Every Season",
        subtitle="A 7-Day Devotional Journey",
        description=(
            "Life moves fast. Seasons change. Uncertainty creeps in. "
            "But God's peace is not dependent on your circumstances \u2014 "
            "it is anchored in His presence. Over the next seven days, "
            "let these scriptures quiet your heart and remind you that "
            "the God of all peace is walking with you, right now, "
            "in this very season."
        ),
        cover_keywords=[
            "calm lake sunrise peaceful mountains",
            "morning mist forest serene landscape",
            "peaceful ocean sunset golden light",
        ],
        days=(
            DayConfig(
                day_number=1,
                day_title="Peace That Surpasses Understanding",
                verse_ref="Philippians 4:6-7",
                mood_keywords=["calm morning light meadow", "peaceful sunrise field"],
                reflection_focus="Trading anxiety for prayer \u2014 finding peace through surrender",
            ),
            DayConfig(
                day_number=2,
                day_title="Be Still and Know",
                verse_ref="Psalm 46:10",
                mood_keywords=["still lake reflection dawn", "quiet forest morning mist"],
                reflection_focus="The discipline of stillness in a noisy world",
            ),
            DayConfig(
                day_number=3,
                day_title="Perfect Peace",
                verse_ref="Isaiah 26:3",
                mood_keywords=["mountain summit peaceful sunrise", "calm ocean horizon"],
                reflection_focus="Keeping your mind fixed on God through trust",
            ),
            DayConfig(
                day_number=4,
                day_title="My Peace I Give You",
                verse_ref="John 14:27",
                mood_keywords=["warm sunlight through window", "gentle stream forest"],
                reflection_focus="The difference between the world's peace and Christ's peace",
            ),
            DayConfig(
                day_number=5,
                day_title="Peace in the Storm",
                verse_ref="Mark 4:39-40",
                mood_keywords=["calm after storm landscape", "rainbow clouds dramatic sky"],
                reflection_focus="Jesus calming the storm \u2014 peace is a person, not a circumstance",
            ),
            DayConfig(
                day_number=6,
                day_title="The God of Peace",
                verse_ref="Romans 15:13",
                mood_keywords=["golden hour garden flowers", "warm light peaceful garden"],
                reflection_focus="Joy, peace, and hope through the Holy Spirit",
            ),
            DayConfig(
                day_number=7,
                day_title="Rest for Your Soul",
                verse_ref="Matthew 11:28-30",
                mood_keywords=["peaceful path through forest", "quiet morning nature trail"],
                reflection_focus="Coming to Jesus with your burdens \u2014 rest as an invitation",
            ),
        ),
    ),
}


def get_theme(slug: str) -> DevotionalTheme:
    """Get a theme by slug. Raises KeyError if not found."""
    return THEMES[slug]


def list_themes() -> list[str]:
    """Return all available theme slugs."""
    return list(THEMES.keys())
