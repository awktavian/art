from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from kagami.core.resilience.circuit_breaker import CircuitBreaker
from kagami.observability.metrics import (
    EXTERNAL_ERRORS_TOTAL,
    EXTERNAL_REQUEST_DURATION,
)

T = TypeVar("T")


def call_with_resilience_sync(
    integration: str,
    operation: str,
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_backoff: float = 0.1,
    cap_backoff: float = 2.0,
    breaker: CircuitBreaker | None = None,
    on_open_return: T | None = None,
) -> T:
    """Execute a synchronous external call with retries, backoff, and circuit breaker.

    Metrics are recorded under EXTERNAL_REQUEST_DURATION and EXTERNAL_ERRORS_TOTAL.
    If the breaker is open and `on_open_return` is provided, return it immediately;
    otherwise, raise RuntimeError("<integration>_circuit_open").
    """
    start = time.perf_counter()
    if breaker and breaker.is_open:
        try:
            EXTERNAL_ERRORS_TOTAL.labels(integration, "circuit_open").inc()
        except Exception:
            pass
        if on_open_return is not None:
            return on_open_return
        raise RuntimeError(f"{integration}_circuit_open") from None

    last_err: Exception | None = None
    effective_attempts = max(1, int(attempts))
    for attempt in range(effective_attempts):
        try:
            result = fn()
            return result
        except Exception as e:
            last_err = e
            # Backoff if more attempts remain
            if attempt < effective_attempts - 1:
                backoff = min(cap_backoff, base_backoff * (2**attempt))
                jitter = random.uniform(0, 0.5 * backoff)
                try:
                    time.sleep(backoff + jitter)
                except Exception:
                    pass
                continue
            # Exhausted attempts
            try:
                EXTERNAL_ERRORS_TOTAL.labels(integration, type(e).__name__).inc()
            except Exception:
                pass
            break
    # Duration metric (only once per call wrapper)
    try:
        EXTERNAL_REQUEST_DURATION.labels(integration, operation or "unknown").observe(
            time.perf_counter() - start
        )
    except Exception:
        pass
    # Raise final error
    raise last_err if last_err is not None else RuntimeError("external_error") from None


async def call_with_resilience_async(
    integration: str,
    operation: str,
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_backoff: float = 0.1,
    cap_backoff: float = 2.0,
    breaker: CircuitBreaker | None = None,
    on_open_return: T | None = None,
) -> T:
    """Execute an async external call with retries, backoff, and circuit breaker.

    Records EXTERNAL_REQUEST_DURATION and EXTERNAL_ERRORS_TOTAL.
    """
    start = time.perf_counter()
    if breaker and breaker.is_open:
        try:
            EXTERNAL_ERRORS_TOTAL.labels(integration, "circuit_open").inc()
        except Exception:
            pass
        if on_open_return is not None:
            return on_open_return
        raise RuntimeError(f"{integration}_circuit_open") from None

    last_err: Exception | None = None
    effective_attempts = max(1, int(attempts))
    for attempt in range(effective_attempts):
        try:
            result = await fn()
            return result
        except Exception as e:
            last_err = e
            if attempt < effective_attempts - 1:
                backoff = min(cap_backoff, base_backoff * (2**attempt))
                jitter = random.uniform(0, 0.5 * backoff)
                try:
                    await asyncio.sleep(backoff + jitter)
                except Exception:
                    pass
                continue
            try:
                EXTERNAL_ERRORS_TOTAL.labels(integration, type(e).__name__).inc()
            except Exception:
                pass
            break
    try:
        EXTERNAL_REQUEST_DURATION.labels(integration, operation or "unknown").observe(
            time.perf_counter() - start
        )
    except Exception:
        pass
    raise last_err if last_err is not None else RuntimeError("external_error") from None
