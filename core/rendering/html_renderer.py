"""HTML-to-image renderer using Playwright."""
from __future__ import annotations

import html
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "images"


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


def render_html_to_image(
    template_name: str,
    variables: dict[str, Any],
    output_path: str,
    width: int = 1080,
    height: int = 1080,
) -> str | None:
    """Render an HTML template to a PNG image.

    Uses a fresh Playwright browser per call to avoid threading issues
    in multi-threaded FastAPI/Celery environments.
    """
    try:
        from jinja2 import Environment, FileSystemLoader
        from playwright.sync_api import sync_playwright

        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=False,
        )
        template = env.get_template(template_name)
        rendered_html = template.render(**variables)

        # Write temp HTML inside templates dir so relative CSS/asset paths resolve
        temp_html = TEMPLATES_DIR / f"_render_{Path(output_path).stem}.html"
        temp_html.write_text(rendered_html, encoding="utf-8")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu"],
            )
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"file://{temp_html.resolve()}")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=output_path, type="png")
            browser.close()

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
    """Render a scripture single post image."""
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
    """Render 3 carousel slide images. Returns list of PNG paths."""
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
