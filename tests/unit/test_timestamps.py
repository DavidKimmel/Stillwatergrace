"""Tests for core.audio.timestamps — word timestamp parsing and phrase grouping."""

import pytest

from core.audio.timestamps import (
    Phrase,
    WordTimestamp,
    _build_phrase,
    _characters_to_words,
    _ends_with_break_punctuation,
    group_into_phrases,
)


# ── _characters_to_words tests ──


class TestCharactersToWords:
    """Test conversion from character-level alignment to word-level timestamps."""

    def test_single_word(self) -> None:
        alignment = {
            "characters": ["H", "i"],
            "character_start_times_seconds": [0.0, 0.1],
            "character_end_times_seconds": [0.1, 0.2],
        }
        words = _characters_to_words(alignment)
        assert len(words) == 1
        assert words[0].word == "Hi"
        assert words[0].start_time == 0.0
        assert words[0].end_time == 0.2

    def test_two_words(self) -> None:
        alignment = {
            "characters": ["B", "e", " ", "s", "t", "i", "l", "l"],
            "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
            "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        }
        words = _characters_to_words(alignment)
        assert len(words) == 2
        assert words[0].word == "Be"
        assert words[0].start_time == 0.0
        assert words[0].end_time == 0.2
        assert words[1].word == "still"
        assert words[1].start_time == 0.3
        assert words[1].end_time == 0.8

    def test_multiple_spaces(self) -> None:
        """Multiple consecutive spaces should not create empty words."""
        alignment = {
            "characters": ["a", " ", " ", "b"],
            "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3],
            "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4],
        }
        words = _characters_to_words(alignment)
        assert len(words) == 2
        assert words[0].word == "a"
        assert words[1].word == "b"

    def test_empty_input(self) -> None:
        alignment = {
            "characters": [],
            "character_start_times_seconds": [],
            "character_end_times_seconds": [],
        }
        words = _characters_to_words(alignment)
        assert words == []

    def test_punctuation_attached_to_word(self) -> None:
        alignment = {
            "characters": ["G", "o", "d", ",", " ", "a", "n", "d"],
            "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
            "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        }
        words = _characters_to_words(alignment)
        assert len(words) == 2
        assert words[0].word == "God,"
        assert words[1].word == "and"

    def test_trailing_space(self) -> None:
        """Trailing space should not create an empty word."""
        alignment = {
            "characters": ["o", "k", " "],
            "character_start_times_seconds": [0.0, 0.1, 0.2],
            "character_end_times_seconds": [0.1, 0.2, 0.3],
        }
        words = _characters_to_words(alignment)
        assert len(words) == 1
        assert words[0].word == "ok"

    def test_verse_with_reference(self) -> None:
        """Full verse text with reference at end."""
        text = "Be still and know that I am God."
        chars = list(text)
        n = len(chars)
        starts = [i * 0.1 for i in range(n)]
        ends = [(i + 1) * 0.1 for i in range(n)]
        alignment = {
            "characters": chars,
            "character_start_times_seconds": starts,
            "character_end_times_seconds": ends,
        }
        words = _characters_to_words(alignment)
        assert len(words) == 8
        assert words[0].word == "Be"
        assert words[-1].word == "God."


# ── _ends_with_break_punctuation tests ──


class TestBreakPunctuation:
    def test_comma(self) -> None:
        assert _ends_with_break_punctuation("Lord,") is True

    def test_period(self) -> None:
        assert _ends_with_break_punctuation("God.") is True

    def test_semicolon(self) -> None:
        assert _ends_with_break_punctuation("life;") is True

    def test_colon(self) -> None:
        assert _ends_with_break_punctuation("says:") is True

    def test_no_punctuation(self) -> None:
        assert _ends_with_break_punctuation("and") is False

    def test_empty_string(self) -> None:
        assert _ends_with_break_punctuation("") is False

    def test_dash(self) -> None:
        assert _ends_with_break_punctuation("peace-") is True

    def test_em_dash(self) -> None:
        assert _ends_with_break_punctuation("peace\u2014") is True

    def test_trailing_quote(self) -> None:
        """Punctuation before closing quote should still trigger break."""
        assert _ends_with_break_punctuation('world,"') is True

    def test_exclamation(self) -> None:
        assert _ends_with_break_punctuation("Amen!") is True

    def test_question(self) -> None:
        assert _ends_with_break_punctuation("Lord?") is True


# ── group_into_phrases tests ──


def _make_words(texts: list[str], gap: float = 0.3) -> list[WordTimestamp]:
    """Helper: create WordTimestamp list with sequential timing."""
    words = []
    t = 0.0
    for text in texts:
        duration = len(text) * 0.05 + 0.1
        words.append(WordTimestamp(word=text, start_time=t, end_time=t + duration))
        t += duration + gap
    return words


class TestGroupIntoPhrases:
    def test_empty_input(self) -> None:
        assert group_into_phrases([]) == []

    def test_short_text_single_phrase(self) -> None:
        """Two words should form a single phrase."""
        words = _make_words(["Be", "still"])
        phrases = group_into_phrases(words)
        assert len(phrases) == 1
        assert phrases[0].text == "Be still"

    def test_max_words_break(self) -> None:
        """Should break at 5 words (MAX_PHRASE_WORDS)."""
        words = _make_words(["one", "two", "three", "four", "five", "six", "seven"])
        phrases = group_into_phrases(words)
        assert len(phrases) == 2
        assert phrases[0].text == "one two three four five"
        assert phrases[1].text == "six seven"

    def test_punctuation_break(self) -> None:
        """Should break at comma when min words met."""
        words = _make_words(["Be", "still,", "and", "know"])
        phrases = group_into_phrases(words)
        assert len(phrases) == 2
        assert phrases[0].text == "Be still,"
        assert phrases[1].text == "and know"

    def test_punctuation_below_min_no_break(self) -> None:
        """Single word with comma should NOT break (below MIN_PHRASE_WORDS=2)."""
        words = _make_words(["Still,", "and", "know", "that"])
        phrases = group_into_phrases(words)
        # "Still," is only 1 word — punctuation break skipped, continues to 5
        # Actually breaks at "Still, and" (2 words) since comma is at word 1 but min is 2
        # First phrase needs 2+ words. "Still," is word 1 — no break.
        # "Still, and" is 2 words — "Still," has punct, but break check is on "Still,"
        # when len==1 < MIN=2. Next check: "and" no punct, len==2.
        # "know" no punct, len==3. "that" no punct, len==4.
        # Hits end -> flush as single phrase
        assert len(phrases) == 1
        assert phrases[0].text == "Still, and know that"

    def test_merge_trailing_single_word(self) -> None:
        """A trailing single word should merge with the previous phrase."""
        words = _make_words(["one", "two", "three", "four", "five", "six"])
        phrases = group_into_phrases(words)
        # 5-word break: ["one two three four five"], then ["six"] -> merged
        assert len(phrases) == 1
        assert phrases[0].text == "one two three four five six"

    def test_no_merge_when_two_trailing(self) -> None:
        """Two trailing words form their own phrase (not merged)."""
        words = _make_words(["one", "two", "three", "four", "five", "six", "seven"])
        phrases = group_into_phrases(words)
        assert len(phrases) == 2
        assert phrases[1].text == "six seven"

    def test_timing_preserved(self) -> None:
        """Phrase start/end times should match first/last word."""
        words = _make_words(["Be", "still", "and", "know"])
        phrases = group_into_phrases(words)
        assert phrases[0].start_time == words[0].start_time
        assert phrases[0].end_time == words[-1].end_time

    def test_full_verse(self) -> None:
        """Full verse should produce reasonable phrase count."""
        verse = "Be still and know that I am God"
        word_list = verse.split()
        words = _make_words(word_list)
        phrases = group_into_phrases(words)
        # 8 words -> 5 + 3 = 2 phrases
        assert len(phrases) == 2
        assert phrases[0].text == "Be still and know that"
        assert phrases[1].text == "I am God"

    def test_verse_with_punctuation(self) -> None:
        """Verse with commas should break at natural points."""
        word_list = ["For", "God", "so", "loved", "the", "world,",
                     "that", "he", "gave", "his", "only"]
        words = _make_words(word_list)
        phrases = group_into_phrases(words)
        # Breaks: "For God so loved the" (5 max) -> "world, that" or
        # Actually: accumulate until 5 or punct+min2
        # 1: For (1, no punct)
        # 2: God (2, no punct)
        # 3: so (3, no punct)
        # 4: loved (4, no punct)
        # 5: the (5, MAX -> break) -> "For God so loved the"
        # 6: world, (1, punct but <2 min)
        # 7: that (2, no punct)
        # 8: he (3, no punct)
        # 9: gave (4, no punct)
        # 10: his (5, MAX -> break) -> "world, that he gave his"
        # 11: only -> flush, single word -> merge with prev
        assert len(phrases) == 2
        assert "For God so loved the" == phrases[0].text
        assert "world, that he gave his only" == phrases[1].text

    def test_words_tuple_is_frozen(self) -> None:
        """Phrase.words should be a tuple (frozen)."""
        words = _make_words(["Be", "still"])
        phrases = group_into_phrases(words)
        assert isinstance(phrases[0].words, tuple)


# ── _build_phrase tests ──


class TestBuildPhrase:
    def test_basic(self) -> None:
        words = [
            WordTimestamp(word="Be", start_time=0.0, end_time=0.2),
            WordTimestamp(word="still", start_time=0.3, end_time=0.5),
        ]
        phrase = _build_phrase(words)
        assert phrase.text == "Be still"
        assert phrase.start_time == 0.0
        assert phrase.end_time == 0.5
        assert len(phrase.words) == 2
