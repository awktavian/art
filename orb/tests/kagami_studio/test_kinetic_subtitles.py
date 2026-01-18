"""Tests for kinetic subtitle generation.

Tests cover:
- Emotion keyword detection
- Word timing grouping into lines
- ASS format generation
- Multi-language support
- Edge cases (punctuation, empty input)
"""

import pytest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from kagami_studio.subtitles.kinetic import (
    KineticSubtitleGenerator,
    WordTiming,
    EmotionStyle,
    EMOTION_KEYWORDS,
)


class TestEmotionDetection:
    """Tests for emotion keyword detection."""

    def test_power_words_detected(self):
        """Power words like AI, exponential should be detected."""
        gen = KineticSubtitleGenerator(language="en")

        assert gen.detect_emotion("AI") == EmotionStyle.POWER
        assert gen.detect_emotion("exponential") == EmotionStyle.POWER
        assert gen.detect_emotion("capability") == EmotionStyle.POWER

    def test_heart_words_detected(self):
        """Heart words like team, people should be detected."""
        gen = KineticSubtitleGenerator(language="en")

        assert gen.detect_emotion("team") == EmotionStyle.HEART
        assert gen.detect_emotion("people") == EmotionStyle.HEART
        assert gen.detect_emotion("love") == EmotionStyle.HEART

    def test_punctuation_stripped(self):
        """Punctuation should be stripped before emotion lookup."""
        gen = KineticSubtitleGenerator(language="en")

        assert gen.detect_emotion("AI.") == EmotionStyle.POWER
        assert gen.detect_emotion("team,") == EmotionStyle.HEART
        assert gen.detect_emotion("(exponential)") == EmotionStyle.POWER

    def test_unknown_words_return_none(self):
        """Unknown words should return NONE emotion."""
        gen = KineticSubtitleGenerator(language="en")

        assert gen.detect_emotion("the") == EmotionStyle.NONE
        assert gen.detect_emotion("random") == EmotionStyle.NONE

    def test_dutch_keywords(self):
        """Dutch emotion keywords should work."""
        gen = KineticSubtitleGenerator(language="nl")

        assert gen.detect_emotion("AI") == EmotionStyle.POWER
        assert gen.detect_emotion("team") == EmotionStyle.HEART
        assert gen.detect_emotion("exponentieel") == EmotionStyle.POWER


class TestLineGrouping:
    """Tests for word grouping into subtitle lines."""

    def test_speaker_change_creates_new_line(self):
        """Speaker change should create a new line."""
        gen = KineticSubtitleGenerator()

        words = [
            WordTiming(text="Hello", start_ms=0, end_ms=500, speaker="tim"),
            WordTiming(text="Hi", start_ms=600, end_ms=1000, speaker="andy"),
        ]

        lines = gen._group_into_lines(words)

        assert len(lines) == 2
        assert lines[0].words[0].speaker == "tim"
        assert lines[1].words[0].speaker == "andy"

    def test_long_pause_creates_new_line(self):
        """Long pause (>1500ms) should create a new line."""
        gen = KineticSubtitleGenerator()

        words = [
            WordTiming(text="First", start_ms=0, end_ms=500, speaker="tim"),
            WordTiming(text="Second", start_ms=2500, end_ms=3000, speaker="tim"),
        ]

        lines = gen._group_into_lines(words)

        assert len(lines) == 2

    def test_max_words_per_line(self):
        """Lines should break at punctuation when near max length."""
        gen = KineticSubtitleGenerator()

        # Create 20 words - should split at punctuation
        words = [
            WordTiming(
                text=f"word{i}{'.' if i == 14 else ''}",
                start_ms=i * 100,
                end_ms=(i + 1) * 100,
                speaker="tim",
            )
            for i in range(20)
        ]

        lines = gen._group_into_lines(words)

        # Should have multiple lines
        assert len(lines) >= 2

    def test_empty_input(self):
        """Empty input should return empty list."""
        gen = KineticSubtitleGenerator()

        lines = gen._group_into_lines([])

        assert lines == []


class TestASSGeneration:
    """Tests for ASS subtitle format generation."""

    def test_ass_header_contains_styles(self):
        """Generated ASS should contain style definitions."""
        gen = KineticSubtitleGenerator()

        words = [WordTiming(text="Test", start_ms=0, end_ms=1000)]
        ass_content = gen.generate(words)

        assert "[Script Info]" in ass_content
        assert "[V4+ Styles]" in ass_content
        assert "Style: Default" in ass_content
        assert "Style: Power" in ass_content
        assert "Style: Heart" in ass_content

    def test_ass_contains_dialogue_events(self):
        """Generated ASS should contain dialogue events."""
        gen = KineticSubtitleGenerator()

        words = [
            WordTiming(text="Hello", start_ms=0, end_ms=500),
            WordTiming(text="World", start_ms=500, end_ms=1000),
        ]
        ass_content = gen.generate(words)

        assert "Dialogue:" in ass_content
        assert "Hello" in ass_content
        assert "World" in ass_content

    def test_emotion_styling_applied(self):
        """Emotion words should have styling in output."""
        gen = KineticSubtitleGenerator(language="en")

        words = [
            WordTiming(text="The", start_ms=0, end_ms=300),
            WordTiming(text="AI", start_ms=300, end_ms=600),  # Power word
            WordTiming(text="helps", start_ms=600, end_ms=900),
        ]
        ass_content = gen.generate(words)

        # Should have color override for AI
        assert "\\c&H" in ass_content or "\\b1" in ass_content

    def test_time_format_correct(self):
        """Time format should be H:MM:SS.cc."""
        gen = KineticSubtitleGenerator()

        # Test the internal time conversion
        assert gen._ms_to_ass_time(0) == "0:00:00.00"
        assert gen._ms_to_ass_time(1000) == "0:00:01.00"
        assert gen._ms_to_ass_time(61000) == "0:01:01.00"
        assert gen._ms_to_ass_time(3661000) == "1:01:01.00"
        assert gen._ms_to_ass_time(1550) == "0:00:01.55"

    def test_output_file_written(self, tmp_path):
        """Output should be written to file when path provided."""
        gen = KineticSubtitleGenerator()
        output_file = tmp_path / "test.ass"

        words = [WordTiming(text="Test", start_ms=0, end_ms=1000)]
        gen.generate(words, output_path=output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "[Script Info]" in content


class TestWordByWordReveal:
    """Tests for word-by-word reveal behavior."""

    def test_each_word_gets_event(self):
        """Each word should create a dialogue event showing words up to that point."""
        gen = KineticSubtitleGenerator()

        words = [
            WordTiming(text="One", start_ms=0, end_ms=300),
            WordTiming(text="Two", start_ms=300, end_ms=600),
            WordTiming(text="Three", start_ms=600, end_ms=900),
        ]
        ass_content = gen.generate(words)

        # Count dialogue lines
        dialogue_count = ass_content.count("Dialogue:")

        # Should have 3 dialogue events (one per word)
        assert dialogue_count == 3

    def test_progressive_text_buildup(self):
        """Each event should show all previous words plus current."""
        gen = KineticSubtitleGenerator()

        words = [
            WordTiming(text="Hello", start_ms=0, end_ms=500),
            WordTiming(text="World", start_ms=500, end_ms=1000),
        ]
        ass_content = gen.generate(words)

        lines = [l for l in ass_content.split("\n") if l.startswith("Dialogue:")]

        # First event: "Hello"
        assert "Hello" in lines[0]
        assert "World" not in lines[0]

        # Second event: "Hello World"
        assert "Hello" in lines[1]
        assert "World" in lines[1]


class TestMultiLanguage:
    """Tests for multi-language support."""

    def test_dutch_emotion_keywords_loaded(self):
        """Dutch keywords should be loaded when language is nl."""
        gen = KineticSubtitleGenerator(language="nl")

        assert "nl" in EMOTION_KEYWORDS
        assert gen.keywords == EMOTION_KEYWORDS["nl"]

    def test_fallback_to_english(self):
        """Unknown language should fall back to English keywords."""
        gen = KineticSubtitleGenerator(language="unknown")

        assert gen.keywords == EMOTION_KEYWORDS["en"]


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_single_word(self):
        """Single word should work."""
        gen = KineticSubtitleGenerator()

        words = [WordTiming(text="Hello", start_ms=0, end_ms=500)]
        ass_content = gen.generate(words)

        assert "Hello" in ass_content
        assert "Dialogue:" in ass_content

    def test_very_long_word(self):
        """Very long words should work."""
        gen = KineticSubtitleGenerator()

        long_word = "supercalifragilisticexpialidocious"
        words = [WordTiming(text=long_word, start_ms=0, end_ms=5000)]
        ass_content = gen.generate(words)

        assert long_word in ass_content

    def test_special_characters(self):
        """Special characters should be handled."""
        gen = KineticSubtitleGenerator()

        words = [
            WordTiming(text="Don't", start_ms=0, end_ms=500),
            WordTiming(text="stop!", start_ms=500, end_ms=1000),
        ]
        ass_content = gen.generate(words)

        assert "Don't" in ass_content
        assert "stop!" in ass_content

    def test_dict_input(self):
        """Dict input should be converted to WordTiming."""
        gen = KineticSubtitleGenerator()

        words = [
            {"text": "Hello", "start_ms": 0, "end_ms": 500},
            {"text": "World", "start_ms": 500, "end_ms": 1000},
        ]
        ass_content = gen.generate(words)

        assert "Hello" in ass_content
        assert "World" in ass_content
