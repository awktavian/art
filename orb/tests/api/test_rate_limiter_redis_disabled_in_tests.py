from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


def test_redis_rate_limiting_not_enabled_in_tests(monkeypatch: Any) -> None:
    # Ensure test context flag is set so Redis-backed limiter remains disabled
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "rate_limit_test_marker")
    monkeypatch.setenv("KAGAMI_TEST_DISABLE_REDIS", "1")
    monkeypatch.delenv("RATE_LIMIT_USE_REDIS", raising=False)
    # Trigger lazy enable path
    # Should return early and keep in-memory limiters
    import asyncio
    import sys

    # Purge prior imports so eager import branch re-evaluates under test flags
    for mod in ("kagami_api.rate_limiter", "kagami_api"):
        if mod in sys.modules:
            del sys.modules[mod]
    from kagami_api import rate_limiter as rl

    asyncio.get_event_loop().run_until_complete(rl.enable_redis_rate_limiting())
    assert type(rl.api_rate_limiter).__name__ == "RateLimiter"
    assert type(rl.auth_rate_limiter).__name__ == "RateLimiter"
    assert type(rl.public_rate_limiter).__name__ == "RateLimiter"
