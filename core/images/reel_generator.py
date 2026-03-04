"""Animated reel generator — PIL frame rendering + FFmpeg video assembly.

Generates text-reveal style reels for Instagram/TikTok:
  1. Scenic background photo (from Leonardo/Unsplash)
  2. White Bible-page card fades in
  3. Verse text lines appear one by one with yellow highlight
  4. Each line highlights, then the next appears

Output: 9:16 MP4 (1080x1920) at 30fps, 12-18 seconds.
"""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from core.images.image_processor import (
    BRAND_COLORS,
    IMAGES_PROCESSED_DIR,
    _resolve_font,
    _wrap_text,
    get_body_font,
    get_heading_font,
)

logger = logging.getLogger(__name__)

# Reel dimensions (9:16 vertical video)
REEL_W = 1080
REEL_H = 1920
FPS = 30

# Timing (in seconds)
INTRO_HOLD = 1.0        # Show background only
CARD_FADE_FRAMES = 8     # Card fade-in frames
LINE_REVEAL_HOLD = 1.2   # How long each line stays before next appears
FINAL_HOLD = 2.5         # Hold full verse at end
OUTRO_HOLD = 0.8         # Brief hold before end


def generate_reel(
    background_path: str,
    verse_text: str,
    verse_ref: str,
    content_id: int,
    translation: str = "WEB",
) -> Optional[str]:
    """Generate an animated text-reveal reel video.

    Args:
        background_path: Path to background photo (will be cropped to 9:16).
        verse_text: Full Bible verse text.
        verse_ref: Verse reference (e.g. "Psalms 119:105").
        content_id: Content ID for output naming.
        translation: Bible translation abbreviation.

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

    # Crop/resize background to reel dimensions
    bg = _resize_and_crop_reel(bg)

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

    # ── Render frames to temp directory ──
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        frame_num = 0

        # Phase 1: Intro — background only with slight darken
        intro_frames = int(INTRO_HOLD * FPS)
        darkened_bg = _darken_bg(bg)
        for _ in range(intro_frames):
            path = tmpdir / f"frame_{frame_num:05d}.jpg"
            darkened_bg.save(str(path), "JPEG", quality=88)
            frame_num += 1

        # Phase 2: Card fade-in (8 frames)
        for fade_i in range(CARD_FADE_FRAMES):
            alpha = int((fade_i + 1) / CARD_FADE_FRAMES * 248)
            frame = _render_card_frame(
                bg=bg,
                card_alpha=alpha,
                card_x=card_x, card_y=card_y,
                card_w=card_w, card_h=card_h,
                header_text=header_text,
                header_font=header_font,
                header_y_offset=header_y_offset,
                sep_y_offset=sep_y_offset,
                card_padding_x=card_padding_x,
                wm_font=wm_font,
                visible_lines=0,
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

        # Phase 3: Line-by-line reveal
        for line_idx in range(1, len(verse_lines) + 1):
            hold_frames = int(LINE_REVEAL_HOLD * FPS)
            frame = _render_card_frame(
                bg=bg,
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
        final_frames = int(FINAL_HOLD * FPS)
        for _ in range(final_frames):
            path = tmpdir / f"frame_{frame_num:05d}.jpg"
            frame.save(str(path), "JPEG", quality=88)
            frame_num += 1

        # Phase 5: Brief outro
        outro_frames = int(OUTRO_HOLD * FPS)
        for _ in range(outro_frames):
            path = tmpdir / f"frame_{frame_num:05d}.jpg"
            frame.save(str(path), "JPEG", quality=88)
            frame_num += 1

        # ── Assemble with FFmpeg ──
        IMAGES_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        output_path = IMAGES_PROCESSED_DIR / f"{content_id}_reel_9x16.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", str(tmpdir / "frame_%05d.jpg"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "23",
            "-preset", "medium",
            "-movflags", "+faststart",
            str(output_path),
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                logger.error(f"FFmpeg failed: {result.stderr[-500:]}")
                return None
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out")
            return None
        except Exception as e:
            logger.error(f"FFmpeg error: {e}")
            return None

        total_seconds = frame_num / FPS
        logger.info(
            f"Reel generated: {output_path} "
            f"({frame_num} frames, {total_seconds:.1f}s, {len(verse_lines)} lines)"
        )
        return str(output_path)


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
    bg: Image.Image,
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
) -> Image.Image:
    """Render a single reel frame with card and visible verse lines."""
    frame = bg.convert("RGBA")
    w, h = frame.size

    # Darken background
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 50))
    frame = Image.alpha_composite(frame, dark)

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

    return frame.convert("RGB")
