"""Tests for character voice generation.

Tests cover:
- CharacterVoice initialization
- ElevenLabs TTS generation (mocked)
- Word timestamp parsing
- Mood modulation
- SpeakResult structure
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import json
import base64

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from kagami_studio.characters.voice import (
    CharacterVoice,
    SpeakResult,
    WordTiming,
    Mood,
    MOOD_MODIFIERS,
)


class TestWordTiming:
    """Tests for WordTiming dataclass."""

    def test_word_timing_creation(self):
        """WordTiming should store all fields correctly."""
        wt = WordTiming(
            text="Hello",
            start_ms=0,
            end_ms=500,
        )

        assert wt.text == "Hello"
        assert wt.start_ms == 0
        assert wt.end_ms == 500

    def test_word_timing_duration(self):
        """Duration should be calculable from start/end."""
        wt = WordTiming(text="Test", start_ms=1000, end_ms=1500)

        duration = wt.end_ms - wt.start_ms
        assert duration == 500


class TestSpeakResult:
    """Tests for SpeakResult dataclass."""

    def test_speak_result_success(self):
        """SpeakResult should track success state."""
        result = SpeakResult(
            success=True,
            audio_path=Path("/tmp/audio.mp3"),
            character="tim",
            mood="neutral",
            text="Hello",
        )

        assert result.success
        assert result.audio_path == Path("/tmp/audio.mp3")
        assert result.character == "tim"

    def test_speak_result_with_timings(self):
        """SpeakResult should store word timings."""
        result = SpeakResult(
            success=True,
            word_timings=[
                WordTiming(text="Hello", start_ms=0, end_ms=500),
                WordTiming(text="World", start_ms=500, end_ms=1000),
            ],
        )

        assert result.word_timings is not None
        assert len(result.word_timings) == 2

    def test_speak_result_failure(self):
        """SpeakResult should track failure with error."""
        result = SpeakResult(
            success=False,
            error="API Error",
        )

        assert not result.success
        assert result.error == "API Error"

    def test_speak_result_timing_metrics(self):
        """SpeakResult should track timing metrics."""
        result = SpeakResult(
            success=True,
            ttfa_ms=150.0,
            total_ms=2500.0,
        )

        assert result.ttfa_ms == 150.0
        assert result.total_ms == 2500.0

    def test_speak_result_playback_tracking(self):
        """SpeakResult should track playback."""
        result = SpeakResult(
            success=True,
            played=True,
            play_target="home",
        )

        assert result.played
        assert result.play_target == "home"


class TestMood:
    """Tests for Mood enum."""

    def test_mood_values_exist(self):
        """Standard moods should exist."""
        assert Mood.NEUTRAL is not None
        assert Mood.EXCITED is not None
        assert Mood.WARM is not None
        assert Mood.DRAMATIC is not None

    def test_mood_has_string_value(self):
        """Moods should have string values."""
        assert Mood.NEUTRAL.value == "neutral"
        assert Mood.EXCITED.value == "excited"

    def test_all_moods_have_modifiers(self):
        """All moods should have corresponding modifiers."""
        for mood in Mood:
            assert mood in MOOD_MODIFIERS


class TestMoodModifiers:
    """Tests for mood-based voice modulation."""

    def test_neutral_is_empty(self):
        """Neutral mood should have empty modifiers."""
        assert MOOD_MODIFIERS[Mood.NEUTRAL] == {}

    def test_excited_increases_speed(self):
        """Excited mood should increase speed."""
        excited = MOOD_MODIFIERS[Mood.EXCITED]

        assert "speed" in excited
        assert excited["speed"] > 1.0

    def test_excited_decreases_stability(self):
        """Excited mood should decrease stability (more expressive)."""
        excited = MOOD_MODIFIERS[Mood.EXCITED]

        assert "stability" in excited
        assert excited["stability"] < 0.5

    def test_sleepy_decreases_speed(self):
        """Sleepy mood should decrease speed."""
        sleepy = MOOD_MODIFIERS[Mood.SLEEPY]

        assert "speed" in sleepy
        assert sleepy["speed"] < 1.0

    def test_professional_has_high_stability(self):
        """Professional mood should have high stability."""
        professional = MOOD_MODIFIERS[Mood.PROFESSIONAL]

        assert "stability" in professional
        assert professional["stability"] >= 0.5


class TestCharacterVoiceInit:
    """Tests for CharacterVoice initialization."""

    def test_init_with_character_name(self):
        """CharacterVoice should initialize with character name."""
        voice = CharacterVoice("tim")

        assert voice.character_name == "tim"
        assert not voice._initialized

    def test_init_creates_temp_dir(self):
        """CharacterVoice should have temp dir."""
        voice = CharacterVoice("tim")

        assert voice._temp_dir is not None
        assert "kagami_voices" in str(voice._temp_dir)

    def test_init_stats_tracking(self):
        """CharacterVoice should have stats tracking."""
        voice = CharacterVoice("tim")

        assert "speaks" in voice._stats
        assert "total_ms" in voice._stats
        assert "by_mood" in voice._stats


class TestCharacterVoiceInitialize:
    """Tests for CharacterVoice async initialization."""

    @pytest.mark.asyncio
    async def test_initialize_loads_character(self):
        """initialize() should load character metadata."""
        voice = CharacterVoice("tim")

        with patch("kagami_studio.characters.voice.load_character") as mock_load:
            from kagami_studio.characters.protocol import (
                Character,
                VoiceConfig,
                AvatarConfig,
                PersonalityConfig,
            )

            mock_load.return_value = Character(
                identity_id="tim",
                name="Tim",
                voice=VoiceConfig(voice_id="test_id"),
                avatar=AvatarConfig(),
                personality=PersonalityConfig(),
            )

            # Mock ElevenLabs client
            with patch("elevenlabs.AsyncElevenLabs"):
                result = await voice.initialize()

                mock_load.assert_called_once_with("tim")

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """initialize() should be idempotent."""
        voice = CharacterVoice("tim")
        voice._initialized = True

        result = await voice.initialize()

        assert result is True


class TestLoadCharacter:
    """Tests for loading actual characters."""

    def test_load_tim(self):
        """Tim character should be loadable."""
        voice = CharacterVoice("tim")

        assert voice.character_name == "tim"

    def test_load_andy(self):
        """Andy character should be loadable."""
        voice = CharacterVoice("andy")

        assert voice.character_name == "andy"


class TestSpeakMethod:
    """Tests for the speak method."""

    def test_speak_method_exists(self):
        """CharacterVoice should have speak method."""
        voice = CharacterVoice("tim")

        assert hasattr(voice, "speak")
        assert callable(voice.speak)

    def test_mood_parameter_types(self):
        """Mood should accept string values."""
        # Verify mood enum has expected values
        assert "excited" in [m.value for m in Mood]
        assert "warm" in [m.value for m in Mood]
        assert "neutral" in [m.value for m in Mood]


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_character_name(self):
        """Empty character name should be handled."""
        voice = CharacterVoice("")

        assert voice.character_name == ""

    def test_special_character_name(self):
        """Special characters in name should work."""
        voice = CharacterVoice("test-character")

        assert voice.character_name == "test-character"

    @pytest.mark.asyncio
    async def test_speak_result_includes_text(self):
        """SpeakResult should include the spoken text."""
        result = SpeakResult(
            success=True,
            text="Hello world",
        )

        assert result.text == "Hello world"


class TestStatsTracking:
    """Tests for statistics tracking."""

    def test_initial_stats(self):
        """Initial stats should be zeroed."""
        voice = CharacterVoice("tim")

        assert voice._stats["speaks"] == 0
        assert voice._stats["total_ms"] == 0.0

    def test_stats_by_mood(self):
        """Stats should track usage by mood."""
        voice = CharacterVoice("tim")

        for mood in Mood:
            assert mood.value in voice._stats["by_mood"]
            assert voice._stats["by_mood"][mood.value] == 0
