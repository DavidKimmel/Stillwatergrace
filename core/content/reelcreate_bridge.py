"""Bridge between StillwaterGrace and ReelCreate asset generation.

Routes SWG content types to ReelCreate presets, generates high-quality
reels using Remotion/FFmpeg, and returns an MP4 path compatible with
SWG's existing upload and posting pipeline.

Design constraints:
- Default to Unsplash/image backgrounds with Ken Burns (zero video gen cost)
- Never auto-trigger fal.ai — video generation is manual/opt-in only
- Drop-in replacement for SWG's generate_reel() return type (str path or None)
"""
import logging
import os
import random
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

import reelcreate

# Load ReelCreate's .env for API keys not in SWG's environment
_RC_ENV = Path(reelcreate._PROJECT_ROOT) / ".env"
if _RC_ENV.exists():
    load_dotenv(_RC_ENV, override=False)  # don't override SWG's keys

logger = logging.getLogger(__name__)

# ── Content type → ReelCreate preset mapping ──────────────────────

CONTENT_TYPE_PRESET_MAP: dict[str, str] = {
    # Verse-based content → verse card or narrated reel (randomized)
    "daily_verse": "stillwatergrace",
    "encouragement": "encouragement",
    "prayer_prompt": "verse_card",
    "gratitude": "verse_card",
    "coffee_verse": "coffee_verse",
    # Series content → narrated reel with script
    "marriage_monday": "stillwatergrace",
    "parenting_wednesday": "stillwatergrace",
    "faith_friday": "stillwatergrace",
    # Quote content → verse card style
    "christian_quote": "verse_card",
    "conviction_quote": "verse_card",
    # Interactive formats → not reel-able, skip
    "fill_in_blank": None,
    "this_or_that": None,
    "parenting_list": None,
    "marriage_challenge": None,
    "carousel": None,
}

# Content types that randomly alternate between narrated and verse card
MIXED_TYPES = {"daily_verse"}

# ── Emotional tone → ReelCreate mood mapping ─────────────────────

TONE_TO_MOOD: dict[str, str] = {
    "hopeful": "hope",
    "challenging": "strength",
    "reflective": "peace",
    "celebratory": "joy",
}

DEFAULT_MOOD = "peace"

# ── Intro phrases for narrated verse content ─────────────────────

VERSE_INTRO_PHRASES = [
    "The Bible teaches us",
    "In God's word we learn",
    "Scripture says",
    "The Bible says",
    "God's word tells us",
    "The word of God says",
]


def pick_preset_for_content(
    content_type: str,
    force_preset: Optional[str] = None,
) -> Optional[str]:
    """Determine the ReelCreate preset for a given SWG content type.

    Returns None if the content type is not suitable for reel generation.
    """
    if force_preset:
        return force_preset

    if content_type in MIXED_TYPES:
        return random.choice(["stillwatergrace", "verse_card"])

    return CONTENT_TYPE_PRESET_MAP.get(content_type)


def pick_mood(emotional_tone: Optional[str]) -> str:
    """Map SWG emotional tone to ReelCreate mood."""
    if emotional_tone:
        return TONE_TO_MOOD.get(emotional_tone, DEFAULT_MOOD)
    return DEFAULT_MOOD


def generate_reel_for_content(
    background_path: str,
    verse_text: str,
    verse_ref: str,
    content_id: int,
    content_type: str = "daily_verse",
    emotional_tone: Optional[str] = None,
    reel_script: Optional[str] = None,
    translation: str = "NIV",
    force_preset: Optional[str] = None,
    force_voice: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Optional[str]:
    """Generate a reel using ReelCreate and return the output MP4 path.

    This is a drop-in replacement for SWG's generate_reel() — takes similar
    inputs and returns a file path (or None on failure).

    Args:
        background_path: Unsplash image to use as Ken Burns background.
        verse_text: The Bible verse text to display/narrate.
        verse_ref: Verse reference (e.g. "Hebrews 11:1").
        content_id: SWG content ID for output naming.
        content_type: SWG ContentType value (e.g. "daily_verse").
        emotional_tone: SWG EmotionalTone value (e.g. "reflective").
        reel_script: Pre-generated voiceover script (from Claude). If None,
                     the verse text is used directly.
        translation: Bible translation code.
        force_preset: Override the automatic preset selection.
        output_dir: Where to write the output. Defaults to images/processed/.

    Returns:
        Path to the rendered MP4 file, or None on failure.
    """
    # Verify background file exists — if it was cleaned up after R2 upload,
    # fetch a fresh Unsplash image
    if not os.path.exists(background_path):
        logger.warning("Background missing: %s — fetching fresh Unsplash image", background_path)
        try:
            from core.images.unsplash_client import UnsplashClient
            client = UnsplashClient()
            result = client.search_and_download(
                content_type=content_type, high_res=True,
            )
            if result and result.get("local_path"):
                background_path = result["local_path"]
                logger.info("Fetched replacement background: %s", background_path)
            else:
                logger.warning("Unsplash fallback failed, proceeding without background")
        except Exception as e:
            logger.warning("Could not fetch replacement background: %s", e)

    preset_name = pick_preset_for_content(content_type, force_preset)
    if preset_name is None:
        logger.info(
            "Content type %r not suitable for ReelCreate reel, skipping",
            content_type,
        )
        return None

    mood = pick_mood(emotional_tone)
    preset = reelcreate.load_preset(preset_name)
    render_mode = getattr(preset, "render_mode", "narrated_reel")

    # Ensure full book name for display
    display_ref = reelcreate.full_book_name(verse_ref)

    # Output directory
    if output_dir is None:
        output_dir = os.path.join("images", "processed")
    os.makedirs(output_dir, exist_ok=True)

    # Coffee verse uses a fixed background image
    if preset_name == "coffee_verse":
        fixed_bg = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "assets", "backgrounds", "coffee_verse_bg.png")
        if os.path.exists(fixed_bg):
            background_path = fixed_bg
            logger.info("Using fixed coffee_verse background: %s", fixed_bg)

    try:
        if render_mode in ("verse_card", "music_reel"):
            return _render_verse_card(
                preset=preset,
                verse_text=verse_text,
                verse_ref=display_ref,
                content_id=content_id,
                background_path=background_path,
                mood=mood,
                output_dir=output_dir,
                force_voice=force_voice,
            )
        else:
            return _render_narrated_reel(
                preset=preset,
                preset_name=preset_name,
                verse_text=verse_text,
                verse_ref=display_ref,
                reel_script=reel_script,
                content_id=content_id,
                background_path=background_path,
                mood=mood,
                output_dir=output_dir,
                force_voice=force_voice,
            )
    except Exception as e:
        logger.exception(
            "ReelCreate bridge failed for content #%d: %s", content_id, e
        )
        return None


def _render_verse_card(
    preset,
    verse_text: str,
    verse_ref: str,
    content_id: int,
    background_path: str,
    mood: str,
    output_dir: str,
    force_voice: Optional[str] = None,
) -> Optional[str]:
    """Render a verse card (text on gradient/image, optional narration + music)."""
    with reelcreate._rc_context():
        return _render_verse_card_inner(
            preset, verse_text, verse_ref, content_id,
            background_path, mood, output_dir, force_voice,
        )


def _render_verse_card_inner(
    preset, verse_text, verse_ref, content_id,
    background_path, mood, output_dir, force_voice=None,
) -> Optional[str]:
    """Inner implementation — runs inside RC context."""
    from core.rendering.remotion_renderer import is_remotion_available

    if not is_remotion_available():
        logger.warning("Remotion not available, falling back to None")
        return None

    # Determine background mode
    ext = os.path.splitext(background_path)[1].lower()
    if ext in {".mp4", ".mov", ".webm"}:
        bg_mode = "video"
    elif ext in {".jpg", ".jpeg", ".png", ".webp"}:
        bg_mode = "image"
    else:
        bg_mode = "gradient"

    # Extract highlight words
    highlight_words = _extract_highlights(verse_text)

    # Voiceover: generate narration for the verse
    audio_path = None
    timestamps = []
    voiceover_delay_s = 1.5
    duration_s = 16.0

    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if elevenlabs_key:
        from core.ai.elevenlabs_client import ElevenLabsClient, VoiceStyle

        client = ElevenLabsClient(api_key=elevenlabs_key)
        if client.is_available:
            # Pick an intro phrase and prepend to voiceover
            intro = random.choice(VERSE_INTRO_PHRASES)
            voiceover_text = f"{intro}, {verse_text}"

            # Pick a voice from the full pool
            voice_ids = list(preset.voice_ids) if preset.voice_ids else []
            if not voice_ids:
                # Use stillwatergrace voices as default pool
                swg = reelcreate.load_preset("stillwatergrace")
                voice_ids = list(swg.voice_ids)

            voice_id = force_voice or (random.choice(voice_ids) if voice_ids else preset.voice_id)

            style = VoiceStyle(stability=0.5, similarity_boost=0.85, style=0.3, speed=1.0)
            result = client.generate_speech(
                text=voiceover_text,
                voice_id=voice_id,
                voice_style=style,
            )
            if result:
                audio_bytes, timestamps = result
                audio_path = os.path.join(output_dir, f"voiceover_{content_id}.mp3")
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)
                duration_s = max(t["end"] for t in timestamps) + voiceover_delay_s + 3.0
                logger.info("Generated voiceover for verse card #%d", content_id)

    # Music from library
    music_path = _pick_music(output_dir, content_id, timestamps)

    # Build colors from preset
    brand_colors = getattr(preset, "brand_colors", {})

    output_path = os.path.join(output_dir, f"reel_{content_id}.mp4")
    inp = reelcreate.VerseCardRenderInput(
        reference=verse_ref.upper(),
        verse_text=verse_text,
        output_path=output_path,
        highlight_words=highlight_words,
        background_mode=bg_mode,
        background_path=background_path if bg_mode != "gradient" else None,
        audio_path=audio_path,
        voiceover_volume=1.0,
        voiceover_delay_s=voiceover_delay_s,
        music_path=music_path,
        music_volume=0.3,
        duration_s=duration_s,
        gradient_from=brand_colors.get("background_start", "#E8E8E8"),
        gradient_to=brand_colors.get("background_end", "#FAFAFA"),
        text_color=brand_colors.get("primary", "#1A1A1A") if bg_mode == "gradient" else "#FFFFFF",
        highlight_color=brand_colors.get("highlight", "#8B0000") if bg_mode == "gradient" else "#FF2D2D",
    )

    result = reelcreate.render_verse_card(inp)
    if result.success:
        logger.info("Verse card rendered: %s", result.output_path)
        return result.output_path

    logger.error("Verse card render failed: %s", result.error)
    return None


def _render_narrated_reel(
    preset,
    preset_name: str,
    verse_text: str,
    verse_ref: str,
    reel_script: Optional[str],
    content_id: int,
    background_path: str,
    mood: str,
    output_dir: str,
    force_voice: Optional[str] = None,
) -> Optional[str]:
    """Render a narrated reel (image/video background + voiceover + animated captions).

    Assembles the reel directly rather than going through ReelGenerator.generate(),
    which doesn't accept an external background image.
    """
    with reelcreate._rc_context():
        return _render_narrated_reel_inner(
            preset, preset_name, verse_text, verse_ref, reel_script,
            content_id, background_path, mood, output_dir, force_voice,
        )


def _render_narrated_reel_inner(
    preset, preset_name, verse_text, verse_ref, reel_script,
    content_id, background_path, mood, output_dir, force_voice=None,
) -> Optional[str]:
    """Inner implementation — runs inside RC context."""
    from core.ai.elevenlabs_client import ElevenLabsClient, VoiceStyle
    from core.rendering.remotion_renderer import (
        RemotionRenderInput, render_reel, is_remotion_available,
        resolve_video_strategy,
    )

    script = reel_script or verse_text

    # Step 1: Generate voiceover
    audio_path = None
    timestamps = []
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY", "")

    if elevenlabs_key:
        client = ElevenLabsClient(api_key=elevenlabs_key)
        if client.is_available:
            # Pick a voice from the preset pool
            voice_ids = list(preset.voice_ids) if preset.voice_ids else []
            if not voice_ids:
                swg = reelcreate.load_preset("stillwatergrace")
                voice_ids = list(swg.voice_ids)
            voice_id = force_voice or (random.choice(voice_ids) if voice_ids else preset.voice_id)

            style = VoiceStyle(stability=0.5, similarity_boost=0.85, style=0.3, speed=1.0)
            result = client.generate_speech(
                text=script.replace("\n", " "),
                voice_id=voice_id,
                voice_style=style,
            )
            if result:
                audio_bytes, timestamps = result
                audio_path = os.path.join(output_dir, f"voiceover_{content_id}.mp3")
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)
                logger.info("Generated voiceover for narrated reel #%d", content_id)

    if not audio_path:
        logger.warning("No voiceover generated for #%d, cannot render narrated reel", content_id)
        return None

    # Step 2: Music from library
    music_path = _pick_music(output_dir, content_id, timestamps)

    # Step 3: Determine background type
    bg_ext = os.path.splitext(background_path)[1].lower()
    bg_type = "image" if bg_ext in {".png", ".jpg", ".jpeg", ".webp"} else "video"

    # Step 4: Duration from voiceover
    duration_s = max(t["end"] for t in timestamps) + 3.0 if timestamps else 20.0

    # Step 5: Extract highlight words
    highlight_words = _extract_highlights(script)

    # Step 6: Caption style
    caption_mode = getattr(preset, "caption_mode", "word_highlight")
    remotion_mode_map = {
        "word_highlight": "word_highlight",
        "single_word": "single_word",
        "phrase": "stacking",
        "stacking": "stacking",
    }
    remotion_mode = remotion_mode_map.get(caption_mode, "stacking")

    if remotion_mode == "word_highlight":
        caption_style = {
            "fontFamily": "Impact, Arial Black, sans-serif",
            "fontSize": 90,
            "color": "#FFFFFF",
            "highlightColor": "#FF8C00",
            "highlightWords": highlight_words,
            "strokeColor": "#000000",
            "strokeWidth": 5,
            "shadowBlur": 12,
            "shadowColor": "rgba(0,0,0,0.7)",
            "wordsPerGroup": 4,
        }
    else:
        caption_style = {
            "fontFamily": "Impact, Arial Black, sans-serif",
            "fontSize": 120,
            "color": "#FFFFFF",
            "highlightColor": "#FF2D2D",
            "highlightWords": highlight_words,
            "strokeColor": "#000000",
            "strokeWidth": 6,
            "shadowBlur": 16,
            "shadowColor": "rgba(0,0,0,0.8)",
            "wordsPerGroup": 3,
        }

    # Step 7: Render with Remotion (or FFmpeg fallback)
    output_path = os.path.join(output_dir, f"reel_{content_id}.mp4")

    if is_remotion_available():
        inp = RemotionRenderInput(
            background_path=background_path,
            background_type=bg_type,
            audio_path=audio_path,
            timestamps=timestamps,
            output_path=output_path,
            caption_mode=remotion_mode,
            caption_style=caption_style,
            music_path=music_path,
            music_volume=0.12,
            duration_s=duration_s,
        )
        result = render_reel(inp)
        if result.success:
            logger.info("Narrated reel rendered: %s", result.output_path)
            return result.output_path
        logger.error("Remotion render failed: %s", result.error)

    # Fallback to FFmpeg
    logger.info("Using FFmpeg fallback for narrated reel #%d", content_id)
    from core.rendering.simple_pipeline import SimpleReelInput, build_simple_reel
    from core.captions import CaptionStyle as RCCaptionStyle, generate_capcut_captions

    caption_file = None
    if timestamps:
        caption_file = os.path.join(output_dir, f"captions_{content_id}.ass")
        rc_style = RCCaptionStyle(
            highlight_color=getattr(preset, "caption_highlight_color", "&H0000FFFF"),
            primary_color=getattr(preset, "caption_color", "&H00FFFFFF"),
            font=getattr(preset, "caption_font", "Impact"),
        )
        generate_capcut_captions(timestamps, caption_file, style=rc_style)

    reel_input = SimpleReelInput(
        reel_id=f"reel_{content_id}",
        background_path=background_path,
        narration_path=audio_path,
        music_path=music_path,
        timestamps=timestamps,
        caption_file=caption_file,
        output_dir=output_dir,
    )
    ffmpeg_result = build_simple_reel(reel_input)
    if ffmpeg_result.success:
        logger.info("FFmpeg narrated reel rendered: %s", ffmpeg_result.output_path)
        return ffmpeg_result.output_path

    logger.error("FFmpeg fallback also failed: %s", ffmpeg_result.error)
    return None


def _pick_music(output_dir: str, content_id: int, timestamps: list[dict]) -> Optional[str]:
    """Pick background music from the ReelCreate music library."""
    try:
        lib = reelcreate.get_music_library()
        if lib.count == 0:
            return None

        dest = os.path.join(output_dir, f"music_{content_id}.mp3")
        target_s = 18.0
        if timestamps:
            target_s = max(t["end"] for t in timestamps) + 3.0

        return lib.pick_and_copy(dest, target_duration_s=target_s)
    except Exception as e:
        logger.warning("Music library unavailable: %s", e)
        return None


def _extract_highlights(text: str) -> list[str]:
    """Extract emotionally significant words for highlighting."""
    candidates = {
        "love", "loved", "loves", "nothing", "never", "always",
        "god", "jesus", "lord", "faith", "hope", "peace",
        "heart", "soul", "grace", "mercy", "forgive",
        "fear", "fears", "death", "sin", "pain",
        "strength", "power", "mighty", "eternal",
        "separate", "abandon", "forsake",
        "blessed", "beautiful", "wonderful",
        "everything", "forever", "promise",
        "safe", "guarded", "shepherd", "comfort",
    }
    words_in_text = set(w.lower().strip(".,!?;:'\"") for w in text.split())
    return sorted(candidates & words_in_text)
