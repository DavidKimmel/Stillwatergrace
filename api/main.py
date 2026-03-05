"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import content, analytics, monetization, dashboard
from core.config import settings

app = FastAPI(
    title="StillWaterGrace",
    description="Automated faith & family social media content platform",
    version="0.1.0",
)

# CORS — allow dashboard dev server and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5175",  # Docker dashboard
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {
        "status": "ok",
        "env": settings.app_env,
        "services": {
            "anthropic": settings.has_anthropic,
            "instagram": settings.has_instagram,
            "reddit": settings.has_reddit,
        },
    }


# Serve processed images as static files
_images_dir = Path(__file__).resolve().parent.parent / "images" / "processed"
if _images_dir.is_dir():
    app.mount("/static/images", StaticFiles(directory=str(_images_dir)), name="images")

app.include_router(content.router, prefix="/api/content", tags=["content"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(monetization.router, prefix="/api/monetization", tags=["monetization"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
