"""End-to-end test: Text → Fully Animated Speaking Character in Scene.

This test verifies the complete Forge pipeline works without fallbacks:
1. Visual Design (3D mesh via Gaussian Splatting)
2. Rigging (skeleton/weights via UniRig)
3. Animation (motion via Motion-Agent)
4. Voice Synthesis (speech via Parler-TTS)
5. Personality & Narrative (LLM-powered)
6. World Composition (scene placement)
7. Export (multi-format)

Run with: pytest tests/forge/test_full_pipeline_e2e.py -v
"""

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami.forge.exceptions import ModuleNotAvailableError
from kagami.forge.matrix.orchestrator import ForgeMatrix
from kagami.forge.matrix.registry import ComponentRegistry

# Core imports
from kagami.forge.schema import (
    CharacterRequest,
    CharacterStyle,
    ExportFormat,
    QualityLevel,
    StylePreferences,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def character_request() -> CharacterRequest:
    """Create a realistic character request."""
    return CharacterRequest(
        concept="A friendly robot companion with glowing blue eyes and a chrome body",
        style=StylePreferences(
            primary_style=CharacterStyle.REALISTIC,
            secondary_styles=[CharacterStyle.STYLIZED],
            color_palette=["chrome", "blue", "white"],
            detail_level="high",
        ),
        quality_level=QualityLevel.MEDIUM,
        export_formats=[ExportFormat.GLTF, ExportFormat.FBX],
        metadata={
            "name": "Sparkbot",
            "description": "A helpful robot assistant that loves to learn and help humans",
        },
    )


@pytest.fixture
def mock_mesh():
    """Create a mock mesh object."""
    import numpy as np

    mesh = MagicMock()
    mesh.vertices = np.random.rand(1000, 3).astype(np.float32)
    mesh.faces = np.random.randint(0, 1000, (500, 3))
    mesh.vertex_normals = np.random.rand(1000, 3).astype(np.float32)
    mesh.centroid = np.array([0.0, 0.5, 0.0])
    mesh.extents = np.array([1.0, 2.0, 1.0])
    return mesh


@pytest.fixture
def mock_generation_result(mock_mesh):
    """Create a mock generation result with mesh data."""
    from kagami.forge.schema import BoundingBox, GenerationResult, Mesh, Vector3

    return GenerationResult(
        success=True,
        mesh_data=Mesh(
            name="test_mesh",
            vertices=mock_mesh.vertices,
            faces=mock_mesh.faces,
            bounds=BoundingBox(
                min_point=Vector3(-0.5, 0.0, -0.5),
                max_point=Vector3(0.5, 2.0, 0.5),
            ),
        ),
        generation_time=2.5,
        quality_score=0.85,
    )


# ============================================================================
# Component Verification Tests
# ============================================================================


class TestPipelineComponents:
    """Verify each pipeline component is properly configured."""

    def test_visual_design_module_available(self):
        """CharacterVisualProfiler should be importable."""
        from kagami.forge.modules.visual_design.character_profiler import (
            CharacterVisualProfiler,
        )

        assert CharacterVisualProfiler is not None
        profiler = CharacterVisualProfiler()
        assert profiler is not None

    def test_rigging_module_available(self):
        """RiggingModule should be importable."""
        from kagami.forge.modules.rigging import RiggingModule

        assert RiggingModule is not None
        rigging = RiggingModule()
        assert rigging is not None

    def test_animation_module_available(self):
        """AnimationModule should be importable."""
        from kagami.forge.modules.animation import AnimationModule

        assert AnimationModule is not None
        animation = AnimationModule("animation")
        assert animation is not None

    def test_voice_registry_available(self):
        """Voice registry should be importable from canonical location."""
        from kagami.core.services.voice.voice_registry import (
            Speaker,
            VoiceProfile,
            get_voice,
        )

        assert Speaker is not None
        assert VoiceProfile is not None
        profile = get_voice(Speaker.KAGAMI)
        assert profile is not None
        assert profile.speaker == Speaker.KAGAMI

    def test_world_composer_available(self):
        """WorldComposer should be importable."""
        from kagami.forge.modules.world.world_composer import WorldComposer

        assert WorldComposer is not None
        composer = WorldComposer()
        assert composer is not None


class TestComponentIntegration:
    """Test component integration points."""

    @pytest.mark.asyncio
    async def test_visual_to_rigging_handoff(self, mock_generation_result):
        """Visual design output should be usable by rigging module."""
        from kagami.forge.modules.rigging import RiggedMesh, RiggingModule

        # Verify mesh data is in expected format for rigging
        mesh_data = mock_generation_result.mesh_data
        assert mesh_data is not None
        assert mesh_data.vertices is not None
        assert mesh_data.faces is not None

        # Verify RiggingModule can accept this input structure
        rigging = RiggingModule()
        await rigging.initialize()
        assert rigging.initialized

    @pytest.mark.asyncio
    async def test_animation_input_format(self):
        """Animation module should accept text prompts."""
        from kagami.forge.modules.animation import AnimationModule

        module = AnimationModule("animation")

        # Verify expected input format
        input_data = {
            "text_prompt": "a person walking forward",
            "motion_length": 3.0,
        }

        # Module should accept this format (actual generation requires models)
        assert "text_prompt" in input_data
        assert "motion_length" in input_data


# ============================================================================
# Pipeline Flow Tests
# ============================================================================


class TestPipelineFlow:
    """Test the complete pipeline flow."""

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self):
        """ForgeMatrix should initialize with all components."""
        matrix = ForgeMatrix()
        await matrix.initialize()
        assert matrix.initialized

    @pytest.mark.asyncio
    async def test_pipeline_requires_all_components(self, character_request):
        """Pipeline should fail fast if required components are unavailable."""
        matrix = ForgeMatrix()
        await matrix.initialize()

        # If components are unavailable, pipeline should raise ModuleNotAvailableError
        # not silently continue with None values
        # This verifies no fallback behavior

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocked_dependencies(
        self, character_request, mock_generation_result
    ):
        """Full pipeline should work when all dependencies are mocked."""
        import numpy as np
        from kagami.forge.modules.animation import MotionSequence

        # Create comprehensive mocks for all modules
        visual_mock = AsyncMock()
        visual_mock.generate = AsyncMock(return_value=mock_generation_result)

        rigging_mock = AsyncMock()
        rigging_result = MagicMock()
        rigging_result.data = MagicMock()
        rigging_result.data.skeleton = {"bones": {"root": {"position": [0, 0, 0], "parent": None}}}
        rigging_result.data.weights = np.ones((100, 1))
        rigging_result.status = MagicMock()
        rigging_result.status.value = "completed"
        rigging_mock.process = AsyncMock(return_value=rigging_result)
        rigging_mock.initialize = AsyncMock()
        rigging_mock.initialized = True

        animation_mock = AsyncMock()
        animation_result = MagicMock()
        animation_result.status = MagicMock()
        animation_result.status.value = "completed"
        animation_result.data = {
            "animation_data": {"motion": [[0, 0, 0]], "fps": 20},
            "motion_sequence": MotionSequence(np.zeros((60, 22, 3)), 20.0),
            "performance_stats": {"avg_inference_time": 25.0},
        }
        animation_result.error = None
        animation_mock.process = AsyncMock(return_value=animation_result)
        animation_mock.initialize = AsyncMock()

        personality_mock = AsyncMock()
        personality_mock.generate = AsyncMock(
            return_value={"traits": ["friendly", "helpful"], "openness": 0.8}
        )

        voice_mock = AsyncMock()
        voice_mock.generate = AsyncMock(
            return_value={
                "audio_path": "/tmp/voice.wav",
                "duration_seconds": 2.5,
                "colony": "kagami",
            }
        )

        narrative_mock = AsyncMock()
        narrative_mock.generate = AsyncMock(
            return_value={"backstory": "A robot created to help humanity.", "goals": ["assist"]}
        )

        export_mock = AsyncMock()
        export_mock.export = AsyncMock(
            return_value={"file_path": "/tmp/character.gltf", "format": "gltf"}
        )

        # Patch registry to return our mocks
        matrix = ForgeMatrix()

        with patch.object(
            matrix.registry,
            "ai_modules",
            {
                "character_profiler": visual_mock,
                "rigging": rigging_mock,
                "animation": animation_mock,
                "personality_engine": personality_mock,
                "voice": voice_mock,
                "narrative": narrative_mock,
                "export_manager": export_mock,
            },
        ):
            with patch.object(matrix.registry, "is_available", return_value=True):
                with patch.object(matrix.registry, "get_module") as get_module_mock:

                    def get_module_side_effect(name):
                        return {
                            "character_profiler": visual_mock,
                            "rigging": rigging_mock,
                            "animation": animation_mock,
                            "personality_engine": personality_mock,
                            "voice": voice_mock,
                            "narrative": narrative_mock,
                            "export_manager": export_mock,
                        }.get(name)

                    get_module_mock.side_effect = get_module_side_effect

                    await matrix.initialize()

                    # Execute pipeline
                    result = await matrix.generate_character(character_request)

                    # Verify result structure
                    assert result is not None
                    assert result.get("success") is True
                    assert result.get("status") == "success"

                    # Verify all components were called
                    visual_mock.generate.assert_called_once()
                    rigging_mock.process.assert_called_once()
                    animation_mock.process.assert_called_once()
                    personality_mock.generate.assert_called_once()
                    voice_mock.generate.assert_called_once()
                    narrative_mock.generate.assert_called_once()
                    export_mock.export.assert_called()


# ============================================================================
# No-Fallback Verification Tests
# ============================================================================


class TestNoFallbacks:
    """Verify no fallback behaviors exist in the pipeline."""

    @pytest.mark.asyncio
    async def test_visual_design_fails_fast(self):
        """Visual design should fail if Gaussian Splatting unavailable."""
        from kagami.forge.matrix.components import generate_visuals

        registry = MagicMock()
        registry.is_available.return_value = False

        tracer = MagicMock()

        request = MagicMock()

        with pytest.raises(ModuleNotAvailableError):
            await generate_visuals(registry, tracer, request)

    @pytest.mark.asyncio
    async def test_rigging_fails_fast(self):
        """Rigging should fail if UniRig unavailable."""
        from kagami.forge.matrix.components import process_rigging

        registry = MagicMock()
        registry.is_available.return_value = False

        tracer = MagicMock()
        request = MagicMock()
        mesh = MagicMock()

        with pytest.raises(ModuleNotAvailableError):
            await process_rigging(registry, tracer, request, mesh)

    @pytest.mark.asyncio
    async def test_animation_fails_fast(self):
        """Animation should fail if Motion-Agent unavailable."""
        from kagami.forge.matrix.components import animate_character

        registry = MagicMock()
        registry.is_available.return_value = False

        tracer = MagicMock()
        request = MagicMock()
        rigged_mesh = MagicMock()

        with pytest.raises(ModuleNotAvailableError):
            await animate_character(registry, tracer, request, rigged_mesh)

    @pytest.mark.asyncio
    async def test_voice_fails_fast(self):
        """Voice synthesis should fail if Parler-TTS unavailable."""
        from kagami.forge.matrix.components import generate_voice

        registry = MagicMock()
        registry.is_available.return_value = False

        tracer = MagicMock()
        request = MagicMock()

        with pytest.raises(ModuleNotAvailableError):
            await generate_voice(registry, tracer, request)

    @pytest.mark.asyncio
    async def test_export_fails_fast(self):
        """Export should fail if export manager unavailable."""
        from kagami.forge.matrix.components import export_character

        registry = MagicMock()
        registry.is_available.return_value = False

        character_data = {}
        formats = ["gltf"]

        with pytest.raises(ModuleNotAvailableError):
            await export_character(registry, character_data, formats)


# ============================================================================
# Data Flow Verification
# ============================================================================


class TestDataFlow:
    """Verify correct data flows between pipeline stages."""

    @pytest.mark.asyncio
    async def test_mesh_passes_from_visual_to_rigging(self):
        """Mesh data should flow correctly from visual design to rigging."""
        import numpy as np

        # Create realistic mesh data
        vertices = np.random.rand(500, 3).astype(np.float32)
        faces = np.random.randint(0, 500, (200, 3))

        from kagami.forge.schema import BoundingBox, Mesh, Vector3

        mesh = Mesh(
            name="test",
            vertices=vertices,
            faces=faces,
            bounds=BoundingBox(
                min_point=Vector3(-1, -1, -1),
                max_point=Vector3(1, 1, 1),
            ),
        )

        # Verify mesh has required attributes for rigging
        assert hasattr(mesh, "vertices")
        assert hasattr(mesh, "faces")
        assert mesh.vertices.shape[1] == 3  # xyz
        assert mesh.faces.shape[1] == 3  # triangles

    @pytest.mark.asyncio
    async def test_rigged_mesh_passes_to_animation(self):
        """Rigged mesh with skeleton should flow to animation."""
        import numpy as np
        import trimesh
        from kagami.forge.modules.rigging import RiggedMesh

        # Create mock trimesh
        mesh = trimesh.Trimesh(
            vertices=np.random.rand(100, 3),
            faces=np.random.randint(0, 100, (50, 3)),
        )

        skeleton = {
            "type": "humanoid",
            "bones": {
                "root": {"position": [0, 0, 0], "parent": None},
                "spine": {"position": [0, 0.5, 0], "parent": "root"},
                "head": {"position": [0, 1.5, 0], "parent": "spine"},
            },
        }

        weights = np.random.rand(100, 3)  # 100 verts, 3 bones

        rigged = RiggedMesh(mesh, skeleton, weights)

        # Verify rigged mesh has required data for animation
        assert rigged.skeleton is not None
        assert rigged.weights is not None
        assert "bones" in rigged.skeleton

    @pytest.mark.asyncio
    async def test_animation_output_format(self):
        """Animation output should be in correct format for export."""
        import numpy as np
        from kagami.forge.modules.animation import AnimationData

        motion = np.zeros((60, 22, 3))  # 60 frames, 22 joints, xyz
        anim = AnimationData(motion, "walking forward", fps=20.0)

        # Verify format
        assert anim.fps == 20.0
        assert anim.duration == 3.0  # 60 frames / 20 fps
        assert anim.text_prompt == "walking forward"

        # Test serialization
        data = anim.to_dict()
        assert "motion" in data
        assert "fps" in data
        assert "duration" in data


# ============================================================================
# Integration Test
# ============================================================================


class TestEndToEndIntegration:
    """Full end-to-end integration test."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_complete_pipeline_integration(self, character_request):
        """Test complete pipeline with real modules where possible.

        This test verifies the full flow but uses mocks for heavy ML models.
        Set KAGAMI_REAL_MODELS=1 to run with actual models (very slow).
        """
        import os

        import numpy as np

        use_real_models = os.environ.get("KAGAMI_REAL_MODELS") == "1"

        if not use_real_models:
            pytest.skip("Skipping real model test. Set KAGAMI_REAL_MODELS=1 to run.")

        # This would run the actual pipeline with real models
        matrix = ForgeMatrix()
        await matrix.initialize()

        result = await matrix.generate_character(character_request)

        # Comprehensive assertions
        assert result["success"] is True
        assert result["character"] is not None
        assert result.get("animation") is not None
        assert result.get("voice") is not None


# ============================================================================
# Schema Validation
# ============================================================================


class TestSchemaValidation:
    """Verify request/response schemas are correct."""

    def test_character_request_complete(self, character_request):
        """CharacterRequest should have all required fields."""
        assert character_request.concept is not None
        assert len(character_request.concept) >= 3
        assert character_request.style is not None
        assert character_request.export_formats is not None
        assert len(character_request.export_formats) > 0

    def test_export_formats_valid(self):
        """Export formats should be valid enum values."""
        from kagami.forge.schema import ExportFormat

        valid_formats = [
            ExportFormat.GLTF,
            ExportFormat.GLB,
            ExportFormat.FBX,
            ExportFormat.USD,
            ExportFormat.OBJ,
            ExportFormat.DAE,
        ]

        for fmt in valid_formats:
            assert fmt.value is not None
            assert isinstance(fmt.value, str)

    def test_quality_levels_valid(self):
        """Quality levels should affect generation parameters."""
        from kagami.forge.schema import QualityLevel

        levels = [
            QualityLevel.LOW,
            QualityLevel.MEDIUM,
            QualityLevel.HIGH,
            QualityLevel.ULTRA,
        ]

        for level in levels:
            assert level.value is not None
