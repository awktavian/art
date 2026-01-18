"""Octonion Operations Package.

Consolidated octonion algebra, attention, and regularization.

Organization:
- algebra.py: Core OctonionManifold, multiplication, manifold ops
- attention.py: FanoOctonionAttention
- regularization.py: OctonionRegularization

This package provides a single import location for all octonion operations,
replacing the previous scattered files:
- kagami.math.octonions (wrapper)
- kagami.math.octonion_attention
- kagami.core.training.octonion_regularization
- kagami.core.world_model.manifolds.octonion

All previous import paths remain valid for backward compatibility.
"""

from __future__ import annotations

from typing import Any

# Hierarchical octonions (direct import)
from kagami_math.hierarchical_octonions import HierarchicalOctonionFusion

# Core algebra
from kagami_math.octonions.algebra import (
    OctonionManifold,
    cayley_dickson_mul,
    embed_to_8d,
    extract_from_8d,
    multiply_8d,
    octonion_conjugate,
    octonion_norm,
    unit_normalize,
)

# Attention mechanism
from kagami_math.octonions.attention import FanoOctonionAttention

# Regularization
from kagami_math.octonions.regularization import OctonionRegularization

# Backward compatibility aliases
octonion_mul = cayley_dickson_mul
octonion_multiply = cayley_dickson_mul


def octonion_inverse(o):  # type: ignore[no-untyped-def]
    """Octonion inverse with lazy import.

    Backward compatibility wrapper for old API.
    """
    manifold = OctonionManifold()
    return manifold.inverse(o)


__all__ = [
    # Attention
    "FanoOctonionAttention",
    # Hierarchical
    "HierarchicalOctonionFusion",
    # Core algebra
    "OctonionManifold",
    # Regularization
    "OctonionRegularization",
    "cayley_dickson_mul",
    "embed_to_8d",
    "extract_from_8d",
    "multiply_8d",
    "octonion_conjugate",
    "octonion_inverse",
    # Backward compatibility (function aliases only)
    "octonion_mul",
    "octonion_multiply",
    "octonion_norm",
    "unit_normalize",
]
