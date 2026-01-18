"""Worker Lifecycle Management.

Extracted from GeometricWorker to reduce god class complexity.

This module handles:
- Hibernation/wake cycles
- Retirement decisions
- Death/division checks
- Worker cloning
- Circuit breaker pattern (Dec 27, 2025)
- Dynamic health checks

Created: December 21, 2025
Updated: December 27, 2025 - Added circuit breaker for cascade failure prevention
Updated: January 11, 2026 - Consolidated CircuitBreakerConfig to shared module
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import torch

# Import shared config (CONSOLIDATED: Jan 11, 2026)
from kagami.core.config.shared import CircuitBreakerConfig
from kagami.core.exceptions import CircuitOpenError

if TYPE_CHECKING:
    from kagami.core.unified_agents.geometric_worker import GeometricWorker

logger = logging.getLogger(__name__)


# =============================================================================
# CIRCUIT BREAKER (Dec 27, 2025)
# =============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


# CircuitBreakerConfig is now imported from kagami.core.config.shared
# Re-exported for backward compatibility


@dataclass
class CircuitBreakerState:
    """Runtime state for circuit breaker."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0  # For half-open → closed transition
    last_failure_time: float = 0.0
    last_state_change: float = field(default_factory=time.time)
    half_open_calls: int = 0


class CircuitBreaker:
    """Circuit breaker for worker protection.

    PATTERN (Dec 27, 2025):
    =====================
    Implements the circuit breaker pattern to prevent cascade failures:

    CLOSED → [failures ≥ threshold] → OPEN
    OPEN → [timeout elapsed] → HALF_OPEN
    HALF_OPEN → [successes ≥ threshold] → CLOSED
    HALF_OPEN → [any failure] → OPEN

    This protects:
    - Individual workers from repeated failures
    - The organism from cascade effects
    - System resources from exhaustion

    Usage:
        breaker = CircuitBreaker()
        if breaker.can_execute():
            try:
                result = await do_work()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure()
                raise
        else:
            raise CircuitOpenError("Circuit breaker open")
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        """Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
        """
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state.state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self._state.state == CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if execution is allowed.

        Returns:
            True if request can proceed
        """
        if self._state.state == CircuitState.CLOSED:
            return True

        if self._state.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            elapsed = time.time() - self._state.last_failure_time
            if elapsed >= self.config.recovery_timeout:
                self._transition_to_half_open()
                return True
            return False

        # HALF_OPEN: Allow limited calls
        if self._state.half_open_calls < self.config.half_open_max_calls:
            self._state.half_open_calls += 1
            return True
        return False

    def record_success(self) -> None:
        """Record successful execution."""
        if self._state.state == CircuitState.HALF_OPEN:
            self._state.success_count += 1
            if self._state.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        else:
            # Reset failure count on success in closed state
            self._state.failure_count = 0

    def record_failure(self) -> None:
        """Record failed execution."""
        self._state.failure_count += 1
        self._state.last_failure_time = time.time()

        if self._state.state == CircuitState.HALF_OPEN:
            # Any failure in half-open returns to open
            self._transition_to_open()
        elif self._state.failure_count >= self.config.failure_threshold:
            self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self._state.state = CircuitState.OPEN
        self._state.last_state_change = time.time()
        self._state.success_count = 0
        self._state.half_open_calls = 0
        logger.warning(
            f"Circuit breaker OPENED: {self._state.failure_count} failures, "
            f"recovery in {self.config.recovery_timeout}s"
        )

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self._state.state = CircuitState.HALF_OPEN
        self._state.last_state_change = time.time()
        self._state.success_count = 0
        self._state.half_open_calls = 0
        logger.info("Circuit breaker HALF_OPEN: testing recovery")

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self._state.state = CircuitState.CLOSED
        self._state.last_state_change = time.time()
        self._state.failure_count = 0
        self._state.success_count = 0
        self._state.half_open_calls = 0
        logger.info("Circuit breaker CLOSED: normal operation resumed")

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitBreakerState()

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "state": self._state.state.value,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "last_failure": self._state.last_failure_time,
            "last_state_change": self._state.last_state_change,
            "half_open_calls": self._state.half_open_calls,
        }


# =============================================================================
# HEALTH CHECK (Dec 27, 2025)
# =============================================================================


@dataclass
class HealthCheckConfig:
    """Configuration for health checks."""

    interval: float = 10.0  # Seconds between checks
    timeout: float = 5.0  # Timeout for health check
    unhealthy_threshold: int = 3  # Failures before unhealthy
    healthy_threshold: int = 2  # Successes to become healthy


class HealthMonitor:
    """Monitors worker health with configurable checks.

    PATTERN (Dec 27, 2025):
    Continuous health monitoring with:
    - Configurable check interval
    - Threshold-based status transitions
    - Async check execution
    """

    def __init__(
        self,
        check_fn: Callable[[], bool],
        config: HealthCheckConfig | None = None,
    ):
        """Initialize health monitor.

        Args:
            check_fn: Function that returns True if healthy
            config: Health check configuration
        """
        self.check_fn = check_fn
        self.config = config or HealthCheckConfig()
        self._healthy = True
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_check = 0.0
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def is_healthy(self) -> bool:
        """Check if currently healthy."""
        return self._healthy

    async def start(self) -> None:
        """Start background health monitoring."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """Stop health monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            await asyncio.sleep(self.config.interval)
            await self.check()

    async def check(self) -> bool:
        """Perform health check.

        Returns:
            True if healthy
        """
        self._last_check = time.time()

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self.check_fn),
                timeout=self.config.timeout,
            )
            healthy = bool(result)
        except (TimeoutError, Exception) as e:
            logger.debug(f"Health check failed: {e}")
            healthy = False

        if healthy:
            self._consecutive_failures = 0
            self._consecutive_successes += 1
            if not self._healthy and self._consecutive_successes >= self.config.healthy_threshold:
                self._healthy = True
                logger.info("Worker became healthy")
        else:
            self._consecutive_successes = 0
            self._consecutive_failures += 1
            if self._healthy and self._consecutive_failures >= self.config.unhealthy_threshold:
                self._healthy = False
                logger.warning(
                    f"Worker became unhealthy after {self._consecutive_failures} failures"
                )

        return self._healthy

    def get_stats(self) -> dict[str, Any]:
        """Get health monitor statistics."""
        return {
            "healthy": self._healthy,
            "consecutive_failures": self._consecutive_failures,
            "consecutive_successes": self._consecutive_successes,
            "last_check": self._last_check,
            "running": self._running,
        }


class WorkerLifecycle:
    """Manages worker lifecycle transitions.

    Handles:
    - Hibernation (low activity → sleep)
    - Retirement (low fitness or high age → shutdown)
    - Death (fitness collapse)
    - Division (high fitness → spawn child)
    """

    def __init__(
        self,
        worker: GeometricWorker,
        idle_timeout: float = 300.0,
        max_operations: int = 1000,
    ):
        """Initialize lifecycle manager.

        Args:
            worker: Parent worker instance
            idle_timeout: Seconds before hibernation
            max_operations: Max ops before retirement
        """
        self.worker = worker
        self.idle_timeout = idle_timeout
        self.max_operations = max_operations

    def should_retire(self) -> bool:
        """Check if worker should retire.

        Retirement criteria:
        - Too many operations (max_operations)
        - Low fitness with sufficient history

        Returns:
            True if worker should retire
        """
        total_ops = self.worker.state.completed_tasks + self.worker.state.failed_tasks

        # Too many operations
        if total_ops >= self.max_operations:
            return True

        # Too low fitness
        if self.worker.state.fitness < 0.1 and total_ops > 50:
            return True

        return False

    def should_hibernate(self) -> bool:
        """Check if worker should hibernate.

        Returns:
            True if idle timeout exceeded
        """
        idle_time = time.time() - self.worker.state.last_active
        return idle_time > self.idle_timeout

    async def hibernate(self) -> None:
        """Enter hibernation.

        Hibernating workers:
        - Accept no new tasks
        - Preserve state
        - Can be woken
        """
        from kagami.core.unified_agents.geometric_worker import WorkerStatus

        self.worker.state.status = WorkerStatus.HIBERNATING
        logger.info(f"Worker {self.worker.worker_id} entering hibernation")

    async def wake(self) -> None:
        """Wake from hibernation.

        Restores worker to IDLE state.
        """
        from kagami.core.unified_agents.geometric_worker import WorkerStatus

        self.worker.state.status = WorkerStatus.IDLE
        self.worker.state.last_active = time.time()
        logger.info(f"Worker {self.worker.worker_id} woke from hibernation")

    async def retire(self) -> None:
        """Retire worker (graceful shutdown).

        Retired workers:
        - Cannot accept tasks
        - State is preserved for metrics
        - Cannot be reactivated
        """
        from kagami.core.unified_agents.geometric_worker import WorkerStatus

        self.worker.state.status = WorkerStatus.DEAD
        logger.info(
            f"Worker {self.worker.worker_id} retiring: "
            f"completed={self.worker.state.completed_tasks}, "
            f"failed={self.worker.state.failed_tasks}, "
            f"fitness={self.worker.state.fitness:.2f}"
        )

    def should_die(self) -> bool:
        """Check if agent should die (low fitness).

        Death criteria (stricter than retirement):
        - Very low fitness (<0.1)
        - Sufficient task history (>10)

        Returns:
            True if agent should be removed
        """
        return (
            self.worker.state.fitness < 0.1
            and (self.worker.state.completed_tasks + self.worker.state.failed_tasks) > 10
        )

    def should_divide(self) -> bool:
        """Check if agent should divide (high fitness).

        Division criteria:
        - High fitness (>0.8)
        - Sufficient success history (>5 tasks)

        Returns:
            True if agent should spawn child
        """
        return self.worker.state.fitness > 0.8 and self.worker.state.completed_tasks > 5

    def divide(self) -> GeometricWorker:
        """Create a child agent through division.

        Child agent:
        - Same colony assignment
        - Half parent fitness (both parent and child)
        - Slightly mutated H¹⁴ position
        - Shares program library and catastrophe dynamics

        Returns:
            New GeometricWorker child
        """
        from kagami.core.unified_agents.geometric_worker import GeometricWorker

        child = GeometricWorker(
            config=self.worker.config,
            colony_idx=self.worker.config.colony_idx,
        )

        # Inherit half fitness
        child.state.fitness = self.worker.state.fitness * 0.5
        self.worker.state.fitness = self.worker.state.fitness * 0.5

        # Slightly mutate H¹⁴ position
        child.state.h14_position = self.worker.state.h14_position + 0.1 * torch.randn(14)

        # Wire shared resources
        if self.worker._program_library is not None:
            child._program_library = self.worker._program_library  # type: ignore[unreachable]
        if self.worker._catastrophe_dynamics is not None:
            child._catastrophe_dynamics = self.worker._catastrophe_dynamics  # type: ignore[unreachable]

        logger.info(
            f"Worker {self.worker.worker_id} divided → child {child.worker_id} "
            f"(parent fitness: {self.worker.state.fitness:.2f}, "
            f"child fitness: {child.state.fitness:.2f})"
        )

        return child


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerState",
    "CircuitOpenError",
    "CircuitState",
    "HealthCheckConfig",
    "HealthMonitor",
    "WorkerLifecycle",
]
