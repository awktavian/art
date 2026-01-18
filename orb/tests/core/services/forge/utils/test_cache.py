"""Tests for forge utils cache module."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio

from kagami.forge.utils.cache import (
    CacheManager,
    MemoryCache,
    cache_llm_response,
    cache_visual_analysis,
    clear_llm_cache,
    clear_visual_cache,
)


class TestMemoryCache:
    """Tests for MemoryCache class."""

    def test_creation(self) -> None:
        """Test cache creation."""
        cache = MemoryCache(name="test", max_size=100, default_ttl=60)

        assert cache.name == "test"
        assert cache.max_size == 100
        assert cache.default_ttl == 60

    def test_set_and_get_sync(self) -> None:
        """Test synchronous set and get."""
        cache = MemoryCache(name="test")

        cache.set_sync("key1", "value1")
        result = cache.get_sync("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_set_and_get_async(self) -> None:
        """Test asynchronous set and get."""
        cache = MemoryCache(name="test")

        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

    def test_get_missing_key(self) -> None:
        """Test getting missing key returns default."""
        cache = MemoryCache(name="test")

        result = cache.get_sync("missing", default="fallback")

        assert result == "fallback"

    def test_lru_eviction(self) -> None:
        """Test LRU eviction when cache is full."""
        cache = MemoryCache(name="test", max_size=3)

        cache.set_sync("a", 1)
        cache.set_sync("b", 2)
        cache.set_sync("c", 3)
        cache.set_sync("d", 4)  # Should evict "a"

        assert cache.get_sync("a") is None
        assert cache.get_sync("b") == 2
        assert cache.get_sync("c") == 3
        assert cache.get_sync("d") == 4

    def test_ttl_expiration(self) -> None:
        """Test TTL expiration."""
        import time

        cache = MemoryCache(name="test", default_ttl=0.1)  # 100ms

        cache.set_sync("key", "value")
        assert cache.get_sync("key") == "value"

        time.sleep(0.15)  # Wait for expiration
        assert cache.get_sync("key") is None

    def test_zero_ttl_deletes_entry(self) -> None:
        """Test zero TTL deletes/prevents entry."""
        cache = MemoryCache(name="test")

        cache.set_sync("key", "value", ttl=0)
        assert cache.get_sync("key") is None

    def test_delete(self) -> None:
        """Test delete functionality."""
        cache = MemoryCache(name="test")

        cache.set_sync("key", "value")
        assert cache.delete_sync("key") is True
        assert cache.get_sync("key") is None
        assert cache.delete_sync("missing") is False

    def test_exists(self) -> None:
        """Test exists functionality."""
        cache = MemoryCache(name="test")

        cache.set_sync("key", "value")
        assert cache.exists_sync("key") is True
        assert cache.exists_sync("missing") is False

    def test_clear(self) -> None:
        """Test clear functionality."""
        cache = MemoryCache(name="test")

        cache.set_sync("a", 1)
        cache.set_sync("b", 2)
        cache.clear_sync()

        # After clear, cache should be empty
        # Note: get_sync will increment misses
        assert len(cache.cache) == 0
        assert cache.hits == 0

    def test_stats(self) -> None:
        """Test stats functionality."""
        cache = MemoryCache(name="test", max_size=10)

        cache.set_sync("a", 1)
        cache.get_sync("a")  # Hit
        cache.get_sync("b")  # Miss

        stats = cache.stats()

        assert stats["size"] == 1
        assert stats["max_size"] == 10
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_get_stats_memory(self) -> None:
        """Test get_stats includes memory info."""
        cache = MemoryCache(name="test")
        cache.set_sync("key", "value" * 100)

        stats = cache.get_stats()

        assert "memory_usage_mb" in stats
        assert stats["type"] == "memory"


class TestCacheManager:
    """Tests for CacheManager class."""

    def test_creation(self) -> None:
        """Test CacheManager creation."""
        manager = CacheManager()

        assert manager.default_ttl == 3600
        assert manager.default_max_size == 1000

    def test_get_cache(self) -> None:
        """Test getting named cache."""
        manager = CacheManager()

        cache1 = manager.get_cache("test1")
        cache2 = manager.get_cache("test1")
        cache3 = manager.get_cache("test2")

        assert cache1 is cache2
        assert cache1 is not cache3

    def test_get_set_value(self) -> None:
        """Test get_value and set_value."""
        manager = CacheManager()

        manager.set_value("cache1", "key", "value")
        result = manager.get_value("cache1", "key")

        assert result == "value"

    @pytest.mark.asyncio
    async def test_async_get_set(self) -> None:
        """Test async get and set."""
        manager = CacheManager()

        await manager.set("key", "value")
        result = await manager.get("key")

        assert result == "value"

    def test_clear_specific_cache(self) -> None:
        """Test clearing specific cache."""
        manager = CacheManager()

        manager.set_value("cache1", "key", "value1")
        manager.set_value("cache2", "key", "value2")

        manager.clear("cache1")

        assert manager.get_value("cache1", "key") is None
        assert manager.get_value("cache2", "key") == "value2"

    def test_clear_all_caches(self) -> None:
        """Test clearing all caches."""
        manager = CacheManager()

        manager.set_value("cache1", "key", "value1")
        manager.set_value("cache2", "key", "value2")

        manager.clear()

        assert manager.get_value("cache1", "key") is None
        assert manager.get_value("cache2", "key") is None

    def test_stats_all_caches(self) -> None:
        """Test stats for all caches."""
        manager = CacheManager()

        manager.set_value("cache1", "key", "value")
        manager.set_value("cache2", "key", "value")

        stats = manager.stats()

        assert isinstance(stats, dict)
        assert "cache1" in stats
        assert "cache2" in stats


class TestCacheDecorators:
    """Tests for cache decorators."""

    @pytest.mark.asyncio
    async def test_cache_llm_response_decorator(self) -> None:
        """Test cache_llm_response decorator."""
        call_count = 0

        @cache_llm_response
        async def mock_llm(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"response to {prompt}"

        # First call should execute
        result1 = await mock_llm("hello")
        assert result1 == "response to hello"
        assert call_count == 1

        # Second call should use cache
        result2 = await mock_llm("hello")
        assert result2 == "response to hello"
        assert call_count == 1  # Not incremented

        # Different args should execute again
        result3 = await mock_llm("world")
        assert result3 == "response to world"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cache_visual_analysis_decorator(self) -> None:
        """Test cache_visual_analysis decorator."""
        call_count = 0

        @cache_visual_analysis
        async def mock_analysis(image_path: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"path": image_path}

        result1 = await mock_analysis("/path/to/image.png")
        result2 = await mock_analysis("/path/to/image.png")

        assert result1 == result2
        assert call_count == 1  # Only called once

    def test_clear_llm_cache(self) -> None:
        """Test clear_llm_cache function."""
        # Should not raise
        clear_llm_cache()

    def test_clear_visual_cache(self) -> None:
        """Test clear_visual_cache function."""
        # Should not raise
        clear_visual_cache()
