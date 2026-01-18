"""Calibration Tracker for World Model Predictions.

Implements calibration learning: comparing predicted outcomes to actual outcomes
and adjusting confidence estimates to improve future predictions.

Mathematical Foundation:
    Calibration Error = E[|P(success|confidence) - confidence|]

A well-calibrated model satisfies: P(success | confidence = p) = p
When the model predicts 80% confidence, it should succeed 80% of the time.

We use an exponential moving average (EMA) to track calibration error
per confidence bin, and adjust the confidence estimator accordingly.

Created: November 29, 2025
Status: Production-ready
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CalibrationBin:
    """A single bin for calibration tracking.

    Tracks predictions within a confidence range (e.g., 0.7-0.8)
    and computes the actual success rate.
    """

    lower: float  # Lower bound of confidence range
    upper: float  # Upper bound of confidence range

    # Running statistics
    total_predictions: int = 0
    successful_predictions: int = 0

    # Exponential moving average of success rate
    ema_success_rate: float = 0.5
    ema_alpha: float = 0.1  # EMA smoothing factor

    # History for debugging
    recent_outcomes: deque[Any] = field(default_factory=lambda: deque(maxlen=100))

    def record(self, confidence: float, actual_success: bool) -> float:
        """Record a prediction outcome and return calibration error.

        Args:
            confidence: Predicted confidence (should be in [lower, upper])
            actual_success: Whether the prediction succeeded

        Returns:
            Calibration error for this prediction
        """
        self.total_predictions += 1
        if actual_success:
            self.successful_predictions += 1

        # Update EMA
        outcome = 1.0 if actual_success else 0.0
        self.ema_success_rate = (
            self.ema_alpha * outcome + (1 - self.ema_alpha) * self.ema_success_rate
        )

        # Record for debugging
        self.recent_outcomes.append((confidence, actual_success))

        # Calibration error: |predicted_confidence - actual_success_rate|
        # For a single sample, we use the confidence vs outcome directly
        return abs(confidence - outcome)

    @property
    def empirical_success_rate(self) -> float:
        """Actual success rate observed in this bin."""
        if self.total_predictions == 0:
            # Beta prior: alpha=1, beta=1 gives uniform prior
            # Posterior mean = (successes + alpha) / (total + alpha + beta)
            return (self.successful_predictions + 1) / (self.total_predictions + 2)
        return self.successful_predictions / self.total_predictions

    @property
    def calibration_error(self) -> float:
        """Expected calibration error for this bin.

        ECE_bin = |mean(confidence) - empirical_success_rate|
        """
        if self.total_predictions == 0:
            return 0.0

        # Average confidence in this bin
        mean_confidence = (self.lower + self.upper) / 2
        return abs(mean_confidence - self.ema_success_rate)

    @property
    def adjustment_factor(self) -> float:
        """Multiplicative factor to adjust confidence predictions.

        If we predict 80% but only succeed 60%, adjustment = 0.6/0.8 = 0.75
        """
        mean_confidence = (self.lower + self.upper) / 2
        if mean_confidence < 0.01:
            return 1.0

        # Bounded adjustment to prevent extreme corrections
        raw_adjustment = self.ema_success_rate / mean_confidence
        return max(0.5, min(2.0, raw_adjustment))


@dataclass
class CalibrationRecord:
    """Record of a single prediction for calibration."""

    confidence: float
    threat_score: float
    uncertainty: float
    actual_success: bool
    duration_ms: float
    action_type: str
    agent_domain: str
    timestamp: float = field(default_factory=lambda: __import__("time").time())


class CalibrationTracker:
    """Tracks and improves world model prediction calibration.

    Maintains calibration bins and computes adjustment factors
    to improve future confidence estimates.

    Usage:
        tracker = CalibrationTracker()

        # After each prediction is verified:
        error = tracker.record(
            predictions=[{"confidence": 0.8, ...}],
            actual_success=True,
            task_context={...}
        )

        # Get adjustment for future predictions:
        adjusted_confidence = tracker.adjust_confidence(0.8, domain="forge")
    """

    def __init__(
        self,
        num_bins: int = 10,
        ema_alpha: float = 0.1,
        enable_domain_specific: bool = True,
    ) -> None:
        """Initialize calibration tracker.

        Args:
            num_bins: Number of calibration bins (default 10 for 0.0-0.1, 0.1-0.2, etc.)
            ema_alpha: EMA smoothing factor for running statistics
            enable_domain_specific: Track per-domain calibration
        """
        self.num_bins = num_bins
        self.ema_alpha = ema_alpha
        self.enable_domain_specific = enable_domain_specific

        # Global calibration bins
        self._bins = self._create_bins()

        # Per-domain calibration bins
        self._domain_bins: dict[str, list[CalibrationBin]] = {}

        # Running metrics
        self._total_records = 0
        self._running_ece = 0.0  # Expected Calibration Error

        # History for debugging and analysis
        self._recent_records: deque[CalibrationRecord] = deque(maxlen=1000)

        logger.info(
            f"CalibrationTracker initialized: {num_bins} bins, "
            f"domain_specific={enable_domain_specific}"
        )

    def _create_bins(self) -> list[CalibrationBin]:
        """Create calibration bins covering [0, 1]."""
        bins = []
        step = 1.0 / self.num_bins
        for i in range(self.num_bins):
            lower = i * step
            upper = (i + 1) * step
            bins.append(
                CalibrationBin(
                    lower=lower,
                    upper=upper,
                    ema_alpha=self.ema_alpha,
                )
            )
        return bins

    def _get_bin_index(self, confidence: float) -> int:
        """Get the bin index for a given confidence value."""
        # Clamp to [0, 1]
        confidence = max(0.0, min(1.0, confidence))
        # Handle edge case of confidence = 1.0
        idx = int(confidence * self.num_bins)
        return min(idx, self.num_bins - 1)

    def record(
        self,
        predictions: list[dict[str, Any]],
        actual_success: bool,
        task_context: dict[str, Any] | None = None,
        agent_domain: str = "unknown",
        duration_ms: float = 0.0,
    ) -> float:
        """Record prediction outcomes and compute calibration error.

        Args:
            predictions: List of prediction dicts with 'confidence', 'threat_score', etc.
            actual_success: Whether the executed action succeeded
            task_context: Optional task context for debugging
            agent_domain: Agent's domain for domain-specific calibration
            duration_ms: Execution duration

        Returns:
            Calibration error (average over all predictions)
        """
        if not predictions:
            return 0.0

        total_error = 0.0

        for pred in predictions:
            confidence = pred.get("confidence", 0.5)
            threat_score = pred.get("threat_score", 0.0)
            uncertainty = pred.get("uncertainty", 0.5)
            action_type = pred.get("action", pred.get("action_type", "unknown"))
            if isinstance(action_type, dict):
                action_type = action_type.get("type", "unknown")

            # Record in global bins
            bin_idx = self._get_bin_index(confidence)
            error = self._bins[bin_idx].record(confidence, actual_success)
            total_error += error

            # Record in domain-specific bins
            if self.enable_domain_specific:
                if agent_domain not in self._domain_bins:
                    self._domain_bins[agent_domain] = self._create_bins()
                self._domain_bins[agent_domain][bin_idx].record(confidence, actual_success)

            # Store record with optional task context for debugging
            record = CalibrationRecord(
                confidence=confidence,
                threat_score=threat_score,
                uncertainty=uncertainty,
                actual_success=actual_success,
                duration_ms=duration_ms,
                action_type=str(action_type),
                agent_domain=agent_domain,
            )
            # Attach task_context metadata for debugging if provided
            if task_context is not None:
                record.task_context = task_context  # type: ignore[attr-defined]
            self._recent_records.append(record)

        self._total_records += len(predictions)

        # Update running ECE
        avg_error = total_error / len(predictions)
        self._running_ece = self.ema_alpha * avg_error + (1 - self.ema_alpha) * self._running_ece

        return avg_error

    def adjust_confidence(
        self,
        raw_confidence: float,
        domain: str | None = None,
    ) -> float:
        """Adjust a raw confidence value based on calibration history.

        Args:
            raw_confidence: The world model's raw confidence prediction
            domain: Optional domain for domain-specific adjustment

        Returns:
            Calibrated confidence value
        """
        # Get the relevant bins
        if domain and domain in self._domain_bins:
            bins = self._domain_bins[domain]
        else:
            bins = self._bins

        bin_idx = self._get_bin_index(raw_confidence)
        adjustment = bins[bin_idx].adjustment_factor

        # Apply adjustment with smoothing toward 1.0
        # This prevents over-correction when we have few samples
        n_samples = bins[bin_idx].total_predictions
        smoothing = min(1.0, n_samples / 50)  # Full adjustment after 50 samples
        effective_adjustment = 1.0 + smoothing * (adjustment - 1.0)

        adjusted = raw_confidence * effective_adjustment

        # Clamp to valid range
        return max(0.01, min(0.99, adjusted))

    def compute_expected_calibration_error(self) -> float:
        """Compute Expected Calibration Error (ECE) across all bins.

        ECE = sum_b (n_b / N) * |accuracy_b - confidence_b|

        Returns:
            ECE value in [0, 1]
        """
        total_samples = sum(b.total_predictions for b in self._bins)
        if total_samples == 0:
            return 0.0

        ece = 0.0
        for bin_ in self._bins:
            if bin_.total_predictions > 0:
                weight = bin_.total_predictions / total_samples
                ece += weight * bin_.calibration_error

        return ece

    def get_calibration_report(self) -> dict[str, Any]:
        """Generate a comprehensive calibration report.

        Returns:
            Dict with calibration metrics and per-bin statistics
        """
        return {
            "expected_calibration_error": self.compute_expected_calibration_error(),
            "running_ece": self._running_ece,
            "total_records": self._total_records,
            "bins": [
                {
                    "range": f"{b.lower:.1f}-{b.upper:.1f}",
                    "predictions": b.total_predictions,
                    "success_rate": b.empirical_success_rate,
                    "ema_success_rate": b.ema_success_rate,
                    "calibration_error": b.calibration_error,
                    "adjustment_factor": b.adjustment_factor,
                }
                for b in self._bins
            ],
            "domain_ece": {
                domain: sum(b.calibration_error for b in bins) / len(bins)
                for domain, bins in self._domain_bins.items()
            },
        }

    def get_adjustment_matrix(self) -> np.ndarray[Any, Any]:
        """Get adjustment factors as a matrix for vectorized operations.

        Returns:
            [num_bins] array of adjustment factors
        """
        return np.array([b.adjustment_factor for b in self._bins], dtype=np.float32)


# Global singleton instance
_calibration_tracker: CalibrationTracker | None = None


def get_calibration_tracker() -> CalibrationTracker:
    """Get global calibration tracker instance."""
    global _calibration_tracker
    if _calibration_tracker is None:
        _calibration_tracker = CalibrationTracker()
    return _calibration_tracker


def reset_calibration_tracker() -> None:
    """Reset global calibration tracker (for testing)."""
    global _calibration_tracker
    _calibration_tracker = None


try:
    import torch
    import torch.nn as nn

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


class TemperatureScaler:
    """Temperature scaling for calibrated confidence estimates.

    Temperature scaling is a simple post-hoc calibration method:
    - T > 1: Makes probabilities softer (less confident)
    - T < 1: Makes probabilities sharper (more confident)
    - T = 1: No change

    The optimal temperature T* minimizes negative log-likelihood on
    a held-out calibration set[Any].

    This class works both with and without PyTorch. When PyTorch is available,
    it provides a `.temperature` tensor and gradient-based calibration.
    When PyTorch is not available, it uses pure Python.

    Reference: Guo et al. (2017) "On Calibration of Modern Neural Networks"
    """

    def __init__(self, temperature: float = 1.0):
        """Initialize temperature scaler.

        Args:
            temperature: Initial temperature (default 1.0 = no scaling)
        """
        if _TORCH_AVAILABLE:
            self.temperature = nn.Parameter(torch.tensor([temperature]))
        else:
            self._temperature = temperature
        self._calibration_data: list[tuple[float, bool]] = []

    def __call__(self, logits: torch.Tensor | float) -> torch.Tensor | float:
        """Apply temperature scaling to logits.

        Args:
            logits: Raw logits (tensor or float)

        Returns:
            Scaled logits (same type as input)
        """
        if _TORCH_AVAILABLE and isinstance(logits, torch.Tensor):
            return logits / self.temperature
        else:
            temp = self.temperature.item() if _TORCH_AVAILABLE else self._temperature
            if hasattr(logits, "__iter__") and not isinstance(logits, (str, bytes)):
                return [l / temp for l in logits]  # type: ignore[return-value]
            return logits / temp

    def scale(self, logits_or_probs: float, is_logits: bool = False) -> float:
        """Apply temperature scaling.

        Args:
            logits_or_probs: Raw logits or probability
            is_logits: If True, input is logits; if False, input is probability

        Returns:
            Calibrated probability
        """
        temp = self.temperature.item() if _TORCH_AVAILABLE else self._temperature

        if is_logits:
            # Apply temperature to logits
            scaled_logit = logits_or_probs / temp
            return 1.0 / (1.0 + math.exp(-scaled_logit))
        else:
            # Convert prob to logit, scale, convert back
            prob = max(1e-7, min(1 - 1e-7, logits_or_probs))
            logit = math.log(prob / (1 - prob))
            scaled_logit = logit / temp
            return 1.0 / (1.0 + math.exp(-scaled_logit))

    def add_calibration_point(self, predicted_prob: float, actual_success: bool) -> None:
        """Add a calibration data point.

        Args:
            predicted_prob: Model's predicted probability
            actual_success: Whether the prediction was correct
        """
        self._calibration_data.append((predicted_prob, actual_success))

    def calibrate(
        self,
        confidence_scores: torch.Tensor | list[float],
        accuracy_scores: torch.Tensor | list[float],
        num_epochs: int = 100,
        lr: float = 0.01,
    ) -> float:
        """Calibrate temperature using gradient descent.

        Args:
            confidence_scores: Predicted confidence values
            accuracy_scores: Binary accuracy (0 or 1)
            num_epochs: Number of optimization epochs
            lr: Learning rate

        Returns:
            Final temperature value
        """
        if not _TORCH_AVAILABLE:
            # Fallback to grid search
            return self.optimize_temperature()

        # Ensure tensors
        if not isinstance(confidence_scores, torch.Tensor):
            confidence_scores = torch.tensor(confidence_scores, dtype=torch.float32)
        if not isinstance(accuracy_scores, torch.Tensor):
            accuracy_scores = torch.tensor(accuracy_scores, dtype=torch.float32)

        # Reset temperature to 1.0 before optimization
        self.temperature.data = torch.tensor([1.0])

        optimizer = torch.optim.LBFGS([self.temperature], lr=lr, max_iter=num_epochs)

        def closure() -> Any:
            optimizer.zero_grad()
            # Convert confidence to logit, scale, compute NLL
            conf_clamped = torch.clamp(confidence_scores, 1e-7, 1 - 1e-7)
            logits = torch.log(conf_clamped / (1 - conf_clamped))
            scaled_logits = logits / self.temperature
            probs = torch.sigmoid(scaled_logits)

            # Binary cross-entropy loss
            eps = 1e-7
            loss = -torch.mean(
                accuracy_scores * torch.log(probs + eps)
                + (1 - accuracy_scores) * torch.log(1 - probs + eps)
            )
            loss.backward()
            return loss

        optimizer.step(closure)

        # Clamp temperature to reasonable range
        self.temperature.data = torch.clamp(self.temperature.data, 0.1, 10.0)

        return self.temperature.item()

    def optimize_temperature(self) -> float:
        """Find optimal temperature by minimizing NLL on calibration data.

        Returns:
            Optimal temperature value
        """
        if len(self._calibration_data) < 10:
            logger.warning(
                "Not enough calibration data, keeping T=%.2f",
                self.temperature.item() if _TORCH_AVAILABLE else self._temperature,
            )
            return self.temperature.item() if _TORCH_AVAILABLE else self._temperature

        best_t = 1.0
        best_nll = float("inf")

        # Grid search over temperature values
        for t in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]:
            nll = self._compute_nll(t)
            if nll < best_nll:
                best_nll = nll
                best_t = t

        if _TORCH_AVAILABLE:
            self.temperature.data = torch.tensor([best_t])
        else:
            self._temperature = best_t

        logger.info("Optimized temperature to T=%.2f (NLL=%.4f)", best_t, best_nll)
        return best_t

    def _compute_nll(self, temperature: float) -> float:
        """Compute negative log-likelihood for a given temperature."""
        total_nll = 0.0
        for prob, success in self._calibration_data:
            # Convert to logit, scale, convert back
            prob = max(1e-7, min(1 - 1e-7, prob))
            logit = math.log(prob / (1 - prob))
            scaled_prob = 1.0 / (1.0 + math.exp(-logit / temperature))

            # NLL: -log(p) if success, -log(1-p) if failure
            if success:
                total_nll -= math.log(max(1e-7, scaled_prob))
            else:
                total_nll -= math.log(max(1e-7, 1 - scaled_prob))

        return total_nll / len(self._calibration_data)


def compute_ece(
    confidence_scores: np.ndarray[Any, Any] | list[float],
    accuracy_scores: np.ndarray[Any, Any] | list[float],
    n_bins: int = 10,
) -> tuple[float, np.ndarray[Any, Any]]:
    """Compute Expected Calibration Error (ECE).

    ECE = sum_b (n_b / N) * |accuracy_b - confidence_b|

    Args:
        confidence_scores: Array of predicted confidence values [0, 1]
        accuracy_scores: Array of binary accuracy (0 or 1) or success rates
        n_bins: Number of calibration bins (default 10)

    Returns:
        Tuple of (ECE value in [0, 1], bin_counts array)

    Example:
        >>> confidences = [0.9, 0.8, 0.7, 0.6]
        >>> accuracies = [1, 1, 0, 0]  # 50% actual accuracy
        >>> ece, counts = compute_ece(confidences, accuracies)
        >>> print(f"ECE: {ece:.4f}")
    """
    confidence_scores = np.asarray(confidence_scores)
    accuracy_scores = np.asarray(accuracy_scores)

    if len(confidence_scores) == 0:
        return 0.0, np.zeros(n_bins)

    n_samples = len(confidence_scores)
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    bin_counts = np.zeros(n_bins)

    for i in range(n_bins):
        lower = bin_boundaries[i]
        upper = bin_boundaries[i + 1]

        # Find samples in this bin
        in_bin = (confidence_scores > lower) & (confidence_scores <= upper)
        n_in_bin = np.sum(in_bin)
        bin_counts[i] = n_in_bin

        if n_in_bin > 0:
            # Average confidence and accuracy in this bin
            avg_confidence = np.mean(confidence_scores[in_bin])
            avg_accuracy = np.mean(accuracy_scores[in_bin])

            # Weighted calibration error
            ece += (n_in_bin / n_samples) * abs(avg_accuracy - avg_confidence)

    return float(ece), bin_counts


__all__ = [
    "CalibrationBin",
    "CalibrationRecord",
    "CalibrationTracker",
    "TemperatureScaler",
    "compute_ece",
    "get_calibration_tracker",
    "reset_calibration_tracker",
]
