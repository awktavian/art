"""Resilience patterns for fault-tolerant systems.

This module provides:
- CircuitBreaker: Prevent cascading failures
- Retry: Exponential backoff for transient failures

Example:
    >>> from kagami.core.patterns import CircuitBreaker, retry
    >>>
    >>> # Using circuit breaker
    >>> breaker = CircuitBreaker(failure_threshold=5)
    >>> async with breaker:
    ...     result = await external_api()
    >>>
    >>> # Using retry decorator
    >>> @retry(max_attempts=5, base_delay=1.0)
    ... async def fetch_data():
    ...     return await api.get("/data")
"""

# Re-export from canonical location (kagami.core.resilience.circuit_breaker)
from kagami.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    get_circuit_breaker,
)
from kagami.core.resilience.circuit_breaker import (
    CircuitOpen as CircuitBreakerError,  # Alias for backward compatibility
)


# Stats wrapper for backward compatibility
def get_all_circuit_breaker_stats() -> dict:
    """Get statistics for all circuit breakers."""
    from kagami.core.resilience.circuit_breaker import _circuit_breakers

    return {name: breaker.get_stats() for name, breaker in _circuit_breakers.items()}


# Backward compatibility - CircuitBreakerStats is no longer a separate class
# Individual breaker stats are accessed via CircuitBreaker.get_stats()
CircuitBreakerStats = dict  # type: ignore[misc]
from kagami.core.patterns.retry import (
    RETRY_AGGRESSIVE,
    RETRY_CONSERVATIVE,
    RETRY_QUICK,
    RetryConfig,
    RetryContext,
    calculate_backoff,
    retry,
)

__all__ = [
    "RETRY_AGGRESSIVE",
    "RETRY_CONSERVATIVE",
    "RETRY_QUICK",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerStats",
    "CircuitState",
    # Retry
    "RetryConfig",
    "RetryContext",
    "calculate_backoff",
    "get_all_circuit_breaker_stats",
    "get_circuit_breaker",
    "retry",
]
