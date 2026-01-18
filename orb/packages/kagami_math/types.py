"""E8 Math Type Definitions and Protocols.

This module provides shared type definitions and protocols for the E8 math
subsystem. Centralizing these here breaks potential circular dependencies
between:
  - e8_lattice_quantizer.py (core quantization)
  - e8_lattice_protocol.py (serialization)
  - e8_lookup_table.py (optimization)
  - e8_cache.py (runtime caching)
  - e8.py (high-level API)

ARCHITECTURE NOTE (Dec 2025):
==============================
The E8 math modules form a directed acyclic graph:

    e8_lattice_quantizer.py (no internal deps, core algorithms)
           ↓
    e8_lattice_protocol.py → e8_lookup_table.py
           ↓                      ↓
    e8_cache.py ──────────────────┘
           ↓
    e8.py (high-level facade)

This types.py module sits at the root, imported by all others.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import torch


# =============================================================================
# PROTOCOLS
# =============================================================================


@runtime_checkable
class E8QuantizerProtocol(Protocol):
    """Protocol for E8 lattice quantizers.

    Any quantizer that maps R^8 → E8 lattice points should implement this.
    """

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        """Quantize input to nearest E8 lattice point.

        Args:
            x: [..., 8] float tensor

        Returns:
            y: [..., 8] float tensor in E8 lattice
        """
        ...

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass (alias for __call__)."""
        ...


@runtime_checkable
class E8CacheProtocol(Protocol):
    """Protocol for E8 quantization caches.

    Caches store previously computed quantization results for speedup.
    """

    def get_cache_stats(self) -> dict[str, float | int]:
        """Return cache performance statistics."""
        ...

    def clear_cache(self) -> None:
        """Clear all cached entries."""
        ...

    def get_memory_usage(self) -> int:
        """Return estimated cache memory usage in bytes."""
        ...


@runtime_checkable
class E8LookupProtocol(Protocol):
    """Protocol for E8 lookup table implementations.

    Lookup tables pre-compute quantization results for a grid of points.
    """

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        """Look up nearest E8 point via pre-computed table.

        Args:
            x: [..., 8] float tensor

        Returns:
            y: [..., 8] float tensor (approximate E8 lattice point)
        """
        ...

    @property
    def memory_mb(self) -> float:
        """Memory usage of lookup table in megabytes."""
        ...


# =============================================================================
# CONFIGURATION DATACLASSES
# =============================================================================


@dataclass
class E8QuantizationConfig:
    """Configuration for E8 quantization operations.

    This centralizes config that was previously scattered across multiple
    modules (e8_lattice_protocol.py, e8_cache.py, e8_lookup_table.py).
    """

    # Residual VQ config
    max_levels: int = 16
    min_levels: int = 1
    initial_scale: float = 2.0
    decay: float = 15.491933384829668  # sqrt(240)
    adaptive_levels: bool = True
    residual_threshold: float = 1e-3

    # Lookup table config
    use_lookup_table: bool = field(default=False)
    lookup_resolution: int = 8
    lookup_use_fp16: bool = True

    # Cache config
    use_cache: bool = False
    max_cache_size: int = 8192
    cache_precision: int = 4
    use_cpu_cache: bool = True


@dataclass
class E8CacheStats:
    """Cache performance statistics.

    Provides a structured way to report cache metrics.
    """

    cache_hits: int = 0
    cache_misses: int = 0
    hit_rate: float = 0.0
    cache_size: int = 0
    evictions: int = 0
    max_cache_size: int = 8192
    memory_bytes: int = 0

    @property
    def memory_kb(self) -> float:
        """Memory usage in kilobytes."""
        return self.memory_bytes / 1024


# =============================================================================
# TYPE ALIASES
# =============================================================================

# E8 lattice point coordinates in half-step integer units
# (a = 2y where y is the float E8 coordinate)
E8HalfStepCoords = "torch.Tensor"  # [..., 8] int64

# E8 lattice point in float coordinates
E8FloatCoords = "torch.Tensor"  # [..., 8] float32

# Residual codes from multi-level quantization
E8ResidualCodes = list["torch.Tensor"]  # List of [..., 8] int64


# =============================================================================
# CONSTANTS
# =============================================================================

# E8 lattice constants
E8_DIM = 8
E8_NUM_ROOTS = 240  # Kissing number of E8
E8_SQRT_240 = 15.491933384829668

# Wire protocol version for serialization
E8_PROTOCOL_VERSION = 2
E8_PROTOCOL_MAGIC = 0x20
E8_PROTOCOL_FLAG_METADATA = 0x08
