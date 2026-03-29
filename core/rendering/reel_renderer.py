"""Branded reel video renderer.

Generates 9:16 (1080x1920) MP4 reels from HTML templates + TTS narration.

Three visual styles, matched to content type:
  - scripture: Green hook → verse with highlights → cream reflection → CTA
  - bold:      Cream statement → gold accent frame → green CTA (punchy, minimal)
  - story:     Cream hook → green narrative → green verse → green CTA (devotional)

Pipeline:
  1. Render branded frame PNGs via Playwright
  2. Generate TTS narration + background music via ElevenLabs
  3. Composite frames + audio into MP4 via FFmpeg concat demuxer
"""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from core.rendering.html_renderer import render_html_to_image, apply_highlights

logger = logging.getLogger(__name__)

# ── Style routing: content type → reel visual style ──
STYLE_MAP: dict[str, str] = {
    # Scripture style — verse-focused, green bg
    "daily_verse": "scripture",
    "daily_devotional": "scripture",
    "prayer_prompt": "scripture",
    "gratitude": "scripture",
    # Bold style — punchy, cream bg, big text
    "conviction_quote": "bold",
    "fill_in_blank": "bold",
    "this_or_that": "bold",
    "christian_quote": "bold",
    "marriage_challenge": "bold",
    "parenting_list": "bold",
    # Story style — narrative arc, devotional pace
    "faith_friday": "story",
    "encouragement": "story",
    "marriage_monday": "story",
    "parenting_wednesday": "story",
}

# Default CTA lines per style
CTA_OPTIONS: dict[str, list[str]] = {
    "scripture": [
        "Save this for when you need it",
        "Share this with someone today",
        "Let this truth settle in your heart",
    ],
    "bold": [
        "Type AMEN if you believe this",
        "Double tap if this hit home",
        "Tag someone who needs this",
    ],
    "story": [
        "Save this for when you need it",
        "Share with someone going through it",
        "Follow for daily encouragement",
    ],
}

# Frame timing defaults (seconds)
HOOK_DURATION = 3.0
REFLECTION_DURATION = 3.0
CTA_DURATION = 2.5
NARRATIVE_DURATION = 5.0
MIN_VERSE_DURATION = 5.0
BOLD_STATEMENT_DURATION = 5.0


def get_reel_style(content_type: str) -> str:
    """Get the reel visual style for a content type."""
    return STYLE_MAP.get(content_type, "scripture")


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
        return 15.0


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
    style: Optional[str] = None,
    narrative_text: Optional[str] = None,
) -> Optional[str]:
    """Render a branded reel video from HTML templates + audio.

    Args:
        hook_text: Bold opening line (max ~10 words).
        verse_text: Full verse text.
        verse_reference: e.g. "Philippians 4:6-7 NIV".
        highlights: Phrases to highlight in the verse.
        reflection_text: Brief application/reflection line.
        content_id: Content ID for file naming and audio lookup.
        narration_path: Path to pre-generated narration MP3.
        music_mood: Content type for mood-matched music selection.
        cta_text: Custom CTA text. If None, picks from style defaults.
        style: Reel style override. If None, derived from music_mood.
        narrative_text: Longer narrative for story-style reels. Falls
            back to reflection_text if not provided.

    Returns:
        Path to the rendered MP4 file, or None on failure.
    """
    if not shutil.which("ffmpeg"):
        logger.error("FFmpeg not found — cannot render reel video")
        return None

    import random

    if not style:
        style = get_reel_style(music_mood)

    if not cta_text:
        cta_text = random.choice(CTA_OPTIONS.get(style, CTA_OPTIONS["scripture"]))

    if not narrative_text:
        narrative_text = reflection_text

    output_dir = Path(__file__).resolve().parent.parent.parent / "output" / "reels"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"reel_{content_id}.mp4"

    logger.info(f"Rendering reel #{content_id} with style '{style}'")

    # ── Step 1: Generate or locate audio ──
    audio_path = _prepare_audio(
        verse_text=verse_text,
        verse_reference=verse_reference,
        content_id=content_id,
        narration_path=narration_path,
        music_mood=music_mood,
    )

    if audio_path:
        audio_duration = _get_audio_duration(audio_path)
        total_duration = max(audio_duration, 12.0)
    else:
        total_duration = 15.0
        logger.warning(f"No audio for reel #{content_id}, using {total_duration}s silent")

    # ── Step 2: Render frames + calculate durations per style ──
    with tempfile.TemporaryDirectory() as tmpdir:
        if style == "bold":
            frames, durations = _render_bold_frames(
                tmpdir, hook_text, verse_text, cta_text,
                content_id, total_duration,
            )
        elif style == "story":
            frames, durations = _render_story_frames(
                tmpdir, hook_text, narrative_text, verse_text,
                verse_reference, highlights, cta_text,
                content_id, total_duration,
            )
        else:  # scripture (default)
            frames, durations = _render_scripture_frames(
                tmpdir, hook_text, verse_text, verse_reference,
                highlights, reflection_text, cta_text,
                content_id, total_duration,
            )

        if len(frames) < 2:
            logger.error(f"Only rendered {len(frames)} frames for reel #{content_id}")
            return None

        total_duration = sum(durations)

        # ── Step 3: Composite video via FFmpeg ──
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
                f"style={style}, {total_duration:.1f}s, {output_path}"
            )
            return str(output_path)

    return None


# ── Style-specific frame renderers ──

def _render_scripture_frames(
    tmpdir: str, hook_text: str, verse_text: str, verse_reference: str,
    highlights: list[str], reflection_text: str, cta_text: str,
    content_id: int, total_duration: float,
) -> tuple[list[str], list[float]]:
    """Style 1: Scripture — green hook → verse → cream reflection → CTA."""
    verse_html = apply_highlights(verse_text, highlights)

    frame_specs = [
        ("reel_hook.html", {"hook_text": hook_text}),
        ("reel_verse.html", {"verse_html": verse_html, "verse_reference": verse_reference}),
        ("reel_reflection.html", {"reflection_text": reflection_text}),
        ("reel_cta.html", {"cta_text": cta_text}),
    ]

    frames = _render_frame_list(frame_specs, tmpdir, content_id)

    verse_dur = max(
        MIN_VERSE_DURATION,
        total_duration - HOOK_DURATION - REFLECTION_DURATION - CTA_DURATION,
    )
    durations = [HOOK_DURATION, verse_dur, REFLECTION_DURATION, CTA_DURATION]
    return frames, durations


def _render_bold_frames(
    tmpdir: str, hook_text: str, statement_text: str, cta_text: str,
    content_id: int, total_duration: float,
) -> tuple[list[str], list[float]]:
    """Style 2: Bold Statement — cream statement → green accent → CTA.

    Only 3 frames. Statement is the hero — big, punchy, lots of whitespace.
    """
    frame_specs = [
        ("reel_bold_statement.html", {"statement_text": hook_text, "sub_text": ""}),
        ("reel_bold_statement.html", {"statement_text": statement_text, "sub_text": ""}),
        ("reel_bold_cta.html", {"cta_text": cta_text}),
    ]

    frames = _render_frame_list(frame_specs, tmpdir, content_id)

    statement_dur = max(
        BOLD_STATEMENT_DURATION,
        total_duration - HOOK_DURATION - CTA_DURATION,
    )
    durations = [HOOK_DURATION, statement_dur, CTA_DURATION]
    return frames, durations


def _render_story_frames(
    tmpdir: str, hook_text: str, narrative_text: str, verse_text: str,
    verse_reference: str, highlights: list[str], cta_text: str,
    content_id: int, total_duration: float,
) -> tuple[list[str], list[float]]:
    """Style 3: Story — cream hook → green narrative → green verse → CTA.

    Four frames with a narrative arc: hook the viewer, tell the story,
    anchor with scripture, close with CTA.
    """
    verse_html = apply_highlights(verse_text, highlights)

    frame_specs = [
        ("reel_story_hook.html", {"hook_text": hook_text}),
        ("reel_story_narrative.html", {"narrative_text": narrative_text}),
        ("reel_story_verse.html", {"verse_html": verse_html, "verse_reference": verse_reference}),
        ("reel_cta.html", {"cta_text": cta_text}),
    ]

    frames = _render_frame_list(frame_specs, tmpdir, content_id)

    verse_dur = max(
        MIN_VERSE_DURATION,
        total_duration - HOOK_DURATION - NARRATIVE_DURATION - CTA_DURATION,
    )
    durations = [HOOK_DURATION, NARRATIVE_DURATION, verse_dur, CTA_DURATION]
    return frames, durations


def _render_frame_list(
    frame_specs: list[tuple[str, dict]],
    tmpdir: str,
    content_id: int,
) -> list[str]:
    """Render a list of (template, variables) to PNG files."""
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


# ── Audio preparation ──

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

    delayed_path = _delay_narration(narr_path, content_id)
    if not delayed_path:
        return None

    delayed_duration = _get_audio_duration(delayed_path)
    target_duration = delayed_duration + REFLECTION_DURATION + CTA_DURATION

    mixed = premix_audio(
        narration_path=delayed_path,
        music_mood=music_mood,
        duration_seconds=target_duration,
        content_id=content_id,
    )
    return mixed


def _delay_narration(narration_path: str, content_id: int) -> Optional[str]:
    """Prepend silence equal to HOOK_DURATION before narration."""
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


# ── Video composition ──

def _compose_video(
    frame_paths: list[str],
    frame_durations: list[float],
    audio_path: Optional[str],
    output_path: str,
    total_duration: float,
) -> bool:
    """Compose frame images + audio into an MP4 using FFmpeg concat demuxer."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as concat_file:
        for frame_path, duration in zip(frame_paths, frame_durations):
            concat_file.write(f"file '{frame_path}'\n")
            concat_file.write(f"duration {duration}\n")
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
            cmd.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])
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
