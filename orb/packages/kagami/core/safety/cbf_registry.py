"""Centralized CBF Registry - Single Source of Truth for All Barriers.

CREATED: December 14, 2025
PURPOSE: Catalog and manage all Control Barrier Functions across the 3-tier hierarchy

ARCHITECTURE:
=============
CBFRegistry (thread-safe singleton)
    │
    ├─ Tier 1: Organism barriers (memory, process, blanket integrity, disk)
    ├─ Tier 2: Colony barriers (7 colonies × behavioral constraints)
    └─ Tier 3: Action barriers (output safety, resource quotas)

USAGE:
======
```python
# Get singleton instance
registry = CBFRegistry()

# Register a barrier
registry.register(
    tier=1,
    name="memory_usage",
    func=lambda state: 0.5 - state.get('memory_pct', 0.0),
    threshold=0.0,
    description="Memory usage must stay below 50%"
)

# Check all barriers
results = registry.check_all(state={'memory_pct': 0.3})

# Check if safe
safe = registry.is_safe(tier=1, state=current_state)

# Get violations
violations = registry.get_violations(state=current_state)
```

DESIGN PRINCIPLES:
==================
1. Thread-safe singleton (only one instance exists)
2. Fast lookups via tier/colony indexing
3. Enable/disable barriers for debugging (WITH WARNINGS)
4. Complete audit trail of all barrier evaluations
5. Integration with CBFMonitor for runtime tracking

SAFETY INVARIANT:
=================
h(x) ≥ 0 for all enabled barriers → system is safe
Any violation → BLOCK action, escalate to operator

References:
- Ames et al. (2019): Control Barrier Functions
- KagamiOS Architecture: 3-tier safety hierarchy
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from kagami.core.safety.types import StateDict

logger = logging.getLogger(__name__)

# Type aliases
TierLevel = Literal[1, 2, 3]
# BarrierFunction supports both zero-arg (legacy) and one-arg (new) signatures
# Zero-arg: lambda: compute_h()
# One-arg: lambda state: compute_h(state)
BarrierFunction = Callable[..., float]


# =============================================================================
# BARRIER ENTRY
# =============================================================================


@dataclass
class BarrierEntry:
    """Single barrier function entry in registry.

    A barrier entry encapsulates:
    - The barrier function h(x) itself
    - Metadata (tier, colony, name, description)
    - Runtime state (enabled, threshold)
    - Evaluation history

    Attributes:
        tier: Hierarchy level (1=organism, 2=colony, 3=action)
        name: Unique barrier identifier
        func: Barrier function h(x) -> float
        threshold: Safety threshold (h >= threshold means safe)
        enabled: Whether this barrier is active
        colony: Colony ID for Tier 2 barriers (0-6, or None)
        description: Human-readable description
        evaluation_count: Number of times evaluated
        violation_count: Number of times violated
        last_value: Most recent h(x) value
        last_check: Timestamp of last evaluation
    """

    tier: TierLevel
    name: str
    func: BarrierFunction
    threshold: float = 0.0
    enabled: bool = True
    colony: int | None = None
    description: str = ""

    # Runtime statistics (mutable)
    evaluation_count: int = field(default=0, init=False)
    violation_count: int = field(default=0, init=False)
    last_value: float | None = field(default=None, init=False)
    last_check: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Validate barrier entry."""
        # Validate tier
        if self.tier not in (1, 2, 3):
            raise ValueError(f"tier must be 1, 2, or 3, got {self.tier}")

        # Validate colony for tier 2
        if self.tier == 2:
            if self.colony is None:
                raise ValueError("Tier 2 barriers must specify colony (0-6)")
            if not 0 <= self.colony <= 6:
                raise ValueError(f"colony must be 0-6, got {self.colony}")
        elif self.colony is not None:
            logger.warning(f"colony={self.colony} specified for tier {self.tier}, ignoring")
            self.colony = None

        # Validate name
        if not self.name or not isinstance(self.name, str):
            raise ValueError(f"name must be non-empty string, got {self.name}")

        # Validate function
        if not callable(self.func):
            raise TypeError(f"func must be callable, got {type(self.func)}")

    def evaluate(self, state: StateDict | None = None) -> float:
        """Evaluate barrier function h(x).

        Args:
            state: Current state dict[str, Any] (optional, barrier may not need it)

        Returns:
            Barrier value h(x)

        Updates:
            - evaluation_count
            - last_value
            - last_check
            - violation_count (if h < threshold)
        """
        try:
            h_x = float(self.func(state))
        except Exception as e:
            logger.error(f"Barrier '{self.name}' evaluation failed: {e}")
            # Return highly negative value to force violation
            h_x = -1000.0

        # Update statistics
        self.evaluation_count += 1
        self.last_value = h_x
        self.last_check = time.time()

        if h_x < self.threshold:
            self.violation_count += 1

        return h_x

    def is_safe(self, state: StateDict | None = None) -> bool:
        """Check if barrier is satisfied.

        Args:
            state: Current state dict[str, Any]

        Returns:
            True if h(x) >= threshold, False otherwise
        """
        if not self.enabled:
            return True  # Disabled barriers are always "safe"

        h_x = self.evaluate(state)
        return h_x >= self.threshold

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tier": self.tier,
            "name": self.name,
            "threshold": self.threshold,
            "enabled": self.enabled,
            "colony": self.colony,
            "description": self.description,
            "evaluation_count": self.evaluation_count,
            "violation_count": self.violation_count,
            "last_value": self.last_value,
            "last_check": self.last_check,
        }


# =============================================================================
# CBF REGISTRY (SINGLETON)
# =============================================================================


class CBFRegistry:
    """Centralized registry for all Control Barrier Functions.

    Thread-safe singleton pattern ensures single source of truth for all
    barrier functions across the 3-tier hierarchy.

    The registry provides:
    1. Barrier registration and cataloging
    2. Fast lookups by tier/colony/name
    3. Bulk evaluation of barriers
    4. Safety checking (all barriers satisfied?)
    5. Violation detection and reporting

    Example:
        >>> registry = CBFRegistry()
        >>> registry.register(
        ...     tier=1,
        ...     name="memory",
        ...     func=lambda s: 0.5 - s.get('mem', 0.0),
        ...     description="Memory < 50%"
        ... )
        >>> registry.is_safe(state={'mem': 0.3})
        True
    """

    _instance: CBFRegistry | None = None
    _lock = threading.Lock()
    _initialized: bool

    def __new__(cls) -> CBFRegistry:
        """Singleton pattern with thread safety.

        Only one instance of CBFRegistry can exist. Subsequent calls
        to CBFRegistry() return the same instance.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        """Initialize registry (only once due to singleton)."""
        # Skip if already initialized
        if self._initialized:
            return

        # Core storage
        self._barriers: dict[str, BarrierEntry] = {}

        # Indices for fast lookup
        self._tier_index: dict[TierLevel, list[str]] = {1: [], 2: [], 3: []}
        self._colony_index: dict[int, list[str]] = defaultdict(list[Any])

        # Thread safety for registration/modification
        self._registry_lock = threading.RLock()

        # Logging
        self._logger = logging.getLogger(__name__)

        # Mark as initialized
        self._initialized = True

        self._logger.info("CBFRegistry initialized (singleton)")

    def register(
        self,
        tier: TierLevel,
        name: str,
        func: BarrierFunction,
        threshold: float = 0.0,
        enabled: bool = True,
        colony: int | None = None,
        description: str = "",
        skip_if_exists: bool = True,
    ) -> bool:
        """Register a barrier function.

        Args:
            tier: Hierarchy level (1=organism, 2=colony, 3=action)
            name: Unique barrier name (must be unique across all tiers)
            func: Barrier function h(x) -> float
            threshold: Safety threshold (default 0.0)
            enabled: Whether barrier is active (default True)
            colony: Colony ID for Tier 2 barriers (0-6)
            description: Human-readable description
            skip_if_exists: If True (default), silently skip duplicates. If False, raise ValueError.

        Returns:
            True if barrier was registered, False if skipped due to existing registration

        Raises:
            ValueError: If barrier name already exists and skip_if_exists=False
            TypeError: If func is not callable

        Example:
            >>> registry.register(
            ...     tier=1,
            ...     name="memory_limit",
            ...     func=lambda s: 0.8 - s['memory_pct'],
            ...     description="Memory usage must stay below 80%"
            ... )
        """
        with self._registry_lock:
            # Check for duplicate name
            if name in self._barriers:
                if skip_if_exists:
                    self._logger.debug(f"Barrier '{name}' already registered, skipping")
                    return False
                raise ValueError(
                    f"Barrier '{name}' already registered (tier {self._barriers[name].tier})"
                )

            # Create entry (validation happens in __post_init__)
            entry = BarrierEntry(
                tier=tier,
                name=name,
                func=func,
                threshold=threshold,
                enabled=enabled,
                colony=colony,
                description=description,
            )

            # Store in main dict[str, Any]
            self._barriers[name] = entry

            # Update indices
            self._tier_index[tier].append(name)
            if colony is not None:
                self._colony_index[colony].append(name)

            self._logger.debug(
                f"Registered barrier '{name}' (tier={tier}, colony={colony}, "
                f"threshold={threshold:.3f}, enabled={enabled})"
            )
            return True

    def unregister(self, name: str) -> None:
        """Unregister a barrier.

        Use sparingly - barriers should generally persist for system lifetime.

        Args:
            name: Barrier name to remove

        Raises:
            KeyError: If barrier not found
        """
        with self._registry_lock:
            if name not in self._barriers:
                raise KeyError(f"Barrier '{name}' not found in registry")

            entry = self._barriers[name]

            # Remove from indices
            self._tier_index[entry.tier].remove(name)
            if entry.colony is not None:
                self._colony_index[entry.colony].remove(name)

            # Remove from main dict[str, Any]
            del self._barriers[name]

            self._logger.warning(f"Unregistered barrier '{name}'")

    def get_barrier(self, name: str) -> BarrierEntry | None:
        """Retrieve barrier entry by name.

        Args:
            name: Barrier name

        Returns:
            BarrierEntry if found, None otherwise
        """
        return self._barriers.get(name)

    def check_all(
        self,
        tier: TierLevel | None = None,
        colony: int | None = None,
        state: StateDict | None = None,
    ) -> dict[str, float]:
        """Check all barriers matching filters.

        Evaluates all barriers that match the specified filters and
        returns their h(x) values.

        Args:
            tier: If specified, only check barriers at this tier
            colony: If specified, only check barriers for this colony
            state: Current state dict[str, Any] to evaluate barriers on

        Returns:
            Dict mapping barrier name -> h(x) value

        Example:
            >>> results = registry.check_all(tier=1, state={'memory': 0.4})
            >>> results
            {'memory_limit': 0.4, 'disk_space': 0.6}
        """
        # Determine which barriers to check
        if colony is not None:
            # Colony filter: check all barriers for this colony
            barrier_names = self._colony_index.get(colony, [])
        elif tier is not None:
            # Tier filter: check all barriers at this tier
            barrier_names = self._tier_index[tier]
        else:
            # No filter: check ALL barriers
            barrier_names = list(self._barriers.keys())

        # Evaluate each barrier
        results: dict[str, float] = {}
        for name in barrier_names:
            entry = self._barriers[name]
            if entry.enabled:
                h_x = entry.evaluate(state)
                results[name] = h_x

        return results

    def is_safe(
        self,
        tier: TierLevel | None = None,
        colony: int | None = None,
        state: StateDict | None = None,
    ) -> bool:
        """Check if all matching barriers are satisfied.

        Args:
            tier: If specified, only check barriers at this tier
            colony: If specified, only check barriers for this colony
            state: Current state dict[str, Any]

        Returns:
            True if ALL matching barriers satisfy h(x) >= threshold, False otherwise

        Example:
            >>> registry.is_safe(tier=1, state={'memory': 0.3})
            True
            >>> registry.is_safe(tier=1, state={'memory': 0.9})
            False
        """
        results = self.check_all(tier=tier, colony=colony, state=state)

        for name, h_x in results.items():
            entry = self._barriers[name]
            if h_x < entry.threshold:
                return False

        return True

    def get_violations(
        self,
        tier: TierLevel | None = None,
        colony: int | None = None,
        state: StateDict | None = None,
    ) -> list[dict[str, Any]]:
        """Get all violated barriers.

        Args:
            tier: If specified, only check barriers at this tier
            colony: If specified, only check barriers for this colony
            state: Current state dict[str, Any]

        Returns:
            List of dicts with violation details:
            - name: Barrier name
            - h_x: Barrier value
            - threshold: Required threshold
            - margin: How far below threshold (negative)
            - tier: Barrier tier
            - colony: Barrier colony (if applicable)
            - description: Barrier description

        Example:
            >>> violations = registry.get_violations(state={'memory': 0.9})
            >>> violations
            [{'name': 'memory_limit', 'h_x': -0.1, 'threshold': 0.0,
              'margin': -0.1, 'tier': 1, 'colony': None,
              'description': 'Memory usage must stay below 80%'}]
        """
        results = self.check_all(tier=tier, colony=colony, state=state)
        violations = []

        for name, h_x in results.items():
            entry = self._barriers[name]
            if h_x < entry.threshold:
                violations.append(
                    {
                        "name": name,
                        "h_x": h_x,
                        "threshold": entry.threshold,
                        "margin": h_x - entry.threshold,
                        "tier": entry.tier,
                        "colony": entry.colony,
                        "description": entry.description,
                    }
                )

        return violations

    def enable(self, name: str) -> None:
        """Enable a barrier.

        Args:
            name: Barrier name

        Raises:
            KeyError: If barrier not found
        """
        with self._registry_lock:
            if name not in self._barriers:
                raise KeyError(f"Barrier '{name}' not found in registry")

            self._barriers[name].enabled = True
            self._logger.info(f"Enabled barrier '{name}'")

    def disable(self, name: str) -> None:
        """Disable a barrier (for debugging only).

        SECURITY WARNING: Disabling barriers reduces system safety.
        Only use for controlled debugging scenarios.

        Args:
            name: Barrier name

        Raises:
            KeyError: If barrier not found
        """
        with self._registry_lock:
            if name not in self._barriers:
                raise KeyError(f"Barrier '{name}' not found in registry")

            self._barriers[name].enabled = False
            self._logger.warning(
                f"⚠️  DISABLED barrier '{name}' - system safety reduced! Only use for debugging."
            )

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Dict with:
            - total_barriers: Total number of registered barriers
            - tier_1: Count of Tier 1 barriers
            - tier_2: Count of Tier 2 barriers
            - tier_3: Count of Tier 3 barriers
            - enabled: Count of enabled barriers
            - disabled: Count of disabled barriers
            - total_evaluations: Sum of all evaluation counts
            - total_violations: Sum of all violation counts

        Example:
            >>> stats = registry.get_stats()
            >>> stats
            {'total_barriers': 15, 'tier_1': 4, 'tier_2': 7, 'tier_3': 4,
             'enabled': 15, 'disabled': 0, 'total_evaluations': 1234,
             'total_violations': 5}
        """
        total_evals = sum(e.evaluation_count for e in self._barriers.values())
        total_violations = sum(e.violation_count for e in self._barriers.values())
        enabled_count = sum(1 for e in self._barriers.values() if e.enabled)

        return {
            "total_barriers": len(self._barriers),
            "tier_1": len(self._tier_index[1]),
            "tier_2": len(self._tier_index[2]),
            "tier_3": len(self._tier_index[3]),
            "enabled": enabled_count,
            "disabled": len(self._barriers) - enabled_count,
            "total_evaluations": total_evals,
            "total_violations": total_violations,
        }

    def list_barriers(
        self,
        tier: TierLevel | None = None,
        colony: int | None = None,
        enabled_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List all barriers matching filters.

        Args:
            tier: If specified, only list[Any] barriers at this tier
            colony: If specified, only list[Any] barriers for this colony
            enabled_only: If True, only list[Any] enabled barriers

        Returns:
            List of barrier info dicts (from BarrierEntry.to_dict())

        Example:
            >>> barriers = registry.list_barriers(tier=1, enabled_only=True)
            >>> barriers[0]
            {'name': 'memory_limit', 'tier': 1, 'enabled': True, ...}
        """
        # Determine which barriers to list[Any]
        if colony is not None:
            barrier_names = self._colony_index.get(colony, [])
        elif tier is not None:
            barrier_names = self._tier_index[tier]
        else:
            barrier_names = list(self._barriers.keys())

        # Filter and convert to dicts
        result = []
        for name in barrier_names:
            entry = self._barriers[name]
            if enabled_only and not entry.enabled:
                continue
            result.append(entry.to_dict())

        return result

    def reset_stats(self) -> None:
        """Reset evaluation and violation counts for all barriers.

        Use this to clear statistics when starting a new training run
        or evaluation phase.
        """
        with self._registry_lock:
            for entry in self._barriers.values():
                entry.evaluation_count = 0
                entry.violation_count = 0
                entry.last_value = None
                entry.last_check = None

            self._logger.info("Reset all barrier statistics")

    @classmethod
    def reset_singleton(cls) -> None:
        """Reset singleton instance (for testing only).

        DANGER: This clears the global registry. Only use in tests.
        """
        with cls._lock:
            cls._instance = None
            # Also reset in centralized registry
            from kagami.core.shared_abstractions.singleton_consolidation import (
                get_singleton_registry,
            )

            get_singleton_registry().reset("cbf_registry")
            logger.warning("CBFRegistry singleton reset - only use in tests!")


# =============================================================================
# INITIALIZATION HELPERS
# =============================================================================


def init_cbf_registry() -> CBFRegistry:
    """Initialize CBF registry with all barriers.

    This function should be called at system startup to register
    all barriers from all tiers.

    HARDENED (Dec 23, 2025): Uses real OrganismBarriers instead of placeholders.

    Currently registers Tier 1 (organism) barriers. Tier 2 (colony)
    barriers are registered by each colony during initialization.
    Tier 3 (action) barriers are registered dynamically.

    Returns:
        Initialized CBFRegistry singleton

    Example:
        >>> registry = init_cbf_registry()
        >>> registry.get_stats()
        {'total_barriers': 4, 'tier_1': 4, ...}
    """
    registry = CBFRegistry()

    # Tier 1: Organism barriers - USE REAL IMPLEMENTATION
    from kagami.core.safety.organism_barriers import get_organism_barriers

    organism_barriers = get_organism_barriers()

    # Wrap OrganismBarriers methods as registry-compatible functions
    def h_memory(state: StateDict | None) -> float:
        """Memory usage barrier via OrganismBarriers."""
        return organism_barriers.h_memory(state)

    def h_process(state: StateDict | None) -> float:
        """Process count barrier via OrganismBarriers."""
        return organism_barriers.h_process(state)

    def h_blanket_integrity(state: StateDict | None) -> float:
        """Markov blanket integrity via OrganismBarriers."""
        return organism_barriers.h_blanket_integrity(state)

    def h_disk_space(state: StateDict | None) -> float:
        """Disk space barrier via OrganismBarriers."""
        return organism_barriers.h_disk_space(state)

    # Register Tier 1 barriers (idempotent - register() skips duplicates by default)
    registry.register(
        tier=1,
        name="organism.memory",
        func=h_memory,
        description="Memory usage must stay below configured threshold (real psutil check)",
    )
    registry.register(
        tier=1,
        name="organism.process",
        func=h_process,
        description="Process count must stay below configured limit (real psutil check)",
    )
    registry.register(
        tier=1,
        name="organism.blanket_integrity",
        func=h_blanket_integrity,
        description="Markov blanket integrity: I(μ; η) must stay below tolerance",
    )
    registry.register(
        tier=1,
        name="organism.disk_space",
        func=h_disk_space,
        description="Disk usage must stay below configured threshold (real shutil check)",
    )

    logger.debug(
        f"CBF registry initialized with {len(registry._barriers)} barriers (using OrganismBarriers)"
    )

    return registry


# =============================================================================
# SINGLETON FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
# Register via the centralized registry for consistency
# Note: CBFRegistry already uses __new__ for singleton, so we register the constructor
get_cbf_registry = _singleton_registry.register_sync("cbf_registry", CBFRegistry)


__all__ = [
    "BarrierEntry",
    "BarrierFunction",
    "CBFRegistry",
    "TierLevel",
    "get_cbf_registry",
    "init_cbf_registry",
]
