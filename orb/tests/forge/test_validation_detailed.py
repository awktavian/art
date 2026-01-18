"""Tests for Forge validation system."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from kagami.forge.schema import CharacterRequest, QualityLevel, CharacterStyle

pytestmark = pytest.mark.tier_unit


class TestCharacterRequestValidation:
    """Test CharacterRequest validation."""

    def test_valid_character_request(self):
        """Test creating valid CharacterRequest."""
        request = CharacterRequest(
            request_id="test-123",
            concept="warrior character",
            quality_level=QualityLevel.MEDIUM,
        )

        assert request.request_id == "test-123"
        assert request.concept == "warrior character"
        assert request.quality_level == QualityLevel.MEDIUM

    def test_minimal_character_request(self):
        """Test minimal valid CharacterRequest."""
        request = CharacterRequest(
            request_id="test-123",
            concept="warrior",
        )

        assert request.concept == "warrior"

    def test_concept_whitespace_handling(self):
        """Test concept with leading/trailing whitespace."""
        request = CharacterRequest(
            request_id="test-123",
            concept="  warrior  ",
        )

        # Validation should handle whitespace
        assert "warrior" in request.concept

    def test_quality_level_defaults(self):
        """Test quality level defaults."""
        request = CharacterRequest(
            request_id="test",
            concept="test",
        )

        # Should have a default quality level
        assert hasattr(request, "quality_level")


class TestInputSanitization:
    """Test input sanitization."""

    def test_concept_length_limits(self):
        """Test concept length validation."""
        # Very long concept
        long_concept = "a" * 10000
        request = CharacterRequest(
            request_id="test",
            concept=long_concept,
        )

        # Should handle long input gracefully
        assert len(request.concept) > 0

    def test_special_characters_in_concept(self):
        """Test special characters in concept."""
        request = CharacterRequest(
            request_id="test",
            concept="warrior <script>alert('xss')</script>",
        )

        # Concept should be stored (sanitization handled downstream)
        assert request.concept is not None

    def test_unicode_in_concept(self):
        """Test Unicode characters in concept."""
        request = CharacterRequest(
            request_id="test",
            concept="戦士 warrior kämpfer",
        )

        assert "warrior" in request.concept


class TestExportFormatValidation:
    """Test export format validation."""

    def test_valid_export_formats(self):
        """Test valid export formats."""
        from kagami.forge.schema import ExportFormat

        request = CharacterRequest(
            request_id="test",
            concept="test",
            export_formats=[
                ExportFormat.FBX,
                ExportFormat.GLTF,
                ExportFormat.USD,
            ],
        )

        assert len(request.export_formats) == 3

    def test_empty_export_formats(self):
        """Test empty export formats list."""
        request = CharacterRequest(
            request_id="test",
            concept="test",
            export_formats=[],
        )

        assert request.export_formats == []


class TestStyleValidation:
    """Test style preferences validation."""

    def test_valid_style_preferences(self):
        """Test valid style preferences."""
        from kagami.forge.schema import StylePreferences

        request = CharacterRequest(
            request_id="test",
            concept="test",
            style=StylePreferences(
                primary_style=CharacterStyle.REALISTIC,
            ),
        )

        assert request.style.primary_style == CharacterStyle.REALISTIC

    def test_default_style(self):
        """Test default style handling."""
        request = CharacterRequest(
            request_id="test",
            concept="test",
        )

        # Should have style attribute
        assert hasattr(request, "style")


class TestMetadataValidation:
    """Test metadata validation."""

    def test_metadata_dict(self):
        """Test metadata as dictionary."""
        request = CharacterRequest(
            request_id="test",
            concept="test",
            metadata={"author": "test", "version": "1.0"},
        )

        assert request.metadata["author"] == "test"

    def test_metadata_empty(self):
        """Test empty metadata."""
        request = CharacterRequest(
            request_id="test",
            concept="test",
            metadata={},
        )

        assert request.metadata == {}

    def test_metadata_nested(self):
        """Test nested metadata structures."""
        request = CharacterRequest(
            request_id="test",
            concept="test",
            metadata={
                "visual_features": {
                    "hair_color": "brown",
                    "eye_color": "blue",
                },
                "personality": {
                    "traits": ["brave", "loyal"],
                },
            },
        )

        assert "visual_features" in request.metadata
        assert request.metadata["personality"]["traits"] == ["brave", "loyal"]


class TestRequestIdValidation:
    """Test request_id validation."""

    def test_valid_request_ids(self):
        """Test various valid request ID formats."""
        ids = [
            "test-123",
            "abc_123",
            "uuid-4f3a-9c2b",
            "REQ001",
        ]

        for req_id in ids:
            request = CharacterRequest(
                request_id=req_id,
                concept="test",
            )
            assert request.request_id == req_id

    def test_empty_request_id(self):
        """Test empty request_id."""
        request = CharacterRequest(
            request_id="",
            concept="test",
        )

        assert request.request_id == ""


class TestQualityLevelValidation:
    """Test quality level validation."""

    def test_all_quality_levels(self):
        """Test all quality level enum values."""
        levels = [QualityLevel.LOW, QualityLevel.MEDIUM, QualityLevel.HIGH]

        for level in levels:
            request = CharacterRequest(
                request_id="test",
                concept="test",
                quality_level=level,
            )
            assert request.quality_level == level


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_concept(self):
        """Test empty string concept."""
        request = CharacterRequest(
            request_id="test",
            concept="",
        )

        assert request.concept == ""

    def test_whitespace_only_concept(self):
        """Test whitespace-only concept."""
        request = CharacterRequest(
            request_id="test",
            concept="   ",
        )

        assert len(request.concept.strip()) == 0

    def test_none_values_in_optional_fields(self):
        """Test None values in optional fields."""
        request = CharacterRequest(
            request_id="test",
            concept="test",
            personality_brief=None,
            backstory_brief=None,
        )

        assert request.personality_brief is None
        assert request.backstory_brief is None
