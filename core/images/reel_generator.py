"""Animated reel generator — PIL frame rendering + FFmpeg video assembly.

Generates text-reveal style reels for Instagram/TikTok:
  1. Scenic background with Ken Burns motion (slow zoom/pan via FFmpeg zoompan)
  2. White Bible-page card fades in (rendered as transparent PNGs, composited via FFmpeg overlay)
  3. Verse text lines appear one by one with yellow highlight
  4. Each line highlights, then the next appears
  5. Background music mixed in (if audio files available)

Output: 9:16 MP4 (1080x1920) at 30fps, ~12-15 seconds.
"""

import logging
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from core.config import settings
from core.images.image_processor import (
    BRAND_COLORS,
    IMAGES_PROCESSED_DIR,
    _resolve_font,
    _wrap_text,
    get_body_font,
    get_heading_font,
)

logger = logging.getLogger(__name__)

# Audio directory for background music
AUDIO_DIR = Path(__file__).parent.parent.parent / "audio"

# Reel dimensions (9:16 vertical video)
REEL_W = 1080
REEL_H = 1920
FPS = 30

# Timing (in seconds) — targeting 12-15s total reel length
# These are defaults; actual values come from the selected reel style
INTRO_HOLD = 1.8        # Show background only (let viewer settle in)
CARD_FADE_FRAMES = 10    # Card fade-in frames
LINE_REVEAL_HOLD = 1.6   # How long each line stays before next appears
FINAL_HOLD = 3.5         # Hold full verse at end (time to read/absorb)
OUTRO_HOLD = 1.0         # Brief hold before end
MAX_REEL_SECONDS = 30.0  # Hard cap — Instagram reels should stay concise

# Reel presentation styles — rotated by content_id for feed variety
REEL_STYLES = {
    "classic": {
        # Original: intro hold → card fade → line-by-line reveal
        "intro_hold": 1.8,
        "card_fade_frames": 10,
        "line_reveal_hold": 1.6,
        "final_hold": 3.5,
        "outro_hold": 1.0,
        "reveal_mode": "line_by_line",
    },
    "quick": {
        # Fast start: short intro → quick fade → all text at once
        "intro_hold": 0.6,
        "card_fade_frames": 6,
        "line_reveal_hold": 0.0,  # all lines appear together
        "final_hold": 5.0,
        "outro_hold": 1.0,
        "reveal_mode": "all_at_once",
    },
    "cinematic": {
        # Slow build: long scenic intro → gradual card → line-by-line
        "intro_hold": 3.0,
        "card_fade_frames": 15,
        "line_reveal_hold": 1.4,
        "final_hold": 3.0,
        "outro_hold": 1.5,
        "reveal_mode": "line_by_line",
    },
}
REEL_STYLE_ORDER = ["classic", "quick", "cinematic"]

# Ken Burns minimum source image size (zoompan needs headroom)
KEN_BURNS_MIN_WIDTH = 1728


def generate_reel(
    background_path: str,
    verse_text: str,
    verse_ref: str,
    content_id: int,
    translation: str = "WEB",
    content_type: str = "",
) -> Optional[str]:
    """Generate an animated text-reveal reel video.

    Args:
        background_path: Path to background photo (will be cropped to 9:16).
        verse_text: Full Bible verse text.
        verse_ref: Verse reference (e.g. "Psalms 119:105").
        content_id: Content ID for output naming.
        translation: Bible translation abbreviation.
        content_type: Content type string (unused, kept for API compatibility).

    Returns:
        Path to output MP4 file, or None on failure.
    """
    if not shutil.which("ffmpeg"):
        logger.error("FFmpeg not found — cannot generate reel")
        return None

    try:
        bg = Image.open(background_path).convert("RGB")
    except Exception as e:
        logger.error(f"Failed to open background image: {e}")
        return None

    # Select reel presentation style based on content_id for variety
    style_name = REEL_STYLE_ORDER[content_id % len(REEL_STYLE_ORDER)]
    style = REEL_STYLES[style_name]
    logger.info(f"Reel style: {style_name} for content #{content_id}")

    # Normalize verse text
    verse_text = " ".join(verse_text.split())

    # Parse reference
    ref_parts = verse_ref.split()
    book_name = " ".join(ref_parts[:-1]) if len(ref_parts) > 1 else verse_ref
    chapter_verse = ref_parts[-1] if len(ref_parts) > 1 else ""
    chapter_num = ""
    verse_start_str = ""
    if ":" in chapter_verse:
        chapter_num, verse_start_str = chapter_verse.split(":", 1)
        if "-" in verse_start_str:
            verse_start_str = verse_start_str.split("-")[0]

    # Prepare fonts and text layout
    header_font = get_body_font(26)
    verse_num_font = get_body_font(28)
    wm_font = get_body_font(18)

    verse_font_names = [
        "georgia.ttf", "LiberationSerif-Regular.ttf", "DejaVuSerif.ttf",
        "times.ttf",
    ]

    # Card sizing
    card_margin_x = int(REEL_W * 0.06)
    card_w = REEL_W - card_margin_x * 2
    card_padding_x = 48
    text_area_w = card_w - card_padding_x * 2

    # Adaptive font for verse text
    font_size = 50
    verse_font = _resolve_font(verse_font_names, font_size)
    verse_lines = _wrap_text(verse_text, verse_font, text_area_w - 40)
    max_lines = 7
    while len(verse_lines) > max_lines and font_size > 34:
        font_size -= 4
        verse_font = _resolve_font(verse_font_names, font_size)
        verse_lines = _wrap_text(verse_text, verse_font, text_area_w - 40)

    # Measure dimensions
    measure_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    sample_bbox = measure_draw.textbbox((0, 0), "Ay", font=verse_font)
    line_h = (sample_bbox[3] - sample_bbox[1]) + 18

    # Card dimensions
    card_padding_top = 60
    card_padding_bottom = 55
    header_h = 60
    verse_block_h = len(verse_lines) * line_h
    card_h = card_padding_top + header_h + verse_block_h + card_padding_bottom
    min_card_h = int(REEL_H * 0.30)
    max_card_h = int(REEL_H * 0.60)
    card_h = max(min_card_h, min(card_h, max_card_h))

    card_x = card_margin_x
    card_y = (REEL_H - card_h) // 2 - 40

    # Header text
    header_text = f"{book_name} {chapter_num}" if chapter_num else verse_ref
    header_text += f"  |  {translation.upper()}"
    verse_num_text = f"{verse_start_str} " if verse_start_str else ""

    # Calculate text starting Y (centered in card)
    text_x = card_x + card_padding_x + 4
    header_y_offset = card_padding_top
    sep_y_offset = header_y_offset + 45
    text_start_offset = sep_y_offset + 24
    remaining = card_h - card_padding_bottom - text_start_offset
    total_verse_h = len(verse_lines) * line_h
    text_y_offset = text_start_offset
    if total_verse_h < remaining:
        text_y_offset += (remaining - total_verse_h) // 2

    # Calculate total frame count using selected style's timing
    s_intro = style["intro_hold"]
    s_card_fade = style["card_fade_frames"]
    s_line_reveal = style["line_reveal_hold"]
    s_final = style["final_hold"]
    s_outro = style["outro_hold"]
    reveal_mode = style["reveal_mode"]

    intro_frames = int(s_intro * FPS)
    if reveal_mode == "all_at_once":
        line_reveal_frames = 0  # all lines shown together during final_hold
    else:
        line_reveal_frames = len(verse_lines) * int(s_line_reveal * FPS)
    final_frames = int(s_final * FPS)
    outro_frames = int(s_outro * FPS)
    total_frames = intro_frames + s_card_fade + line_reveal_frames + final_frames + outro_frames
    total_seconds = total_frames / FPS

    # Determine motion style
    motion_style = settings.reel_motion_style
    use_ken_burns = motion_style == "ken_burns" and bg.width >= KEN_BURNS_MIN_WIDTH

    # Generate TTS narration (if ElevenLabs configured)
    narration_path: Optional[Path] = None
    try:
        from core.audio.elevenlabs_music import generate_narration
        narration_path = generate_narration(
            verse_text=verse_text,
            verse_ref=verse_ref,
            content_id=content_id,
        )
    except Exception as e:
        logger.warning(f"Narration generation failed: {e}")

    # Extend video if narration is longer than visual timing (capped at MAX_REEL_SECONDS)
    # If narration still doesn't fit after extension, drop it (no speedup — sounds unnatural)
    if narration_path and narration_path.exists():
        narration_delay = s_intro + (s_card_fade / FPS) + 0.3
        narration_dur = _get_audio_duration(narration_path)
        if narration_dur:
            narration_end = narration_delay + narration_dur + 1.5  # 1.5s breathing room
            if narration_end > total_seconds:
                extra = min(narration_end - total_seconds, MAX_REEL_SECONDS - total_seconds)
                if extra > 0:
                    logger.info(
                        f"Extending reel by {extra:.1f}s for narration "
                        f"(narration={narration_dur:.1f}s, video was {total_seconds:.1f}s)"
                    )
                    extra_frames = int(extra * FPS)
                    final_frames += extra_frames
                    total_frames += extra_frames
                    total_seconds = total_frames / FPS

            # After extension, check if narration still overruns the video
            available_time = total_seconds - narration_delay - 1.5
            if narration_dur > available_time + 0.5:  # 0.5s tolerance
                # Try regenerating narration at higher speed (native ElevenLabs, sounds natural)
                needed_speed = narration_dur / max(available_time, 1.0)
                if needed_speed <= 1.8:  # Only speed up moderately
                    try:
                        from core.audio.elevenlabs_music import generate_narration_at_speed
                        fast_path = generate_narration_at_speed(
                            verse_text=verse_text,
                            verse_ref=verse_ref,
                            content_id=content_id,
                            speed=needed_speed,
                        )
                        if fast_path and fast_path.exists():
                            fast_dur = _get_audio_duration(fast_path)
                            if fast_dur and fast_dur <= available_time + 0.5:
                                narration_path = fast_path
                                narration_dur = fast_dur
                                logger.info(
                                    f"Using {needed_speed:.2f}x speed narration "
                                    f"({fast_dur:.1f}s fits in {available_time:.1f}s)"
                                )
                            else:
                                logger.warning("Speed-adjusted narration still too long")
                    except Exception as e:
                        logger.warning(f"Native speed narration failed: {e}")

                # If still too long after speed attempt, drop narration
                if narration_dur > available_time + 0.5:
                    logger.warning(
                        f"Narration too long ({narration_dur:.1f}s) for {available_time:.1f}s "
                        f"available — dropping narration, shortening reel to ~15s"
                    )
                    narration_path = None
                    target_seconds = 15.0
                    target_frames = int(target_seconds * FPS)
                    if total_frames > target_frames:
                        overshoot = total_frames - target_frames
                        final_frames = max(int(2.0 * FPS), final_frames - overshoot)
                        total_frames = intro_frames + CARD_FADE_FRAMES + line_reveal_frames + final_frames + outro_frames
                        total_seconds = total_frames / FPS

    # ── Render to temp directory ──
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        IMAGES_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        output_path = IMAGES_PROCESSED_DIR / f"{content_id}_reel_9x16.mp4"

        if use_ken_burns:
            result = _generate_two_pass(
                bg=bg,
                tmpdir=tmpdir,
                output_path=output_path,
                total_frames=total_frames,
                total_seconds=total_seconds,
                card_x=card_x, card_y=card_y,
                card_w=card_w, card_h=card_h,
                card_padding_x=card_padding_x,
                header_text=header_text,
                header_font=header_font,
                header_y_offset=header_y_offset,
                sep_y_offset=sep_y_offset,
                wm_font=wm_font,
                verse_lines=verse_lines,
                verse_font=verse_font,
                verse_num_font=verse_num_font,
                verse_num_text=verse_num_text,
                text_x=text_x,
                text_y_offset=text_y_offset,
                line_h=line_h,
                intro_frames=intro_frames,
                card_fade_frames=s_card_fade,
                line_reveal_hold=s_line_reveal,
                final_frames=final_frames,
                outro_frames=outro_frames,
                reveal_mode=reveal_mode,
                narration_path=narration_path,
                content_type=content_type,
                content_id=content_id,
            )
        else:
            result = _generate_static(
                bg=bg,
                tmpdir=tmpdir,
                output_path=output_path,
                total_seconds=total_seconds,
                card_x=card_x, card_y=card_y,
                card_w=card_w, card_h=card_h,
                card_padding_x=card_padding_x,
                header_text=header_text,
                header_font=header_font,
                header_y_offset=header_y_offset,
                sep_y_offset=sep_y_offset,
                wm_font=wm_font,
                verse_lines=verse_lines,
                verse_font=verse_font,
                verse_num_font=verse_num_font,
                verse_num_text=verse_num_text,
                text_x=text_x,
                text_y_offset=text_y_offset,
                line_h=line_h,
                intro_hold=s_intro,
                card_fade_frames=s_card_fade,
                line_reveal_hold=s_line_reveal,
                final_hold=s_final,
                outro_hold=s_outro,
                reveal_mode=reveal_mode,
                narration_path=narration_path,
                content_type=content_type,
                content_id=content_id,
            )

        if result:
            logger.info(
                f"Reel generated: {output_path} "
                f"({total_frames} frames, {total_seconds:.1f}s, {len(verse_lines)} lines, "
                f"style={style_name}, motion={'ken_burns' if use_ken_burns else 'static'})"
            )
        return result


def _generate_two_pass(
    bg: Image.Image,
    tmpdir: Path,
    output_path: Path,
    total_frames: int,
    total_seconds: float,
    card_x: int, card_y: int,
    card_w: int, card_h: int,
    card_padding_x: int,
    header_text: str,
    header_font: ImageFont.FreeTypeFont,
    header_y_offset: int,
    sep_y_offset: int,
    wm_font: ImageFont.FreeTypeFont,
    verse_lines: list[str],
    verse_font: ImageFont.FreeTypeFont,
    verse_num_font: ImageFont.FreeTypeFont,
    verse_num_text: str,
    text_x: int,
    text_y_offset: int,
    line_h: int,
    intro_frames: int,
    card_fade_frames: int = CARD_FADE_FRAMES,
    line_reveal_hold: float = LINE_REVEAL_HOLD,
    final_frames: int = int(FINAL_HOLD * FPS),
    outro_frames: int = int(OUTRO_HOLD * FPS),
    reveal_mode: str = "line_by_line",
    narration_path: Optional[Path] = None,
    content_type: str = "",
    content_id: int = 0,
) -> Optional[str]:
    """Two-pass Ken Burns approach: zoompan background + transparent card overlay."""

    # ── Pass 1: Generate motion background with zoompan ──
    bg_source_path = tmpdir / "bg_source.jpg"
    # Save the full-res background (don't crop yet — zoompan crops for us)
    bg.save(str(bg_source_path), "JPEG", quality=95)

    bg_motion_path = tmpdir / "bg_motion.mp4"

    # Calculate zoom: start at 1.0, end at ~1.15 (subtle 15% zoom over duration)
    zoom_per_frame = 0.0005
    max_zoom = 1.0 + zoom_per_frame * total_frames

    # Zoompan filter: slow zoom-in centered, outputs at reel dimensions
    zoompan_filter = (
        f"zoompan="
        f"z='min(zoom+{zoom_per_frame},{max_zoom:.4f})':"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"d={total_frames}:"
        f"s={REEL_W}x{REEL_H}:"
        f"fps={FPS}"
    )

    cmd_bg = [
        "ffmpeg", "-y",
        "-i", str(bg_source_path),
        "-vf", zoompan_filter,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "medium",
        str(bg_motion_path),
    ]

    try:
        result = subprocess.run(cmd_bg, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning(f"Ken Burns zoompan failed, falling back to static: {result.stderr[-300:]}")
            return None
    except Exception as e:
        logger.warning(f"Ken Burns generation error, falling back to static: {e}")
        return None

    # ── Render transparent card overlay frames as PNGs ──
    frame_num = 0

    # Phase 1: Intro — transparent (no card, just a slight darken overlay)
    dark_overlay = Image.new("RGBA", (REEL_W, REEL_H), (0, 0, 0, 50))
    for _ in range(intro_frames):
        path = tmpdir / f"overlay_{frame_num:05d}.png"
        dark_overlay.save(str(path), "PNG")
        frame_num += 1

    # Phase 2: Card fade-in
    for fade_i in range(card_fade_frames):
        alpha = int((fade_i + 1) / card_fade_frames * 248)
        # For "all_at_once" show all lines as card fades in
        vis = len(verse_lines) if reveal_mode == "all_at_once" else 0
        frame = _render_card_frame(
            bg=None, transparent_bg=True,
            card_alpha=alpha,
            card_x=card_x, card_y=card_y,
            card_w=card_w, card_h=card_h,
            header_text=header_text,
            header_font=header_font,
            header_y_offset=header_y_offset,
            sep_y_offset=sep_y_offset,
            card_padding_x=card_padding_x,
            wm_font=wm_font,
            visible_lines=vis,
            verse_lines=verse_lines,
            verse_font=verse_font,
            verse_num_font=verse_num_font,
            verse_num_text=verse_num_text,
            text_x=text_x,
            text_y_offset=text_y_offset,
            line_h=line_h,
        )
        path = tmpdir / f"overlay_{frame_num:05d}.png"
        frame.save(str(path), "PNG")
        frame_num += 1

    # Phase 3: Line-by-line reveal (skipped for "all_at_once")
    if reveal_mode == "line_by_line":
        for line_idx in range(1, len(verse_lines) + 1):
            hold_frames = int(line_reveal_hold * FPS)
            frame = _render_card_frame(
                bg=None, transparent_bg=True,
                card_alpha=248,
                card_x=card_x, card_y=card_y,
                card_w=card_w, card_h=card_h,
                header_text=header_text,
                header_font=header_font,
                header_y_offset=header_y_offset,
                sep_y_offset=sep_y_offset,
                card_padding_x=card_padding_x,
                wm_font=wm_font,
                visible_lines=line_idx,
                verse_lines=verse_lines,
                verse_font=verse_font,
                verse_num_font=verse_num_font,
                verse_num_text=verse_num_text,
                text_x=text_x,
                text_y_offset=text_y_offset,
                line_h=line_h,
            )
            for _ in range(hold_frames):
                path = tmpdir / f"overlay_{frame_num:05d}.png"
                frame.save(str(path), "PNG")
                frame_num += 1

    # Phase 4: Final hold — all lines visible
    full_card = _render_card_frame(
        bg=None, transparent_bg=True,
        card_alpha=248,
        card_x=card_x, card_y=card_y,
        card_w=card_w, card_h=card_h,
        header_text=header_text,
        header_font=header_font,
        header_y_offset=header_y_offset,
        sep_y_offset=sep_y_offset,
        card_padding_x=card_padding_x,
        wm_font=wm_font,
        visible_lines=len(verse_lines),
        verse_lines=verse_lines,
        verse_font=verse_font,
        verse_num_font=verse_num_font,
        verse_num_text=verse_num_text,
        text_x=text_x,
        text_y_offset=text_y_offset,
        line_h=line_h,
    )
    for _ in range(final_frames):
        path = tmpdir / f"overlay_{frame_num:05d}.png"
        full_card.save(str(path), "PNG")
        frame_num += 1

    # Phase 5: Brief outro
    for _ in range(outro_frames):
        path = tmpdir / f"overlay_{frame_num:05d}.png"
        full_card.save(str(path), "PNG")
        frame_num += 1

    # ── Pass 2: Composite overlay onto motion background + audio ──
    audio_track, audio_start = _select_audio_track(content_type, content_id)
    ambient_sound = _select_ambient_sound(content_type, content_id)
    narration_delay = (intro_frames / FPS) + (card_fade_frames / FPS) + 0.3  # Start after card appears

    cmd = _build_composite_cmd(
        video_path=str(bg_motion_path),
        overlay_pattern=str(tmpdir / "overlay_%05d.png"),
        output_path=str(output_path),
        total_seconds=total_seconds,
        audio_track=audio_track,
        audio_start=audio_start,
        narration_path=narration_path,
        narration_delay=narration_delay,
        use_shortest=True,
        ambient_path=ambient_sound,
    )
    audio_desc = []
    if audio_track:
        audio_desc.append(f"music: {audio_track.name} (seek {audio_start:.1f}s)")
    if narration_path:
        audio_desc.append(f"narration: {narration_path.name} (delay {narration_delay:.1f}s)")
    if ambient_sound:
        audio_desc.append(f"ambient: {ambient_sound.name}")
    logger.info(f"Compositing Ken Burns + overlay + {', '.join(audio_desc) or 'no audio'}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            logger.error(f"FFmpeg composite failed: {result.stderr[-500:]}")
            return None
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg composite timed out")
        return None
    except Exception as e:
        logger.error(f"FFmpeg composite error: {e}")
        return None

    return str(output_path)


def _generate_static(
    bg: Image.Image,
    tmpdir: Path,
    output_path: Path,
    total_seconds: float,
    card_x: int, card_y: int,
    card_w: int, card_h: int,
    card_padding_x: int,
    header_text: str,
    header_font: ImageFont.FreeTypeFont,
    header_y_offset: int,
    sep_y_offset: int,
    wm_font: ImageFont.FreeTypeFont,
    verse_lines: list[str],
    verse_font: ImageFont.FreeTypeFont,
    verse_num_font: ImageFont.FreeTypeFont,
    verse_num_text: str,
    text_x: int,
    text_y_offset: int,
    line_h: int,
    intro_hold: float = INTRO_HOLD,
    card_fade_frames: int = CARD_FADE_FRAMES,
    line_reveal_hold: float = LINE_REVEAL_HOLD,
    final_hold: float = FINAL_HOLD,
    outro_hold: float = OUTRO_HOLD,
    reveal_mode: str = "line_by_line",
    narration_path: Optional[Path] = None,
    content_type: str = "",
    content_id: int = 0,
) -> Optional[str]:
    """Original static-background approach: PIL renders full frames as JPGs."""

    # Crop/resize background to reel dimensions
    bg = _resize_and_crop_reel(bg)

    frame_num = 0

    # Phase 1: Intro — background only with slight darken
    intro_frames = int(intro_hold * FPS)
    darkened_bg = _darken_bg(bg)
    for _ in range(intro_frames):
        path = tmpdir / f"frame_{frame_num:05d}.jpg"
        darkened_bg.save(str(path), "JPEG", quality=88)
        frame_num += 1

    # Phase 2: Card fade-in
    for fade_i in range(card_fade_frames):
        alpha = int((fade_i + 1) / card_fade_frames * 248)
        vis = len(verse_lines) if reveal_mode == "all_at_once" else 0
        frame = _render_card_frame(
            bg=bg, transparent_bg=False,
            card_alpha=alpha,
            card_x=card_x, card_y=card_y,
            card_w=card_w, card_h=card_h,
            header_text=header_text,
            header_font=header_font,
            header_y_offset=header_y_offset,
            sep_y_offset=sep_y_offset,
            card_padding_x=card_padding_x,
            wm_font=wm_font,
            visible_lines=vis,
            verse_lines=verse_lines,
            verse_font=verse_font,
            verse_num_font=verse_num_font,
            verse_num_text=verse_num_text,
            text_x=text_x,
            text_y_offset=text_y_offset,
            line_h=line_h,
        )
        path = tmpdir / f"frame_{frame_num:05d}.jpg"
        frame.save(str(path), "JPEG", quality=88)
        frame_num += 1

    # Phase 3: Line-by-line reveal (skipped for "all_at_once")
    if reveal_mode == "line_by_line":
        for line_idx in range(1, len(verse_lines) + 1):
            hold_frames = int(line_reveal_hold * FPS)
            frame = _render_card_frame(
                bg=bg, transparent_bg=False,
                card_alpha=248,
                card_x=card_x, card_y=card_y,
                card_w=card_w, card_h=card_h,
                header_text=header_text,
                header_font=header_font,
                header_y_offset=header_y_offset,
                sep_y_offset=sep_y_offset,
                card_padding_x=card_padding_x,
                wm_font=wm_font,
                visible_lines=line_idx,
                verse_lines=verse_lines,
                verse_font=verse_font,
                verse_num_font=verse_num_font,
                verse_num_text=verse_num_text,
                text_x=text_x,
                text_y_offset=text_y_offset,
                line_h=line_h,
            )
            for _ in range(hold_frames):
                path = tmpdir / f"frame_{frame_num:05d}.jpg"
                frame.save(str(path), "JPEG", quality=88)
                frame_num += 1

    # Phase 4: Final hold — all lines visible
    full_frame = _render_card_frame(
        bg=bg, transparent_bg=False,
        card_alpha=248,
        card_x=card_x, card_y=card_y,
        card_w=card_w, card_h=card_h,
        header_text=header_text,
        header_font=header_font,
        header_y_offset=header_y_offset,
        sep_y_offset=sep_y_offset,
        card_padding_x=card_padding_x,
        wm_font=wm_font,
        visible_lines=len(verse_lines),
        verse_lines=verse_lines,
        verse_font=verse_font,
        verse_num_font=verse_num_font,
        verse_num_text=verse_num_text,
        text_x=text_x,
        text_y_offset=text_y_offset,
        line_h=line_h,
    )
    f_final_frames = int(final_hold * FPS)
    for _ in range(f_final_frames):
        path = tmpdir / f"frame_{frame_num:05d}.jpg"
        full_frame.save(str(path), "JPEG", quality=88)
        frame_num += 1

    # Phase 5: Brief outro
    f_outro_frames = int(outro_hold * FPS)
    for _ in range(f_outro_frames):
        path = tmpdir / f"frame_{frame_num:05d}.jpg"
        full_frame.save(str(path), "JPEG", quality=88)
        frame_num += 1

    # ── Assemble with FFmpeg ──
    audio_track, audio_start = _select_audio_track(content_type, content_id)
    ambient_sound = _select_ambient_sound(content_type, content_id)
    narration_delay = intro_hold + (card_fade_frames / FPS) + 0.3

    # For static, frames are JPGs (no overlay composite needed)
    cmd = _build_static_cmd(
        frame_pattern=str(tmpdir / "frame_%05d.jpg"),
        output_path=str(output_path),
        total_seconds=total_seconds,
        audio_track=audio_track,
        audio_start=audio_start,
        narration_path=narration_path,
        narration_delay=narration_delay,
        ambient_path=ambient_sound,
    )
    if audio_track:
        logger.info(f"Mixing audio: {audio_track.name} (seek {audio_start:.1f}s)")
    if narration_path:
        logger.info(f"Mixing narration: {narration_path.name} (delay {narration_delay:.1f}s)")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"FFmpeg failed: {result.stderr[-500:]}")
            return None
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timed out")
        return None
    except Exception as e:
        logger.error(f"FFmpeg error: {e}")
        return None

    return str(output_path)


def _build_composite_cmd(
    video_path: str,
    overlay_pattern: str,
    output_path: str,
    total_seconds: float,
    audio_track: Optional[Path] = None,
    audio_start: float = 0.0,
    narration_path: Optional[Path] = None,
    narration_delay: float = 2.0,
    use_shortest: bool = True,
    ambient_path: Optional[Path] = None,
) -> list[str]:
    """Build FFmpeg command for Ken Burns composite with optional narration + music + ambient.

    Audio mixing strategy:
      - Narration: full volume, delayed to start after card appears
      - Music: ducked low behind narration (8%), or 20% standalone
      - Ambient: very subtle layer (5%) for immersive nature atmosphere
      - All layers fade out at end
    """
    music_fade_start = max(0, total_seconds - 2.5)
    narr_fade_start = max(0, total_seconds - 0.5)
    has_music = audio_track is not None
    has_narration = narration_path is not None
    has_ambient = ambient_path is not None

    cmd = ["ffmpeg", "-y"]

    # Input 0: motion background video
    cmd += ["-i", video_path]
    # Input 1: overlay PNG frames
    cmd += ["-framerate", str(FPS), "-i", overlay_pattern]

    input_idx = 2

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

    # Build filter complex
    filters = ["[0:v][1:v]overlay=0:0:eof_action=repeat[v]"]

    # Build audio mix labels
    mix_labels = []
    mix_count = 0

    if has_narration:
        filters.append(
            f"[{narr_idx}:a]adelay={int(narration_delay * 1000)}|{int(narration_delay * 1000)},"
            f"afade=t=out:st={narr_fade_start}:d=0.8[narr]"
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

    if mix_count > 1:
        filters.append(
            f"{''.join(mix_labels)}amix=inputs={mix_count}:duration=longest:normalize=0[a]"
        )
    elif mix_count == 1:
        # Single audio stream — rename to [a]
        last_filter = filters[-1]
        # Replace the label at the end with [a]
        for label in ["[narr]", "[music]", "[amb]"]:
            if last_filter.endswith(label):
                filters[-1] = last_filter[:-len(label)] + "[a]"
                break

    cmd += ["-filter_complex", ";".join(filters)]
    cmd += ["-map", "[v]"]

    if mix_count > 0:
        cmd += ["-map", "[a]"]
        cmd += ["-c:a", "aac", "-b:a", "128k"]

    cmd += [
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        "-preset", "medium",
        "-movflags", "+faststart",
    ]

    if use_shortest and not has_narration:
        cmd += ["-shortest"]

    cmd += ["-t", str(total_seconds), output_path]
    return cmd


def _build_static_cmd(
    frame_pattern: str,
    output_path: str,
    total_seconds: float,
    audio_track: Optional[Path] = None,
    audio_start: float = 0.0,
    narration_path: Optional[Path] = None,
    narration_delay: float = 2.0,
    ambient_path: Optional[Path] = None,
) -> list[str]:
    """Build FFmpeg command for static frame assembly with optional narration + music + ambient."""
    music_fade_start = max(0, total_seconds - 2.5)
    narr_fade_start = max(0, total_seconds - 0.5)
    has_music = audio_track is not None
    has_narration = narration_path is not None
    has_ambient = ambient_path is not None

    cmd = ["ffmpeg", "-y"]

    # Input 0: frame sequence
    cmd += ["-framerate", str(FPS), "-i", frame_pattern]

    input_idx = 1

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

    # Build audio filters
    mix_labels = []
    mix_count = 0
    filters = []

    if has_narration:
        filters.append(
            f"[{narr_idx}:a]adelay={int(narration_delay * 1000)}|{int(narration_delay * 1000)},"
            f"afade=t=out:st={narr_fade_start}:d=0.8[narr]"
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

    if mix_count > 1:
        filters.append(
            f"{''.join(mix_labels)}amix=inputs={mix_count}:duration=longest:normalize=0[a]"
        )
        cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]"]
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    elif mix_count == 1:
        last_filter = filters[-1]
        for label in ["[narr]", "[music]", "[amb]"]:
            if last_filter.endswith(label):
                filters[-1] = last_filter[:-len(label)] + "[a]"
                break
        cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]"]
        cmd += ["-c:a", "aac", "-b:a", "128k"]

    cmd += [
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        "-preset", "medium",
        "-movflags", "+faststart",
    ]

    if has_music and not has_narration:
        cmd += ["-shortest"]

    cmd += ["-t", str(total_seconds), output_path]
    return cmd


def _select_ambient_sound(content_type: str = "", content_id: int = 0) -> Optional[Path]:
    """Select a content-matched ambient sound effect, if available."""
    try:
        from core.audio.elevenlabs_music import select_ambient_sound
        path = select_ambient_sound(content_type, content_id)
        if path:
            logger.info(f"Selected ambient: {path.name} for {content_type}")
        return path
    except Exception:
        return None


def _select_audio_track(
    content_type: str = "",
    content_id: int = 0,
) -> tuple[Optional[Path], float]:
    """Pick a mood-matched audio track and find a good start offset.

    Uses content-type-aware selection when available, falls back to random.

    Returns:
        (track_path, start_seconds) — start_seconds skips past any quiet intro
        and picks a random position within the "loud" portion of the track.
    """
    if not settings.reel_music_enabled:
        return None, 0.0
    if not AUDIO_DIR.exists():
        return None, 0.0

    # Try mood-matched selection first
    track = None
    if content_type:
        try:
            from core.audio.elevenlabs_music import select_music_for_content
            track = select_music_for_content(content_type, content_id)
            if track:
                logger.info(f"Mood-matched music for {content_type}: {track.name}")
        except Exception:
            pass

    # Fall back to random selection
    if not track:
        tracks = [
            t for t in (list(AUDIO_DIR.glob("*.mp3")) + list(AUDIO_DIR.glob("*.m4a")))
            if t.stat().st_size > 1000
        ]
        if not tracks:
            return None, 0.0
        track = random.choice(tracks)

    start = _find_audio_start(track)
    logger.debug(f"Selected audio track: {track.name} (start at {start:.1f}s)")
    return track, start


def _get_audio_duration(audio_path: Path) -> Optional[float]:
    """Get duration of an audio file in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def _speed_up_audio(audio_path: Path, speed: float) -> Path:
    """Speed up an audio file using FFmpeg atempo filter. Returns path to sped-up file."""
    sped_path = audio_path.with_suffix(".fast.mp3")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(audio_path),
                "-filter:a", f"atempo={speed:.4f}",
                "-vn", str(sped_path),
            ],
            capture_output=True, timeout=30,
        )
        if sped_path.exists() and sped_path.stat().st_size > 500:
            return sped_path
    except Exception:
        pass
    return audio_path


def _find_audio_start(track_path: Path, min_reel_seconds: float = 15.0) -> float:
    """Find a good start offset in a track by detecting where audio gets loud.

    Uses FFmpeg silencedetect to find the end of any quiet intro, then picks
    a random offset between that point and (duration - min_reel_seconds).

    Args:
        track_path: Path to audio file.
        min_reel_seconds: Minimum remaining audio needed after offset.

    Returns:
        Offset in seconds to seek to when mixing audio.
    """
    duration = _get_audio_duration(track_path)
    if duration <= 0:
        return 0.0

    # Use silencedetect to find where sound actually starts.
    # -50dB is lenient enough for quiet ambient/piano tracks.
    cmd = [
        "ffmpeg", "-i", str(track_path),
        "-af", "silencedetect=noise=-50dB:d=0.5",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        stderr = result.stderr
    except Exception:
        return 0.0

    # Parse first silence_end — that's where audible content begins
    first_sound_at = 0.0
    for line in stderr.split("\n"):
        if "silence_end:" in line:
            try:
                part = line.split("silence_end:")[1].split("|")[0].strip()
                first_sound_at = float(part)
            except (ValueError, IndexError):
                pass
            break

    # Cap first_sound_at so we always have enough audio remaining
    latest_safe_start = max(0.0, duration - min_reel_seconds)
    first_sound_at = min(first_sound_at, latest_safe_start)

    # If the track is short, just start at where sound begins
    if duration <= min_reel_seconds + 5:
        return first_sound_at

    # For longer tracks: pick a random offset in the "active" portion.
    # max_start ensures we don't start so late that audio ends mid-reel.
    max_start = max(0.0, duration - min_reel_seconds - 5)
    if max_start <= first_sound_at:
        return first_sound_at

    offset = random.uniform(first_sound_at, max_start)
    return round(offset, 1)


def _get_audio_duration(track_path: Path) -> float:
    """Get duration of an audio file in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(track_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _resize_and_crop_reel(img: Image.Image) -> Image.Image:
    """Resize and center-crop to 1080x1920 (9:16)."""
    target_ratio = REEL_W / REEL_H
    img_w, img_h = img.size
    img_ratio = img_w / img_h

    if img_ratio > target_ratio:
        new_h = img_h
        new_w = int(img_h * target_ratio)
        left = (img_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, new_h))
    else:
        new_w = img_w
        new_h = int(img_w / target_ratio)
        top = (img_h - new_h) // 2
        img = img.crop((0, top, new_w, top + new_h))

    return img.resize((REEL_W, REEL_H), Image.Resampling.LANCZOS)


def _darken_bg(bg: Image.Image) -> Image.Image:
    """Apply slight darken to background for reel."""
    rgba = bg.convert("RGBA")
    dark = Image.new("RGBA", rgba.size, (0, 0, 0, 50))
    return Image.alpha_composite(rgba, dark).convert("RGB")


def _render_card_frame(
    bg: Optional[Image.Image],
    card_alpha: int,
    card_x: int,
    card_y: int,
    card_w: int,
    card_h: int,
    header_text: str,
    header_font: ImageFont.FreeTypeFont,
    header_y_offset: int,
    sep_y_offset: int,
    card_padding_x: int,
    wm_font: ImageFont.FreeTypeFont,
    visible_lines: int,
    verse_lines: list[str],
    verse_font: ImageFont.FreeTypeFont,
    verse_num_font: ImageFont.FreeTypeFont,
    verse_num_text: str,
    text_x: int,
    text_y_offset: int,
    line_h: int,
    transparent_bg: bool = False,
) -> Image.Image:
    """Render a single reel frame with card and visible verse lines.

    When transparent_bg=True, returns an RGBA image with clear background
    (for compositing via FFmpeg overlay on motion background).
    When transparent_bg=False, composites onto the provided bg image.
    """
    if transparent_bg:
        # Transparent canvas for overlay compositing
        frame = Image.new("RGBA", (REEL_W, REEL_H), (0, 0, 0, 0))
        # Add slight darken overlay
        dark = Image.new("RGBA", (REEL_W, REEL_H), (0, 0, 0, 50))
        frame = Image.alpha_composite(frame, dark)
    else:
        frame = bg.convert("RGBA")
        w, h = frame.size
        dark = Image.new("RGBA", (w, h), (0, 0, 0, 50))
        frame = Image.alpha_composite(frame, dark)

    w, h = frame.size

    # Draw card
    card_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_layer)

    # Shadow
    try:
        cd.rounded_rectangle(
            (card_x + 5, card_y + 5, card_x + card_w + 5, card_y + card_h + 5),
            radius=16, fill=(0, 0, 0, min(45, card_alpha // 5)),
        )
    except AttributeError:
        cd.rectangle(
            (card_x + 5, card_y + 5, card_x + card_w + 5, card_y + card_h + 5),
            fill=(0, 0, 0, min(45, card_alpha // 5)),
        )

    # White card
    card_fill = (255, 255, 255, card_alpha)
    try:
        cd.rounded_rectangle(
            (card_x, card_y, card_x + card_w, card_y + card_h),
            radius=16, fill=card_fill,
        )
    except AttributeError:
        cd.rectangle(
            (card_x, card_y, card_x + card_w, card_y + card_h),
            fill=card_fill,
        )

    frame = Image.alpha_composite(frame, card_layer)

    # Only draw text if card is mostly opaque
    if card_alpha < 150:
        if transparent_bg:
            return frame  # Return RGBA
        return frame.convert("RGB")

    draw = ImageDraw.Draw(frame)
    header_x = card_x + card_padding_x

    # Header
    draw.text(
        (header_x, card_y + header_y_offset),
        header_text, fill=(120, 115, 110, card_alpha), font=header_font,
    )

    # Separator
    sep_y = card_y + sep_y_offset
    draw.line(
        [(header_x, sep_y), (card_x + card_w - card_padding_x, sep_y)],
        fill=(215, 215, 215, card_alpha), width=1,
    )

    # Watermark
    wm_text = "@stillwatergrace"
    wm_bbox = draw.textbbox((0, 0), wm_text, font=wm_font)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text(
        (card_x + card_w - card_padding_x - wm_w, card_y + card_h - 40),
        wm_text, fill=(180, 170, 160, card_alpha), font=wm_font,
    )

    if visible_lines <= 0:
        if transparent_bg:
            return frame
        return frame.convert("RGB")

    # ── Draw verse lines with highlights ──
    highlight_color = (255, 243, 115, 170)

    # First pass: highlights
    hl_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hl_draw = ImageDraw.Draw(hl_layer)

    for i in range(min(visible_lines, len(verse_lines))):
        line = verse_lines[i]
        y = card_y + text_y_offset + i * line_h

        if y + line_h > card_y + card_h - 50:
            break

        x_offset = 0
        if i == 0 and verse_num_text:
            num_bbox = draw.textbbox((0, 0), verse_num_text, font=verse_num_font)
            x_offset = (num_bbox[2] - num_bbox[0]) + 4

        line_bbox = draw.textbbox((0, 0), line, font=verse_font)
        line_w = line_bbox[2] - line_bbox[0]
        line_text_h = line_bbox[3] - line_bbox[1]

        hl_draw.rectangle(
            [(text_x + x_offset - 4, y - 3),
             (text_x + x_offset + line_w + 4, y + line_text_h + 5)],
            fill=highlight_color,
        )

    frame = Image.alpha_composite(frame, hl_layer)
    draw = ImageDraw.Draw(frame)

    # Second pass: text on top of highlights
    for i in range(min(visible_lines, len(verse_lines))):
        line = verse_lines[i]
        y = card_y + text_y_offset + i * line_h

        if y + line_h > card_y + card_h - 50:
            break

        x_offset = 0
        if i == 0 and verse_num_text:
            num_bbox = draw.textbbox((0, 0), verse_num_text, font=verse_num_font)
            num_w = num_bbox[2] - num_bbox[0]
            draw.text(
                (text_x, y + 2), verse_num_text,
                fill=BRAND_COLORS["gold"], font=verse_num_font,
            )
            x_offset = num_w + 4

        draw.text(
            (text_x + x_offset, y), line,
            fill=(50, 50, 50), font=verse_font,
        )

    if transparent_bg:
        return frame  # Return RGBA for PNG overlay
    return frame.convert("RGB")
