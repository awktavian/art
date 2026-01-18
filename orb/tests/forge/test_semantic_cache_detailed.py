"""Tests for kagami.forge.semantic_cache (SemanticCache)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from kagami.forge.semantic_cache import SemanticCache, CachedResult, get_semantic_cache

pytestmark = pytest.mark.tier_unit


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    service = MagicMock()
    service.embed_text = MagicMock(
        return_value=[0.1, 0.2, 0.3, 0.4]  # Mock embedding
    )
    return service


@pytest.fixture
def semantic_cache(mock_embedding_service):
    """Create SemanticCache with mocked embedding service."""
    cache = SemanticCache(similarity_threshold=0.92)
    cache.encoder = mock_embedding_service
    return cache


class TestCachedResult:
    """Test CachedResult dataclass."""

    def test_cached_result_creation(self):
        """Test creating a CachedResult."""
        result = CachedResult(
            concept="warrior",
            embedding=[0.1, 0.2, 0.3],
            result={"character": "data"},
            timestamp=time.time(),
            hit_count=0,
        )

        assert result.concept == "warrior"
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.result == {"character": "data"}
        assert result.hit_count == 0

    def test_cached_result_increment_hits(self):
        """Test incrementing hit count."""
        result = CachedResult(
            concept="warrior",
            embedding=[0.1, 0.2, 0.3],
            result={},
            timestamp=time.time(),
        )

        assert result.hit_count == 0
        result.hit_count += 1
        assert result.hit_count == 1


class TestSemanticCacheInitialization:
    """Test SemanticCache initialization."""

    def test_init_default_threshold(self):
        """Test default similarity threshold."""
        cache = SemanticCache()
        assert cache.similarity_threshold == 0.92

    def test_init_custom_threshold(self):
        """Test custom similarity threshold."""
        cache = SemanticCache(similarity_threshold=0.85)
        assert cache.similarity_threshold == 0.85

    def test_init_stats(self):
        """Test initial statistics."""
        cache = SemanticCache()
        assert cache.hits == 0
        assert cache.misses == 0
        assert len(cache.cache) == 0

    def test_init_embedding_service(self):
        """Test embedding service initialization."""
        with patch("kagami.core.services.embedding_service.get_embedding_service") as mock:
            mock.return_value = MagicMock()
            cache = SemanticCache()
            assert cache.encoder is not None


class TestCacheMiss:
    """Test cache miss scenarios."""

    @pytest.mark.asyncio
    async def test_cache_miss_empty_cache(self, semantic_cache):
        """Test cache miss with empty cache."""
        async def generator(prompt):
            return {"character": "generated"}

        result, cached = await semantic_cache.get_or_generate(
            "warrior",
            generator
        )

        assert cached is False
        assert result == {"character": "generated"}
        assert semantic_cache.misses == 1
        assert semantic_cache.hits == 0

    @pytest.mark.asyncio
    async def test_cache_miss_no_similar_entry(self, semantic_cache):
        """Test cache miss when no similar entry exists."""
        # Pre-populate cache with dissimilar entry
        semantic_cache.cache["key1"] = CachedResult(
            concept="mage",
            embedding=[0.9, 0.1, 0.0, 0.0],  # Very different
            result={"character": "mage"},
            timestamp=time.time(),
        )

        async def generator(prompt):
            return {"character": "warrior"}

        with patch("numpy.dot") as mock_dot, \
             patch("numpy.linalg.norm") as mock_norm:
            mock_dot.return_value = 0.1  # Low similarity
            mock_norm.return_value = 1.0

            result, cached = await semantic_cache.get_or_generate(
                "warrior",
                generator
            )

            assert cached is False
            assert semantic_cache.misses == 1

    @pytest.mark.asyncio
    async def test_cache_miss_no_encoder(self):
        """Test cache miss when encoder is not available."""
        cache = SemanticCache()
        cache.encoder = None

        async def generator(prompt):
            return {"character": "generated"}

        result, cached = await cache.get_or_generate("warrior", generator)

        assert cached is False
        assert result == {"character": "generated"}
        assert cache.misses == 1


class TestCacheHit:
    """Test cache hit scenarios."""

    @pytest.mark.asyncio
    async def test_cache_hit_exact_match(self, semantic_cache):
        """Test cache hit with high similarity."""
        # Pre-populate cache
        semantic_cache.cache["key1"] = CachedResult(
            concept="warrior",
            embedding=[0.1, 0.2, 0.3, 0.4],
            result={"character": "cached_warrior"},
            timestamp=time.time(),
        )

        async def generator(prompt):
            return {"character": "generated"}

        with patch("numpy.dot") as mock_dot, \
             patch("numpy.linalg.norm") as mock_norm:
            mock_dot.return_value = 0.95
            mock_norm.return_value = 1.0

            result, cached = await semantic_cache.get_or_generate(
                "warrior character",
                generator
            )

            assert cached is True
            assert result == {"character": "cached_warrior"}
            assert semantic_cache.hits == 1
            assert semantic_cache.misses == 0

    @pytest.mark.asyncio
    async def test_cache_hit_increments_hit_count(self, semantic_cache):
        """Test that cache hits increment the hit count."""
        cached_result = CachedResult(
            concept="warrior",
            embedding=[0.1, 0.2, 0.3, 0.4],
            result={"character": "cached"},
            timestamp=time.time(),
            hit_count=0,
        )
        semantic_cache.cache["key1"] = cached_result

        async def generator(prompt):
            return {"character": "generated"}

        with patch("numpy.dot") as mock_dot, \
             patch("numpy.linalg.norm") as mock_norm:
            mock_dot.return_value = 0.95
            mock_norm.return_value = 1.0

            await semantic_cache.get_or_generate("warrior", generator)

            assert cached_result.hit_count == 1

    @pytest.mark.asyncio
    async def test_cache_hit_multiple_entries(self, semantic_cache):
        """Test finding best match among multiple entries."""
        # Add multiple entries with different similarities
        semantic_cache.cache["key1"] = CachedResult(
            concept="mage",
            embedding=[0.9, 0.1, 0.0, 0.0],
            result={"character": "mage"},
            timestamp=time.time(),
        )
        semantic_cache.cache["key2"] = CachedResult(
            concept="warrior",
            embedding=[0.1, 0.2, 0.3, 0.4],
            result={"character": "warrior"},
            timestamp=time.time(),
        )
        semantic_cache.cache["key3"] = CachedResult(
            concept="rogue",
            embedding=[0.5, 0.5, 0.0, 0.0],
            result={"character": "rogue"},
            timestamp=time.time(),
        )

        async def generator(prompt):
            return {"character": "generated"}

        with patch("numpy.dot") as mock_dot, \
             patch("numpy.linalg.norm") as mock_norm:
            # Simulate different similarities
            mock_dot.side_effect = [0.5, 0.96, 0.7]  # Best match is key2
            mock_norm.return_value = 1.0

            result, cached = await semantic_cache.get_or_generate(
                "warrior knight",
                generator
            )

            assert cached is True
            assert result == {"character": "warrior"}


class TestCacheStorage:
    """Test cache storage and retrieval."""

    @pytest.mark.asyncio
    async def test_stores_result_after_generation(self, semantic_cache):
        """Test that generated results are stored in cache."""
        async def generator(prompt):
            return {"character": "newly_generated"}

        result, cached = await semantic_cache.get_or_generate(
            "warrior",
            generator
        )

        assert cached is False
        assert len(semantic_cache.cache) == 1

        # Verify stored entry
        stored = list(semantic_cache.cache.values())[0]
        assert stored.concept == "warrior"
        assert stored.result == {"character": "newly_generated"}

    @pytest.mark.asyncio
    async def test_generator_not_called_on_hit(self, semantic_cache):
        """Test that generator is not called on cache hit."""
        # Pre-populate cache
        semantic_cache.cache["key1"] = CachedResult(
            concept="warrior",
            embedding=[0.1, 0.2, 0.3, 0.4],
            result={"character": "cached"},
            timestamp=time.time(),
        )

        generator_called = False

        async def generator(prompt):
            nonlocal generator_called
            generator_called = True
            return {"character": "generated"}

        with patch("numpy.dot") as mock_dot, \
             patch("numpy.linalg.norm") as mock_norm:
            mock_dot.return_value = 0.95
            mock_norm.return_value = 1.0

            await semantic_cache.get_or_generate("warrior", generator)

            assert generator_called is False


class TestSimilarityThreshold:
    """Test similarity threshold behavior."""

    @pytest.mark.asyncio
    async def test_below_threshold_is_miss(self, semantic_cache):
        """Test that similarity below threshold is a miss."""
        semantic_cache.similarity_threshold = 0.92

        semantic_cache.cache["key1"] = CachedResult(
            concept="warrior",
            embedding=[0.1, 0.2, 0.3, 0.4],
            result={"character": "cached"},
            timestamp=time.time(),
        )

        async def generator(prompt):
            return {"character": "generated"}

        with patch("numpy.dot") as mock_dot, \
             patch("numpy.linalg.norm") as mock_norm:
            mock_dot.return_value = 0.90  # Below threshold
            mock_norm.return_value = 1.0

            result, cached = await semantic_cache.get_or_generate(
                "warrior knight",
                generator
            )

            assert cached is False
            assert result == {"character": "generated"}

    @pytest.mark.asyncio
    async def test_at_threshold_is_hit(self, semantic_cache):
        """Test that similarity at threshold is a hit."""
        semantic_cache.similarity_threshold = 0.92

        semantic_cache.cache["key1"] = CachedResult(
            concept="warrior",
            embedding=[0.1, 0.2, 0.3, 0.4],
            result={"character": "cached"},
            timestamp=time.time(),
        )

        async def generator(prompt):
            return {"character": "generated"}

        with patch("numpy.dot") as mock_dot, \
             patch("numpy.linalg.norm") as mock_norm:
            mock_dot.return_value = 0.92  # At threshold
            mock_norm.return_value = 1.0

            result, cached = await semantic_cache.get_or_generate(
                "warrior",
                generator
            )

            assert cached is True


class TestStatistics:
    """Test cache statistics."""

    def test_get_stats_empty(self):
        """Test statistics for empty cache."""
        cache = SemanticCache()
        cache.encoder = MagicMock()

        stats = cache.get_stats()

        assert stats["enabled"] is True
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["cache_size"] == 0

    def test_get_stats_with_hits(self, semantic_cache):
        """Test statistics with hits and misses."""
        semantic_cache.hits = 7
        semantic_cache.misses = 3

        stats = semantic_cache.get_stats()

        assert stats["hits"] == 7
        assert stats["misses"] == 3
        assert stats["hit_rate"] == 0.7

    def test_get_stats_no_encoder(self):
        """Test statistics when encoder unavailable."""
        cache = SemanticCache()
        cache.encoder = None

        stats = cache.get_stats()

        assert stats["enabled"] is False


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_embedding_error_is_miss(self, semantic_cache):
        """Test that embedding errors result in cache miss."""
        semantic_cache.encoder.embed_text.side_effect = RuntimeError("Embedding failed")

        async def generator(prompt):
            return {"character": "generated"}

        result, cached = await semantic_cache.get_or_generate("warrior", generator)

        assert cached is False
        assert result == {"character": "generated"}
        assert semantic_cache.misses == 1

    @pytest.mark.asyncio
    async def test_similarity_computation_error(self, semantic_cache):
        """Test handling of similarity computation errors."""
        semantic_cache.cache["key1"] = CachedResult(
            concept="warrior",
            embedding=[0.1, 0.2],
            result={"character": "cached"},
            timestamp=time.time(),
        )

        async def generator(prompt):
            return {"character": "generated"}

        # Simulate error in similarity computation
        with patch("numpy.dot") as mock_dot:
            mock_dot.side_effect = RuntimeError("Computation failed")

            result, cached = await semantic_cache.get_or_generate(
                "warrior",
                generator
            )

            # Should fall back to generation
            assert cached is False


class TestSingletonAccess:
    """Test singleton access pattern."""

    def test_get_semantic_cache(self):
        """Test get_semantic_cache singleton."""
        cache1 = get_semantic_cache()
        cache2 = get_semantic_cache()

        assert cache1 is cache2
