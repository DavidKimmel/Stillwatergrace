"""TikTok Content Posting API client.

Handles OAuth 2.0 authorization and video publishing via the Content Posting API.
Uses file upload (push) method since our R2 domain isn't verified for pull.

API docs: https://developers.tiktok.com/doc/content-posting-api-get-started
OAuth docs: https://developers.tiktok.com/doc/login-kit-web

Scopes: user.info.basic, video.publish, video.upload
"""

import logging
import re
import time
from pathlib import Path
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
ENV_FILE = Path(__file__).parent.parent.parent / ".env"

# Video constraints
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_RETRIES = 3
RETRY_DELAY = 30


def get_auth_url(redirect_uri: str) -> str:
    """Build the TikTok OAuth authorization URL."""
    import urllib.parse

    params = {
        "client_key": settings.tiktok_client_key,
        "scope": "user.info.basic,video.publish,video.upload",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": "stillwatergrace",
    }
    return f"{TIKTOK_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code: str, redirect_uri: str) -> Optional[dict]:
    """Exchange an authorization code for an access token.

    Returns dict with access_token, refresh_token, expires_in, open_id.
    """
    url = f"{TIKTOK_API_BASE}/oauth/token/"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                data={
                    "client_key": settings.tiktok_client_key,
                    "client_secret": settings.tiktok_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            data = response.json()
    except Exception as e:
        logger.error(f"TikTok token exchange failed: {e}")
        return None

    if data.get("error"):
        logger.error(f"TikTok token error: {data.get('error_description', data.get('error'))}")
        return None

    token_data = {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in"),
        "open_id": data.get("open_id"),
    }

    # Save to .env
    if token_data["access_token"]:
        _update_env("TIKTOK_ACCESS_TOKEN", token_data["access_token"])
        settings.tiktok_access_token = token_data["access_token"]
        if token_data["refresh_token"]:
            _update_env("TIKTOK_REFRESH_TOKEN", token_data["refresh_token"])
        logger.info("TikTok access token saved to .env")

    return token_data


def refresh_tiktok_token() -> Optional[str]:
    """Refresh the TikTok access token using the refresh token."""
    refresh_token = _get_env_value("TIKTOK_REFRESH_TOKEN")
    if not refresh_token:
        logger.error("No TikTok refresh token available")
        return None

    url = f"{TIKTOK_API_BASE}/oauth/token/"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                data={
                    "client_key": settings.tiktok_client_key,
                    "client_secret": settings.tiktok_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            data = response.json()
    except Exception as e:
        logger.error(f"TikTok token refresh failed: {e}")
        return None

    if data.get("error"):
        logger.error(f"TikTok refresh error: {data.get('error_description')}")
        return None

    new_token = data.get("access_token")
    new_refresh = data.get("refresh_token")

    if new_token:
        _update_env("TIKTOK_ACCESS_TOKEN", new_token)
        settings.tiktok_access_token = new_token
        if new_refresh:
            _update_env("TIKTOK_REFRESH_TOKEN", new_refresh)
        logger.info("TikTok token refreshed successfully")

    return new_token


class TikTokClient:
    """Client for posting videos to TikTok via Content Posting API."""

    def __init__(self):
        self.access_token = settings.tiktok_access_token
        self.mock_mode = not bool(self.access_token)

        if self.mock_mode:
            logger.warning("TikTok client running in mock mode (no access token)")

        self.client = httpx.Client(timeout=60.0)

    def publish_video(
        self,
        video_url: str,
        caption: str,
        disable_comment: bool = False,
    ) -> Optional[dict]:
        """Publish a video to TikTok by downloading from URL and uploading via file.

        Steps:
        1. Download video from R2 URL
        2. Initialize upload with TikTok
        3. Upload video bytes to TikTok's upload URL
        4. Wait for publish to complete
        """
        if self.mock_mode:
            logger.info(f"[MOCK TikTok] Would post video: {caption[:50]}...")
            return {"mock": True, "status": "would_post"}

        try:
            # Step 1: Download video from R2
            logger.info(f"Downloading video from {video_url[:80]}...")
            video_response = self.client.get(video_url)
            video_response.raise_for_status()
            video_bytes = video_response.content
            video_size = len(video_bytes)

            if video_size > MAX_VIDEO_SIZE:
                raise ValueError(f"Video too large: {video_size / 1024 / 1024:.1f} MB (max 50 MB)")

            logger.info(f"Downloaded video: {video_size / 1024:.0f} KB")

            # Step 2: Initialize upload
            init_data = self._init_upload(
                video_size=video_size,
                caption=caption,
                disable_comment=disable_comment,
            )

            if not init_data:
                raise RuntimeError("Failed to initialize TikTok upload")

            publish_id = init_data.get("publish_id")
            upload_url = init_data.get("upload_url")

            logger.info(f"TikTok upload initialized: publish_id={publish_id}")

            # Step 3: Upload video bytes
            upload_result = self._upload_video(upload_url, video_bytes)
            if not upload_result:
                raise RuntimeError("Failed to upload video to TikTok")

            logger.info(f"Video uploaded to TikTok, publish_id={publish_id}")

            # Step 4: Poll for completion
            status = self._wait_for_publish(publish_id)

            return {
                "publish_id": publish_id,
                "status": status or "submitted",
            }

        except Exception as e:
            logger.error(f"TikTok publish failed: {e}")
            return None

    def _init_upload(
        self,
        video_size: int,
        caption: str,
        disable_comment: bool = False,
    ) -> Optional[dict]:
        """Initialize a file upload with TikTok."""
        # Truncate caption — TikTok allows up to 2200 chars but keep it concise
        title = caption[:150]

        # Sandbox apps can only post to private; production can post public
        privacy = "SELF_ONLY" if settings.tiktok_sandbox else "PUBLIC_TO_EVERYONE"

        response = self._api_post(
            "/post/publish/video/init/",
            json={
                "post_info": {
                    "title": title,
                    "privacy_level": privacy,
                    "disable_comment": disable_comment,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_size,
                    "chunk_size": video_size,  # Single chunk upload
                    "total_chunk_count": 1,
                },
            },
        )

        if not response:
            return None

        data = response.get("data", {})
        return {
            "publish_id": data.get("publish_id"),
            "upload_url": data.get("upload_url"),
        }

    def _upload_video(self, upload_url: str, video_bytes: bytes) -> bool:
        """Upload video bytes to TikTok's upload URL."""
        video_size = len(video_bytes)

        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(video_size),
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
        }

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.put(
                    upload_url,
                    content=video_bytes,
                    headers=headers,
                )
                if response.status_code in (200, 201):
                    return True
                logger.warning(f"TikTok upload attempt {attempt + 1} returned {response.status_code}")
            except Exception as e:
                logger.error(f"TikTok upload attempt {attempt + 1} failed: {e}")

            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

        return False

    def _wait_for_publish(self, publish_id: str, max_wait: int = 120) -> Optional[str]:
        """Poll for publish completion."""
        start = time.time()

        while time.time() - start < max_wait:
            status = self.check_publish_status(publish_id)
            if not status:
                time.sleep(10)
                continue

            pub_status = status.get("data", {}).get("status")
            if pub_status == "PUBLISH_COMPLETE":
                logger.info(f"TikTok publish complete: {publish_id}")
                return "success"
            elif pub_status in ("FAILED", "PUBLISH_FAILED"):
                fail_reason = status.get("data", {}).get("fail_reason", "unknown")
                logger.error(f"TikTok publish failed: {fail_reason}")
                return "failed"

            time.sleep(10)

        logger.warning(f"TikTok publish status unknown after {max_wait}s")
        return None

    def check_publish_status(self, publish_id: str) -> Optional[dict]:
        """Check the status of a pending publish."""
        if self.mock_mode:
            return {"status": "mock_complete"}

        return self._api_post(
            "/post/publish/status/fetch/",
            json={"publish_id": publish_id},
        )

    def _api_post(self, endpoint: str, json: dict) -> Optional[dict]:
        """Make an authenticated POST to the TikTok API."""
        url = f"{TIKTOK_API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        try:
            response = self.client.post(url, json=json, headers=headers)
            data = response.json()

            error = data.get("error", {})
            if error.get("code") not in ("ok", None):
                logger.error(
                    f"TikTok API error: {error.get('message', '')} "
                    f"(code: {error.get('code')})"
                )
                return None

            return data

        except Exception as e:
            logger.error(f"TikTok API request failed: {e}")
            return None


def _update_env(key: str, value: str) -> bool:
    """Update or add a key in the .env file."""
    try:
        content = ENV_FILE.read_text(encoding="utf-8")
        pattern = rf"^{re.escape(key)}=.*$"
        if re.search(pattern, content, flags=re.MULTILINE):
            updated = re.sub(pattern, f"{key}={value}", content, flags=re.MULTILINE)
        else:
            updated = content.rstrip() + f"\n{key}={value}\n"
        ENV_FILE.write_text(updated, encoding="utf-8")
        return True
    except Exception as e:
        logger.error(f"Failed to update .env: {e}")
        return False


def _get_env_value(key: str) -> Optional[str]:
    """Read a value from the .env file."""
    try:
        content = ENV_FILE.read_text(encoding="utf-8")
        match = re.search(rf"^{re.escape(key)}=(.+)$", content, flags=re.MULTILINE)
        return match.group(1).strip() if match else None
    except Exception:
        return None
