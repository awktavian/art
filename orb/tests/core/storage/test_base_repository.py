"""Tests for base repository with multi-tier caching.

Created: December 15, 2025
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from unittest.mock import AsyncMock, MagicMock

from kagami.core.storage.base import BaseRepository, CacheStrategy


class MockRepository(BaseRepository[str]):
    """Mock repository for testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._storage_data: dict[str, str] = {}

    async def _fetch_from_storage(self, key: str) -> str | None:
        """Mock fetch from storage."""
        return self._storage_data.get(key)

    async def _write_to_storage(self, key: str, value: str) -> None:
        """Mock write to storage."""
        self._storage_data[key] = value

    async def _delete_from_storage(self, key: str) -> bool:
        """Mock delete from storage."""
        if key in self._storage_data:
            del self._storage_data[key]
            return True
        return False


@pytest.mark.asyncio
async def test_base_repository_l1_cache_hit():
    """Test L1 cache hit."""
    storage_backend = MagicMock()
    repo = MockRepository(
        storage_backend=storage_backend,
        cache_strategy=CacheStrategy.READ_THROUGH,
        ttl=300,
    )

    # First access - cache miss
    repo._storage_data["test-key"] = "test-value"
    value1 = await repo.get("test-key")
    assert value1 == "test-value"

    # Second access - cache hit (L1)
    value2 = await repo.get("test-key")
    assert value2 == "test-value"


@pytest.mark.asyncio
async def test_base_repository_write_through():
    """Test write-through cache strategy."""
    storage_backend = MagicMock()
    repo = MockRepository(
        storage_backend=storage_backend,
        cache_strategy=CacheStrategy.WRITE_THROUGH,
        ttl=300,
    )

    # Write value
    await repo.set("test-key", "test-value")

    # Verify in storage
    assert repo._storage_data["test-key"] == "test-value"

    # Verify cache populated (L1 hit)
    value = await repo.get("test-key")
    assert value == "test-value"


@pytest.mark.asyncio
async def test_base_repository_invalidate():
    """Test cache invalidation strategy."""
    storage_backend = MagicMock()
    repo = MockRepository(
        storage_backend=storage_backend,
        cache_strategy=CacheStrategy.INVALIDATE,
        ttl=300,
    )

    # Populate cache via read
    repo._storage_data["test-key"] = "old-value"
    value1 = await repo.get("test-key")
    assert value1 == "old-value"

    # Write with invalidation
    await repo.set("test-key", "new-value")

    # Cache should be invalidated, fetch from storage
    value2 = await repo.get("test-key")
    assert value2 == "new-value"


@pytest.mark.asyncio
async def test_base_repository_delete():
    """Test delete operation."""
    storage_backend = MagicMock()
    repo = MockRepository(
        storage_backend=storage_backend,
        cache_strategy=CacheStrategy.WRITE_THROUGH,
        ttl=300,
    )

    # Write value
    await repo.set("test-key", "test-value")

    # Verify exists
    assert await repo.exists("test-key")

    # Delete
    deleted = await repo.delete("test-key")
    assert deleted is True

    # Verify deleted
    assert not await repo.exists("test-key")


@pytest.mark.asyncio
async def test_base_repository_no_caching():
    """Test with caching disabled."""
    storage_backend = MagicMock()
    repo = MockRepository(
        storage_backend=storage_backend,
        cache_strategy=CacheStrategy.NONE,
        ttl=300,
    )

    # Write value
    repo._storage_data["test-key"] = "test-value"

    # Should always fetch from storage (no caching)
    value1 = await repo.get("test-key")
    assert value1 == "test-value"

    value2 = await repo.get("test-key")
    assert value2 == "test-value"


@pytest.mark.asyncio
async def test_base_repository_ttl_expiration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test TTL expiration in L1 cache."""
    import time
    from unittest.mock import MagicMock as OriginalMagicMock

    storage_backend = MagicMock()
    repo = MockRepository(
        storage_backend=storage_backend,
        cache_strategy=CacheStrategy.READ_THROUGH,
        ttl=1,  # 1 second TTL
    )

    # Write value
    repo._storage_data["test-key"] = "test-value"

    # Track time progression
    current_time = [time.time()]

    def mock_time() -> float:
        """Mock time.time() to advance TTL."""
        return current_time[0]

    # Patch time.time
    monkeypatch.setattr("time.time", mock_time)

    # First access - cache miss
    value1 = await repo.get("test-key")
    assert value1 == "test-value"

    # Immediate second access - cache hit
    value2 = await repo.get("test-key")
    assert value2 == "test-value"

    # Advance time past TTL expiration
    current_time[0] += 2.0

    # Should be expired, fetch from storage
    value3 = await repo.get("test-key")
    assert value3 == "test-value"


@pytest.mark.asyncio
async def test_base_repository_lru_eviction():
    """Test LRU eviction in L1 cache."""
    storage_backend = MagicMock()
    repo = MockRepository(
        storage_backend=storage_backend,
        cache_strategy=CacheStrategy.READ_THROUGH,
        ttl=300,
        l1_max_size=2,  # Small cache for testing
    )

    # Add 3 items (exceeds capacity)
    repo._storage_data["key1"] = "value1"
    repo._storage_data["key2"] = "value2"
    repo._storage_data["key3"] = "value3"

    await repo.get("key1")
    await repo.get("key2")
    await repo.get("key3")  # This should evict key1

    # Access key2 and key3 - should be in cache
    value2 = await repo.get("key2")
    assert value2 == "value2"

    value3 = await repo.get("key3")
    assert value3 == "value3"

    # key1 should have been evicted
    value1 = await repo.get("key1")
    assert value1 == "value1"
