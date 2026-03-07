import os
import tempfile
from pathlib import Path

from core.devotional.pdf_renderer import DevotionalPDFRenderer


def _make_test_days():
    """Create minimal test data for 7 days."""
    return [
        {
            "day_number": i,
            "day_title": f"Day {i} Title",
            "verse_ref": f"Psalm {i}:1",
            "verse_text": f"Test verse text for day {i}.",
            "reflection": f"A reflection for day {i}. " * 20,
            "prayer": f"Lord, thank you for day {i}.",
            "questions": [f"What does day {i} mean to you?"],
            "image_path": None,
        }
        for i in range(1, 8)
    ]


def test_render_pdf_creates_file():
    days = _make_test_days()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_devotional.pdf")
        renderer = DevotionalPDFRenderer()
        result = renderer.render(
            title="Test Devotional",
            subtitle="A Test Journey",
            description="This is a test devotional.",
            days=days,
            output_path=output_path,
        )
        assert Path(result).exists()
        assert Path(result).stat().st_size > 1000


def test_render_pdf_has_correct_filename():
    days = _make_test_days()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "my_devotional.pdf")
        renderer = DevotionalPDFRenderer()
        result = renderer.render(
            title="Test",
            subtitle="Test",
            description="Test",
            days=days,
            output_path=output_path,
        )
        assert result.endswith(".pdf")
