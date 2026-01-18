"""Resilience patterns for antifragile systems.

This module provides battle-tested patterns for:
- Circuit breakers (stop calling failed dependencies) ✅ IMPLEMENTED
- Bulkheads (isolate resources to prevent cascading failures) ⏳ DESIGNED
- Rate limiters (prevent resource exhaustion) ⏳ DESIGNED
- Retry logic (exponential backoff) ⏳ DESIGNED
- Timeouts (fail fast) ⏳ DESIGNED
- Fallbacks (graceful degradation) ⏳ DESIGNED

Based on adversarial audit findings (Jan 5, 2026).
"""

from kagami.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpen,
    CircuitState,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitOpen",
    "CircuitState",
]

# Future patterns (circuit breaker implemented, these are on backlog):
# from kagami.core.resilience.bulkhead import Bulkhead, BulkheadConfig
# from kagami.core.resilience.rate_limiter import RateLimiter, TokenBucket
# from kagami.core.resilience.retry import retry_with_backoff, RetryConfig
# from kagami.core.resilience.timeout import with_timeout, TimeoutError
# from kagami.core.resilience.fallback import with_fallback, FallbackChain
