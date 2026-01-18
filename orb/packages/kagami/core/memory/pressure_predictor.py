"""Memory Pressure Predictor - Proactive memory management.

Predicts future memory pressure based on trends to take action BEFORE limits are hit.
Uses time series forecasting (exponential smoothing).
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MemoryPressureForecast:
    """Forecast of future memory pressure."""

    current_usage_gb: float
    predicted_usage_gb: float  # Predicted usage in next interval
    time_to_limit_seconds: float | None  # Seconds until hard limit hit
    pressure_trend: str  # "increasing", "stable", "decreasing"
    confidence: float  # 0-1


class MemoryPressurePredictor:
    """Predict future memory pressure for proactive management.

    Uses exponential smoothing to forecast memory usage trends.
    """

    def __init__(self, alpha: float = 0.3, history_size: int = 60) -> None:
        """Initialize predictor.

        Args:
            alpha: Smoothing factor (0-1, higher = more weight on recent)
            history_size: Number of historical samples to keep
        """
        self.alpha = alpha
        self.history: deque[tuple[float, float]] = deque(maxlen=history_size)  # (time, usage_gb)
        self.smoothed_value: float | None = None
        self.smoothed_trend: float | None = None

    def add_sample(self, usage_gb: float) -> None:
        """Add memory usage sample.

        Args:
            usage_gb: Current memory usage in GB
        """
        current_time = time.time()
        self.history.append((current_time, usage_gb))

        # Update exponential smoothing
        if self.smoothed_value is None:
            self.smoothed_value = usage_gb
            self.smoothed_trend = 0.0
        else:
            # Double exponential smoothing (Holt's method)
            error = usage_gb - self.smoothed_value
            self.smoothed_value = self.smoothed_value + self.alpha * error

            if self.smoothed_trend is None:
                self.smoothed_trend = 0.0
            else:
                beta = self.alpha  # Trend smoothing factor
                self.smoothed_trend = self.smoothed_trend + beta * (error - self.smoothed_trend)

    def predict(self, horizon_seconds: float, hard_limit_gb: float) -> MemoryPressureForecast:
        """Predict memory pressure.

        Args:
            horizon_seconds: How far ahead to predict
            hard_limit_gb: Hard memory limit

        Returns:
            MemoryPressureForecast
        """
        if len(self.history) < 3:
            # Not enough data
            current = self.history[-1][1] if self.history else 0.0
            return MemoryPressureForecast(
                current_usage_gb=current,
                predicted_usage_gb=current,
                time_to_limit_seconds=None,
                pressure_trend="unknown",
                confidence=0.0,
            )

        current_usage = self.history[-1][1]

        # Predict using smoothed value + trend
        if self.smoothed_value is not None and self.smoothed_trend is not None:
            # Linear extrapolation
            predicted_usage = self.smoothed_value + self.smoothed_trend * horizon_seconds
        else:
            predicted_usage = current_usage

        # Determine trend
        if self.smoothed_trend is not None:
            if self.smoothed_trend > 0.01:  # Growing > 10MB/s
                trend = "increasing"
            elif self.smoothed_trend < -0.01:  # Shrinking
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "unknown"

        # Time to limit (if increasing)
        time_to_limit = None
        if self.smoothed_trend is not None and self.smoothed_trend > 0:
            remaining = hard_limit_gb - current_usage
            if remaining > 0:
                time_to_limit = remaining / self.smoothed_trend

        # Confidence based on history size
        confidence = min(1.0, len(self.history) / 20.0)  # Full confidence at 20 samples

        return MemoryPressureForecast(
            current_usage_gb=current_usage,
            predicted_usage_gb=predicted_usage,
            time_to_limit_seconds=time_to_limit,
            pressure_trend=trend,
            confidence=confidence,
        )


__all__ = ["MemoryPressureForecast", "MemoryPressurePredictor"]
