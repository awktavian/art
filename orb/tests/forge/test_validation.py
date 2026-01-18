"""Comprehensive tests for forge validation module.

Tests ForgeValidator class and all validation methods.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.schema import CharacterRequest, QualityLevel
from kagami.forge.validation import ForgeValidator, get_validator


class TestForgeValidator:
    """Test ForgeValidator class."""

    @pytest.fixture
    def validator(self) -> ForgeValidator:
        return ForgeValidator()

    def test_validate_request_valid(self, validator: Any) -> None:
        """Test validation passes for valid request."""
        request = CharacterRequest(concept="A brave warrior hero")
        errors = validator.validate_request(request)
        assert len(errors) == 0

    def test_validate_request_concept_too_short(self, validator: Any) -> None:
        """Test validation fails for short concept."""
        request = CharacterRequest(concept="ab")
        errors = validator.validate_request(request)
        assert len(errors) > 0
        assert any("at least 3 characters" in err for err in errors)

    def test_validate_request_empty_concept(self, validator: Any) -> None:
        """Test validation fails for empty concept."""
        request = CharacterRequest(concept="")
        errors = validator.validate_request(request)
        assert len(errors) > 0

    def test_validate_request_concept_too_long(self, validator: Any) -> None:
        """Test validation fails for overly long concept."""
        request = CharacterRequest(concept="x" * 501)
        errors = validator.validate_request(request)
        assert len(errors) > 0
        assert any("500 characters or less" in err for err in errors)


class TestModerateContent:
    """Test content moderation functionality."""

    @pytest.fixture
    def validator(self) -> ForgeValidator:
        return ForgeValidator()

    @pytest.mark.asyncio
    async def test_moderate_content_clean(self, validator: Any) -> None:
        """Test moderation passes for clean content."""
        result = await validator.moderate_content("A friendly character design")
        assert result["flagged"] is False
        assert result["reason"] is None
        assert result["categories"] == []

    @pytest.mark.asyncio
    async def test_moderate_content_flagged(self, validator: Any) -> None:
        """Test moderation flags prohibited content."""
        result = await validator.moderate_content("explicit content here")
        assert result["flagged"] is True
        assert "explicit" in result["categories"]
        assert result["reason"] is not None

    @pytest.mark.asyncio
    async def test_moderate_content_multiple_violations(self, validator: Any) -> None:
        """Test moderation detects multiple violations."""
        result = await validator.moderate_content("explicit and violent content")
        assert result["flagged"] is True
        assert "explicit" in result["categories"]
        assert "violent" in result["categories"]


class TestValidateMesh:
    """Test mesh validation functionality."""

    @pytest.fixture
    def validator(self) -> ForgeValidator:
        return ForgeValidator()

    def test_validate_mesh_valid(self, validator: Any) -> None:
        """Test validation passes for valid mesh."""

        class MockMesh:
            vertices = list(range(1000))
            faces = list(range(500))
            has_uvs = True
            is_non_manifold = False

        result = validator.validate_mesh(MockMesh())
        assert result["score"] > 0.5
        assert len(result["issues"]) == 0

    def test_validate_mesh_no_vertices(self, validator: Any) -> None:
        """Test validation fails for mesh with no vertices."""

        class MockMesh:
            vertices = []
            faces = []

        result = validator.validate_mesh(MockMesh())
        assert "no vertices" in result["issues"][0].lower()
        assert result["score"] < 1.0

    def test_validate_mesh_no_faces(self, validator: Any) -> None:
        """Test validation flags mesh with no faces."""

        class MockMesh:
            vertices = list(range(100))
            faces = []

        result = validator.validate_mesh(MockMesh())
        assert any("no faces" in issue.lower() for issue in result["issues"])

    def test_validate_mesh_high_vertex_count(self, validator: Any) -> None:
        """Test validation warns for high vertex count."""

        class MockMesh:
            vertices = list(range(150000))
            faces = list(range(50000))

        result = validator.validate_mesh(MockMesh())
        assert any("high vertex count" in w.lower() for w in result["warnings"])

    def test_validate_mesh_no_uvs_warning(self, validator: Any) -> None:
        """Test validation warns for missing UVs."""

        class MockMesh:
            vertices = list(range(100))
            faces = list(range(50))
            has_uvs = False

        result = validator.validate_mesh(MockMesh())
        assert any("uv" in w.lower() for w in result["warnings"])

    def test_validate_mesh_non_manifold(self, validator: Any) -> None:
        """Test validation flags non-manifold geometry."""

        class MockMesh:
            vertices = list(range(100))
            faces = list(range(50))
            is_non_manifold = True

        result = validator.validate_mesh(MockMesh())
        assert any("non-manifold" in issue.lower() for issue in result["issues"])


class TestValidateResult:
    """Test result validation functionality."""

    @pytest.fixture
    def validator(self) -> ForgeValidator:
        return ForgeValidator()

    def test_validate_result_no_data(self, validator: Any) -> None:
        """Test validation fails for result with no data."""

        class MockResult:
            data = None

        result = validator.validate_result(MockResult())
        assert result["overall_score"] == 0.0
        assert any("no data" in issue.lower() for issue in result["issues"])

    def test_validate_result_with_mesh(self, validator: Any) -> None:
        """Test validation processes mesh in result."""

        class MockMesh:
            vertices = list(range(1000))
            faces = list(range(500))

        class MockResult:
            data = {"mesh": MockMesh()}

        result = validator.validate_result(MockResult())
        assert result["overall_score"] > 0


class TestGetValidator:
    """Test validator singleton."""

    def test_get_validator_singleton(self) -> None:
        """Test get_validator returns same instance."""
        v1 = get_validator()
        v2 = get_validator()
        assert v1 is v2

    def test_get_validator_type(self) -> None:
        """Test get_validator returns ForgeValidator."""
        v = get_validator()
        assert isinstance(v, ForgeValidator)
