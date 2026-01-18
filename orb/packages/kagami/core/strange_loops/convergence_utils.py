from __future__ import annotations

"Convergence detection utilities for fixed-point iteration.\n\nProvides mathematical tools for detecting convergence, divergence, and oscillation\nin iterative refinement processes.\n"
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ConvergenceResult:
    """Result of convergence analysis."""

    converged: bool
    iterations: int
    final_distance: float
    convergence_rate: float | None = None
    reason: str = ""


class ConvergenceDetector:
    """Detect convergence in iterative fixed-point processes.

    Based on:
    - Distance threshold (||x_{n+1} - x_n|| < ε)
    - Rate of change (exponential decay expected)
    - Oscillation detection (cycling through same states)
    """

    def __init__(
        self, epsilon: float = 0.01, max_iterations: int = 10, min_progress_rate: float = 0.1
    ) -> None:
        """Initialize convergence detector.

        Args:
            epsilon: Convergence threshold (distance < epsilon → converged)
            max_iterations: Maximum iterations before timeout
            min_progress_rate: Minimum fractional progress per iteration
        """
        self.epsilon = epsilon
        self.max_iterations = max_iterations
        self.min_progress_rate = min_progress_rate
        self.distance_history: list[float] = []
        self.state_history: list[Any] = []

    def check_convergence(self, current_distance: float, iteration: int) -> ConvergenceResult:
        """Check if iteration has converged.

        Args:
            current_distance: Distance between current and previous iterate
            iteration: Current iteration number

        Returns:
            ConvergenceResult with convergence status and diagnostics
        """
        self.distance_history.append(current_distance)
        if current_distance < self.epsilon:
            rate = self._estimate_convergence_rate()
            return ConvergenceResult(
                converged=True,
                iterations=iteration,
                final_distance=current_distance,
                convergence_rate=rate,
                reason="distance_threshold",
            )
        if iteration >= self.max_iterations:
            return ConvergenceResult(
                converged=False,
                iterations=iteration,
                final_distance=current_distance,
                reason="max_iterations_reached",
            )
        if len(self.distance_history) >= 3:
            recent = self.distance_history[-3:]
            if max(recent) - min(recent) < self.epsilon * 0.1:
                return ConvergenceResult(
                    converged=False,
                    iterations=iteration,
                    final_distance=current_distance,
                    reason="stagnation_detected",
                )
        if len(self.distance_history) >= 2:
            if current_distance > self.distance_history[0] * 2.0:
                return ConvergenceResult(
                    converged=False,
                    iterations=iteration,
                    final_distance=current_distance,
                    reason="divergence_detected",
                )
        return ConvergenceResult(
            converged=False,
            iterations=iteration,
            final_distance=current_distance,
            reason="iterating",
        )

    def _estimate_convergence_rate(self) -> float | None:
        """Estimate convergence rate from distance history.

        For contractive mappings, expect exponential decay:
        d_n ≈ d_0 · α^n where α < 1

        Returns:
            Estimated contraction factor α, or None if insufficient data
        """
        if len(self.distance_history) < 3:
            return None
        ratios = []
        for i in range(1, len(self.distance_history)):
            if self.distance_history[i - 1] > 1e-08:
                ratio = self.distance_history[i] / self.distance_history[i - 1]
                if 0 < ratio < 2.0:
                    ratios.append(ratio)
        if not ratios:
            return None
        alpha = np.mean(ratios)
        return float(alpha)

    def reset(self) -> None:
        """Reset history for new iteration sequence."""
        self.distance_history.clear()
        self.state_history.clear()


def compute_embedding_distance(
    embedding1: np.ndarray | list[float],
    embedding2: np.ndarray | list[float],
    metric: str = "l2",
) -> float:
    """Compute distance between embeddings.

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        metric: Distance metric ("l2", "cosine", "l1")

    Returns:
        Distance (non-negative float)
    """
    emb1 = np.asarray(embedding1, dtype=np.float32)
    emb2 = np.asarray(embedding2, dtype=np.float32)
    if metric == "l2":
        distance = float(np.linalg.norm(emb1 - emb2))
    elif metric == "cosine":
        dot = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 < 1e-08 or norm2 < 1e-08:
            distance = 1.0
        else:
            cosine_sim = dot / (norm1 * norm2)
            distance = float(1.0 - cosine_sim)
    elif metric == "l1":
        distance = float(np.sum(np.abs(emb1 - emb2)))
    else:
        raise ValueError(f"Unknown metric: {metric}")
    return distance


def is_contractive(distances: list[float], threshold: float = 1.0) -> tuple[bool, float]:
    """Check if iteration sequence is contractive.

    A mapping is contractive if d(T(x), T(y)) ≤ α·d(x, y) where α < 1.

    Args:
        distances: Sequence of distances between consecutive iterates
        threshold: Maximum allowed contraction factor (< 1.0 for contraction)

    Returns:
        (is_contractive, estimated_alpha)
    """
    if len(distances) < 2:
        return (False, 1.0)
    ratios = []
    for i in range(1, len(distances)):
        if distances[i - 1] > 1e-08:
            ratio = distances[i] / distances[i - 1]
            ratios.append(ratio)
    if not ratios:
        return (False, 1.0)
    alpha = float(np.mean(ratios))
    is_contract = alpha < threshold
    return (is_contract, alpha)


def detect_oscillation(
    state_history: list[Any], window: int = 5, similarity_threshold: float = 0.99
) -> bool:
    """Detect if iteration is oscillating (cycling through states).

    Args:
        state_history: Sequence of states (as hashable objects or embeddings)
        window: Size of window to check for cycles
        similarity_threshold: Threshold for considering states identical

    Returns:
        True if oscillation detected
    """
    if len(state_history) < window * 2:
        return False
    recent = state_history[-window:]
    for i in range(len(state_history) - window * 2, 0, -1):
        candidate = state_history[i : i + window]
        matches = 0
        for r, c in zip(recent, candidate, strict=False):
            if r == c:
                matches += 1
            elif isinstance(r, (list, np.ndarray)) and isinstance(c, (list[Any], np.ndarray)):
                distance = compute_embedding_distance(r, c)
                if distance < 1 - similarity_threshold:
                    matches += 1
        if matches >= window * 0.8:
            return True
    return False
