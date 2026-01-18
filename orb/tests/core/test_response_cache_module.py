from __future__ import annotations

import pytest
import asyncio
import hashlib
import json
import time

from kagami.core.caching.response_cache import ResponseCache, CacheConfig


def _intent_to_key(intent: dict) -> str:
    """Convert intent dict to stable cache key."""
    return hashlib.sha256(json.dumps(intent, sort_keys=True).encode()).hexdigest()[:16]


@pytest.mark.asyncio
async def test_cache_hit_miss_and_eviction():
    # Disable Redis for LRU testing (Redis doesn't have size limits)
    config = CacheConfig(max_size=2, ttl=1.0, enable_redis=False)
    cache = ResponseCache(config=config, namespace="test")

    intent1 = {"action": "query.items", "params": {"q": "a"}, "target": "t"}
    intent2 = {"action": "query.items", "params": {"q": "b"}, "target": "t"}
    intent3 = {"action": "query.items", "params": {"q": "c"}, "target": "t"}

    key1 = _intent_to_key(intent1)
    key2 = _intent_to_key(intent2)
    key3 = _intent_to_key(intent3)

    assert await cache.get(key1) is None
    await cache.set(key1, {"ok": 1})
    assert await cache.get(key1) == {"ok": 1}

    await cache.set(key2, {"ok": 2})
    # Evict LRU when adding third
    await cache.set(key3, {"ok": 3})

    # One of the first two must be evicted (LRU = key1)
    assert await cache.get(key1) is None
    assert await cache.get(key2) == {"ok": 2}
    assert await cache.get(key3) == {"ok": 3}

    # TTL expiry
    await asyncio.sleep(1.1)
    assert await cache.get(key2) is None
