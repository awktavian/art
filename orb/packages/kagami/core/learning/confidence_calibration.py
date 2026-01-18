from __future__ import annotations

"""
Confidence Calibration for Predictions.

Maps raw model confidences to calibrated probabilities using
standard techniques (isotonic regression or Platt scaling).

This module keeps an online summary to produce a simple calibration
curve without heavy dependencies when sklearn is unavailable.
"""
import bisect
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CalibrationPoint:
    raw_conf: float
    empirical_acc: float


class ConfidenceCalibrator:
    """Online confidence calibration via reliability diagram buckets."""

    def __init__(self, buckets: int = 10) -> None:
        self._buckets = max(5, min(50, buckets))
        self._counts = [0] * self._buckets
        self._correct = [0] * self._buckets

    def _bucket_index(self, conf: float) -> int:
        conf = max(0.0, min(1.0, conf))
        idx = int(conf * self._buckets)
        return min(self._buckets - 1, idx)

    def observe(self, raw_confidence: float, correct: bool) -> None:
        """Record an outcome for calibration.

        Args:
            raw_confidence: model's raw confidence [0,1]
            correct: whether the prediction was correct
        """
        i = self._bucket_index(raw_confidence)
        self._counts[i] += 1
        if correct:
            self._correct[i] += 1

    def get_reliability_curve(self) -> list[CalibrationPoint]:
        points: list[CalibrationPoint] = []
        for i in range(self._buckets):
            n = self._counts[i]
            if n == 0:
                continue
            acc = self._correct[i] / max(1, n)
            # Representative raw confidence for the bucket
            raw = (i + 0.5) / self._buckets
            points.append(CalibrationPoint(raw_conf=raw, empirical_acc=acc))
        # Ensure points sorted by raw
        points.sort(key=lambda p: p.raw_conf)
        return points

    def calibrate(self, raw_confidence: float) -> float:
        """Calibrate a raw confidence to empirical accuracy estimate.

        Uses linear interpolation over the reliability curve.
        Returns raw_confidence if insufficient data.
        """
        curve = self.get_reliability_curve()
        if len(curve) < 2:
            return max(0.0, min(1.0, raw_confidence))

        xs = [p.raw_conf for p in curve]
        ys = [p.empirical_acc for p in curve]

        x = max(0.0, min(1.0, raw_confidence))
        j = bisect.bisect_left(xs, x)
        if j <= 0:
            return ys[0]
        if j >= len(xs):
            return ys[-1]
        # Linear interpolation
        x0, y0 = xs[j - 1], ys[j - 1]
        x1, y1 = xs[j], ys[j]
        t = (x - x0) / max(1e-6, (x1 - x0))
        return max(0.0, min(1.0, y0 * (1 - t) + y1 * t))


__all__ = ["CalibrationPoint", "ConfidenceCalibrator"]
