"""HTML-to-image renderer using Playwright."""
from __future__ import annotations

import html
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "images"

_browser = None
_playwright = None


def apply_highlights(text: str, highlights: list[str]) -> str:
    """Wrap matching phrases in highlight spans. Case-sensitive exact match."""
    result = text
    for phrase in highlights:
        if phrase in result:
            escaped = html.escape(phrase)
            result = result.replace(
                phrase, f'<span class="highlight">{escaped}</span>'
            )
    return result


def _get_browser():
    """Get or create a persistent browser instance."""
    global _browser, _playwright
    if _browser is None or not _browser.is_connected():
        from playwright.sync_api import sync_playwright

        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        logger.info("Playwright browser launched")
    return _browser


def render_html_to_image(
    template_name: str,
    variables: dict[str, Any],
    output_path: str,
    width: int = 1080,
    height: int = 1080,
) -> str | None:
    """Render an HTML template to a PNG image.

    Args:
        template_name: Filename of the template in TEMPLATES_DIR.
        variables: Template variables passed to Jinja2.
        output_path: Destination path for the rendered PNG.
        width: Viewport width in pixels.
        height: Viewport height in pixels.

    Returns:
        The output_path on success, or None on failure.
    """
    try:
        from jinja2 import Environment, FileSystemLoader

        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=False,
        )
        template = env.get_template(template_name)
        rendered_html = template.render(**variables)

        temp_html = Path(output_path).with_suffix(".html")
        temp_html.parent.mkdir(parents=True, exist_ok=True)
        temp_html.write_text(rendered_html, encoding="utf-8")

        browser = _get_browser()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(f"file://{temp_html.resolve()}")
        page.wait_for_load_state("networkidle")

        page.screenshot(path=output_path, type="png")
        page.close()

        temp_html.unlink(missing_ok=True)

        logger.info(
            "Rendered %s -> %s (%dx%d)", template_name, output_path, width, height
        )
        return output_path

    except Exception as e:
        logger.error("HTML render failed: %s", e)
        return None


def render_scripture_image(
    verse_text: str,
    verse_reference: str,
    highlights: list[str],
    output_path: str,
) -> str | None:
    """Render a scripture single post image.

    Args:
        verse_text: The verse body text.
        verse_reference: The reference string (e.g. "Psalm 46:10").
        highlights: Phrases to wrap in highlight spans.
        output_path: Destination path for the rendered PNG.

    Returns:
        The output_path on success, or None on failure.
    """
    verse_html = apply_highlights(verse_text, highlights)
    return render_html_to_image(
        template_name="scripture_single.html",
        variables={"verse_html": verse_html, "verse_reference": verse_reference},
        output_path=output_path,
    )


def render_carousel_images(
    cover_text: str,
    cover_highlights: list[str],
    content_text: str,
    content_highlights: list[str],
    verse_text: str,
    verse_reference: str,
    verse_highlights: list[str],
    output_dir: str,
    content_id: int,
) -> list[str]:
    """Render 3 carousel slide images.

    Args:
        cover_text: Text for the cover slide.
        cover_highlights: Highlight phrases for the cover.
        content_text: Text for the content slide.
        content_highlights: Highlight phrases for the content.
        verse_text: Scripture verse text for the CTA slide.
        verse_reference: Verse reference for the CTA slide.
        verse_highlights: Highlight phrases for the verse.
        output_dir: Directory to write the slide PNGs into.
        content_id: Content ID used in filenames.

    Returns:
        List of successfully rendered PNG paths.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results: list[str] = []

    slides = [
        (
            "carousel_cover.html",
            {"cover_html": apply_highlights(cover_text, cover_highlights)},
        ),
        (
            "carousel_content.html",
            {"content_html": apply_highlights(content_text, content_highlights)},
        ),
        (
            "carousel_cta.html",
            {
                "verse_html": apply_highlights(verse_text, verse_highlights),
                "verse_reference": verse_reference,
            },
        ),
    ]

    for i, (template, variables) in enumerate(slides):
        path = f"{output_dir}/carousel_{content_id}_slide{i + 1}.png"
        result = render_html_to_image(template, variables, path)
        if result:
            results.append(result)
        else:
            logger.error(
                "Failed to render carousel slide %d for content #%d",
                i + 1,
                content_id,
            )

    return results
