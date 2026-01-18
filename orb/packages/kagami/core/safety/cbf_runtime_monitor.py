"""Runtime CBF monitoring with early warning system.

Continuously tracks h(x) values and alerts when approaching safety boundary.

CREATED: December 15, 2025
AUTHOR: Forge (e₂)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CBFCheckRecord:
    """Record of a single CBF check."""

    timestamp: float
    h_value: float
    operation: str
    context: dict[str, Any] = field(default_factory=dict[str, Any])
    safe: bool = True
    barrier_name: str | None = None
    tier: int = 3


class CBFRuntimeMonitor:
    """Continuous monitoring of CBF safety margins.

    Features:
    - Historical h(x) tracking (last 1000 checks)
    - Early warning alerts (h < threshold)
    - Fail-fast triggers (no degradation)
    - Forensics for safety incidents

    Thread-safe for multi-threaded environments.
    """

    def __init__(
        self,
        history_size: int = 1000,
        alert_threshold: float = 0.1,
        critical_threshold: float = 0.05,
        enable_alerts: bool = True,
    ):
        """Initialize CBF monitor.

        Args:
            history_size: Number of recent checks to keep
            alert_threshold: Trigger warning when h < threshold
            critical_threshold: Trigger critical alert when h < threshold
            enable_alerts: Whether to emit log alerts
        """
        self.history: deque[CBFCheckRecord] = deque(maxlen=history_size)
        self.alert_threshold = alert_threshold
        self.critical_threshold = critical_threshold
        self.enable_alerts = enable_alerts

        # Statistics
        self.total_checks = 0
        self.violations = 0  # h < 0
        self.warnings = 0  # 0 <= h < alert_threshold
        self.criticals = 0  # 0 <= h < critical_threshold

        # Thread safety
        self._lock = threading.Lock()

        # Callbacks for graceful degradation
        self._warning_callbacks: list[Callable[[CBFCheckRecord], None]] = []
        self._critical_callbacks: list[Callable[[CBFCheckRecord], None]] = []

        logger.info(
            f"CBF Runtime Monitor initialized (alert={alert_threshold:.3f}, "
            f"critical={critical_threshold:.3f})"
        )

    def log_check(
        self,
        h_value: float,
        operation: str,
        context: dict[str, Any] | None = None,
        safe: bool | None = None,
        barrier_name: str | None = None,
        tier: int = 3,
    ) -> None:
        """Log a CBF check result.

        Args:
            h_value: Barrier function value h(x)
            operation: Description of operation being checked
            context: Additional context (state, action, etc.)
            safe: Whether check passed (defaults to h_value >= 0)
            barrier_name: Name of barrier being checked
            tier: Tier level (1=organism, 2=colony, 3=action)
        """
        if safe is None:
            safe = h_value >= 0.0

        record = CBFCheckRecord(
            timestamp=time.time(),
            h_value=h_value,
            operation=operation,
            context=context or {},
            safe=safe,
            barrier_name=barrier_name,
            tier=tier,
        )

        with self._lock:
            self.history.append(record)
            self.total_checks += 1

            # Update statistics
            if h_value < 0:
                self.violations += 1
            elif h_value < self.critical_threshold:
                self.criticals += 1
                self._trigger_critical(record)
            elif h_value < self.alert_threshold:
                self.warnings += 1
                self._trigger_warning(record)

    def _trigger_warning(self, record: CBFCheckRecord) -> None:
        """Handle warning-level alert (h approaching boundary)."""
        if self.enable_alerts:
            logger.warning(
                f"CBF near violation: h(x)={record.h_value:.4f} "
                f"(threshold={self.alert_threshold:.3f}) "
                f"during '{record.operation}' "
                f"[barrier={record.barrier_name or 'unknown'}, tier={record.tier}]"
            )

        # Execute warning callbacks
        for callback in self._warning_callbacks:
            try:
                callback(record)
            except Exception as e:
                logger.error(f"Warning callback failed: {e}", exc_info=True)

    def _trigger_critical(self, record: CBFCheckRecord) -> None:
        """Handle critical-level alert (h very close to violation)."""
        if self.enable_alerts:
            logger.critical(
                f"CBF CRITICAL: h(x)={record.h_value:.4f} "
                f"(threshold={self.critical_threshold:.3f}) "
                f"during '{record.operation}' - INITIATING SAFE FALLBACK "
                f"[barrier={record.barrier_name or 'unknown'}, tier={record.tier}]"
            )

        # Execute critical callbacks (e.g., halt non-essential operations)
        for callback in self._critical_callbacks:
            try:
                callback(record)
            except Exception as e:
                logger.error(f"Critical callback failed: {e}", exc_info=True)

    def register_warning_callback(self, callback: Callable[[CBFCheckRecord], None]) -> None:
        """Register callback for warning-level alerts."""
        with self._lock:
            self._warning_callbacks.append(callback)

    def register_critical_callback(self, callback: Callable[[CBFCheckRecord], None]) -> None:
        """Register callback for critical-level alerts."""
        with self._lock:
            self._critical_callbacks.append(callback)

    def get_recent_history(self, n: int = 10) -> list[CBFCheckRecord]:
        """Get N most recent CBF checks."""
        with self._lock:
            return list(self.history)[-n:]

    def get_statistics(self) -> dict[str, Any]:
        """Get monitoring statistics.

        Returns:
            Dictionary with:
            - total_checks: Total number of checks
            - violations: Count of h < 0
            - warnings: Count of 0 <= h < alert_threshold
            - criticals: Count of 0 <= h < critical_threshold
            - violation_rate: Fraction of checks that violated
            - warning_rate: Fraction of checks that warned
            - min_h: Minimum h value in history
            - mean_h: Mean h value in history
            - std_h: Standard deviation of h values
            - recent_trend: "improving" | "stable" | "degrading"
        """
        with self._lock:
            recent = list(self.history)

            if not recent:
                return {
                    "total_checks": 0,
                    "violations": 0,
                    "warnings": 0,
                    "criticals": 0,
                    "min_h": None,
                    "mean_h": None,
                    "recent_trend": None,
                }

            h_values = [r.h_value for r in recent]

            return {
                "total_checks": self.total_checks,
                "violations": self.violations,
                "warnings": self.warnings,
                "criticals": self.criticals,
                "violation_rate": (
                    self.violations / self.total_checks if self.total_checks > 0 else 0
                ),
                "warning_rate": (self.warnings / self.total_checks if self.total_checks > 0 else 0),
                "min_h": float(min(h_values)),
                "mean_h": float(np.mean(h_values)),
                "std_h": float(np.std(h_values)),
                "recent_trend": (
                    self._compute_trend(h_values[-100:])
                    if len(h_values) >= 10
                    else "insufficient_data"
                ),
            }

    def _compute_trend(self, h_values: list[float]) -> str:
        """Compute trend direction of recent h values.

        Returns:
            "improving" | "stable" | "degrading"
        """
        if len(h_values) < 10:
            return "insufficient_data"

        # Linear regression slope
        x = np.arange(len(h_values))
        y = np.array(h_values)
        slope = np.polyfit(x, y, 1)[0]

        if slope > 0.001:
            return "improving"
        elif slope < -0.001:
            return "degrading"
        else:
            return "stable"

    def clear_history(self) -> None:
        """Clear monitoring history (for testing or reset)."""
        with self._lock:
            self.history.clear()
            self.total_checks = 0
            self.violations = 0
            self.warnings = 0
            self.criticals = 0
        logger.info("CBF monitor history cleared")

    def get_violations(self) -> list[CBFCheckRecord]:
        """Get all violation records (h < 0) from history."""
        with self._lock:
            return [r for r in self.history if r.h_value < 0]

    def get_warnings_in_range(self, start_time: float, end_time: float) -> list[CBFCheckRecord]:
        """Get warning records in time range."""
        with self._lock:
            return [
                r
                for r in self.history
                if start_time <= r.timestamp <= end_time and 0 <= r.h_value < self.alert_threshold
            ]

    def export_forensics(self) -> dict[str, Any]:
        """Export comprehensive forensics data for debugging.

        Returns:
            Dictionary with:
            - statistics: Overall stats
            - violations: All violation records
            - recent_warnings: Last 50 warnings
            - trend_analysis: Trend over time
        """
        with self._lock:
            stats = self.get_statistics()
            violations = self.get_violations()
            recent = list(self.history)

            # Get recent warnings
            warnings = [r for r in recent if 0 <= r.h_value < self.alert_threshold][-50:]

            return {
                "statistics": stats,
                "violations": [
                    {
                        "timestamp": v.timestamp,
                        "h_value": v.h_value,
                        "operation": v.operation,
                        "barrier": v.barrier_name,
                        "tier": v.tier,
                    }
                    for v in violations
                ],
                "recent_warnings": [
                    {
                        "timestamp": w.timestamp,
                        "h_value": w.h_value,
                        "operation": w.operation,
                        "barrier": w.barrier_name,
                        "tier": w.tier,
                    }
                    for w in warnings
                ],
                "trend_analysis": stats.get("recent_trend"),
                "timestamp": time.time(),
            }


# =============================================================================
# GLOBAL MONITOR SINGLETON
# =============================================================================

_global_monitor: CBFRuntimeMonitor | None = None
_monitor_lock = threading.Lock()


def get_cbf_monitor() -> CBFRuntimeMonitor:
    """Get or create global CBF monitor singleton.

    Thread-safe lazy initialization.
    """
    global _global_monitor
    if _global_monitor is None:
        with _monitor_lock:
            # Double-check locking pattern
            if _global_monitor is None:
                _global_monitor = CBFRuntimeMonitor()
    return _global_monitor


def reset_cbf_monitor() -> None:
    """Reset global monitor (for testing)."""
    global _global_monitor
    with _monitor_lock:
        _global_monitor = None


__all__ = [
    "CBFCheckRecord",
    "CBFRuntimeMonitor",
    "get_cbf_monitor",
    "reset_cbf_monitor",
]
