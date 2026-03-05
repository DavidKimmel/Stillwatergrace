"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import AliasChoices, Field


class Settings(BaseSettings):
    """All application settings, loaded from .env file."""

    # Database
    database_url: str = "postgresql://faithpage:faithpage@localhost:5432/faithpage"
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic (Claude API)
    anthropic_api_key: str = ""

    # Canva
    canva_client_id: str = ""
    canva_client_secret: str = ""

    # Instagram / Meta
    instagram_access_token: str = ""
    instagram_business_account_id: str = ""
    facebook_page_id: str = ""
    meta_app_id: str = ""
    meta_app_secret: str = ""

    # TikTok
    tiktok_access_token: str = ""
    tiktok_client_key: str = ""

    # Cloudflare R2
    cloudflare_r2_access_key: str = ""
    cloudflare_r2_secret_key: str = ""
    cloudflare_r2_bucket: str = "stillwatergrace-images"
    cloudflare_r2_endpoint: str = ""
    cloudflare_r2_public_url: str = ""  # e.g. https://pub-xxx.r2.dev

    # Email (SendGrid)
    sendgrid_api_key: str = ""
    alert_email_to: str = ""
    alert_email_from: str = "noreply@stillwatergrace.com"

    # Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "StillWaterGrace/1.0"

    # Unsplash
    unsplash_access_key: str = ""

    # ElevenLabs (TTS narration + music generation)
    elevenlabs_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("elevenlabs_api_key", "ellevenlabs_api_key"),
    )
    reel_narration_enabled: bool = True

    # ConvertKit
    convertkit_api_key: str = ""

    # Monetization
    gumroad_access_token: str = ""
    amazon_associates_tag: str = ""

    # App
    app_env: str = "development"
    app_secret_key: str = "change-me-to-a-random-string"
    timezone: str = "America/New_York"
    auto_approve_content: bool = False
    reel_music_enabled: bool = True
    reel_motion_style: str = "ken_burns"  # ken_burns or static

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def has_instagram(self) -> bool:
        return bool(self.instagram_access_token and self.instagram_business_account_id)

    @property
    def has_facebook(self) -> bool:
        return bool(self.instagram_access_token and self.facebook_page_id)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_r2(self) -> bool:
        return bool(
            self.cloudflare_r2_access_key
            and self.cloudflare_r2_secret_key
            and self.cloudflare_r2_endpoint
            and self.cloudflare_r2_public_url
        )

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key)

    @property
    def has_reddit(self) -> bool:
        return bool(self.reddit_client_id and self.reddit_client_secret)


settings = Settings()
