"""E8 Residual Bottleneck + G₂ Tower Equivariance Module.

ARCHITECTURE (December 2, 2025):
================================
    Bulk(configurable) → G₂ Tower → E8 Residual (1-16 bytes) → G₂ Tower → Bulk

ALL FEATURES MANDATORY:
=======================
- G₂ Irrep Tower: Tensor product expansion (7⊗7 → 1⊕7⊕14⊕27)
- E8 Residual Bottleneck: Variable-length compression (7.9-126.6 bits)
- Skip Connections: Learnable gates for encoder→decoder
- Fano Constraints: Colony interactions via Fano plane

No optional features. No degraded modes. Full architecture always.

E8 RESIDUAL CAPACITY:
====================
- L=1:  7.9 bits   (240 states)
- L=4:  31.6 bits  (3.3B states)
- L=8:  63.3 bits  (1.1e19 states)
- L=16: 126.6 bits (1.2e38 states)

USAGE:
------
    from kagami.core.world_model.equivariance import (
        UnifiedEquivariantHourglass,
        create_unified_hourglass,
    )

    model = create_unified_hourglass()  # 512D default

    # Encode → E8 indices
    encoded = model.encode(x, return_intermediates=True)
    e8_indices = encoded["e8_indices"]

    # Decode
    decoded = model.decode(e8_indices)
"""

# =============================================================================
# E8 RESIDUAL + G₂ TOWER (December 2025)
# =============================================================================
# =============================================================================
# G₂ EXACT PRIMITIVES (used by G₂ tower)
# =============================================================================
from kagami.core.world_model.equivariance.g2_exact import (
    G2ExactProjectors,
    G2LieAlgebra,
    G2PhiPsi,
)
from kagami.core.world_model.equivariance.unified_equivariant_hierarchy import (
    E8_BITS_PER_LEVEL,
    PARAM_ALLOCATION,
    FanoColonyLayer,
    G2CrossCopyInteraction,
    # G₂ tower (used internally, exported for advanced use)
    G2HardwareConfig,
    G2IrrepTower,
    HierarchyLevel,
    IrrepLevel,
    ScalableG2Hierarchy,
    # Main class
    UnifiedEquivariantHourglass,
    # Config
    UnifiedHierarchyConfig,
    create_base_hourglass,
    create_large_hourglass,
    create_nano_hourglass,
    create_small_hourglass,
    # Factories
    create_unified_hourglass,
    get_optimal_g2_config,
)

# =============================================================================
# MATRYOSHKA MULTI-SCALE (Dec 7, 2025 - CANONICAL)
# =============================================================================
# Multi-scale outputs from TRUE exceptional hierarchy.
from kagami.core.world_model.matryoshka_hourglass import (
    MATRYOSHKA_SCALES,
    MatryoshkaConfig,
    MatryoshkaHourglass,
)

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "E8_BITS_PER_LEVEL",
    "MATRYOSHKA_SCALES",
    "PARAM_ALLOCATION",
    "FanoColonyLayer",
    "G2CrossCopyInteraction",
    "G2ExactProjectors",
    # G₂ tower
    "G2HardwareConfig",
    "G2IrrepTower",
    "G2LieAlgebra",
    # G₂ primitives
    "G2PhiPsi",
    "HierarchyLevel",
    "IrrepLevel",
    "MatryoshkaConfig",
    # === MATRYOSHKA MULTI-SCALE (Dec 7, 2025) ===
    "MatryoshkaHourglass",
    "ScalableG2Hierarchy",
    # Main class
    "UnifiedEquivariantHourglass",
    # Config
    "UnifiedHierarchyConfig",
    "create_base_hourglass",
    "create_large_hourglass",
    "create_nano_hourglass",
    "create_small_hourglass",
    # Factories
    "create_unified_hourglass",
    "get_optimal_g2_config",
]
