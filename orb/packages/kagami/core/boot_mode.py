"""Boot mode detection and dependency graph for K os.

Two modes:
- FULL: All dependencies required with full optimization (production, dev)
- TEST: Mock heavy dependencies (unit tests)

BOOT SEQUENCE (Dec 27, 2025):
Provides explicit dependency ordering for initialization:
1. Core systems (logging, config)
2. Math layer (E8, octonions, Fano)
3. Safety layer (CBF, barriers)
4. World model (RSSM, predictions)
5. Colonies (7 agents)
6. Organism (unified)
7. API (routes, sockets)

Created: December 14, 2025
Updated: December 27, 2025 - Added boot dependency graph
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}


class BootMode(Enum):
    """K os boot modes."""

    FULL = "full"  # All dependencies required with full optimization (production, dev)
    TEST = "test"  # Mock heavy dependencies (unit tests)


def get_boot_mode() -> BootMode:
    """Get current boot mode from environment.

    Returns:
        BootMode enum value

    Environment:
        KAGAMI_BOOT_MODE: "full" (default) or "test"
    """
    # Canonical test-mode flag used across the codebase and in pytest fixtures.
    # This must be checked BEFORE the cached BOOT_MODE is used so that tests that
    # monkeypatch env vars (or rely on conftest defaults) behave deterministically.
    try:
        if os.getenv("KAGAMI_TEST_MODE", "0").lower() in _TRUTHY:
            return BootMode.TEST
    except Exception:
        # Extremely defensive: never let boot-mode detection crash import.
        pass

    # If the suite is running, prefer TEST mode unless explicitly overridden.
    # (PYTEST_CURRENT_TEST is set[Any] by pytest; PYTEST_RUNNING is used in some fixtures.)
    if os.getenv("KAGAMI_BOOT_MODE") is None and (
        os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PYTEST_RUNNING") == "1"
    ):
        return BootMode.TEST

    mode_str = os.getenv("KAGAMI_BOOT_MODE", "full").lower()

    try:
        mode = BootMode(mode_str)
    except ValueError:
        logger.warning(
            f"Invalid boot mode '{mode_str}', defaulting to 'full'. "
            f"Valid modes: {[m.value for m in BootMode]}"
        )
        mode = BootMode.FULL

    if mode != BootMode.FULL:
        logger.info(f"K os boot mode: {mode.value}")

    return mode


# Global boot mode - set[Any] once at import
BOOT_MODE = get_boot_mode()


def is_full_mode() -> bool:
    """Check if running in full mode (all dependencies)."""
    # Respect env flags even if BOOT_MODE was computed before monkeypatching.
    try:
        if os.getenv("KAGAMI_BOOT_MODE", "").lower() == "full":
            return True
        if os.getenv("KAGAMI_BOOT_MODE", "").lower() == "test":
            return False
        if os.getenv("KAGAMI_TEST_MODE", "0").lower() in _TRUTHY:
            return False
        if os.getenv("ENVIRONMENT", "").lower() == "test":
            return False
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PYTEST_RUNNING") == "1":
            return False
    except Exception:
        pass
    return BOOT_MODE == BootMode.FULL


def is_test_mode() -> bool:
    """Check if running in test mode (mocked dependencies)."""
    # Dynamic check so pytest monkeypatch/env fixtures take effect even if
    # kagami.core.boot_mode was imported earlier.
    try:
        if os.getenv("KAGAMI_BOOT_MODE", "").lower() == "test":
            return True
        if os.getenv("KAGAMI_TEST_MODE", "0").lower() in _TRUTHY:
            return True
        if os.getenv("ENVIRONMENT", "").lower() == "test":
            return True
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PYTEST_RUNNING") == "1":
            return True
    except Exception:
        pass
    return BOOT_MODE == BootMode.TEST


def require_full_mode(feature_name: str) -> None:
    """Raise error if not in full mode.

    Args:
        feature_name: Name of feature requiring full mode

    Raises:
        RuntimeError: If not in full mode
    """
    if BOOT_MODE != BootMode.FULL:
        raise RuntimeError(
            f"{feature_name} requires full mode. "
            f"Current mode: {BOOT_MODE.value}. "
            "Set KAGAMI_BOOT_MODE=full"
        )


# =============================================================================
# BOOT DEPENDENCY GRAPH (Dec 27, 2025)
# =============================================================================


class BootPhase(Enum):
    """Boot phases in dependency order."""

    CORE = "core"  # Logging, config, environment
    MATH = "math"  # E8, octonions, Fano plane
    SAFETY = "safety"  # CBF, barriers, constraints
    WORLD_MODEL = "world_model"  # RSSM, predictions
    COLONIES = "colonies"  # 7 agent colonies
    ORGANISM = "organism"  # Unified organism
    API = "api"  # Routes, sockets


@dataclass
class BootComponent:
    """A bootable component with dependencies.

    Attributes:
        name: Component identifier
        phase: Boot phase
        dependencies: List of component names this depends on
        init_fn: Async function to initialize component
        cleanup_fn: Optional async function for cleanup
        timeout: Maximum seconds for initialization
        required: Whether component is required for boot
    """

    name: str
    phase: BootPhase
    dependencies: list[str] = field(default_factory=list[Any])
    init_fn: Callable[[], Any] | None = None
    cleanup_fn: Callable[[], Any] | None = None
    timeout: float = 30.0
    required: bool = True

    # Runtime state
    initialized: bool = False
    init_time: float = 0.0
    error: str | None = None


@dataclass
class BootResult:
    """Result of boot sequence execution."""

    success: bool
    total_time: float
    components_initialized: list[str]
    components_failed: list[str]
    errors: dict[str, str]


class BootSequence:
    """Manages boot sequence with dependency ordering.

    PATTERN (Dec 27, 2025):
    =====================
    Topologically sorts components by dependencies, then initializes
    in order with timeout and error handling.

    Usage:
        boot = BootSequence()
        boot.register("config", BootPhase.CORE, init_fn=init_config)
        boot.register("e8", BootPhase.MATH, dependencies=["config"], init_fn=init_e8)
        result = await boot.execute()
    """

    def __init__(self) -> None:
        """Initialize boot sequence."""
        self._components: dict[str, BootComponent] = {}
        self._boot_order: list[str] = []
        self._started = False
        self._completed = False

    def register(
        self,
        name: str,
        phase: BootPhase,
        dependencies: list[str] | None = None,
        init_fn: Callable[[], Any] | None = None,
        cleanup_fn: Callable[[], Any] | None = None,
        timeout: float = 30.0,
        required: bool = True,
    ) -> None:
        """Register a component for boot.

        Args:
            name: Component identifier
            phase: Boot phase
            dependencies: Components this depends on
            init_fn: Initialization function (sync or async)
            cleanup_fn: Cleanup function (sync or async)
            timeout: Max initialization time
            required: Whether failure blocks boot
        """
        component = BootComponent(
            name=name,
            phase=phase,
            dependencies=dependencies or [],
            init_fn=init_fn,
            cleanup_fn=cleanup_fn,
            timeout=timeout,
            required=required,
        )
        self._components[name] = component
        self._boot_order = []  # Invalidate cached order

    def _compute_order(self) -> list[str]:
        """Compute topological order for boot sequence.

        Returns:
            List of component names in dependency order

        Raises:
            ValueError: If circular dependency detected
        """
        if self._boot_order:
            return self._boot_order

        # Kahn's algorithm for topological sort
        in_degree: dict[str, int] = dict[str, Any].fromkeys(self._components, 0)
        for name, comp in self._components.items():
            for dep in comp.dependencies:
                if dep not in self._components:
                    logger.warning(f"Unknown dependency {dep} for {name}")
                    continue
                in_degree[name] += 1

        # Start with nodes that have no dependencies
        queue = [name for name, deg in in_degree.items() if deg == 0]

        # Sort by phase for deterministic order within same dependency level
        phase_order = {phase: i for i, phase in enumerate(BootPhase)}
        queue.sort(key=lambda n: phase_order[self._components[n].phase])

        result = []
        while queue:
            current = queue.pop(0)
            result.append(current)

            # Reduce in-degree for dependents
            for name, comp in self._components.items():
                if current in comp.dependencies:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)
                        queue.sort(key=lambda n: phase_order[self._components[n].phase])

        if len(result) != len(self._components):
            remaining = set(self._components.keys()) - set(result)
            raise ValueError(f"Circular dependency detected involving: {remaining}")

        self._boot_order = result
        return result

    async def execute(self) -> BootResult:
        """Execute boot sequence.

        Returns:
            BootResult with success status and timing
        """
        self._started = True
        start_time = time.time()

        order = self._compute_order()
        initialized = []
        failed = []
        errors = {}

        logger.info(f"Boot sequence starting: {len(order)} components")

        for name in order:
            comp = self._components[name]

            # Check dependencies
            deps_ok = all(
                self._components[d].initialized for d in comp.dependencies if d in self._components
            )
            if not deps_ok:
                if comp.required:
                    failed.append(name)
                    errors[name] = "Dependencies not satisfied"
                    logger.error(f"Boot {name}: dependencies not satisfied")
                continue

            # Initialize component
            try:
                if comp.init_fn is not None:
                    comp_start = time.time()

                    # Handle both sync and async init functions
                    if asyncio.iscoroutinefunction(comp.init_fn):
                        await asyncio.wait_for(comp.init_fn(), timeout=comp.timeout)
                    else:
                        await asyncio.wait_for(
                            asyncio.to_thread(comp.init_fn),
                            timeout=comp.timeout,
                        )

                    comp.init_time = time.time() - comp_start

                comp.initialized = True
                initialized.append(name)
                logger.debug(f"Boot {name}: OK ({comp.init_time:.3f}s)")

            except TimeoutError:
                comp.error = f"Timeout after {comp.timeout}s"
                if comp.required:
                    failed.append(name)
                    errors[name] = comp.error
                    logger.error(f"Boot {name}: {comp.error}")
                else:
                    logger.warning(f"Boot {name}: {comp.error} (non-required)")

            except Exception as e:
                comp.error = str(e)
                if comp.required:
                    failed.append(name)
                    errors[name] = comp.error
                    logger.error(f"Boot {name}: {comp.error}")
                else:
                    logger.warning(f"Boot {name}: {comp.error} (non-required)")

        total_time = time.time() - start_time
        self._completed = True

        success = len(failed) == 0
        logger.info(
            f"Boot sequence {'complete' if success else 'FAILED'}: "
            f"{len(initialized)}/{len(order)} components, {total_time:.2f}s"
        )

        return BootResult(
            success=success,
            total_time=total_time,
            components_initialized=initialized,
            components_failed=failed,
            errors=errors,
        )

    async def shutdown(self) -> None:
        """Execute cleanup in reverse boot order."""
        if not self._completed:
            logger.warning("Shutdown called before boot completed")
            return

        order = list(reversed(self._compute_order()))

        for name in order:
            comp = self._components[name]
            if not comp.initialized:
                continue

            if comp.cleanup_fn is not None:
                try:
                    if asyncio.iscoroutinefunction(comp.cleanup_fn):
                        await asyncio.wait_for(comp.cleanup_fn(), timeout=10.0)
                    else:
                        await asyncio.wait_for(
                            asyncio.to_thread(comp.cleanup_fn),
                            timeout=10.0,
                        )
                    logger.debug(f"Cleanup {name}: OK")
                except Exception as e:
                    logger.error(f"Cleanup {name}: {e}")

            comp.initialized = False

    def get_status(self) -> dict[str, Any]:
        """Get boot sequence status."""
        return {
            "started": self._started,
            "completed": self._completed,
            "components": {
                name: {
                    "phase": comp.phase.value,
                    "initialized": comp.initialized,
                    "init_time": comp.init_time,
                    "error": comp.error,
                    "dependencies": comp.dependencies,
                }
                for name, comp in self._components.items()
            },
            "order": self._boot_order,
        }


# Global boot sequence instance
_boot_sequence: BootSequence | None = None


def get_boot_sequence() -> BootSequence:
    """Get or create the global boot sequence."""
    global _boot_sequence
    if _boot_sequence is None:
        _boot_sequence = BootSequence()
    return _boot_sequence


# =============================================================================
# STANDARD BOOT COMPONENTS
# =============================================================================


def register_standard_components() -> None:
    """Register standard Kagami boot components.

    Call this to set[Any] up the default boot sequence.
    """
    boot = get_boot_sequence()

    # Phase 1: Core
    boot.register("logging", BootPhase.CORE)
    boot.register("config", BootPhase.CORE, dependencies=["logging"])

    # Phase 2: Math
    boot.register("e8_lattice", BootPhase.MATH, dependencies=["config"], required=False)
    boot.register("octonions", BootPhase.MATH, dependencies=["config"], required=False)
    boot.register("fano_plane", BootPhase.MATH, dependencies=["octonions"], required=False)

    # Phase 3: Safety
    boot.register(
        "cbf",
        BootPhase.SAFETY,
        dependencies=["config"],
        timeout=10.0,
    )
    boot.register("barriers", BootPhase.SAFETY, dependencies=["cbf"])

    # Phase 4: World Model
    boot.register(
        "rssm",
        BootPhase.WORLD_MODEL,
        dependencies=["e8_lattice", "barriers"],
        timeout=60.0,
    )
    boot.register("predictions", BootPhase.WORLD_MODEL, dependencies=["rssm"])

    # Phase 5: Colonies
    for colony in ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]:
        boot.register(
            f"colony_{colony}",
            BootPhase.COLONIES,
            dependencies=["fano_plane", "cbf"],
            timeout=15.0,
        )

    # Phase 6: Organism
    boot.register(
        "organism",
        BootPhase.ORGANISM,
        dependencies=[
            f"colony_{c}" for c in ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
        ],
        timeout=30.0,
    )

    # 🔥 FORGE COLONY: Smart home organism bridge (after organism, before API)
    boot.register(
        "smart_home_organism",
        BootPhase.ORGANISM,
        dependencies=["organism"],
        timeout=45.0,
        required=False,  # Optional for systems without smart home
    )

    # Phase 7: API
    boot.register("api_routes", BootPhase.API, dependencies=["organism"])
    boot.register("api_sockets", BootPhase.API, dependencies=["organism"])

    logger.debug(f"Registered {len(boot._components)} boot components")
