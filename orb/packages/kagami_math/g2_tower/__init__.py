"""G₂ Irreducible Representation Tower - Modular Implementation.

This package provides a scalable G₂-equivariant architecture by building
towers of irreducible representations via tensor products.

The implementation is split into logical submodules:
- irrep_levels: IrrepLevel enum and dimension constants
- hardware: SDPAttention, G2HardwareConfig, and optimization presets
- clebsch_gordan: G2ClebschGordan with EXACT coefficients
- tower: G2IrrepTower main class
- cross_copy: G2CrossCopyInteraction for rep_multiplier scaling
- hierarchy: ScalableG2Hierarchy combining all optimizations

All exports maintain backward compatibility with the original monolithic module.
"""

from __future__ import annotations

# Import from submodules
from .clebsch_gordan import G2ClebschGordan
from .cross_copy import G2CrossCopyInteraction
from .hardware import G2HardwareConfig, SDPAttention, get_optimal_g2_config
from .hierarchy import ScalableG2Hierarchy, create_optimal_g2_hierarchy
from .irrep_levels import (
    CORE_IRREP_TOTAL,
    EXTENDED_IRREP_TOTAL,
    IRREP_DIMS,
    IrrepLevel,
)
from .tower import G2IrrepTower

# Re-export everything for backward compatibility
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
