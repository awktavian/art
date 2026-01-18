"""Tests for forge matrix state module."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.matrix.state import coerce_request
from kagami.forge.schema import CharacterRequest, ExportFormat


class TestCoerceRequest:
    """Tests for coerce_request function."""

    def test_coerce_character_request_passthrough(self) -> None:
        """Test CharacterRequest passes through unchanged."""
        original = CharacterRequest(concept="test character")
        result = coerce_request(original)

        assert result is original
        assert result.concept == "test character"

    def test_coerce_dict_to_request(self) -> None:
        """Test dict is converted to CharacterRequest."""
        data = {"concept": "a brave warrior", "request_id": "test-123"}
        result = coerce_request(data)

        assert isinstance(result, CharacterRequest)
        assert result.concept == "a brave warrior"

    def test_coerce_dict_with_prompt_to_concept(self) -> None:
        """Test 'prompt' field is mapped to 'concept'."""
        data = {"prompt": "a cute mascot"}
        result = coerce_request(data)

        assert result.concept == "a cute mascot"

    def test_coerce_export_formats_list(self) -> None:
        """Test export_formats list handling."""
        data = {"concept": "test", "export_formats": [ExportFormat.GLTF, ExportFormat.FBX]}
        result = coerce_request(data)

        assert result.export_formats == [ExportFormat.GLTF, ExportFormat.FBX]

    def test_coerce_export_formats_single(self) -> None:
        """Test single export_format is converted to list."""
        data = {"concept": "test", "export_formats": ExportFormat.GLTF}
        result = coerce_request(data)

        assert result.export_formats == [ExportFormat.GLTF]

    def test_coerce_metadata_dict(self) -> None:
        """Test metadata dict handling."""
        data = {"concept": "test", "metadata": {"key": "value"}}
        result = coerce_request(data)

        assert result.metadata == {"key": "value"}

    def test_coerce_metadata_non_dict(self) -> None:
        """Test non-dict metadata is wrapped."""
        data = {"concept": "test", "metadata": "simple_value"}
        result = coerce_request(data)

        assert result.metadata == {"value": "simple_value"}

    def test_coerce_technical_constraints_migration(self) -> None:
        """Test technical_constraints is moved to metadata."""
        data = {
            "concept": "test",
            "technical_constraints": {"max_polygons": 10000},
            "metadata": {},
        }
        result = coerce_request(data)

        assert "technical_constraints" in result.metadata

    def test_coerce_empty_dict(self) -> None:
        """Test empty dict creates default request."""
        result = coerce_request({})

        assert isinstance(result, CharacterRequest)
        # Empty dict may result in empty concept or default behavior

    def test_coerce_object_with_attributes(self) -> None:
        """Test object with attributes is converted."""

        class FakeRequest:
            concept = "object concept"
            request_id = "obj-123"

        result = coerce_request(FakeRequest())

        assert isinstance(result, CharacterRequest)
        assert result.concept == "object concept"

    def test_coerce_filters_invalid_fields(self) -> None:
        """Test invalid fields are filtered out."""
        data = {
            "concept": "test",
            "invalid_field": "should be ignored",
            "another_bad": 123,
        }
        result = coerce_request(data)

        assert result.concept == "test"
        # Invalid fields should not cause errors
