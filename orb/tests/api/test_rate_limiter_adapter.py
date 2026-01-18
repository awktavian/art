"""Tests for RateLimiter (consolidated from adapter)."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration
from unittest.mock import MagicMock
from kagami_api.rate_limiter import RateLimiter
@pytest.mark.asyncio
async def test_adapter_allows_first_requests():
    """Adapter should allow requests within limit."""
    limiter = RateLimiter(requests_per_minute=10, window_size=60)
    allowed, remaining, _reset = await limiter.is_allowed_async("client-001")
    assert allowed is True
    assert remaining == 9  # 10 - 1
@pytest.mark.asyncio
async def test_adapter_rejects_over_limit():
    """Adapter should reject requests exceeding limit."""
    limiter = RateLimiter(requests_per_minute=2, window_size=60)
    # Allow first two
    await limiter.is_allowed_async("client-002")
    await limiter.is_allowed_async("client-002")
    # Third should be rejected
    allowed, remaining, _reset = await limiter.is_allowed_async("client-002")
    assert allowed is False
    assert remaining == 0
def test_adapter_get_client_id():
    """Adapter should extract client_id from request."""
    limiter = RateLimiter()
    # Mock request
    request = MagicMock()
    request.headers.get = lambda k, default="": {
        "X-Real-IP": "192.168.1.1",
        "User-Agent": "test-agent",
    }.get(k, default)
    request.client.host = "192.168.1.1"
    client_id = limiter.get_client_id(request)
    assert "192.168.1.1" in client_id
@pytest.mark.asyncio
async def test_adapter_sync_is_allowed():
    """Sync is_allowed should work outside event loop."""
    limiter = RateLimiter(requests_per_minute=5, window_size=60)
    # Call sync version (no running loop)
    allowed, remaining, _reset = limiter.is_allowed("client-003")
    assert allowed is True
    assert remaining >= 0
@pytest.mark.asyncio
async def test_adapter_reset():
    """Adapter reset should clear client state."""
    limiter = RateLimiter(requests_per_minute=3, window_size=60)
    # Exhaust limit
    await limiter.is_allowed_async("client-004")
    await limiter.is_allowed_async("client-004")
    await limiter.is_allowed_async("client-004")
    allowed, _, _ = await limiter.is_allowed_async("client-004")
    assert allowed is False
    # Reset
    await limiter.reset_async("client-004")
    # Should allow again
    allowed, _, _ = await limiter.is_allowed_async("client-004")
    assert allowed is True
