"""Comprehensive tests for forge semantic cache module.

Tests SemanticCache class and caching functionality.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.semantic_cache import (
    AVAILABLE,
    CachedResult,
    SemanticCache,
    get_semantic_cache,
)


class TestCachedResult:
    """Test CachedResult dataclass."""

    def test_creation(self) -> None:
        """Test creating a cached result."""
        import time

        result = CachedResult(
            concept="A brave warrior",
            embedding=[0.1, 0.2, 0.3],
            result={"character": "generated"},
            timestamp=time.time(),
        )

        assert result.concept == "A brave warrior"
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.result == {"character": "generated"}
        assert result.hit_count == 0

    def test_hit_count_increment(self) -> None:
        """Test that hit count can be incremented."""
        import time

        result = CachedResult(
            concept="test",
            embedding=None,
            result={},
            timestamp=time.time(),
        )

        assert result.hit_count == 0
        result.hit_count += 1
        assert result.hit_count == 1


class TestSemanticCache:
    """Test SemanticCache class."""

    @pytest.fixture
    def cache(self):
        """Create a semantic cache instance."""
        return SemanticCache(similarity_threshold=0.9)

    @pytest.mark.asyncio
    async def test_get_or_generate_miss(self, cache: Any, monkeypatch: Any) -> None:
        """Test cache miss calls generator."""
        call_count = 0

        async def generator(prompt: Any, **kwargs) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"generated": True, "prompt": prompt}

        # Disable encoder to force miss
        monkeypatch.setattr(cache, "encoder", None)

        result, is_cached = await cache.get_or_generate("test prompt", generator)

        assert result["generated"] is True
        assert result["prompt"] == "test prompt"
        assert is_cached is False
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_get_or_generate_no_encoder(self, cache: Any, monkeypatch: Any) -> Any:
        """Test behavior when encoder is unavailable."""
        monkeypatch.setattr(cache, "encoder", None)

        async def generator(prompt: Any, **kwargs) -> Dict[str, Any]:
            return {"result": prompt}

        result, is_cached = await cache.get_or_generate("test", generator)

        assert result == {"result": "test"}
        assert is_cached is False
        assert cache.misses == 1

    @pytest.mark.asyncio
    async def test_get_or_generate_encoder_error(self, cache: Any, monkeypatch: Any) -> Any:
        """Test behavior when encoder raises error."""

        class MockEncoder:
            def embed_text(self, text: Any) -> None:
                raise Exception("Embedding failed")

        monkeypatch.setattr(cache, "encoder", MockEncoder())

        async def generator(prompt: Any, **kwargs) -> Dict[str, Any]:
            return {"result": prompt}

        result, is_cached = await cache.get_or_generate("test", generator)

        assert result == {"result": "test"}
        assert is_cached is False
        assert cache.misses == 1

    def test_get_stats_empty(self, cache: Any, monkeypatch: Any) -> Any:
        """Test stats when cache is empty."""
        monkeypatch.setattr(cache, "encoder", None)

        stats = cache.get_stats()

        assert stats["enabled"] is False
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["cache_size"] == 0

    def test_get_stats_with_activity(self, cache: Any) -> None:
        """Test stats after cache activity."""
        cache.hits = 3
        cache.misses = 7
        cache.cache = {"key1": None, "key2": None}

        stats = cache.get_stats()

        assert stats["hits"] == 3
        assert stats["misses"] == 7
        assert stats["hit_rate"] == 0.3
        assert stats["cache_size"] == 2


class TestGetSemanticCache:
    """Test get_semantic_cache singleton."""

    def test_get_semantic_cache_singleton(self) -> None:
        """Test that get_semantic_cache returns singleton."""
        c1 = get_semantic_cache()
        c2 = get_semantic_cache()
        assert c1 is c2

    def test_get_semantic_cache_type(self) -> None:
        """Test that get_semantic_cache returns SemanticCache."""
        c = get_semantic_cache()
        assert isinstance(c, SemanticCache)


class TestAVAILABLE:
    """Test AVAILABLE constant."""

    def test_available_is_bool(self) -> None:
        """Test AVAILABLE is a boolean."""
        assert isinstance(AVAILABLE, bool)
