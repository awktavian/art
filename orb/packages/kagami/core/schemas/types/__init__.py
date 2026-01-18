"""K os Type System - Protocols and type definitions for the codebase."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = [
    "DecoderProtocol",
    "EncoderProtocol",
    "HasEmbedding",
    "HasEpisodes",
    "HasName",
    "HasPayload",
    "HasSuccessRates",
    # Base types (consolidated from kagami/core/base/)
    "Intent",
    "IntentType",
    "LLMServiceMixin",
    "LLMServiceProtocol",
    "LazyImport",
    "LossDict",
    "MemoryProtocol",
    "MetricsDict",
    "MissingDependencyError",
    "OptionalLLMService",
    "OptionalWorldModel",
    "QuantizerProtocol",
    "Response",
    "Serializable",
    "ShapeType",
    # Tensor/PyTorch type helpers (from tensor_helpers.py)
    "T",
    "TensorDict",
    # Optional dependency types
    "WorldModelProtocol",
    "as_tensor",
    # Runtime type checking
    "check_implements_protocol",
    # Fallback utilities
    "create_fallback_class",
    "create_fallback_function",
    "ensure_tensor",
    "ensure_type",
    "has_method",
    "has_methods",
    "module_out",
    "optional_cast",
    "param_data",
    "safe_cast",
    "validate_type",
]

# Import from submodules (relative imports - files are in this package)
from .base import Intent, IntentType, Response
from .fallbacks import (
    LazyImport,
    MissingDependencyError,
    create_fallback_class,
    create_fallback_function,
)
from .llm_mixin import LLMServiceMixin
from .optional_deps import (
    LLMServiceProtocol,
    OptionalLLMService,
    OptionalWorldModel,
    WorldModelProtocol,
)
from .runtime import (
    check_implements_protocol,
    ensure_type,
    has_method,
    has_methods,
    optional_cast,
    safe_cast,
    validate_type,
)
from .tensor_helpers import (
    DecoderProtocol,
    EncoderProtocol,
    LossDict,
    MemoryProtocol,
    MetricsDict,
    QuantizerProtocol,
    ShapeType,
    T,
    TensorDict,
    as_tensor,
    ensure_tensor,
    module_out,
    param_data,
)


@runtime_checkable
class HasName(Protocol):
    """Protocol for objects with a name attribute."""

    name: str


@runtime_checkable
class HasPayload(Protocol):
    """Protocol for SQLAlchemy models or objects with JSONB payload column."""

    payload: dict[str, Any]


@runtime_checkable
class HasSuccessRates(Protocol):
    """Protocol for agent trackers with success rate tracking."""

    _success_rates: dict[str, dict[str, float]]


@runtime_checkable
class HasEmbedding(Protocol):
    """Protocol for objects with embedding vectors."""

    embedding: list[float] | Any  # numpy array or torch tensor


@runtime_checkable
class HasEpisodes(Protocol):
    """Protocol for objects with episode storage (learning systems)."""

    _episodes: list[dict[str, Any]]


@runtime_checkable
class Serializable(Protocol):
    """Protocol for objects that can be serialized to dict[str, Any]."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any:
        """Create from dictionary."""
        ...
