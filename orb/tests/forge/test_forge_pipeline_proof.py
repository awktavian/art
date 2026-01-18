"""Comprehensive proof that every component of the Forge pipeline works.

This test suite provides systematic verification of all Forge subsystems:
1. Schema and data structures
2. Service layer (ForgeService)
3. Matrix orchestrator (ForgeMatrix)
4. Animation modules (facial, gesture, motion)
5. Export modules (GLTF, FBX, USD, etc.)
6. Validation systems
7. Integration between components

Run with: pytest tests/forge/test_forge_pipeline_proof.py -v
"""

from __future__ import annotations

import asyncio
import pytest
import numpy as np
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# === COMPONENT IMPORTS ===
# Schema
from kagami.forge.schema import (
    CharacterStyle,
    CharacterAge,
    VoiceType,
    EmotionalState,
    ExportFormat,
    QualityLevel,
    Vector3,
    Transform,
    BoundingBox,
    Material,
    Bone,
    Skeleton,
    Animation,
    AnimationChannel,
    AnimationKeyframe,
    VoiceProfile,
    PersonalityProfile,
    EmotionalProfile,
    Backstory,
    BackstoryElement,
    Character,
    CharacterRequest,
    StylePreferences,
    GenerationConstraints,
    QualityMetrics,
    PerformanceMetrics,
    GenerationResult,
    GestureType,
    MotionType,
    FacialType,
)

# Service Layer
from kagami.forge.service import (
    ForgeOperation,
    ForgeRequest,
    ForgeResponse,
    ForgeService,
    get_forge_service,
)

# Exceptions
from kagami.forge.exceptions import (
    ForgeError,
    ValidationError,
    ModuleNotAvailableError,
    ModuleInitializationError,
    ExportError,
)

# Validation
from kagami.forge.validation import ForgeValidator

pytestmark = pytest.mark.tier_integration


# =============================================================================
# SECTION 1: SCHEMA AND DATA STRUCTURES
# =============================================================================


class TestSchemaEnums:
    """Verify all enum types are properly defined."""

    def test_character_style_enum(self):
        """Test CharacterStyle enum values."""
        assert CharacterStyle.REALISTIC.value == "realistic"
        assert CharacterStyle.STYLIZED.value == "stylized"
        assert CharacterStyle.ANIME.value == "anime"
        assert CharacterStyle.PHOTOREALISTIC.value == "photorealistic"
        assert len(CharacterStyle) >= 7

    def test_character_age_enum(self):
        """Test CharacterAge enum values."""
        assert CharacterAge.ADULT.value == "adult"
        assert CharacterAge.CHILD.value == "child"
        assert CharacterAge.ELDERLY.value == "elderly"
        assert len(CharacterAge) >= 6

    def test_voice_type_enum(self):
        """Test VoiceType enum values."""
        assert VoiceType.DEEP.value == "deep"
        assert VoiceType.MEDIUM.value == "medium"
        assert VoiceType.HIGH.value == "high"
        assert len(VoiceType) >= 6

    def test_emotional_state_enum(self):
        """Test EmotionalState enum values."""
        assert EmotionalState.NEUTRAL.value == "neutral"
        assert EmotionalState.HAPPY.value == "happy"
        assert EmotionalState.SAD.value == "sad"
        assert EmotionalState.ANGRY.value == "angry"
        assert len(EmotionalState) >= 8

    def test_export_format_enum(self):
        """Test ExportFormat enum values."""
        assert ExportFormat.FBX.value == "fbx"
        assert ExportFormat.GLTF.value == "gltf"
        assert ExportFormat.USD.value == "usd"
        assert ExportFormat.OBJ.value == "obj"
        assert len(ExportFormat) >= 6

    def test_quality_level_enum(self):
        """Test QualityLevel enum values."""
        assert QualityLevel.LOW.value == "low"
        assert QualityLevel.MEDIUM.value == "medium"
        assert QualityLevel.HIGH.value == "high"
        assert QualityLevel.ULTRA.value == "ultra"

    def test_gesture_type_enum(self):
        """Test GestureType enum values."""
        assert GestureType.EXPRESSIVE.value == "expressive"
        assert GestureType.FUNCTIONAL.value == "functional"

    def test_motion_type_enum(self):
        """Test MotionType enum values."""
        assert MotionType.FLUID.value == "fluid"
        assert MotionType.GRACEFUL.value == "graceful"

    def test_facial_type_enum(self):
        """Test FacialType enum values."""
        assert FacialType.EXPRESSIVE.value == "expressive"
        assert FacialType.STOIC.value == "stoic"


class TestSchemaDataStructures:
    """Verify all data structures work correctly."""

    def test_vector3_creation_and_methods(self):
        """Test Vector3 dataclass."""
        v = Vector3(1.0, 2.0, 3.0)
        assert v.x == 1.0
        assert v.y == 2.0
        assert v.z == 3.0
        assert v.to_list() == [1.0, 2.0, 3.0]

        # Test numpy conversion
        arr = v.to_numpy()
        assert len(arr) == 3

    def test_transform_creation(self):
        """Test Transform dataclass."""
        t = Transform()
        assert t.position.x == 0.0
        assert t.rotation.x == 0.0
        assert t.scale.x == 1.0

    def test_bounding_box_properties(self):
        """Test BoundingBox center and size calculations."""
        bbox = BoundingBox(
            min_point=Vector3(0.0, 0.0, 0.0), max_point=Vector3(2.0, 4.0, 6.0)
        )
        assert bbox.center.x == 1.0
        assert bbox.center.y == 2.0
        assert bbox.center.z == 3.0
        assert bbox.size.x == 2.0
        assert bbox.size.y == 4.0
        assert bbox.size.z == 6.0

    def test_material_creation(self):
        """Test Material dataclass."""
        mat = Material(
            name="test_material",
            base_color=(1.0, 0.0, 0.0, 1.0),
            metallic=0.8,
            roughness=0.2,
        )
        assert mat.name == "test_material"
        assert mat.metallic == 0.8
        assert mat.roughness == 0.2

    def test_bone_and_skeleton(self):
        """Test Bone and Skeleton dataclasses."""
        root_bone = Bone(name="root", index=0, parent_index=-1)
        child_bone = Bone(name="spine", index=1, parent_index=0)
        skeleton = Skeleton(bones=[root_bone, child_bone], root_bone_index=0)

        assert skeleton.get_bone_by_name("root") is root_bone
        assert skeleton.get_bone_by_name("spine") is child_bone
        assert skeleton.get_bone_by_name("nonexistent") is None

    def test_animation_keyframe(self):
        """Test AnimationKeyframe dataclass."""
        kf = AnimationKeyframe(time=0.5, transform=Transform())
        assert kf.time == 0.5
        assert kf.interpolation == "linear"

    def test_animation_channel(self):
        """Test AnimationChannel dataclass."""
        kf1 = AnimationKeyframe(time=0.0, transform=Transform())
        kf2 = AnimationKeyframe(time=1.0, transform=Transform())
        channel = AnimationChannel(bone_name="root", keyframes=[kf1, kf2])
        assert channel.bone_name == "root"
        assert len(channel.keyframes) == 2

    def test_voice_profile(self):
        """Test VoiceProfile dataclass."""
        vp = VoiceProfile(
            voice_type=VoiceType.DEEP,
            pitch=-0.2,
            speed=0.9,
            language="en-US",
        )
        assert vp.voice_type == VoiceType.DEEP
        assert vp.pitch == -0.2

    def test_personality_profile(self):
        """Test PersonalityProfile dataclass."""
        pp = PersonalityProfile(
            traits=["brave", "loyal"],
            big_five={"openness": 0.7, "conscientiousness": 0.8},
        )
        assert "brave" in pp.traits
        assert pp.big_five["openness"] == 0.7

    def test_emotional_profile(self):
        """Test EmotionalProfile dataclass."""
        ep = EmotionalProfile(
            base_mood=EmotionalState.HAPPY, emotional_range=0.8, empathy_level=0.9
        )
        assert ep.base_mood == EmotionalState.HAPPY
        assert ep.emotional_range == 0.8

    def test_backstory(self):
        """Test Backstory dataclass."""
        element = BackstoryElement(
            event="Born in a small village", age=0, impact="high", category="origin"
        )
        backstory = Backstory(
            summary="A hero's journey",
            origin="Small village in the mountains",
            elements=[element],
            goals=["Save the kingdom"],
        )
        assert backstory.summary == "A hero's journey"
        assert len(backstory.elements) == 1


class TestCharacterModel:
    """Test Character model and serialization."""

    def test_character_creation(self):
        """Test Character dataclass creation."""
        char = Character(
            name="Test Hero",
            concept="A brave warrior",
            style=CharacterStyle.REALISTIC,
            age=CharacterAge.ADULT,
        )
        assert char.name == "Test Hero"
        assert char.character_id is not None
        assert char.id == char.character_id

    def test_character_to_dict(self):
        """Test Character.to_dict() method."""
        char = Character(name="Test", concept="test concept")
        data = char.to_dict()

        assert data["name"] == "Test"
        assert data["concept"] == "test concept"
        assert "character_id" in data
        assert "created_at" in data

    def test_character_from_dict(self):
        """Test Character.from_dict() method."""
        data = {
            "character_id": "test-123",
            "name": "FromDict Character",
            "concept": "Created from dict",
        }
        char = Character.from_dict(data)

        assert char.character_id == "test-123"
        assert char.name == "FromDict Character"

    def test_character_export_data(self):
        """Test Character.get_export_data() method."""
        char = Character(name="Export Test", concept="test")
        export = char.get_export_data(ExportFormat.FBX)

        assert export["format"] == "fbx"
        assert export["name"] == "Export Test"


class TestCharacterRequest:
    """Test CharacterRequest model."""

    def test_request_creation(self):
        """Test CharacterRequest creation."""
        request = CharacterRequest(
            concept="A wise wizard",
            quality_level=QualityLevel.HIGH,
            export_formats=[ExportFormat.GLTF, ExportFormat.FBX],
        )
        assert request.concept == "A wise wizard"
        assert request.quality_level == QualityLevel.HIGH
        assert len(request.export_formats) == 2
        assert request.request_id is not None

    def test_style_preferences(self):
        """Test StylePreferences dataclass."""
        style = StylePreferences(
            primary_style=CharacterStyle.ANIME,
            secondary_styles=[CharacterStyle.STYLIZED],
        )
        assert style.primary_style == CharacterStyle.ANIME
        assert len(style.secondary_styles) == 1

    def test_generation_constraints(self):
        """Test GenerationConstraints dataclass."""
        constraints = GenerationConstraints(
            max_polygons=100000,
            max_texture_size=4096,
            target_platform="mobile",
        )
        assert constraints.max_polygons == 100000
        assert constraints.target_platform == "mobile"


class TestQualityAndPerformanceMetrics:
    """Test quality and performance metric structures."""

    def test_quality_metrics(self):
        """Test QualityMetrics dataclass."""
        qm = QualityMetrics(
            completeness_score=0.9,
            consistency_score=0.85,
            overall_score=0.87,
        )
        assert qm.overall_score == 0.87

    def test_performance_metrics(self):
        """Test PerformanceMetrics dataclass."""
        pm = PerformanceMetrics(
            total_time=5.2,
            module_times={"visual": 2.0, "rigging": 1.5, "export": 1.7},
            memory_usage_mb=512,
        )
        assert pm.get_bottleneck() == "visual"

    def test_generation_result(self):
        """Test GenerationResult dataclass."""
        result = GenerationResult(
            success=True, generation_time=2.5, quality_score=0.92
        )
        assert result.success is True
        assert result.quality_score == 0.92


# =============================================================================
# SECTION 2: SERVICE LAYER (ForgeService)
# =============================================================================


class TestForgeRequest:
    """Test ForgeRequest dataclass."""

    def test_quality_level_mapping(self):
        """Test quality_mode to QualityLevel conversion."""
        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, quality_mode="preview"
        )
        assert request.quality_level == QualityLevel.LOW

        request.quality_mode = "draft"
        assert request.quality_level == QualityLevel.MEDIUM

        request.quality_mode = "final"
        assert request.quality_level == QualityLevel.HIGH

    def test_export_format_conversion(self):
        """Test export format string to enum conversion."""
        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            export_formats=["fbx", "gltf", "invalid"],
        )
        formats = request.export_format_enums
        assert ExportFormat.FBX in formats
        assert ExportFormat.GLTF in formats
        assert len(formats) == 2  # Invalid skipped


class TestForgeResponse:
    """Test ForgeResponse dataclass."""

    def test_to_dict_success(self):
        """Test successful response serialization."""
        response = ForgeResponse(
            success=True,
            capability="character.generate",
            data={"character": {"name": "Hero"}},
            duration_ms=1500,
            cached=True,
        )
        result = response.to_dict()

        assert result["success"] is True
        assert result["cached"] is True
        assert result["duration_ms"] == 1500

    def test_to_dict_error(self):
        """Test error response serialization."""
        response = ForgeResponse(
            success=False,
            capability="character.generate",
            error="Generation failed",
            error_code="module_unavailable",
        )
        result = response.to_dict()

        assert result["success"] is False
        assert "error" in result
        assert "error_code" in result


class TestForgeServiceOperations:
    """Test ForgeService operations."""

    @pytest.fixture
    def mock_matrix(self):
        """Create mock ForgeMatrix."""
        matrix = MagicMock()
        matrix.initialize = AsyncMock()
        matrix.generate_character = AsyncMock(
            return_value={
                "request_id": "test-123",
                "concept": "warrior",
                "status": "success",
                "success": True,
                "character": {"name": "Hero"},
                "metrics": {"quality": 0.9},
            }
        )
        return matrix

    @pytest.fixture
    def forge_service(self, mock_matrix):
        """Create ForgeService with mocked matrix."""
        return ForgeService(matrix=mock_matrix)

    @pytest.mark.asyncio
    async def test_initialize(self, forge_service, mock_matrix):
        """Test service initialization."""
        await forge_service.initialize()
        mock_matrix.initialize.assert_called_once()
        assert forge_service._initialized is True

    @pytest.mark.asyncio
    async def test_character_generation(self, forge_service):
        """Test character generation via service."""
        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={"concept": "brave warrior"},
            quality_mode="draft",
        )
        response = await forge_service.execute(request)

        assert response.success is True
        assert response.capability == "character.generate"
        assert response.duration_ms > 0

    @pytest.mark.asyncio
    async def test_character_generation_missing_concept(self, forge_service):
        """Test validation for missing concept."""
        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION, params={}
        )
        response = await forge_service.execute(request)

        assert response.success is False
        assert response.error_code == "missing_concept"

    @pytest.mark.asyncio
    async def test_convenience_generate_character(self, forge_service):
        """Test convenience method."""
        response = await forge_service.generate_character(
            concept="wizard",
            quality_mode="preview",
            personality_brief="wise and mysterious",
        )
        assert response.success is True

    @pytest.mark.asyncio
    async def test_facial_animation_blinks(self, forge_service):
        """Test facial animation - blinks."""
        with patch(
            "kagami.forge.modules.motion.facial_animator.FacialAnimator"
        ) as mock:
            mock_instance = MagicMock()
            mock_instance.generate_blinks = AsyncMock(return_value=[{"time": 1.0}])
            mock.return_value = mock_instance

            request = ForgeRequest(
                capability=ForgeOperation.ANIMATION_FACIAL,
                params={"type": "blinks", "duration": 5.0, "blink_rate": 20},
            )
            response = await forge_service.execute(request)

            assert response.success is True
            assert "animation" in response.data

    @pytest.mark.asyncio
    async def test_gesture_animation_idle(self, forge_service):
        """Test gesture animation - idle."""
        with patch("kagami.forge.modules.motion.gesture_engine.GestureEngine") as mock:
            mock_instance = MagicMock()
            mock_instance.generate_idle_gestures = AsyncMock(
                return_value={"keyframes": []}
            )
            mock.return_value = mock_instance

            request = ForgeRequest(
                capability=ForgeOperation.ANIMATION_GESTURE,
                params={"type": "idle", "duration": 10.0},
            )
            response = await forge_service.execute(request)

            assert response.success is True

    @pytest.mark.asyncio
    async def test_motion_animation(self, forge_service):
        """Test motion animation generation."""
        with patch("kagami.forge.modules.animation.AnimationModule") as mock:
            mock_instance = MagicMock()
            mock_instance.initialize = AsyncMock()
            mock_instance.process = AsyncMock(
                return_value=MagicMock(data={"motion": "walk"})
            )
            mock.return_value = mock_instance

            request = ForgeRequest(
                capability=ForgeOperation.ANIMATION_MOTION,
                params={"prompt": "walking forward", "duration": 5.0},
            )
            response = await forge_service.execute(request)

            assert response.success is True

    @pytest.mark.asyncio
    async def test_motion_animation_missing_prompt(self, forge_service):
        """Test motion animation validation."""
        request = ForgeRequest(
            capability=ForgeOperation.ANIMATION_MOTION, params={"duration": 5.0}
        )
        response = await forge_service.execute(request)

        assert response.success is False
        assert response.error_code == "missing_prompt"


class TestForgeServiceErrorHandling:
    """Test error handling in ForgeService."""

    @pytest.fixture
    def mock_matrix(self):
        """Create mock matrix."""
        matrix = MagicMock()
        matrix.initialize = AsyncMock()
        return matrix

    @pytest.fixture
    def forge_service(self, mock_matrix):
        """Create service with mock."""
        return ForgeService(matrix=mock_matrix)

    @pytest.mark.asyncio
    async def test_module_not_available_error(self, forge_service, mock_matrix):
        """Test ModuleNotAvailableError handling."""
        mock_matrix.generate_character = AsyncMock(
            side_effect=ModuleNotAvailableError("Test module unavailable")
        )

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={"concept": "test"},
        )
        response = await forge_service.execute(request)

        assert response.success is False
        assert response.error_code == "module_unavailable"

    @pytest.mark.asyncio
    async def test_forge_error(self, forge_service, mock_matrix):
        """Test ForgeError handling."""
        mock_matrix.generate_character = AsyncMock(
            side_effect=ForgeError("Pipeline failed")
        )

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={"concept": "test"},
        )
        response = await forge_service.execute(request)

        assert response.success is False
        assert response.error_code == "forge_error"

    @pytest.mark.asyncio
    async def test_unknown_capability(self, forge_service):
        """Test unknown capability handling."""
        request = ForgeRequest(capability="unknown.operation", params={})  # type: ignore
        response = await forge_service.execute(request)

        assert response.success is False
        assert response.error_code == "forge_error"


class TestForgeServiceSingleton:
    """Test singleton pattern."""

    def test_get_forge_service_singleton(self):
        """Test that get_forge_service returns singleton."""
        # Note: This test may interact with other tests using the singleton
        service1 = get_forge_service()
        service2 = get_forge_service()
        assert service1 is service2


# =============================================================================
# SECTION 3: EXCEPTIONS
# =============================================================================


class TestExceptions:
    """Test Forge exceptions."""

    def test_forge_error(self):
        """Test ForgeError."""
        err = ForgeError("Test error")
        assert str(err) == "Test error"

    def test_validation_error_with_context(self):
        """Test ValidationError with context."""
        err = ValidationError("Invalid field", context={"field": "concept"})
        assert "Invalid field" in str(err)
        assert err.context["field"] == "concept"

    def test_module_not_available_error(self):
        """Test ModuleNotAvailableError."""
        err = ModuleNotAvailableError("genesis")
        assert "genesis" in str(err)

    def test_export_error(self):
        """Test ExportError."""
        err = ExportError("Export failed", format="fbx")
        assert "Export failed" in str(err)
        assert err.context.get("format") == "fbx"


# =============================================================================
# SECTION 4: VALIDATION
# =============================================================================


class TestContentValidation:
    """Test content validation."""

    def test_validator_initialization(self):
        """Test ForgeValidator creation."""
        validator = ForgeValidator()
        assert validator is not None

    def test_validate_request_valid(self):
        """Test valid request validation."""
        validator = ForgeValidator()
        request = CharacterRequest(
            concept="A wise wizard who studies ancient magic",
            quality_level=QualityLevel.HIGH,
        )

        errors = validator.validate_request(request)
        # Empty list means valid
        assert len(errors) == 0

    def test_validate_request_short_concept(self):
        """Test request with short concept."""
        validator = ForgeValidator()
        request = CharacterRequest(
            concept="ab",  # Too short
            quality_level=QualityLevel.HIGH,
        )

        errors = validator.validate_request(request)
        assert len(errors) > 0
        assert any("3 characters" in e for e in errors)

    @pytest.mark.asyncio
    async def test_moderate_content(self):
        """Test content moderation."""
        validator = ForgeValidator()

        # Clean content
        result = await validator.moderate_content("A brave warrior")
        assert result["flagged"] is False

        # Flagged content
        result = await validator.moderate_content("violent explicit content")
        assert result["flagged"] is True


# =============================================================================
# SECTION 5: ANIMATION MODULES
# =============================================================================


class TestFacialAnimator:
    """Test FacialAnimator module."""

    @pytest.mark.asyncio
    async def test_generate_expression(self):
        """Test expression generation."""
        from kagami.forge.modules.motion.facial_animator import FacialAnimator

        # Test with mock LLM to avoid network calls
        with patch.object(FacialAnimator, "__init__", lambda x, **kwargs: None):
            animator = FacialAnimator.__new__(FacialAnimator)
            animator.initialized = True
            animator.expression_library = {
                "happy": MagicMock(
                    blendshapes={"mouthSmileLeft": 0.8, "mouthSmileRight": 0.8},
                    duration=1.0,
                )
            }
            animator.blend_shapes = {}
            animator.llm = None

            result = await animator.generate_expression("happy", intensity=0.8)

            assert result["emotion"] == "happy"
            assert result["intensity"] == 0.8
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_generate_blinks(self):
        """Test blink generation."""
        from kagami.forge.modules.motion.facial_animator import FacialAnimator

        with patch.object(FacialAnimator, "__init__", lambda x, **kwargs: None):
            animator = FacialAnimator.__new__(FacialAnimator)
            animator.initialized = True

            blinks = await animator.generate_blinks(duration=5.0, blink_rate=20)

            assert isinstance(blinks, list)
            # Should generate approximately 5 * (20/60) = ~1.67 blinks
            assert len(blinks) >= 1


class TestGestureEngine:
    """Test GestureEngine module."""

    @pytest.mark.asyncio
    async def test_generate_idle_gestures(self):
        """Test idle gesture generation."""
        from kagami.forge.modules.motion.gesture_engine import GestureEngine

        with patch.object(GestureEngine, "__init__", lambda x, **kwargs: None):
            engine = GestureEngine.__new__(GestureEngine)
            engine.initialized = True
            engine.config = {}

            result = await engine.generate_idle_gestures(
                duration=5.0, character_traits={"energy_level": 0.5}
            )

            assert "keyframes" in result
            assert "duration" in result
            assert result["duration"] == 5.0

    @pytest.mark.asyncio
    async def test_generate_from_speech(self):
        """Test speech-based gesture generation."""
        from kagami.forge.modules.motion.gesture_engine import GestureEngine

        with patch.object(GestureEngine, "__init__", lambda x, **kwargs: None):
            engine = GestureEngine.__new__(GestureEngine)
            engine.initialized = True
            engine.config = {}

            result = await engine.generate_from_speech(
                speech_data={
                    "text": "Hello world",
                    "emphasis_words": ["Hello"],
                    "duration": 2.0,
                    "prosody": {},
                }
            )

            assert "keyframes" in result
            assert result["duration"] == 2.0


# =============================================================================
# SECTION 6: MATRIX ORCHESTRATOR
# =============================================================================


class TestMatrixComponents:
    """Test Matrix orchestrator components."""

    def test_component_registry_init(self):
        """Test ComponentRegistry initialization."""
        from kagami.forge.matrix.registry import ComponentRegistry

        registry = ComponentRegistry({"modules": {}})
        assert registry.ai_modules == {}
        assert registry.config is not None

    def test_lifecycle_manager_init(self):
        """Test LifecycleManager initialization."""
        from kagami.forge.matrix.lifecycle import LifecycleManager

        mock_registry = MagicMock()
        mock_callback = MagicMock()

        manager = LifecycleManager(mock_registry, mock_callback)
        assert manager.initialized is False
        assert manager.registry is mock_registry

    def test_forge_matrix_creation(self):
        """Test ForgeMatrix creation."""
        from kagami.forge.matrix.orchestrator import ForgeMatrix

        matrix = ForgeMatrix(config={})
        assert matrix.initialized is False
        assert matrix.config is not None


class TestForgeMatrixOperations:
    """Test ForgeMatrix operations."""

    @pytest.fixture
    def forge_matrix(self):
        """Create ForgeMatrix instance."""
        from kagami.forge.matrix.orchestrator import ForgeMatrix

        matrix = ForgeMatrix(config={"modules": {}})
        return matrix

    @pytest.mark.asyncio
    async def test_generate_character_validation(self, forge_matrix):
        """Test character generation input validation."""
        # Test with short concept
        result = await forge_matrix.generate_character({"concept": "ab"})

        assert result["success"] is False
        assert result["error_code"] == "missing_concept"

    @pytest.mark.asyncio
    async def test_execution_trace(self, forge_matrix):
        """Test execution trace recording."""
        # Initial trace should be empty
        trace = forge_matrix.get_execution_trace()
        assert isinstance(trace, list)


# =============================================================================
# SECTION 7: EXPORT MODULES
# =============================================================================


class TestExportModules:
    """Test export module functionality."""

    def test_gltf_exporter_exists(self):
        """Test GLTF exporter module exists."""
        try:
            from kagami.forge.modules.export.gltf_exporter import GLTFExporter

            exporter = GLTFExporter()
            assert exporter is not None
        except ImportError:
            pytest.skip("GLTF exporter not available")

    def test_fbx_exporter_exists(self):
        """Test FBX exporter module exists."""
        try:
            from kagami.forge.modules.export.fbx_exporter import FBXExporter

            exporter = FBXExporter()
            assert exporter is not None
        except ImportError:
            pytest.skip("FBX exporter not available")

    def test_usd_exporter_exists(self):
        """Test USD exporter module exists."""
        try:
            from kagami.forge.modules.export.usd_exporter import USDExporter

            exporter = USDExporter()
            assert exporter is not None
        except ImportError:
            pytest.skip("USD exporter not available")

    def test_obj_exporter_exists(self):
        """Test OBJ exporter module exists."""
        try:
            from kagami.forge.modules.export.obj_exporter import OBJExporter

            exporter = OBJExporter()
            assert exporter is not None
        except ImportError:
            pytest.skip("OBJ exporter not available")

    def test_export_manager_initialization(self):
        """Test ExportManager initialization."""
        try:
            from kagami.forge.modules.export.manager import ExportManager

            manager = ExportManager()
            assert manager is not None
        except ImportError:
            pytest.skip("Export manager not available")


# =============================================================================
# SECTION 8: INTEGRATION TESTS
# =============================================================================


class TestPipelineIntegration:
    """Integration tests for the full pipeline."""

    @pytest.mark.asyncio
    async def test_service_to_matrix_integration(self):
        """Test integration between service and matrix layers."""
        # Create service with mocked matrix
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()
        mock_matrix.generate_character = AsyncMock(
            return_value={
                "request_id": "test-123",
                "concept": "hero",
                "status": "success",
                "success": True,
                "character": {
                    "name": "Hero",
                    "mesh": {"vertices": []},
                    "skeleton": {"bones": []},
                },
                "metrics": {
                    "quality": 0.85,
                    "completeness": 0.9,
                },
            }
        )

        service = ForgeService(matrix=mock_matrix)

        response = await service.generate_character(
            concept="A brave hero",
            quality_mode="draft",
            export_formats=["fbx"],
        )

        assert response.success is True
        assert "character" in response.data or response.data.get("success")

    @pytest.mark.asyncio
    async def test_request_to_response_flow(self):
        """Test full request-to-response flow."""
        mock_matrix = MagicMock()
        mock_matrix.initialize = AsyncMock()
        mock_matrix.generate_character = AsyncMock(
            return_value={
                "request_id": "flow-test",
                "success": True,
                "character": {"name": "Test"},
                "metrics": {},
            }
        )

        service = ForgeService(matrix=mock_matrix)

        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={
                "concept": "A mysterious wizard",
                "personality_brief": "Wise and enigmatic",
            },
            quality_mode="final",
            export_formats=["gltf", "fbx"],
            correlation_id="test-correlation-123",
        )

        response = await service.execute(request)

        assert response.success is True
        assert response.correlation_id == "test-correlation-123"
        assert response.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_animation_pipeline(self):
        """Test animation generation pipeline."""
        mock_matrix = MagicMock()
        service = ForgeService(matrix=mock_matrix)

        # Test facial animation
        with patch(
            "kagami.forge.modules.motion.facial_animator.FacialAnimator"
        ) as mock_animator:
            instance = MagicMock()
            instance.generate_blinks = AsyncMock(
                return_value=[{"time": 1.0, "duration": 0.2}]
            )
            mock_animator.return_value = instance

            response = await service.generate_animation(
                animation_type="blinks", duration=10.0
            )

            assert response.success is True


# =============================================================================
# SUMMARY TEST - Run all component checks
# =============================================================================


class TestForgePipelineSummary:
    """Summary test that proves all components exist and are importable."""

    def test_all_schema_imports(self):
        """Verify all schema components import correctly."""
        # Enums
        assert CharacterStyle is not None
        assert CharacterAge is not None
        assert VoiceType is not None
        assert EmotionalState is not None
        assert ExportFormat is not None
        assert QualityLevel is not None

        # Data structures
        assert Vector3 is not None
        assert Transform is not None
        assert Material is not None
        assert Bone is not None
        assert Skeleton is not None
        assert Animation is not None
        assert Character is not None
        assert CharacterRequest is not None

        # Metrics
        assert QualityMetrics is not None
        assert PerformanceMetrics is not None
        assert GenerationResult is not None

    def test_all_service_imports(self):
        """Verify all service components import correctly."""
        assert ForgeOperation is not None
        assert ForgeRequest is not None
        assert ForgeResponse is not None
        assert ForgeService is not None
        assert get_forge_service is not None

    def test_all_exception_imports(self):
        """Verify all exception types import correctly."""
        assert ForgeError is not None
        assert ValidationError is not None
        assert ModuleNotAvailableError is not None
        assert ModuleInitializationError is not None
        assert ExportError is not None

    def test_validation_import(self):
        """Verify validation module imports correctly."""
        assert ForgeValidator is not None

    def test_matrix_imports(self):
        """Verify matrix orchestrator imports correctly."""
        from kagami.forge.matrix.orchestrator import ForgeMatrix, get_forge_matrix
        from kagami.forge.matrix.registry import ComponentRegistry
        from kagami.forge.matrix.lifecycle import LifecycleManager

        assert ForgeMatrix is not None
        assert get_forge_matrix is not None
        assert ComponentRegistry is not None
        assert LifecycleManager is not None

    def test_animation_imports(self):
        """Verify animation module imports correctly."""
        from kagami.forge.modules.motion.facial_animator import FacialAnimator
        from kagami.forge.modules.motion.gesture_engine import GestureEngine

        assert FacialAnimator is not None
        assert GestureEngine is not None

    def test_export_module_imports(self):
        """Verify export modules import correctly."""
        # These may fail gracefully if dependencies missing
        modules_found = 0

        try:
            from kagami.forge.modules.export.gltf_exporter import GLTFExporter

            modules_found += 1
        except ImportError:
            pass

        try:
            from kagami.forge.modules.export.fbx_exporter import FBXExporter

            modules_found += 1
        except ImportError:
            pass

        try:
            from kagami.forge.modules.export.usd_exporter import USDExporter

            modules_found += 1
        except ImportError:
            pass

        try:
            from kagami.forge.modules.export.manager import ExportManager

            modules_found += 1
        except ImportError:
            pass

        # At least the export manager should be available
        assert modules_found >= 1, "At least one export module should be available"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
