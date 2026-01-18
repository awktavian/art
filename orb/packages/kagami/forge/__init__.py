"""K OS Forge Module - Character Generation Pipeline.

Forge is the implementation colony (e₂, Cusp A₃ catastrophe) responsible for
building, coding, and decision execution. This module provides:

- Character generation from text concepts (text-to-3D)
- Image-to-character conversion
- Animation generation (facial, gesture, motion)
- Quality validation and safety gates
- Multi-format export (FBX, GLTF, USD, etc.)

ARCHITECTURE (Dec 4, 2025):
==========================
                    ForgeService (unified entry point)
                          │
                    ForgeMatrix (orchestrator)
                          │
    ┌─────────┬──────────┼──────────┬─────────┐
    │         │          │          │         │
  Visual   Behavior    Voice    Rigging    Export
  Design   (AI)       (TTS)    (UniRig)   (multi-format)

COLONY INTEGRATION:
==================
Forge (e₂) coordinates with:
- Spark (e₁) for creative ideation
- Crystal (e₇) for quality verification
- Nexus (e₄) for memory integration

Usage:
    from kagami.forge import (
        ForgeService,
        ForgeOperation,
        ForgeRequest,
        ForgeResponse,
        get_forge_service,
    )

    service = get_forge_service()
    result = await service.generate_character(
        concept="warrior princess",
        quality_mode="draft",
    )
"""

from __future__ import annotations

# Integration types
from kagami.forge.core_integration import (
    BaseComponent,
    CharacterGenerationContext,
    CharacterResult,
    ForgeComponent,
    ForgeLLMAdapter,
    ProcessingStatus,
)
from kagami.forge.creator_api import (
    generate_genesis_video,
    parse_genesis_video_spec,
)

# Exceptions
from kagami.forge.exceptions import (
    AnimationError,
    ExportError,
    ForgeError,
    GenerationError,
    GenerationTimeoutError,
    ModuleInitializationError,
    ModuleNotAvailableError,
    NarrativeGenerationError,
    PersonalityGenerationError,
    RiggingError,
    ValidationError,
    VisualGenerationError,
    VoiceGenerationError,
)

# Core components
from kagami.forge.forge_llm_base import (
    CharacterAspect,
    CharacterContext,
    ForgeLLMBase,
    LLMRequest,
    LLMResponse,
    ReasoningStrategy,
)

# Middleware decorator
from kagami.forge.forge_middleware import forge_operation

# LLM service adapter
from kagami.forge.llm_service_adapter import KagamiOSLLMServiceAdapter

# Matrix orchestrator
from kagami.forge.matrix import (
    ForgeMatrix,
    get_forge_matrix,
)

# Multi-Colony Conversation System
from kagami.forge.modules.conversation import (
    ColonyPersonality,
    ColonyRoomAffinity,
    ConversationAudioRouter,
    ConversationState,
    ConversationTurn,
    EmotionType,
    ForgeConversationManager,
    RealtimeRoomStreamer,
    RoomProfile,
    SmartHomeRoomMapper,
    get_colony_personality,
    get_colony_response_pattern,
)

# Rooms export (Forge → Rooms integration)
from kagami.forge.rooms_export import ForgeRoomsExporter
from kagami.forge.safety import SafetyGate, get_safety_gate

# Schema types
from kagami.forge.schema import (
    Character,
    CharacterRequest,
    ExportFormat,
    QualityLevel,
    QualityMetrics,
)

# Service layer (primary interface)
from kagami.forge.service import (
    ForgeOperation,
    ForgeRequest,
    ForgeResponse,
    ForgeService,
    get_forge_service,
)

# Shared context
from kagami.forge.shared_context import (
    FlexibleReasoningGenerator,
    SharedContext,
)

# Streaming support
from kagami.forge.streaming import (
    GenerationStage,
    ProgressUpdate,
    StreamingGenerator,
    get_streaming_generator,
)

# Validation and safety
from kagami.forge.validation import ForgeValidator, get_validator

# Colony integration (optional - may not be available in all contexts)
try:
    from kagami.forge.colony_integration import (
        FORGE_CATASTROPHE,
        FORGE_COLONY_INDEX,
        FORGE_COLOR,
        CuspActivation,
        ForgeColonyBridge,
        ForgeColonyState,
        OptimalForge,
        get_forge_colony_bridge,
        get_optimal_forge,
    )

    _HAS_COLONY_INTEGRATION = True
except ImportError:
    _HAS_COLONY_INTEGRATION = False
    # Define stubs for __all__
    ForgeColonyBridge = None  # type: ignore
    ForgeColonyState = None  # type: ignore
    OptimalForge = None  # type: ignore
    CuspActivation = None  # type: ignore
    get_forge_colony_bridge = None  # type: ignore
    get_optimal_forge = None  # type: ignore
    FORGE_COLONY_INDEX = 1
    FORGE_COLOR = "#FF4444"
    FORGE_CATASTROPHE = "cusp_a3"

__all__ = [
    "FORGE_CATASTROPHE",
    "FORGE_COLONY_INDEX",
    "FORGE_COLOR",
    # Exceptions
    "AnimationError",
    # Integration
    "BaseComponent",
    # Schema
    "Character",
    # LLM base
    "CharacterAspect",
    "CharacterContext",
    "CharacterGenerationContext",
    "CharacterRequest",
    "CharacterResult",
    # Multi-Colony Conversation System
    "ColonyPersonality",
    "ColonyRoomAffinity",
    "ConversationAudioRouter",
    "ConversationState",
    "ConversationTurn",
    "CuspActivation",
    "EmotionType",
    "ExportError",
    "ExportFormat",
    "FlexibleReasoningGenerator",
    # Colony integration
    "ForgeColonyBridge",
    "ForgeColonyState",
    "ForgeComponent",
    # Conversation System
    "ForgeConversationManager",
    "ForgeError",
    "ForgeLLMAdapter",
    "ForgeLLMBase",
    # Matrix
    "ForgeMatrix",
    # Service layer
    "ForgeOperation",
    "ForgeRequest",
    "ForgeResponse",
    # Rooms export
    "ForgeRoomsExporter",
    "ForgeService",
    # Validation/Safety
    "ForgeValidator",
    "GenerationError",
    # Streaming
    "GenerationStage",
    "GenerationTimeoutError",
    # LLM adapter
    "KagamiOSLLMServiceAdapter",
    "LLMRequest",
    "LLMResponse",
    "ModuleInitializationError",
    "ModuleNotAvailableError",
    "NarrativeGenerationError",
    "OptimalForge",
    "PersonalityGenerationError",
    "ProcessingStatus",
    "ProgressUpdate",
    "QualityLevel",
    "QualityMetrics",
    # Real-time Room Streaming & Smart Home Integration
    "RealtimeRoomStreamer",
    "ReasoningStrategy",
    "RiggingError",
    "RoomProfile",
    "SafetyGate",
    # Context
    "SharedContext",
    # Smart Home Integration
    "SmartHomeRoomMapper",
    "StreamingGenerator",
    "ValidationError",
    "VisualGenerationError",
    "VoiceGenerationError",
    # Middleware
    "forge_operation",
    "generate_genesis_video",
    # Character & Colony Functions
    "get_colony_personality",
    "get_colony_response_pattern",
    "get_forge_colony_bridge",
    "get_forge_matrix",
    "get_forge_service",
    "get_optimal_forge",
    "get_safety_gate",
    "get_streaming_generator",
    "get_validator",
    # Creator API (Genesis)
    "parse_genesis_video_spec",
]
