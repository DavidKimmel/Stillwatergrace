"""ElevenLabs TTS with word-level timestamps and phrase grouping.

Generates narration audio with character-level alignment data from ElevenLabs,
converts to word boundaries, and groups into natural 3-5 word phrases for
dynamic caption rendering in reels.
"""

import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import settings

logger = logging.getLogger(__name__)

NARRATION_DIR = Path(__file__).parent.parent.parent / "audio" / "narration"

# Punctuation that forces a phrase break (even if word count < 3)
PHRASE_BREAK_CHARS = {",", ".", ";", ":", "!", "?", "\u2014", "\u2013", "-"}

# Max words per phrase before forcing a break
MAX_PHRASE_WORDS = 5

# Min words per phrase (try to avoid 1-word phrases unless forced by punctuation)
MIN_PHRASE_WORDS = 2


@dataclass(frozen=True)
class WordTimestamp:
    """A single word with its start and end times in seconds."""

    word: str
    start_time: float
    end_time: float


@dataclass(frozen=True)
class Phrase:
    """A group of words forming a natural phrase, with timing."""

    text: str
    start_time: float
    end_time: float
    words: tuple[WordTimestamp, ...]


def generate_narration_with_timestamps(
    text: str,
    content_id: int,
    voice_index: Optional[int] = None,
) -> Optional[tuple[Path, list[WordTimestamp]]]:
    """Generate TTS audio with word-level timestamps using ElevenLabs.

    Uses the convert_with_timestamps endpoint which returns character-level
    alignment data. Converts character timestamps to word boundaries.

    Args:
        text: Text to narrate.
        content_id: Content ID for cache naming and voice selection.
        voice_index: Override voice selection (0-8). If None, uses content_id rotation.

    Returns:
        Tuple of (audio_path, word_timestamps), or None if TTS unavailable.
    """
    if not settings.has_elevenlabs:
        logger.warning("ElevenLabs not configured -- skipping timestamped narration")
        return None

    try:
        from elevenlabs import ElevenLabs, VoiceSettings
    except ImportError:
        logger.error("elevenlabs package not installed -- run: pip install elevenlabs")
        return None

    from core.audio.elevenlabs_music import NARRATION_VOICES, _select_narration_voice

    NARRATION_DIR.mkdir(parents=True, exist_ok=True)

    # Select voice
    if voice_index is not None:
        voice = NARRATION_VOICES[voice_index % len(NARRATION_VOICES)]
    else:
        voice = _select_narration_voice(content_id)

    output_path = NARRATION_DIR / f"narration_phrase_{content_id}.mp3"

    logger.info(
        f"Generating timestamped narration for content #{content_id}: "
        f"voice={voice['name']}, {len(text)} chars"
    )

    try:
        client = ElevenLabs(api_key=settings.elevenlabs_api_key)

        # Use convert_with_timestamps for character-level alignment
        response = client.text_to_speech.convert_with_timestamps(
            text=text,
            voice_id=voice["id"],
            model_id="eleven_v3",
            output_format="mp3_44100_128",
            voice_settings=VoiceSettings(
                stability=0.4,
                similarity_boost=0.75,
                style=0.3,
                use_speaker_boost=True,
            ),
        )

        # Collect audio chunks and alignment data
        audio_chunks: list[bytes] = []
        alignment_data: Optional[dict] = None

        for item in response:
            if hasattr(item, "audio_base64") and item.audio_base64:
                audio_chunks.append(base64.b64decode(item.audio_base64))
            if hasattr(item, "alignment") and item.alignment is not None:
                alignment_data = {
                    "characters": list(item.alignment.characters),
                    "character_start_times_seconds": list(
                        item.alignment.character_start_times_seconds
                    ),
                    "character_end_times_seconds": list(
                        item.alignment.character_end_times_seconds
                    ),
                }

        if not audio_chunks:
            logger.error("No audio data received from ElevenLabs")
            return None

        # Write audio file
        with open(output_path, "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)

        if output_path.stat().st_size < 1000:
            logger.warning("Timestamped narration file is empty/corrupt, removing")
            output_path.unlink()
            return None

        # Parse alignment into word timestamps
        if alignment_data is None:
            logger.warning("No alignment data returned -- falling back to empty timestamps")
            return output_path, []

        words = _characters_to_words(alignment_data)
        logger.info(
            f"Timestamped narration saved: {output_path.name} "
            f"({output_path.stat().st_size / 1024:.0f} KB, "
            f"{len(words)} words, voice={voice['name']})"
        )
        return output_path, words

    except Exception as e:
        logger.error(f"Timestamped TTS narration failed: {e}")
        if output_path.exists() and output_path.stat().st_size < 1000:
            output_path.unlink()
        return None


def _characters_to_words(alignment: dict) -> list[WordTimestamp]:
    """Convert character-level alignment to word-level timestamps.

    ElevenLabs returns parallel arrays:
      - characters: list of individual characters
      - character_start_times_seconds: start time per character
      - character_end_times_seconds: end time per character

    Words are delimited by spaces. We take the start time of the first
    character and end time of the last character in each word.
    """
    characters = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]

    if not characters:
        return []

    words: list[WordTimestamp] = []
    current_word_chars: list[str] = []
    word_start: Optional[float] = None
    word_end: float = 0.0

    for i, char in enumerate(characters):
        if char == " ":
            # End of word
            if current_word_chars:
                word_text = "".join(current_word_chars)
                words.append(WordTimestamp(
                    word=word_text,
                    start_time=word_start if word_start is not None else 0.0,
                    end_time=word_end,
                ))
                current_word_chars = []
                word_start = None
        else:
            current_word_chars.append(char)
            if word_start is None:
                word_start = starts[i]
            word_end = ends[i]

    # Flush last word
    if current_word_chars:
        word_text = "".join(current_word_chars)
        words.append(WordTimestamp(
            word=word_text,
            start_time=word_start if word_start is not None else 0.0,
            end_time=word_end,
        ))

    return words


def group_into_phrases(words: list[WordTimestamp]) -> list[Phrase]:
    """Group words into natural 3-5 word phrases for on-screen display.

    Phrase break rules:
      1. Break after punctuation at end of word (, . ; : ! ? -- -)
      2. Break when word count reaches MAX_PHRASE_WORDS (5)
      3. Try to keep at least MIN_PHRASE_WORDS (2) per phrase unless
         punctuation forces an earlier break
      4. Final phrase gets whatever is left

    Args:
        words: List of word timestamps from ElevenLabs alignment.

    Returns:
        List of Phrase objects with aggregated text and timing.
    """
    if not words:
        return []

    phrases: list[Phrase] = []
    current_words: list[WordTimestamp] = []

    for word in words:
        current_words.append(word)

        # Check if this word ends with phrase-break punctuation
        has_break_punct = _ends_with_break_punctuation(word.word)

        # Decide whether to break
        should_break = False
        if len(current_words) >= MAX_PHRASE_WORDS:
            should_break = True
        elif has_break_punct and len(current_words) >= MIN_PHRASE_WORDS:
            should_break = True

        if should_break:
            phrases.append(_build_phrase(current_words))
            current_words = []

    # Flush remaining words
    if current_words:
        # If remaining is just 1 word and we have a previous phrase, merge it
        if len(current_words) == 1 and phrases:
            last = phrases.pop()
            merged_words = list(last.words) + current_words
            phrases.append(_build_phrase(merged_words))
        else:
            phrases.append(_build_phrase(current_words))

    return phrases


def _ends_with_break_punctuation(word: str) -> bool:
    """Check if a word ends with punctuation that should trigger a phrase break."""
    if not word:
        return False
    # Strip trailing quotes/parens to check the actual punctuation
    stripped = word.rstrip("\"')")
    if not stripped:
        return False
    return stripped[-1] in PHRASE_BREAK_CHARS


def _build_phrase(words: list[WordTimestamp]) -> Phrase:
    """Build a Phrase from a list of WordTimestamp objects."""
    text = " ".join(w.word for w in words)
    return Phrase(
        text=text,
        start_time=words[0].start_time,
        end_time=words[-1].end_time,
        words=tuple(words),
    )
