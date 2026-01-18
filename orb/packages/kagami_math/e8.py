"""Canonical E8 Module — Single Source of Truth for E8 Operations.

CONSOLIDATION (December 6, 2025):
=================================
This module consolidates ALL E8-related code that was previously scattered across:

DELETED DUPLICATES (Dec 7, 2025):
- kagami/core/world_model/memory/e8_vq.py (E8VQ) → DELETED, use SemanticResidualE8
- kagami/core/world_model/optimizations.py (VectorizedE8Quantizer, FusedE8Operations) → DELETED
- kagami/core/world_model/optimization_integration.py (OptimizedE8Wrapper) → DELETED
- kagami/core/math/s7_parallel_ops.py (ParallelE8Quantizer) → DELETED
- kagami/core/training/embedding_distillation.py (E8VideoQuantizer) → DELETED
- kagami/core/world_model/improved_hourglass.py (CurriculumResidualE8, PredictiveResidualE8) → DELETED
- kagami/core/world_model/optimal_hourglass.py (E8ResidualVQ) → DELETED

CANONICAL SOURCE (v2 lattice protocol):
- kagami/core/math/e8_lattice_quantizer.py: nearest-point quantizer for the true E8 lattice
- kagami/core/math/e8_lattice_protocol.py: versioned byte protocol + residual lattice VQ
- kagami/core/math/e8.py (THIS MODULE): Re-exports and convenience wrappers

ARCHITECTURE:
=============
All E8 quantization uses the same flow:
    Input → Project to 8D → E8 Lattice Residual VQ → v2 bytes → Decode → Output

Mathematical Foundation:
- Viazovska (2016): E8 = optimal sphere packing in 8D
- 240 roots with norm √2 (kissing number = 240)
- v2 lattice residual protocol: each level is an E8 lattice point represented as
  8 half-step integer coordinates (not a 0-239 root index); byte encoding uses
  varints, so bitrate is variable. (We still use log₂(240) ≈ 7.91 as a legacy
  *proxy* in a few telemetry paths.)

Created: December 6, 2025
Purpose: Single source of truth for E8 operations
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "E8_DIM",
    "E8_ROOTS",
    "SQRT_240",
    # === OPTIMIZATION: RUNTIME CACHE (Dec 18, 2025) ===
    "CachedE8Quantizer",
    # === CONVENIENCE ALIASES ===
    "CanonicalE8Quantizer",
    "E8LatticeResidualConfig",
    # === OPTIMIZATION: LOOKUP TABLE (Dec 16, 2025) ===
    "E8LookupTable",
    "E8Quantizer",  # FIX: Add missing E8Quantizer alias
    "E8QuantizerConfig",
    # === MAIN QUANTIZER (v2 lattice residual) ===
    "ResidualE8LatticeVQ",
    # === LEGACY NAME (Dec 7, 2025: kept for compatibility) ===
    "SemanticResidualE8",
    "SemanticResidualE8Config",
    "create_cached_quantizer",
    # === FACTORY FUNCTIONS ===
    "create_e8_quantizer",
    "create_fast_quantizer",
    "create_lookup_table",
    "create_quality_quantizer",
    "estimate_memory_usage",
    # === CANONICAL E8 ROOTS (from dimensions.py) ===
    "generate_e8_roots",
    "get_e8_roots",
    # === LATTICE QUANTIZER UTILITIES ===
    "nearest_e8",
]

import math

# === CANONICAL CONSTANTS ===
E8_DIM = 8  # E8 lattice dimension
E8_ROOTS = 240  # Number of E8 roots (kissing number)
SQRT_240 = math.sqrt(240)  # ≈ 15.49 — optimal decay factor

# === CANONICAL ROOT GENERATION (from kagami_math.dimensions) ===
from kagami_math.dimensions import (
    generate_e8_roots,
    get_e8_roots,
)

# === OPTIMIZATION: RUNTIME CACHE (Dec 18, 2025) ===
from kagami_math.e8_cache import (
    CachedE8Quantizer,
    create_cached_quantizer,
)

# === MAIN E8 QUANTIZER (CANONICAL IMPLEMENTATION) ===
from kagami_math.e8_lattice_protocol import (
    E8LatticeResidualConfig,
    ResidualE8LatticeVQ,
)

# === LATTICE QUANTIZER ===
from kagami_math.e8_lattice_quantizer import nearest_e8

# === OPTIMIZATION: LOOKUP TABLE (Dec 16, 2025) ===
from kagami_math.e8_lookup_table import (
    E8LookupTable,
    create_lookup_table,
    estimate_memory_usage,
)

# === CONVENIENCE ALIASES ===
# These point to the canonical implementations
CanonicalE8Quantizer = ResidualE8LatticeVQ
E8Quantizer = ResidualE8LatticeVQ  # FIX: Add missing E8Quantizer alias
E8QuantizerConfig = E8LatticeResidualConfig

# === LEGACY ALIASES ===
# Older code used "SemanticResidualE8" for the residual quantizer.
SemanticResidualE8 = ResidualE8LatticeVQ
SemanticResidualE8Config = E8LatticeResidualConfig


# === FACTORY FUNCTIONS ===
def create_e8_quantizer(
    training_levels: int = 8,
    inference_levels: int = 16,
    min_levels: int = 2,
    adaptive_levels: bool = True,
    commitment_weight: float = 0.25,
    balance_loss_weight: float = 2.0,
    enable_cache: bool = True,
    cache_size: int = 8192,
    **kwargs: Any,
) -> ResidualE8LatticeVQ | CachedE8Quantizer:
    """Create a canonical E8 quantizer with sensible defaults.

    Args:
        training_levels: Number of residual levels during training (default: 8)
        inference_levels: Number of residual levels during inference (default: 16)
        min_levels: Minimum residual levels (default: 2)
        adaptive_levels: Whether to adapt depth to input complexity (default: True)
        commitment_weight: Weight for commitment loss (default: 0.25)
        balance_loss_weight: Weight for codebook balance loss (default: 2.0)
        enable_cache: Enable runtime caching for repeated queries (default: True)
        cache_size: Cache size if caching enabled (default: 8192)
        **kwargs: Additional config options

    Returns:
        Configured E8 quantizer (cached if enable_cache=True)
    """
    # v2 lattice VQ is not a learned codebook; it uses a true nearest-point lattice quantizer.
    # We keep the factory signature for compatibility and map inference_levels -> max_levels.
    _ = (
        training_levels,
        adaptive_levels,
        commitment_weight,
        balance_loss_weight,
    )  # unused in lattice VQ

    if enable_cache:
        # Return cached quantizer wrapping the base quantizer
        return create_cached_quantizer(
            max_cache_size=cache_size,
            backend="nearest_e8",
            **kwargs,
        )
    else:
        # Return base quantizer without caching
        config = E8LatticeResidualConfig(
            max_levels=inference_levels,
            min_levels=min_levels,
            **kwargs,
        )
        return ResidualE8LatticeVQ(config)


def create_fast_quantizer(
    training_levels: int = 4,
    inference_levels: int = 8,
    **kwargs: Any,
) -> ResidualE8LatticeVQ:
    """Create a fast E8 quantizer optimized for speed.

    Uses fewer levels for faster quantization at the cost of precision.
    Good for real-time applications.
    """
    return create_e8_quantizer(  # type: ignore[return-value]
        training_levels=training_levels,
        inference_levels=inference_levels,
        adaptive_levels=True,
        min_levels=1,
        **kwargs,
    )


def create_quality_quantizer(
    training_levels: int = 12,
    inference_levels: int = 24,
    **kwargs: Any,
) -> ResidualE8LatticeVQ:
    """Create a high-quality E8 quantizer optimized for reconstruction.

    Uses more levels for better reconstruction at the cost of speed.
    Good for archival/quality-sensitive applications.
    """
    return create_e8_quantizer(  # type: ignore[return-value]
        training_levels=training_levels,
        inference_levels=inference_levels,
        adaptive_levels=True,
        min_levels=4,
        **kwargs,
    )
