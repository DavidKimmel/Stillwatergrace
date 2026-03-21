"""Remotion renderer bridge — builds props and calls npx remotion render."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REMOTION_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent / "rendering" / "remotion"
PUBLIC_DIR = REMOTION_PROJECT_DIR / "public"
FPS = 30


def build_render_props(
    image_path: str,
    audio_path: str,
    words: list[dict[str, Any]],
    verse_reference: str,
    duration_seconds: float,
    verse_text: str = "",
) -> dict[str, Any]:
    """Build the props dict that Remotion will receive."""
    return {
        "imageSrc": Path(image_path).name,
        "audioSrc": Path(audio_path).name,
        "words": words,
        "verseReference": verse_reference,
        "verseText": verse_text,
        "durationInSeconds": duration_seconds,
    }


def render_devotional_reel(
    image_path: str,
    audio_path: str,
    words: list[dict[str, Any]],
    verse_reference: str,
    duration_seconds: float,
    output_path: str,
    verse_text: str = "",
) -> str | None:
    """Render a devotional reel using Remotion.

    Args:
        image_path: Path to the background Unsplash image.
        audio_path: Path to the pre-mixed audio file (narration + music).
        words: Word-level timestamps from ElevenLabs.
        verse_reference: e.g., "Psalm 46:10 NIV"
        duration_seconds: Total reel duration.
        output_path: Where to save the rendered MP4.
        verse_text: The full verse text to display on screen.

    Returns:
        The output path on success, None on failure.
    """
    try:
        PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

        # Copy assets to Remotion public directory
        shutil.copy2(image_path, PUBLIC_DIR / Path(image_path).name)
        shutil.copy2(audio_path, PUBLIC_DIR / Path(audio_path).name)

        # Build and write props
        props = build_render_props(
            image_path=image_path,
            audio_path=audio_path,
            words=words,
            verse_reference=verse_reference,
            duration_seconds=duration_seconds,
            verse_text=verse_text,
        )
        props_file = REMOTION_PROJECT_DIR / "render-props.json"
        props_file.write_text(json.dumps(props, indent=2))

        # Calculate frame count
        total_frames = int(duration_seconds * FPS)

        # Call Remotion render (v4 requires entry point as first positional arg)
        cmd = [
            "npx", "remotion", "render",
            "src/Root.tsx",
            "DevotionalReel",
            output_path,
            "--props", str(props_file),
            "--frames", f"0-{total_frames - 1}",
            "--codec", "h264",
            "--image-format", "jpeg",
            "--log", "error",
        ]

        logger.info(
            "Rendering reel: %s (%.1fs, %d frames)",
            verse_reference,
            duration_seconds,
            total_frames,
        )

        result = subprocess.run(
            cmd,
            cwd=str(REMOTION_PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.error("Remotion render failed: %s", result.stderr)
            return None

        logger.info("Reel rendered successfully: %s", output_path)
        return output_path

    except subprocess.TimeoutExpired:
        logger.error("Remotion render timed out after 300s")
        return None
    except Exception as e:
        logger.error("Render error: %s", e)
        return None
    finally:
        # Clean up public assets
        for f in [Path(image_path).name, Path(audio_path).name]:
            (PUBLIC_DIR / f).unlink(missing_ok=True)
