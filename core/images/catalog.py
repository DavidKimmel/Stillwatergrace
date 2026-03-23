"""Image catalog for organizing and reusing background images by theme."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

IMAGES_BASE_DIR = Path(__file__).parent.parent.parent / "images"

THEME_FOLDERS = ["nature", "people", "faith", "dramatic", "interactive", "botanical"]

_CONTENT_TYPE_THEME: dict[str, str] = {
    "daily_verse": "nature",
    "encouragement": "nature",
    "gratitude": "nature",
    "fill_in_blank": "nature",
    "marriage_monday": "people",
    "parenting_wednesday": "people",
    "faith_friday": "faith",
    "prayer_prompt": "faith",
    "christian_quote": "faith",
    "conviction_quote": "dramatic",
    "reel": "dramatic",
    "this_or_that": "interactive",
    "carousel": "botanical",
}


def theme_for_content_type(content_type: str) -> str:
    """Map a content type to its image theme folder. Defaults to 'nature'."""
    return _CONTENT_TYPE_THEME.get(content_type, "nature")


class ImageCatalog:
    """Manages a JSON catalog of background images organized by theme."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or IMAGES_BASE_DIR
        self._catalog_path = self._base_dir / "catalog.json"
        self._raw_dir = self._base_dir / "raw"
        self._entries: list[dict[str, Any]] = self._load()
        self._ensure_theme_dirs()

    def _ensure_theme_dirs(self) -> None:
        for theme in THEME_FOLDERS:
            (self._raw_dir / theme).mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if self._catalog_path.exists():
            try:
                return json.loads(self._catalog_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load catalog: {e}")
        return []

    def _save(self) -> None:
        self._catalog_path.write_text(
            json.dumps(self._entries, indent=2, default=str),
            encoding="utf-8",
        )

    def register(
        self,
        image_id: str,
        provider: str,
        theme: str,
        filename: str,
        content_type: str,
        content_id: Optional[int] = None,
        prompt_or_query: str = "",
        photographer: str = "",
        attribution: str = "",
    ) -> dict[str, Any]:
        """Register an image in the catalog. If it already exists, update used_by."""
        existing = next((e for e in self._entries if e["id"] == image_id), None)

        if existing:
            if content_id and content_id not in existing["used_by"]:
                existing["used_by"].append(content_id)
            self._save()
            return existing

        entry = {
            "id": image_id,
            "provider": provider,
            "theme": theme,
            "filename": filename,
            "prompt_or_query": prompt_or_query,
            "content_type": content_type,
            "used_by": [content_id] if content_id else [],
            "photographer": photographer,
            "attribution": attribution,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._entries.append(entry)
        self._save()
        return entry

    def get_save_path(self, theme: str, filename: str) -> Path:
        """Return the full path for saving a new image, ensuring the theme dir exists."""
        theme_dir = self._raw_dir / theme
        theme_dir.mkdir(parents=True, exist_ok=True)
        return theme_dir / filename

    def find_by_id(self, image_id: str) -> Optional[dict[str, Any]]:
        """Return a single catalog entry by ID, or None if not found."""
        return next((e for e in self._entries if e["id"] == image_id), None)

    def find_by_theme(self, theme: str) -> list[dict[str, Any]]:
        """Return all catalog entries for a given theme."""
        return [e for e in self._entries if e["theme"] == theme]

    def find_unused(self, theme: str) -> list[dict[str, Any]]:
        """Return catalog entries in a theme that have never been used by content."""
        return [e for e in self._entries if e["theme"] == theme and not e["used_by"]]
