"""Tests for the devotional content generator."""

import json
from unittest.mock import MagicMock, patch

from core.devotional.generator import DevotionalGenerator


def _mock_claude_response(
    reflection: str, prayer: str, questions: list[str]
) -> MagicMock:
    """Create a mock Claude API response."""
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text=json.dumps(
                {
                    "reflection": reflection,
                    "prayer": prayer,
                    "questions": questions,
                }
            )
        )
    ]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)
    return mock_response


@patch("core.devotional.generator.anthropic.Anthropic")
def test_generate_day_content(mock_anthropic_cls: MagicMock) -> None:
    """Single-day generation returns reflection, prayer, and questions."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _mock_claude_response(
        reflection="God's peace is available to us...",
        prayer="Lord, help me to release my anxieties...",
        questions=["What are you anxious about today?"],
    )

    gen = DevotionalGenerator()
    result = gen.generate_day_content(
        verse_ref="Philippians 4:6-7",
        verse_text="Do not be anxious about anything...",
        day_title="Peace That Surpasses Understanding",
        reflection_focus="Trading anxiety for prayer",
        theme_title="Finding Peace in Every Season",
    )

    assert result["reflection"] == "God's peace is available to us..."
    assert result["prayer"] == "Lord, help me to release my anxieties..."
    assert len(result["questions"]) >= 1
    mock_client.messages.create.assert_called_once()


@patch("core.devotional.generator.anthropic.Anthropic")
def test_generate_day_content_strips_markdown_fences(
    mock_anthropic_cls: MagicMock,
) -> None:
    """Generator strips markdown code fences from Claude response."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    fenced_json = (
        '```json\n{"reflection": "Test", "prayer": "Amen", "questions": ["Q?"]}\n```'
    )
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=fenced_json)]
    mock_response.usage = MagicMock(input_tokens=50, output_tokens=80)
    mock_client.messages.create.return_value = mock_response

    gen = DevotionalGenerator()
    result = gen.generate_day_content(
        verse_ref="Psalm 46:10",
        verse_text="Be still and know that I am God...",
        day_title="Be Still and Know",
        reflection_focus="Stillness in a noisy world",
        theme_title="Finding Peace in Every Season",
        day_number=2,
    )

    assert result["reflection"] == "Test"
    assert result["prayer"] == "Amen"
    assert result["questions"] == ["Q?"]


@patch("core.devotional.generator.anthropic.Anthropic")
def test_generate_all_days(mock_anthropic_cls: MagicMock) -> None:
    """Full theme generation returns 7 enriched day entries."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _mock_claude_response(
        reflection="A reflection...",
        prayer="A prayer...",
        questions=["A question?"],
    )

    gen = DevotionalGenerator()
    from core.devotional.themes import get_theme

    theme = get_theme("finding_peace")

    with patch.object(gen, "_fetch_verse_text", return_value="Verse text here..."):
        results = gen.generate_all_days(theme)

    assert len(results) == 7
    assert all(r["reflection"] for r in results)
    assert all(r["verse_ref"] for r in results)
    assert all(r["day_title"] for r in results)
    assert results[0]["day_number"] == 1
    assert results[6]["day_number"] == 7
    assert mock_client.messages.create.call_count == 7
