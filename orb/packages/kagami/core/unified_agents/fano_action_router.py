"""Fano Action Router - Unified 1/3/7 Action Generation.
# quality-gate: exempt file-length (complete Fano plane algebra implementation)

This module implements the mathematically grounded routing strategy:
- Simple tasks (complexity < 0.3): 1 action → single catastrophe colony
- Complex tasks (complexity 0.3-0.7): 3 actions → Fano line (3 catastrophes)
- Synthesis tasks (complexity ≥ 0.7): 7 actions → all 7 catastrophes

CATASTROPHE COMPOSITION:
========================
The Fano plane encodes valid catastrophe compositions:
- 7 points = 7 catastrophe colonies
- 7 lines = 7 valid 3-catastrophe compositions

Fano lines encode which catastrophe dynamics compose productively:
    Line 1: Fold × Cusp → Swallowtail
    Line 2: Fold × Butterfly → Hyperbolic
    Line 3: Fold × Parabolic → Elliptic
    Line 4: Cusp × Butterfly → Elliptic
    Line 5: Cusp × Hyperbolic → Parabolic
    Line 6: Swallowtail × Butterfly → Parabolic
    Line 7: Swallowtail × Hyperbolic → Elliptic

References:
- Thom (1972): Structural Stability and Morphogenesis
- Fano (1892): Sui postulati fondamentali della geometria projettiva

REFACTORING (December 28, 2025):
=================================
This module has been split into three focused submodules:
1. router_core.py - Core FanoActionRouter class and Fano plane geometry
2. router_scoring.py - Colony scoring, utility calculations, complexity inference
3. router_composition.py - Action composition, Fano line generation, consensus routing

This file now serves as the main entry point, combining the mixins and
re-exporting all public APIs for backward compatibility.

Created: December 2, 2025
Refactored: December 28, 2025
"""

from __future__ import annotations

from .router_composition import (
    ConsensusAwareFanoRouter,
    RouterCompositionMixin,
    fano_line_consensus,
)
from .router_core import (
    CATASTROPHE_INDEX,
    COLONY_NAMES,
    FANO_LINES,
    FANO_LINES_0IDX,
    ActionMode,
    ColonyAction,
    RoutingResult,
)

# Local threshold defaults (prefer LLMDrivenColonyRouter for new code)
_DEFAULT_SIMPLE_THRESHOLD = 0.3
_DEFAULT_COMPLEX_THRESHOLD = 0.7

# Public aliases for tests
SIMPLE_THRESHOLD = _DEFAULT_SIMPLE_THRESHOLD
COMPLEX_THRESHOLD = _DEFAULT_COMPLEX_THRESHOLD
from .router_core import (
    FanoActionRouter as _FanoActionRouterBase,
)
from .router_scoring import RouterScoringMixin

# =============================================================================
# COMBINED FANO ACTION ROUTER
# =============================================================================


class FanoActionRouter(
    RouterScoringMixin,
    RouterCompositionMixin,
    _FanoActionRouterBase,
):
    """Unified routing with 1/3/7 action generation + Nash equilibrium.

    This class combines three mixins to provide full routing functionality:
    - _FanoActionRouterBase: Core infrastructure, Fano geometry, cache
    - RouterScoringMixin: Colony scoring, complexity inference, utilities
    - RouterCompositionMixin: Action composition, multi-colony coordination

    Uses task complexity to determine action mode:
    - Simple (< 0.3): Route to single best colony
    - Complex (0.3-0.7): Use Fano line composition (3 colonies)
    - Synthesis (≥ 0.7): Engage all 7 colonies

    GÖDEL AGENT INTEGRATION (December 2025):
    - ColonyGameModel: Auto-instantiated if unavailable
    - StigmergyLearner: REQUIRED for pattern-based routing

    FALLBACK CHAIN (robust routing):
    1. World model hint (if confident)
    2. Keyword affinity matching (deterministic)
    3. Receipt learning utilities (dynamic)
    4. Nash equilibrium (game-theoretic)
    5. Domain context matching
    6. Default to Forge (colony 1)

    SAFETY ENFORCEMENT:
    - CBF safety violations trigger fallback to SINGLE mode
    - Crystal (colony 6) auto-included for safety-critical operations

    The router respects the mathematical structure of the Fano plane,
    ensuring that multi-colony compositions follow valid octonion
    multiplication rules.
    """

    pass  # All functionality inherited from base class and mixins


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_fano_router(
    simple_threshold: float = _DEFAULT_SIMPLE_THRESHOLD,
    complex_threshold: float = _DEFAULT_COMPLEX_THRESHOLD,
    device: str = "cpu",
    cache_size: int = 8192,
) -> FanoActionRouter:
    """Create a Fano action router with all mixins.

    Args:
        simple_threshold: Below this, use single action
        complex_threshold: Above this, use all colonies
        device: Torch device
        cache_size: Size of affinity cache (LRU)

    Returns:
        Configured FanoActionRouter with all routing capabilities
    """
    return FanoActionRouter(
        simple_threshold=simple_threshold,
        complex_threshold=complex_threshold,
        device=device,
        cache_size=cache_size,
    )


def create_consensus_aware_router(
    fano_router: FanoActionRouter | None = None,
    consensus=None,
    enable_consensus: bool = True,
    consensus_timeout: float = 2.0,
    **router_kwargs,
) -> ConsensusAwareFanoRouter:
    """Create a consensus-aware Fano router.

    Args:
        fano_router: Base FanoActionRouter (or None to create default)
        consensus: KagamiConsensus instance (or None to create default)
        enable_consensus: Enable consensus validation
        consensus_timeout: Timeout for consensus (seconds)
        **router_kwargs: Additional kwargs for FanoActionRouter creation

    Returns:
        Configured ConsensusAwareFanoRouter
    """
    if fano_router is None:
        fano_router = create_fano_router(**router_kwargs)

    return ConsensusAwareFanoRouter(
        fano_router=fano_router,
        consensus=consensus,
        enable_consensus=enable_consensus,
        consensus_timeout=consensus_timeout,
    )


# =============================================================================
# SINGLETON PATTERN
# =============================================================================

_FANO_ROUTER: FanoActionRouter | None = None


def get_fano_router() -> FanoActionRouter:
    """Get the global FanoActionRouter singleton.

    Returns:
        The global FanoActionRouter instance, created on first call.
    """
    global _FANO_ROUTER
    if _FANO_ROUTER is None:
        _FANO_ROUTER = create_fano_router()
    return _FANO_ROUTER


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CATASTROPHE_INDEX",
    "COLONY_NAMES",
    "COMPLEX_THRESHOLD",
    "FANO_LINES",
    "FANO_LINES_0IDX",
    "SIMPLE_THRESHOLD",
    "ActionMode",
    "ColonyAction",
    "ConsensusAwareFanoRouter",
    "FanoActionRouter",
    "RoutingResult",
    "create_consensus_aware_router",
    "create_fano_router",
    "fano_line_consensus",
    "get_fano_router",
]
