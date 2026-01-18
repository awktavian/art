"""Unit tests for KagamiVoice TTS service.

Tests the colony voice settings, model selection, and synthesis logic
without requiring actual ElevenLabs API calls.

Created: January 11, 2026
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.tier_unit


# =============================================================================
# Imports
# =============================================================================


def get_colony_enum():
    """Import Colony enum."""
    from kagami.core.services.voice.kagami_voice import Colony

    return Colony


def get_model_enum():
    """Import Model enum."""
    from kagami.core.services.voice.kagami_voice import Model

    return Model


def get_colony_voice_settings():
    """Import ColonyVoiceSettings and COLONY_VOICE_SETTINGS."""
    from kagami.core.services.voice.kagami_voice import (
        COLONY_VOICE_SETTINGS,
        ColonyVoiceSettings,
    )

    return ColonyVoiceSettings, COLONY_VOICE_SETTINGS


# =============================================================================
# Colony Enum Tests
# =============================================================================


class TestColonyEnum:
    """Test Colony enum values and properties."""

    def test_all_colonies_exist(self):
        """Test all expected colonies are defined."""
        Colony = get_colony_enum()

        expected = ["kagami", "spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]

        for name in expected:
            assert hasattr(Colony, name.upper()), f"Colony.{name.upper()} should exist"

    def test_colony_values(self):
        """Test colony values are lowercase strings."""
        Colony = get_colony_enum()

        assert Colony.KAGAMI.value == "kagami"
        assert Colony.SPARK.value == "spark"
        assert Colony.FORGE.value == "forge"
        assert Colony.FLOW.value == "flow"
        assert Colony.NEXUS.value == "nexus"
        assert Colony.BEACON.value == "beacon"
        assert Colony.GROVE.value == "grove"
        assert Colony.CRYSTAL.value == "crystal"

    def test_colony_is_string_enum(self):
        """Test Colony is a string enum for easy comparison."""
        Colony = get_colony_enum()

        assert Colony.KAGAMI == "kagami"
        assert str(Colony.SPARK) == "spark"

    def test_colony_count(self):
        """Test we have exactly 8 colonies."""
        Colony = get_colony_enum()

        assert len(Colony) == 8


# =============================================================================
# Model Enum Tests
# =============================================================================


class TestModelEnum:
    """Test Model enum values."""

    def test_all_models_exist(self):
        """Test all expected models are defined."""
        Model = get_model_enum()

        assert hasattr(Model, "FLASH")
        assert hasattr(Model, "TURBO")
        assert hasattr(Model, "QUALITY")
        assert hasattr(Model, "V3")

    def test_model_values_are_elevenlabs_ids(self):
        """Test model values are valid ElevenLabs model IDs."""
        Model = get_model_enum()

        assert Model.FLASH.value == "eleven_flash_v2_5"
        assert Model.TURBO.value == "eleven_turbo_v2_5"
        assert Model.QUALITY.value == "eleven_multilingual_v2"
        assert Model.V3.value == "eleven_v3"

    def test_flash_is_fastest(self):
        """Document that FLASH is the low-latency model."""
        Model = get_model_enum()

        # Flash is explicitly for 75ms latency real-time use
        assert "flash" in Model.FLASH.value


# =============================================================================
# ColonyVoiceSettings Tests
# =============================================================================


class TestColonyVoiceSettings:
    """Test ColonyVoiceSettings dataclass and configurations."""

    def test_colony_voice_settings_creation(self):
        """Test creating a ColonyVoiceSettings instance."""
        ColonyVoiceSettings, _ = get_colony_voice_settings()
        Colony = get_colony_enum()

        settings = ColonyVoiceSettings(
            colony=Colony.KAGAMI,
            stability=0.5,
            similarity_boost=0.75,
            style=0.3,
            speed=1.0,
        )

        assert settings.colony == Colony.KAGAMI
        assert settings.stability == 0.5
        assert settings.similarity_boost == 0.75
        assert settings.style == 0.3
        assert settings.speed == 1.0
        assert settings.use_speaker_boost is True  # Default

    def test_colony_voice_settings_to_elevenlabs(self):
        """Test conversion to ElevenLabs format."""
        ColonyVoiceSettings, _ = get_colony_voice_settings()
        Colony = get_colony_enum()

        settings = ColonyVoiceSettings(
            colony=Colony.SPARK,
            stability=0.32,
            similarity_boost=0.75,
            style=0.48,
            speed=1.06,
        )

        eleven_dict = settings.to_elevenlabs()

        assert eleven_dict["stability"] == 0.32
        assert eleven_dict["similarity_boost"] == 0.75
        assert eleven_dict["style"] == 0.48
        assert eleven_dict["speed"] == 1.06
        assert eleven_dict["use_speaker_boost"] is True

    def test_colony_voice_settings_immutable(self):
        """Test ColonyVoiceSettings is frozen (immutable)."""
        ColonyVoiceSettings, _ = get_colony_voice_settings()
        Colony = get_colony_enum()

        settings = ColonyVoiceSettings(
            colony=Colony.FLOW,
            stability=0.42,
            similarity_boost=0.75,
            style=0.28,
            speed=0.98,
        )

        with pytest.raises(AttributeError):
            settings.stability = 0.5  # type: ignore


# =============================================================================
# COLONY_VOICE_SETTINGS Dictionary Tests
# =============================================================================


class TestColonyVoiceSettingsDict:
    """Test the COLONY_VOICE_SETTINGS configuration dictionary."""

    def test_all_colonies_have_settings(self):
        """Test every colony has voice settings defined."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        for colony in Colony:
            assert colony in COLONY_VOICE_SETTINGS, f"{colony} should have settings"

    def test_kagami_is_default_balanced(self):
        """Test Kagami settings are balanced/natural."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        kagami = COLONY_VOICE_SETTINGS[Colony.KAGAMI]

        # Balanced stability (not too variable, not monotone)
        assert 0.4 <= kagami.stability <= 0.5
        # Natural pace
        assert kagami.speed == 1.0

    def test_spark_is_energetic(self):
        """Test Spark settings express energy."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        spark = COLONY_VOICE_SETTINGS[Colony.SPARK]

        # Lower stability = more emotional variation
        assert spark.stability < 0.4
        # Higher style = more expressive
        assert spark.style > 0.4
        # Faster pace
        assert spark.speed > 1.0

    def test_forge_is_deliberate(self):
        """Test Forge settings express deliberation."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        forge = COLONY_VOICE_SETTINGS[Colony.FORGE]

        # Higher stability = consistent, deliberate
        assert forge.stability > 0.5
        # Slightly slower = measured
        assert forge.speed < 1.0

    def test_flow_is_adaptive(self):
        """Test Flow settings express smooth adaptability."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        flow = COLONY_VOICE_SETTINGS[Colony.FLOW]

        # Lower style = smooth, not dramatic
        assert flow.style < 0.3
        # Natural/unhurried
        assert 0.95 <= flow.speed <= 1.0

    def test_beacon_is_clear_direct(self):
        """Test Beacon settings express clarity."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        beacon = COLONY_VOICE_SETTINGS[Colony.BEACON]

        # High stability = clear, stable
        assert beacon.stability >= 0.5
        # High similarity_boost = clear signal
        assert beacon.similarity_boost >= 0.8
        # Lower style = professional, not dramatic
        assert beacon.style < 0.25

    def test_grove_is_warm_exploratory(self):
        """Test Grove settings express warmth and curiosity."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        grove = COLONY_VOICE_SETTINGS[Colony.GROVE]

        # Lower stability = curious variation
        assert grove.stability < 0.4
        # Warmer style
        assert grove.style >= 0.4
        # Unhurried exploration
        assert grove.speed < 1.0

    def test_crystal_is_precise(self):
        """Test Crystal settings express precision."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        crystal = COLONY_VOICE_SETTINGS[Colony.CRYSTAL]

        # High stability = precise, stable
        assert crystal.stability >= 0.5
        # High similarity_boost = authoritative
        assert crystal.similarity_boost >= 0.8

    def test_all_settings_in_valid_ranges(self):
        """Test all voice settings are within ElevenLabs valid ranges."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()

        for colony, settings in COLONY_VOICE_SETTINGS.items():
            assert 0.0 <= settings.stability <= 1.0, f"{colony} stability out of range"
            assert 0.0 <= settings.similarity_boost <= 1.0, (
                f"{colony} similarity_boost out of range"
            )
            assert 0.0 <= settings.style <= 1.0, f"{colony} style out of range"
            assert 0.5 <= settings.speed <= 2.0, f"{colony} speed out of range"


# =============================================================================
# Voice Settings Conversion Tests
# =============================================================================


class TestVoiceSettingsConversion:
    """Test converting settings to ElevenLabs API format."""

    def test_all_colonies_convert_to_elevenlabs(self):
        """Test all colony settings can be converted to ElevenLabs format."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()

        for _colony, settings in COLONY_VOICE_SETTINGS.items():
            eleven_dict = settings.to_elevenlabs()

            assert isinstance(eleven_dict, dict)
            assert "stability" in eleven_dict
            assert "similarity_boost" in eleven_dict
            assert "style" in eleven_dict
            assert "speed" in eleven_dict
            assert "use_speaker_boost" in eleven_dict

    def test_elevenlabs_dict_values_match_settings(self):
        """Test converted values match original settings."""
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        settings = COLONY_VOICE_SETTINGS[Colony.SPARK]
        eleven_dict = settings.to_elevenlabs()

        assert eleven_dict["stability"] == settings.stability
        assert eleven_dict["similarity_boost"] == settings.similarity_boost
        assert eleven_dict["style"] == settings.style
        assert eleven_dict["speed"] == settings.speed


# =============================================================================
# Colony Character Tests (Documentation)
# =============================================================================


class TestColonyCharacteristics:
    """Test that colony settings match their documented character traits."""

    def test_personality_gradient_stability(self):
        """Test stability varies appropriately across personalities.

        Stability gradient: Expressive ← → Stable
        Lower = more emotional variation (Spark, Grove)
        Higher = more consistent (Beacon, Crystal)
        """
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        # Expressive colonies should have lower stability
        spark = COLONY_VOICE_SETTINGS[Colony.SPARK]
        grove = COLONY_VOICE_SETTINGS[Colony.GROVE]

        # Stable colonies should have higher stability
        beacon = COLONY_VOICE_SETTINGS[Colony.BEACON]
        crystal = COLONY_VOICE_SETTINGS[Colony.CRYSTAL]

        assert spark.stability < beacon.stability
        assert grove.stability < crystal.stability

    def test_personality_gradient_speed(self):
        """Test speed varies appropriately across personalities.

        Speed gradient: Deliberate ← → Energetic
        Slower = thoughtful, measured (Forge, Grove)
        Faster = energetic, efficient (Spark, Beacon)
        """
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        spark = COLONY_VOICE_SETTINGS[Colony.SPARK]
        forge = COLONY_VOICE_SETTINGS[Colony.FORGE]

        assert spark.speed > forge.speed

    def test_personality_gradient_style(self):
        """Test style varies appropriately across personalities.

        Style gradient: Professional ← → Expressive
        Lower = subtle, professional (Beacon)
        Higher = dramatic, expressive (Spark, Grove)
        """
        _, COLONY_VOICE_SETTINGS = get_colony_voice_settings()
        Colony = get_colony_enum()

        spark = COLONY_VOICE_SETTINGS[Colony.SPARK]
        beacon = COLONY_VOICE_SETTINGS[Colony.BEACON]

        assert spark.style > beacon.style
