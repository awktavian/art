"""Type definitions for optional dependencies.

This module provides Protocol-based type definitions and type aliases for optional
dependencies in K os. This allows proper type checking while gracefully handling
missing optional dependencies at runtime.

Usage:
    from kagami.core.schemas.types.optional_deps import WorldModelProtocol, OptionalWorldModel

    def get_model() -> OptionalWorldModel:
        if WorldModelType is not None:
            return WorldModelType()
        return None
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from torch import Tensor

# ============================================================================
# World Model Protocols
# ============================================================================


@runtime_checkable
class WorldModelProtocol(Protocol):
    """Protocol for world model implementations."""

    def encode(self, x: Any) -> Tensor:
        """Encode input to latent representation."""
        ...

    def decode(self, z: Tensor) -> Any:
        """Decode latent representation to output."""
        ...

    def forward(self, x: Any) -> tuple[Tensor, dict[str, Any]]:
        """Forward pass through world model."""
        ...


@runtime_checkable
class OptimizedWorldModelProtocol(WorldModelProtocol, Protocol):
    """Protocol for optimized world model implementations."""

    def get_preset(self) -> str:
        """Get current preset configuration."""
        ...


@runtime_checkable
class EnsembleWorldModelProtocol(Protocol):
    """Protocol for ensemble world model implementations."""

    def predict_with_uncertainty(self, x: Any) -> tuple[Tensor, Tensor]:  # mean, variance
        """Predict with uncertainty estimates."""
        ...


# ============================================================================
# LLM Service Protocols
# ============================================================================


@runtime_checkable
class LLMServiceProtocol(Protocol):
    """Protocol for LLM service implementations."""

    async def generate(  # type: ignore[no-untyped-def]
        self,
        prompt: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """Generate text from prompt."""
        ...

    async def embed(self, text: str) -> list[float]:
        """Generate embeddings for text."""
        ...


@runtime_checkable
class StructuredOutputProtocol(Protocol):
    """Protocol for structured output clients."""

    async def generate_structured(
        self, prompt: str, response_model: type[Any], **kwargs: Any
    ) -> Any:
        """Generate structured output conforming to response_model."""
        ...


# ============================================================================
# Forge/Graphics Protocols
# ============================================================================


@runtime_checkable
class GenesisPhysicsProtocol(Protocol):
    """Protocol for Genesis physics wrapper."""

    def simulate_character_motion(
        self, character_params: dict[str, Any], duration: float
    ) -> dict[str, Any]:
        """Simulate character motion using physics.

        Args:
            character_params: Character configuration including:
                - motion_type: Type of motion ('walk', 'run', 'idle', etc.)
                - speed: Movement speed multiplier
                - amplitude: Motion amplitude
            duration: Duration of simulation in seconds

        Returns:
            Dictionary with:
                - frames: List of frame data
                - joint_positions: Joint trajectory data
                - root_trajectory: Root motion path
                - metadata: Additional simulation info
        """
        ...


@runtime_checkable
class Audio2FaceProtocol(Protocol):
    """Protocol for Audio2Face integration."""

    async def generate_animation(self, audio_path: str, character_id: str) -> dict[str, Any]:
        """Generate facial animation from audio.

        Args:
            audio_path: Path to audio file
            character_id: Character identifier for animation target

        Returns:
            Dictionary with:
                - blendshapes: Facial blendshape weights over time
                - timestamps: Time markers for each frame
                - duration: Total animation duration
                - metadata: Additional animation info
        """
        ...


@runtime_checkable
class ForgeMatrixProtocol(Protocol):
    """Protocol for ForgeMatrix character generation."""

    async def generate_character(self, request: dict[str, Any]) -> dict[str, Any]:
        """Generate complete 3D character.

        Args:
            request: Character generation request with:
                - description: Text description of character
                - style: Art style ('realistic', 'stylized', 'anime', etc.)
                - gender: Character gender
                - age: Character age range
                - body_type: Body type specification

        Returns:
            Dictionary with:
                - mesh: 3D mesh data or path
                - textures: Texture maps
                - skeleton: Rig/skeleton data
                - blendshapes: Facial blendshapes
                - metadata: Generation metadata
        """
        ...


# ============================================================================
# Training/RL Protocols
# ============================================================================


@runtime_checkable
class MetaLearnerProtocol(Protocol):
    """Protocol for meta-learning systems."""

    async def adapt(self, task_data: list[Any]) -> dict[str, Any]:  # type: ignore[return]
        """Adapt model to new task."""
        _ = task_data
        ...

    def get_adapted_model(self) -> Any:
        """Get adapted model."""
        ...


@runtime_checkable
class ReplayBufferProtocol(Protocol):
    """Protocol for replay buffer implementations."""

    def add(self, experience: dict[str, Any]) -> None:
        """Add experience to buffer."""
        ...

    def sample(self, batch_size: int) -> list[dict[str, Any]]:
        """Sample batch from buffer."""
        ...


# ============================================================================
# Database/Storage Protocols
# ============================================================================


@runtime_checkable
class AsyncEngineProtocol(Protocol):
    """Protocol for async database engine."""

    async def execute(self, query: str, *args: Any) -> Any:
        """Execute database query."""
        ...

    async def dispose(self) -> None:
        """Dispose of engine resources."""
        ...


@runtime_checkable
class RedisProtocol(Protocol):
    """Protocol for Redis client."""

    async def get(self, key: str) -> str | None:
        """Get value from Redis."""
        ...

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """Set value in Redis."""
        ...

    async def delete(self, *keys: str) -> int:
        """Delete keys from Redis."""
        ...


# ============================================================================
# Type Aliases for Optional Dependencies
# ============================================================================

# World Models
OptionalWorldModel = WorldModelProtocol | None
OptionalOptimizedWorldModel = OptimizedWorldModelProtocol | None
OptionalEnsembleWorldModel = EnsembleWorldModelProtocol | None

# LLM Services
OptionalLLMService = LLMServiceProtocol | None
OptionalStructuredOutput = StructuredOutputProtocol | None

# Forge/Graphics
OptionalGenesisPhysics = GenesisPhysicsProtocol | None
OptionalAudio2Face = Audio2FaceProtocol | None
OptionalForgeMatrix = ForgeMatrixProtocol | None

# Training/RL
OptionalMetaLearner = MetaLearnerProtocol | None
OptionalReplayBuffer = ReplayBufferProtocol | None

# Database/Storage
OptionalAsyncEngine = AsyncEngineProtocol | None
OptionalRedis = RedisProtocol | None

# ============================================================================
# Type Guards
# ============================================================================


def is_world_model(obj: Any) -> bool:
    """Check if object implements WorldModelProtocol."""
    return isinstance(obj, WorldModelProtocol)


def is_llm_service(obj: Any) -> bool:
    """Check if object implements LLMServiceProtocol."""
    return isinstance(obj, LLMServiceProtocol)


def is_genesis_physics(obj: Any) -> bool:
    """Check if object implements GenesisPhysicsProtocol."""
    return isinstance(obj, GenesisPhysicsProtocol)


# ============================================================================
# Module Type Variables
# ============================================================================

# Use TYPE_CHECKING to provide types for static analysis
# while allowing None at runtime
if TYPE_CHECKING:
    from kagami.core.services.llm.service import KagamiOSLLMService
    from kagami.core.world_model.jepa.core import WorldModel
    from kagami.core.world_model.kagami_world_model import KagamiWorldModel

    WorldModelType = WorldModel
    KagamiWorldModelType = KagamiWorldModel
    LLMServiceType = KagamiOSLLMService
else:
    # At runtime, these may be None if dependencies are missing
    WorldModelType = None  # type: ignore[assignment]
    KagamiWorldModelType = None  # type: ignore[assignment]
    LLMServiceType = None  # type: ignore[assignment]
