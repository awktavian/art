"""CBF Runtime Safety Monitoring.

CREATED: December 14, 2025
CONSOLIDATED: December 14, 2025 into kagami.core.safety.cbf_utils

For new code, import from cbf_utils:
    from kagami.core.safety.cbf_utils import (
        DecentralizedCBFMonitor,
        CompositeMonitor,
        create_composite_monitor,
    )

Direct imports from this module still work for backward compatibility.

PURPOSE: Real-time monitoring of Control Barrier Function safety invariants

This module provides comprehensive runtime monitoring for CBF safety properties:
1. Decentralized CBF violations (h_i < 0 for any colony i)
2. Adaptive E8 depth variance (compression quality)
3. Gated Fano attention gate collapse (sparsity health)

DESIGN PRINCIPLES:
==================
- Lightweight: < 1ms overhead per check
- Configurable: Adjustable thresholds and warning zones
- Detailed: Per-colony, per-component diagnostics
- Actionable: Clear status with violation details

SAFETY ZONES:
=============
GREEN:  h > warn_threshold       Full autonomy
YELLOW: threshold ≤ h ≤ warn     Caution, verify
RED:    h < threshold            BLOCKED - violation

INTEGRATION:
============
```python
monitor = CompositeMonitor()

for batch in dataloader:
    output = model(batch)

    metrics = {
        'h_values': output['cbf']['h'],
        'importance': output['e8']['importance'],
        'gates': output['fano']['gates'],
    }

    status = monitor.check_all(metrics)
    if status['status'] == 'violation':
        logger.error(f"Safety violation: {status}")
```

Reference:
- Ames et al. (2017): Control Barrier Functions
- Crystal verification report (Dec 14, 2025)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import torch

# TESTABILITY: Import configuration constants (Dec 14, 2025)
from kagami.core.safety.cbf_constants import (
    COLONY_NAMES,
    DEFAULT_CBF_THRESHOLD,
    DEFAULT_CBF_WARN_THRESHOLD,
    DEFAULT_E8_MAX_MEAN_DEPTH,
    DEFAULT_E8_MIN_MEAN_DEPTH,
    DEFAULT_E8_VARIANCE_THRESHOLD,
    DEFAULT_E8_VARIANCE_WARN,
    DEFAULT_GATE_EPSILON,
    DEFAULT_GATE_MAX,
    DEFAULT_GATE_WARN_THRESHOLD,
    DEFAULT_HISTORY_SIZE,
    DEFAULT_MAX_SPARSITY,
    DEFAULT_MIN_SPARSITY,
    E8_VARIANCE_WARN_FACTOR,
    FANO_LINES,
    NUM_COLONIES,
    SPARSITY_COMPARISON_THRESHOLD,
)

logger = logging.getLogger(__name__)


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

SafetyStatus = Literal["safe", "warning", "violation"]


@dataclass
class MonitorResult:
    """Result of a safety monitor check.

    Attributes:
        status: "safe", "warning", or "violation"
        value: The monitored metric value
        threshold: Current safety threshold
        warn_threshold: Warning zone threshold
        details: Additional diagnostic information
        timestamp: When the check was performed
    """

    status: SafetyStatus
    value: float
    threshold: float
    warn_threshold: float
    details: dict[str, Any] = field(default_factory=dict[str, Any])
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "value": self.value,
            "threshold": self.threshold,
            "warn_threshold": self.warn_threshold,
            "details": self.details,
            "timestamp": self.timestamp,
        }


# =============================================================================
# BASE MONITOR
# =============================================================================


class CBFMonitor(ABC):
    """Base class for CBF safety monitoring.

    Implements core functionality for threshold checking, history tracking,
    and status reporting.

    Safety zones:
    - GREEN: value > warn_threshold
    - YELLOW: threshold ≤ value ≤ warn_threshold
    - RED: value < threshold

    Args:
        threshold: Minimum safe value (violations below this)
        warn_threshold: Warning zone start (should be > threshold)
        history_size: Number of historical checks to retain
    """

    def __init__(
        self,
        threshold: float = DEFAULT_CBF_THRESHOLD,
        warn_threshold: float = DEFAULT_CBF_WARN_THRESHOLD,
        history_size: int = DEFAULT_HISTORY_SIZE,
    ):
        # TESTABILITY: Validate parameters for testability (Dec 14, 2025)
        if warn_threshold <= threshold:
            raise ValueError(f"warn_threshold ({warn_threshold}) must be > threshold ({threshold})")

        self.threshold = threshold
        self.warn_threshold = warn_threshold
        self.history_size = history_size
        self.history: deque[MonitorResult] = deque(maxlen=history_size)

    def _classify_status(self, value: float) -> SafetyStatus:
        """Classify value into safety zone."""
        if value < self.threshold:
            return "violation"
        elif value <= self.warn_threshold:
            return "warning"
        else:
            return "safe"

    def log(self, result: MonitorResult) -> None:
        """Log a monitoring result to history.

        Args:
            result: MonitorResult to store
        """
        self.history.append(result)

    def report(self) -> dict[str, Any]:
        """Generate summary statistics from history.

        Returns:
            Dictionary with:
            - total_checks: Number of checks performed
            - violations: Count of violations
            - warnings: Count of warnings
            - safe: Count of safe checks
            - violation_rate: Fraction of checks that violated
            - warning_rate: Fraction of checks in warning zone
            - current_status: Most recent status
        """
        if not self.history:
            return {
                "total_checks": 0,
                "violations": 0,
                "warnings": 0,
                "safe": 0,
                "violation_rate": 0.0,
                "warning_rate": 0.0,
                "current_status": None,
            }

        violations = sum(1 for r in self.history if r.status == "violation")
        warnings = sum(1 for r in self.history if r.status == "warning")
        safe = sum(1 for r in self.history if r.status == "safe")
        total = len(self.history)

        return {
            "total_checks": total,
            "violations": violations,
            "warnings": warnings,
            "safe": safe,
            "violation_rate": violations / total if total > 0 else 0.0,
            "warning_rate": warnings / total if total > 0 else 0.0,
            "current_status": self.history[-1].status,
        }

    @abstractmethod
    def check(self, values: torch.Tensor | np.ndarray[Any, Any]) -> MonitorResult:
        """Check a metric tensor/array and return a MonitorResult.

        Subclasses must implement this method to provide specific monitoring
        logic for their metric type. This is an abstract base class method.

        Args:
            values: Input tensor/array to monitor

        Returns:
            MonitorResult with safety status and details
        """
        ...


# =============================================================================
# DECENTRALIZED CBF MONITOR
# =============================================================================


class DecentralizedCBFMonitor(CBFMonitor):
    """Monitor for per-colony decentralized CBF safety.

    Tracks h_i for each colony i ∈ {0..6} and identifies which colonies
    violate safety constraints.

    Additional checks:
    - Compositional safety: ALL colonies must be safe
    - Fano line coherence: Check violations on each of 7 Fano lines
    - Worst-case colony tracking

    Args:
        threshold: Minimum safe h value (default: 0.0)
        warn_threshold: Warning zone start (default: 0.1)
        num_colonies: Number of colonies (default: 7)
        history_size: History retention size
    """

    def __init__(
        self,
        threshold: float = DEFAULT_CBF_THRESHOLD,
        warn_threshold: float = DEFAULT_CBF_WARN_THRESHOLD,
        num_colonies: int = NUM_COLONIES,
        history_size: int = DEFAULT_HISTORY_SIZE,
        # TESTABILITY: Injectable Fano structure for testing (Dec 14, 2025)
        fano_lines: list[list[int]] | None = None,
        colony_names: list[str] | None = None,
    ):
        super().__init__(threshold, warn_threshold, history_size)
        self.num_colonies = num_colonies

        # TESTABILITY: Use injected or default Fano structure (Dec 14, 2025)
        self.fano_lines = fano_lines if fano_lines is not None else FANO_LINES
        self.colony_names = colony_names if colony_names is not None else COLONY_NAMES

    def check(self, h_values: torch.Tensor | np.ndarray[Any, Any]) -> MonitorResult:
        """Check decentralized CBF safety.

        Args:
            h_values: Barrier values [B, 7] or [7] for per-colony h_i

        Returns:
            MonitorResult with compositional safety status

        Raises:
            ValueError: If input shape is invalid
            TypeError: If input type is unsupported
        """
        # Input validation and error handling
        if h_values is None:
            raise ValueError("h_values cannot be None")

        # Convert to numpy for consistency
        try:
            if isinstance(h_values, torch.Tensor):
                # Check for invalid tensor values
                if not torch.isfinite(h_values).all():
                    logger.warning("Non-finite values detected in h_values tensor")
                    # Replace NaN/inf with safe fallback
                    h_values = torch.where(torch.isfinite(h_values), h_values, torch.tensor(-1.0))
                h_values = h_values.detach().cpu().numpy()
            elif isinstance(h_values, np.ndarray):
                # Check for invalid numpy values
                if not np.isfinite(h_values).all():
                    logger.warning("Non-finite values detected in h_values array")
                    # Replace NaN/inf with safe fallback
                    h_values = np.where(np.isfinite(h_values), h_values, -1.0)
            else:
                raise TypeError(
                    f"Unsupported input type: {type(h_values)}. Expected torch.Tensor or np.ndarray"
                )
        except Exception as e:
            logger.error(f"Failed to process h_values: {e}")
            # Return violation status for safety
            return MonitorResult(
                status="violation",
                value=-float("inf"),
                threshold=self.threshold,
                warn_threshold=self.warn_threshold,
                details={"error": str(e), "safe_fallback": True},
            )

        # Validate dimensions
        if h_values.ndim == 0:
            raise ValueError("h_values must be at least 1-dimensional")
        elif h_values.ndim > 2:
            raise ValueError(
                f"h_values has too many dimensions: {h_values.ndim}. Expected 1D or 2D"
            )

        # Handle batch dimension
        if h_values.ndim == 2:
            if h_values.shape[0] == 0:
                raise ValueError("Empty batch dimension")
            h_values = h_values.mean(axis=0)  # Average over batch

        # Validate colony count
        if h_values.shape[0] != self.num_colonies:
            raise ValueError(
                f"Expected {self.num_colonies} colony values, got {h_values.shape[0]}. "
                f"Received shape: {h_values.shape}"
            )

        # Compositional safety: min over all colonies
        min_h = float(h_values.min())
        status = self._classify_status(min_h)

        # Identify unsafe colonies
        unsafe_colonies = []
        warning_colonies = []
        for i, h_i in enumerate(h_values):
            if h_i < self.threshold:
                unsafe_colonies.append(i)
            elif h_i <= self.warn_threshold:
                warning_colonies.append(i)

        # Check Fano line violations
        violated_lines = []
        for line_idx, colonies in enumerate(self.fano_lines):
            line_h = [h_values[i] for i in colonies]
            if any(h < self.threshold for h in line_h):
                violated_lines.append(
                    {
                        "line_idx": line_idx,
                        "colonies": [self.colony_names[i] for i in colonies],
                        "h_values": [float(h) for h in line_h],
                    }
                )

        # Build details
        details = {
            "min_h": min_h,
            "max_h": float(h_values.max()),
            "mean_h": float(h_values.mean()),
            "per_colony_h": {self.colony_names[i]: float(h) for i, h in enumerate(h_values)},
            "unsafe_colonies": [self.colony_names[i] for i in unsafe_colonies],
            "warning_colonies": [self.colony_names[i] for i in warning_colonies],
            "violated_fano_lines": violated_lines,
            "compositional_safe": len(unsafe_colonies) == 0,
        }

        result = MonitorResult(
            status=status,
            value=min_h,
            threshold=self.threshold,
            warn_threshold=self.warn_threshold,
            details=details,
        )

        self.log(result)
        return result


# =============================================================================
# ADAPTIVE E8 MONITOR
# =============================================================================


class AdaptiveE8Monitor(CBFMonitor):
    """Monitor for Adaptive E8 depth selection quality.

    Tracks:
    1. Depth variance: σ²(depth_map) - should be bounded
    2. Average depth: mean(depth_map) - compression ratio indicator
    3. Importance distribution: Check for degenerate predictions

    Safety property:
        σ²(depth) < variance_threshold

    Too low variance → uniform depth (wasting capacity on simple frames)
    Too high variance → unstable, extreme depth variations

    Args:
        variance_threshold: Maximum allowed depth variance (default: 4.0)
        variance_warn: Warning threshold for variance (default: 3.0)
        min_mean_depth: Minimum average depth (default: 2.0)
        max_mean_depth: Maximum average depth (default: 14.0)
        history_size: History retention size
    """

    def __init__(
        self,
        variance_threshold: float = DEFAULT_E8_VARIANCE_THRESHOLD,
        variance_warn: float = DEFAULT_E8_VARIANCE_WARN,
        min_mean_depth: float = DEFAULT_E8_MIN_MEAN_DEPTH,
        max_mean_depth: float = DEFAULT_E8_MAX_MEAN_DEPTH,
        history_size: int = DEFAULT_HISTORY_SIZE,
    ):
        super().__init__(
            threshold=-variance_threshold,  # Negate for "lower is worse" metric
            warn_threshold=-variance_warn,
            history_size=history_size,
        )
        # TESTABILITY: Store thresholds for testing (Dec 14, 2025)
        self.variance_threshold = variance_threshold
        self.variance_warn = variance_warn
        self.min_mean_depth = min_mean_depth
        self.max_mean_depth = max_mean_depth

    def check(self, importance: torch.Tensor | np.ndarray[Any, Any]) -> MonitorResult:
        """Check adaptive E8 depth quality.

        Args:
            importance: Importance scores [B, T] or depth map [B, T]

        Returns:
            MonitorResult with variance status
        """
        # Convert to numpy
        if isinstance(importance, torch.Tensor):
            importance = importance.detach().cpu().numpy()

        # Compute depth variance (negative so lower variance = worse)
        variance = float(np.var(importance))
        mean_depth = float(np.mean(importance))

        # Check variance bounds
        # TESTABILITY: Type-safe status assignment (Dec 14, 2025)
        status: SafetyStatus
        if variance > self.variance_threshold:
            status = "violation"
        elif variance > self.variance_warn:
            status = "warning"
        else:
            status = "safe"

        # Check mean depth bounds
        # TESTABILITY: Type-safe mean status (Dec 14, 2025)
        mean_status: SafetyStatus = "safe"
        if mean_depth < self.min_mean_depth or mean_depth > self.max_mean_depth:
            mean_status = "violation"

        # Override status if mean is violated
        if mean_status == "violation":
            status = "violation"

        details = {
            "depth_variance": variance,
            "depth_mean": mean_depth,
            "depth_std": float(np.std(importance)),
            "depth_min": float(np.min(importance)),
            "depth_max": float(np.max(importance)),
            "variance_ok": variance <= self.variance_threshold,
            "mean_depth_ok": self.min_mean_depth <= mean_depth <= self.max_mean_depth,
        }

        result = MonitorResult(
            status=status,
            value=variance,
            threshold=self.variance_threshold,
            warn_threshold=self.variance_warn,
            details=details,
        )

        self.log(result)
        return result


# =============================================================================
# GATED FANO MONITOR
# =============================================================================


class GatedFanoMonitor(CBFMonitor):
    """Monitor for Gated Fano attention gate health.

    Tracks:
    1. Gate collapse: min(gates) > ε and max(gates) < 1-ε
    2. Sparsity: fraction of gates < 0.5
    3. Per-head statistics: Ensure no head degenerates

    Safety properties:
        ε < min(gates) < max(gates) < 1-ε
        0.3 < sparsity < 0.9

    Gate collapse detection:
        - All gates → 0: Attention is being fully blocked (bad)
        - All gates → 1: Gating has no effect (wasteful, not necessarily bad)

    Args:
        epsilon: Minimum gate value to avoid collapse (default: 0.01)
        max_gate: Maximum gate value (default: 0.99)
        min_sparsity: Minimum desired sparsity (default: 0.3)
        max_sparsity: Maximum desired sparsity (default: 0.9)
        history_size: History retention size
    """

    def __init__(
        self,
        epsilon: float = DEFAULT_GATE_EPSILON,
        max_gate: float = DEFAULT_GATE_MAX,
        min_sparsity: float = DEFAULT_MIN_SPARSITY,
        max_sparsity: float = DEFAULT_MAX_SPARSITY,
        history_size: int = DEFAULT_HISTORY_SIZE,
        # TESTABILITY: Injectable warn threshold and sparsity threshold (Dec 14, 2025)
        warn_threshold: float = DEFAULT_GATE_WARN_THRESHOLD,
        sparsity_threshold: float = SPARSITY_COMPARISON_THRESHOLD,
    ):
        super().__init__(
            threshold=epsilon,
            warn_threshold=warn_threshold,
            history_size=history_size,
        )
        # TESTABILITY: Store thresholds for testing (Dec 14, 2025)
        self.epsilon = epsilon
        self.max_gate = max_gate
        self.min_sparsity = min_sparsity
        self.max_sparsity = max_sparsity
        self.sparsity_threshold = sparsity_threshold

    def check(self, gates: torch.Tensor | np.ndarray[Any, Any]) -> MonitorResult:
        """Check gated Fano attention health.

        Args:
            gates: Attention gates [B, num_heads, T, T] or [B, T]

        Returns:
            MonitorResult with gate collapse status
        """
        # Convert to numpy
        if isinstance(gates, torch.Tensor):
            gates = gates.detach().cpu().numpy()

        # Flatten to get all gate values
        gates_flat = gates.flatten()

        # Compute gate statistics
        # TESTABILITY: Extract statistics computation for testing (Dec 14, 2025)
        min_gate = float(gates_flat.min())
        max_gate = float(gates_flat.max())
        mean_gate = float(gates_flat.mean())
        sparsity = float((gates_flat < self.sparsity_threshold).mean())

        # Check for gate collapse
        collapsed_low = min_gate < self.epsilon
        collapsed_high = max_gate > self.max_gate
        collapse_detected = collapsed_low or collapsed_high

        # Check sparsity bounds
        sparsity_ok = self.min_sparsity <= sparsity <= self.max_sparsity

        # Determine status
        # TESTABILITY: Type-safe status assignment (Dec 14, 2025)
        status: SafetyStatus
        if collapse_detected:
            status = "violation"
        elif not sparsity_ok:
            status = "warning"
        else:
            status = "safe"

        details = {
            "min_gate": min_gate,
            "max_gate": max_gate,
            "mean_gate": mean_gate,
            "sparsity": sparsity,
            "collapsed_low": collapsed_low,
            "collapsed_high": collapsed_high,
            "sparsity_ok": sparsity_ok,
            "epsilon": self.epsilon,
        }

        # Per-head statistics if available
        if gates.ndim >= 2:
            num_heads = gates.shape[1] if gates.ndim > 2 else 1
            if num_heads > 1 and gates.ndim >= 3:
                per_head_mean = (
                    gates.mean(axis=(0, 2, 3)) if gates.ndim == 4 else gates.mean(axis=0)
                )
                details["per_head_mean"] = per_head_mean.tolist()

        result = MonitorResult(
            status=status,
            value=min_gate,
            threshold=self.epsilon,
            warn_threshold=self.warn_threshold,
            details=details,
        )

        self.log(result)
        return result


# =============================================================================
# COMPOSITE MONITOR
# =============================================================================


class CompositeMonitor:
    """Composite monitor combining all CBF safety checks.

    Manages multiple monitors and provides unified status reporting.

    Components:
    - DecentralizedCBFMonitor: Per-colony h_i safety
    - AdaptiveE8Monitor: Depth variance quality
    - GatedFanoMonitor: Attention gate health

    Args:
        cbf_threshold: Threshold for CBF violations (default: 0.0)
        cbf_warn: Warning threshold for CBF (default: 0.1)
        e8_variance_threshold: Max depth variance (default: 4.0)
        gate_epsilon: Min gate value (default: 0.01)
        history_size: History retention size
    """

    def __init__(
        self,
        cbf_threshold: float = DEFAULT_CBF_THRESHOLD,
        cbf_warn: float = DEFAULT_CBF_WARN_THRESHOLD,
        e8_variance_threshold: float = DEFAULT_E8_VARIANCE_THRESHOLD,
        gate_epsilon: float = DEFAULT_GATE_EPSILON,
        history_size: int = DEFAULT_HISTORY_SIZE,
        # TESTABILITY: Injectable monitors for testing (Dec 14, 2025)
        monitors: dict[str, CBFMonitor] | None = None,
    ):
        # TESTABILITY: Allow injecting pre-configured monitors for testing
        if monitors is not None:
            self.monitors = monitors
        else:
            self.monitors = {
                "cbf": DecentralizedCBFMonitor(
                    threshold=cbf_threshold,
                    warn_threshold=cbf_warn,
                    history_size=history_size,
                ),
                "e8": AdaptiveE8Monitor(
                    variance_threshold=e8_variance_threshold,
                    variance_warn=e8_variance_threshold * E8_VARIANCE_WARN_FACTOR,
                    history_size=history_size,
                ),
                "fano": GatedFanoMonitor(
                    epsilon=gate_epsilon,
                    history_size=history_size,
                ),
            }

    def check_all(
        self,
        metrics: dict[str, torch.Tensor | np.ndarray[Any, Any]],
    ) -> dict[str, Any]:
        """Check all safety properties.

        Args:
            metrics: Dictionary containing:
                - 'h_values': CBF barrier values [B, 7]
                - 'importance': E8 importance scores [B, T]
                - 'gates': Fano attention gates [B, num_heads, T, T]

        Returns:
            Composite status dictionary with:
            - status: Overall status ("safe", "warning", "violation")
            - results: Individual monitor results
            - summary: Aggregate statistics
        """
        results = {}

        # Run each monitor if metrics available
        if "h_values" in metrics:
            results["cbf"] = self.monitors["cbf"].check(metrics["h_values"])

        if "importance" in metrics:
            results["e8"] = self.monitors["e8"].check(metrics["importance"])

        if "gates" in metrics:
            results["fano"] = self.monitors["fano"].check(metrics["gates"])

        # Determine overall status (worst case)
        statuses = [r.status for r in results.values()]
        if "violation" in statuses:
            overall_status = "violation"
        elif "warning" in statuses:
            overall_status = "warning"
        else:
            overall_status = "safe"

        # Build summary
        summary = {
            "overall_status": overall_status,
            "num_violations": sum(1 for s in statuses if s == "violation"),
            "num_warnings": sum(1 for s in statuses if s == "warning"),
            "monitors_checked": list(results.keys()),
        }

        return {
            "status": overall_status,
            "results": {k: v.to_dict() for k, v in results.items()},
            "summary": summary,
            "timestamp": time.time(),
        }

    def report_all(self) -> dict[str, Any]:
        """Generate aggregate report from all monitors.

        Returns:
            Dictionary with reports from each monitor
        """
        return {name: monitor.report() for name, monitor in self.monitors.items()}


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_cbf_monitor(
    cbf_threshold: float = DEFAULT_CBF_THRESHOLD,
    cbf_warn: float = DEFAULT_CBF_WARN_THRESHOLD,
    history_size: int = DEFAULT_HISTORY_SIZE,
) -> DecentralizedCBFMonitor:
    """Factory for creating DecentralizedCBFMonitor.

    TESTABILITY: Uses constants from cbf_constants.py (Dec 14, 2025)

    Args:
        cbf_threshold: Minimum safe h value
        cbf_warn: Warning threshold
        history_size: History retention size

    Returns:
        Configured DecentralizedCBFMonitor
    """
    return DecentralizedCBFMonitor(
        threshold=cbf_threshold,
        warn_threshold=cbf_warn,
        history_size=history_size,
    )


def create_composite_monitor(
    cbf_threshold: float = DEFAULT_CBF_THRESHOLD,
    cbf_warn: float = DEFAULT_CBF_WARN_THRESHOLD,
    e8_variance_threshold: float = DEFAULT_E8_VARIANCE_THRESHOLD,
    gate_epsilon: float = DEFAULT_GATE_EPSILON,
    history_size: int = DEFAULT_HISTORY_SIZE,
) -> CompositeMonitor:
    """Factory for creating CompositeMonitor.

    TESTABILITY: Uses constants from cbf_constants.py (Dec 14, 2025)

    Args:
        cbf_threshold: Threshold for CBF violations
        cbf_warn: Warning threshold for CBF
        e8_variance_threshold: Max depth variance
        gate_epsilon: Min gate value
        history_size: History retention size

    Returns:
        Configured CompositeMonitor
    """
    return CompositeMonitor(
        cbf_threshold=cbf_threshold,
        cbf_warn=cbf_warn,
        e8_variance_threshold=e8_variance_threshold,
        gate_epsilon=gate_epsilon,
        history_size=history_size,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AdaptiveE8Monitor",
    "CBFMonitor",
    "CompositeMonitor",
    "DecentralizedCBFMonitor",
    "GatedFanoMonitor",
    "MonitorResult",
    "create_cbf_monitor",
    "create_composite_monitor",
]
