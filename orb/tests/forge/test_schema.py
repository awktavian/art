"""Comprehensive tests for forge schema module.

Tests all dataclasses, enums, and methods in kagami.forge.schema.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import uuid
from datetime import datetime


class TestEnums:
    """Test all enum definitions."""

    def test_character_style_values(self) -> None:
        from kagami.forge.schema import CharacterStyle

        assert CharacterStyle.REALISTIC.value == "realistic"
        assert CharacterStyle.STYLIZED.value == "stylized"
        assert CharacterStyle.CARTOON.value == "cartoon"
        assert CharacterStyle.ANIME.value == "anime"
        assert CharacterStyle.FANTASY.value == "fantasy"
        assert CharacterStyle.SCIFI.value == "scifi"
        assert CharacterStyle.ABSTRACT.value == "abstract"
        assert CharacterStyle.PHOTOREALISTIC.value == "photorealistic"

    def test_character_age_values(self) -> None:
        from kagami.forge.schema import CharacterAge

        assert CharacterAge.CHILD.value == "child"
        assert CharacterAge.TEEN.value == "teen"
        assert CharacterAge.YOUNG_ADULT.value == "young_adult"
        assert CharacterAge.ADULT.value == "adult"
        assert CharacterAge.MIDDLE_AGED.value == "middle_aged"
        assert CharacterAge.ELDERLY.value == "elderly"
        assert CharacterAge.AGELESS.value == "ageless"

    def test_voice_type_values(self) -> None:
        from kagami.forge.schema import VoiceType

        assert VoiceType.DEEP.value == "deep"
        assert VoiceType.MEDIUM.value == "medium"
        assert VoiceType.HIGH.value == "high"
        assert VoiceType.RASPY.value == "raspy"
        assert VoiceType.SMOOTH.value == "smooth"

    def test_emotional_state_values(self) -> None:
        from kagami.forge.schema import EmotionalState

        assert EmotionalState.NEUTRAL.value == "neutral"
        assert EmotionalState.HAPPY.value == "happy"
        assert EmotionalState.SAD.value == "sad"
        assert EmotionalState.ANGRY.value == "angry"

    def test_export_format_values(self) -> None:
        from kagami.forge.schema import ExportFormat

        assert ExportFormat.FBX.value == "fbx"
        assert ExportFormat.USD.value == "usd"
        assert ExportFormat.GLTF.value == "gltf"
        assert ExportFormat.GLB.value == "glb"
        assert ExportFormat.OBJ.value == "obj"

    def test_quality_level_values(self) -> None:
        from kagami.forge.schema import QualityLevel

        assert QualityLevel.LOW.value == "low"
        assert QualityLevel.MEDIUM.value == "medium"
        assert QualityLevel.HIGH.value == "high"
        assert QualityLevel.ULTRA.value == "ultra"
        assert QualityLevel.CUSTOM.value == "custom"

    def test_moral_alignment_values(self) -> None:
        from kagami.forge.schema import MoralAlignment

        assert MoralAlignment.LAWFUL_GOOD.value == "lawful_good"
        assert MoralAlignment.CHAOTIC_EVIL.value == "chaotic_evil"
        assert MoralAlignment.TRUE_NEUTRAL.value == "true_neutral"


class TestVector3:
    """Test Vector3 dataclass."""

    def test_default_values(self) -> None:
        from kagami.forge.schema import Vector3

        v = Vector3()
        assert v.x == 0.0
        assert v.y == 0.0
        assert v.z == 0.0

    def test_custom_values(self) -> None:
        from kagami.forge.schema import Vector3

        v = Vector3(1.0, 2.0, 3.0)
        assert v.x == 1.0
        assert v.y == 2.0
        assert v.z == 3.0

    def test_to_list(self) -> None:
        from kagami.forge.schema import Vector3

        v = Vector3(1.0, 2.0, 3.0)
        assert v.to_list() == [1.0, 2.0, 3.0]

    def test_to_numpy(self) -> None:
        from kagami.forge.schema import Vector3

        v = Vector3(1.0, 2.0, 3.0)
        result = v.to_numpy()
        # Should be a list or numpy array
        assert len(result) == 3


class TestBoundingBox:
    """Test BoundingBox dataclass."""

    def test_center_calculation(self):
        from kagami.forge.schema import BoundingBox, Vector3

        bb = BoundingBox(min_point=Vector3(0.0, 0.0, 0.0), max_point=Vector3(2.0, 4.0, 6.0))
        center = bb.center
        assert center.x == 1.0
        assert center.y == 2.0
        assert center.z == 3.0

    def test_size_calculation(self):
        from kagami.forge.schema import BoundingBox, Vector3

        bb = BoundingBox(min_point=Vector3(0.0, 0.0, 0.0), max_point=Vector3(2.0, 4.0, 6.0))
        size = bb.size
        assert size.x == 2.0
        assert size.y == 4.0
        assert size.z == 6.0


class TestMaterial:
    """Test Material dataclass."""

    def test_default_values(self):
        from kagami.forge.schema import Material

        m = Material(name="test_material")
        assert m.name == "test_material"
        assert m.base_color == (0.8, 0.8, 0.8, 1.0)
        assert m.metallic == 0.0
        assert m.roughness == 0.5
        assert m.normal_map is None
        assert m.properties == {}


class TestSkeleton:
    """Test Skeleton dataclass."""

    def test_get_bone_by_name_found(self):
        from kagami.forge.schema import Bone, Skeleton

        bones = [Bone(name="root", index=0), Bone(name="spine", index=1, parent_index=0)]
        skeleton = Skeleton(bones=bones)

        found = skeleton.get_bone_by_name("spine")
        assert found is not None
        assert found.name == "spine"
        assert found.index == 1

    def test_get_bone_by_name_not_found(self):
        from kagami.forge.schema import Bone, Skeleton

        bones = [Bone(name="root", index=0)]
        skeleton = Skeleton(bones=bones)

        not_found = skeleton.get_bone_by_name("nonexistent")
        assert not_found is None


class TestCharacter:
    """Test Character dataclass."""

    def test_default_creation(self):
        from kagami.forge.schema import Character

        char = Character()
        assert char.name == "Unnamed Character"
        assert char.concept == ""
        assert char.character_id is not None

    def test_post_init_id_sync(self):
        from kagami.forge.schema import Character

        # Test when id is provided but character_id is empty
        char = Character(id="test-id", character_id="")
        assert char.character_id == "test-id"

        # Test when character_id is provided but id is None
        char2 = Character(character_id="char-id", id=None)
        assert char2.id == "char-id"

        # Test when both are provided, they stay as is
        char3 = Character(id="id-1", character_id="char-1")
        assert char3.id == "id-1"
        assert char3.character_id == "char-1"

    def test_to_dict(self):
        from kagami.forge.schema import Character

        char = Character(name="Test Hero", concept="A brave warrior")
        data = char.to_dict()

        assert data["name"] == "Test Hero"
        assert data["concept"] == "A brave warrior"
        assert "character_id" in data
        assert "created_at" in data

    def test_from_dict(self):
        from kagami.forge.schema import Character

        data = {
            "name": "Dragon Knight",
            "concept": "An ancient dragon",
            "character_id": "dk-001",
        }
        char = Character.from_dict(data)

        assert char.name == "Dragon Knight"
        assert char.concept == "An ancient dragon"
        assert char.character_id == "dk-001"

    def test_get_export_data(self):
        from kagami.forge.schema import Character, ExportFormat

        char = Character(name="Export Test", concept="Testing exports")
        export_data = char.get_export_data(ExportFormat.FBX)

        assert export_data["name"] == "Export Test"
        assert export_data["format"] == "fbx"
        assert "character_id" in export_data


class TestCharacterRequest:
    """Test CharacterRequest dataclass."""

    def test_default_creation(self):
        from kagami.forge.schema import CharacterRequest, QualityLevel

        req = CharacterRequest(concept="A mysterious wizard")
        assert req.concept == "A mysterious wizard"
        assert req.quality_level == QualityLevel.HIGH
        assert req.priority == 5
        assert req.request_id is not None

    def test_with_constraints(self):
        from kagami.forge.schema import (
            CharacterRequest,
            GenerationConstraints,
        )

        constraints = GenerationConstraints(max_polygons=10000, max_bones=50)
        req = CharacterRequest(concept="Simple character", constraints=constraints)

        assert req.constraints.max_polygons == 10000
        assert req.constraints.max_bones == 50


class TestQualityMetrics:
    """Test QualityMetrics dataclass."""

    def test_default_values(self):
        from kagami.forge.schema import QualityMetrics

        metrics = QualityMetrics()
        assert metrics.completeness_score == 0.0
        assert metrics.overall_quality == 0.0
        assert metrics.issues == []

    def test_post_init_overall_quality(self):
        from kagami.forge.schema import QualityMetrics

        metrics = QualityMetrics(overall_score=0.85)
        assert metrics.overall_quality == 0.85


class TestPerformanceMetrics:
    """Test PerformanceMetrics dataclass."""

    def test_get_bottleneck_empty(self):
        from kagami.forge.schema import PerformanceMetrics

        metrics = PerformanceMetrics()
        assert metrics.get_bottleneck() is None

    def test_get_bottleneck_with_data(self):
        from kagami.forge.schema import PerformanceMetrics

        metrics = PerformanceMetrics(module_times={"mesh": 5.0, "rigging": 10.0, "texture": 3.0})
        bottleneck = metrics.get_bottleneck()
        assert bottleneck == "rigging"


class TestPipelineStage:
    """Test PipelineStage dataclass."""

    def test_duration_not_set(self):
        from kagami.forge.schema import PipelineStage

        stage = PipelineStage(name="mesh_gen")
        assert stage.duration is None

    def test_duration_calculated(self):
        from datetime import timedelta

        from kagami.forge.schema import PipelineStage

        now = datetime.now()
        stage = PipelineStage(name="mesh_gen", start_time=now, end_time=now + timedelta(seconds=5))
        assert stage.duration == 5.0


class TestProfiles:
    """Test various profile dataclasses."""

    def test_voice_profile(self):
        from kagami.forge.schema import VoiceProfile, VoiceType

        profile = VoiceProfile(voice_type=VoiceType.DEEP)
        assert profile.voice_type == VoiceType.DEEP
        assert profile.language == "en-US"
        assert profile.tts_model == "tortoise"

    def test_personality_profile(self):
        from kagami.forge.schema import PersonalityProfile

        profile = PersonalityProfile(traits=["brave", "curious"])
        assert "brave" in profile.traits
        assert profile.social_style == "balanced"

    def test_emotional_profile(self):
        from kagami.forge.schema import EmotionalProfile, EmotionalState

        profile = EmotionalProfile()
        assert profile.base_mood == EmotionalState.NEUTRAL
        assert profile.emotional_range == 0.7


class TestGenerationResults:
    """Test generation result dataclasses."""

    def test_generation_result(self):
        from kagami.forge.schema import GenerationResult

        result = GenerationResult(success=True, generation_time=2.5, quality_score=0.9)
        assert result.success is True
        assert result.generation_time == 2.5
        assert result.quality_score == 0.9

    def test_voice_result(self):
        from kagami.forge.schema import VoiceResult

        result = VoiceResult(success=False, error="Model not available")
        assert result.success is False
        assert result.error == "Model not available"

    def test_behavior_result(self):
        from kagami.forge.schema import BehaviorResult

        result = BehaviorResult(success=True, consistency_score=0.95)
        assert result.consistency_score == 0.95
