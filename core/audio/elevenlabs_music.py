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

# ── ElevenLabs mood-matched music prompts ──
# Each track is tagged with content types it suits best.
ELEVENLABS_PROMPTS: list[dict] = [
    {
        "name": "el_peaceful_piano",
        "prompt": "peaceful ambient piano worship instrumental, soft and reflective, gentle chords",
        "moods": ["daily_verse", "prayer_prompt", "gratitude"],
    },
    {
        "name": "el_acoustic_guitar",
        "prompt": "gentle acoustic guitar ambient instrumental, warm fingerpicking, calm and soothing",
        "moods": ["marriage_monday", "encouragement", "parenting_wednesday"],
    },
    {
        "name": "el_cinematic_strings",
        "prompt": "cinematic strings inspirational instrumental, soaring and hopeful, orchestral warmth",
        "moods": ["faith_friday", "conviction_quote", "encouragement"],
    },
    {
        "name": "el_worship_keys",
        "prompt": "soft worship keys and pads instrumental, reverberant and ethereal, contemplative",
        "moods": ["daily_verse", "prayer_prompt", "faith_friday"],
    },
    {
        "name": "el_warm_cello",
        "prompt": "warm solo cello instrumental, emotional and reflective, slow sustained notes",
        "moods": ["faith_friday", "conviction_quote", "gratitude"],
    },
    {
        "name": "el_morning_light",
        "prompt": "bright morning piano and light strings instrumental, uplifting and joyful, optimistic",
        "moods": ["encouragement", "gratitude", "marriage_monday"],
    },
    {
        "name": "el_tender_family",
        "prompt": "tender piano and soft strings instrumental, warm and nurturing, gentle family warmth",
        "moods": ["parenting_wednesday", "marriage_monday", "gratitude"],
    },
    {
        "name": "el_strength_resolve",
        "prompt": "deep ambient piano with low strings instrumental, grounded and resolute, quiet strength",
        "moods": ["conviction_quote", "faith_friday", "prayer_prompt"],
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


def select_music_for_content(content_type: str, content_id: int) -> Optional[Path]:
    """Select a background music track matched to the content type.

    Prefers ElevenLabs mood-matched tracks, falls back to Mixkit.
    """
    import random as _rand

    # Try ElevenLabs tracks first (mood-matched)
    matching_el = [
        e for e in ELEVENLABS_PROMPTS
        if content_type in e.get("moods", [])
    ]
    if matching_el:
        entry = matching_el[content_id % len(matching_el)]
        el_path = AUDIO_DIR / f"{entry['name']}.mp3"
        if el_path.exists() and el_path.stat().st_size > 1000:
            return el_path

    # Fall back to any ElevenLabs track
    el_tracks = [AUDIO_DIR / f"{e['name']}.mp3" for e in ELEVENLABS_PROMPTS]
    el_available = [p for p in el_tracks if p.exists() and p.stat().st_size > 1000]
    if el_available:
        return el_available[content_id % len(el_available)]

    # Fall back to Mixkit
    mixkit_tracks = [AUDIO_DIR / f"{t['name']}.mp3" for t in MIXKIT_TRACKS]
    mixkit_available = [p for p in mixkit_tracks if p.exists() and p.stat().st_size > 1000]
    if mixkit_available:
        return mixkit_available[content_id % len(mixkit_available)]

    # Last resort: any MP3 in audio dir
    all_tracks = [
        p for p in AUDIO_DIR.glob("*.mp3")
        if p.stat().st_size > 1000 and "narration" not in p.name
    ]
    if all_tracks:
        return all_tracks[content_id % len(all_tracks)]

    return None


# ── Ambient Sound Effects ──

AMBIENT_SOUNDS_DIR = AUDIO_DIR / "ambient"

AMBIENT_PROMPTS: list[dict[str, str]] = [
    {
        "name": "gentle_stream",
        "prompt": "Gentle flowing stream with soft water sounds, peaceful and calming",
    },
    {
        "name": "forest_birds",
        "prompt": "Soft forest ambiance with distant birds chirping, gentle and serene",
    },
    {
        "name": "light_rain",
        "prompt": "Light rain falling softly on leaves, peaceful and meditative",
    },
    {
        "name": "morning_nature",
        "prompt": "Early morning nature ambiance, soft wind and distant birdsong at dawn",
    },
    {
        "name": "ocean_waves",
        "prompt": "Gentle ocean waves lapping on shore, calm and rhythmic",
    },
    {
        "name": "soft_wind",
        "prompt": "Soft wind blowing through tall grass in an open field, peaceful and spacious",
    },
]

# Map content types to ambient sounds for thematic matching
CONTENT_AMBIENT_MAP: dict[str, list[str]] = {
    "daily_verse": ["gentle_stream", "morning_nature", "forest_birds"],
    "encouragement": ["morning_nature", "gentle_stream", "soft_wind"],
    "marriage_monday": ["ocean_waves", "soft_wind", "gentle_stream"],
    "parenting_wednesday": ["forest_birds", "morning_nature", "gentle_stream"],
    "faith_friday": ["light_rain", "gentle_stream", "ocean_waves"],
    "gratitude": ["morning_nature", "forest_birds", "soft_wind"],
    "prayer_prompt": ["light_rain", "gentle_stream", "soft_wind"],
    "conviction_quote": ["ocean_waves", "soft_wind", "light_rain"],
}


def generate_ambient_sounds(overwrite: bool = False) -> list[Path]:
    """Generate ambient sound effect loops using ElevenLabs Sound Effects API.

    Returns list of paths to generated ambient MP3 files.
    """
    if not settings.has_elevenlabs:
        logger.info("ElevenLabs not configured — skipping ambient sound generation")
        return []

    try:
        from elevenlabs import ElevenLabs
    except ImportError:
        logger.error("elevenlabs package not installed")
        return []

    AMBIENT_SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    generated: list[Path] = []

    for entry in AMBIENT_PROMPTS:
        name = entry["name"]
        prompt = entry["prompt"]
        output_path = AMBIENT_SOUNDS_DIR / f"{name}.mp3"

        if output_path.exists() and not overwrite:
            if output_path.stat().st_size > 1000:
                logger.info(f"Skipping ambient {name} (already exists)")
                generated.append(output_path)
                continue
            else:
                output_path.unlink()

        logger.info(f"Generating ambient sound: {name}")
        try:
            audio = client.text_to_sound_effects.convert(
                text=prompt,
                duration_seconds=15.0,
                prompt_influence=0.5,
                loop=True,
            )

            with open(output_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)

            if output_path.stat().st_size < 1000:
                logger.warning(f"Ambient {name} is empty/corrupt, removing")
                output_path.unlink()
                continue

            size_kb = output_path.stat().st_size / 1024
            logger.info(f"Saved ambient: {name}.mp3 ({size_kb:.0f} KB)")
            generated.append(output_path)

        except Exception as e:
            logger.error(f"Failed to generate ambient {name}: {e}")

    return generated


def select_ambient_sound(content_type: str, content_id: int) -> Optional[Path]:
    """Select an ambient sound file matched to the content type.

    Returns path to ambient MP3, or None if unavailable.
    """
    if not AMBIENT_SOUNDS_DIR.exists():
        return None

    # Get preferred sounds for this content type
    preferred = CONTENT_AMBIENT_MAP.get(content_type, list(CONTENT_AMBIENT_MAP["daily_verse"]))

    # Rotate through preferred sounds based on content_id
    for i in range(len(preferred)):
        idx = (content_id + i) % len(preferred)
        name = preferred[idx]
        path = AMBIENT_SOUNDS_DIR / f"{name}.mp3"
        if path.exists() and path.stat().st_size > 1000:
            return path

    # Fall back to any available ambient sound
    available = [p for p in AMBIENT_SOUNDS_DIR.glob("*.mp3") if p.stat().st_size > 1000]
    if available:
        return available[content_id % len(available)]

    return None


# ── TTS Verse Narration ──

NARRATION_DIR = AUDIO_DIR / "narration"

# Curated narration voices — rotated by content_id for variety.
# Each entry: (voice_id, name, description)
# Add community voices by getting their ID from elevenlabs.io/voice-library.
import random as _random

NARRATION_VOICES: list[dict[str, str]] = [
    {
        "id": "3AvFKjwBVQoGCFjmz5ib",
        "name": "Suzanne",
    },
    {
        "id": "oQV06a7Gn8pbCJh5DXcO",
        "name": "Archer",
    },
    {
        "id": "EkK5I93UQWFDigLMpZcX",
        "name": "James",
    },
    {
        "id": "uju3wxzG5OhpWcoi3SMy",
        "name": "Michael C. Vincent",
    },
    {
        "id": "jfIS2w2yJi0grJZPyEsk",
        "name": "Oliver Silk",
    },
    {
        "id": "B5jEZPqk2OJ2vkPw3wBM",
        "name": "Cillian",
    },
    {
        "id": "66y97vsfcmXgLh93gcal",
        "name": "Connery",
    },
    {
        "id": "kBag1HOZlaVBH7ICPE8x",
        "name": "Sakky Ford",
    },
    {
        "id": "lL4hpA5hxNF3ovpnRQT5",
        "name": "Barry",
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
    # Extract book name from reference (e.g. "John 3:16" → "John")
    book = verse_ref.rsplit(" ", 1)[0] if " " in verse_ref else ""
    # Handle "1 John 4:7" → "1 John" by checking if last part has digits
    parts = verse_ref.split()
    book = " ".join(parts[:-1]) if len(parts) > 1 else ""
    narration_text = _prepare_narration_text(verse_text, verse_ref, content_id, book)

    logger.info(
        f"Generating TTS narration for content #{content_id}: "
        f"voice={voice['name']}, {len(narration_text)} chars"
    )

    try:
        from elevenlabs import VoiceSettings

        client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        audio = client.text_to_speech.convert(
            text=narration_text,
            voice_id=voice["id"],
            model_id="eleven_v3",
            output_format="mp3_44100_128",
            voice_settings=VoiceSettings(
                stability=0.4,           # More emotional range for scripture
                similarity_boost=0.75,   # Stay close to voice character
                style=0.3,              # Subtle style exaggeration
                use_speaker_boost=True,  # Enhanced clarity
            ),
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


def generate_narration_at_speed(
    verse_text: str,
    verse_ref: str,
    content_id: int,
    speed: float = 1.0,
) -> Optional[Path]:
    """Re-generate narration at a different speed using ElevenLabs native speed param.

    Uses speed=0.25-4.0. More natural than FFmpeg atempo time-stretching.
    Returns path to the speed-adjusted narration, or None if TTS unavailable.
    """
    if not settings.has_elevenlabs or not settings.reel_narration_enabled:
        return None

    NARRATION_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f".fast" if speed > 1.0 else f".slow"
    output_path = NARRATION_DIR / f"narration_{content_id}{suffix}.mp3"

    if output_path.exists() and output_path.stat().st_size > 1000:
        return output_path

    try:
        from elevenlabs import ElevenLabs, VoiceSettings

        client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        voice = _select_narration_voice(content_id)
        parts = verse_ref.split()
        book = " ".join(parts[:-1]) if len(parts) > 1 else ""
        narration_text = _prepare_narration_text(verse_text, verse_ref, content_id, book)

        # Clamp speed to ElevenLabs range
        speed = max(0.25, min(4.0, speed))

        logger.info(
            f"Regenerating narration for content #{content_id} at {speed:.2f}x speed "
            f"(voice={voice['name']})"
        )

        audio = client.text_to_speech.convert(
            text=narration_text,
            voice_id=voice["id"],
            model_id="eleven_v3",
            output_format="mp3_44100_128",
            voice_settings=VoiceSettings(
                stability=0.4,
                similarity_boost=0.75,
                style=0.3,
                speed=speed,
                use_speaker_boost=True,
            ),
        )

        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        if output_path.stat().st_size < 1000:
            output_path.unlink()
            return None

        logger.info(f"Speed-adjusted narration saved: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Speed-adjusted narration failed: {e}")
        if output_path.exists() and output_path.stat().st_size < 1000:
            output_path.unlink()
        return None


# Intro phrases for narration variety — rotated by content_id
# Some reference Christ's words, others are generic scripture intros,
# and some start directly with the verse for variety.
NARRATION_INTROS: list[dict[str, str]] = [
    {"phrase": "", "type": "direct"},  # No intro — just start reading
    {"phrase": "The Bible says,", "type": "generic"},
    {"phrase": "In God's Word it says,", "type": "generic"},
    {"phrase": "The Bible teaches,", "type": "generic"},
    {"phrase": "Scripture tells us,", "type": "generic"},
    {"phrase": "", "type": "direct"},  # No intro — variety
    {"phrase": "God's Word reminds us,", "type": "generic"},
    {"phrase": "The Word of God says,", "type": "generic"},
    {"phrase": "We read in Scripture,", "type": "generic"},
    {"phrase": "", "type": "direct"},  # No intro — variety
]

# Intros specifically for words of Christ (books: Matthew, Mark, Luke, John)
CHRIST_INTROS: list[str] = [
    "Jesus says,",
    "Jesus teaches,",
    "Christ tells us,",
    "The Lord says,",
    "Jesus reminds us,",
    "Our Savior says,",
]

# Books that contain direct words of Jesus
GOSPEL_BOOKS = {"Matthew", "Mark", "Luke", "John", "Revelation"}


def _prepare_narration_text(
    verse_text: str,
    verse_ref: str,
    content_id: int = 0,
    book: str = "",
) -> str:
    """Prepare verse text for natural-sounding TTS narration.

    Adds an intro phrase for variety and the reference at the end.
    Selects Christ-specific intros for Gospel passages.
    """
    # Clean up whitespace and newlines
    text = " ".join(verse_text.split())

    # Select intro phrase
    intro = ""
    if book in GOSPEL_BOOKS:
        # Use Christ-specific intro ~50% of the time for gospel verses
        if content_id % 3 != 0:  # 2 out of 3 times
            intro = CHRIST_INTROS[content_id % len(CHRIST_INTROS)]
        else:
            entry = NARRATION_INTROS[content_id % len(NARRATION_INTROS)]
            intro = entry["phrase"]
    else:
        entry = NARRATION_INTROS[content_id % len(NARRATION_INTROS)]
        intro = entry["phrase"]

    # Build full narration text
    if intro:
        text = f"{intro} {text}"

    # Add the verse reference at the end with a pause
    text = f"{text} — {verse_ref}."

    return text
