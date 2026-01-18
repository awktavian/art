"""Type helpers and protocols for K OS.

CREATED (Dec 8, 2025):
======================
Centralized type utilities to fix PyTorch typing issues:
- nn.Parameter returns Tensor|Module (should be Tensor)
- nn.Module.__call__ returns Any (should be Tensor)
- Union types need explicit narrowing

This module provides:
1. Cast helpers for common PyTorch patterns
2. Protocol classes for duck-typed interfaces
3. Type aliases for clarity

Usage:
    from kagami.core.schemas.types import T, module_out, param_data

    # Instead of: x = self.linear(x)  # type is Any
    x = module_out(self.linear, x)    # type is Tensor

    # Instead of: w = self.weight  # type is Tensor|Module
    w = param_data(self.weight)       # type is Tensor
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, cast, overload, runtime_checkable

import torch
import torch.nn as nn
from torch import Tensor

__all__ = [
    "DecoderProtocol",
    # Protocols
    "EncoderProtocol",
    "LossDict",
    "MemoryProtocol",
    "MetricsDict",
    "QuantizerProtocol",
    "ShapeType",
    # Cast helpers
    "T",
    # Type aliases
    "TensorDict",
    "WorldModelProtocol",
    "as_tensor",
    "ensure_tensor",
    "module_out",
    "param_data",
]


# =============================================================================
# TYPE VARIABLES
# =============================================================================

T = TypeVar("T", bound=Tensor)


# =============================================================================
# CAST HELPERS
# =============================================================================


def module_out(module: nn.Module, x: Tensor, *args: Any, **kwargs: Any) -> Tensor:
    """Call nn.Module and cast output to Tensor.

    Fixes: nn.Module.__call__ returns Any, but we know it's Tensor.

    Usage:
        # Instead of:
        x = self.linear(x)  # type: Any

        # Use:
        x = module_out(self.linear, x)  # type: Tensor
    """
    result = module(x, *args, **kwargs)
    return cast(Tensor, result)


def param_data(param: nn.Parameter | Tensor) -> Tensor:
    """Get Tensor from nn.Parameter.

    Fixes: nn.Parameter is typed as Tensor|Module, but .data is always Tensor.

    Usage:
        # Instead of:
        w = self.weight  # type: Tensor|Module

        # Use:
        w = param_data(self.weight)  # type: Tensor
    """
    if isinstance(param, nn.Parameter):
        return param.data
    return cast(Tensor, param)  # type: ignore[redundant-cast]


@overload
def as_tensor(x: Tensor) -> Tensor: ...


@overload
def as_tensor(x: Any) -> Tensor: ...


def as_tensor(x: Any) -> Tensor:
    """Cast any value to Tensor type (compile-time only).

    Use when you KNOW the value is a Tensor but mypy doesn't.
    """
    return cast(Tensor, x)


def ensure_tensor(
    x: Tensor | None, default_shape: tuple[int, ...], device: torch.device | str = "cpu"
) -> Tensor:
    """Ensure x is a Tensor, creating zeros if None.

    Fixes: Optional[Tensor] patterns where we need a Tensor.
    """
    if x is None:
        return torch.zeros(default_shape, device=device)
    return x


# =============================================================================
# TYPE ALIASES
# =============================================================================

TensorDict = dict[str, Tensor]
"""Dict mapping string keys to Tensors (common return type)."""

LossDict = dict[str, Tensor | float]
"""Dict mapping loss names to values (Tensor or float)."""

MetricsDict = dict[str, Any]
"""Dict mapping metric names to values (various types)."""

ShapeType = tuple[int, ...]
"""Tensor shape as tuple[Any, ...] of ints."""


# =============================================================================
# PROTOCOLS
# =============================================================================


@runtime_checkable
class EncoderProtocol(Protocol):
    """Protocol for encoder modules."""

    def encode(
        self,
        x: Tensor,
        return_intermediates: bool = False,
    ) -> dict[str, Any] | Tensor:
        """Encode input to latent representation."""
        ...

    def forward(self, x: Tensor) -> Tensor:
        """Forward pass (encode only)."""
        ...


@runtime_checkable
class DecoderProtocol(Protocol):
    """Protocol for decoder modules."""

    def decode(self, z: Tensor) -> Tensor:
        """Decode latent to output."""
        ...

    def forward(self, z: Tensor) -> Tensor:
        """Forward pass (decode only)."""
        ...


@runtime_checkable
class WorldModelProtocol(Protocol):
    """Protocol for world model modules."""

    config: Any

    def encode(self, x: Tensor, mask: Tensor | None = None) -> tuple[Any, dict[str, Any]]:
        """Encode observation to state."""
        ...

    def decode(self, state: Any) -> Tensor:
        """Decode state to observation."""
        ...

    def step(self, state: Any, action: Tensor) -> tuple[Any, dict[str, Any]]:
        """Step dynamics given state and action."""
        ...


@runtime_checkable
class MemoryProtocol(Protocol):
    """Protocol for memory modules."""

    def store(self, key: Tensor, value: Tensor) -> None:
        """Store key-value pair."""
        ...

    def retrieve(self, query: Tensor) -> Tensor:
        """Retrieve value by query."""
        ...


@runtime_checkable
class QuantizerProtocol(Protocol):
    """Protocol for vector quantization modules."""

    def quantize(self, x: Tensor) -> tuple[Tensor, Tensor, dict[str, Any]]:
        """Quantize continuous to discrete.

        Returns:
            (quantized, indices, metrics)
        """
        ...

    def dequantize(self, indices: Tensor) -> Tensor:
        """Convert indices back to embeddings."""
        ...


# =============================================================================
# INLINE TYPE IGNORES (for use in comments)
# =============================================================================

# Common patterns that are safe to ignore:
# # type: ignore[no-any-return]  - Module call returns Any but we know it's Tensor
# # type: ignore[arg-type]       - Union type passes to function expecting concrete
# # type: ignore[union-attr]     - Accessing attr on Optional after None check
