"""Migrate raw images into themed folders using DB content types.

Looks up each image's content type from the database via raw_url,
then moves it into the correct theme folder and updates the catalog.

Usage:
    docker compose exec api python scripts/migrate_images.py
    python scripts/migrate_images.py  (local)
"""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.images.catalog import (
    ImageCatalog,
    IMAGES_BASE_DIR,
    theme_for_content_type,
    THEME_FOLDERS,
)

RAW_DIR = IMAGES_BASE_DIR / "raw"


def _build_photo_id_to_content_type() -> dict[str, str]:
    """Query DB to map unsplash photo IDs and fal filenames to content types."""
    from database.session import get_db
    from database.models import GeneratedImage, GeneratedContent

    mapping: dict[str, str] = {}

    with get_db() as db:
        images = db.query(GeneratedImage).filter(
            GeneratedImage.raw_url.isnot(None)
        ).all()

        for img in images:
            raw_url = img.raw_url or ""
            filename = Path(raw_url).stem  # e.g. "unsplash_abc123" or "20260310_000317_752010211"

            content = db.query(GeneratedContent).filter_by(id=img.content_id).first()
            if content and content.content_type:
                content_type = content.content_type.value
                # Store by filename stem for matching
                if filename not in mapping:
                    mapping[filename] = content_type

    return mapping


def migrate() -> None:
    # Build lookup from DB
    print("Looking up content types from database...")
    photo_to_type = _build_photo_id_to_content_type()
    print(f"  Found {len(photo_to_type)} image-to-content-type mappings")

    catalog = ImageCatalog()

    # Clear existing catalog to rebuild with correct themes
    catalog._entries = []
    catalog._save()

    moved = 0
    by_theme: dict[str, int] = {t: 0 for t in THEME_FOLDERS}

    # Scan all files — both flat root and already-migrated theme dirs
    all_files: list[tuple[Path, bool]] = []

    # Files in theme subdirs (from previous migration)
    for theme_dir in RAW_DIR.iterdir():
        if not theme_dir.is_dir() or theme_dir.name not in THEME_FOLDERS:
            continue
        for f in theme_dir.iterdir():
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                all_files.append((f, True))

    # Files still in flat root
    for f in RAW_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
            all_files.append((f, False))

    for f, already_in_theme_dir in all_files:
        # Determine provider
        if f.name.startswith("unsplash_"):
            provider = "unsplash"
            image_id = f"unsplash_{f.stem.replace('unsplash_', '')}"
        elif f.name.startswith("ai_"):
            provider = "fal"
            image_id = f"fal_{f.stem.replace('ai_', '')}"
        else:
            provider = "fal"
            image_id = f"fal_{f.stem}"

        # Look up content type from DB, default to unknown
        content_type = photo_to_type.get(f.stem, "unknown")
        theme = theme_for_content_type(content_type) if content_type != "unknown" else "nature"

        dest = catalog.get_save_path(theme, f.name)

        # Move if not already in the correct location
        if f != dest:
            if dest.exists():
                # Same filename already in target — skip
                continue
            shutil.move(str(f), str(dest))

        catalog.register(
            image_id=image_id,
            provider=provider,
            theme=theme,
            filename=f"{theme}/{f.name}",
            content_type=content_type,
        )
        by_theme[theme] = by_theme.get(theme, 0) + 1
        moved += 1

    print(f"\nMigration complete: {moved} images cataloged")
    for theme, count in sorted(by_theme.items()):
        if count:
            print(f"  {theme}: {count}")
    print(f"\nCatalog: {len(catalog._entries)} entries in images/catalog.json")


if __name__ == "__main__":
    migrate()
