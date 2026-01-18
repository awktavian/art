"""Fano Action Router - Core Routing Logic.

This module contains the main FanoActionRouter class with core routing decisions,
Fano plane geometry, and fundamental routing infrastructure.

Split from fano_action_router.py (December 28, 2025)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import torch
else:
    torch = None  # type: ignore

logger = logging.getLogger(__name__)


def _lazy_import_torch() -> Any:
    """Lazy import torch (200-1000ms delay deferral).

    Defers torch import until first actual usage, avoiding
    eager import overhead during module load.
    """
    import torch as _torch

    return _torch


# =============================================================================
# CONSTANTS (imported from canonical sources)
# =============================================================================

# Colony and catastrophe names from canonical source
from kagami_math.catastrophe_constants import (
    CATASTROPHE_INDEX,
    COLONY_NAMES,
)

# Fano lines (CANONICAL SOURCE: kagami_math/fano_plane.py)
from kagami_math.fano_plane import (
    FANO_LINES,
    get_fano_lines_zero_indexed,
)

# 0-indexed version for array access
FANO_LINES_0IDX = get_fano_lines_zero_indexed()

# Complexity thresholds for action routing
# Note: LLMDrivenColonyRouter is preferred for new code
_DEFAULT_SIMPLE_THRESHOLD = 0.3
_DEFAULT_COMPLEX_THRESHOLD = 0.7


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class ActionMode(Enum):
    """Action generation mode based on complexity."""

    SINGLE = "single"  # 1 action (simple tasks)
    FANO_LINE = "fano"  # 3 actions (Fano composition)
    ALL_COLONIES = "all"  # 7 actions (synthesis)


@dataclass
class ColonyAction:
    """Action to be executed by a specific catastrophe colony."""

    colony_idx: int  # 0-6 (Fold→Parabolic)
    colony_name: str  # "spark", "forge", etc.
    action: str  # Action name
    params: dict[str, Any]  # Action parameters
    weight: float = 1.0  # Contribution weight
    is_primary: bool = False  # Primary action in composition
    fano_role: str | None = None  # "source", "partner", "result" for Fano

    @property
    def s7_basis(self) -> Any:  # torch.Tensor at runtime
        """Get S⁷ basis vector for this colony."""
        torch = _lazy_import_torch()
        basis = torch.zeros(8)
        basis[self.colony_idx + 1] = 1.0  # e₁ at index 1, etc.
        return basis


@dataclass
class RoutingResult:
    """Result of routing decision."""

    mode: ActionMode
    actions: list[ColonyAction]
    complexity: float
    fano_line: tuple[int, int, int] | None = None  # For FANO_LINE mode
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


# =============================================================================
# FANO ACTION ROUTER
# =============================================================================


class FanoActionRouter:
    """Unified routing with 1/3/7 action generation + Nash equilibrium.

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

    def __init__(
        self,
        simple_threshold: float = _DEFAULT_SIMPLE_THRESHOLD,
        complex_threshold: float = _DEFAULT_COMPLEX_THRESHOLD,
        device: str = "cpu",
        cache_size: int = 8192,
    ):
        """Initialize Fano action router.

        Args:
            simple_threshold: Below this, use single action
            complex_threshold: Above this, use all colonies
            device: Torch device for computations
            cache_size: Size of affinity cache (LRU)
        """
        self.simple_threshold = simple_threshold
        self.complex_threshold = complex_threshold
        self.device = device

        # Build Fano adjacency for quick lookups
        self._fano_neighbors = self._build_fano_neighbors()

        # Colony domain affinity (learned or configured)
        self._domain_affinity = self._build_domain_affinity()

        # PERFORMANCE OPTIMIZATION: Precompute Fano lookup table (7×7)
        self._fano_lookup_table = self._build_fano_lookup_table()

        # PERFORMANCE OPTIMIZATION: LRU cache for affinity results
        from collections import OrderedDict

        self._affinity_cache: OrderedDict[tuple[str, frozenset], int] = OrderedDict()
        self._cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0

        # GÖDEL AGENT: ColonyGameModel for Nash equilibrium routing (REQUIRED)
        from kagami.core.unified_agents.memory.stigmergy import get_stigmergy_learner

        self._stigmergy_learner = get_stigmergy_learner()
        if self._stigmergy_learner.game_model is None:
            from kagami.core.unified_agents.memory.stigmergy import ColonyGameModel

            self._stigmergy_learner.game_model = ColonyGameModel()

        # ROUTING MONITOR: Detect local optima and dead colonies
        from kagami.core.unified_agents.colony_routing_monitor import create_routing_monitor

        self.routing_monitor = create_routing_monitor(
            window_size=1000,
            dead_threshold=0.05,
            gini_threshold=0.7,
        )
        self._route_count = 0  # Track total routes for health checks

        # BRAIN-INSPIRED INHIBITION (Dec 26, 2025)
        # Implements PV/SST/VIP-like inhibitory mechanisms for colony competition
        # ALWAYS use inhibitory gate - create identity gate if real gate unavailable
        try:
            from kagami.core.unified_agents.inhibitory_gate import create_inhibitory_gate

            self._inhibitory_gate = create_inhibitory_gate(num_colonies=7)
            self._inhibitory_gate_enabled = True
            inhibit_status = "ACTIVE"
        except Exception as e:
            logger.warning(f"InhibitoryGate unavailable ({e}), creating identity gate")
            # Create identity gate that passes through unchanged (strength=0)
            from kagami.core.unified_agents.inhibitory_gate import create_identity_gate

            self._inhibitory_gate = create_identity_gate(num_colonies=7)  # type: ignore[assignment]
            self._inhibitory_gate_enabled = True  # ALWAYS enabled, just identity
            inhibit_status = "IDENTITY"
        logger.debug(
            f"FanoActionRouter initialized: "
            f"simple<{simple_threshold}, complex≥{complex_threshold}, "
            f"ColonyGameModel=ACTIVE, RoutingMonitor=ACTIVE, "
            f"InhibitoryGate={inhibit_status}, cache_size={cache_size}"
        )

    def _build_fano_neighbors(self) -> dict[int, list[tuple[int, int]]]:
        """Build Fano neighbor lookup: colony → [(partner, result), ...]"""
        neighbors: dict[int, list[tuple[int, int]]] = {i: [] for i in range(7)}

        for i, j, k in FANO_LINES_0IDX:
            # i × j = k (and cyclic permutations)
            neighbors[i].append((j, k))
            neighbors[j].append((k, i))
            neighbors[k].append((i, j))

        return neighbors

    def _build_fano_lookup_table(self) -> Any:  # torch.Tensor at runtime
        """Precompute all 7×7 Fano compositions at startup.

        PERFORMANCE OPTIMIZATION: This table eliminates repeated lookups
        during routing by precomputing all possible colony compositions.

        Returns:
            Tensor of shape [7, 7] where entry [i,j] is the result colony.
            Entry is -1 if (i,j) is not a valid Fano composition.
        """
        torch = _lazy_import_torch()
        table = torch.full((7, 7), -1, dtype=torch.long)

        for i in range(7):
            for j in range(7):
                # Use existing get_fano_composition method
                result = self.get_fano_composition(i, j)
                if result is not None:
                    table[i, j] = result

        logger.debug(f"📊 Fano lookup table built: {table.count_nonzero()}/49 valid compositions")
        return table

    def _validate_fano_line(self, line: tuple[int, int, int]) -> bool:
        """Validate that a line is in the canonical Fano set[Any].

        Args:
            line: Tuple of 3 colony indices (0-indexed)

        Returns:
            True if line is valid, False otherwise
        """
        line_set = set(line)
        # Check if this set[Any] of 3 colonies appears in any canonical Fano line
        return any(set(canonical_line) == line_set for canonical_line in FANO_LINES_0IDX)

    def _build_domain_affinity(self) -> dict[str, int]:
        """Map action keywords to preferred colonies."""
        return {
            # Spark (creative)
            "create": 0,
            "generate": 0,
            "brainstorm": 0,
            "innovate": 0,
            "imagine": 0,
            "design": 0,
            "ideate": 0,
            # Forge (build)
            "build": 1,
            "implement": 1,
            "code": 1,
            "construct": 1,
            "execute": 1,
            "make": 1,
            "develop": 1,
            # Flow (maintain)
            "fix": 2,
            "repair": 2,
            "maintain": 2,
            "adapt": 2,
            "recover": 2,
            "debug": 2,
            "patch": 2,
            # Nexus (integrate)
            "integrate": 3,
            "connect": 3,
            "merge": 3,
            "unify": 3,
            "consolidate": 3,
            "combine": 3,
            "sync": 3,
            # Beacon (plan)
            "plan": 4,
            "strategize": 4,
            "roadmap": 4,
            "schedule": 4,
            "organize": 4,
            "prioritize": 4,
            "focus": 4,
            # Grove (research)
            "research": 5,
            "document": 5,
            "explore": 5,
            "discover": 5,
            "learn": 5,
            "study": 5,
            "investigate": 5,
            # Crystal (verify)
            "test": 6,
            "verify": 6,
            "validate": 6,
            "check": 6,
            "audit": 6,
            "review": 6,
            "ensure": 6,
        }

    def _is_safety_critical(self, action: str, params: dict[str, Any]) -> bool:
        """Detect if action requires mandatory Crystal verification.

        Safety-critical operations include:
        - File system modifications (write, delete, modify)
        - External service interactions (deploy, install, API calls)
        - Authentication/authorization changes
        - Data persistence operations
        - Code execution

        Args:
            action: Action name to analyze
            params: Action parameters to inspect

        Returns:
            True if Crystal verification is mandatory, False otherwise
        """
        action_lower = action.lower()

        # Safety-critical action keywords
        critical_keywords = [
            "execute",
            "write",
            "delete",
            "remove",
            "update",
            "modify",
            "create",
            "deploy",
            "install",
            "run",
            "launch",
            "start",
            "stop",
            "kill",
            "terminate",
            "persist",
            "save",
            "commit",
            "push",
            "publish",
            "configure",
            "alter",
        ]

        # Check action string for critical keywords
        if any(keyword in action_lower for keyword in critical_keywords):
            return True

        # Check for file system operations
        if any(
            fs_keyword in action_lower
            for fs_keyword in ["file", "path", "directory", "folder", "disk"]
        ):
            if any(op in action_lower for op in ["write", "delete", "modify", "create"]):
                return True

        # Check for external service interactions
        if any(
            ext_keyword in action_lower
            for ext_keyword in ["api", "external", "remote", "network", "http", "request"]
        ):
            return True

        # Check for authentication/authorization operations
        if any(
            auth_keyword in action_lower
            for auth_keyword in [
                "auth",
                "login",
                "permission",
                "access",
                "credential",
                "token",
                "key",
            ]
        ):
            return True

        # Check params for sensitive operations
        if params:
            # Persistence indicators
            if params.get("persist") or params.get("save") or params.get("commit"):
                return True

            # External call indicators
            if params.get("external_call") or params.get("api_call") or params.get("remote"):
                return True

            # File operations
            if params.get("file_path") or params.get("path") or params.get("filename"):
                if any(op in params for op in ["write", "delete", "modify", "operation"]):
                    return True

            # Destructive operations
            if params.get("destructive") or params.get("force"):
                return True

        return False

    def get_fano_composition(
        self,
        source_colony: int,
        partner_colony: int,
    ) -> int | None:
        """Get result colony for Fano composition.

        Returns the colony k where eₛ × eₚ = eₖ.
        Returns None if not a valid Fano line.

        Note: Due to octonion anti-commutativity, both (i,j) and (j,i)
        return the same colony index (but with opposite signs in full algebra).
        """
        for i, j, k in FANO_LINES_0IDX:
            # Check cyclic order: i×j=k, j×k=i, k×i=j
            if (source_colony, partner_colony) == (i, j):
                return k
            if (source_colony, partner_colony) == (j, k):
                return i
            if (source_colony, partner_colony) == (k, i):
                return j
            # Check anti-cyclic order: j×i=-k, k×j=-i, i×k=-j
            # (returns same index, sign difference handled at algebra level)
            if (source_colony, partner_colony) == (j, i):
                return k
            if (source_colony, partner_colony) == (k, j):
                return i
            if (source_colony, partner_colony) == (i, k):
                return j
        return None

    def resolve_conflict_by_catastrophe_index(
        self,
        candidate_colonies: list[int],
    ) -> int:
        """Resolve conflict between colonies using catastrophe index.

        Per CLAUDE.md: "Two colonies claim same task | Higher catastrophe index wins
                        (D₅ > D₄⁺ > A₅ > A₄ > A₃ > A₂)"

        This is the explicit implementation of the catastrophe hierarchy.

        Args:
            candidate_colonies: List of colony indices claiming the task

        Returns:
            Winning colony index (highest catastrophe index)
        """
        if not candidate_colonies:
            return 5  # Default to Grove (research first)

        if len(candidate_colonies) == 1:
            return candidate_colonies[0]

        # Resolve by catastrophe index (higher wins)
        winner = max(candidate_colonies, key=lambda idx: CATASTROPHE_INDEX[idx])
        winner_name = COLONY_NAMES[winner]
        winner_cat_idx = CATASTROPHE_INDEX[winner]

        logger.debug(
            f"⚔️ Conflict resolution: {winner_name} wins "
            f"(catastrophe_index={winner_cat_idx}) from {len(candidate_colonies)} candidates"
        )

        return winner

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache performance statistics.

        Returns:
            Dictionary with cache hit rate, size, and metrics
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "cache_size": len(self._affinity_cache),
            "cache_capacity": self._cache_size,
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_fano_router(
    simple_threshold: float = _DEFAULT_SIMPLE_THRESHOLD,
    complex_threshold: float = _DEFAULT_COMPLEX_THRESHOLD,
    device: str = "cpu",
) -> FanoActionRouter:
    """Create a Fano action router.

    Args:
        simple_threshold: Below this, use single action
        complex_threshold: Above this, use all colonies
        device: Torch device

    Returns:
        Configured FanoActionRouter
    """
    return FanoActionRouter(
        simple_threshold=simple_threshold,
        complex_threshold=complex_threshold,
        device=device,
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
    "FANO_LINES",
    "FANO_LINES_0IDX",
    "ActionMode",
    "ColonyAction",
    "FanoActionRouter",
    "RoutingResult",
    "create_fano_router",
    "get_fano_router",
]
