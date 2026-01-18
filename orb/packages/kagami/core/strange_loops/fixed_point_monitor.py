from __future__ import annotations

"""Fixed-point iteration monitor with safety guarantees.

Monitors iterative refinement processes and enforces:
- Convergence detection
- Divergence protection
- Oscillation handling
- Timeout limits
"""
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kagami.core.strange_loops.convergence_utils import (
    ConvergenceDetector,
    compute_embedding_distance,
    detect_oscillation,
    is_contractive,
)

logger = logging.getLogger(__name__)


@dataclass
class FixedPointResult:
    """Result of fixed-point iteration."""

    converged: bool
    final_value: Any
    iterations: int
    final_distance: float
    convergence_rate: float | None
    total_time_ms: float
    reason: str
    history: list[dict[str, Any]] = field(default_factory=list[Any])


class FixedPointMonitor:
    """Monitor and enforce safe fixed-point iteration.

    Ensures:
    1. Convergence detection (distance threshold)
    2. Divergence protection (hard limits)
    3. Oscillation detection (cycle detection)
    4. Timeout enforcement
    5. Contraction verification

    Based on Banach fixed-point theorem safety requirements.
    """

    def __init__(
        self,
        epsilon: float = 0.01,
        max_iterations: int = 10,
        max_time_seconds: float = 30.0,
        divergence_threshold: float = 2.0,
        require_contraction: bool = False,
    ) -> None:
        """Initialize fixed-point monitor.

        Args:
            epsilon: Convergence threshold
            max_iterations: Maximum iterations before timeout
            max_time_seconds: Maximum wall-clock time
            divergence_threshold: Multiplier for divergence detection
            require_contraction: Enforce contraction property
        """
        self.epsilon = epsilon
        self.max_iterations = max_iterations
        self.max_time_seconds = max_time_seconds
        self.divergence_threshold = divergence_threshold
        self.require_contraction = require_contraction

        # Internal state
        self.detector = ConvergenceDetector(epsilon=epsilon, max_iterations=max_iterations)
        self.start_time: float | None = None
        self.iteration_history: list[dict[str, Any]] = []

    async def iterate_to_fixpoint(
        self,
        initial_value: Any,
        transformation: Callable[[Any], Any] | Callable[[Any], tuple[Any, dict[str, Any]]],
        distance_fn: Callable[[Any, Any], float] | None = None,
        emit_metrics: Callable[[str, float], None] | None = None,
    ) -> FixedPointResult:
        """Iterate transformation until fixed point reached.

        Args:
            initial_value: Starting value x_0
            transformation: Function T such that T(x) = x* at fixed point
                           Can return (value, metadata) tuple[Any, ...]
            distance_fn: Distance metric (defaults to L2 on embeddings)
            emit_metrics: Optional metrics emission callback

        Returns:
            FixedPointResult with convergence info and final value
        """
        self.start_time = time.time()
        self.detector.reset()
        self.iteration_history.clear()

        current_value = initial_value
        current_embedding = self._extract_embedding(current_value)

        # Initial distance (for divergence check)
        initial_distance: float | None = None

        for iteration in range(self.max_iterations):
            # Apply transformation
            try:
                result = await transformation(current_value)  # type: ignore  # Misc

                # Handle both single value and (value, metadata) returns
                if isinstance(result, tuple) and len(result) == 2:
                    next_value, metadata = result
                else:
                    next_value = result
                    metadata = {}

            except Exception as e:
                logger.error(f"Transformation failed at iteration {iteration}: {e}")
                return self._create_failure_result(
                    current_value,
                    iteration,
                    reason=f"transformation_error: {e}",
                )

            # Compute distance
            next_embedding = self._extract_embedding(next_value)

            if distance_fn:
                try:
                    distance = distance_fn(current_value, next_value)
                except Exception:
                    distance = compute_embedding_distance(current_embedding, next_embedding)
            else:
                distance = compute_embedding_distance(current_embedding, next_embedding)

            # Track initial distance
            if initial_distance is None:
                initial_distance = distance

            # Store history
            self.iteration_history.append(
                {
                    "iteration": iteration,
                    "distance": distance,
                    "value": next_value,
                    "metadata": metadata,
                    "timestamp": time.time() - self.start_time,
                }
            )

            # Emit metrics
            if emit_metrics:
                emit_metrics("fixed_point_iteration_distance", distance)
                emit_metrics("fixed_point_iteration", float(iteration))

            # Check convergence
            convergence_result = self.detector.check_convergence(distance, iteration + 1)

            if convergence_result.converged:
                # Success!
                return self._create_success_result(
                    next_value,
                    iteration + 1,
                    distance,
                    convergence_result.convergence_rate,
                    convergence_result.reason,
                )

            # Check failure modes
            failure = self._check_failure_modes(
                distance,
                initial_distance or 1.0,
                iteration + 1,
            )

            if failure:
                return self._create_failure_result(
                    current_value,  # Return last stable value
                    iteration + 1,
                    reason=failure,
                )

            # Continue iteration
            current_value = next_value
            current_embedding = next_embedding

        # Max iterations reached
        return self._create_failure_result(
            current_value,
            self.max_iterations,
            reason="max_iterations_reached",
        )

    def _extract_embedding(self, value: Any) -> list[float]:
        """Extract embedding vector from value for distance computation.

        Args:
            value: Value to extract embedding from

        Returns:
            Embedding vector (list[Any] of floats)
        """
        # If already an embedding
        if isinstance(value, (list, tuple)):
            return list(value)

        # If numpy array
        try:
            import numpy as np

            if isinstance(value, np.ndarray):
                return value.tolist()  # External lib
        except ImportError:
            pass

        # If dict[str, Any] with 'embedding' key
        if isinstance(value, dict) and "embedding" in value:
            emb = value["embedding"]
            if isinstance(emb, (list, tuple)):
                return list(emb)

        # If string, hash to embedding
        if isinstance(value, str):
            import hashlib

            hash_bytes = hashlib.md5(value.encode(), usedforsecurity=False).digest()
            return [float(b) / 255.0 for b in hash_bytes[:16]]

        # Fallback: Convert to string and hash
        return self._extract_embedding(str(value))

    def _check_failure_modes(
        self,
        current_distance: float,
        initial_distance: float,
        iteration: int,
    ) -> str | None:
        """Check for failure modes (divergence, timeout, oscillation).

        Args:
            current_distance: Current iterate distance
            initial_distance: Initial distance for comparison
            iteration: Current iteration number

        Returns:
            Failure reason string, or None if no failure detected
        """
        # Check timeout
        if self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed > self.max_time_seconds:
                return "timeout_exceeded"

        # Check divergence
        if current_distance > initial_distance * self.divergence_threshold:
            return "divergence_detected"

        # Check oscillation
        if len(self.iteration_history) >= 6:
            values = [h["value"] for h in self.iteration_history]
            if detect_oscillation(values, window=3):
                return "oscillation_detected"

        # Check contraction property (if required)
        if self.require_contraction and len(self.detector.distance_history) >= 3:
            is_contract, alpha = is_contractive(self.detector.distance_history)
            if not is_contract:
                return f"non_contractive (α={alpha:.3f})"

        return None

    def _create_success_result(
        self,
        final_value: Any,
        iterations: int,
        final_distance: float,
        convergence_rate: float | None,
        reason: str,
    ) -> FixedPointResult:
        """Create successful convergence result."""
        elapsed = time.time() - (self.start_time or time.time())

        return FixedPointResult(
            converged=True,
            final_value=final_value,
            iterations=iterations,
            final_distance=final_distance,
            convergence_rate=convergence_rate,
            total_time_ms=elapsed * 1000,
            reason=reason,
            history=self.iteration_history,
        )

    def _create_failure_result(
        self,
        final_value: Any,
        iterations: int,
        reason: str,
    ) -> FixedPointResult:
        """Create failure result."""
        elapsed = time.time() - (self.start_time or time.time())

        final_distance = (
            self.detector.distance_history[-1] if self.detector.distance_history else float("inf")
        )

        return FixedPointResult(
            converged=False,
            final_value=final_value,
            iterations=iterations,
            final_distance=final_distance,
            convergence_rate=None,
            total_time_ms=elapsed * 1000,
            reason=reason,
            history=self.iteration_history,
        )
