"""Branded reel video renderer.

Generates 9:16 (1080x1920) MP4 reels from HTML templates + TTS narration.

Pipeline:
  1. Render 4 branded frame PNGs via Playwright (hook, verse, reflection, CTA)
  2. Generate TTS narration + background music via ElevenLabs
  3. Composite frames + audio into MP4 via FFmpeg concat demuxer
"""

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from core.rendering.html_renderer import render_html_to_image, apply_highlights

logger = logging.getLogger(__name__)

# Default CTA lines — randomly selected per reel
CTA_OPTIONS = [
    "Save this for when you need it",
    "Share this with someone today",
    "Let this truth settle in your heart",
    "Tag someone who needs to hear this",
    "Follow for daily encouragement",
]

# Frame timing defaults (seconds)
HOOK_DURATION = 3.0
REFLECTION_DURATION = 3.0
CTA_DURATION = 2.5
MIN_VERSE_DURATION = 5.0


def _get_audio_duration(audio_path: str) -> float:
    """Get duration of an audio file in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"ffprobe failed for {audio_path}: {e}")
        return 15.0  # fallback


def render_reel_video(
    hook_text: str,
    verse_text: str,
    verse_reference: str,
    highlights: list[str],
    reflection_text: str,
    content_id: int,
    narration_path: Optional[str] = None,
    music_mood: str = "daily_verse",
    cta_text: Optional[str] = None,
) -> Optional[str]:
    """Render a branded reel video from HTML templates + audio.

    Args:
        hook_text: Bold opening line (max ~10 words).
        verse_text: Full verse text.
        verse_reference: e.g. "Philippians 4:6-7 NIV".
        highlights: Phrases to highlight in the verse.
        reflection_text: Brief application/reflection line.
        content_id: Content ID for file naming and audio lookup.
        narration_path: Path to pre-generated narration MP3. If None,
            generates narration via ElevenLabs.
        music_mood: Content type for mood-matched music selection.
        cta_text: Custom CTA text. If None, picks from CTA_OPTIONS.

    Returns:
        Path to the rendered MP4 file, or None on failure.
    """
    if not shutil.which("ffmpeg"):
        logger.error("FFmpeg not found — cannot render reel video")
        return None

    import random

    if not cta_text:
        cta_text = random.choice(CTA_OPTIONS)

    output_dir = Path(__file__).resolve().parent.parent.parent / "output" / "reels"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"reel_{content_id}.mp4"

    # ── Step 1: Generate or locate audio ──
    audio_path = _prepare_audio(
        verse_text=verse_text,
        verse_reference=verse_reference,
        content_id=content_id,
        narration_path=narration_path,
        music_mood=music_mood,
    )

    if audio_path:
        # Audio already includes hook silence + narration + padding
        audio_duration = _get_audio_duration(audio_path)
        total_duration = max(audio_duration, 12.0)
    else:
        total_duration = 15.0
        logger.warning(f"No audio for reel #{content_id}, using {total_duration}s silent")

    # Calculate frame durations — verse gets whatever time remains
    verse_duration = max(
        MIN_VERSE_DURATION,
        total_duration - HOOK_DURATION - REFLECTION_DURATION - CTA_DURATION,
    )
    total_duration = HOOK_DURATION + verse_duration + REFLECTION_DURATION + CTA_DURATION

    # ── Step 2: Render frame PNGs ──
    with tempfile.TemporaryDirectory() as tmpdir:
        frames = _render_frames(
            tmpdir=tmpdir,
            hook_text=hook_text,
            verse_text=verse_text,
            verse_reference=verse_reference,
            highlights=highlights,
            reflection_text=reflection_text,
            cta_text=cta_text,
            content_id=content_id,
        )

        if len(frames) < 4:
            logger.error(f"Only rendered {len(frames)}/4 frames for reel #{content_id}")
            return None

        # ── Step 3: Composite video via FFmpeg ──
        durations = [HOOK_DURATION, verse_duration, REFLECTION_DURATION, CTA_DURATION]
        result = _compose_video(
            frame_paths=frames,
            frame_durations=durations,
            audio_path=audio_path,
            output_path=str(output_path),
            total_duration=total_duration,
        )

        if result:
            logger.info(
                f"Reel rendered for content #{content_id}: "
                f"{total_duration:.1f}s, {output_path}"
            )
            return str(output_path)

    return None


def _prepare_audio(
    verse_text: str,
    verse_reference: str,
    content_id: int,
    narration_path: Optional[str],
    music_mood: str,
) -> Optional[str]:
    """Generate narration and mix with background music.

    Narration is delayed by HOOK_DURATION so it starts when the verse
    frame appears (hook frame plays with music only).

    Returns path to the mixed audio file, or None.
    """
    from core.audio.elevenlabs_music import generate_narration, premix_audio

    # Use provided narration or generate fresh
    if narration_path and Path(narration_path).exists():
        narr_path = narration_path
    else:
        narr_result = generate_narration(
            verse_text=verse_text,
            verse_ref=verse_reference.split(" NIV")[0].split(" ESV")[0],
            content_id=content_id,
        )
        narr_path = str(narr_result) if narr_result else None

    if not narr_path:
        return None

    # Prepend silence to narration so it starts after the hook frame
    delayed_path = _delay_narration(narr_path, content_id)
    if not delayed_path:
        return None

    # Get total narration duration (including the prepended silence)
    delayed_duration = _get_audio_duration(delayed_path)
    # Total audio = delayed narration + reflection + CTA
    target_duration = delayed_duration + REFLECTION_DURATION + CTA_DURATION

    mixed = premix_audio(
        narration_path=delayed_path,
        music_mood=music_mood,
        duration_seconds=target_duration,
        content_id=content_id,
    )
    return mixed


def _delay_narration(narration_path: str, content_id: int) -> Optional[str]:
    """Prepend silence equal to HOOK_DURATION before narration.

    This ensures the voice starts when the verse frame appears,
    not during the hook title card.
    """
    output_dir = Path(__file__).resolve().parent.parent.parent / "output" / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)
    delayed_path = output_dir / f"delayed_{content_id}.mp3"

    delay_ms = int(HOOK_DURATION * 1000)

    cmd = [
        "ffmpeg", "-y",
        "-i", narration_path,
        "-af", f"adelay={delay_ms}|{delay_ms}",
        "-c:a", "libmp3lame", "-q:a", "2",
        str(delayed_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"Narration delay failed: {result.stderr[-300:]}")
            return None
        return str(delayed_path)
    except Exception as e:
        logger.error(f"Narration delay error: {e}")
        return None


def _render_frames(
    tmpdir: str,
    hook_text: str,
    verse_text: str,
    verse_reference: str,
    highlights: list[str],
    reflection_text: str,
    cta_text: str,
    content_id: int,
) -> list[str]:
    """Render the 4 reel frames as PNGs via Playwright."""
    verse_html = apply_highlights(verse_text, highlights)

    frame_specs = [
        ("reel_hook.html", {"hook_text": hook_text}),
        ("reel_verse.html", {"verse_html": verse_html, "verse_reference": verse_reference}),
        ("reel_reflection.html", {"reflection_text": reflection_text}),
        ("reel_cta.html", {"cta_text": cta_text}),
    ]

    rendered: list[str] = []
    for i, (template, variables) in enumerate(frame_specs):
        output_path = f"{tmpdir}/frame_{content_id}_{i}.png"
        result = render_html_to_image(
            template_name=template,
            variables=variables,
            output_path=output_path,
            width=1080,
            height=1920,
        )
        if result:
            rendered.append(result)
        else:
            logger.error(
                f"Failed to render reel frame {i} ({template}) for content #{content_id}"
            )

    return rendered


def _compose_video(
    frame_paths: list[str],
    frame_durations: list[float],
    audio_path: Optional[str],
    output_path: str,
    total_duration: float,
) -> bool:
    """Compose frame images + audio into an MP4 using FFmpeg concat demuxer.

    Each frame is displayed for its specified duration. Cross-fade transitions
    are not used in v1 to keep things simple and reliable.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as concat_file:
        for frame_path, duration in zip(frame_paths, frame_durations):
            # FFmpeg concat format: file + duration
            concat_file.write(f"file '{frame_path}'\n")
            concat_file.write(f"duration {duration}\n")
        # Repeat last frame to avoid black frame at end
        concat_file.write(f"file '{frame_paths[-1]}'\n")
        concat_list = concat_file.name

    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
        ]

        if audio_path:
            cmd.extend(["-i", audio_path])

        cmd.extend([
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-r", "30",
        ])

        if audio_path:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
            ])
        else:
            cmd.extend(["-an"])

        cmd.extend(["-t", str(total_duration), output_path])

        logger.info(f"Composing reel video: {len(frame_paths)} frames, {total_duration:.1f}s")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"FFmpeg reel compose failed: {result.stderr[-500:]}")
            return False

        out = Path(output_path)
        if not out.exists() or out.stat().st_size < 10_000:
            logger.error("Reel output is missing or too small")
            return False

        size_mb = out.stat().st_size / (1024 * 1024)
        logger.info(f"Reel video created: {output_path} ({size_mb:.1f} MB)")
        return True

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg reel compose timed out")
        return False
    finally:
        Path(concat_list).unlink(missing_ok=True)
