"""Circuit breaker decorator for Forge modules.

Re-exports circuit breaker functionality from kagami.core.resilience
with a convenient decorator for Forge service calls.

Created: December 8, 2025
"""

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from kagami.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitState,
    get_circuit_breaker,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Re-export for convenience
__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpen",
    "CircuitState",
    "get_circuit_breaker",
    "with_circuit_breaker",
]


def with_circuit_breaker(
    name: str | None = None,
    failure_threshold: int = 5,
    timeout_seconds: float = 60.0,
) -> Callable[[F], F]:
    """Decorator to wrap a function with circuit breaker protection.

    Uses the global circuit breaker registry to ensure breakers are tracked
    and can be inspected via get_all_circuit_breakers().

    Args:
        name: Circuit breaker name (defaults to function name)
        failure_threshold: Failures before opening
        timeout_seconds: Time before trying half-open

    Usage:
        @with_circuit_breaker("llm_service")
        async def call_llm(prompt: str) -> str:
            ...
    """

    def decorator(func: F) -> F:
        breaker_name = name or func.__name__
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds,
        )
        # Use get_circuit_breaker to register in global registry
        breaker = get_circuit_breaker(breaker_name, config)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await breaker.call(func, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
