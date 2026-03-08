"""Phrase Pop reel generator — dynamic caption reels with word-synced text.

Renders reels where text appears phrase-by-phrase synced to TTS narration.
Uses FFmpeg drawtext filter with enable='between(t,start,end)' for each phrase,
overlaid on a Ken Burns zoompan background.

Pipeline:
  1. Generate TTS with timestamps via ElevenLabs
  2. Group words into 3-5 word phrases at natural breaks
  3. Render Ken Burns background (FFmpeg zoompan)
  4. Apply drawtext overlays for each phrase at exact timestamps
  5. Mix audio: narration + mood-matched music
  6. Output: 1080x1920 MP4

Output: 9:16 MP4 (1080x1920) at 30fps.
"""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image

from core.audio.timestamps import (
    Phrase,
    WordTimestamp,
    generate_narration_with_timestamps,
    group_into_phrases,
)
from core.config import settings
from core.images.image_processor import IMAGES_PROCESSED_DIR

logger = logging.getLogger(__name__)

# Reel dimensions (9:16 vertical video)
REEL_W = 1080
REEL_H = 1920
FPS = 30

# Ken Burns zoom rate per frame
ZOOM_PER_FRAME = 0.0005

# Ken Burns minimum source width
KEN_BURNS_MIN_WIDTH = 1728

# Padding before first phrase and after last phrase (seconds)
PRE_PHRASE_PAD = 0.8
POST_PHRASE_PAD = 1.5

# Font settings for drawtext
FONT_SIZE = 80
SHADOW_OFFSET = 4
SHADOW_COLOR = "black@0.6"
TEXT_COLOR = "white"

# Font file search order (Georgia Bold preferred for brand)
FONT_CANDIDATES = [
    "georgiab.ttf",
    "georgia.ttf",
    "Georgia-Bold.ttf",
    "LiberationSerif-Bold.ttf",
    "DejaVuSerif-Bold.ttf",
    "times.ttf",
    "arial.ttf",
]

# Windows and Linux font directories
_FONT_DIRS = [
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/truetype"),
    Path("/usr/share/fonts"),
]


def generate_phrase_reel(
    background_path: str,
    text: str,
    content_id: int = 0,
    voice_index: Optional[int] = None,
    content_type: str = "daily_verse",
) -> Optional[str]:
    """Generate a phrase-pop reel with word-synced captions.

    Args:
        background_path: Path to background image (will be Ken Burns animated).
        text: Text to narrate and display phrase-by-phrase.
        content_id: Content ID for voice selection, music matching, and output naming.
        voice_index: Override voice index (0-8). None uses content_id rotation.
        content_type: Content type for mood-matched music selection.

    Returns:
        Path to output MP4 file, or None on failure.
    """
    if not shutil.which("ffmpeg"):
        logger.error("FFmpeg not found -- cannot generate phrase reel")
        return None

    # Validate background image
    try:
        bg = Image.open(background_path).convert("RGB")
    except Exception as e:
        logger.error(f"Failed to open background image: {e}")
        return None

    # Normalize text whitespace
    text = " ".join(text.split())

    logger.info(f"Generating phrase-pop reel for content #{content_id}: {len(text)} chars")

    # Step 1: Generate TTS with timestamps
    tts_result = generate_narration_with_timestamps(
        text=text,
        content_id=content_id,
        voice_index=voice_index,
    )

    if tts_result is None:
        logger.error("Failed to generate timestamped narration")
        return None

    narration_path, word_timestamps = tts_result

    if not word_timestamps:
        logger.error("No word timestamps returned -- cannot sync phrases")
        return None

    # Step 2: Group into phrases
    phrases = group_into_phrases(word_timestamps)
    if not phrases:
        logger.error("No phrases generated from word timestamps")
        return None

    logger.info(f"Grouped {len(word_timestamps)} words into {len(phrases)} phrases")
    for i, phrase in enumerate(phrases):
        logger.debug(
            f"  Phrase {i}: [{phrase.start_time:.2f}-{phrase.end_time:.2f}] "
            f'"{phrase.text}"'
        )

    # Step 3: Calculate total duration
    # Duration = narration length + padding
    narration_end = phrases[-1].end_time
    total_seconds = narration_end + PRE_PHRASE_PAD + POST_PHRASE_PAD
    total_frames = int(total_seconds * FPS)

    # Get narration audio duration for more accurate timing
    narration_duration = _get_audio_duration(narration_path)
    if narration_duration and narration_duration > total_seconds:
        total_seconds = narration_duration + POST_PHRASE_PAD
        total_frames = int(total_seconds * FPS)

    logger.info(f"Reel duration: {total_seconds:.1f}s ({total_frames} frames)")

    # Step 4: Prepare background
    bg = _prepare_background(bg)

    # Step 5: Select music
    audio_track, audio_start = _select_audio_track(content_type, content_id)

    # Step 6: Build and run FFmpeg
    IMAGES_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = IMAGES_PROCESSED_DIR / f"{content_id}_phrase_reel.mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Save background for zoompan
        bg_source = tmpdir_path / "bg_source.jpg"
        bg.save(str(bg_source), "JPEG", quality=95)

        # Pass 1: Ken Burns background
        bg_motion_path = tmpdir_path / "bg_motion.mp4"
        success = _render_ken_burns_background(
            bg_source, bg_motion_path, total_frames
        )
        if not success:
            logger.error("Ken Burns background generation failed")
            return None

        # Pass 2: Composite with drawtext phrases + audio
        font_path = _find_font_path()
        success = _render_phrase_composite(
            video_path=bg_motion_path,
            output_path=output_path,
            phrases=phrases,
            phrase_offset=PRE_PHRASE_PAD,
            total_seconds=total_seconds,
            font_path=font_path,
            narration_path=narration_path,
            audio_track=audio_track,
            audio_start=audio_start,
            content_type=content_type,
            content_id=content_id,
        )

        if not success:
            logger.error("Phrase composite rendering failed")
            return None

    if output_path.exists() and output_path.stat().st_size > 10_000:
        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Phrase reel saved: {output_path} ({size_mb:.1f} MB)")
        return str(output_path)

    logger.error("Phrase reel output is missing or too small")
    return None


def _prepare_background(bg: Image.Image) -> Image.Image:
    """Resize background for Ken Burns zoompan (needs headroom for zoom)."""
    # Ken Burns needs source larger than output to zoom into
    target_w = max(KEN_BURNS_MIN_WIDTH, int(REEL_W * 1.6))
    aspect = REEL_H / REEL_W
    target_h = int(target_w * aspect)

    if bg.width < target_w or bg.height < target_h:
        bg = bg.resize((target_w, target_h), Image.LANCZOS)
    else:
        # Crop to 9:16 from center, keeping resolution
        src_aspect = bg.width / bg.height
        target_aspect = REEL_W / REEL_H
        if src_aspect > target_aspect:
            # Too wide -- crop horizontally
            new_w = int(bg.height * target_aspect)
            left = (bg.width - new_w) // 2
            bg = bg.crop((left, 0, left + new_w, bg.height))
        else:
            # Too tall -- crop vertically
            new_h = int(bg.width / target_aspect)
            top = (bg.height - new_h) // 2
            bg = bg.crop((0, top, bg.width, top + new_h))

        # Ensure minimum size for zoompan
        if bg.width < target_w:
            scale = target_w / bg.width
            bg = bg.resize(
                (int(bg.width * scale), int(bg.height * scale)),
                Image.LANCZOS,
            )

    return bg


def _render_ken_burns_background(
    bg_source: Path,
    output_path: Path,
    total_frames: int,
) -> bool:
    """Render Ken Burns zoompan background video."""
    max_zoom = 1.0 + ZOOM_PER_FRAME * total_frames

    zoompan_filter = (
        f"zoompan="
        f"z='min(zoom+{ZOOM_PER_FRAME},{max_zoom:.4f})':"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"d={total_frames}:"
        f"s={REEL_W}x{REEL_H}:"
        f"fps={FPS}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(bg_source),
        "-vf", zoompan_filter,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "medium",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            logger.error(f"Ken Burns zoompan failed: {result.stderr[-300:]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("Ken Burns zoompan timed out")
        return False
    except Exception as e:
        logger.error(f"Ken Burns error: {e}")
        return False


def _render_phrase_composite(
    video_path: Path,
    output_path: Path,
    phrases: list[Phrase],
    phrase_offset: float,
    total_seconds: float,
    font_path: Optional[str],
    narration_path: Optional[Path],
    audio_track: Optional[Path],
    audio_start: float,
    content_type: str,
    content_id: int,
) -> bool:
    """Render final video with drawtext phrase overlays and audio mix.

    Uses FFmpeg drawtext filter with enable='between(t,start,end)' for each
    phrase. Each phrase gets:
      - Large white text centered on screen
      - Drop shadow for readability
      - Slight dark overlay behind text area
    """
    music_fade_start = max(0, total_seconds - 2.5)
    narr_fade_start = max(0, total_seconds - 0.5)
    has_narration = narration_path is not None and narration_path.exists()
    has_music = audio_track is not None

    # Select ambient sound
    ambient_path = _select_ambient_sound(content_type, content_id)
    has_ambient = ambient_path is not None

    cmd = ["ffmpeg", "-y"]

    # Input 0: Ken Burns background video
    cmd += ["-i", str(video_path)]

    input_idx = 1

    # Audio inputs
    narr_idx = -1
    music_idx = -1
    ambient_idx = -1

    if has_narration:
        cmd += ["-i", str(narration_path)]
        narr_idx = input_idx
        input_idx += 1

    if has_music:
        cmd += ["-ss", str(audio_start), "-i", str(audio_track)]
        music_idx = input_idx
        input_idx += 1

    if has_ambient:
        cmd += ["-stream_loop", "-1", "-i", str(ambient_path)]
        ambient_idx = input_idx

    # Build video filter: dark overlay + drawtext per phrase
    video_filters = _build_drawtext_filters(
        phrases=phrases,
        phrase_offset=phrase_offset,
        font_path=font_path,
    )

    # Build audio filters
    audio_filters, audio_map = _build_audio_filters(
        has_narration=has_narration,
        has_music=has_music,
        has_ambient=has_ambient,
        narr_idx=narr_idx,
        music_idx=music_idx,
        ambient_idx=ambient_idx,
        narr_fade_start=narr_fade_start,
        music_fade_start=music_fade_start,
    )

    # Combine all filters
    all_filters = video_filters + audio_filters
    if all_filters:
        cmd += ["-filter_complex", ";".join(all_filters)]

    # Map video output
    if video_filters:
        cmd += ["-map", "[vout]"]
    else:
        cmd += ["-map", "0:v"]

    # Map audio output
    if audio_map:
        cmd += ["-map", audio_map]
        cmd += ["-c:a", "aac", "-b:a", "128k"]

    cmd += [
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        "-preset", "medium",
        "-movflags", "+faststart",
        "-t", str(total_seconds),
        str(output_path),
    ]

    logger.debug(f"FFmpeg phrase composite command: {' '.join(str(c) for c in cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            logger.error(f"FFmpeg phrase composite failed: {result.stderr[-500:]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg phrase composite timed out")
        return False
    except Exception as e:
        logger.error(f"FFmpeg phrase composite error: {e}")
        return False


def _build_drawtext_filters(
    phrases: list[Phrase],
    phrase_offset: float,
    font_path: Optional[str],
) -> list[str]:
    """Build FFmpeg drawtext filter chain for phrase-by-phrase display.

    Each phrase gets two drawtext filters (shadow + text) with
    enable='between(t,start,end)' for timing.

    Returns list of filter strings to join with ';'.
    """
    if not phrases:
        return []

    # Semi-transparent dark band behind text for readability
    # Covers middle third of screen
    band_y = REEL_H // 3
    band_h = REEL_H // 3
    base_filter = (
        f"[0:v]drawbox=x=0:y={band_y}:w={REEL_W}:h={band_h}:"
        f"color=black@0.35:t=fill"
    )

    # Font file argument (if found)
    font_arg = f":fontfile='{font_path}'" if font_path else ""

    # Chain drawtext filters for each phrase
    prev_label = ""
    filters: list[str] = []

    for i, phrase in enumerate(phrases):
        start = phrase.start_time + phrase_offset
        end = phrase.end_time + phrase_offset

        # Add small gap between phrases for visual breathing room
        # Fade: show 0.1s before start_time, hold until end_time + 0.15s
        display_start = max(0, start - 0.1)
        display_end = end + 0.15

        escaped_text = _escape_drawtext(phrase.text)

        # Shadow drawtext
        shadow_filter = (
            f"drawtext=text='{escaped_text}'"
            f"{font_arg}"
            f":fontsize={FONT_SIZE}"
            f":fontcolor={SHADOW_COLOR}"
            f":x=(w-text_w)/2+{SHADOW_OFFSET}"
            f":y=(h-text_h)/2+{SHADOW_OFFSET}"
            f":enable='between(t,{display_start:.3f},{display_end:.3f})'"
        )

        # Main text drawtext
        text_filter = (
            f"drawtext=text='{escaped_text}'"
            f"{font_arg}"
            f":fontsize={FONT_SIZE}"
            f":fontcolor={TEXT_COLOR}"
            f":borderw=2:bordercolor=black@0.3"
            f":x=(w-text_w)/2"
            f":y=(h-text_h)/2"
            f":enable='between(t,{display_start:.3f},{display_end:.3f})'"
        )

        if i == 0:
            # First phrase: chain from base (drawbox)
            filters.append(f"{base_filter},{shadow_filter},{text_filter}")
            prev_label = ""
        else:
            # Subsequent phrases: chain from previous output
            in_label = f"[dt{i - 1}]"
            filters_text = f"{in_label}{shadow_filter},{text_filter}"
            filters.append(filters_text)

        # Label output for next filter (except last which becomes [vout])
        if i < len(phrases) - 1:
            filters[-1] += f"[dt{i}]"
        else:
            filters[-1] += "[vout]"

    return filters


def _build_audio_filters(
    has_narration: bool,
    has_music: bool,
    has_ambient: bool,
    narr_idx: int,
    music_idx: int,
    ambient_idx: int,
    narr_fade_start: float,
    music_fade_start: float,
) -> tuple[list[str], str]:
    """Build audio mixing filters matching existing reel_generator patterns.

    Returns (filter_list, audio_map_label).
    """
    filters: list[str] = []
    mix_labels: list[str] = []
    mix_count = 0

    if has_narration:
        filters.append(
            f"[{narr_idx}:a]afade=t=out:st={narr_fade_start}:d=0.8[narr]"
        )
        mix_labels.append("[narr]")
        mix_count += 1

    if has_music:
        music_vol = "0.08" if has_narration else "0.20"
        filters.append(
            f"[{music_idx}:a]volume={music_vol},"
            f"afade=t=in:st=0:d=1.5,"
            f"afade=t=out:st={music_fade_start}:d=2.5[music]"
        )
        mix_labels.append("[music]")
        mix_count += 1

    if has_ambient:
        filters.append(
            f"[{ambient_idx}:a]volume=0.05,"
            f"afade=t=in:st=0:d=2.0,"
            f"afade=t=out:st={music_fade_start}:d=2.5[amb]"
        )
        mix_labels.append("[amb]")
        mix_count += 1

    audio_map = ""
    if mix_count > 1:
        filters.append(
            f"{''.join(mix_labels)}amix=inputs={mix_count}:duration=longest:normalize=0[a]"
        )
        audio_map = "[a]"
    elif mix_count == 1:
        # Rename the single audio stream to [a]
        last_filter = filters[-1]
        for label in ["[narr]", "[music]", "[amb]"]:
            if last_filter.endswith(label):
                filters[-1] = last_filter[: -len(label)] + "[a]"
                break
        audio_map = "[a]"

    return filters, audio_map


def _escape_drawtext(text: str) -> str:
    """Escape text for FFmpeg drawtext filter.

    FFmpeg drawtext requires escaping of:
      - Single quotes -> not allowed in single-quoted text, use Unicode
      - Colons -> \\:
      - Backslashes -> \\\\
      - Percent signs -> %%
      - Semicolons (filter separator) -> handled by quoting
    """
    # Replace backslashes first
    text = text.replace("\\", "\\\\")
    # Escape colons (FFmpeg drawtext option separator)
    text = text.replace(":", "\\:")
    # Escape single quotes (we use single quotes to wrap the text value)
    text = text.replace("'", "\u2019")  # Replace with right single quote
    # Escape percent signs
    text = text.replace("%", "%%")
    # Escape semicolons
    text = text.replace(";", "\\;")
    return text


def _find_font_path() -> Optional[str]:
    """Find a suitable font file for FFmpeg drawtext."""
    for name in FONT_CANDIDATES:
        for fonts_dir in _FONT_DIRS:
            candidate = fonts_dir / name
            if candidate.exists():
                # FFmpeg needs forward slashes even on Windows
                return str(candidate).replace("\\", "/")
    return None


def _get_audio_duration(audio_path: Path) -> Optional[float]:
    """Get audio file duration in seconds using ffprobe."""
    if not audio_path.exists():
        return None

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def _select_audio_track(
    content_type: str,
    content_id: int,
) -> tuple[Optional[Path], float]:
    """Select mood-matched background music. Reuses existing reel_generator logic."""
    try:
        from core.images.reel_generator import _select_audio_track as _reel_select_audio
        return _reel_select_audio(content_type, content_id)
    except ImportError:
        return None, 0.0


def _select_ambient_sound(
    content_type: str,
    content_id: int,
) -> Optional[Path]:
    """Select ambient sound effect. Reuses existing reel_generator logic."""
    try:
        from core.audio.elevenlabs_music import select_ambient_sound
        path = select_ambient_sound(content_type, content_id)
        if path:
            logger.info(f"Selected ambient: {path.name}")
        return path
    except Exception:
        return None
