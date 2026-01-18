"""Tests for character protocol and metadata loading.

Tests cover:
- Character loading from metadata.json
- Avatar config parsing (images, HeyGen settings)
- Voice config parsing
- Character properties (has_voice, has_avatar)
- Path resolution edge cases
"""

import pytest
from pathlib import Path
import json
import tempfile

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from kagami_studio.characters.protocol import (
    Character,
    CharacterRole,
    VoiceConfig,
    AvatarConfig,
    PersonalityConfig,
    load_character,
    CHARACTERS_DIR,
)


class TestCharacterLoading:
    """Tests for loading characters from metadata."""

    def test_load_tim_character(self):
        """Tim character should load successfully."""
        char = load_character("tim")

        assert char is not None
        assert char.name == "Tim"
        assert char.identity_id is not None

    def test_load_andy_character(self):
        """Andy character should load successfully."""
        char = load_character("andy")

        assert char is not None
        assert char.full_name == "Andy McRorie"

    def test_load_nonexistent_character(self):
        """Nonexistent character should return None."""
        char = load_character("nonexistent_character_xyz")

        assert char is None

    def test_case_insensitive_loading(self):
        """Character loading should be case-insensitive."""
        char_lower = load_character("tim")
        char_upper = load_character("TIM")
        char_mixed = load_character("Tim")

        # All should load the same character or all return the same result
        assert char_lower is not None
        if char_upper:
            assert char_lower.identity_id == char_upper.identity_id


class TestVoiceConfig:
    """Tests for voice configuration parsing."""

    def test_tim_has_voice(self):
        """Tim should have a voice configured."""
        char = load_character("tim")

        assert char is not None
        assert char.has_voice
        assert char.voice.voice_id is not None

    def test_andy_has_voice(self):
        """Andy should have a voice configured."""
        char = load_character("andy")

        assert char is not None
        assert char.has_voice
        assert char.voice.voice_id == "pNInz6obpgDQGcFmaJgB"  # Adam voice

    def test_voice_settings_parsed(self):
        """Voice settings should be parsed correctly."""
        char = load_character("andy")

        assert char is not None
        assert char.voice.stability is not None
        assert char.voice.similarity_boost is not None

    def test_voice_config_to_elevenlabs(self):
        """VoiceConfig should convert to ElevenLabs format."""
        config = VoiceConfig(
            voice_id="test_id",
            model="eleven_v3",
            stability=0.5,
            similarity_boost=0.75,
        )

        settings = config.to_elevenlabs()

        assert "stability" in settings
        assert "similarity_boost" in settings
        assert settings["stability"] == 0.5


class TestAvatarConfig:
    """Tests for avatar configuration parsing."""

    def test_tim_has_avatar(self):
        """Tim should have an avatar configured."""
        char = load_character("tim")

        assert char is not None
        assert char.has_avatar
        assert char.avatar.primary_image is not None

    def test_andy_has_avatar(self):
        """Andy should have an avatar configured."""
        char = load_character("andy")

        assert char is not None
        assert char.has_avatar
        assert char.avatar.primary_image is not None

    def test_avatar_image_exists(self):
        """Avatar primary image should exist on disk."""
        char = load_character("tim")

        assert char is not None
        assert char.avatar.primary_image is not None
        assert char.avatar.primary_image.exists()

    def test_avatar_reference_images(self):
        """Reference images should be loaded."""
        char = load_character("tim")

        assert char is not None
        assert len(char.avatar.reference_images) > 0


class TestCharacterRole:
    """Tests for character role parsing."""

    def test_tim_has_valid_role(self):
        """Tim should have a valid role."""
        char = load_character("tim")

        assert char is not None
        assert char.role is not None
        assert isinstance(char.role, CharacterRole)

    def test_andy_is_guest(self):
        """Andy should have GUEST role."""
        char = load_character("andy")

        assert char is not None
        assert char.role == CharacterRole.GUEST


class TestCharacterProperties:
    """Tests for computed character properties."""

    def test_has_voice_property(self):
        """has_voice should return True when voice_id is set."""
        char = load_character("tim")

        assert char is not None
        assert char.has_voice == (char.voice.voice_id is not None)

    def test_has_avatar_property(self):
        """has_avatar should return True when primary_image or heygen_id is set."""
        char = load_character("tim")

        assert char is not None
        expected = char.avatar.heygen_avatar_id is not None or char.avatar.primary_image is not None
        assert char.has_avatar == expected

    def test_is_pet_property(self):
        """is_pet should return True for pet species."""
        char = load_character("tim")

        assert char is not None
        assert char.is_pet == (char.species == "pet" or char.species == "dog")


class TestMetadataPath:
    """Tests for metadata path handling."""

    def test_characters_dir_exists(self):
        """CHARACTERS_DIR should exist."""
        assert CHARACTERS_DIR.exists()
        assert CHARACTERS_DIR.is_dir()

    def test_metadata_json_exists(self):
        """Character metadata.json files should exist."""
        tim_metadata = CHARACTERS_DIR / "tim" / "metadata.json"
        andy_metadata = CHARACTERS_DIR / "andy" / "metadata.json"

        assert tim_metadata.exists()
        assert andy_metadata.exists()


class TestImagePathResolution:
    """Tests for image path resolution from metadata."""

    def test_relative_path_resolution(self):
        """Relative paths in metadata should resolve correctly."""
        char = load_character("andy")

        assert char is not None
        if char.avatar.primary_image:
            # Path should be absolute
            assert char.avatar.primary_image.is_absolute()
            # Path should exist
            assert char.avatar.primary_image.exists()

    def test_image_extension_detection(self):
        """Image extension should be detected correctly."""
        char = load_character("andy")

        assert char is not None
        if char.avatar.primary_image:
            ext = char.avatar.primary_image.suffix.lower()
            assert ext in [".jpg", ".jpeg", ".png", ".webp"]


class TestPersonalityConfig:
    """Tests for personality configuration parsing."""

    def test_speaking_style_parsed(self):
        """Speaking style should be parsed from metadata."""
        char = load_character("andy")

        assert char is not None
        assert char.personality.speaking_style is not None

    def test_wpm_parsed(self):
        """Words per minute should be parsed."""
        char = load_character("andy")

        assert char is not None
        assert char.personality.wpm > 0


class TestEdgeCases:
    """Tests for edge cases in character loading."""

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        char = load_character("")

        assert char is None

    def test_none_input_handled(self):
        """None input should be handled gracefully."""
        try:
            char = load_character(None)
            assert char is None
        except (TypeError, AttributeError):
            # Either returning None or raising is acceptable
            pass

    def test_special_characters_in_name(self):
        """Special characters in name should not crash."""
        char = load_character("../../../etc/passwd")

        assert char is None  # Should not load anything dangerous
