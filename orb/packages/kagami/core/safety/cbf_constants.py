"""CBF Configuration Constants.

Extracted from cbf_monitor.py to improve testability.
These constants can be overridden in tests without modifying production code.

CREATED: December 14, 2025
PURPOSE: Testability refactoring - separate configuration from implementation
"""

from __future__ import annotations

# =============================================================================
# CBF SAFETY THRESHOLDS
# =============================================================================

# Default CBF barrier threshold (h(x) must be >= this value)
DEFAULT_CBF_THRESHOLD = 0.0

# Warning threshold (h(x) in [threshold, warn_threshold] triggers warnings)
DEFAULT_CBF_WARN_THRESHOLD = 0.1

# History size for monitoring (number of checks to retain)
DEFAULT_HISTORY_SIZE = 1000

# =============================================================================
# ADAPTIVE E8 THRESHOLDS
# =============================================================================

# Maximum allowed depth variance (prevents unstable depth selection)
DEFAULT_E8_VARIANCE_THRESHOLD = 4.0

# Warning threshold for depth variance
DEFAULT_E8_VARIANCE_WARN = 3.0

# Minimum average depth (prevents over-compression)
DEFAULT_E8_MIN_MEAN_DEPTH = 2.0

# Maximum average depth (prevents wasted capacity)
DEFAULT_E8_MAX_MEAN_DEPTH = 14.0

# =============================================================================
# GATED FANO ATTENTION THRESHOLDS
# =============================================================================

# Minimum gate value to avoid collapse (epsilon)
DEFAULT_GATE_EPSILON = 0.01

# Maximum gate value (prevents saturation)
DEFAULT_GATE_MAX = 0.99

# Gate warning threshold
DEFAULT_GATE_WARN_THRESHOLD = 0.05

# Minimum desired sparsity (fraction of gates < 0.5)
DEFAULT_MIN_SPARSITY = 0.3

# Maximum desired sparsity
DEFAULT_MAX_SPARSITY = 0.9

# Sparsity comparison threshold
SPARSITY_COMPARISON_THRESHOLD = 0.5

# =============================================================================
# COMPOSITE MONITOR DEFAULTS
# =============================================================================

# E8 variance warn factor (fraction of threshold)
E8_VARIANCE_WARN_FACTOR = 0.75

# =============================================================================
# COLONY STRUCTURE (FANO PLANE)
# =============================================================================

# Number of colonies in the system
NUM_COLONIES = 7

# Colony names (for diagnostics)
COLONY_NAMES = [
    "Spark",  # e₁
    "Forge",  # e₂
    "Flow",  # e₃
    "Nexus",  # e₄
    "Beacon",  # e₅
    "Grove",  # e₆
    "Crystal",  # e₇
]

# Fano plane structure: 7 lines, each containing 3 colonies
# Each line represents a composition in the Fano algebra (0-indexed)
# CRITICAL: Order matters for octonion multiplication semantics.
# e_i × e_j = ±e_k depends on (i,j) being in cyclic order on the line.
# These must match kagami/core/math/fano_plane.py get_fano_lines_zero_indexed()
# Verification: Dec 20, 2025 - All 7 lines verified against canonical source
FANO_LINES = [
    [0, 1, 2],  # e₀ × e₁ = e₂ (Spark × Forge = Flow)
    [0, 3, 4],  # e₀ × e₃ = e₄ (Spark × Nexus = Beacon)
    [0, 6, 5],  # e₀ × e₆ = e₅ (Spark × Crystal = Grove) — FIXED Dec 20
    [1, 3, 5],  # e₁ × e₃ = e₅ (Forge × Nexus = Grove)
    [1, 4, 6],  # e₁ × e₄ = e₆ (Forge × Beacon = Crystal)
    [2, 3, 6],  # e₂ × e₃ = e₆ (Flow × Nexus = Crystal)
    [2, 5, 4],  # e₂ × e₅ = e₄ (Flow × Grove = Beacon) — FIXED Dec 20
]

# =============================================================================
# VALIDATION
# =============================================================================


def validate_constants() -> None:
    """Validate that constants are consistent.

    Raises:
        ValueError: If constants are inconsistent
    """
    if DEFAULT_CBF_WARN_THRESHOLD <= DEFAULT_CBF_THRESHOLD:
        raise ValueError(
            f"CBF warn threshold ({DEFAULT_CBF_WARN_THRESHOLD}) must be > "
            f"threshold ({DEFAULT_CBF_THRESHOLD})"
        )

    if DEFAULT_E8_VARIANCE_WARN >= DEFAULT_E8_VARIANCE_THRESHOLD:
        raise ValueError(
            f"E8 variance warn ({DEFAULT_E8_VARIANCE_WARN}) must be < "
            f"threshold ({DEFAULT_E8_VARIANCE_THRESHOLD})"
        )

    if DEFAULT_E8_MIN_MEAN_DEPTH >= DEFAULT_E8_MAX_MEAN_DEPTH:
        raise ValueError(
            f"E8 min depth ({DEFAULT_E8_MIN_MEAN_DEPTH}) must be < "
            f"max depth ({DEFAULT_E8_MAX_MEAN_DEPTH})"
        )

    if DEFAULT_MIN_SPARSITY >= DEFAULT_MAX_SPARSITY:
        raise ValueError(
            f"Min sparsity ({DEFAULT_MIN_SPARSITY}) must be < max sparsity ({DEFAULT_MAX_SPARSITY})"
        )

    if len(COLONY_NAMES) != NUM_COLONIES:
        raise ValueError(f"COLONY_NAMES has {len(COLONY_NAMES)} entries, expected {NUM_COLONIES}")

    if len(FANO_LINES) != NUM_COLONIES:
        raise ValueError(f"FANO_LINES has {len(FANO_LINES)} entries, expected {NUM_COLONIES}")

    for i, line in enumerate(FANO_LINES):
        if len(line) != 3:
            raise ValueError(f"Fano line {i} has {len(line)} colonies, expected 3")

        if not all(0 <= idx < NUM_COLONIES for idx in line):
            raise ValueError(f"Fano line {i} contains invalid colony index")


# Validate on import (fail fast if configuration is broken)
validate_constants()


__all__ = [
    "COLONY_NAMES",
    # CBF thresholds
    "DEFAULT_CBF_THRESHOLD",
    "DEFAULT_CBF_WARN_THRESHOLD",
    "DEFAULT_E8_MAX_MEAN_DEPTH",
    "DEFAULT_E8_MIN_MEAN_DEPTH",
    # E8 thresholds
    "DEFAULT_E8_VARIANCE_THRESHOLD",
    "DEFAULT_E8_VARIANCE_WARN",
    # Gated Fano thresholds
    "DEFAULT_GATE_EPSILON",
    "DEFAULT_GATE_MAX",
    "DEFAULT_GATE_WARN_THRESHOLD",
    "DEFAULT_HISTORY_SIZE",
    "DEFAULT_MAX_SPARSITY",
    "DEFAULT_MIN_SPARSITY",
    # Composite monitor
    "E8_VARIANCE_WARN_FACTOR",
    "FANO_LINES",
    # Colony structure
    "NUM_COLONIES",
    "SPARSITY_COMPARISON_THRESHOLD",
    # Validation
    "validate_constants",
]
