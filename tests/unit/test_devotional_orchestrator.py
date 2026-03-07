import sys
from unittest.mock import MagicMock, patch

# Ensure weasyprint can be imported even if not installed
if "weasyprint" not in sys.modules:
    sys.modules["weasyprint"] = MagicMock()

from core.devotional.orchestrator import DevotionalOrchestrator


@patch("core.devotional.orchestrator.DevotionalPDFRenderer")
@patch("core.devotional.orchestrator.DevotionalGenerator")
@patch("core.devotional.orchestrator.UnsplashClient")
def test_orchestrator_generates_pdf(mock_unsplash_cls, mock_gen_cls, mock_renderer_cls):
    # Mock Unsplash
    mock_unsplash = MagicMock()
    mock_unsplash_cls.return_value = mock_unsplash
    mock_unsplash.search_and_download.return_value = {
        "local_path": "/tmp/test_img.jpg"
    }

    # Mock content generator
    mock_gen = MagicMock()
    mock_gen_cls.return_value = mock_gen
    mock_gen.generate_all_days.return_value = [
        {
            "day_number": i,
            "day_title": f"Day {i}",
            "verse_ref": f"Psalm {i}:1",
            "verse_text": f"Verse {i}",
            "reflection": f"Reflection {i}",
            "prayer": f"Prayer {i}",
            "questions": [f"Question {i}?"],
        }
        for i in range(1, 8)
    ]

    # Mock renderer
    mock_renderer = MagicMock()
    mock_renderer_cls.return_value = mock_renderer
    mock_renderer.render.return_value = "/tmp/output.pdf"

    orch = DevotionalOrchestrator()
    result = orch.generate("finding_peace")

    assert result == "/tmp/output.pdf"
    mock_gen.generate_all_days.assert_called_once()
    mock_renderer.render.assert_called_once()
    # Should have fetched 8 images (1 cover + 7 days)
    assert mock_unsplash.search_and_download.call_count == 8
