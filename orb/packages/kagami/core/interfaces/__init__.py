"""K OS Interfaces — Unified Type Definitions and Protocols.

CONSOLIDATION (December 8, 2025):
================================
This module consolidates 16 interface files into a single source of truth.
All types, protocols, and DTOs are now defined here.

Categories:
- Common Types: Basic type aliases used everywhere
- API Events: Broadcasting protocols
- Audio Types: STT/TTS protocols
- Chaos Types: Attractor and safety types
- Composio: Integration interface
- Database Types: DB protocols and metadata
- Forge Types: Generation service types
- Introspection: Self-analysis types
- Learning: Learning system protocols
- Privacy: Privacy and encryption protocols
- Receipts: Receipt emission interface
- Scheduling: Job scheduling types
- Service: Base service protocols
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from kagami.forge.schema import CharacterRequest

# =============================================================================
# COMMON TYPES
# =============================================================================

ConfigDict: TypeAlias = dict[str, Any]
MetadataDict: TypeAlias = dict[str, Any]
ResultDict: TypeAlias = dict[str, Any]
ParamsDict: TypeAlias = dict[str, Any]
HeadersDict: TypeAlias = dict[str, str]

# Type variables
T = TypeVar("T")
ModelT = TypeVar("ModelT")


# =============================================================================
# API EVENTS
# =============================================================================


@runtime_checkable
class EventBroadcaster(Protocol):
    """Protocol for broadcasting realtime events."""

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event payload."""
        ...


@runtime_checkable
class RealtimeBroadcaster(EventBroadcaster, Protocol):
    """Protocol for targeted realtime events (supporting rooms)."""

    async def emit(
        self,
        event: str,
        data: Any,
        room: str | None = None,
        skip_sid: str | None = None,
        namespace: str | None = None,
        callback: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Emit an event to a specific room or globally."""
        ...


# =============================================================================
# AUDIO TYPES
# =============================================================================


class STTProviderProtocol(Protocol):
    """Speech-to-text provider contract."""

    name: str

    async def initialize(self) -> None: ...

    async def start_session(
        self,
        session_id: str,
        sample_rate: int = 16000,
        channels: int = 1,
        fmt: str = "pcm16",
        language: str | None = None,
        **kwargs: Any,
    ) -> Any: ...

    async def accept_chunk(self, session: Any, audio_bytes: bytes) -> None: ...

    async def finalize(self, session: Any) -> str: ...


class TTSProviderProtocol(Protocol):
    """Text-to-speech provider contract."""

    async def initialize(self) -> None: ...

    async def synthesize(self, text: str, voice_profile: Any, stream: bool = False) -> Any: ...


class AudioServiceProtocol(Protocol):
    """Unified audio pipeline contract."""

    async def initialize(self) -> None: ...

    async def speech_to_text(self, audio_input: Any) -> str: ...

    async def text_to_speech(self, audio_output: Any) -> bytes: ...


# =============================================================================
# CHAOS TYPES
# =============================================================================


@dataclass
class AttractorConfig:
    """Configuration for a chaotic attractor."""

    name: str
    parameters: dict[str, float]
    dimensions: int
    initial_state: list[float]


@dataclass
class ChaosParams:
    """Parameters for chaos engine generation."""

    temperature: float = 1.0
    breadth_k: int = 3
    analogy_density: str = "low"
    novelty_target: float = 0.2
    diversity_penalty: float = 0.2


@dataclass
class ChaosSafetyResult:
    """Result of a chaos safety check."""

    safe: bool
    cbf_value: float | None = None
    intervention_needed: bool = False
    distance_from_boundary: float | None = None
    message: str | None = None
    error: str | None = None


@dataclass
class ChaosSafetyMetrics:
    """Metrics for chaos safety monitoring."""

    total_interventions: int = 0
    violations_prevented: int = 0
    intervention_rate: float = 0.0
    last_intervention_at: float = 0.0


# =============================================================================
# COMPOSIO INTERFACE
# =============================================================================


class IComposioService(ABC):
    """Interface for Composio service."""

    @property
    @abstractmethod
    def initialized(self) -> bool:
        """Check if service is initialized."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service."""

    @abstractmethod
    async def execute_action(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a Composio action."""


# =============================================================================
# DATABASE TYPES
# =============================================================================


@runtime_checkable
class DatabaseConfig(Protocol):
    """Protocol for database configuration."""

    connection_string: str
    pool_size: int
    max_overflow: int
    pool_timeout: float


@runtime_checkable
class DatabaseProvider(Protocol):
    """Protocol for database access providers."""

    async def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a query and return results."""
        ...

    async def fetch_one(
        self, query: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Fetch a single row."""
        ...

    async def fetch_all(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all rows."""
        ...

    async def transaction(self) -> Any:
        """Start a database transaction."""
        ...


@runtime_checkable
class Repository(Protocol[ModelT]):
    """Generic repository protocol."""

    async def get(self, id: Any) -> ModelT | None:
        """Get entity by ID."""
        ...

    async def create(self, entity: ModelT) -> ModelT:
        """Create new entity."""
        ...

    async def update(self, entity: ModelT) -> ModelT:
        """Update existing entity."""
        ...

    async def delete(self, id: Any) -> bool:
        """Delete entity by ID."""
        ...


class DatabaseMetadata:
    """Metadata about database state (pure data)."""

    def __init__(
        self,
        connection_count: int = 0,
        active_transactions: int = 0,
        last_query_time: datetime | None = None,
        metadata: MetadataDict | None = None,
    ):
        self.connection_count = connection_count
        self.active_transactions = active_transactions
        self.last_query_time = last_query_time
        self.metadata = metadata or {}


# =============================================================================
# FORGE TYPES
# =============================================================================


class ForgeCapability(str, Enum):
    """Forge service capabilities."""

    TEXT_GENERATION = "text_generation"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    AUDIO_GENERATION = "audio_generation"
    CODE_GENERATION = "code_generation"
    MOTION_GENERATION = "motion_generation"
    PHYSICS_SIMULATION = "physics_simulation"


class ForgeStatus(str, Enum):
    """Forge operation status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@runtime_checkable
class ForgeProvider(Protocol):
    """Protocol for Forge service providers."""

    async def generate(
        self,
        capability: ForgeCapability,
        params: ParamsDict,
        config: ConfigDict | None = None,
    ) -> dict[str, Any]:
        """Generate content using specified capability."""
        ...

    async def get_status(self, job_id: str) -> ForgeStatus:
        """Get status of a forge job."""
        ...

    async def cancel(self, job_id: str) -> bool:
        """Cancel a running forge job."""
        ...

    def get_supported_capabilities(self) -> list[ForgeCapability]:
        """Get list[Any] of supported capabilities."""
        ...


@runtime_checkable
class ForgeUtility(Protocol):
    """Protocol for Forge utility operations."""

    def validate_params(self, capability: ForgeCapability, params: ParamsDict) -> bool:
        """Validate parameters for a capability."""
        ...

    def estimate_cost(self, capability: ForgeCapability, params: ParamsDict) -> float:
        """Estimate computational cost."""
        ...

    def estimate_duration(self, capability: ForgeCapability, params: ParamsDict) -> float:
        """Estimate duration in seconds."""
        ...


class ForgeMetadata:
    """Metadata about forge operations (pure data)."""

    def __init__(
        self,
        job_id: str | None = None,
        capability: ForgeCapability | None = None,
        status: ForgeStatus = ForgeStatus.PENDING,
        cost: float = 0.0,
        duration_seconds: float = 0.0,
        metadata: MetadataDict | None = None,
    ):
        self.job_id = job_id
        self.capability = capability
        self.status = status
        self.cost = cost
        self.duration_seconds = duration_seconds
        self.metadata = metadata or {}


# =============================================================================
# FORGE DTOs
# =============================================================================


@dataclass
class VisualDesignRequestDTO:
    """Minimal request surface required by visual design modules."""

    request_id: str
    concept: str
    personality_brief: str | None
    backstory_brief: str | None
    export_formats: list[str] = field(default_factory=list[Any])
    quality_mode: str = "preview"
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    @classmethod
    def from_character_request(cls, request: CharacterRequest) -> VisualDesignRequestDTO:
        """Create DTO from the rich CharacterRequest dataclass."""
        quality_mode = getattr(getattr(request, "quality_level", None), "value", "preview")
        export_formats = [
            getattr(fmt, "value", str(fmt)) for fmt in getattr(request, "export_formats", [])
        ]

        return cls(
            request_id=getattr(request, "request_id", ""),
            concept=getattr(request, "concept", ""),
            personality_brief=getattr(request, "personality_brief", None),
            backstory_brief=getattr(request, "backstory_brief", None),
            export_formats=export_formats,
            quality_mode=str(quality_mode or "preview"),
            metadata=dict(getattr(request, "metadata", {}) or {}),
        )


@dataclass
class ForgeJobDTO:
    """Forge job status representation for API responses."""

    job_id: str
    status: str  # pending|running|completed|failed|cancelled
    progress_percent: float = 0.0
    capability: str = ""
    created_at: str = ""
    updated_at: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "capability": self.capability,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


# =============================================================================
# INTROSPECTION TYPES
# =============================================================================


@dataclass
class ReasoningTrace:
    """Minimal reasoning trace summary."""

    steps: list[dict[str, Any]]
    conclusion: str
    confidence: float
    alternative_paths: list[str]


@dataclass
class SelfExplanation:
    """Explanation of an internal decision."""

    decision: str
    reasoning_chain: list[str]
    key_factors: list[tuple[str, float]]
    confidence: float
    uncertainties: list[str]


@dataclass
class ErrorDetection:
    """Potential self-detected error."""

    error_type: str
    location: str
    evidence: list[str]
    severity: float
    suggested_fix: str


class IntrospectionEngineProtocol(Protocol):
    """Protocol for introspection/analysis engines."""

    def explain_decision(
        self, decision: dict[str, Any], context: dict[str, Any]
    ) -> SelfExplanation: ...

    def detect_own_errors(
        self, decision: dict[str, Any], context: dict[str, Any]
    ) -> list[ErrorDetection]: ...

    def record_error(self, error: ErrorDetection, actual_outcome: dict[str, Any]) -> None: ...


# =============================================================================
# LEARNING PROTOCOLS
# =============================================================================


@runtime_checkable
class ILearningCoordinator(Protocol):
    """Interface for the unified learning coordinator."""

    async def start_batch_training_loop(self, interval_seconds: int = 300) -> None:
        """Start background batch training loop."""
        ...

    async def record_experience(self, experience: dict[str, Any]) -> None:
        """Record an experience for learning."""
        ...


@runtime_checkable
class IWorldModelUpdater(Protocol):
    """Interface for updating the world model."""

    async def update(self, observation: Any, action: Any, reward: float, done: bool) -> None:
        """Update world model with new observation."""
        ...


@runtime_checkable
class IMemorySystem(Protocol):
    """Interface for memory storage systems."""

    async def store(self, key: str, value: Any, metadata: dict[str, Any] | None = None) -> None:
        """Store a value in memory."""
        ...

    async def retrieve(self, key: str) -> Any:
        """Retrieve a value from memory."""
        ...


# =============================================================================
# PRIVACY PROTOCOLS
# =============================================================================


class PrivacyLevel(str, Enum):
    """Privacy levels for data classification."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ConsentType(str, Enum):
    """Types of user consent."""

    NECESSARY = "necessary"
    FUNCTIONAL = "functional"
    ANALYTICS = "analytics"
    MARKETING = "marketing"


@runtime_checkable
class PrivacyProvider(Protocol):
    """Protocol for privacy operations."""

    async def classify_data(self, data: dict[str, Any]) -> PrivacyLevel:
        """Classify data according to privacy level."""
        ...

    async def anonymize(self, data: dict[str, Any], fields: list[str]) -> dict[str, Any]:
        """Anonymize specified fields in data."""
        ...

    async def check_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        """Check if user has given specified consent."""
        ...

    async def audit_access(self, user_id: str, resource: str, action: str) -> None:
        """Audit data access for compliance."""
        ...


@runtime_checkable
class EncryptionProvider(Protocol):
    """Protocol for encryption operations."""

    async def encrypt(self, data: bytes, key_id: str | None = None) -> bytes:
        """Encrypt data."""
        ...

    async def decrypt(self, encrypted_data: bytes, key_id: str | None = None) -> bytes:
        """Decrypt data."""
        ...

    def get_key_id(self, data: bytes) -> str | None:
        """Get key ID used to encrypt data."""
        ...


class PrivacyMetadata:
    """Metadata about privacy operations (pure data)."""

    def __init__(
        self,
        level: PrivacyLevel = PrivacyLevel.INTERNAL,
        encrypted: bool = False,
        anonymized: bool = False,
        consents: list[ConsentType] | None = None,
        metadata: MetadataDict | None = None,
    ):
        self.level = level
        self.encrypted = encrypted
        self.anonymized = anonymized
        self.consents = consents or []
        self.metadata = metadata or {}


# =============================================================================
# SCHEDULING TYPES
# =============================================================================


@dataclass
class CandidateFilterContext:
    """Context passed to novelty/aperiodic filters."""

    agent_id: str
    task_id: str
    correlation_id: str | None = None
    metadata: dict[str, Any] | None = None


class CandidateFilterProtocol(Protocol):
    """Protocol for filtering or ranking candidate agent actions."""

    def select(
        self,
        candidates: list[dict[str, Any]],
        context: CandidateFilterContext,
    ) -> list[dict[str, Any]]: ...


# =============================================================================
# SERVICE PROTOCOLS
# =============================================================================


@runtime_checkable
class ServiceProtocol(Protocol):
    """Base protocol for all core services."""

    async def initialize(self) -> bool:
        """Initialize the service."""
        ...

    async def shutdown(self) -> None:
        """Shutdown the service and release resources."""
        ...

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        ...


@runtime_checkable
class IForgeService(ServiceProtocol, Protocol):
    """Interface for Forge (Generative AI) service."""

    async def generate_content(self, prompt: str, params: dict[str, Any]) -> Any:
        """Generate content based on prompt."""
        ...


@runtime_checkable
class ILLMService(ServiceProtocol, Protocol):
    """Interface for LLM service."""

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        """Generate text completion."""
        ...

    async def embed(self, text: str) -> list[float]:
        """Generate text embeddings."""
        ...


# =============================================================================
# SERVICE TYPES
# =============================================================================


class ServiceStatus(Enum):
    """Status of a service."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ServiceConfig:
    """Base configuration for a service."""

    enabled: bool = True
    name: str = ""
    options: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class ServiceHealth:
    """Health status of a service."""

    name: str
    status: ServiceStatus
    uptime_seconds: float
    last_error: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict[str, Any])


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Chaos Types
    "AttractorConfig",
    "AudioServiceProtocol",
    # Scheduling Types
    "CandidateFilterContext",
    "CandidateFilterProtocol",
    "ChaosParams",
    "ChaosSafetyMetrics",
    "ChaosSafetyResult",
    # Common Types
    "ConfigDict",
    "ConsentType",
    # Database Types
    "DatabaseConfig",
    "DatabaseMetadata",
    "DatabaseProvider",
    "EncryptionProvider",
    "ErrorDetection",
    # API Events
    "EventBroadcaster",
    # Forge Types
    "ForgeCapability",
    "ForgeJobDTO",
    "ForgeMetadata",
    "ForgeProvider",
    "ForgeStatus",
    "ForgeUtility",
    "HeadersDict",
    # Composio
    "IComposioService",
    "IForgeService",
    "ILLMService",
    # Learning Protocols
    "ILearningCoordinator",
    "IMemorySystem",
    "IWorldModelUpdater",
    "IntrospectionEngineProtocol",
    "MetadataDict",
    "ParamsDict",
    # Privacy Protocols
    "PrivacyLevel",
    "PrivacyMetadata",
    "PrivacyProvider",
    "RealtimeBroadcaster",
    # Introspection Types
    "ReasoningTrace",
    "Repository",
    "ResultDict",
    # Audio Types
    "STTProviderProtocol",
    "SelfExplanation",
    "ServiceConfig",
    "ServiceHealth",
    # Service Protocols
    "ServiceProtocol",
    # Service Types
    "ServiceStatus",
    "TTSProviderProtocol",
    # Forge DTOs
    "VisualDesignRequestDTO",
]
