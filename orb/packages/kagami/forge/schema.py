from __future__ import annotations

"Forge Schema - Data structures and models for character generation.\n\nThis module defines all data structures used throughout the Forge character\ngeneration pipeline, ensuring consistency and type safety.\n\nCategories:\n    - Character Models: Core character data structures\n    - Generation Requests: Input specifications\n    - Module Results: Output from each pipeline stage\n    - Quality Metrics: Performance and quality measurements\n    - Export Formats: Industry-standard format definitions\n"
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

if TYPE_CHECKING:
    import numpy as np


class CharacterStyle(Enum):
    """Visual style for character generation"""

    REALISTIC = "realistic"
    STYLIZED = "stylized"
    CARTOON = "cartoon"
    ANIME = "anime"
    FANTASY = "fantasy"
    SCIFI = "scifi"
    ABSTRACT = "abstract"
    PHOTOREALISTIC = "photorealistic"


class CharacterAge(Enum):
    """Age categories for characters"""

    CHILD = "child"
    TEEN = "teen"
    YOUNG_ADULT = "young_adult"
    ADULT = "adult"
    MIDDLE_AGED = "middle_aged"
    ELDERLY = "elderly"
    AGELESS = "ageless"


class VoiceType(Enum):
    """Voice type classifications"""

    DEEP = "deep"
    MEDIUM = "medium"
    HIGH = "high"
    RASPY = "raspy"
    SMOOTH = "smooth"
    ROUGH = "rough"
    SOFT = "soft"
    POWERFUL = "powerful"


class EmotionalState(Enum):
    """Basic emotional states"""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEARFUL = "fearful"
    SURPRISED = "surprised"
    DISGUSTED = "disgusted"
    CONTEMPTUOUS = "contemptuous"
    EXCITED = "excited"
    CALM = "calm"


class ExportFormat(Enum):
    """Supported export formats"""

    FBX = "fbx"
    USD = "usd"
    GLTF = "gltf"
    GLB = "glb"
    OBJ = "obj"
    DAE = "dae"
    BLEND = "blend"
    MAX = "max"
    MAYA = "maya"


class ExportType(Enum):
    """Export type classifications"""

    STATIC_MESH = "static_mesh"
    RIGGED_CHARACTER = "rigged_character"
    ANIMATION = "animation"
    GAME_READY = "game_ready"
    ENVIRONMENT = "environment"
    PROP = "prop"
    VEHICLE = "vehicle"
    TEXTURE_ONLY = "texture_only"


class QualityLevel(Enum):
    """Quality levels for generation"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"
    CUSTOM = "custom"


@dataclass
class Vector3:
    """3D vector representation"""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_list(self) -> list[float]:
        return [self.x, self.y, self.z]

    def to_numpy(self) -> Any:
        # Import guard - np may be None if numpy not installed
        try:
            import numpy as np_module

            return np_module.array([self.x, self.y, self.z])
        except ImportError:
            return [self.x, self.y, self.z]


@dataclass
class Transform:
    """3D transformation"""

    position: Vector3 = field(default_factory=Vector3)
    rotation: Vector3 = field(default_factory=Vector3)
    scale: Vector3 = field(default_factory=lambda: Vector3(1.0, 1.0, 1.0))


@dataclass
class BoundingBox:
    """3D bounding box"""

    min_point: Vector3 = field(default_factory=Vector3)
    max_point: Vector3 = field(default_factory=Vector3)

    @property
    def center(self) -> Vector3:
        return Vector3(
            (self.min_point.x + self.max_point.x) / 2,
            (self.min_point.y + self.max_point.y) / 2,
            (self.min_point.z + self.max_point.z) / 2,
        )

    @property
    def size(self) -> Vector3:
        return Vector3(
            self.max_point.x - self.min_point.x,
            self.max_point.y - self.min_point.y,
            self.max_point.z - self.min_point.z,
        )


@dataclass
class Material:
    """Material properties"""

    name: str
    base_color: tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0)
    metallic: float = 0.0
    roughness: float = 0.5
    normal_map: str | None = None
    diffuse_map: str | None = None
    specular_map: str | None = None
    emission_map: str | None = None
    properties: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class Mesh:
    """3D mesh data"""

    name: str
    vertices: np.ndarray[Any, Any]
    faces: np.ndarray[Any, Any]
    normals: np.ndarray[Any, Any] | None = None
    uvs: np.ndarray[Any, Any] | None = None
    material: Material | None = None
    bounds: BoundingBox | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class Bone:
    """Skeletal bone definition"""

    name: str
    index: int
    parent_index: int = -1
    position: Vector3 = field(default_factory=Vector3)
    rotation: Vector3 = field(default_factory=Vector3)
    scale: Vector3 = field(default_factory=lambda: Vector3(1.0, 1.0, 1.0))
    children: list[int] = field(default_factory=list[Any])


@dataclass
class Skeleton:
    """Character skeleton structure"""

    bones: list[Bone]
    root_bone_index: int = 0
    bone_hierarchy: dict[str, list[str]] = field(default_factory=dict[str, Any])
    rest_pose: dict[str, Transform] = field(default_factory=dict[str, Any])

    def get_bone_by_name(self, name: str) -> Bone | None:
        for bone in self.bones:
            if bone.name == name:
                return bone
        return None


@dataclass
class AnimationKeyframe:
    """Single animation keyframe"""

    time: float
    transform: Transform
    interpolation: str = "linear"


@dataclass
class AnimationChannel:
    """Animation channel for a specific bone"""

    bone_name: str
    keyframes: list[AnimationKeyframe]
    property_type: str = "transform"


@dataclass
class Animation:
    """Character animation data"""

    name: str
    duration: float
    fps: float = 30.0
    channels: list[AnimationChannel] = field(default_factory=list[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class VoiceProfile:
    """Character voice characteristics"""

    voice_type: VoiceType
    pitch: float = 0.0
    speed: float = 1.0
    tone: str = "neutral"
    accent: str | None = None
    language: str = "en-US"
    emotion_modulation: bool = True
    sample_audio: str | None = None
    tts_model: str = "tortoise"
    voice_id: str | None = None


@dataclass
class PersonalityProfile:
    """Character personality definition"""

    traits: list[str]
    big_five: dict[str, float] = field(default_factory=dict[str, Any])
    values: list[str] = field(default_factory=list[Any])
    fears: list[str] = field(default_factory=list[Any])
    desires: list[str] = field(default_factory=list[Any])
    quirks: list[str] = field(default_factory=list[Any])
    social_style: str = "balanced"
    conflict_resolution: str = "diplomatic"
    decision_making: str = "analytical"
    motivations: list[str] = field(default_factory=list[Any])


@dataclass
class EmotionalProfile:
    """Character emotional characteristics"""

    base_mood: EmotionalState = EmotionalState.NEUTRAL
    emotional_range: float = 0.7
    mood_stability: float = 0.5
    triggers: dict[str, EmotionalState] = field(default_factory=dict[str, Any])
    emotional_intelligence: float = 0.6
    empathy_level: float = 0.7


@dataclass
class BackstoryElement:
    """Single element of character backstory"""

    event: str
    age: int | None = None
    impact: str = "medium"
    category: str = "general"
    details: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class Backstory:
    """Complete character backstory"""

    summary: str
    origin: str
    elements: list[BackstoryElement] = field(default_factory=list[Any])
    current_situation: str = ""
    goals: list[str] = field(default_factory=list[Any])
    motivations: list[str] = field(default_factory=list[Any])
    relationships: dict[str, str] = field(default_factory=dict[str, Any])


@dataclass
class ExportProfile:
    """Export profile for character assets"""

    export_type: ExportType
    supported_formats: list[str] = field(default_factory=list[Any])
    quality_settings: dict[str, Any] = field(default_factory=dict[str, Any])
    optimization_hints: dict[str, Any] = field(default_factory=dict[str, Any])
    target_platforms: list[str] = field(default_factory=list[Any])
    file_size_constraints: dict[str, Any] = field(default_factory=dict[str, Any])
    performance_requirements: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class GestureProfile:
    """Character gesture profile"""

    gesture_type: str
    frequency: float = 0.5
    intensity: float = 0.5
    contexts: list[str] = field(default_factory=list[Any])
    variations: list[str] = field(default_factory=list[Any])


@dataclass
class MotionProfile:
    """Character motion profile"""

    motion_type: str
    speed: float = 1.0
    fluidity: float = 0.7
    characteristics: list[str] = field(default_factory=list[Any])


@dataclass
class GaitProfile:
    """Character gait profile"""

    gait_type: str
    step_length: float = 0.7
    cadence: float = 1.0
    characteristics: list[str] = field(default_factory=list[Any])


@dataclass
class FacialProfile:
    """Character facial profile"""

    facial_type: str
    expressiveness: float = 0.7
    asymmetry: float = 0.1
    characteristics: list[str] = field(default_factory=list[Any])


@dataclass
class BackstoryProfile:
    """Character backstory profile"""

    narrative_type: str
    complexity: float = 0.6
    trauma_level: float = 0.3
    key_events: list[str] = field(default_factory=list[Any])


@dataclass
class MotivationProfile:
    """Character motivation profile"""

    motivation_type: str
    intensity: float = 0.7
    stability: float = 0.6
    drivers: list[str] = field(default_factory=list[Any])


class MoralAlignment(Enum):
    """D&D-style moral alignment system"""

    LAWFUL_GOOD = "lawful_good"
    NEUTRAL_GOOD = "neutral_good"
    CHAOTIC_GOOD = "chaotic_good"
    LAWFUL_NEUTRAL = "lawful_neutral"
    TRUE_NEUTRAL = "true_neutral"
    CHAOTIC_NEUTRAL = "chaotic_neutral"
    LAWFUL_EVIL = "lawful_evil"
    NEUTRAL_EVIL = "neutral_evil"
    CHAOTIC_EVIL = "chaotic_evil"


class GestureType(Enum):
    """Types of gestures"""

    EXPRESSIVE = "expressive"
    FUNCTIONAL = "functional"
    NERVOUS = "nervous"
    CULTURAL = "cultural"


class MotionType(Enum):
    """Types of motion"""

    FLUID = "fluid"
    ROBOTIC = "robotic"
    GRACEFUL = "graceful"
    AGGRESSIVE = "aggressive"


class GaitType(Enum):
    """Types of gait"""

    CONFIDENT = "confident"
    NERVOUS = "nervous"
    RELAXED = "relaxed"
    PURPOSEFUL = "purposeful"


class FacialType(Enum):
    """Types of facial expressions"""

    EXPRESSIVE = "expressive"
    STOIC = "stoic"
    ANIMATED = "animated"
    SUBTLE = "subtle"


class NarrativeType(Enum):
    """Types of narratives"""

    HEROIC = "heroic"
    TRAGIC = "tragic"
    COMEDIC = "comedic"
    DRAMATIC = "dramatic"


class MotivationType(Enum):
    """Types of motivation"""

    ACHIEVEMENT = "achievement"
    SURVIVAL = "survival"
    LOVE = "love"
    POWER = "power"
    KNOWLEDGE = "knowledge"


@dataclass
class GenerationConstraints:
    """Technical constraints for generation"""

    max_polygons: int = 50000
    max_texture_size: int = 2048
    max_bones: int = 100
    max_animations: int = 10
    target_platform: str = "desktop"
    file_size_limit_mb: float | None = None
    gpu_memory_limit_mb: float | None = None


@dataclass
class StylePreferences:
    """Visual style preferences"""

    primary_style: CharacterStyle = CharacterStyle.REALISTIC
    secondary_styles: list[CharacterStyle] = field(default_factory=list[Any])
    color_palette: list[tuple[int, int, int]] = field(default_factory=list[Any])
    material_style: str = "pbr"
    detail_level: str = "medium"
    artistic_references: list[str] = field(default_factory=list[Any])


@dataclass
class CharacterRequest:
    """Complete character generation request"""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    concept: str = ""
    style: StylePreferences = field(default_factory=StylePreferences)
    age: CharacterAge = CharacterAge.ADULT
    personality_brief: str | None = None
    backstory_brief: str | None = None
    reference_images: list[str] = field(default_factory=list[Any])
    constraints: GenerationConstraints = field(default_factory=GenerationConstraints)
    quality_level: QualityLevel = QualityLevel.HIGH
    export_formats: list[ExportFormat] = field(default_factory=list[Any])
    priority: int = 5
    deadline: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class GenerationResult:
    """Result from 3D generation module"""

    success: bool
    mesh_data: Mesh | None = None
    textures: dict[str, str] = field(default_factory=dict[str, Any])
    generation_time: float = 0.0
    quality_score: float = 0.0
    error: str | None = None
    warnings: list[str] = field(default_factory=list[Any])


@dataclass
class VoiceResult:
    """Result from voice synthesis module"""

    success: bool
    voice_profile: VoiceProfile | None = None
    sample_audio_path: str | None = None
    tts_model_config: dict[str, Any] = field(default_factory=dict[str, Any])
    generation_time: float = 0.0
    quality_score: float = 0.0
    error: str | None = None


@dataclass
class BehaviorResult:
    """Result from behavior/personality module"""

    success: bool
    personality: PersonalityProfile | None = None
    emotional_profile: EmotionalProfile | None = None
    decision_tree: dict[str, Any] | None = None
    behavior_scripts: dict[str, str] = field(default_factory=dict[str, Any])
    generation_time: float = 0.0
    consistency_score: float = 0.0
    error: str | None = None


@dataclass
class Character:
    """Complete character with all components"""

    character_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    id: str | None = None
    name: str = "Unnamed Character"
    concept: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    mesh: Mesh | None = None
    skeleton: Skeleton | None = None
    materials: list[Material] = field(default_factory=list[Any])
    textures: dict[str, str] = field(default_factory=dict[str, Any])
    animations: list[Animation] = field(default_factory=list[Any])
    default_animation: str | None = None
    voice_profile: VoiceProfile | None = None
    personality: Any | None = None
    emotional_profile: EmotionalProfile | None = None
    backstory: Backstory | None = None
    visual_design: dict[str, Any] | None = None
    style: CharacterStyle = CharacterStyle.REALISTIC
    age: CharacterAge = CharacterAge.ADULT
    tags: list[str] = field(default_factory=list[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    quality_scores: dict[str, float] = field(default_factory=dict[str, Any])
    generation_metrics: dict[str, Any] = field(default_factory=dict[str, Any])
    world_environment: dict[str, Any] = field(default_factory=dict[str, Any])

    def __post_init__(self) -> None:
        """Post-initialization processing"""
        if self.id and (not self.character_id):
            self.character_id = self.id
        elif self.character_id and (not self.id):
            self.id = self.character_id

    def to_dict(self) -> dict[str, Any]:
        """Convert character to dictionary"""
        data = asdict(self)
        data["concept"] = self.concept
        if isinstance(self.created_at, datetime):
            data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Character:
        """Create Character from dictionary"""
        character_data = {
            "character_id": data.get("character_id", str(uuid.uuid4())),
            "name": data.get("name", "Unnamed Character"),
            "concept": data.get("concept", ""),
        }
        optional_fields = [
            "id",
            "created_at",
            "mesh",
            "skeleton",
            "materials",
            "textures",
            "animations",
            "default_animation",
            "voice_profile",
            "personality",
            "emotional_profile",
            "backstory",
            "visual_design",
            "style",
            "gender",
            "age",
            "tags",
            "metadata",
            "quality_scores",
            "generation_metrics",
        ]
        for optional_field in optional_fields:
            if optional_field in data:
                character_data[optional_field] = data[optional_field]
        return cls(**character_data)

    def get_export_data(self, format: ExportFormat) -> dict[str, Any]:
        """Get data formatted for specific export format"""
        export_data: dict[str, Any] = {
            "character_id": self.character_id,
            "name": self.name,
            "format": format.value,
            "created_at": self.created_at.isoformat(),
        }
        if format in [ExportFormat.FBX, ExportFormat.USD, ExportFormat.GLTF]:
            export_data["mesh"] = self.mesh
            export_data["skeleton"] = self.skeleton
            export_data["animations"] = self.animations
            export_data["materials"] = self.materials
        return export_data


@dataclass
class QualityMetrics:
    """Quality measurements for generated character.

    Consolidates all quality scoring into a single canonical structure.
    Use `overall_score` as the primary quality metric.
    """

    completeness_score: float = 0.0
    consistency_score: float = 0.0
    creativity_score: float = 0.0
    technical_quality_score: float = 0.0
    overall_score: float = 0.0
    processing_time_ms: float = 0.0
    issues: list[str] = field(default_factory=list[Any])
    mesh_quality: float = 0.0
    texture_quality: float = 0.0
    rigging_quality: float = 0.0
    animation_quality: float = 0.0
    voice_quality: float = 0.0
    behavior_coherence: float = 0.0
    details: dict[str, Any] = field(default_factory=dict[str, Any])
    warnings: list[str] = field(default_factory=list[Any])
    suggestions: list[str] = field(default_factory=list[Any])


@dataclass
class PerformanceMetrics:
    """Performance measurements for generation pipeline"""

    total_time: float = 0.0
    module_times: dict[str, float] = field(default_factory=dict[str, Any])
    memory_usage_mb: float = 0.0
    peak_memory_mb: float = 0.0
    gpu_usage_percent: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    parallel_efficiency: float = 0.0

    def get_bottleneck(self) -> str | None:
        """Identify performance bottleneck"""
        if not self.module_times:
            return None
        return max(self.module_times.items(), key=lambda x: x[1])[0]


@dataclass
class PipelineStage:
    """Single stage in the generation pipeline"""

    name: str
    status: str = "pending"
    progress: float = 0.0
    start_time: datetime | None = None
    end_time: datetime | None = None
    result: Any | None = None
    error: str | None = None

    @property
    def duration(self) -> float | None:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


@dataclass
class AssetReference:
    """Reference to an external asset file"""

    asset_type: str
    file_path: Path
    format: str
    size_bytes: int
    checksum: str
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class ColorPalette:
    """Color palette specification"""

    primary: str
    secondary: str
    accent: str
    background: str = "#FFFFFF"
    text: str = "#000000"
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class StyleGuide:
    """Style guide for character design"""

    style_name: str
    description: str
    art_style: str
    rendering_style: str
    color_palette: ColorPalette
    themes: list[str] = field(default_factory=list[Any])
    reference_images: list[str] = field(default_factory=list[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class VisualProfile:
    """Complete visual profile for character"""

    character_name: str
    physical_description: str
    style_guide: StyleGuide
    proportions: dict[str, float] = field(default_factory=dict[str, Any])
    distinguishing_features: list[str] = field(default_factory=list[Any])
    clothing_style: str = ""
    accessories: list[str] = field(default_factory=list[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
