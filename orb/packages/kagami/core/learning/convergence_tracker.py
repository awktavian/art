from __future__ import annotations

"""Convergence Tracker - Monitor learning loop closure.

Tracks whether prediction error decreases over time (proof of learning).
Measures:
- Prediction error trend (should decrease)
- Confidence trend (should increase)
- Training velocity (rate of improvement)
- Convergence status (converged, improving, stagnant, diverging)
"""
import logging
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


class ConvergenceTracker:
    """Track learning convergence over time."""

    def __init__(self, window_size: int = 20) -> None:
        """Initialize tracker.

        Args:
            window_size: Number of recent training cycles to track
        """
        self.window_size = window_size
        self.prediction_errors: deque[float] = deque(maxlen=window_size)
        self.confidences: deque[float] = deque(maxlen=window_size)
        self.timestamps: deque[float] = deque(maxlen=window_size)

    def record_training_cycle(
        self,
        prediction_error: float,
        confidence: float,
    ) -> None:
        """Record a training cycle.

        Args:
            prediction_error: Average prediction error this cycle
            confidence: Average confidence this cycle
        """
        self.prediction_errors.append(prediction_error)
        self.confidences.append(confidence)
        self.timestamps.append(time.time())

    def get_convergence_status(self) -> dict[str, Any]:
        """Compute convergence status from recent history.

        Returns:
            Dict with:
            - status: "converged" | "improving" | "stagnant" | "diverging"
            - prediction_error_trend: Slope of prediction error (negative is good)
            - confidence_trend: Slope of confidence (positive is good)
            - velocity: Rate of improvement per hour
            - cycles_tracked: Number of cycles in window
        """
        if len(self.prediction_errors) < 5:
            return {
                "status": "insufficient_data",
                "cycles_tracked": len(self.prediction_errors),
                "prediction_error_trend": 0.0,
                "confidence_trend": 0.0,
                "velocity": 0.0,
            }

        # Compute trend via linear regression (simple slope)
        n = len(self.prediction_errors)
        x = list(range(n))  # Time steps

        # Prediction error trend (negative = improving)
        y_err = list(self.prediction_errors)
        err_trend = self._compute_slope(x, y_err)

        # Confidence trend (positive = improving)
        y_conf = list(self.confidences)
        conf_trend = self._compute_slope(x, y_conf)

        # Velocity: Change per hour
        if len(self.timestamps) >= 2:
            time_span_hours = (self.timestamps[-1] - self.timestamps[0]) / 3600
            error_change = self.prediction_errors[-1] - self.prediction_errors[0]
            velocity = error_change / time_span_hours if time_span_hours > 0 else 0.0
        else:
            velocity = 0.0

        # Classify status
        if err_trend < -0.05 and conf_trend > 0.01:
            status = "converged" if abs(err_trend) < 0.01 else "improving"
        elif abs(err_trend) < 0.05 and abs(conf_trend) < 0.01:
            status = "stagnant"
        elif err_trend > 0.05:
            status = "diverging"
        else:
            status = "stable"

        return {
            "status": status,
            "prediction_error_trend": round(err_trend, 4),
            "confidence_trend": round(conf_trend, 4),
            "velocity": round(velocity, 4),
            "cycles_tracked": n,
            "latest_error": round(self.prediction_errors[-1], 2),
            "latest_confidence": round(self.confidences[-1], 3),
        }

    def _compute_slope(self, x: list[int], y: list[float]) -> float:
        """Compute linear regression slope."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        x_mean = sum(x) / n
        y_mean = sum(y) / n

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        return numerator / denominator if denominator > 0 else 0.0

    def emit_metrics(self) -> None:
        """Emit convergence metrics to Prometheus."""
        try:
            from kagami_observability.metrics import REGISTRY, Gauge

            status = self.get_convergence_status()

            # Prediction error trend
            trend_gauge = Gauge(
                "kagami_learning_prediction_error_trend",
                "Slope of prediction error over time (negative = improving)",
                registry=REGISTRY,
            )
            trend_gauge.set(status["prediction_error_trend"])

            # Confidence trend
            conf_trend_gauge = Gauge(
                "kagami_learning_confidence_trend",
                "Slope of confidence over time (positive = improving)",
                registry=REGISTRY,
            )
            conf_trend_gauge.set(status["confidence_trend"])

            # Learning velocity
            velocity_gauge = Gauge(
                "kagami_learning_velocity",
                "Rate of prediction error change per hour (negative = improving)",
                registry=REGISTRY,
            )
            velocity_gauge.set(status["velocity"])

            # Status as enum (map to numeric for Prometheus)
            status_map = {
                "converged": 4,
                "improving": 3,
                "stable": 2,
                "stagnant": 1,
                "diverging": 0,
                "insufficient_data": -1,
            }
            status_gauge = Gauge(
                "kagami_learning_convergence_status",
                "Learning convergence status (4=converged, 3=improving, 2=stable, 1=stagnant, 0=diverging, -1=insufficient_data)",
                registry=REGISTRY,
            )
            status_gauge.set(status_map.get(status["status"], -1))

        except Exception as e:
            logger.debug(f"Failed to emit convergence metrics: {e}")


# Global singleton
_tracker: ConvergenceTracker | None = None


def get_convergence_tracker() -> ConvergenceTracker:
    """Get global convergence tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = ConvergenceTracker()
    return _tracker


__all__ = ["ConvergenceTracker", "get_convergence_tracker"]
