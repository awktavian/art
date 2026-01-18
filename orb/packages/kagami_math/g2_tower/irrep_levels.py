"""G₂ Irreducible Representation Levels and Constants.

Defines the hierarchy of irreps available at different complexity levels,
from minimal (1+7) to maximal (1+7+14+27+64+77+77'+189).
"""

from enum import IntEnum

# =============================================================================
# CONSTANTS: G₂ REPRESENTATION THEORY
# =============================================================================

# G₂ irreducible representation dimensions
# From Fulton & Harris, "Representation Theory", Chapter 22
IRREP_DIMS = {
    "trivial": 1,  # Scalar (invariant)
    "standard": 7,  # Fundamental representation Im(𝕆)
    "adjoint": 14,  # Lie algebra g₂ itself
    "sym2_traceless": 27,  # Symmetric traceless 2-tensors
    "mixed_64": 64,  # From 7⊗14 decomposition
    "sym3_1": 77,  # First 77D irrep
    "sym3_2": 77,  # Second 77D irrep (77')
    "higher_189": 189,  # Higher irrep for very large models
}

# Total dimension of all standard irreps (1+7+14+27 = 49)
CORE_IRREP_TOTAL = 1 + 7 + 14 + 27  # 49

# Extended irreps total (adds 64 + 77 + 77 = 267)
EXTENDED_IRREP_TOTAL = CORE_IRREP_TOTAL + 64 + 77 + 77  # 267


class IrrepLevel(IntEnum):
    """Level of irrep computation."""

    MINIMAL = 0  # 1 ⊕ 7 only (8D) - fastest
    STANDARD = 1  # 1 ⊕ 7 ⊕ 14 ⊕ 27 (49D) - balanced
    EXTENDED = 2  # + 64 ⊕ 77 (190D) - expressive
    MAXIMAL = 3  # + 77' ⊕ 189 (456D) - maximum


__all__ = [
    "CORE_IRREP_TOTAL",
    "EXTENDED_IRREP_TOTAL",
    "IRREP_DIMS",
    "IrrepLevel",
]
