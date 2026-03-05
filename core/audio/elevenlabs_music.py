"""Audio for reels — background music and TTS verse narration.

Background music priority:
  1. ElevenLabs Music API (paid plan required) — AI-generated instrumentals
  2. Mixkit free stock music — real royalty-free tracks, no API key needed
  3. FFmpeg sine-wave fallback — synthetic tones, last resort

TTS narration:
  ElevenLabs text-to-speech converts verse text to spoken audio.
  Mixed over background music in the reel at higher volume.

Tracks are saved to audio/ and randomly selected for each reel.
Narration files are cached in audio/narration/ keyed by content_id.
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

AUDIO_DIR = Path(__file__).parent.parent.parent / "audio"

# ── Mixkit curated tracks (royalty-free, no attribution required) ──
# Pattern: https://assets.mixkit.co/music/{ID}/{ID}.mp3
MIXKIT_TRACKS: list[dict[str, str | int]] = [
    {
        "name": "peaceful_piano_reflections",
        "id": 22,
        "description": "Calm piano reflections — soft, contemplative",
    },
    {
        "name": "relaxing_in_nature",
        "id": 522,
        "description": "Relaxing nature ambiance with gentle piano",
    },
    {
        "name": "possible_dreams",
        "id": 599,
        "description": "Hopeful piano and pads — uplifting, dreamy",
    },
    {
        "name": "skyline_piano",
        "id": 601,
        "description": "Skyline — cinematic piano, reflective mood",
    },
    {
        "name": "valley_sunset",
        "id": 127,
        "description": "Valley sunset — ambient, warm, golden hour feel",
    },
    {
        "name": "spirit_in_the_woods",
        "id": 139,
        "description": "Spirit in the woods — atmospheric, meditative",
    },
    {
        "name": "forest_treasure",
        "id": 138,
        "description": "Forest treasure — nature ambient, peaceful exploration",
    },
    {
        "name": "meditation_ambient",
        "id": 441,
        "description": "Meditation — soft ambient pads, calming",
    },
    {
        "name": "rest_now",
        "id": 584,
        "description": "Rest now — gentle piano, end-of-day calm",
    },
    {
        "name": "vastness_ambient",
        "id": 184,
        "description": "Vastness — expansive ambient, cinematic feel",
    },
]

# ── ElevenLabs prompts (for paid users) ──
ELEVENLABS_PROMPTS: list[dict[str, str]] = [
    {
        "name": "el_peaceful_piano",
        "prompt": "peaceful ambient piano worship instrumental, soft and reflective, gentle chords",
    },
    {
        "name": "el_acoustic_guitar",
        "prompt": "gentle acoustic guitar ambient instrumental, warm fingerpicking, calm and soothing",
    },
    {
        "name": "el_cinematic_strings",
        "prompt": "cinematic strings inspirational instrumental, soaring and hopeful, orchestral warmth",
    },
    {
        "name": "el_worship_keys",
        "prompt": "soft worship keys and pads instrumental, reverberant and ethereal, contemplative",
    },
    {
        "name": "el_warm_cello",
        "prompt": "warm solo cello instrumental, emotional and reflective, slow sustained notes",
    },
    {
        "name": "el_morning_light",
        "prompt": "bright morning piano and light strings instrumental, uplifting and joyful, optimistic",
    },
]


def generate_tracks(
    source: Optional[str] = None,
    overwrite: bool = False,
) -> list[Path]:
    """Download or generate background music tracks.

    Args:
        source: Force a specific source: 'elevenlabs', 'mixkit', or 'sine'.
                If None, auto-selects best available.
        overwrite: If True, re-download/regenerate even if files exist.

    Returns:
        List of paths to audio files.
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    if source == "elevenlabs" or (source is None and settings.has_elevenlabs):
        result = _generate_elevenlabs(overwrite=overwrite)
        if result:
            return result
        logger.warning("ElevenLabs failed, falling back to Mixkit")

    if source == "sine":
        return _generate_sine_wave_fallback()

    # Default: Mixkit free tracks
    result = _download_mixkit(overwrite=overwrite)
    if result:
        return result

    logger.warning("Mixkit download failed, falling back to FFmpeg sine waves")
    return _generate_sine_wave_fallback()


def _download_mixkit(overwrite: bool = False) -> list[Path]:
    """Download curated royalty-free tracks from Mixkit."""
    downloaded: list[Path] = []

    client = httpx.Client(timeout=30.0, follow_redirects=True)

    for track in MIXKIT_TRACKS:
        name = track["name"]
        track_id = track["id"]
        output_path = AUDIO_DIR / f"{name}.mp3"

        if output_path.exists() and not overwrite:
            if output_path.stat().st_size > 1000:
                logger.info(f"Skipping {name} (already exists)")
                downloaded.append(output_path)
                continue
            else:
                output_path.unlink()

        url = f"https://assets.mixkit.co/music/{track_id}/{track_id}.mp3"
        logger.info(f"Downloading: {name} (Mixkit #{track_id})")

        try:
            response = client.get(url)
            response.raise_for_status()

            if len(response.content) < 10_000:
                logger.warning(f"Track {name} too small ({len(response.content)} bytes), skipping")
                continue

            output_path.write_bytes(response.content)
            size_kb = output_path.stat().st_size / 1024
            logger.info(f"Saved: {name}.mp3 ({size_kb:.0f} KB)")
            downloaded.append(output_path)

        except Exception as e:
            logger.error(f"Failed to download {name}: {e}")
            if output_path.exists() and output_path.stat().st_size < 1000:
                output_path.unlink()

    client.close()
    return downloaded


def _generate_elevenlabs(
    overwrite: bool = False,
    duration_ms: int = 30_000,
) -> list[Path]:
    """Generate tracks via ElevenLabs Music API (paid plan required)."""
    if not settings.has_elevenlabs:
        return []

    try:
        from elevenlabs import ElevenLabs
    except ImportError:
        logger.error("elevenlabs package not installed — run: pip install elevenlabs")
        return []

    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    generated: list[Path] = []

    for entry in ELEVENLABS_PROMPTS:
        name = entry["name"]
        prompt = entry["prompt"]
        output_path = AUDIO_DIR / f"{name}.mp3"

        if output_path.exists() and not overwrite:
            if output_path.stat().st_size > 1000:
                logger.info(f"Skipping {name} (already exists)")
                generated.append(output_path)
                continue
            else:
                output_path.unlink()

        logger.info(f"Generating track: {name}")
        try:
            result = client.music.compose(
                prompt=prompt,
                output_format="mp3_44100_128",
                music_length_ms=duration_ms,
                force_instrumental=True,
            )

            with open(output_path, "wb") as f:
                for chunk in result:
                    f.write(chunk)

            if output_path.stat().st_size < 1000:
                logger.warning(f"Track {name} is empty/corrupt, removing")
                output_path.unlink()
                continue

            logger.info(f"Saved: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")
            generated.append(output_path)

        except Exception as e:
            logger.error(f"Failed to generate {name}: {e}")
            if output_path.exists() and output_path.stat().st_size < 1000:
                output_path.unlink()

    return generated


def _generate_sine_wave_fallback() -> list[Path]:
    """Generate simple sine-wave ambient tones using FFmpeg as fallback."""
    if not shutil.which("ffmpeg"):
        logger.error("FFmpeg not found — cannot generate fallback audio")
        return []

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    tracks = [
        ("sine_warm", 220.0),
        ("sine_peaceful", 261.63),
        ("sine_deep", 164.81),
        ("sine_hopeful", 293.66),
        ("sine_reflective", 196.0),
    ]

    generated: list[Path] = []
    duration = 30

    for name, freq in tracks:
        output = AUDIO_DIR / f"{name}.mp3"
        if output.exists() and output.stat().st_size > 1000:
            logger.info(f"Skipping {name} (already exists)")
            generated.append(output)
            continue

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"sine=frequency={freq}:duration={duration},volume=0.15",
            "-f", "lavfi", "-i",
            f"sine=frequency={freq * 1.5}:duration={duration},volume=0.08",
            "-f", "lavfi", "-i",
            f"sine=frequency={freq * 2}:duration={duration},volume=0.05",
            "-filter_complex",
            (
                f"[0:a][1:a][2:a]amix=inputs=3:duration=longest,"
                f"afade=t=in:st=0:d=3,"
                f"afade=t=out:st={duration - 3}:d=3,"
                f"lowpass=f=2000,"
                f"volume=0.6"
            ),
            "-c:a", "libmp3lame", "-q:a", "4",
            str(output),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Created fallback track: {name}.mp3")
            generated.append(output)
        else:
            logger.error(f"Failed to create {name}: {result.stderr[-200:]}")

    return generated


# ── TTS Verse Narration ──

NARRATION_DIR = AUDIO_DIR / "narration"

# Curated narration voices — rotated by content_id for variety.
# Each entry: (voice_id, name, description)
# Add community voices by getting their ID from elevenlabs.io/voice-library.
import random as _random

NARRATION_VOICES: list[dict[str, str]] = [
    {
        "id": "JBFqnCBsd6RMkjVDRZzb",
        "name": "George",
        "description": "British male, warm and raspy — calm narration",
    },
    {
        "id": "onwK4e9ZLuTAKqWW03F9",
        "name": "Daniel",
        "description": "British male, deep — authoritative scripture reading",
    },
    {
        "id": "ZQe5CZNOzWyzPSCn5a3c",
        "name": "James",
        "description": "Australian male, calm — reflective and measured",
    },
    {
        "id": "lL4hpA5hxNF3ovpnRQT5",
        "name": "Barry",
        "description": "Narration voice — rich and engaging",
    },
    {
        "id": "4dZr8J4CBeokyRkTRpoN",
        "name": "Hardwood",
        "description": "Narration voice — warm and grounded",
    },
    {
        "id": "kBag1HOZlaVBH7ICPE8x",
        "name": "Sakky Ford",
        "description": "Narration voice — expressive and distinctive",
    },
    {
        "id": "66y97vsfcmXgLh93gcal",
        "name": "Connery",
        "description": "Narration voice — commanding and distinctive",
    },
    {
        "id": "4QLC5fepxZkYmdD2IGRU",
        "name": "Matthew",
        "description": "Narration voice — clear and expressive",
    },
    {
        "id": "jfIS2w2yJi0grJZPyEsk",
        "name": "Oliver Silk",
        "description": "Narration voice — smooth and refined",
    },
    {
        "id": "B5jEZPqk2OJ2vkPw3wBM",
        "name": "Cillian",
        "description": "Narration voice — intense and captivating",
    },
]


def _select_narration_voice(content_id: int) -> dict[str, str]:
    """Select a narration voice, rotating by content_id for variety."""
    idx = content_id % len(NARRATION_VOICES)
    return NARRATION_VOICES[idx]


def generate_narration(
    verse_text: str,
    verse_ref: str,
    content_id: int,
) -> Optional[Path]:
    """Generate TTS narration of a Bible verse using ElevenLabs.

    Rotates through curated narration voices based on content_id.

    Args:
        verse_text: The verse text to narrate.
        verse_ref: Verse reference (e.g. "Psalms 23:1") — spoken at the end.
        content_id: Content ID for cache naming and voice rotation.

    Returns:
        Path to the narration MP3 file, or None if TTS is unavailable.
    """
    if not settings.has_elevenlabs or not settings.reel_narration_enabled:
        return None

    NARRATION_DIR.mkdir(parents=True, exist_ok=True)

    # Cache by content_id — don't regenerate for same content
    output_path = NARRATION_DIR / f"narration_{content_id}.mp3"
    if output_path.exists() and output_path.stat().st_size > 1000:
        logger.info(f"Using cached narration for content #{content_id}")
        return output_path

    try:
        from elevenlabs import ElevenLabs
    except ImportError:
        logger.error("elevenlabs package not installed — run: pip install elevenlabs")
        return None

    # Select voice for this content
    voice = _select_narration_voice(content_id)
    narration_text = _prepare_narration_text(verse_text, verse_ref)

    logger.info(
        f"Generating TTS narration for content #{content_id}: "
        f"voice={voice['name']}, {len(narration_text)} chars"
    )

    try:
        client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        audio = client.text_to_speech.convert(
            text=narration_text,
            voice_id=voice["id"],
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        # Write audio chunks to file
        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        if output_path.stat().st_size < 1000:
            logger.warning("TTS narration file is empty/corrupt, removing")
            output_path.unlink()
            return None

        size_kb = output_path.stat().st_size / 1024
        logger.info(f"Narration saved: {output_path} ({size_kb:.0f} KB, voice={voice['name']})")
        return output_path

    except Exception as e:
        logger.error(f"TTS narration failed: {e}")
        if output_path.exists() and output_path.stat().st_size < 1000:
            output_path.unlink()
        return None


def _prepare_narration_text(verse_text: str, verse_ref: str) -> str:
    """Prepare verse text for natural-sounding TTS narration.

    Adds a brief pause before the reference and cleans up formatting.
    """
    # Clean up whitespace and newlines
    text = " ".join(verse_text.split())

    # Add the verse reference at the end with a pause
    # The period + dash create a natural pause before the reference
    text = f"{text} — {verse_ref}."

    return text
