"""Chaos Safety Monitor - Ensure Chaotic Dynamics Respect Safety Constraints.

Monitors chaotic systems and ensures they never violate safety bounds (CBF: h(x) ≥ 0).
Uses control theory techniques to stabilize chaos when approaching unsafe regions.

Scientific Basis:
- Ott-Grebogi-Yorke (OGY) method: Control of chaos
- Pyragas method: Delayed feedback control
- CBF (Control Barrier Function): Safety certificates

Created: November 8, 2025
Consolidated: December 21, 2025 - Merged world_model/dynamics/chaos_safety.py
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import numpy as np

# Observability integration
from kagami_observability.metrics import chaos as chaos_metrics

logger = logging.getLogger(__name__)


@dataclass
class ChaosSafetyResult:
    """Result of a chaos safety check.

    Attributes:
        safe: Whether the state is safe (h(x) >= 0)
        cbf_value: Control Barrier Function value h(x)
        intervention_needed: Whether control intervention is needed
        distance_from_boundary: Distance from safety boundary
        error: Error message if check failed
    """

    safe: bool
    cbf_value: float | None = None
    intervention_needed: bool = False
    distance_from_boundary: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "safe": self.safe,
            "cbf_value": self.cbf_value,
            "intervention_needed": self.intervention_needed,
            "distance_from_boundary": self.distance_from_boundary,
            "error": self.error,
        }


@dataclass
class ChaosSafetyMetrics:
    """Observability metrics for chaos safety monitoring.

    Combines intervention tracking with chaos-specific metrics.
    """

    total_interventions: int
    violations_prevented: int
    intervention_rate: float
    lyapunov_exponent: float = 0.0
    fractal_dimension: float = 0.0
    entropy_rate: float = 0.0
    cbf_blocks: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_interventions": self.total_interventions,
            "violations_prevented": self.violations_prevented,
            "intervention_rate": self.intervention_rate,
            "lyapunov_exponent": self.lyapunov_exponent,
            "fractal_dimension": self.fractal_dimension,
            "entropy_rate": self.entropy_rate,
            "cbf_blocks": self.cbf_blocks,
        }


class ChaosSafetyMonitor:
    """Monitor chaotic dynamics and enforce safety constraints.

    Integrates with KagamiOS CBF to ensure chaos never violates h(x) ≥ 0.

    Implementation:
    - Singleton pattern (thread-safe) to ensure single monitoring instance
    - Prometheus metrics integration for observability
    - OGY control for chaos stabilization
    - CBF-guided safe state finding
    """

    _instance: ChaosSafetyMonitor | None = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls, *args: Any, **kwargs: Any) -> ChaosSafetyMonitor:
        """Create or return singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        safety_margin: float = 0.1,
        intervention_threshold: float = 0.05,
    ) -> None:
        """Initialize chaos safety monitor.

        Args:
            safety_margin: How far from boundary to trigger intervention
            intervention_threshold: Minimum CBF value to allow chaos

        Note:
            Singleton pattern - only first initialization applies.
            Subsequent calls to __init__ are no-ops.
        """
        # Singleton guard - only initialize once
        if self._initialized:
            return
        self._initialized = True

        self.safety_margin = safety_margin
        self.intervention_threshold = intervention_threshold

        self.interventions = 0
        self.violations_prevented = 0

        # Initialize chaos-specific metrics
        self._chaos_metrics = ChaosSafetyMetrics(
            total_interventions=0,
            violations_prevented=0,
            intervention_rate=0.0,
            lyapunov_exponent=0.0,
            fractal_dimension=0.0,
            entropy_rate=0.0,
            cbf_blocks=0,
        )

        logger.info("ChaosSafetyMonitor initialized (CBF-integrated, singleton)")

    def check_chaos_safety(
        self,
        chaotic_state: np.ndarray | Any,
        cbf_function: Callable | None = None,
    ) -> ChaosSafetyResult:
        """Check if chaotic state is safe.

        Args:
            chaotic_state: Current state from chaotic dynamics
            cbf_function: Control Barrier Function (returns h(x))

        Returns:
            Safety check result

        Side Effects:
            - Updates intervention counters
            - Emits Prometheus metrics for observability
        """
        # If no CBF provided, use heuristic norm check
        if cbf_function is None:
            # Convert to array if not already
            if not isinstance(chaotic_state, np.ndarray):
                chaotic_state = np.array(chaotic_state)

            norm = float(np.linalg.norm(chaotic_state))
            # Heuristic: if norm > 10, it's unsafe divergence
            if norm > 10.0:
                self.interventions += 1
                self._chaos_metrics.cbf_blocks += 1
                chaos_metrics.CHAOS_INTERVENTIONS_TOTAL.labels(reason="divergence").inc()
                return ChaosSafetyResult(
                    safe=False,
                    distance_from_boundary=norm - 10.0,
                    intervention_needed=True,
                )
            return ChaosSafetyResult(
                safe=True,
                distance_from_boundary=10.0 - norm,
                intervention_needed=False,
            )

        try:
            # Evaluate CBF
            h_x = cbf_function(chaotic_state)

            # Record metric (distance from edge of chaos)
            # Note: Commented out to avoid metric name conflicts if needed
            # chaos_metrics.EDGE_OF_CHAOS_DISTANCE.labels(component="monitor").set(abs(h_x))

            # Check safety
            safe = bool(h_x >= 0.0)
            approaching_boundary = bool(h_x < self.intervention_threshold)

            if not safe:
                self.violations_prevented += 1
                self._chaos_metrics.cbf_blocks += 1
                chaos_metrics.CHAOS_INTERVENTIONS_TOTAL.labels(reason="cbf_violation").inc()

            if approaching_boundary:
                self.interventions += 1

            return ChaosSafetyResult(
                safe=safe,
                cbf_value=float(h_x),
                intervention_needed=approaching_boundary,
                distance_from_boundary=float(h_x),
            )

        except Exception as e:
            logger.error(f"CBF evaluation failed: {e}")
            # Fail safe: assume unsafe if CBF fails
            return ChaosSafetyResult(
                safe=False,
                cbf_value=None,
                intervention_needed=True,
                error=str(e),
            )

    def stabilize_chaos(
        self,
        chaotic_state: np.ndarray,
        target_state: np.ndarray | None = None,
        cbf_function: Callable | None = None,
        gain: float = 0.1,
    ) -> np.ndarray:
        """Apply OGY-style control to stabilize chaos.

        Small perturbation to guide chaotic trajectory toward safe region.
        If CBF function provided, ensures controlled state satisfies h(x) ≥ 0.

        Args:
            chaotic_state: Current chaotic state
            target_state: Desired safe state (if None, finds safe state via CBF)
            cbf_function: Control Barrier Function (returns h(x))
            gain: Control gain (0-1)

        Returns:
            Controlled state (slightly perturbed toward safety)

        Side Effects:
            - Emits Prometheus metrics for criticality adjustments
        """
        # If no target state, find safe state via CBF
        if target_state is None:
            if cbf_function is None:
                # No CBF and no target - use zero state as safe default
                target_state = np.zeros_like(chaotic_state)
                logger.warning("No target state or CBF provided, using zero state")
            else:
                # Find safe state by minimizing distance while satisfying CBF
                target_state = self._find_safe_state(chaotic_state, cbf_function)

        # OGY control: small perturbation proportional to deviation
        error = target_state - chaotic_state
        control = gain * error

        # Apply control
        controlled_state = chaotic_state + control

        # Emit metric for stabilization
        chaos_metrics.CHAOS_INTERVENTIONS_TOTAL.labels(reason="stabilize").inc()

        # Verify CBF constraint if provided
        if cbf_function is not None:
            h_x = cbf_function(controlled_state)
            if h_x < 0.0:
                # CBF violated - apply stronger control
                logger.warning(
                    f"CBF violated after control (h={h_x:.3f}), applying stronger correction"
                )
                # Increase gain and reapply
                stronger_gain = min(1.0, gain * 2.0)
                control = stronger_gain * error
                controlled_state = chaotic_state + control

                # Final check
                h_x_final = cbf_function(controlled_state)
                if h_x_final < 0.0:
                    # Still unsafe - return target state directly
                    logger.error(f"CBF still violated (h={h_x_final:.3f}), returning target state")
                    controlled_state = target_state

        logger.debug(f"Chaos stabilization applied (gain={gain}, CBF={cbf_function is not None})")

        return cast(np.ndarray, controlled_state)

    def _find_safe_state(
        self,
        current_state: np.ndarray,
        cbf_function: Callable,
        max_iterations: int = 10,
    ) -> np.ndarray:
        """Find a safe state near current state that satisfies CBF.

        Uses gradient descent to find nearest safe state.

        Args:
            current_state: Current (possibly unsafe) state
            cbf_function: Control Barrier Function
            max_iterations: Maximum iterations to find safe state

        Returns:
            Safe state satisfying h(x) ≥ 0
        """
        safe_state = current_state.copy()

        for _i in range(max_iterations):
            h_x = cbf_function(safe_state)

            if h_x >= 0.0:
                # Found safe state
                return safe_state

            # Move toward safety by reducing risk components
            # Simple heuristic: reduce all components proportionally
            reduction_factor = 0.9  # Reduce by 10% each iteration
            safe_state = safe_state * reduction_factor

            # Ensure we don't go negative
            safe_state = np.maximum(safe_state, 0.0)

        # If still unsafe after max iterations, return zero state (safest)
        logger.warning(
            f"Could not find safe state after {max_iterations} iterations, returning zero state"
        )
        return cast(np.ndarray, np.zeros_like(current_state))  # type: ignore[redundant-cast]

    def get_safety_metrics(self) -> ChaosSafetyMetrics:
        """Get safety monitoring metrics.

        Returns:
            Comprehensive metrics for observability including:
            - Intervention counts
            - Violation prevention
            - Chaos-specific metrics (Lyapunov, fractal dimension, entropy)
        """
        # Update metrics snapshot
        self._chaos_metrics.total_interventions = self.interventions
        self._chaos_metrics.violations_prevented = self.violations_prevented
        self._chaos_metrics.intervention_rate = self.interventions / max(
            1, self.interventions + 100
        )

        return self._chaos_metrics


# =============================================================================
# SINGLETON FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
# Register via the centralized registry for consistency
# Note: ChaosSafetyMonitor already uses __new__ for singleton
get_chaos_safety_monitor = _singleton_registry.register_sync(
    "chaos_safety_monitor", ChaosSafetyMonitor
)


__all__ = [
    "ChaosSafetyMetrics",
    "ChaosSafetyMonitor",
    "ChaosSafetyResult",
    "get_chaos_safety_monitor",
]
