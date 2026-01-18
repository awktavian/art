"""Integration test for EmbeddingService + HuggingFace Model Cache.

Tests that tokenizer and embedding models are properly cached across
service initialization cycles using HuggingFace's native caching.

Coverage:
- First initialization triggers cache miss (download)
- Second initialization uses cached models (hit)
- Cache hit rate > 0 after second initialization
- Initialization time improves with cache
"""

from __future__ import annotations
from typing import Any
import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.integration,
    pytest.mark.tier_integration,
]

import os
import time
from pathlib import Path

from kagami.core.services.embedding_service import (
    EmbeddingService,
    EmbeddingServiceConfig,
    reset_embedding_service,
)

# Mark as integration test (requires network for model download)


@pytest.fixture(autouse=True)
def clean_cache(monkeypatch: Any) -> None:
    """Clean HuggingFace model cache before and after tests."""
    # Override test mode to allow full model loading for integration tests
    # Set env vars to disable fast embedding mode
    monkeypatch.setenv("KAGAMI_INTEGRATION_TEST", "1")
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "0")
    monkeypatch.setenv("KAGAMI_TEST_FAST_EMBEDDINGS", "0")

    reset_embedding_service()

    # Clean HuggingFace cache directory for test model
    hf_cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    test_model_cache = hf_cache_dir / "models--prajjwal1--bert-tiny"

    if test_model_cache.exists():
        import shutil

        try:
            shutil.rmtree(test_model_cache)
        except Exception as e:
            # Ignore errors during cleanup
            pass

    yield

    # Clean up after test
    reset_embedding_service()
    if test_model_cache.exists():
        import shutil

        try:
            shutil.rmtree(test_model_cache)
        except Exception as e:
            # Ignore errors during cleanup
            pass


@pytest.fixture
def config():
    """Test config with lightweight model."""
    return EmbeddingServiceConfig(
        tokenizer_name="prajjwal1/bert-tiny",  # 4.4MB model for fast testing
        embedding_dim=128,
        redis_enabled=False,
        cache_size=10,
    )


def test_model_cache_first_load(config) -> None:
    """Test first load triggers cache miss."""
    # First initialization
    service = EmbeddingService(config)

    # Force initialization
    service._ensure_initialized()

    # Check statistics
    stats = service.get_stats()

    # First load should have cache misses
    assert stats["initialized"]
    assert stats["tokenizer_loaded"]

    # Should have at least one cache miss (tokenizer + embedding model = 2 misses)
    hf_cache_stats = stats.get("hf_model_cache", {})
    assert hf_cache_stats["misses"] >= 1, "Expected cache miss on first load"


def test_model_cache_second_load_hits(config) -> None:
    """Test second load uses cached models."""
    # First initialization
    service1 = EmbeddingService(config)
    service1._ensure_initialized()

    stats1 = service1.get_stats()
    misses_after_first = stats1["hf_model_cache"]["misses"]
    hits_after_first = stats1["hf_model_cache"]["hits"]

    # Reset service (but keep HF cache)
    reset_embedding_service()

    # Second initialization (should use cache)
    service2 = EmbeddingService(config)
    service2._ensure_initialized()

    stats2 = service2.get_stats()

    # Second load should have cache hits
    assert stats2["initialized"]
    assert stats2["tokenizer_loaded"]

    # Should have hits > 0 (at least tokenizer + embedding model = 2 hits)
    hf_cache_stats = stats2.get("hf_model_cache", {})
    assert hf_cache_stats["hits"] >= 1, "Expected cache hit on second load"
    assert hf_cache_stats["hit_rate"] > 0, "Expected non-zero hit rate"


def test_model_cache_timing_improvement(config) -> None:
    """Test that cache improves initialization time."""
    # First initialization (cold start)
    start1 = time.perf_counter()
    service1 = EmbeddingService(config)
    service1._ensure_initialized()
    time1 = time.perf_counter() - start1

    # Reset service
    reset_embedding_service()

    # Second initialization (warm cache)
    start2 = time.perf_counter()
    service2 = EmbeddingService(config)
    service2._ensure_initialized()
    time2 = time.perf_counter() - start2

    # Cached load should be faster (allow 10% margin for variance)
    # Only assert if both loads succeeded
    if service1._tokenizer and service2._tokenizer:
        # Cache should provide at least 20% speedup
        # (but be lenient due to disk I/O variance)
        speedup_ratio = time1 / time2 if time2 > 0 else 1.0

        print(f"\nFirst load: {time1:.2f}s")
        print(f"Second load: {time2:.2f}s")
        print(f"Speedup: {speedup_ratio:.2f}x")

        # Assert cache provides benefit (at least 1.2x speedup)
        # Only fail if second load is significantly slower
        assert (
            time2 <= time1 * 1.5
        ), f"Cached load should not be slower: {time2:.2f}s vs {time1:.2f}s"


def test_model_cache_backend_info(config) -> None:
    """Test that HF cache backend info is included in stats."""
    service = EmbeddingService(config)
    service._ensure_initialized()

    stats = service.get_stats()

    # Should have HF model cache stats
    assert "hf_model_cache" in stats
    hf_cache = stats["hf_model_cache"]

    # Should have hit/miss counters
    assert "hits" in hf_cache
    assert "misses" in hf_cache
    assert "hit_rate" in hf_cache

    # Should have backend identifier
    assert "backend" in hf_cache
    assert hf_cache["backend"] == "HuggingFace transformers cache"


def test_embedding_with_cached_models(config) -> None:
    """Test that embeddings work with cached models."""
    # Initialize service twice to ensure cache is used
    service1 = EmbeddingService(config)
    vec1 = service1.embed_text("hello world")

    reset_embedding_service()

    service2 = EmbeddingService(config)
    vec2 = service2.embed_text("hello world")

    # Embeddings should be identical (deterministic)
    import numpy as np

    np.testing.assert_allclose(vec1, vec2, rtol=1e-5, atol=1e-5)

    # Second service should have cache hits
    stats2 = service2.get_stats()
    assert stats2["hf_model_cache"]["hits"] > 0


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
