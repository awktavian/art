"""G₂ Group Operations - Unified Exports.

This module provides unified access to G₂-related operations:
- G₂ equivariance validation
- G₂ invariant pooling
- G₂ tensor product decompositions (via G2ClebschGordan)

CANONICAL IMPLEMENTATIONS:
=========================
- G2ClebschGordan: kagami.math.g2_irrep_tower (tensor products)
- G2EquivarianceValidator: kagami.math.g2_validator
- G2InvariantPooling: kagami.math.g2_invariant_pooling

Updated: December 2, 2025 - Unified on g2_irrep_tower.py
"""

from kagami_math.g2_invariant_pooling import G2InvariantPooling
from kagami_math.g2_irrep_tower import G2ClebschGordan
from kagami_math.g2_validator import G2EquivarianceValidator

# Alias for backward compatibility
G2TensorProduct = G2ClebschGordan

__all__ = [
    "G2ClebschGordan",
    "G2EquivarianceValidator",
    "G2InvariantPooling",
    "G2TensorProduct",
]
