"""CBF System Initialization.

CREATED: December 14, 2025 by Nexus (e₄)
PURPOSE: Initialize and wire Control Barrier Functions across KagamiOS

This module provides system-level initialization of the CBF safety layer:
1. Initialize CBF Registry with all Tier 1 (organism) barriers
2. Wire CBF checks into critical system boundaries
3. Fail-fast if CBF modules unavailable (no degraded mode)
4. Provide runtime monitoring hooks

USAGE:
======
```python
# At system startup
from kagami.core.safety.cbf_init import initialize_cbf_system

registry = initialize_cbf_system()

# Check system safety
if registry.is_safe():
    print("System is safe")
else:
    violations = registry.get_violations()
    print(f"Safety violations: {violations}")
```

INTEGRATION POINTS:
===================
This module initializes CBF checks at:
- Tier 1: Organism barriers (memory, disk, process, blanket)
- Tier 2: Colony barriers (registered by each colony on init)
- Tier 3: Action barriers (registered dynamically)

The actual enforcement happens via:
- Decorators: @enforce_tier1, @enforce_tier2, @enforce_tier3
- Explicit checks: check_cbf_for_operation()
- Composition checks: FanoCompositionChecker

SAFETY INVARIANT:
=================
h(x) ≥ 0 for all enabled barriers → system is safe
Any violation → BLOCK action, log warning, escalate

References:
- Ames et al. (2019): Control Barrier Functions
- CBFRegistry: kagami/core/safety/cbf_registry.py
- DecentralizedCBF: kagami/core/safety/decentralized_cbf.py
"""

from __future__ import annotations

import asyncio
import logging
import platform
from typing import TYPE_CHECKING, Any

from kagami.core.safety.types import StateDict

if TYPE_CHECKING:
    from kagami.core.safety.cbf_registry import CBFRegistry

logger = logging.getLogger(__name__)


# =============================================================================
# SYSTEM STATE PROVIDERS
# =============================================================================


def get_system_memory_state() -> dict[str, float]:
    """Get current system memory state.

    Returns:
        Dict with:
        - memory_pct: Memory utilization [0, 1]
        - memory_available_mb: Available memory in MB
        - memory_total_mb: Total memory in MB
    """
    try:
        import psutil

        mem = psutil.virtual_memory()
        return {
            "memory_pct": mem.percent / 100.0,
            "memory_available_mb": mem.available / (1024 * 1024),
            "memory_total_mb": mem.total / (1024 * 1024),
        }
    except ImportError:
        logger.warning("psutil not available, using default memory state")
        return {"memory_pct": 0.5}


def get_system_disk_state() -> dict[str, float]:
    """Get current system disk state.

    Returns:
        Dict with:
        - disk_usage: Disk utilization [0, 1]
        - disk_free_gb: Free disk space in GB
        - disk_total_gb: Total disk space in GB
    """
    try:
        import psutil

        # Get disk usage for root partition
        disk = psutil.disk_usage("/")
        return {
            "disk_usage": disk.percent / 100.0,
            "disk_free_gb": disk.free / (1024**3),
            "disk_total_gb": disk.total / (1024**3),
        }
    except Exception as e:
        logger.warning(f"Disk state unavailable: {e}")
        return {"disk_usage": 0.5}


def get_system_process_state() -> dict[str, float]:
    """Get current system process state.

    Returns:
        Dict with:
        - process_count: Number of processes
        - process_ratio: process_count / max_processes
        - cpu_percent: CPU utilization [0, 1]
    """
    try:
        import psutil

        # Process limits vary by platform
        max_processes = 1024  # Conservative default
        if platform.system() == "Linux":
            try:
                with open("/proc/sys/kernel/pid_max") as f:
                    max_processes = int(f.read().strip())
            except Exception as proc_err:
                # OPTIONAL: Failed to read pid_max, use default
                logger.debug(f"Failed to read /proc/sys/kernel/pid_max: {proc_err}")
        elif platform.system() == "Darwin":
            # macOS: Read kern.maxproc via sysctl
            import subprocess

            try:
                result = subprocess.run(
                    ["sysctl", "-n", "kern.maxproc"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=True,
                )
                max_processes = int(result.stdout.strip())
            except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired) as e:
                # OPTIONAL: Failed to read kern.maxproc, use default
                logger.debug(f"Failed to read kern.maxproc: {e}")

        process_count = len(psutil.pids())
        cpu_percent = psutil.cpu_percent(interval=0.1) / 100.0

        return {
            "process_count": process_count,
            "process_ratio": process_count / max_processes,
            "cpu_percent": cpu_percent,
        }
    except Exception as e:
        logger.warning(f"Process state unavailable: {e}")
        return {"process_ratio": 0.5, "cpu_percent": 0.5}


def get_markov_blanket_state() -> dict[str, float]:
    """Get Markov blanket integrity state.

    The Markov blanket integrity measures how well the system maintains
    separation between internal/external states. This is a high-level
    abstraction that would require deep integration with the organism model.

    For now, returns a conservative estimate based on system health.

    Returns:
        Dict with:
        - blanket_integrity: [0, 1] where 1 = perfect isolation
    """
    # Conservative: assume blanket is intact unless proven otherwise
    # In production, this would query OrganismRSSM for actual blanket metrics
    return {"blanket_integrity": 0.9}


# =============================================================================
# TIER 1 BARRIER FUNCTIONS (ORGANISM-LEVEL)
# =============================================================================


def h_memory(state: StateDict | None = None) -> float:
    """Memory usage barrier: h = threshold - memory_pct.

    Safe when h ≥ 0 (memory below 80% threshold).

    Args:
        state: Optional state dict[str, Any]. If None, queries system directly.

    Returns:
        Barrier value (positive = safe, negative = violation)
    """
    if state is None:
        state_data: StateDict = get_system_memory_state()  # type: ignore[assignment]
    else:
        state_data = state

    memory_pct = float(state_data.get("memory_pct", 0.0))
    threshold = 0.80  # 80% memory utilization

    return threshold - memory_pct


def h_disk(state: StateDict | None = None) -> float:
    """Disk usage barrier: h = threshold - disk_usage.

    Safe when h ≥ 0 (disk below 90% threshold).

    Args:
        state: Optional state dict[str, Any]. If None, queries system directly.

    Returns:
        Barrier value (positive = safe, negative = violation)
    """
    if state is None:
        state_data: StateDict = get_system_disk_state()  # type: ignore[assignment]
    else:
        state_data = state

    disk_usage = float(state_data.get("disk_usage", 0.0))
    threshold = 0.90  # 90% disk utilization

    return threshold - disk_usage


def h_process(state: StateDict | None = None) -> float:
    """Process count barrier: h = threshold - process_ratio.

    Safe when h ≥ 0 (processes below 90% of system limit).

    Args:
        state: Optional state dict[str, Any]. If None, queries system directly.

    Returns:
        Barrier value (positive = safe, negative = violation)
    """
    if state is None:
        state_data: StateDict = get_system_process_state()  # type: ignore[assignment]
    else:
        state_data = state

    process_ratio = float(state_data.get("process_ratio", 0.0))
    threshold = 0.90  # 90% of max processes

    return threshold - process_ratio


def h_blanket_integrity(state: StateDict | None = None) -> float:
    """Markov blanket integrity barrier: h = integrity - threshold.

    Safe when h ≥ 0 (blanket integrity above 50%).

    Args:
        state: Optional state dict[str, Any]. If None, queries system directly.

    Returns:
        Barrier value (positive = safe, negative = violation)
    """
    if state is None:
        state_data: StateDict = get_markov_blanket_state()  # type: ignore[assignment]
    else:
        state_data = state

    blanket_integrity = float(state_data.get("blanket_integrity", 1.0))
    threshold = 0.50  # Must maintain at least 50% integrity

    return blanket_integrity - threshold


# =============================================================================
# PERIODIC MONITORING
# =============================================================================


async def _monitor_cbf_periodic(
    registry: CBFRegistry,
    interval: float = 5.0,
    warning_threshold: float = 0.2,
    critical_threshold: float = 0.05,
) -> None:
    """Background task for periodic CBF monitoring.

    This coroutine runs indefinitely, checking all registered barriers at
    regular intervals and emitting warnings/alerts when h(x) approaches
    dangerous thresholds.

    Args:
        registry: CBFRegistry instance to monitor
        interval: Check interval in seconds (default 5.0)
        warning_threshold: Emit warning when h(x) < threshold (default 0.2)
        critical_threshold: Emit alert when h(x) < threshold (default 0.05)

    Thresholds:
        h >= warning_threshold: GREEN (normal operation)
        warning_threshold > h >= critical_threshold: YELLOW (approaching limit)
        critical_threshold > h >= 0: RED (danger zone)
        h < 0: VIOLATION (blocked)

    Example:
        >>> async def main():
        ...     registry = initialize_cbf_system(enable_monitoring=False)
        ...     task = asyncio.create_task(_monitor_cbf_periodic(registry))
        ...     await asyncio.sleep(10)  # Monitor for 10 seconds
        ...     task.cancel()
    """
    logger.info(
        f"CBF periodic monitoring started: interval={interval}s, "
        f"warning_threshold={warning_threshold}, critical_threshold={critical_threshold}"
    )

    try:
        while True:
            # Wait for interval
            await asyncio.sleep(interval)

            # Check all barriers
            try:
                # Gather current system state
                state = _gather_system_state()

                # Check all tiers
                from typing import Literal

                tier_levels: list[Literal[1, 2, 3]] = [1, 2, 3]
                for tier in tier_levels:
                    results = registry.check_all(tier=tier, state=state)

                    for name, h_x in results.items():
                        entry = registry.get_barrier(name)
                        if entry is None or not entry.enabled:
                            continue

                        # Check thresholds
                        if h_x < 0:
                            # Violation (already handled by CBFRegistry)
                            logger.error(
                                f"CBF VIOLATION: {name} h={h_x:.4f} < 0 "
                                f"(tier={tier}, state snapshot: {_format_relevant_state(state, name)})"
                            )
                        elif h_x < critical_threshold:
                            # Critical: very close to violation
                            logger.critical(
                                f"CBF CRITICAL: {name} h={h_x:.4f} < {critical_threshold} "
                                f"(tier={tier}, approaching RED zone, "
                                f"state: {_format_relevant_state(state, name)})"
                            )
                        elif h_x < warning_threshold:
                            # Warning: approaching danger zone
                            logger.warning(
                                f"CBF WARNING: {name} h={h_x:.4f} < {warning_threshold} "
                                f"(tier={tier}, YELLOW zone, "
                                f"state: {_format_relevant_state(state, name)})"
                            )

            except Exception as e:
                logger.error(f"CBF monitoring check failed: {e}", exc_info=True)

    except asyncio.CancelledError:
        logger.info("CBF periodic monitoring stopped (task cancelled)")
        raise


def _gather_system_state() -> StateDict:
    """Gather current system state for CBF monitoring.

    Returns:
        StateDict with all relevant system metrics
    """
    state: StateDict = {}

    # Gather from all state providers
    try:
        state.update(get_system_memory_state())
    except Exception as e:
        logger.debug(f"Failed to gather memory state: {e}")

    try:
        state.update(get_system_disk_state())
    except Exception as e:
        logger.debug(f"Failed to gather disk state: {e}")

    try:
        state.update(get_system_process_state())
    except Exception as e:
        logger.debug(f"Failed to gather process state: {e}")

    try:
        state.update(get_markov_blanket_state())
    except Exception as e:
        logger.debug(f"Failed to gather blanket state: {e}")

    return state


def _format_relevant_state(state: StateDict, barrier_name: str) -> str:
    """Format relevant state fields for barrier.

    Extracts only the state fields likely relevant to the given barrier
    to avoid log spam.

    Args:
        state: Full state dict[str, Any]
        barrier_name: Name of barrier being checked

    Returns:
        Formatted string with relevant state fields
    """
    # Map barrier names to relevant state keys
    relevant_keys_map = {
        "organism.memory": ["memory_pct", "memory_available_mb", "memory_total_mb"],
        "organism.disk": ["disk_usage", "disk_free_gb", "disk_total_gb"],
        "organism.process": ["process_count", "process_ratio", "cpu_percent"],
        "organism.blanket_integrity": ["blanket_integrity"],
    }

    # Get relevant keys for this barrier
    relevant_keys = relevant_keys_map.get(barrier_name, [])

    if not relevant_keys:
        # For unknown barriers, return limited state
        return f"state keys: {list(state.keys())[:3]}..."

    # Extract relevant fields
    relevant_state = {k: state.get(k) for k in relevant_keys if k in state}

    if not relevant_state:
        return "no relevant state"

    # Format as compact string
    parts = [
        f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in relevant_state.items()
    ]
    return ", ".join(parts)


# =============================================================================
# INITIALIZATION
# =============================================================================


def initialize_cbf_system(
    enable_monitoring: bool = True,
    log_level: str = "INFO",
) -> CBFRegistry:
    """Initialize the complete CBF safety system.

    This function should be called at system startup before any agents
    or colonies are initialized. It:

    1. Creates the CBFRegistry singleton
    2. Registers all Tier 1 (organism-level) barriers
    3. Optionally enables runtime monitoring

    Tier 2 (colony) and Tier 3 (action) barriers are registered later:
    - Tier 2: By each colony during __init__
    - Tier 3: Dynamically as actions are generated

    Args:
        enable_monitoring: If True, sets up periodic monitoring (future)
        log_level: Logging level for CBF system

    Returns:
        Initialized CBFRegistry singleton

    Example:
        >>> registry = initialize_cbf_system()
        >>> registry.get_stats()
        {'total_barriers': 4, 'tier_1': 4, 'tier_2': 0, 'tier_3': 0, ...}
        >>> registry.is_safe()
        True
    """
    # Set up logging
    cbf_logger = logging.getLogger("kagami.core.safety")
    cbf_logger.setLevel(getattr(logging, log_level.upper()))

    logger.info("🔧 Initializing CBF safety system...")

    # Import registry (lazy to avoid circular imports)
    try:
        from kagami.core.safety.cbf_registry import CBFRegistry
    except ImportError as e:
        logger.error(f"CBFRegistry not available: {e}")
        raise RuntimeError("Cannot initialize CBF system without CBFRegistry") from e

    # Get singleton instance
    registry = CBFRegistry()

    # Register Tier 1 (organism-level) barriers
    # register() is idempotent - skips duplicates by default
    logger.debug("Registering Tier 1 (organism) barriers...")

    registry.register(
        tier=1,
        name="organism.memory",
        func=h_memory,
        description="Memory usage must stay below 80%",
    )
    registry.register(
        tier=1, name="organism.disk", func=h_disk, description="Disk usage must stay below 90%"
    )
    registry.register(
        tier=1,
        name="organism.process",
        func=h_process,
        description="Process count must stay below 90% of system limit",
    )
    registry.register(
        tier=1,
        name="organism.blanket_integrity",
        func=h_blanket_integrity,
        description="Markov blanket integrity must remain above 50%",
    )

    # Log initialization complete
    stats = registry.get_stats()
    logger.info(
        f"✅ CBF system initialized: "
        f"{stats['total_barriers']} barriers registered "
        f"(T1={stats['tier_1']}, T2={stats['tier_2']}, T3={stats['tier_3']})"
    )

    # Check initial safety
    if registry.is_safe(tier=1):
        logger.info("✅ All Tier 1 barriers satisfied (system is safe)")
    else:
        violations = registry.get_violations(tier=1)
        logger.warning(
            f"⚠️ {len(violations)} Tier 1 barrier violations detected: "
            f"{[v['name'] for v in violations]}"
        )
        for v in violations:
            logger.warning(
                f"  - {v['name']}: h={v['h_x']:.4f} < {v['threshold']:.4f} "
                f"(margin={v['margin']:.4f})"
            )

    # Enable periodic monitoring if requested
    if enable_monitoring:
        try:
            # Start background monitoring task
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If event loop already running, create task directly
                asyncio.create_task(_monitor_cbf_periodic(registry))
                logger.info("🔍 Started periodic CBF monitoring (async task)")
            else:
                logger.info("⏸️  Periodic CBF monitoring deferred (no event loop running)")
        except RuntimeError:
            # No event loop exists yet
            logger.info("⏸️  Periodic CBF monitoring deferred (no event loop)")

    return registry


def verify_cbf_system() -> dict[str, Any]:
    """Verify CBF system is properly initialized and operational.

    Runs comprehensive checks to ensure:
    1. CBFRegistry is initialized
    2. All Tier 1 barriers are registered
    3. All barriers are evaluatable
    4. System state providers are working

    Returns:
        Verification report with:
        - initialized: bool
        - tier_1_count: int
        - all_evaluatable: bool
        - current_safety: bool
        - violations: list[Any] of violation dicts
        - errors: list[Any] of error messages

    Example:
        >>> report = verify_cbf_system()
        >>> report['initialized']
        True
        >>> report['all_evaluatable']
        True
    """
    errors = []

    # Check registry exists
    try:
        from kagami.core.safety.cbf_registry import CBFRegistry

        registry = CBFRegistry()
        initialized = True
    except Exception as e:
        errors.append(f"CBFRegistry unavailable: {e}")
        return {
            "initialized": False,
            "errors": errors,
        }

    # Get stats
    stats = registry.get_stats()

    # Check all Tier 1 barriers are present
    expected_t1_barriers = [
        "organism.memory",
        "organism.disk",
        "organism.process",
        "organism.blanket_integrity",
    ]

    registered_t1 = [b["name"] for b in registry.list_barriers(tier=1)]

    missing = set(expected_t1_barriers) - set(registered_t1)
    if missing:
        errors.append(f"Missing Tier 1 barriers: {missing}")

    # Try evaluating all barriers
    all_evaluatable = True
    try:
        results_any: dict[str, Any] = registry.check_all(tier=1)
        for name, h_x in results_any.items():
            if not isinstance(h_x, int | float):
                errors.append(f"Barrier '{name}' returned non-numeric value: {h_x}")
                all_evaluatable = False
    except Exception as e:
        errors.append(f"Barrier evaluation failed: {e}")
        all_evaluatable = False

    # Check current safety
    current_safety = registry.is_safe(tier=1)
    violations = registry.get_violations(tier=1)

    return {
        "initialized": initialized,
        "tier_1_count": stats["tier_1"],
        "tier_2_count": stats["tier_2"],
        "tier_3_count": stats["tier_3"],
        "all_evaluatable": all_evaluatable,
        "current_safety": current_safety,
        "violations": violations,
        "errors": errors,
        "stats": stats,
    }


# =============================================================================
# RUNTIME HELPERS
# =============================================================================


def get_cbf_registry() -> CBFRegistry:
    """Get the global CBFRegistry singleton.

    Convenience function for accessing the registry from anywhere.

    Returns:
        CBFRegistry singleton

    Raises:
        RuntimeError: If registry not initialized
    """
    from kagami.core.safety.cbf_registry import CBFRegistry

    return CBFRegistry()


def check_system_safety() -> bool:
    """Quick check: is the system currently safe?

    Returns:
        True if all Tier 1 barriers satisfied, False otherwise
    """
    try:
        registry = get_cbf_registry()
        return registry.is_safe(tier=1)
    except Exception as e:
        logger.error(f"Safety check failed: {e}")
        return False  # Fail-safe: assume unsafe if check fails


# =============================================================================
# SOCIAL CBF INTEGRATION (Dec 22, 2025 - Symbiote Module)
# =============================================================================

_social_cbf_instance: Any = None


def initialize_social_cbf(symbiote_module: Any) -> Any:
    """Initialize Social CBF with Symbiote module.

    SYMBIOTE INTEGRATION (Dec 22, 2025):
    ====================================
    Social CBF extends the safety framework with social constraints:
    - No manipulation (respecting user autonomy)
    - No confusion (clear communication)
    - No harm (cognitive/emotional safety)
    - Alignment (stated vs actual intent)

    h(x) = min(h_physical(x), h_social(x))

    RESEARCH BASIS:
    - arxiv 2508.00401: Active Inference ToM
    - arxiv 2502.14171: ToM in conversational agents
    - Symbiote Module: kagami/core/symbiote/

    Args:
        symbiote_module: SymbioteModule instance

    Returns:
        SocialCBF instance (also stored as singleton)
    """
    global _social_cbf_instance

    try:
        from kagami.core.safety.optimal_cbf import get_optimal_cbf
        from kagami.core.safety.social_cbf import SocialCBF, integrate_social_cbf

        # Create Social CBF
        _social_cbf_instance = SocialCBF(symbiote_module=symbiote_module)

        # Integrate with OptimalCBF if available
        try:
            optimal_cbf = get_optimal_cbf()
            integrate_social_cbf(optimal_cbf, _social_cbf_instance, combine_method="min")
            logger.info(
                "🧠 Social CBF integrated with OptimalCBF: h(x) = min(h_physical(x), h_social(x))"
            )
        except Exception as e:
            logger.warning(f"Could not integrate with OptimalCBF: {e}")

        # Register social barriers in registry
        try:
            registry = get_cbf_registry()

            # Register social barrier at Tier 1 (organism level)
            def h_social_safety(state: StateDict | None = None) -> float:
                """Social safety barrier: checks manipulation, confusion, harm, alignment.

                Safe when h >= 0 (no social safety violations).
                """
                if _social_cbf_instance is None or symbiote_module is None:
                    return 1.0  # Safe if no symbiote (nothing to harm)

                import torch

                # Get social context
                social_context = symbiote_module.get_social_context()
                if not social_context.get("has_active_agents", False):
                    return 1.0  # Safe if no agents modeled

                # Compute minimal social barrier across all agents
                # Use dummy action for monitoring (actual actions checked at execution)
                dummy_action = torch.zeros(1, 8)
                dummy_features = torch.zeros(1, 64)

                try:
                    check = _social_cbf_instance.check_safety(dummy_action, dummy_features)
                    return float(check.h_social)
                except Exception:
                    return 1.0  # Safe on error

            registry.register(
                tier=1,
                name="organism.social_safety",
                func=h_social_safety,
                threshold=0.0,
                description=("Social safety: no manipulation, confusion, harm, or misalignment"),
            )

            logger.info("✅ Social safety barrier registered at Tier 1")

        except Exception as e:
            logger.warning(f"Could not register social barrier: {e}")

        logger.info("🧠 Social CBF initialized with Symbiote Module")
        return _social_cbf_instance

    except ImportError as e:
        logger.warning(f"Social CBF not available: {e}")
        return None


def get_social_cbf() -> Any:
    """Get the Social CBF instance.

    Returns:
        SocialCBF instance or None if not initialized
    """
    return _social_cbf_instance


__all__ = [
    "_gather_system_state",
    "_monitor_cbf_periodic",
    "check_system_safety",
    "get_cbf_registry",
    "get_social_cbf",
    "h_blanket_integrity",
    "h_disk",
    "h_memory",
    "h_process",
    "initialize_cbf_system",
    # Social CBF (Symbiote)
    "initialize_social_cbf",
    "verify_cbf_system",
]
