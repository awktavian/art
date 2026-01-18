"""Canonical Catastrophe Theory Constants.

SINGLE SOURCE OF TRUTH for catastrophe type definitions, codimension tables,
and colony-catastrophe mappings throughout K OS.

The 7 Elementary Catastrophes (Thom Classification):
====================================================

CUSPOID FAMILY (corank 1, 1D state variable):
- Fold (A₂):       V = x³ + ax                    codim=1
- Cusp (A₃):       V = x⁴ + ax² + bx              codim=2
- Swallowtail (A₄): V = x⁵ + ax³ + bx² + cx       codim=3
- Butterfly (A₅):  V = x⁶ + ax⁴ + bx³ + cx² + dx  codim=4

UMBILIC FAMILY (corank 2, 2D state variable):
- Hyperbolic (D₄⁺): V = x³ + y³ + axy + bx + cy         codim=3
- Elliptic (D₄⁻):   V = x³ - 3xy² + a(x²+y²) + bx + cy  codim=3
- Parabolic (D₅):   V = x²y + y⁴ + ax² + by² + cx + dy  codim=4

References:
- Thom (1972): Structural Stability and Morphogenesis
- Arnold (1975): Critical Points of Smooth Functions

Created: December 3, 2025
"""

from __future__ import annotations

from enum import IntEnum


class CatastropheType(IntEnum):
    """The 7 elementary catastrophes mapped to colony indices (0-6).

    Index corresponds to octonion imaginary basis eᵢ (i=1..7).
    """

    FOLD = 0  # Spark  - e₁ - A₂
    CUSP = 1  # Forge  - e₂ - A₃
    SWALLOWTAIL = 2  # Flow   - e₃ - A₄
    BUTTERFLY = 3  # Nexus  - e₄ - A₅
    HYPERBOLIC = 4  # Beacon - e₅ - D₄⁺
    ELLIPTIC = 5  # Grove  - e₆ - D₄⁻
    PARABOLIC = 6  # Crystal - e₇ - D₅


# Colony names (human-readable)
COLONY_NAMES: tuple[str, ...] = (
    "spark",  # 0
    "forge",  # 1
    "flow",  # 2
    "nexus",  # 3
    "beacon",  # 4
    "grove",  # 5
    "crystal",  # 6
)

# Catastrophe names (human-readable)
CATASTROPHE_NAMES: tuple[str, ...] = (
    "fold",  # 0 - A₂
    "cusp",  # 1 - A₃
    "swallowtail",  # 2 - A₄
    "butterfly",  # 3 - A₅
    "hyperbolic",  # 4 - D₄⁺
    "elliptic",  # 5 - D₄⁻
    "parabolic",  # 6 - D₅
)


# Canonical configuration: codimension and state dimension per type
CATASTROPHE_CONFIG: dict[str, dict[str, int]] = {
    "fold": {"codim": 1, "state_dim": 1},
    "cusp": {"codim": 2, "state_dim": 1},
    "swallowtail": {"codim": 3, "state_dim": 1},
    "butterfly": {"codim": 4, "state_dim": 1},
    "hyperbolic": {"codim": 3, "state_dim": 2},
    "elliptic": {"codim": 3, "state_dim": 2},
    "parabolic": {"codim": 4, "state_dim": 2},
}

# Colony name to catastrophe type mapping
COLONY_CATASTROPHE_MAP: dict[str, str] = {
    "spark": "fold",
    "forge": "cusp",
    "flow": "swallowtail",
    "nexus": "butterfly",
    "beacon": "hyperbolic",
    "grove": "elliptic",
    "crystal": "parabolic",
}

# Maximum control parameters across all types (butterfly/parabolic have 4)
MAX_CONTROL_PARAMS: int = 4

# Catastrophe index for conflict resolution (higher wins)
# Per CLAUDE.md: D₅ > D₄⁺ > A₅ > A₄ > A₃ > A₂
# Index encodes complexity: D₅(6) > D₄⁺(5) > D₄⁻(4) > A₅(3) > A₄(2) > A₃(1) > A₂(0)
# Note: D₄⁻ (elliptic/grove) has same codim as D₄⁺ but lower index for determinism
CATASTROPHE_INDEX: tuple[int, ...] = (
    0,  # spark  - A₂ (fold)       - lowest
    1,  # forge  - A₃ (cusp)
    2,  # flow   - A₄ (swallowtail)
    3,  # nexus  - A₅ (butterfly)
    5,  # beacon - D₄⁺ (hyperbolic) - 2nd highest
    4,  # grove  - D₄⁻ (elliptic)
    6,  # crystal - D₅ (parabolic)  - highest
)


def get_codim(catastrophe_type: str | CatastropheType | int) -> int:
    """Get codimension for a catastrophe type.

    Args:
        catastrophe_type: Type name, enum, or index

    Returns:
        Codimension (number of control parameters)
    """
    # Check CatastropheType first since it's a subclass of int (IntEnum)
    if isinstance(catastrophe_type, CatastropheType):
        catastrophe_type = CATASTROPHE_NAMES[catastrophe_type.value]
    elif isinstance(catastrophe_type, int):
        catastrophe_type = CATASTROPHE_NAMES[catastrophe_type]
    return CATASTROPHE_CONFIG[catastrophe_type]["codim"]


def get_state_dim(catastrophe_type: str | CatastropheType | int) -> int:
    """Get state dimension for a catastrophe type.

    Args:
        catastrophe_type: Type name, enum, or index

    Returns:
        State dimension (1 for cuspoid, 2 for umbilic)
    """
    # Check CatastropheType first since it's a subclass of int (IntEnum)
    if isinstance(catastrophe_type, CatastropheType):
        catastrophe_type = CATASTROPHE_NAMES[catastrophe_type.value]
    elif isinstance(catastrophe_type, int):
        catastrophe_type = CATASTROPHE_NAMES[catastrophe_type]
    return CATASTROPHE_CONFIG[catastrophe_type]["state_dim"]


# For backward compatibility with various import patterns
CatastropheTypeEnum = CatastropheType


def get_catastrophe_index(colony_idx: int) -> int:
    """Get catastrophe index for conflict resolution.

    Higher index wins in conflict resolution per CLAUDE.md:
    D₅ > D₄⁺ > A₅ > A₄ > A₃ > A₂

    Args:
        colony_idx: Colony index (0-6)

    Returns:
        Catastrophe index (0-6, higher = higher priority)
    """
    return CATASTROPHE_INDEX[colony_idx]


__all__ = [
    "CATASTROPHE_CONFIG",
    "CATASTROPHE_INDEX",
    "CATASTROPHE_NAMES",
    "COLONY_CATASTROPHE_MAP",
    "COLONY_NAMES",
    "MAX_CONTROL_PARAMS",
    "CatastropheType",
    "CatastropheTypeEnum",
    "get_catastrophe_index",
    "get_codim",
    "get_state_dim",
]
