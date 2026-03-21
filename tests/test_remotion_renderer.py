"""Tests for the Remotion renderer bridge."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.rendering.remotion_renderer import (
    build_render_props,
    REMOTION_PROJECT_DIR,
)


class TestBuildRenderProps:
    def test_builds_valid_props(self):
        words = [
            {"word": "Be", "start": 0.0, "end": 0.3},
            {"word": "still", "start": 0.3, "end": 0.7},
        ]
        props = build_render_props(
            image_path="/tmp/bg.jpg",
            audio_path="/tmp/mixed.mp3",
            words=words,
            verse_reference="Psalm 46:10 NIV",
            duration_seconds=15.0,
        )
        assert props["imageSrc"] == "bg.jpg"
        assert props["audioSrc"] == "mixed.mp3"
        assert props["words"] == words
        assert props["verseReference"] == "Psalm 46:10 NIV"
        assert props["verseText"] == ""
        assert props["durationInSeconds"] == 15.0

    def test_duration_rounds_up(self):
        props = build_render_props(
            image_path="/tmp/bg.jpg",
            audio_path="/tmp/mixed.mp3",
            words=[],
            verse_reference="Gen 1:1",
            duration_seconds=15.3,
        )
        assert props["durationInSeconds"] == 15.3

    def test_remotion_project_dir_exists(self):
        assert REMOTION_PROJECT_DIR.name == "remotion"
