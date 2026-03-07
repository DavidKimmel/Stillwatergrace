"""PDF renderer using WeasyPrint + Jinja2 HTML templates.

Renders a devotional theme into a branded multi-page PDF.
"""

import logging
from pathlib import Path, PurePosixPath

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "devotional"


class DevotionalPDFRenderer:
    """Renders devotional content into a branded PDF."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True,
        )

    def render(
        self,
        title: str,
        subtitle: str,
        description: str,
        days: list[dict],
        output_path: str,
        cover_image: str | None = None,
    ) -> str:
        """Render a complete devotional PDF.

        Args:
            title: Devotional title.
            subtitle: Subtitle line.
            description: Welcome page description text.
            days: List of day dicts with keys: day_number, day_title,
                  verse_ref, verse_text, reflection, prayer, questions,
                  image_path (optional, absolute path or None).
            output_path: Where to save the PDF.
            cover_image: Optional cover image path.

        Returns:
            Path to the generated PDF file.
        """
        # Convert local file paths to file:// URIs for WeasyPrint
        if cover_image:
            cover_image = Path(cover_image).as_uri()
        for day in days:
            if day.get("image_path"):
                day["image_path"] = Path(day["image_path"]).as_uri()

        template = self.env.get_template("devotional.html")
        html_content = template.render(
            title=title,
            subtitle=subtitle,
            description=description,
            days=days,
            cover_image=cover_image,
        )

        base_url = str(self.templates_dir)
        html = HTML(string=html_content, base_url=base_url)
        html.write_pdf(output_path)

        output = Path(output_path)
        size_kb = output.stat().st_size / 1024
        logger.info(f"Generated PDF: {output_path} ({size_kb:.0f} KB)")
        return str(output)
