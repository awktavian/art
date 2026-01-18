
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration


import time

from kagami.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from kagami_integrations.resilience import call_with_resilience_sync


def test_circuit_breaker_opens_and_closes():
    config = CircuitBreakerConfig(failure_threshold=2, timeout_seconds=1.0)
    br = CircuitBreaker(name="test", config=config)

    calls = {"n": 0}

    async def flaky_async():
        calls["n"] += 1
        raise RuntimeError("boom")

    # Two failures → open (circuit breaker needs async)
    import asyncio

    for _ in range(2):
        try:
            asyncio.run(br.call(flaky_async))
        except Exception:
            pass
    assert br.is_open is True

    # While open, fast-fail with on_open_return
    val = call_with_resilience_sync(
        integration="x",
        operation="y",
        fn=lambda: 1,
        attempts=1,
        breaker=br,
        on_open_return=0,
    )
    assert val == 0

    # After recovery window, make a call to trigger state transition to HALF_OPEN
    time.sleep(1.1)

    # Circuit breaker needs a call to transition from OPEN → HALF_OPEN
    # Successful call will then close it
    async def success_async():
        return "ok"

    # This call should succeed and close the breaker
    result = asyncio.run(br.call(success_async))
    assert result == "ok"
    assert br.is_open is False
