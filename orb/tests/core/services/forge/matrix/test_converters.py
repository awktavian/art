"""Tests for forge matrix converters module."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.matrix.converters import (
    calculate_quality_metrics,
    compile_character,
)
from kagami.forge.schema import Character, PersonalityProfile, QualityMetrics


class TestCompileCharacter:
    """Tests for compile_character function."""

    def test_compile_empty_components(self) -> None:
        """Test compiling empty components dict."""
        character = compile_character({})

        assert isinstance(character, Character)
        assert character.name == "Generated Character"
        assert character.concept == ""

    def test_compile_with_character_data(self) -> None:
        """Test compiling with character_data."""
        components = {
            "character_data": {"name": "Hero", "concept": "A brave hero"},
        }
        character = compile_character(components)

        assert character.name == "Hero"
        assert character.concept == "A brave hero"

    def test_compile_with_behavior(self) -> None:
        """Test compiling with behavior creates personality."""
        components = {
            "character_data": {"name": "Test"},
            "behavior": {"traits": ["brave", "loyal"]},
        }
        character = compile_character(components)

        assert character.personality is not None

    def test_compile_with_metadata(self) -> None:
        """Test compiling includes metadata."""
        components = {
            "character_data": {"name": "Test"},
            "behavior": {"traits": ["curious"]},
            "voice": {"pitch": 1.0},
            "narrative": {"backstory": "Once upon a time"},
        }
        character = compile_character(components)

        assert character.metadata is not None
        assert "behavior" in character.metadata
        assert "voice" in character.metadata
        assert "narrative" in character.metadata
        assert "generation_timestamp" in character.metadata

    def test_compile_with_non_dict_character_data(self) -> None:
        """Test compiling handles non-dict character_data."""
        components = {"character_data": "not a dict"}
        character = compile_character(components)

        assert character.name == "Generated Character"

    def test_compile_with_invalid_behavior(self) -> None:
        """Test compiling handles invalid behavior gracefully."""
        components = {
            "character_data": {"name": "Test"},
            "behavior": "invalid",  # Not a dict
        }
        character = compile_character(components)

        # Should not crash, personality may be None
        assert isinstance(character, Character)


class TestCalculateQualityMetrics:
    """Tests for calculate_quality_metrics function."""

    def test_metrics_with_personality(self) -> None:
        """Test quality metrics with personality present."""
        character = Character(
            name="Test",
            personality=PersonalityProfile(traits=["brave"]),
        )
        metrics = calculate_quality_metrics(character)

        assert isinstance(metrics, QualityMetrics)
        assert metrics.overall_quality >= 0.7  # Higher for personality

    def test_metrics_without_personality(self) -> None:
        """Test quality metrics without personality."""
        character = Character(name="Test")
        metrics = calculate_quality_metrics(character)

        assert isinstance(metrics, QualityMetrics)
        assert metrics.overall_quality >= 0.4

    def test_metrics_structure(self) -> None:
        """Test quality metrics has expected structure."""
        character = Character(name="Test")
        metrics = calculate_quality_metrics(character)

        # Check all expected fields exist
        assert hasattr(metrics, "overall_quality")
        assert hasattr(metrics, "behavior_coherence")
        assert hasattr(metrics, "voice_quality")
        assert hasattr(metrics, "animation_quality")
        assert hasattr(metrics, "rigging_quality")
        assert hasattr(metrics, "mesh_quality")
        assert hasattr(metrics, "texture_quality")

    def test_metrics_values_are_valid(self) -> None:
        """Test quality metrics values are in valid range."""
        character = Character(name="Test")
        metrics = calculate_quality_metrics(character)

        assert 0.0 <= metrics.overall_quality <= 1.0
        assert 0.0 <= metrics.behavior_coherence <= 1.0
