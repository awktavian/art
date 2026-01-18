"""
K os Math Primitives (Top-Level Module).

This module consolidates geometric and algebraic primitives for the
exceptional Lie algebra hierarchy: G₂ ⊂ F₄ ⊂ E₆ ⊂ E₇ ⊂ E₈

EXTRACTED: December 2025 - Promoted from kagami.core.math to kagami.math
Backward compatibility maintained via kagami.core.math re-exports.

HIERARCHY:
- Octonions (𝕆): 8D non-associative division algebra
- G₂ = Aut(𝕆): 14D exceptional Lie group
- F₄ = Aut(J₃(𝕆)): 52D, automorphisms of Albert algebra
- E₆: 78D, structure group of Albert algebra
- E₇: 133D, extended structure
- E₈: 248D, complete lattice (240 roots)
"""

# =============================================================================
# TRUE CLEBSCH-GORDAN COEFFICIENTS (December 7, 2025) ⭐ MATHEMATICALLY EXACT
# =============================================================================
# Exact projections computed from root system structure and branching rules
# NOT learned parameters - these are fixed mathematical objects
from kagami_math.clebsch_gordan_exceptional import (
    # G2 Dual Projector (G2 → S7 + E8_lattice)
    G2DualProjector,
    # True projector modules
    TrueExceptionalHierarchy,
    compute_e6_to_f4_clebsch_gordan,
    compute_e7_to_e6_clebsch_gordan,
    # C-G matrices (the actual mathematical objects)
    compute_e8_to_e7_clebsch_gordan,
    compute_f4_to_g2_clebsch_gordan,
    compute_g2_to_s7_clebsch_gordan,
    generate_e7_roots_from_e8,
    # Root systems
    generate_e8_roots,
    generate_f4_roots,
    generate_g2_roots,
)

# Canonical dimension enum (single source of truth)
from kagami_math.dimensions import ExceptionalLevel
from kagami_math.e8_lattice_quantizer import nearest_e8
from kagami_math.g2 import (
    G2EquivarianceValidator,
    G2InvariantPooling,
    G2TensorProduct,  # Alias for G2ClebschGordan
)
from kagami_math.g2_forms import (
    G2ExactClebschGordan as G2ExactCG,
)

# =============================================================================
# G₂ FORMS - PURE MATHEMATICAL G₂ STRUCTURES (December 14, 2025)
# =============================================================================
# Extracted to break circular dependency: math should not depend on world_model
from kagami_math.g2_forms import (
    G2PhiPsi,
)

# =============================================================================
# G₂ IRREP TOWER - SCALABLE EQUIVARIANT ARCHITECTURE (December 2, 2025)
# =============================================================================
# Tensor product expansion for optimal G₂ scaling without breaking equivariance
from kagami_math.g2_irrep_tower import (
    CORE_IRREP_TOTAL,
    EXTENDED_IRREP_TOTAL,
    # Constants
    IRREP_DIMS,
    # Core modules
    G2ClebschGordan,
    G2CrossCopyInteraction,
    # Configuration
    G2HardwareConfig,
    G2IrrepTower,
    IrrepLevel,
    ScalableG2Hierarchy,
    create_optimal_g2_hierarchy,
    # Factory functions
    get_optimal_g2_config,
)
from kagami_math.g2_strict import (
    G2EquivariantFeedForward,
    G2InvariantAttention,
)
from kagami_math.hadamard_transform import (
    HadamardE8Quantizer,
    create_hadamard_e8_quantizer,
    hadamard_transform,
    inverse_hadamard_transform,
)
from kagami_math.octonions import (
    FanoOctonionAttention,
    octonion_conjugate,
    octonion_inverse,
    octonion_mul,
    octonion_norm,
)
from kagami_math.quaternion import (
    quat_conj,
    quat_from_axis_angle,
    quat_inverse,
    quat_mul,
    quat_norm,
    quat_normalize,
    quat_slerp,
    quat_to_rotation_matrix,
)

# =============================================================================
# S7-AUGMENTED HIERARCHY (December 13, 2025) ⭐ S7 PHASE AT EVERY LEVEL
# =============================================================================
# Extracts S7 (octonion phase) at every level of the hierarchy, enabling
# colony coherence tracking across the full E8→S7 chain.
from kagami_math.s7_augmented_hierarchy import (
    S7AugmentedHierarchy,
    S7PhaseState,
    StrangeLoopS7Tracker,
)

# =============================================================================
# THEORETICAL IMPROVEMENTS (December 6, 2025)
# =============================================================================
# Advanced mathematical structures for exceptional hierarchy
# NOTE: TheoreticalExceptionalHierarchy is NOT exported — production uses
# TrueExceptionalHierarchy from clebsch_gordan_exceptional.py instead.
# Tests that need it should import directly from theoretical_improvements.
from kagami_math.theoretical_improvements import (
    FreudenthalTripleLayer,
    # Freudenthal Triple System (E₇)
    FreudenthalTripleSystem,
    # G₂ Holonomy
    G2HolonomyDecomposition,
    # Jordan Algebra (F₄)
    JordanAlgebra,
    JordanBeliefPropagation,
    # Octonion Operations
    OctonionLinear,
    OctonionMLP,
    # Weyl Equivariance
    WeylEquivariantConv,
)

# =============================================================================
# ROOT COUNTS (Mathematical Constants)
# =============================================================================
LEVEL_ROOT_COUNTS = {
    ExceptionalLevel.G2: 12,
    ExceptionalLevel.F4: 48,
    ExceptionalLevel.E6: 72,
    ExceptionalLevel.E7: 126,
    ExceptionalLevel.E8: 240,
}

__all__ = [
    "CORE_IRREP_TOTAL",
    "EXTENDED_IRREP_TOTAL",
    "IRREP_DIMS",
    "LEVEL_ROOT_COUNTS",
    # ==========================================================================
    # EXCEPTIONAL HIERARCHY (G₂ ⊂ F₄ ⊂ E₆ ⊂ E₇ ⊂ E₈)
    # ==========================================================================
    "ExceptionalLevel",
    # ==========================================================================
    # OCTONION OPERATIONS (Non-Associative Division Algebra)
    # ==========================================================================
    "FanoOctonionAttention",
    "FreudenthalTripleLayer",
    # ==========================================================================
    # THEORETICAL STRUCTURES (December 6, 2025)
    # ==========================================================================
    # Freudenthal Triple System (E₇ - 3-way interactions)
    "FreudenthalTripleSystem",
    "G2ClebschGordan",
    "G2CrossCopyInteraction",
    # G2 Dual Projector
    "G2DualProjector",
    # ==========================================================================
    # G₂ OPERATIONS (Automorphisms of Octonions)
    # ==========================================================================
    "G2EquivarianceValidator",
    "G2EquivariantFeedForward",
    "G2ExactCG",
    "G2HardwareConfig",
    "G2HolonomyDecomposition",
    "G2InvariantAttention",
    "G2InvariantPooling",
    "G2IrrepTower",
    # G₂ Forms (pure mathematical structures)
    "G2PhiPsi",
    "G2TensorProduct",
    "HadamardE8Quantizer",
    "IrrepLevel",
    # Jordan Algebra (F₄ - Belief Propagation)
    "JordanAlgebra",
    "JordanBeliefPropagation",
    "OctonionLinear",
    "OctonionMLP",
    "S7AugmentedHierarchy",
    # ==========================================================================
    # S7-AUGMENTED HIERARCHY (December 13, 2025) ⭐ S7 PHASE AT EVERY LEVEL
    # ==========================================================================
    "S7PhaseState",
    "ScalableG2Hierarchy",
    "StrangeLoopS7Tracker",
    # True hierarchy
    "TrueExceptionalHierarchy",
    "WeylEquivariantConv",
    "compute_e6_to_f4_clebsch_gordan",
    "compute_e7_to_e6_clebsch_gordan",
    # C-G matrices (mathematical objects)
    "compute_e8_to_e7_clebsch_gordan",
    "compute_f4_to_g2_clebsch_gordan",
    "compute_g2_to_s7_clebsch_gordan",
    "create_hadamard_e8_quantizer",
    "create_optimal_g2_hierarchy",
    "generate_e7_roots_from_e8",
    # NOTE: TheoreticalExceptionalHierarchy removed — use TrueExceptionalHierarchy
    # ==========================================================================
    # TRUE CLEBSCH-GORDAN COEFFICIENTS (December 7, 2025) ⭐ MATHEMATICALLY EXACT
    # ==========================================================================
    # Root systems
    "generate_e8_roots",
    "generate_f4_roots",
    "generate_g2_roots",
    "get_optimal_g2_config",
    # Hadamard preprocessing for E8 quantization (QuIP# approach)
    "hadamard_transform",
    "inverse_hadamard_transform",
    # ==========================================================================
    # E₈ LATTICE (true lattice nearest-point quantization)
    # ==========================================================================
    "nearest_e8",
    "octonion_conjugate",
    "octonion_inverse",
    "octonion_mul",
    "octonion_norm",
    "quat_conj",
    "quat_from_axis_angle",
    "quat_inverse",
    # ==========================================================================
    # QUATERNION OPERATIONS (Hamilton Algebra on S³)
    # ==========================================================================
    "quat_mul",
    "quat_norm",
    "quat_normalize",
    "quat_slerp",
    "quat_to_rotation_matrix",
]
