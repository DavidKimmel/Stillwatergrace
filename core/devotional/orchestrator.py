"""Devotional generation orchestrator.

Coordinates: theme config -> verse fetch -> Claude reflections ->
Unsplash images -> PDF rendering -> R2 upload.
"""

import logging
import random
from pathlib import Path

from core.config import settings
from core.devotional.generator import DevotionalGenerator
from core.devotional.pdf_renderer import DevotionalPDFRenderer
from core.devotional.themes import get_theme
from core.images.unsplash_client import UnsplashClient

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "devotionals"


class DevotionalOrchestrator:
    """End-to-end devotional PDF generation."""

    def __init__(self) -> None:
        self.generator = DevotionalGenerator()
        self.renderer = DevotionalPDFRenderer()
        self.unsplash = UnsplashClient()

    def _download_image(self, keywords: list[str]) -> str | None:
        """Download an image from Unsplash using mood keywords."""
        query = random.choice(keywords)
        try:
            result = self.unsplash.search_and_download(
                content_type="daily_verse",
                custom_query=query,
                high_res=True,
            )
            if result and result.get("local_path"):
                return result["local_path"]
        except Exception as e:
            logger.warning(f"Unsplash download failed for '{query}': {e}")
        return None

    def generate(self, theme_slug: str, output_dir: Path | None = None) -> str:
        """Generate a complete devotional PDF.

        Args:
            theme_slug: Theme identifier (e.g., 'finding_peace').
            output_dir: Optional output directory override.

        Returns:
            Path to the generated PDF file.
        """
        theme = get_theme(theme_slug)
        out_dir = output_dir or OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir / f"{theme.slug}.pdf")

        logger.info(f"Generating devotional: {theme.title}")

        # 1. Generate all devotional text via Claude API
        logger.info("Step 1/3: Generating devotional reflections...")
        day_contents = self.generator.generate_all_days(theme)

        # 2. Download images from Unsplash
        logger.info("Step 2/3: Downloading images...")
        cover_image = self._download_image(theme.cover_keywords)

        for day_config, day_content in zip(theme.days, day_contents):
            img_path = self._download_image(day_config.mood_keywords)
            day_content["image_path"] = img_path

        # 3. Render PDF
        logger.info("Step 3/3: Rendering PDF...")
        result = self.renderer.render(
            title=theme.title,
            subtitle=theme.subtitle,
            description=theme.description,
            days=day_contents,
            output_path=output_path,
            cover_image=cover_image,
        )

        logger.info(f"Devotional PDF generated: {result}")
        return result

    def generate_and_upload(self, theme_slug: str) -> str:
        """Generate PDF and upload to R2. Returns public URL."""
        import boto3

        pdf_path = self.generate(theme_slug)
        theme = get_theme(theme_slug)

        if not settings.cloudflare_r2_access_key:
            logger.warning("R2 not configured — PDF saved locally only")
            return pdf_path

        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=settings.cloudflare_r2_endpoint,
                aws_access_key_id=settings.cloudflare_r2_access_key,
                aws_secret_access_key=settings.cloudflare_r2_secret_key,
            )

            key = f"devotionals/{theme.slug}.pdf"
            s3.upload_file(
                pdf_path,
                settings.cloudflare_r2_bucket,
                key,
                ExtraArgs={"ContentType": "application/pdf"},
            )

            public_base = settings.cloudflare_r2_public_url.rstrip("/")
            url = f"{public_base}/{key}"
            logger.info(f"Uploaded to R2: {url}")
            return url

        except Exception as e:
            logger.error(f"R2 upload failed: {e}")
            return pdf_path
