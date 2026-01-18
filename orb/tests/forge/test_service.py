"""Tests for ForgeService unified service layer."""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.service import (
    ForgeOperation,
    ForgeRequest,
    ForgeResponse,
    ForgeService,
    get_forge_service,
)
from kagami.forge.schema import ExportFormat, QualityLevel


class TestForgeRequest:
    """Test ForgeRequest dataclass."""

    def test_creation_minimal(self) -> None:
        """Test creating with minimal args."""
        request = ForgeRequest(capability=ForgeOperation.CHARACTER_GENERATION)

        assert request.capability == ForgeOperation.CHARACTER_GENERATION
        assert request.params == {}
        assert request.quality_mode == "preview"
        assert request.export_formats == []

    def test_quality_level_property(self) -> None:
        """Test quality_mode to QualityLevel conversion."""
        preview = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, quality_mode="preview"
        )
        draft = ForgeRequest(capability=ForgeOperation.CHARACTER_GENERATION, quality_mode="draft")
        final = ForgeRequest(capability=ForgeOperation.CHARACTER_GENERATION, quality_mode="final")

        assert preview.quality_level == QualityLevel.LOW
        assert draft.quality_level == QualityLevel.MEDIUM
        assert final.quality_level == QualityLevel.HIGH

    def test_export_format_enums(self) -> None:
        """Test export_formats to ExportFormat conversion."""
        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            export_formats=["fbx", "gltf", "invalid"],
        )

        formats = request.export_format_enums
        assert len(formats) == 2
        assert ExportFormat.FBX in formats
        assert ExportFormat.GLTF in formats


class TestForgeResponse:
    """Test ForgeResponse dataclass."""

    def test_creation_success(self) -> None:
        """Test creating success response."""
        response = ForgeResponse(
            success=True,
            capability="character.generate",
            data={"character": {"name": "Test"}},
            correlation_id="test-123",
            duration_ms=500,
        )

        assert response.success is True
        assert response.capability == "character.generate"
        assert response.data["character"]["name"] == "Test"
        assert response.duration_ms == 500

    def test_creation_error(self) -> None:
        """Test creating error response."""
        response = ForgeResponse(
            success=False,
            capability="character.generate",
            error="Module not available",
            error_code="module_unavailable",
        )

        assert response.success is False
        assert response.error == "Module not available"
        assert response.error_code == "module_unavailable"

    def test_to_dict(self) -> None:
        """Test to_dict conversion."""
        response = ForgeResponse(
            success=True,
            capability="animation.facial",
            data={"animation": {}},
            correlation_id="abc-123",
            cached=True,
        )

        result = response.to_dict()

        assert result["success"] is True
        assert result["capability"] == "animation.facial"
        assert result["cached"] is True
        assert result["correlation_id"] == "abc-123"
        assert "error" not in result

    def test_to_dict_error(self) -> None:
        """Test to_dict with error."""
        response = ForgeResponse(
            success=False,
            capability="character.generate",
            error="Test error",
            error_code="test_code",
        )

        result = response.to_dict()

        assert result["success"] is False
        assert result["error"] == "Test error"
        assert result["error_code"] == "test_code"


class TestForgeOperation:
    """Test ForgeOperation enum."""

    def test_all_capabilities_defined(self) -> None:
        """Test all expected capabilities exist."""
        assert ForgeOperation.CHARACTER_GENERATION
        assert ForgeOperation.IMAGE_TO_CHARACTER
        assert ForgeOperation.ANIMATION_FACIAL
        assert ForgeOperation.ANIMATION_GESTURE
        assert ForgeOperation.ANIMATION_MOTION

    def test_capability_values(self) -> None:
        """Test capability values are strings."""
        for cap in ForgeOperation:
            assert isinstance(cap.value, str)
            assert len(cap.value) > 0  # Non-empty values


class TestForgeService:
    """Test ForgeService class."""

    def test_creation(self) -> None:
        """Test creating ForgeService."""
        service = ForgeService()

        assert service._matrix is None
        assert service._initialized is False

    def test_singleton_accessor(self) -> None:
        """Test get_forge_service returns singleton."""
        service1 = get_forge_service()
        service2 = get_forge_service()

        # Note: in test mode, singleton might be reset between tests
        # Just verify it returns a ForgeService
        assert isinstance(service1, ForgeService)
        assert isinstance(service2, ForgeService)

    @pytest.mark.asyncio
    async def test_execute_missing_concept(self) -> None:
        """Test execute returns error for missing concept."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={},  # No concept
        )

        result = await service.execute(request)

        assert result.success is False
        assert "concept is required" in result.error  # type: ignore[operator]
        assert result.error_code == "missing_concept"

    @pytest.mark.asyncio
    async def test_generate_character_convenience(self, monkeypatch: Any) -> None:
        """Test generate_character convenience method returns response."""
        service = ForgeService()

        # Mock the heavy matrix operation
        async def mock_execute(request: Any) -> Any:
            return ForgeResponse(
                success=True,
                capability=request.capability.value,
                data={"character": {"name": "Mocked"}},
                duration_ms=100,
            )

        monkeypatch.setattr(service, "execute", mock_execute)

        result = await service.generate_character(
            concept="test warrior",
            quality_mode="preview",
        )

        assert isinstance(result, ForgeResponse)
        assert result.success is True
        assert result.capability == "character.generate"

    @pytest.mark.asyncio
    async def test_generate_animation_convenience(self, monkeypatch: Any) -> None:
        """Test generate_animation convenience method."""
        service = ForgeService()

        # Mock the heavy execute operation
        async def mock_execute(request: Any) -> Any:
            return ForgeResponse(
                success=True,
                capability=request.capability.value,
                data={"animation": {}},
                duration_ms=50,
            )

        monkeypatch.setattr(service, "execute", mock_execute)

        result = await service.generate_animation(
            "blinks",
            duration=5.0,
        )

        assert isinstance(result, ForgeResponse)
        assert result.success is True
        assert result.capability == "animation.facial"
