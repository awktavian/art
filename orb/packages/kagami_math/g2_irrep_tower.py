"""G₂ Irreducible Representation Tower - Scalable Equivariant Architecture.

COMPREHENSIVE G₂ SCALING (Dec 2, 2025):
=======================================
This module implements the OPTIMAL scaling strategy for G₂-equivariant representations
by building towers of irreducible representations (irreps) via tensor products.

The key insight: Instead of abandoning equivariance for expressiveness, we EXPAND
within the equivariant space using G₂ representation theory.

MATHEMATICAL FOUNDATIONS:
========================
G₂ is the 14-dimensional automorphism group of the octonions.
The fundamental representation is the 7D standard representation on Im(𝕆).

Tensor product decompositions (Clebsch-Gordan):
    7 ⊗ 7  = 1 ⊕ 7 ⊕ 14 ⊕ 27
    7 ⊗ 14 = 7 ⊕ 27 ⊕ 64
    14 ⊗ 14 = 1 ⊕ 14 ⊕ 27 ⊕ 77 ⊕ 77'
    7 ⊗ 27 = 7 ⊕ 14 ⊕ 27 ⊕ 64 ⊕ 77

This gives access to irreps: 1, 7, 14, 27, 64, 77, 77', ...

SCALING STRATEGY:
================
1. **Irrep Tower**: Build multiple irreps, mix with learnable (invariant) coefficients
2. **Cross-Copy Interaction**: For rep_multiplier > 1, enable cross-copy tensor products
3. **Hardware Optimization**: Tune for MPS (Apple Silicon) or CUDA

MODULAR STRUCTURE (Refactored):
================================
This module now serves as a backward-compatibility layer, re-exporting all
classes and functions from the g2_tower package submodules:

- g2_tower.irrep_levels: IrrepLevel enum and dimension constants
- g2_tower.hardware: SDPAttention, G2HardwareConfig, optimization presets
- g2_tower.clebsch_gordan: G2ClebschGordan with EXACT coefficients
- g2_tower.tower: G2IrrepTower main class
- g2_tower.cross_copy: G2CrossCopyInteraction for rep_multiplier scaling
- g2_tower.hierarchy: ScalableG2Hierarchy combining all optimizations

All existing imports will continue to work unchanged.

REFERENCES:
==========
- Fulton & Harris: "Representation Theory" (G₂ branching rules)
- Cohen & Welling (2016): "Group Equivariant CNNs"
- Weiler et al. (2018): "3D Steerable CNNs"
- Baez (2002): "The Octonions"

Created: December 2, 2025
Refactored: December 27, 2025
"""

from __future__ import annotations

# Import everything from the modular g2_tower package
# This maintains 100% backward compatibility with existing code
from kagami_math.g2_tower import (
    CORE_IRREP_TOTAL,
    EXTENDED_IRREP_TOTAL,
    IRREP_DIMS,
    G2ClebschGordan,
    G2CrossCopyInteraction,
    G2HardwareConfig,
    G2IrrepTower,
    IrrepLevel,
    ScalableG2Hierarchy,
    SDPAttention,
    create_optimal_g2_hierarchy,
    get_optimal_g2_config,
)

# Re-export everything to maintain API compatibility
__all__ = [
    "CORE_IRREP_TOTAL",
    "EXTENDED_IRREP_TOTAL",
    # Constants
    "IRREP_DIMS",
    # Core modules
    "G2ClebschGordan",
    "G2CrossCopyInteraction",
    "G2HardwareConfig",
    "G2IrrepTower",
    # Enums
    "IrrepLevel",
    # Hardware optimization
    "SDPAttention",
    "ScalableG2Hierarchy",
    # Factory functions
    "create_optimal_g2_hierarchy",
    "get_optimal_g2_config",
]
