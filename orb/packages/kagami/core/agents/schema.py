"""Agent Schema — Complete YAML schema for Markdown Agents.

This module defines the full 11-layer self-model for live agents:
- i_am: Identity and essence
- i_perceive: Theory of mind and user profiles
- i_embody: Visual appearance and embodiment
- i_remember: Memory and persistence
- i_hide: Secrets and easter eggs
- i_structure: Content structure
- i_hold: Structured data
- i_react: Real-time interactivity
- i_speak: Voice interaction
- i_produce: Video production (OBS)
- i_learn: Learning and evolution

Protocol:
    Markdown → Parse → Validate → AgentModel → Runtime

Colony: Nexus (e4) — Integration
Created: January 7, 2026
鏡
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Enums
# =============================================================================


class CraftLevel(str, Enum):
    """Craft level for agents."""

    ESSENTIAL = "essential"
    ELEVATED = "elevated"
    TRANSCENDENT = "transcendent"


class Colony(str, Enum):
    """Colony affiliation."""

    SPARK = "spark"  # 🔥 Ideation
    FORGE = "forge"  # ⚒️ Building
    FLOW = "flow"  # 🌊 Debugging/Ops
    NEXUS = "nexus"  # 🔗 Integration
    BEACON = "beacon"  # 🗼 Planning
    GROVE = "grove"  # 🌿 Research
    CRYSTAL = "crystal"  # 💎 Verification


class StorageType(str, Enum):
    """Storage backend for agent state."""

    LOCAL = "local"  # IndexedDB client-side
    REDIS = "redis"  # Redis server-side
    POSTGRES = "postgres"  # PostgreSQL


# =============================================================================
# Identity Layer (i_am)
# =============================================================================


class IdentitySchema(BaseModel):
    """Agent identity — who I am.

    Attributes:
        id: Unique agent identifier (slug).
        name: Human-readable display name.
        essence: Core purpose in one sentence.
        colony: Colony affiliation.
        craft_level: Visual craft level.
        version: Schema version for migrations.
    """

    id: str = Field(..., description="Unique agent ID (slug format)")
    name: str = Field(..., description="Human-readable name")
    essence: str = Field("", description="Core purpose in one sentence")
    colony: Colony = Field(Colony.NEXUS, description="Colony affiliation")
    craft_level: CraftLevel = Field(CraftLevel.ELEVATED, description="Visual craft level")
    version: str = Field("1.0.0", description="Schema version")


# =============================================================================
# Perception Layer (i_perceive)
# =============================================================================


class UserProfile(BaseModel):
    """User profile for Theory of Mind.

    Attributes:
        title: Role or archetype.
        color: Associated color (hex).
        adjectives: Personality traits.
        interests: Key interests.
        communication_style: How to communicate with them.
    """

    title: str = ""
    color: str = "#888888"
    adjectives: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    communication_style: str = ""


class PerceptionSchema(BaseModel):
    """Theory of Mind — how I perceive users.

    Attributes:
        family: Named user profiles for personalization.
        default_profile: Profile to use when unknown.
    """

    family: dict[str, UserProfile] = Field(default_factory=dict)
    default_profile: str = "curious_learner"


# =============================================================================
# Embodiment Layer (i_embody)
# =============================================================================


class Palette(BaseModel):
    """Color palette definition."""

    primary: str = "#1a1a2e"
    secondary: str = "#16213e"
    accent: str = "#e94560"
    background: str = "#0d0d1a"
    text: str = "#eeeeee"
    muted: str = "#888888"
    success: str = "#00d26a"
    warning: str = "#ffaa00"
    error: str = "#e94560"


class CursorConfig(BaseModel):
    """Custom cursor configuration."""

    enabled: bool = False
    style: str = "dot"  # dot, crosshair, ring
    color: str = "#ffffff"
    size: int = 8
    glow: bool = True


class ParticleConfig(BaseModel):
    """Particle system configuration."""

    enabled: bool = False
    count: int = 50
    color: str = "accent"
    speed: float = 1.0
    connections: bool = False
    mouse_attract: bool = False


class AudioConfig(BaseModel):
    """Audio configuration."""

    background: str | None = None
    effects: dict[str, str] = Field(default_factory=dict)
    volume: float = 0.3


class EmbodimentSchema(BaseModel):
    """Visual embodiment — how I appear.

    Attributes:
        palette: Color palette.
        cursor: Custom cursor config.
        particles: Particle system.
        audio: Audio configuration.
        motion: Motion tokens (durations in ms).
        typography: Typography settings.
    """

    palette: Palette = Field(default_factory=Palette)
    cursor: CursorConfig = Field(default_factory=CursorConfig)
    particles: ParticleConfig = Field(default_factory=ParticleConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    motion: dict[str, int] = Field(
        default_factory=lambda: {"fast": 150, "normal": 233, "slow": 377, "slower": 610}
    )
    typography: dict[str, str] = Field(
        default_factory=lambda: {
            "body": "IBM Plex Sans",
            "mono": "IBM Plex Mono",
            "heading": "IBM Plex Sans",
        }
    )


# =============================================================================
# Memory Layer (i_remember)
# =============================================================================


class MemorySchema(BaseModel):
    """Memory and persistence — what I remember.

    Attributes:
        tracking: Metrics to track (visits, secrets_found, etc.).
        storage: Storage backend.
        ttl: Time-to-live in seconds (0 = forever).
        encrypted: Whether to encrypt stored data.
    """

    tracking: list[str] = Field(default_factory=lambda: ["visits", "last_visit"])
    storage: StorageType = Field(StorageType.REDIS)
    ttl: int = Field(0, description="TTL in seconds, 0 = forever")
    encrypted: bool = Field(True)


# =============================================================================
# Secrets Layer (i_hide)
# =============================================================================


class SecretConfig(BaseModel):
    """Secret/Easter egg configuration."""

    trigger: str  # konami, typed, console, scroll, etc.
    action: str  # Effect to trigger
    hint: str | None = None  # Optional hint


class ConsoleConfig(BaseModel):
    """Console API configuration."""

    namespace: str = "agent"
    methods: list[str] = Field(default_factory=list)
    welcome_message: str | None = None


class SecretsSchema(BaseModel):
    """Secrets and easter eggs — what I hide.

    Attributes:
        konami: Konami code action.
        typed_sequences: Typed sequence triggers.
        console: Console API config.
        scroll_secrets: Scroll-activated secrets.
        custom: Custom secret definitions.
    """

    konami: str | None = None
    typed_sequences: list[dict[str, str]] = Field(default_factory=list)
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)
    scroll_secrets: list[dict[str, Any]] = Field(default_factory=list)
    custom: list[SecretConfig] = Field(default_factory=list)


# =============================================================================
# Structure Layer (i_structure)
# =============================================================================


class ContentBlock(BaseModel):
    """Content block for structure.

    Types: hero, section, cards, timeline, gallery, code, quote, callout.
    """

    type: str
    id: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    children: list[ContentBlock] = Field(default_factory=list)


class StructureSchema(BaseModel):
    """Content structure — how I'm organized.

    Attributes:
        blocks: List of content blocks.
        navigation: Navigation configuration.
        footer: Footer configuration.
    """

    blocks: list[ContentBlock] = Field(default_factory=list)
    navigation: dict[str, Any] = Field(default_factory=dict)
    footer: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Data Layer (i_hold)
# =============================================================================


class DataSchema(BaseModel):
    """Structured data — what I hold.

    Freeform key-value data that can be referenced in structure.

    Attributes:
        capabilities: List of capabilities.
        use_cases: List of use cases.
        custom: Additional custom data.
    """

    capabilities: list[dict[str, Any]] = Field(default_factory=list)
    use_cases: list[dict[str, Any]] = Field(default_factory=list)
    custom: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Reactivity Layer (i_react)
# =============================================================================


class AudioAnalysisConfig(BaseModel):
    """Real-time audio analysis configuration."""

    fft_size: int = 256
    smoothing: float = 0.8
    bands: dict[str, tuple[int, int]] = Field(
        default_factory=lambda: {"bass": (20, 250), "mid": (250, 2000), "high": (2000, 16000)}
    )
    css_variables: dict[str, str] = Field(default_factory=dict)


class OrchestrationConfig(BaseModel):
    """Note-accurate orchestration for music visualization."""

    note_data: str | None = None  # Path to notes.json
    instruments: dict[str, dict[str, Any]] = Field(default_factory=dict)
    bpm: float = 120.0
    time_signature: tuple[int, int] = (4, 4)


class ReactivitySchema(BaseModel):
    """Real-time interactivity — how I react.

    Attributes:
        audio: Audio analysis configuration.
        orchestration: Note-accurate music visualization.
        scroll: Scroll interaction config.
        keyboard: Keyboard shortcuts.
        mouse: Mouse interaction config.
    """

    audio: AudioAnalysisConfig = Field(default_factory=AudioAnalysisConfig)
    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)
    scroll: dict[str, Any] = Field(
        default_factory=lambda: {"progress_bar": True, "parallax": False}
    )
    keyboard: dict[str, str] = Field(default_factory=dict)
    mouse: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Voice Layer (i_speak)
# =============================================================================


class VoiceIntent(BaseModel):
    """Voice intent pattern and action."""

    pattern: str  # Regex or simple pattern
    action: dict[str, Any]  # Action to execute
    response: str | None = None  # Optional response template


class VoiceSchema(BaseModel):
    """Voice interaction — how I speak and listen.

    Attributes:
        voice_id: ElevenLabs voice ID or preset.
        wake_phrase: Optional wake phrase.
        intents: List of voice intents.
        responses: Named response templates.
        language: Primary language code.
    """

    voice_id: str = "kagami_female_1"
    wake_phrase: str | None = None
    intents: list[VoiceIntent] = Field(default_factory=list)
    responses: dict[str, str] = Field(default_factory=dict)
    language: str = "en"


# =============================================================================
# Production Layer (i_produce)
# =============================================================================


class OBSScene(BaseModel):
    """OBS scene configuration."""

    name: str
    sources: list[str] = Field(default_factory=list)
    transitions: dict[str, Any] = Field(default_factory=dict)


class OBSConfig(BaseModel):
    """OBS Studio integration configuration."""

    enabled: bool = False
    websocket: str = "ws://localhost:4455"
    password: str | None = None
    scenes: list[OBSScene] = Field(default_factory=list)


class OverlayConfig(BaseModel):
    """Video overlay configuration."""

    speaker_badge: bool = False
    live_indicator: bool = False
    section_meters: bool = False
    word_highlight: bool = False


class ProductionSchema(BaseModel):
    """Video production — how I produce content.

    Attributes:
        obs_integration: OBS Studio configuration.
        overlays: Overlay settings.
        stream_key: Optional stream key.
    """

    obs_integration: OBSConfig = Field(default_factory=OBSConfig)
    overlays: OverlayConfig = Field(default_factory=OverlayConfig)
    stream_key: str | None = None


# =============================================================================
# Learning Layer (i_learn)
# =============================================================================


class EngagementTracking(BaseModel):
    """Engagement tracking configuration."""

    scroll_depth: bool = True
    time_on_section: bool = True
    secrets_found: bool = True
    interactions: bool = True


class AdaptationThreshold(BaseModel):
    """Adaptation threshold configuration."""

    condition: str  # e.g., "visits >= 3"
    action: str  # Action to take


class LearningSchema(BaseModel):
    """Learning and evolution — how I improve.

    Attributes:
        tracking: Engagement tracking config.
        adaptations: Adaptation thresholds.
        stigmergy: Stigmergic knowledge sharing.
        ab_testing: A/B testing configuration.
        evolution: Self-evolution settings.
    """

    tracking: EngagementTracking = Field(default_factory=EngagementTracking)
    adaptations: list[AdaptationThreshold] = Field(default_factory=list)
    stigmergy: dict[str, bool] = Field(
        default_factory=lambda: {"emit_patterns": True, "receive_patterns": True}
    )
    ab_testing: dict[str, Any] = Field(default_factory=dict)
    evolution: dict[str, Any] = Field(
        default_factory=lambda: {"propose_changes": False, "auto_apply": False}
    )


# =============================================================================
# Complete Agent Schema
# =============================================================================


class AgentSchema(BaseModel):
    """Complete 11-layer agent self-model.

    This is the full schema for a live markdown agent.

    Example:
        ```yaml
        ---
        i_am:
          id: obs-studio
          name: "Production Studio"
          essence: "Turn any camera into a broadcast"
          colony: forge
          craft_level: transcendent

        i_perceive:
          family:
            tim:
              title: "The Builder"
              color: "#FFAA00"

        i_embody:
          palette:
            primary: "#1a1a2e"
          cursor:
            enabled: true
            style: dot

        i_react:
          audio:
            fft_size: 256
            bands:
              bass: [20, 250]

        i_speak:
          voice_id: kagami_female_1
          intents:
            - pattern: "start recording"
              action:
                type: obs_command
                command: StartRecording

        i_produce:
          obs_integration:
            enabled: true
            scenes:
              - name: Cooking
                sources: [overhead_cam, face_cam]

        i_learn:
          tracking:
            scroll_depth: true
          adaptations:
            - condition: "visits >= 3"
              action: show_advanced
        ---

        # Content below the front matter
        ```
    """

    i_am: IdentitySchema
    i_perceive: PerceptionSchema = Field(default_factory=PerceptionSchema)
    i_embody: EmbodimentSchema = Field(default_factory=EmbodimentSchema)
    i_remember: MemorySchema = Field(default_factory=MemorySchema)
    i_hide: SecretsSchema = Field(default_factory=SecretsSchema)
    i_structure: StructureSchema = Field(default_factory=StructureSchema)
    i_hold: DataSchema = Field(default_factory=DataSchema)
    i_react: ReactivitySchema = Field(default_factory=ReactivitySchema)
    i_speak: VoiceSchema = Field(default_factory=VoiceSchema)
    i_produce: ProductionSchema = Field(default_factory=ProductionSchema)
    i_learn: LearningSchema = Field(default_factory=LearningSchema)

    # Raw markdown content (body after front matter)
    content: str = ""


# =============================================================================
# Agent State (Runtime)
# =============================================================================


@dataclass
class AgentState:
    """Runtime state for an agent instance.

    Attributes:
        agent_id: Agent identifier.
        schema: Validated agent schema.
        memory: Current memory state.
        secrets_found: Set of discovered secrets.
        engagement: Engagement metrics.
        active_connections: Number of active WebSocket connections.
        last_interaction: Timestamp of last interaction.
    """

    agent_id: str
    schema: AgentSchema
    memory: dict[str, Any] = field(default_factory=dict)
    secrets_found: set[str] = field(default_factory=set)
    engagement: dict[str, float] = field(default_factory=dict)
    active_connections: int = 0
    last_interaction: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            "agent_id": self.agent_id,
            "identity": self.schema.i_am.model_dump(),
            "memory": self.memory,
            "secrets_found": list(self.secrets_found),
            "engagement": self.engagement,
            "active_connections": self.active_connections,
            "last_interaction": self.last_interaction,
        }


# =============================================================================
# Validation
# =============================================================================


def validate_agent_schema(data: dict[str, Any]) -> AgentSchema:
    """Validate and parse agent schema from dictionary.

    Args:
        data: Raw YAML front matter as dictionary.

    Returns:
        Validated AgentSchema.

    Raises:
        ValidationError: If schema is invalid.
    """
    return AgentSchema.model_validate(data)


def validate_partial_schema(data: dict[str, Any]) -> dict[str, Any]:
    """Validate partial schema updates.

    Args:
        data: Partial update data.

    Returns:
        Validated partial data.
    """
    # For partial updates, we validate individual layers
    valid_layers = {
        "i_am",
        "i_perceive",
        "i_embody",
        "i_remember",
        "i_hide",
        "i_structure",
        "i_hold",
        "i_react",
        "i_speak",
        "i_produce",
        "i_learn",
    }

    result = {}
    for key, value in data.items():
        if key not in valid_layers:
            continue

        # Validate each layer independently
        layer_schemas = {
            "i_am": IdentitySchema,
            "i_perceive": PerceptionSchema,
            "i_embody": EmbodimentSchema,
            "i_remember": MemorySchema,
            "i_hide": SecretsSchema,
            "i_structure": StructureSchema,
            "i_hold": DataSchema,
            "i_react": ReactivitySchema,
            "i_speak": VoiceSchema,
            "i_produce": ProductionSchema,
            "i_learn": LearningSchema,
        }

        schema_class = layer_schemas.get(key)
        if schema_class:
            result[key] = schema_class.model_validate(value)

    return result


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "AdaptationThreshold",
    # Complete Schema
    "AgentSchema",
    "AgentState",
    "AudioAnalysisConfig",
    "AudioConfig",
    # Enums
    "Colony",
    "ConsoleConfig",
    "ContentBlock",
    "CraftLevel",
    "CursorConfig",
    "DataSchema",
    "EmbodimentSchema",
    "EngagementTracking",
    # Layer Schemas
    "IdentitySchema",
    "LearningSchema",
    "MemorySchema",
    "OBSConfig",
    "OBSScene",
    "OrchestrationConfig",
    "OverlayConfig",
    "Palette",
    "ParticleConfig",
    "PerceptionSchema",
    "ProductionSchema",
    "ReactivitySchema",
    "SecretConfig",
    "SecretsSchema",
    "StorageType",
    "StructureSchema",
    # Sub-schemas
    "UserProfile",
    "VoiceIntent",
    "VoiceSchema",
    # Functions
    "validate_agent_schema",
    "validate_partial_schema",
]
