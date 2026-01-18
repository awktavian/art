"""Colony Constants - Catastrophe-Based Agent Dynamics.

This module re-exports canonical constants from kagami_math.catastrophe_constants
and provides additional utilities (S⁷ embeddings, DomainType enum).

CATASTROPHE THEORY (Thom, 1972):
================================
The 7 colonies correspond to the 7 elementary catastrophes:

    ┌──────────┬─────────┬──────────────────┬──────────────┐
    │ Colony   │ Persona │ Catastrophe      │ Role         │
    ├──────────┼─────────┼──────────────────┼──────────────┤
    │ spark    │ Spark   │ Fold (A₂)        │ Ignition     │
    │ forge    │ Forge   │ Cusp (A₃)        │ Decision     │
    │ flow     │ Flow    │ Swallowtail (A₄) │ Recovery     │
    │ nexus    │ Nexus   │ Butterfly (A₅)   │ Integration  │
    │ beacon   │ Beacon  │ Hyperbolic (D₄⁺) │ Focus        │
    │ grove    │ Grove   │ Elliptic (D₄⁻)   │ Search       │
    │ crystal  │ Crystal │ Parabolic (D₅)   │ Safety       │
    └──────────┴─────────┴──────────────────┴──────────────┘

Each catastrophe defines a different phase transition dynamics and
behavior pattern for the colony.

For Fano plane operations, use:
    from kagami_math.fano_plane import FANO_LINES, FANO_SIGNS

For differentiable DNA encoding, use the canonical lattice protocol:
    from kagami_math.e8_lattice_protocol import ResidualE8LatticeVQ

Created: December 2, 2025
Updated: December 6, 2025 - Consolidated to import from canonical source
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Final

import torch

# =============================================================================
# CANONICAL IMPORTS (Single Source of Truth)
# =============================================================================
from kagami_math.catastrophe_constants import (
    CATASTROPHE_NAMES,
    COLONY_CATASTROPHE_MAP,
    COLONY_NAMES,
)

# =============================================================================
# INDEX MAPPINGS (derived from canonical names)
# =============================================================================

# 0-indexed (for tensor operations)
COLONY_TO_INDEX: Final[dict[str, int]] = {name: idx for idx, name in enumerate(COLONY_NAMES)}

INDEX_TO_COLONY: Final[dict[int, str]] = dict(enumerate(COLONY_NAMES))

# 1-indexed (for mathematical convention e₁...e₇)
COLONY_TO_INDEX_1BASED: Final[dict[str, int]] = {
    name: idx + 1 for idx, name in enumerate(COLONY_NAMES)
}

INDEX_TO_COLONY_1BASED: Final[dict[int, str]] = {
    idx + 1: name for idx, name in enumerate(COLONY_NAMES)
}

# Re-export canonical mappings with local aliases
COLONY_TO_CATASTROPHE: Final[dict[str, str]] = COLONY_CATASTROPHE_MAP

CATASTROPHE_TO_COLONY: Final[dict[str, str]] = {
    cat: name for name, cat in COLONY_CATASTROPHE_MAP.items()
}


# =============================================================================
# S⁷ EMBEDDINGS (Differentiable)
# =============================================================================


@lru_cache(maxsize=1)
def get_s7_basis(device: str = "cpu") -> torch.Tensor:
    """Get the 7 unit basis vectors on S⁷ (differentiable).

    Returns:
        Tensor of shape (7, 7) where each row is a unit octonion imaginary.
        Row i corresponds to eᵢ (1-indexed convention).
    """
    return torch.eye(7, device=device)


@lru_cache(maxsize=8)
def get_colony_embedding(colony: str, device: str = "cpu") -> torch.Tensor:
    """Get the S⁷ embedding for a colony (differentiable).

    Args:
        colony: Colony name ("spark", "forge", etc.)
        device: Target device

    Returns:
        Tensor of shape (7,) - unit vector on S⁷
    """
    idx = COLONY_TO_INDEX[colony]
    basis = get_s7_basis(device)
    return basis[idx]


@lru_cache(maxsize=2)
def get_all_colony_embeddings(device: str = "cpu") -> torch.Tensor:
    """Get all 7 colony embeddings as a batch (differentiable).

    Returns:
        Tensor of shape (7, 7) - one embedding per colony
    """
    return get_s7_basis(device)


# =============================================================================
# DOMAIN TYPE ENUM (Backward Compatibility)
# =============================================================================


class DomainType(Enum):
    """Agent domain types mapped to Thom's 7 Elementary Catastrophes.

    Each colony embodies a catastrophe's phase transition dynamics:

    ┌──────────────────┬─────────┬──────────────────────────────────┐
    │ Catastrophe      │ Colony  │ Dynamics                         │
    ├──────────────────┼─────────┼──────────────────────────────────┤
    │ Fold (A₂)        │ Spark   │ Sudden ignition, threshold burst │
    │ Cusp (A₃)        │ Forge   │ Bistable decision, hysteresis    │
    │ Swallowtail (A₄) │ Flow    │ Multi-stable recovery paths      │
    │ Butterfly (A₅)   │ Nexus   │ Complex integration manifold     │
    │ Hyperbolic (D₄⁺) │ Beacon  │ Outward-splitting focus          │
    │ Elliptic (D₄⁻)   │ Grove   │ Inward-converging search         │
    │ Parabolic (D₅)   │ Crystal │ Edge detection, safety boundary  │
    └──────────────────┴─────────┴──────────────────────────────────┘
    """

    SPARK = "spark"
    FORGE = "forge"
    FLOW = "flow"
    NEXUS = "nexus"
    BEACON = "beacon"
    GROVE = "grove"
    CRYSTAL = "crystal"

    def to_index(self) -> int:
        """Get 0-indexed position."""
        return COLONY_TO_INDEX[self.value]

    def to_embedding(self, device: str = "cpu") -> torch.Tensor:
        """Get differentiable S⁷ embedding."""
        return get_colony_embedding(self.value, device)

    @classmethod
    def from_index(cls, idx: int) -> DomainType:
        """Create from 0-indexed position."""
        return cls(INDEX_TO_COLONY[idx])


# =============================================================================
# CATASTROPHE MAPPING (alias for backward compatibility)
# =============================================================================

# Maps colony to catastrophe type (for reference only)
# The actual differentiable dynamics are in differentiable_catastrophe.py
COLONY_CATASTROPHE_TYPES: Final[dict[str, str]] = COLONY_TO_CATASTROPHE


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Catastrophe names (canonical)
    "CATASTROPHE_NAMES",
    "CATASTROPHE_TO_COLONY",
    "COLONY_CATASTROPHE_TYPES",
    # Colony names
    "COLONY_NAMES",
    # Catastrophe mappings (primary)
    "COLONY_TO_CATASTROPHE",
    # Index mappings
    "COLONY_TO_INDEX",
    "COLONY_TO_INDEX_1BASED",
    "INDEX_TO_COLONY",
    "INDEX_TO_COLONY_1BASED",
    # Enum
    "DomainType",
    "get_all_colony_embeddings",
    "get_colony_embedding",
    # Differentiable embeddings
    "get_s7_basis",
]
