"""Custom assertions for kagamiOS test suite."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def assert_latency_under(actual_ms: float, max_ms: float, operation: str = "Operation") -> None:
    """Assert that latency is under the specified maximum."""
    assert actual_ms <= max_ms, f"{operation} latency {actual_ms:.2f}ms exceeds maximum {max_ms}ms"


class PerformanceTimer:
    """Context manager for timing operations with timeout support."""

    def __init__(
        self, max_duration_ms: float, operation: str = "Operation", timeout_enabled: bool = True
    ) -> None:
        self.max_duration_ms = max_duration_ms
        self.operation = operation
        self.timeout_enabled = timeout_enabled
        self.start_time: float | None = None
        self.duration_ms: float | None = None
        self._timeout_task = None

    def __enter__(self) -> PerformanceTimer:
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.duration_ms = (time.time() - self.start_time) * 1000  # type: ignore[operator]
        if exc_type is None and self.timeout_enabled:
            assert_latency_under(self.duration_ms, self.max_duration_ms, self.operation)


class CircuitBreaker:
    """Circuit breaker pattern for preventing cascading failures."""

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "CLOSED"

    def __call__(self, func: F) -> F:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.reset_timeout:  # type: ignore[operator]
                    self.state = "HALF_OPEN"
                else:
                    raise AssertionError(
                        f"Circuit breaker OPEN: {func.__name__} temporarily disabled"
                    )
            try:
                result = await func(*args, **kwargs)
                if self.state == "HALF_OPEN":
                    self.state = "CLOSED"
                    self.failure_count = 0
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                raise e

        return wrapper  # type: ignore[return-value]


def with_circuit_breaker(
    failure_threshold: int = 5, reset_timeout: float = 60.0
) -> Callable[[F], F]:
    """Decorator to add circuit breaker functionality."""

    def decorator(func: F) -> F:
        breaker = CircuitBreaker(failure_threshold, reset_timeout)
        return breaker(func)

    return decorator
