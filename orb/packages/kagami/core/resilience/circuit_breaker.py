"""Circuit breaker pattern implementation.

Prevents cascading failures by stopping calls to failing dependencies.

Usage:
    breaker = CircuitBreaker(failure_threshold=5, timeout=60)

    try:
        result = await breaker.call(redis.get, "key")
    except CircuitOpen:
        # Use fallback
        result = await db.query(...)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

# Import shared config (CONSOLIDATED: Jan 11, 2026)
from kagami.core.config.shared import CircuitBreakerConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, stop calling
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitOpen(Exception):
    """Raised when circuit breaker is open."""

    pass


# CircuitBreakerConfig is now imported from kagami.core.config.shared
# Re-exported for backward compatibility
# Note: Use config.timeout_seconds for backward compatibility (aliased to recovery_timeout)


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures.

    States:
    - CLOSED: Normal operation (calls pass through)
    - OPEN: Too many failures, stop calling (return error immediately)
    - HALF_OPEN: Testing recovery (allow 1 call, then decide)

    Transitions:
    - CLOSED → OPEN: After failure_threshold consecutive failures
    - OPEN → HALF_OPEN: After timeout seconds
    - HALF_OPEN → CLOSED: If test call succeeds
    - HALF_OPEN → OPEN: If test call fails
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        success_threshold: int = 1,
        name: str | None = None,
        config: CircuitBreakerConfig | None = None,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting recovery
            success_threshold: Successful calls needed to close circuit
            name: Optional name for logging
            config: Optional CircuitBreakerConfig (overrides individual params)
        """
        if config is not None:
            self.failure_threshold = config.failure_threshold
            self.timeout = config.timeout_seconds
            self.success_threshold = config.success_threshold
        else:
            self.failure_threshold = failure_threshold
            self.timeout = timeout
            self.success_threshold = success_threshold
        self.name = name or "anonymous"

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is currently open."""
        return self._state == CircuitState.OPEN

    async def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function through circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of function call

        Raises:
            CircuitOpen: If circuit is open
            Any exception from func
        """
        async with self._lock:
            # Check if we should attempt recovery
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.timeout:
                    logger.info(f"Circuit breaker {self.name}: OPEN → HALF_OPEN (testing recovery)")
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                else:
                    raise CircuitOpen(
                        f"Circuit breaker {self.name} is OPEN "
                        f"(retry in {self.timeout - (time.time() - self._last_failure_time):.1f}s)"
                    )

        # Attempt call
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Success
            async with self._lock:
                self._on_success()

            return result

        except Exception:
            # Failure
            async with self._lock:
                self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful call."""
        self._failure_count = 0

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN → CLOSED (recovered)")
                self._state = CircuitState.CLOSED
                self._success_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Recovery test failed
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN → OPEN (recovery test failed)")
            self._state = CircuitState.OPEN
            self._failure_count = 0

        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker {self.name}: CLOSED → OPEN "
                    f"({self._failure_count} failures, threshold={self.failure_threshold})"
                )
                self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        logger.info(f"Circuit breaker {self.name}: Manually reset to CLOSED")

    def get_stats(self) -> dict[str, Any]:
        """Get current breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "time_until_retry": (
                max(0, self.timeout - (time.time() - self._last_failure_time))
                if self._state == CircuitState.OPEN
                else 0
            ),
        }


# Alias for backward compatibility
CircuitBreakerOpen = CircuitOpen

# Global circuit breaker registry
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout: float = 60.0,
    success_threshold: int = 1,
) -> CircuitBreaker:
    """Get or create a named circuit breaker.

    Args:
        name: Unique name for the circuit breaker
        failure_threshold: Number of failures before opening circuit
        timeout: Seconds to wait before attempting recovery
        success_threshold: Successful calls needed to close circuit

    Returns:
        The circuit breaker instance (creates if doesn't exist)
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout=timeout,
            success_threshold=success_threshold,
            name=name,
        )
    return _circuit_breakers[name]


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers to CLOSED state."""
    for breaker in _circuit_breakers.values():
        breaker.reset()
