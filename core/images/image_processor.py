"""Image processing pipeline — resize, optimize, text overlay, and R2 upload.

Orchestrates the full image pipeline from generation to final storage.
Includes PIL-based text overlay with multiple branded layout templates.
"""

import io
import logging
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from sqlalchemy.orm import Session

from core.config import settings
from database.models import (
    GeneratedContent,
    GeneratedImage,
    ContentStatus,
    ImageProvider,
    ImageFormat,
)

logger = logging.getLogger(__name__)

IMAGES_PROCESSED_DIR = Path(__file__).parent.parent.parent / "images" / "processed"

# Target dimensions for each format
TARGET_SIZES = {
    ImageFormat.feed_4x5: (1080, 1350),
    ImageFormat.feed_1x1: (1080, 1080),
    ImageFormat.story_9x16: (1080, 1920),
}

# Brand colors
BRAND_COLORS = {
    "cream": (255, 248, 240),
    "cream_dark": (245, 235, 220),
    "gold": (212, 168, 83),
    "gold_light": (232, 200, 140),
    "green": (45, 74, 62),
    "green_light": (75, 110, 95),
    "white": (250, 250, 250),
    "warm_gray": (180, 170, 160),
    "overlay_dark": (0, 0, 0, 120),
    "overlay_green": (45, 74, 62, 180),
    "overlay_cream": (255, 248, 240, 200),
    "overlay_dark_heavy": (0, 0, 0, 160),
    "overlay_green_heavy": (45, 74, 62, 210),
    "overlay_green_box": (45, 74, 62, 217),
    "white_text": (255, 255, 255),
}

# Font resolution — try branded fonts first, fall back to system fonts
_FONT_DIRS = [
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/truetype"),
    Path("/usr/share/fonts"),
]


def _resolve_font(preferred: list[str], size: int) -> ImageFont.FreeTypeFont:
    """Try each font file in order across all font directories."""
    for name in preferred:
        for fonts_dir in _FONT_DIRS:
            try:
                return ImageFont.truetype(str(fonts_dir / name), size)
            except OSError:
                continue
        # Try system-wide lookup by name alone
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def get_heading_font(size: int = 48) -> ImageFont.FreeTypeFont:
    """Get serif heading font (Georgia → Liberation Serif → DejaVu Serif → Times)."""
    return _resolve_font([
        "georgia.ttf", "LiberationSerif-Bold.ttf", "DejaVuSerif-Bold.ttf",
        "constan.ttf", "times.ttf", "arial.ttf",
    ], size)


def get_body_font(size: int = 28) -> ImageFont.FreeTypeFont:
    """Get clean body font (Calibri → Liberation Sans → DejaVu Sans)."""
    return _resolve_font([
        "calibri.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf",
        "segoeui.ttf", "arial.ttf",
    ], size)


def get_accent_font(size: int = 22) -> ImageFont.FreeTypeFont:
    """Get accent/attribution font (Georgia Italic → Liberation Serif Italic)."""
    return _resolve_font([
        "georgiai.ttf", "LiberationSerif-Italic.ttf", "DejaVuSerif-Italic.ttf",
        "calibrii.ttf", "ariali.ttf",
    ], size)


class ImagePipeline:
    """Full image processing pipeline from raw generation to final upload."""

    def __init__(self, db: Session):
        self.db = db
        IMAGES_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    def process_pending_content(self) -> int:
        """Process images for all pending content that has image prompts but no images.

        Returns number of content pieces processed.
        """
        # Find content with image prompts but no generated images
        content_items = (
            self.db.query(GeneratedContent)
            .filter(
                GeneratedContent.status == ContentStatus.pending,
                GeneratedContent.image_prompt.isnot(None),
                GeneratedContent.image_prompt != "",
            )
            .outerjoin(GeneratedImage)
            .filter(GeneratedImage.id.is_(None))
            .limit(10)  # Process in batches
            .all()
        )

        processed = 0
        for content in content_items:
            try:
                self.generate_images_for_content(content)
                processed += 1
            except Exception as e:
                logger.error(f"Failed to process images for content #{content.id}: {e}")
                continue

        return processed

    def generate_images_for_content(self, content: GeneratedContent) -> list[GeneratedImage]:
        """Generate all image formats for a content piece.

        Uses Unsplash for background photos, falls back to PIL-only branded images.
        """
        images = []
        raw_path = None
        provider = ImageProvider.pil_fallback

        # Unsplash
        if not raw_path and settings.unsplash_access_key:
            try:
                from core.images.unsplash_client import UnsplashClient
                unsplash = UnsplashClient()
                result = unsplash.search_and_download(
                    content_type=content.content_type.value,
                    high_res=True,  # Full-res for reel zoompan headroom
                )
                if result and result.get("local_path"):
                    raw_path = result["local_path"]
                    provider = ImageProvider.unsplash
                    logger.info(f"Unsplash fallback image for content #{content.id}")
            except Exception as e:
                logger.warning(f"Unsplash fallback also failed: {e}")

        # Process for each format
        for img_format, target_size in TARGET_SIZES.items():
            try:
                if raw_path:
                    processed_path = self._process_image(
                        raw_path=raw_path,
                        target_size=target_size,
                        content=content,
                        img_format=img_format,
                    )
                else:
                    # PIL-only: generate a simple branded image
                    processed_path = self._generate_branded_image(
                        target_size=target_size,
                        content=content,
                        img_format=img_format,
                    )

                if processed_path:
                    # Upload to R2 (or store locally in dev)
                    final_url = self._upload_to_storage(processed_path, content.id, img_format)

                    image_record = GeneratedImage(
                        content_id=content.id,
                        provider=provider,
                        format=img_format,
                        raw_url=raw_path,
                        final_url=final_url,
                        r2_key=f"content/{content.id}/{img_format.value}.jpg",
                        width=target_size[0],
                        height=target_size[1],
                    )
                    self.db.add(image_record)
                    images.append(image_record)

            except Exception as e:
                logger.error(f"Failed to process {img_format.value} for content #{content.id}: {e}")

        # Generate animated reel if content has a verse
        if raw_path and content.verse and content.verse.text:
            try:
                from core.images.reel_generator import generate_reel
                reel_path = generate_reel(
                    background_path=raw_path,
                    verse_text=content.verse.text,
                    verse_ref=content.verse.reference,
                    content_id=content.id,
                    translation=content.verse.translation or "WEB",
                    content_type=content.content_type.value,
                )
                if reel_path:
                    final_url = self._upload_to_storage(
                        reel_path, content.id, ImageFormat.reel_9x16,
                    )
                    reel_record = GeneratedImage(
                        content_id=content.id,
                        provider=provider,
                        format=ImageFormat.reel_9x16,
                        raw_url=raw_path,
                        final_url=final_url,
                        r2_key=f"content/{content.id}/reel_9x16.mp4",
                        width=1080,
                        height=1920,
                    )
                    self.db.add(reel_record)
                    images.append(reel_record)
                    logger.info(f"Reel generated for content #{content.id}")
            except Exception as e:
                logger.error(f"Reel generation failed for content #{content.id}: {e}")

        self.db.flush()
        return images

    def _process_image(
        self,
        raw_path: str,
        target_size: tuple[int, int],
        content: GeneratedContent,
        img_format: ImageFormat,
    ) -> Optional[str]:
        """Resize and optimize a raw image to target dimensions."""
        try:
            img = Image.open(raw_path)
        except Exception as e:
            logger.error(f"Failed to open image {raw_path}: {e}")
            return None

        # Convert to RGB if necessary
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize with crop to fill target dimensions
        img = self._resize_and_crop(img, target_size)

        # Add text overlay for story format
        if img_format == ImageFormat.story_9x16 and content.story_text:
            img = self._add_text_overlay(img, content.story_text)
        elif img_format in (ImageFormat.feed_4x5, ImageFormat.feed_1x1):
            content_type = content.content_type.value if content.content_type else "encouragement"
            # Hook-on-image: use short hook for overlays, full verse in caption
            hook_text = content.hook or content.caption_short or ""
            # Truncate long hooks to ~15 words for image readability
            words = hook_text.split()
            if len(words) > 15:
                hook_text = " ".join(words[:15]) + "..."

            # Extract verse data for bible_page overlay
            verse_text = ""
            verse_ref = ""
            verse_translation = ""
            if content.verse:
                verse_text = content.verse.text or ""
                verse_ref = content.verse.reference or ""
                verse_translation = content.verse.translation or "WEB"

            if hook_text or verse_text:
                img = _apply_feed_overlay(
                    img, hook_text, content.id, content_type,
                    verse_text=verse_text,
                    verse_ref=verse_ref,
                    verse_translation=verse_translation,
                )

        # Save
        output_path = IMAGES_PROCESSED_DIR / f"{content.id}_{img_format.value}.jpg"
        img.save(str(output_path), "JPEG", quality=92, optimize=True)
        logger.info(f"Processed image: {output_path}")

        return str(output_path)

    def _generate_branded_image(
        self,
        target_size: tuple[int, int],
        content: GeneratedContent,
        img_format: ImageFormat,
    ) -> Optional[str]:
        """Generate a branded image using one of several layout templates.

        Layout is selected based on content type for visual variety across the feed.
        """
        content_type = content.content_type.value if content.content_type else "encouragement"

        # Select layout based on content type for feed variety
        layout_map = {
            "daily_verse": "verse_card",
            "encouragement": "minimal_quote",
            "marriage_monday": "series_banner",
            "parenting_wednesday": "series_banner",
            "faith_friday": "series_banner",
            "viral_format": "bold_statement",
            "carousel": "minimal_quote",
            "reel_hook": "bold_statement",
            "gratitude": "verse_card",
            "prayer_prompt": "verse_card",
        }
        layout = layout_map.get(content_type, "minimal_quote")

        text = content.hook or content.caption_short or ""
        verse_ref = ""
        if hasattr(content, "verse") and content.verse and hasattr(content.verse, "reference"):
            verse_ref = content.verse.reference or ""

        series_label = ""
        if content_type == "marriage_monday":
            series_label = "Marriage Monday"
        elif content_type == "parenting_wednesday":
            series_label = "Parenting Wednesday"
        elif content_type == "faith_friday":
            series_label = "Faith Friday"

        img = _render_layout(
            layout=layout,
            target_size=target_size,
            text=text,
            verse_ref=verse_ref,
            series_label=series_label,
        )

        output_path = IMAGES_PROCESSED_DIR / f"{content.id}_{img_format.value}.jpg"
        img.save(str(output_path), "JPEG", quality=92)
        return str(output_path)

    @staticmethod
    def _resize_and_crop(img: Image.Image, target_size: tuple[int, int]) -> Image.Image:
        """Resize and center-crop image to exact target dimensions."""
        target_w, target_h = target_size
        target_ratio = target_w / target_h

        img_w, img_h = img.size
        img_ratio = img_w / img_h

        if img_ratio > target_ratio:
            # Image is wider — crop sides
            new_h = img_h
            new_w = int(img_h * target_ratio)
            left = (img_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, new_h))
        else:
            # Image is taller — crop top/bottom
            new_w = img_w
            new_h = int(img_w / target_ratio)
            top = (img_h - new_h) // 2
            img = img.crop((0, top, new_w, top + new_h))

        return img.resize(target_size, Image.Resampling.LANCZOS)

    @staticmethod
    def _add_text_overlay(
        img: Image.Image,
        text: str,
        position: str = "center",
    ) -> Image.Image:
        """Add text overlay with semi-transparent branded background."""
        draw = ImageDraw.Draw(img, "RGBA")
        width, height = img.size

        # Semi-transparent green overlay band
        band_height = height // 3
        band_top = (height - band_height) // 2
        draw.rectangle(
            [(0, band_top), (width, band_top + band_height)],
            fill=BRAND_COLORS["overlay_green"],
        )

        # Gold accent lines
        draw.line([(60, band_top + 8), (width - 60, band_top + 8)], fill=BRAND_COLORS["gold"], width=1)
        draw.line([(60, band_top + band_height - 8), (width - 60, band_top + band_height - 8)], fill=BRAND_COLORS["gold"], width=1)

        font = get_heading_font(52)
        lines = _wrap_text(text, font, width - 160)
        line_height = 64
        total_text_height = len(lines) * line_height
        y_start = band_top + (band_height - total_text_height) // 2

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            y = y_start + i * line_height
            draw.text((x, y), line, fill=BRAND_COLORS["cream"], font=font)

        return img

    def _upload_to_storage(self, local_path: str, content_id: int, img_format: ImageFormat) -> str:
        """Upload processed image/video to Cloudflare R2 or return local path.

        In development mode (no R2 configured), returns the local file path.
        In production, uploads to R2 and returns the public URL.
        """
        if not settings.has_r2:
            return f"file://{local_path}"

        try:
            import boto3

            s3 = boto3.client(
                "s3",
                endpoint_url=settings.cloudflare_r2_endpoint,
                aws_access_key_id=settings.cloudflare_r2_access_key,
                aws_secret_access_key=settings.cloudflare_r2_secret_key,
            )

            is_video = img_format == ImageFormat.reel_9x16
            ext = "mp4" if is_video else "jpg"
            content_type = "video/mp4" if is_video else "image/jpeg"
            key = f"content/{content_id}/{img_format.value}.{ext}"

            s3.upload_file(
                local_path,
                settings.cloudflare_r2_bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )

            # Public URL via R2 public dev URL or custom domain
            public_base = settings.cloudflare_r2_public_url.rstrip("/")
            url = f"{public_base}/{key}"
            if not url.startswith("https://"):
                logger.warning(f"R2 URL missing https: {url}")
                url = f"https://{url.lstrip('http://')}"
            logger.info(f"Uploaded to R2: {url}")
            return url

        except Exception as e:
            logger.error(f"R2 upload failed: {e}")
            return f"file://{local_path}"


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current_line = ""

    dummy_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def _draw_text_block(
    draw: ImageDraw.Draw,
    text: str,
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    max_width: int,
    color: tuple,
    align: str = "center",
    canvas_width: int = 1080,
    line_spacing: int = 10,
) -> int:
    """Draw a block of word-wrapped text. Returns total height drawn."""
    lines = _wrap_text(text, font, max_width)
    bbox_sample = draw.textbbox((0, 0), "Ay", font=font)
    line_height = (bbox_sample[3] - bbox_sample[1]) + line_spacing

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]

        if align == "center":
            lx = (canvas_width - text_width) // 2
        elif align == "right":
            lx = canvas_width - x - text_width
        else:
            lx = x

        draw.text((lx, y + i * line_height), line, fill=color, font=font)

    return len(lines) * line_height


def _draw_gradient(
    img: Image.Image,
    color_top: tuple[int, int, int],
    color_bottom: tuple[int, int, int],
) -> None:
    """Draw a vertical linear gradient on the image."""
    draw = ImageDraw.Draw(img)
    width, height = img.size
    for y in range(height):
        ratio = y / height
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _draw_decorative_cross(draw: ImageDraw.Draw, x: int, y: int, size: int, color: tuple) -> None:
    """Draw a small decorative cross symbol."""
    half = size // 2
    thickness = max(1, size // 8)
    draw.rectangle([(x - thickness, y - half), (x + thickness, y + half)], fill=color)
    draw.rectangle([(x - half, y - thickness), (x + half, y + thickness)], fill=color)


def _draw_ornament_line(
    draw: ImageDraw.Draw,
    y: int,
    width: int,
    color: tuple,
    style: str = "simple",
) -> None:
    """Draw a decorative horizontal line with optional center ornament."""
    margin = width // 6
    center = width // 2

    if style == "cross":
        draw.line([(margin, y), (center - 20, y)], fill=color, width=1)
        draw.line([(center + 20, y), (width - margin, y)], fill=color, width=1)
        _draw_decorative_cross(draw, center, y, 12, color)
    elif style == "diamond":
        draw.line([(margin, y), (center - 12, y)], fill=color, width=1)
        draw.line([(center + 12, y), (width - margin, y)], fill=color, width=1)
        # Small diamond
        draw.polygon([(center, y - 6), (center + 6, y), (center, y + 6), (center - 6, y)], fill=color)
    else:
        draw.line([(margin, y), (width - margin, y)], fill=color, width=2)


def _render_layout(
    layout: str,
    target_size: tuple[int, int],
    text: str,
    verse_ref: str = "",
    series_label: str = "",
) -> Image.Image:
    """Render a branded image using the specified layout template.

    Layouts:
        verse_card     — Centered verse text with ornamental dividers
        minimal_quote  — Clean quote layout with gold accents
        series_banner  — Series header with themed background
        bold_statement — Large text, high contrast for viral content
    """
    width, height = target_size

    if layout == "verse_card":
        return _layout_verse_card(width, height, text, verse_ref)
    elif layout == "series_banner":
        return _layout_series_banner(width, height, text, series_label)
    elif layout == "bold_statement":
        return _layout_bold_statement(width, height, text)
    else:
        return _layout_minimal_quote(width, height, text, verse_ref)


def _layout_verse_card(w: int, h: int, text: str, verse_ref: str) -> Image.Image:
    """Elegant verse card — cream gradient, centered text, ornamental dividers."""
    img = Image.new("RGB", (w, h))
    _draw_gradient(img, BRAND_COLORS["cream"], BRAND_COLORS["cream_dark"])
    draw = ImageDraw.Draw(img)

    margin = 80
    max_text_width = w - margin * 2

    # Top ornament line
    top_ornament_y = h // 5
    _draw_ornament_line(draw, top_ornament_y, w, BRAND_COLORS["gold"], style="cross")

    # Main verse text
    heading_font = get_heading_font(58)
    text_y = top_ornament_y + 50
    text_height = _draw_text_block(
        draw, text, heading_font, margin, text_y,
        max_width=max_text_width,
        color=BRAND_COLORS["green"],
        align="center",
        canvas_width=w,
        line_spacing=20,
    )

    # Bottom ornament line
    bottom_ornament_y = text_y + text_height + 40
    _draw_ornament_line(draw, bottom_ornament_y, w, BRAND_COLORS["gold"], style="diamond")

    # Verse reference
    if verse_ref:
        ref_font = get_accent_font(26)
        ref_y = bottom_ornament_y + 30
        _draw_text_block(
            draw, f"— {verse_ref}", ref_font, margin, ref_y,
            max_width=max_text_width,
            color=BRAND_COLORS["gold"],
            align="center",
            canvas_width=w,
        )

    # Subtle watermark at bottom
    watermark_font = get_body_font(16)
    _draw_text_block(
        draw, "@stillwatergrace", watermark_font, 0, h - 50,
        max_width=w,
        color=BRAND_COLORS["warm_gray"],
        align="center",
        canvas_width=w,
    )

    return img


def _layout_minimal_quote(w: int, h: int, text: str, verse_ref: str) -> Image.Image:
    """Clean minimal quote — white background, green text, gold accent bar."""
    img = Image.new("RGB", (w, h), BRAND_COLORS["white"])
    draw = ImageDraw.Draw(img)

    margin = 100

    # Left gold accent bar
    bar_x = margin - 30
    bar_top = h // 3
    bar_bottom = h * 2 // 3
    draw.rectangle([(bar_x, bar_top), (bar_x + 4, bar_bottom)], fill=BRAND_COLORS["gold"])

    # Main text centered vertically
    heading_font = get_heading_font(56)
    max_text_width = w - margin * 2
    text_y = h // 3
    text_height = _draw_text_block(
        draw, text, heading_font, margin, text_y,
        max_width=max_text_width,
        color=BRAND_COLORS["green"],
        align="center",
        canvas_width=w,
        line_spacing=18,
    )

    # Verse reference below text
    if verse_ref:
        ref_font = get_accent_font(24)
        ref_y = text_y + text_height + 30
        _draw_text_block(
            draw, f"— {verse_ref}", ref_font, margin, ref_y,
            max_width=max_text_width,
            color=BRAND_COLORS["gold"],
            align="center",
            canvas_width=w,
        )

    # Bottom gold line
    _draw_ornament_line(draw, h - 80, w, BRAND_COLORS["gold_light"], style="simple")

    # Watermark
    watermark_font = get_body_font(16)
    _draw_text_block(
        draw, "@stillwatergrace", watermark_font, 0, h - 50,
        max_width=w,
        color=BRAND_COLORS["warm_gray"],
        align="center",
        canvas_width=w,
    )

    return img


def _layout_series_banner(w: int, h: int, text: str, series_label: str) -> Image.Image:
    """Series banner — green header bar with series name, content below."""
    img = Image.new("RGB", (w, h))
    _draw_gradient(img, BRAND_COLORS["cream"], (255, 252, 245))
    draw = ImageDraw.Draw(img)

    margin = 80

    # Green header band at top
    band_height = h // 6
    draw.rectangle([(0, 0), (w, band_height)], fill=BRAND_COLORS["green"])

    # Series label in the band
    if series_label:
        label_font = get_body_font(32)
        _draw_text_block(
            draw, series_label.upper(), label_font, 0, band_height // 2 - 16,
            max_width=w - 60,
            color=BRAND_COLORS["gold"],
            align="center",
            canvas_width=w,
        )

    # Gold accent under band
    draw.rectangle([(0, band_height), (w, band_height + 4)], fill=BRAND_COLORS["gold"])

    # Main content text
    heading_font = get_heading_font(52)
    max_text_width = w - margin * 2
    text_y = band_height + 60 + (h - band_height - 200) // 4
    text_height = _draw_text_block(
        draw, text, heading_font, margin, text_y,
        max_width=max_text_width,
        color=BRAND_COLORS["green"],
        align="center",
        canvas_width=w,
        line_spacing=18,
    )

    # Decorative element below text
    ornament_y = text_y + text_height + 40
    _draw_ornament_line(draw, ornament_y, w, BRAND_COLORS["gold"], style="cross")

    # Watermark
    watermark_font = get_body_font(16)
    _draw_text_block(
        draw, "@stillwatergrace", watermark_font, 0, h - 50,
        max_width=w,
        color=BRAND_COLORS["warm_gray"],
        align="center",
        canvas_width=w,
    )

    return img


def _layout_bold_statement(w: int, h: int, text: str) -> Image.Image:
    """Bold statement — dark green background, large white/gold text for virality."""
    img = Image.new("RGB", (w, h))
    _draw_gradient(img, BRAND_COLORS["green"], (30, 55, 45))
    draw = ImageDraw.Draw(img)

    margin = 80
    max_text_width = w - margin * 2

    # Top gold line
    _draw_ornament_line(draw, h // 6, w, BRAND_COLORS["gold"], style="simple")

    # Large heading text
    heading_font = get_heading_font(68)
    text_y = h // 4
    _draw_text_block(
        draw, text, heading_font, margin, text_y,
        max_width=max_text_width,
        color=BRAND_COLORS["cream"],
        align="center",
        canvas_width=w,
        line_spacing=24,
    )

    # Bottom gold line
    _draw_ornament_line(draw, h * 5 // 6, w, BRAND_COLORS["gold"], style="diamond")

    # Watermark
    watermark_font = get_body_font(16)
    _draw_text_block(
        draw, "@stillwatergrace", watermark_font, 0, h - 50,
        max_width=w,
        color=BRAND_COLORS["gold_light"],
        align="center",
        canvas_width=w,
    )

    return img


# ── Feed Overlay Functions ──────────────────────────────────────────────────
# These composite bold text on top of existing photos (Unsplash).
# Designed for scroll-stopping readability at Instagram grid thumbnail size.


def _get_adaptive_font(text: str, max_width: int, start_size: int, min_size: int = 44, max_lines: int = 5):
    """Get font and wrapped lines, shrinking if text is too long."""
    size = start_size
    font = get_heading_font(size)
    lines = _wrap_text(text, font, max_width)
    while len(lines) > max_lines and size > min_size:
        size -= 6
        font = get_heading_font(size)
        lines = _wrap_text(text, font, max_width)
    return font, lines, size


def _select_overlay_style(content_id: int, content_type: str, has_verse: bool = False) -> str:
    """Select overlay style based on content type for feed variety."""
    if content_type == "daily_verse" and has_verse:
        return "bible_page"
    if content_type in ("viral_format", "reel_hook", "bold_statement"):
        return "dark_hero"
    if content_type in ("encouragement", "conviction_quote", "gratitude"):
        return "bold_text"
    if content_type in ("marriage_monday", "parenting_wednesday", "faith_friday"):
        return "bottom_band"
    styles = ["dark_hero", "bottom_band", "center_box", "bold_text"]
    return styles[content_id % 4]


def _apply_feed_overlay(
    img: Image.Image,
    text: str,
    content_id: int,
    content_type: str,
    verse_text: str = "",
    verse_ref: str = "",
    verse_translation: str = "",
) -> Image.Image:
    """Apply the appropriate overlay style to a feed image."""
    has_verse = bool(verse_text and verse_ref)
    style = _select_overlay_style(content_id, content_type, has_verse)
    if style == "bible_page":
        return _overlay_bible_page(img, verse_text, verse_ref, verse_translation)
    elif style == "dark_hero":
        return _overlay_dark_hero(img, text)
    elif style == "bottom_band":
        return _overlay_bottom_band(img, text)
    elif style == "bold_text":
        return _overlay_bold_text(img, text)
    else:
        return _overlay_center_box(img, text)


def _overlay_dark_hero(img: Image.Image, text: str) -> Image.Image:
    """Full dark wash over photo with large centered white text.

    Inspired by YouVersion's bold statement posts. High contrast,
    text fills most of the image, readable at any size.
    """
    img = img.convert("RGBA")
    w, h = img.size

    # Full dark wash
    dark = Image.new("RGBA", (w, h), BRAND_COLORS["overlay_dark_heavy"])
    img = Image.alpha_composite(img, dark)

    draw = ImageDraw.Draw(img)
    margin = 80
    max_text_width = w - margin * 2

    # Hook text — large, centered
    font, lines, font_size = _get_adaptive_font(text, max_text_width, 72)
    line_spacing = max(12, font_size // 5)

    # Measure total text height
    sample_bbox = draw.textbbox((0, 0), "Ay", font=font)
    line_h = (sample_bbox[3] - sample_bbox[1]) + line_spacing
    total_text_h = len(lines) * line_h

    text_y = (h - total_text_h) // 2 - 30  # slightly above center

    text_height = _draw_text_block(
        draw, text, font, margin, text_y,
        max_width=max_text_width,
        color=BRAND_COLORS["white_text"],
        align="center",
        canvas_width=w,
        line_spacing=line_spacing,
    )

    # Gold ornament line below text
    ornament_y = text_y + text_height + 30
    _draw_ornament_line(draw, ornament_y, w, BRAND_COLORS["gold"], style="simple")

    # Watermark
    wm_font = get_body_font(18)
    _draw_text_block(
        draw, "@stillwatergrace", wm_font, 0, h - 55,
        max_width=w,
        color=(255, 248, 240, 150),
        align="center",
        canvas_width=w,
    )

    return img.convert("RGB")


def _overlay_bottom_band(img: Image.Image, text: str) -> Image.Image:
    """Gradient band from bottom with text. Photo visible at top.

    Modern editorial style — the top portion shows the background photo
    while the bottom has a gradient fade to brand green with large text.
    """
    img = img.convert("RGBA")
    w, h = img.size

    # Draw gradient overlay on bottom 55% of image
    gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gradient_draw = ImageDraw.Draw(gradient)
    band_start = int(h * 0.45)
    gr, gg, gb = BRAND_COLORS["green"]
    for y in range(band_start, h):
        progress = (y - band_start) / (h - band_start)
        alpha = int(progress * 220)
        gradient_draw.line([(0, y), (w, y)], fill=(gr, gg, gb, alpha))

    img = Image.alpha_composite(img, gradient)
    draw = ImageDraw.Draw(img)

    margin = 80
    max_text_width = w - margin * 2

    # Gold accent line at gradient start
    draw.line([(margin, band_start + 10), (w - margin, band_start + 10)],
              fill=BRAND_COLORS["gold"], width=2)

    # Hook text — large, left-aligned in lower portion
    font, lines, font_size = _get_adaptive_font(text, max_text_width, 64)
    line_spacing = max(10, font_size // 5)

    sample_bbox = draw.textbbox((0, 0), "Ay", font=font)
    line_h = (sample_bbox[3] - sample_bbox[1]) + line_spacing
    total_text_h = len(lines) * line_h

    # Position text in the lower band area
    text_y = band_start + (h - band_start - total_text_h) // 2

    _draw_text_block(
        draw, text, font, margin, text_y,
        max_width=max_text_width,
        color=BRAND_COLORS["cream"],
        align="left",
        canvas_width=w,
        line_spacing=line_spacing,
    )

    # Watermark at bottom right
    wm_font = get_body_font(16)
    wm_bbox = draw.textbbox((0, 0), "@stillwatergrace", font=wm_font)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text((w - margin - wm_w, h - 45), "@stillwatergrace",
              fill=(255, 248, 240, 130), font=wm_font)

    return img.convert("RGB")


def _overlay_center_box(img: Image.Image, text: str) -> Image.Image:
    """Semi-transparent box centered on photo with text inside.

    Inspired by daily_bibleverses card style. Photo peeks above
    and below the text box, creating a layered look.
    """
    img = img.convert("RGBA")
    w, h = img.size

    # Slight overall darken so the box stands out
    darken = Image.new("RGBA", (w, h), (0, 0, 0, 60))
    img = Image.alpha_composite(img, darken)

    margin = 60
    max_text_width = w - margin * 2 - 80  # extra padding inside box

    # Measure text to size the box
    font, lines, font_size = _get_adaptive_font(text, max_text_width, 66)
    line_spacing = max(10, font_size // 5)

    dummy_draw = ImageDraw.Draw(img)
    sample_bbox = dummy_draw.textbbox((0, 0), "Ay", font=font)
    line_h = (sample_bbox[3] - sample_bbox[1]) + line_spacing
    total_text_h = len(lines) * line_h

    # Box dimensions
    box_padding_x = 50
    box_padding_y = 50
    box_w = w - margin * 2
    box_h = total_text_h + box_padding_y * 2
    box_x = margin
    box_y = (h - box_h) // 2

    # Draw the box on a separate layer
    box_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    box_draw = ImageDraw.Draw(box_layer)

    # Rounded rectangle (Pillow 8.2+) with fallback
    box_coords = (box_x, box_y, box_x + box_w, box_y + box_h)
    try:
        box_draw.rounded_rectangle(box_coords, radius=20,
                                   fill=BRAND_COLORS["overlay_green_box"])
    except AttributeError:
        box_draw.rectangle(box_coords, fill=BRAND_COLORS["overlay_green_box"])

    # Gold border
    try:
        box_draw.rounded_rectangle(box_coords, radius=20,
                                   outline=BRAND_COLORS["gold"], width=2)
    except AttributeError:
        box_draw.rectangle(box_coords, outline=BRAND_COLORS["gold"], width=2)

    img = Image.alpha_composite(img, box_layer)
    draw = ImageDraw.Draw(img)

    # Text centered inside box
    text_y = box_y + box_padding_y
    _draw_text_block(
        draw, text, font, box_x + box_padding_x, text_y,
        max_width=max_text_width,
        color=BRAND_COLORS["cream"],
        align="center",
        canvas_width=w,
        line_spacing=line_spacing,
    )

    # Watermark below box
    wm_font = get_body_font(16)
    _draw_text_block(
        draw, "@stillwatergrace", wm_font, 0, h - 50,
        max_width=w,
        color=(255, 248, 240, 130),
        align="center",
        canvas_width=w,
    )

    return img.convert("RGB")


def _overlay_bible_page(
    img: Image.Image,
    verse_text: str,
    verse_ref: str,
    translation: str = "WEB",
) -> Image.Image:
    """White Bible-page card over scenic photo with highlighted verse text.

    Inspired by YouVersion's reel style — a white card that looks like an
    actual Bible page, with verse reference header, formatted scripture text,
    and yellow highlighting behind key lines.
    """
    img = img.convert("RGBA")
    w, h = img.size

    # Normalize verse text — replace newlines with spaces
    verse_text = " ".join(verse_text.split())

    # Slight darken so white card pops
    darken = Image.new("RGBA", (w, h), (0, 0, 0, 50))
    img = Image.alpha_composite(img, darken)

    # Card dimensions — centered, generous padding
    card_margin_x = int(w * 0.08)
    card_w = w - card_margin_x * 2
    card_padding_x = 44
    card_padding_top = 55
    card_padding_bottom = 50
    text_area_w = card_w - card_padding_x * 2

    # Parse reference for display: "John 3:16" → book "John", chapter "3"
    ref_parts = verse_ref.split()
    book_name = " ".join(ref_parts[:-1]) if len(ref_parts) > 1 else verse_ref
    chapter_verse = ref_parts[-1] if len(ref_parts) > 1 else ""

    # Extract chapter number and starting verse for display
    chapter_num = ""
    verse_start_str = ""
    if ":" in chapter_verse:
        chapter_num, verse_start_str = chapter_verse.split(":", 1)
        if "-" in verse_start_str:
            verse_start_str = verse_start_str.split("-")[0]

    # Fonts — use adaptive sizing: larger for short verses, smaller for long
    header_font = get_body_font(24)
    verse_num_font = get_body_font(26)
    wm_font = get_body_font(16)

    # Adaptive verse font: start at 48pt, shrink if needed to fit card
    verse_font_names = [
        "georgia.ttf", "LiberationSerif-Regular.ttf", "DejaVuSerif.ttf",
        "times.ttf",
    ]
    font_size = 48
    verse_font = _resolve_font(verse_font_names, font_size)
    verse_lines = _wrap_text(verse_text, verse_font, text_area_w - 40)

    # If too many lines, shrink font
    max_verse_lines = 8
    while len(verse_lines) > max_verse_lines and font_size > 32:
        font_size -= 4
        verse_font = _resolve_font(verse_font_names, font_size)
        verse_lines = _wrap_text(verse_text, verse_font, text_area_w - 40)

    # Measure line height
    dummy = ImageDraw.Draw(img)
    sample_bbox = dummy.textbbox((0, 0), "Ay", font=verse_font)
    line_h = (sample_bbox[3] - sample_bbox[1]) + 16

    # Calculate card height with minimum
    header_h = 55
    verse_block_h = len(verse_lines) * line_h
    card_h = card_padding_top + header_h + verse_block_h + card_padding_bottom

    # Minimum card height: 40% of image for visual presence
    min_card_h = int(h * 0.40)
    max_card_h = int(h * 0.78)
    card_h = max(min_card_h, min(card_h, max_card_h))

    # Center card vertically, shifted slightly up
    card_x = card_margin_x
    card_y = (h - card_h) // 2 - int(h * 0.02)

    # ── Draw white card with shadow ──
    card_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_layer)

    shadow_coords = (card_x + 5, card_y + 5, card_x + card_w + 5, card_y + card_h + 5)
    try:
        card_draw.rounded_rectangle(shadow_coords, radius=16, fill=(0, 0, 0, 45))
    except AttributeError:
        card_draw.rectangle(shadow_coords, fill=(0, 0, 0, 45))

    card_coords = (card_x, card_y, card_x + card_w, card_y + card_h)
    try:
        card_draw.rounded_rectangle(card_coords, radius=16, fill=(255, 255, 255, 248))
    except AttributeError:
        card_draw.rectangle(card_coords, fill=(255, 255, 255, 248))

    img = Image.alpha_composite(img, card_layer)

    # ── All highlights drawn on a single layer for efficiency ──
    hl_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hl_draw = ImageDraw.Draw(hl_layer)
    highlight_color = (255, 243, 115, 170)

    draw = ImageDraw.Draw(img)

    # ── Header: "Book Chapter  |  Translation" ──
    header_text = f"{book_name} {chapter_num}" if chapter_num else verse_ref
    header_text += f"  |  {translation.upper()}"
    header_x = card_x + card_padding_x
    header_y = card_y + card_padding_top
    draw.text((header_x, header_y), header_text, fill=(120, 115, 110), font=header_font)

    # Thin separator line below header
    sep_y = header_y + 40
    draw.line(
        [(header_x, sep_y), (card_x + card_w - card_padding_x, sep_y)],
        fill=(215, 215, 215), width=1,
    )

    # ── Verse text with yellow highlighting ──
    text_x = header_x + 4
    text_y = sep_y + 22
    verse_num_text = f"{verse_start_str} " if verse_start_str else ""

    # Center verse block vertically within remaining card space
    remaining_space = (card_y + card_h - card_padding_bottom) - text_y
    total_verse_h = len(verse_lines) * line_h
    if total_verse_h < remaining_space:
        text_y += (remaining_space - total_verse_h) // 2

    for i, line in enumerate(verse_lines):
        y = text_y + i * line_h

        if y + line_h > card_y + card_h - card_padding_bottom:
            break

        x_offset = 0
        if i == 0 and verse_num_text:
            num_bbox = draw.textbbox((0, 0), verse_num_text, font=verse_num_font)
            num_w = num_bbox[2] - num_bbox[0]
            # Draw verse number in gold (on main image, not highlight layer)
            draw.text((text_x, y + 2), verse_num_text, fill=BRAND_COLORS["gold"], font=verse_num_font)
            x_offset = num_w + 4

        # Measure text for highlight rectangle
        line_bbox = draw.textbbox((0, 0), line, font=verse_font)
        line_w = line_bbox[2] - line_bbox[0]
        line_text_h = line_bbox[3] - line_bbox[1]

        # Draw highlight on shared layer
        hl_draw.rectangle(
            [(text_x + x_offset - 4, y - 3),
             (text_x + x_offset + line_w + 4, y + line_text_h + 5)],
            fill=highlight_color,
        )

    # Composite all highlights at once, then redraw text on top
    img = Image.alpha_composite(img, hl_layer)
    draw = ImageDraw.Draw(img)

    # Draw text on top of highlights
    for i, line in enumerate(verse_lines):
        y = text_y + i * line_h

        if y + line_h > card_y + card_h - card_padding_bottom:
            break

        x_offset = 0
        if i == 0 and verse_num_text:
            num_bbox = draw.textbbox((0, 0), verse_num_text, font=verse_num_font)
            x_offset = (num_bbox[2] - num_bbox[0]) + 4

        draw.text((text_x + x_offset, y), line, fill=(50, 50, 50), font=verse_font)

    # Re-draw verse number on top of highlight
    if verse_num_text and verse_lines:
        draw.text((text_x, text_y + 2), verse_num_text, fill=BRAND_COLORS["gold"], font=verse_num_font)

    # ── Watermark at bottom-right of card ──
    wm_text = "@stillwatergrace"
    wm_bbox = draw.textbbox((0, 0), wm_text, font=wm_font)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text(
        (card_x + card_w - card_padding_x - wm_w, card_y + card_h - 35),
        wm_text, fill=(180, 170, 160), font=wm_font,
    )

    return img.convert("RGB")


def _overlay_bold_text(img: Image.Image, text: str) -> Image.Image:
    """Massive text filling 70-80% of the frame on a lightly washed photo.

    Inspired by @bible_verses365_ style — ALL CAPS bold serif text directly
    on the photo with a subtle dark wash. Thumb-stopping at grid level.
    """
    img = img.convert("RGBA")
    w, h = img.size

    # Light dark wash — lighter than dark_hero (alpha ~100)
    wash = Image.new("RGBA", (w, h), (0, 0, 0, 110))
    img = Image.alpha_composite(img, wash)

    draw = ImageDraw.Draw(img)
    margin = 60
    max_text_width = w - margin * 2

    # ALL CAPS for maximum impact
    display_text = text.upper()

    # Use larger start size for bold impact — 96pt down to 56pt
    font, lines, font_size = _get_adaptive_font(
        display_text, max_text_width, start_size=96, min_size=56, max_lines=6
    )
    line_spacing = max(14, font_size // 4)

    # Measure total text height
    sample_bbox = draw.textbbox((0, 0), "AY", font=font)
    line_h = (sample_bbox[3] - sample_bbox[1]) + line_spacing
    total_text_h = len(lines) * line_h

    # Center vertically, offset slightly upward
    text_y = (h - total_text_h) // 2 - 40

    # Draw text with slight shadow for depth
    shadow_offset = max(2, font_size // 30)
    _draw_text_block(
        draw, display_text, font, margin + shadow_offset, text_y + shadow_offset,
        max_width=max_text_width,
        color=(0, 0, 0, 80),
        align="center",
        canvas_width=w,
        line_spacing=line_spacing,
    )

    # Main text — bright white
    _draw_text_block(
        draw, display_text, font, margin, text_y,
        max_width=max_text_width,
        color=BRAND_COLORS["white_text"],
        align="center",
        canvas_width=w,
        line_spacing=line_spacing,
    )

    # Small gold watermark at bottom
    ref_font = get_body_font(22)
    _draw_text_block(
        draw, "@stillwatergrace", ref_font, 0, h - 60,
        max_width=w,
        color=BRAND_COLORS["gold"],
        align="center",
        canvas_width=w,
    )

    return img.convert("RGB")
