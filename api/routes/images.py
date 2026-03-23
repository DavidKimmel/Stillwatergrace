"""Image library browsing API routes."""

from typing import Optional

from fastapi import APIRouter, Query

from core.images.catalog import ImageCatalog, THEME_FOLDERS

router = APIRouter()


@router.get("/library")
def get_image_library(
    theme: Optional[str] = Query(None, description="Filter by theme folder"),
    unused: bool = Query(False, description="Only show unused images"),
) -> dict:
    """Browse the image catalog with optional filters."""
    catalog = ImageCatalog()

    if theme and unused:
        images = catalog.find_unused(theme)
    elif theme:
        images = catalog.find_by_theme(theme)
    elif unused:
        # Gather unused images across all themes
        images = []
        for t in THEME_FOLDERS:
            images.extend(catalog.find_unused(t))
    else:
        images = list(catalog._entries)

    return {
        "images": images,
        "total": len(images),
        "themes": list(THEME_FOLDERS),
    }
