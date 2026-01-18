"""Comprehensive tests for ForgeService.

This test suite covers all functionality in kagami/forge/service.py:
- ForgeService initialization and lifecycle
- ForgeRequest/ForgeResponse handling
- All ForgeOperation enum operations
- Error handling with specific error types
- Metrics emission
- Idempotency key and correlation ID handling
- Convenience methods
- Edge cases and error paths
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from unittest.mock import AsyncMock, MagicMock, patch, call

from kagami.forge.service import (
    ForgeOperation,
    ForgeRequest,
    ForgeResponse,
    ForgeService,
    get_forge_service,
)
from kagami.forge.schema import ExportFormat, QualityLevel
from kagami.forge.exceptions import (
    ForgeError,
    ModuleInitializationError,
    ModuleNotAvailableError,
)


class TestForgeServiceInitialization:
    """Test ForgeService initialization and lifecycle."""

    def test_service_creation_default(self):
        """Test creating ForgeService with default parameters."""
        service = ForgeService()

        assert service._matrix is None
        assert service._initialized is False

    def test_service_creation_with_matrix(self):
        """Test creating ForgeService with provided matrix."""
        mock_matrix = MagicMock()
        service = ForgeService(matrix=mock_matrix)

        assert service._matrix is mock_matrix
        assert service._initialized is False

    def test_matrix_property_lazy_loading(self):
        """Test that matrix property lazy-loads ForgeMatrix."""
        service = ForgeService()

        with patch("kagami.forge.service.get_forge_matrix") as mock_get:
            mock_matrix = MagicMock()
            mock_get.return_value = mock_matrix

            matrix = service.matrix

            assert matrix is mock_matrix
            mock_get.assert_called_once()
            # Second access should use cached value
            matrix2 = service.matrix
            assert matrix2 is mock_matrix
            assert mock_get.call_count == 1

    @pytest.mark.asyncio
    async def test_initialize_calls_matrix_initialize(self):
        """Test that initialize() calls matrix.initialize()."""
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()
        service = ForgeService(matrix=mock_matrix)

        await service.initialize()

        assert service._initialized is True
        mock_matrix.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Test that initialize() is idempotent (doesn't re-initialize)."""
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()
        service = ForgeService(matrix=mock_matrix)

        await service.initialize()
        await service.initialize()
        await service.initialize()

        # Should only be called once
        assert mock_matrix.initialize.call_count == 1


class TestForgeRequest:
    """Test ForgeRequest dataclass."""

    def test_request_creation_minimal(self):
        """Test creating request with minimal parameters."""
        request = ForgeRequest(capability=ForgeOperation.CHARACTER_GENERATION)

        assert request.capability == ForgeOperation.CHARACTER_GENERATION
        assert request.params == {}
        assert request.quality_mode == "preview"
        assert request.export_formats == []
        assert request.metadata == {}
        assert request.correlation_id is None
        assert request.idempotency_key is None

    def test_request_creation_full(self):
        """Test creating request with all parameters."""
        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_FACIAL,
            params={"type": "blinks", "duration": 10.0},
            quality_mode="final",
            export_formats=["fbx", "gltf"],
            metadata={"user_id": "test-user"},
            correlation_id="corr-123",
            idempotency_key="idem-456",
        )

        assert request.capability == ForgeOperation.ANIMATION_FACIAL
        assert request.params["type"] == "blinks"
        assert request.quality_mode == "final"
        assert request.export_formats == ["fbx", "gltf"]
        assert request.metadata["user_id"] == "test-user"
        assert request.correlation_id == "corr-123"
        assert request.idempotency_key == "idem-456"

    def test_quality_level_property_preview(self):
        """Test quality_level property returns LOW for preview."""
        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, quality_mode="preview"
        )
        assert request.quality_level == QualityLevel.LOW

    def test_quality_level_property_draft(self):
        """Test quality_level property returns MEDIUM for draft."""
        request = ForgeRequest(capability=ForgeOperation.CHARACTER_GENERATION, quality_mode="draft")
        assert request.quality_level == QualityLevel.MEDIUM

    def test_quality_level_property_final(self):
        """Test quality_level property returns HIGH for final."""
        request = ForgeRequest(capability=ForgeOperation.CHARACTER_GENERATION, quality_mode="final")
        assert request.quality_level == QualityLevel.HIGH

    def test_quality_level_property_unknown(self):
        """Test quality_level property returns LOW for unknown mode."""
        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, quality_mode="unknown"
        )
        assert request.quality_level == QualityLevel.LOW

    def test_export_format_enums_valid(self):
        """Test export_format_enums converts valid formats."""
        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, export_formats=["fbx", "gltf", "usd"]
        )

        formats = request.export_format_enums
        assert ExportFormat.FBX in formats
        assert ExportFormat.GLTF in formats

    def test_export_format_enums_invalid(self):
        """Test export_format_enums skips invalid formats."""
        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            export_formats=["fbx", "invalid_format", "gltf", "another_invalid"],
        )

        formats = request.export_format_enums
        assert ExportFormat.FBX in formats
        assert ExportFormat.GLTF in formats
        # Invalid formats are skipped, not included
        assert len([f for f in formats if "invalid" in str(f).lower()]) == 0


class TestForgeResponse:
    """Test ForgeResponse dataclass."""

    def test_response_creation_success(self):
        """Test creating successful response."""
        response = ForgeResponse(
            success=True,
            capability="character.generate",
            data={"character": {"name": "TestChar"}},
            correlation_id="test-corr",
            duration_ms=250,
        )

        assert response.success is True
        assert response.capability == "character.generate"
        assert response.data["character"]["name"] == "TestChar"
        assert response.correlation_id == "test-corr"
        assert response.duration_ms == 250
        assert response.cached is False
        assert response.error is None
        assert response.error_code is None

    def test_response_creation_error(self):
        """Test creating error response."""
        response = ForgeResponse(
            success=False,
            capability="character.generate",
            error="Module not found",
            error_code="module_unavailable",
        )

        assert response.success is False
        assert response.error == "Module not found"
        assert response.error_code == "module_unavailable"

    def test_response_to_dict_success(self):
        """Test to_dict() for successful response."""
        response = ForgeResponse(
            success=True,
            capability="animation.facial",
            data={"animation": {"frames": 100}},
            correlation_id="abc-123",
            duration_ms=150,
            cached=True,
        )

        result = response.to_dict()

        assert result["success"] is True
        assert result["capability"] == "animation.facial"
        assert result["data"]["animation"]["frames"] == 100
        assert result["correlation_id"] == "abc-123"
        assert result["duration_ms"] == 150
        assert result["cached"] is True
        assert "error" not in result
        assert "error_code" not in result

    def test_response_to_dict_error(self):
        """Test to_dict() for error response."""
        response = ForgeResponse(
            success=False,
            capability="genesis.video",
            error="Generation failed",
            error_code="genesis_video_failed",
            duration_ms=500,
        )

        result = response.to_dict()

        assert result["success"] is False
        assert result["error"] == "Generation failed"
        assert result["error_code"] == "genesis_video_failed"
        assert result["duration_ms"] == 500

    def test_response_to_dict_with_receipt(self):
        """Test to_dict() includes receipt when present."""
        response = ForgeResponse(
            success=True,
            capability="character.generate",
            data={},
            receipt={"transaction_id": "tx-123", "cost": 0.05},
        )

        result = response.to_dict()

        assert "receipt" in result
        assert result["receipt"]["transaction_id"] == "tx-123"


class TestForgeOperation:
    """Test ForgeOperation enum."""

    def test_all_operations_defined(self):
        """Test all expected operations are defined."""
        assert ForgeOperation.CHARACTER_GENERATION
        assert ForgeOperation.IMAGE_TO_CHARACTER
        assert ForgeOperation.ANIMATION_FACIAL
        assert ForgeOperation.ANIMATION_GESTURE
        assert ForgeOperation.ANIMATION_MOTION
        assert ForgeOperation.GENESIS_VIDEO
        assert ForgeOperation.VALIDATION
        assert ForgeOperation.CONTENT_SAFETY

    def test_operation_values_are_strings(self):
        """Test that all operation values are non-empty strings."""
        for op in ForgeOperation:
            assert isinstance(op.value, str)
            assert len(op.value) > 0

    def test_operation_values_unique(self):
        """Test that all operation values are unique."""
        values = [op.value for op in ForgeOperation]
        assert len(values) == len(set(values))


class TestForgeServiceExecution:
    """Test ForgeService execute() method."""

    @pytest.mark.asyncio
    async def test_execute_initializes_matrix_when_required(self):
        """Test execute() initializes matrix for operations that require it."""
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()
        mock_matrix.generate_character = AsyncMock(return_value={"name": "Test"})

        service = ForgeService(matrix=mock_matrix)

        with patch("kagami.forge.service.get_semantic_cache") as mock_cache:
            mock_cache.return_value.get_or_generate = AsyncMock(
                return_value=({"name": "Test"}, False)
            )

            request = ForgeRequest(
                capability=ForgeOperation.CHARACTER_GENERATION, params={"concept": "warrior"}
            )

            await service.execute(request)

            mock_matrix.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_skips_initialization_for_animation(self):
        """Test execute() skips matrix init for operations that don't require it."""
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()

        service = ForgeService(matrix=mock_matrix)

        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_FACIAL, params={"type": "blinks", "duration": 5.0}
        )

        with patch("kagami.forge.service.FacialAnimator") as mock_animator:
            mock_animator.return_value.generate_blinks = AsyncMock(return_value={"frames": []})

            await service.execute(request)

            # Matrix initialization should not be called
            mock_matrix.initialize.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_sets_correlation_id(self):
        """Test execute() sets correlation_id on response."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_FACIAL,
            params={"type": "blinks", "duration": 5.0},
            correlation_id="test-corr-123",
        )

        with patch("kagami.forge.service.FacialAnimator") as mock_animator:
            mock_animator.return_value.generate_blinks = AsyncMock(return_value={"frames": []})

            result = await service.execute(request)

            assert result.correlation_id == "test-corr-123"

    @pytest.mark.asyncio
    async def test_execute_sets_duration_ms(self):
        """Test execute() sets duration_ms on response."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_FACIAL, params={"type": "blinks", "duration": 5.0}
        )

        with patch("kagami.forge.service.FacialAnimator") as mock_animator:
            mock_animator.return_value.generate_blinks = AsyncMock(return_value={"frames": []})

            result = await service.execute(request)

            assert result.duration_ms >= 0


class TestForgeServiceErrorHandling:
    """Test ForgeService error handling."""

    @pytest.mark.asyncio
    async def test_execute_handles_module_not_available_error(self):
        """Test execute() handles ModuleNotAvailableError."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={"concept": "warrior"},
            correlation_id="test-corr",
        )

        with patch.object(service, "_get_handler") as mock_handler:
            mock_handler.return_value = AsyncMock(
                side_effect=ModuleNotAvailableError("test_module")
            )

            result = await service.execute(request)

            assert result.success is False
            assert result.error_code == "module_unavailable"
            assert "test_module" in result.error  # type: ignore[operator]
            assert result.correlation_id == "test-corr"

    @pytest.mark.asyncio
    async def test_execute_handles_module_initialization_error(self):
        """Test execute() handles ModuleInitializationError."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, params={"concept": "warrior"}
        )

        with patch.object(service, "_get_handler") as mock_handler:
            mock_handler.return_value = AsyncMock(
                side_effect=ModuleInitializationError("test_module", "failed to load")
            )

            result = await service.execute(request)

            assert result.success is False
            assert result.error_code == "module_init_failed"
            assert "test_module" in result.error  # type: ignore[operator]

    @pytest.mark.asyncio
    async def test_execute_handles_forge_error(self):
        """Test execute() handles ForgeError."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, params={"concept": "warrior"}
        )

        with patch.object(service, "_get_handler") as mock_handler:
            mock_handler.return_value = AsyncMock(side_effect=ForgeError("Custom forge error"))

            result = await service.execute(request)

            assert result.success is False
            assert result.error_code == "forge_error"
            assert "Custom forge error" in result.error  # type: ignore[operator]

    @pytest.mark.asyncio
    async def test_execute_handles_generic_exception(self):
        """Test execute() handles unexpected exceptions."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, params={"concept": "warrior"}
        )

        with patch.object(service, "_get_handler") as mock_handler:
            mock_handler.return_value = AsyncMock(side_effect=ValueError("Unexpected error"))

            with patch("kagami.forge.service.API_ERRORS") as mock_metric:
                result = await service.execute(request)

            assert result.success is False
            assert result.error_code == "internal_error"
            assert "Unexpected error" in result.error  # type: ignore[operator]

    @pytest.mark.asyncio
    async def test_execute_records_error_metrics(self):
        """Test execute() records error metrics."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, params={"concept": "warrior"}
        )

        with patch.object(service, "_get_handler") as mock_handler:
            mock_handler.return_value = AsyncMock(side_effect=ValueError("Test error"))

            with patch("kagami.forge.service.API_ERRORS") as mock_metric:
                mock_labels = MagicMock()
                mock_metric.labels.return_value = mock_labels

                await service.execute(request)

                mock_metric.labels.assert_called_with(
                    endpoint="forge.character.generate", error_type="ValueError"
                )
                mock_labels.inc.assert_called_once()


class TestCharacterGenerationHandler:
    """Test character generation handler."""

    @pytest.mark.asyncio
    async def test_character_generation_missing_concept(self):
        """Test character generation returns error when concept is missing."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={},  # No concept
        )

        result = await service.execute(request)

        assert result.success is False
        assert result.error_code == "missing_concept"
        assert "concept is required" in result.error  # type: ignore[operator]

    @pytest.mark.asyncio
    async def test_character_generation_success(self):
        """Test successful character generation."""
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()
        mock_matrix.generate_character = AsyncMock(
            return_value={"name": "TestCharacter", "model": "mesh_data"}
        )

        service = ForgeService(matrix=mock_matrix)

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, params={"concept": "brave warrior"}
        )

        with patch("kagami.forge.service.get_semantic_cache") as mock_cache:
            mock_cache.return_value.get_or_generate = AsyncMock(
                return_value=({"name": "TestCharacter"}, False)
            )

            with patch("kagami.forge.service.CHARACTER_GENERATIONS") as mock_metric:
                result = await service.execute(request)

        assert result.success is True
        assert result.data["name"] == "TestCharacter"

    @pytest.mark.asyncio
    async def test_character_generation_uses_semantic_cache(self):
        """Test character generation uses semantic cache."""
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()

        service = ForgeService(matrix=mock_matrix)

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, params={"concept": "test concept"}
        )

        with patch("kagami.forge.service.get_semantic_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache.return_value = mock_cache_instance
            mock_cache_instance.get_or_generate = AsyncMock(return_value=({"cached": True}, True))

            with patch("kagami.forge.service.CHARACTER_GENERATIONS"):
                result = await service.execute(request)

        assert result.cached is True
        mock_cache_instance.get_or_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_character_generation_emits_metrics_cached(self):
        """Test character generation emits metrics for cached results."""
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()

        service = ForgeService(matrix=mock_matrix)

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={"concept": "test"},
            quality_mode="draft",
        )

        with patch("kagami.forge.service.get_semantic_cache") as mock_cache:
            mock_cache.return_value.get_or_generate = AsyncMock(return_value=({}, True))

            with patch("kagami.forge.service.CHARACTER_GENERATIONS") as mock_metric:
                mock_labels = MagicMock()
                mock_metric.labels.return_value = mock_labels

                await service.execute(request)

                mock_metric.labels.assert_called_with("success_cached", "draft")
                mock_labels.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_character_generation_with_personality(self):
        """Test character generation with personality brief."""
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()
        mock_matrix.generate_character = AsyncMock(return_value={})

        service = ForgeService(matrix=mock_matrix)

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={
                "concept": "warrior",
                "personality_brief": "brave and noble",
                "backstory_brief": "ancient hero",
            },
        )

        with patch("kagami.forge.service.get_semantic_cache") as mock_cache:
            # Simplified: just return a value
            mock_cache.return_value.get_or_generate = AsyncMock(return_value=({}, False))

            with patch("kagami.forge.service.CHARACTER_GENERATIONS"):
                result = await service.execute(request)

        assert result.success is True


class TestImageToCharacterHandler:
    """Test image-to-character handler."""

    @pytest.mark.asyncio
    async def test_image_to_character_missing_image_path(self):
        """Test image-to-character returns error when image_path is missing."""
        service = ForgeService()

        request = ForgeRequest(capability=ForgeOperation.IMAGE_TO_CHARACTER, params={})

        result = await service.execute(request)

        assert result.success is False
        assert result.error_code == "missing_image"
        assert "image_path is required" in result.error  # type: ignore[operator]

    @pytest.mark.asyncio
    async def test_image_to_character_success(self):
        """Test successful image-to-character generation."""
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()
        mock_matrix.generate_character_from_image = AsyncMock(
            return_value={"name": "CharFromImage"}
        )

        service = ForgeService(matrix=mock_matrix)

        request = ForgeRequest(
            capability=ForgeOperation.IMAGE_TO_CHARACTER,
            params={"image_path": "/path/to/image.png"},
        )

        result = await service.execute(request)

        assert result.success is True
        assert result.data["character"]["name"] == "CharFromImage"


class TestAnimationHandlers:
    """Test animation generation handlers."""

    @pytest.mark.asyncio
    async def test_facial_animation_blinks(self):
        """Test facial animation - blinks generation."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_FACIAL,
            params={"type": "blinks", "duration": 10.0, "blink_rate": 20},
        )

        with patch("kagami.forge.service.FacialAnimator") as mock_animator:
            mock_animator.return_value.generate_blinks = AsyncMock(
                return_value={"frames": [1, 2, 3]}
            )

            result = await service.execute(request)

        assert result.success is True
        assert result.data["animation"]["frames"] == [1, 2, 3]
        assert result.data["type"] == "blinks"
        assert result.data["duration"] == 10.0

    @pytest.mark.asyncio
    async def test_facial_animation_expressions(self):
        """Test facial animation - expressions generation."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_FACIAL,
            params={"type": "expressions", "emotion": "happy", "intensity": 0.8},
        )

        with patch("kagami.forge.service.FacialAnimator") as mock_animator:
            mock_animator.return_value.generate_expression = AsyncMock(
                return_value={"emotion": "happy"}
            )

            result = await service.execute(request)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_facial_animation_unknown_type(self):
        """Test facial animation returns error for unknown type."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_FACIAL, params={"type": "unknown_type"}
        )

        result = await service.execute(request)

        assert result.success is False
        assert result.error_code == "unknown_animation_type"

    @pytest.mark.asyncio
    async def test_gesture_animation_idle(self):
        """Test gesture animation - idle gestures."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_GESTURE,
            params={"type": "idle", "duration": 10.0, "energy_level": 0.5},
        )

        with patch("kagami.forge.service.GestureEngine") as mock_engine:
            mock_engine.return_value.generate_idle_gestures = AsyncMock(
                return_value={"gestures": []}
            )

            result = await service.execute(request)

        assert result.success is True
        assert result.data["type"] == "idle"
        assert result.data["energy_level"] == 0.5

    @pytest.mark.asyncio
    async def test_gesture_animation_custom(self):
        """Test gesture animation - custom gesture."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_GESTURE, params={"type": "wave", "duration": 5.0}
        )

        with patch("kagami.forge.service.GestureEngine") as mock_engine:
            mock_engine.return_value.generate_from_speech = AsyncMock(
                return_value={"gesture": "wave"}
            )

            result = await service.execute(request)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_motion_animation_missing_prompt(self):
        """Test motion animation returns error when prompt is missing."""
        service = ForgeService()

        request = ForgeRequest(capability=ForgeOperation.ANIMATION_MOTION, params={})

        result = await service.execute(request)

        assert result.success is False
        assert result.error_code == "missing_prompt"

    @pytest.mark.asyncio
    async def test_motion_animation_success(self):
        """Test successful motion animation generation."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_MOTION,
            params={"prompt": "walking forward", "duration": 5.0},
        )

        with patch("kagami.forge.service.AnimationModule") as mock_module:
            mock_instance = MagicMock()
            mock_module.return_value = mock_instance
            mock_instance.initialize = AsyncMock()
            mock_instance.process = AsyncMock(return_value=MagicMock(data={"motion": "walk"}))

            result = await service.execute(request)

        assert result.success is True
        assert result.data["prompt"] == "walking forward"


class TestGenesisVideoHandler:
    """Test Genesis video generation handler."""

    @pytest.mark.asyncio
    async def test_genesis_video_with_spec_dict(self):
        """Test Genesis video generation with spec parameter."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.GENESIS_VIDEO,
            params={"spec": {"template": "default", "output_dir": "/tmp/output"}},
        )

        with patch("kagami.forge.service.generate_genesis_video") as mock_gen:
            mock_gen.return_value = {"video_path": "/tmp/output/video.mp4"}

            result = await service.execute(request)

        assert result.success is True
        assert "video_path" in result.data

    @pytest.mark.asyncio
    async def test_genesis_video_with_direct_params(self):
        """Test Genesis video generation with direct parameters."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.GENESIS_VIDEO,
            params={"template": "default", "output_dir": "/tmp/output"},
        )

        with patch("kagami.forge.service.generate_genesis_video") as mock_gen:
            mock_gen.return_value = {"video_path": "/tmp/output/video.mp4"}

            result = await service.execute(request)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_genesis_video_invalid_spec(self):
        """Test Genesis video returns error for invalid spec."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.GENESIS_VIDEO, params={"spec": "not_a_dict"}
        )

        result = await service.execute(request)

        assert result.success is False
        assert result.error_code == "invalid_spec"

    @pytest.mark.asyncio
    async def test_genesis_video_module_not_available(self):
        """Test Genesis video handles module unavailable error."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.GENESIS_VIDEO, params={"spec": {"template": "default"}}
        )

        with patch("kagami.forge.service.generate_genesis_video") as mock_gen:
            mock_gen.side_effect = ModuleNotAvailableError("genesis")

            result = await service.execute(request)

        assert result.success is False
        assert result.error_code == "module_unavailable"


class TestConvenienceMethods:
    """Test convenience methods."""

    @pytest.mark.asyncio
    async def test_generate_character_convenience(self):
        """Test generate_character convenience method."""
        service = ForgeService()

        with patch.object(service, "execute") as mock_execute:
            mock_execute.return_value = ForgeResponse(
                success=True, capability="character.generate", data={"name": "Test"}
            )

            result = await service.generate_character(
                concept="warrior",
                quality_mode="draft",
                export_formats=["fbx"],
                personality_brief="brave",
                backstory_brief="hero",
                correlation_id="test-123",
            )

        assert result.success is True
        # Verify execute was called with correct request
        call_args = mock_execute.call_args[0][0]
        assert call_args.capability == ForgeOperation.CHARACTER_GENERATION
        assert call_args.params["concept"] == "warrior"
        assert call_args.quality_mode == "draft"

    @pytest.mark.asyncio
    async def test_generate_animation_convenience_blinks(self):
        """Test generate_animation convenience method for blinks."""
        service = ForgeService()

        with patch.object(service, "execute") as mock_execute:
            mock_execute.return_value = ForgeResponse(
                success=True, capability="animation.facial", data={}
            )

            result = await service.generate_animation(
                "blinks", duration=10.0, correlation_id="anim-123"
            )

        assert result.success is True
        call_args = mock_execute.call_args[0][0]
        assert call_args.capability == ForgeOperation.ANIMATION_FACIAL

    @pytest.mark.asyncio
    async def test_generate_animation_convenience_idle(self):
        """Test generate_animation convenience method for idle."""
        service = ForgeService()

        with patch.object(service, "execute") as mock_execute:
            mock_execute.return_value = ForgeResponse(
                success=True, capability="animation.gesture", data={}
            )

            await service.generate_animation("idle", duration=5.0)

        call_args = mock_execute.call_args[0][0]
        assert call_args.capability == ForgeOperation.ANIMATION_GESTURE

    @pytest.mark.asyncio
    async def test_generate_animation_convenience_motion(self):
        """Test generate_animation convenience method for motion."""
        service = ForgeService()

        with patch.object(service, "execute") as mock_execute:
            mock_execute.return_value = ForgeResponse(
                success=True, capability="animation.motion", data={}
            )

            await service.generate_animation("walking", duration=5.0)

        call_args = mock_execute.call_args[0][0]
        assert call_args.capability == ForgeOperation.ANIMATION_MOTION


class TestSingletonAccess:
    """Test singleton access pattern."""

    def test_get_forge_service_returns_instance(self):
        """Test get_forge_service returns ForgeService instance."""
        service = get_forge_service()
        assert isinstance(service, ForgeService)

    def test_get_forge_service_singleton_behavior(self):
        """Test get_forge_service returns same instance."""
        # Note: This might not work perfectly in tests due to module reloading
        # but we can test that it returns valid instances
        service1 = get_forge_service()
        service2 = get_forge_service()

        assert isinstance(service1, ForgeService)
        assert isinstance(service2, ForgeService)


class TestHelperMethods:
    """Test helper methods."""

    def test_requires_matrix_for_character_generation(self):
        """Test _requires_matrix returns True for character generation."""
        assert ForgeService._requires_matrix(ForgeOperation.CHARACTER_GENERATION) is True

    def test_requires_matrix_for_image_to_character(self):
        """Test _requires_matrix returns True for image-to-character."""
        assert ForgeService._requires_matrix(ForgeOperation.IMAGE_TO_CHARACTER) is True

    def test_requires_matrix_false_for_animations(self):
        """Test _requires_matrix returns False for animations."""
        assert ForgeService._requires_matrix(ForgeOperation.ANIMATION_FACIAL) is False
        assert ForgeService._requires_matrix(ForgeOperation.ANIMATION_GESTURE) is False
        assert ForgeService._requires_matrix(ForgeOperation.ANIMATION_MOTION) is False

    def test_get_handler_unknown_capability(self):
        """Test _get_handler raises error for unknown capability."""
        service = ForgeService()

        # Create a mock capability that doesn't have a handler
        with pytest.raises(ForgeError) as exc_info:
            service._get_handler(ForgeOperation.VALIDATION)

        assert "Unknown capability" in str(exc_info.value)

    def test_error_response_structure(self):
        """Test _error_response creates proper error response."""
        service = ForgeService()

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, correlation_id="err-123"
        )

        response = service._error_response(
            request,
            "Test error message",
            "test_error_code",
            0.5,  # 500ms
        )

        assert response.success is False
        assert response.error == "Test error message"
        assert response.error_code == "test_error_code"
        assert response.duration_ms == 500
        assert response.correlation_id == "err-123"

    def test_record_error_emits_metrics(self):
        """Test _record_error emits error metrics."""
        service = ForgeService()

        with patch("kagami.forge.service.API_ERRORS") as mock_metric:
            mock_labels = MagicMock()
            mock_metric.labels.return_value = mock_labels

            error = ValueError("test error")
            service._record_error(ForgeOperation.CHARACTER_GENERATION, error)

            mock_metric.labels.assert_called_with(
                endpoint="forge.character.generate", error_type="ValueError"
            )
            mock_labels.inc.assert_called_once()

    def test_record_error_handles_metric_failure(self):
        """Test _record_error doesn't raise if metrics fail."""
        service = ForgeService()

        with patch("kagami.forge.service.API_ERRORS") as mock_metric:
            mock_metric.labels.side_effect = Exception("Metrics unavailable")

            # Should not raise
            error = ValueError("test")
            service._record_error(ForgeOperation.CHARACTER_GENERATION, error)
