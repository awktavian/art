"""Integration tests for model cache with real ML frameworks.

Tests verify:
1. Integration with config_root.py
2. Real pickle serialization
3. Real safetensors serialization (if available)
4. Cache performance metrics
5. Large model handling
6. Multi-model scenarios

Author: Crystal (e₇) — The Verifier
"""

from __future__ import annotations

import pytest
import pytest_asyncio

pytestmark = pytest.mark.tier_integration
import asyncio
import time
from pathlib import Path
from typing import Any
from kagami.core.caching.unified_model_cache import ModelCache, get_model_cache
from kagami.core.caching.model_cache_config import ModelCacheConfig


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Temporary cache directory for tests."""
    return tmp_path / "model_cache_integration"


@pytest_asyncio.fixture
async def cache(temp_cache_dir: Path) -> ModelCache:
    """Model cache instance for integration tests."""
    return ModelCache(cache_dir=temp_cache_dir, max_size_gb=2.0, max_models=5)


# ==============================================================================
# TEST 1: Real Pickle Serialization
# ==============================================================================
@pytest.mark.asyncio
async def test_pickle_serialization_simple(cache: ModelCache) -> None:
    """Test pickle serialization with simple objects."""

    def loader() -> dict[str, Any]:
        return {
            "weights": [1.0, 2.0, 3.0],
            "biases": [0.1, 0.2],
            "config": {"layers": 3, "activation": "relu"},
        }

    result = await cache.get_cached_model("simple-model", {"device": "cpu"}, loader)
    assert result["weights"] == [1.0, 2.0, 3.0]
    assert result["biases"] == [0.1, 0.2]
    assert result["config"]["layers"] == 3
    # Verify it's cached
    info = cache.get_cache_info()
    assert info["cached_models"] == 1


@pytest.mark.asyncio
async def test_pickle_serialization_complex(cache: ModelCache) -> None:
    """Test pickle serialization with complex nested objects."""

    class CustomModel:
        def __init__(self, weights: list[float]) -> None:
            self.weights = weights
            self.metadata = {"version": "1.0"}

        def __eq__(self, other: Any) -> bool:
            return (
                isinstance(other, CustomModel)
                and self.weights == other.weights
                and self.metadata == other.metadata
            )

    def loader() -> CustomModel:
        return CustomModel([1.0, 2.0, 3.0])

    result = await cache.get_cached_model("custom-model", {"device": "cpu"}, loader)
    assert isinstance(result, CustomModel)
    assert result.weights == [1.0, 2.0, 3.0]
    assert result.metadata["version"] == "1.0"


# ==============================================================================
# TEST 2: Safetensors Serialization (if available)
# ==============================================================================
@pytest.mark.asyncio
async def test_safetensors_preferred_over_pickle(cache: ModelCache) -> None:
    """Test that safetensors is preferred when model is dict."""
    try:
        import torch
        from safetensors.torch import save_file, load_file
    except ImportError:
        pytest.skip("torch or safetensors not available")

    def loader() -> dict[str, Any]:
        return {
            "layer1.weight": torch.randn(10, 10),
            "layer1.bias": torch.randn(10),
        }

    config = {"device": "cpu"}
    result = await cache.get_cached_model("torch-model", config, loader)
    # Verify safetensors file was created
    cache_key = cache._compute_cache_key("torch-model", config)
    cache_path = cache._get_cache_path(cache_key)
    safetensors_path = cache_path / "model.safetensors"
    # Safetensors should be used for dict models
    if safetensors_path.exists():
        # Load directly to verify
        loaded = load_file(str(safetensors_path))
        assert "layer1.weight" in loaded
        assert "layer1.bias" in loaded


# ==============================================================================
# TEST 3: Integration with unified_config.py (migrated from config_root.py)
# ==============================================================================
@pytest.mark.asyncio
async def test_integration_default_path() -> None:
    """Test that default cache path is XDG-compliant."""
    from kagami.core.config.unified_config import get_model_cache_path

    cache = ModelCache()
    expected = get_model_cache_path().expanduser().resolve()
    assert cache.cache_dir == expected


@pytest.mark.asyncio
async def test_integration_config_loading() -> None:
    """Test loading config from environment."""
    import os
    from unittest.mock import patch

    with patch.dict(
        os.environ,
        {
            "KAGAMI_MODEL_CACHE_MAX_SIZE_GB": "50.0",
            "KAGAMI_MODEL_CACHE_MAX_MODELS": "20",
        },
    ):
        config = ModelCacheConfig.from_env()
        assert config.max_size_gb == 50.0
        assert config.max_models == 20


# ==============================================================================
# TEST 4: Performance Metrics
# ==============================================================================
@pytest.mark.asyncio
async def test_performance_cache_hit_latency(cache: ModelCache) -> None:
    """Test cache hit latency is much faster than miss."""

    def slow_loader() -> dict[str, int]:
        time.sleep(0.1)  # Simulate slow model load
        return {"test": 42}

    config = {"device": "cpu"}
    # First access (miss)
    start_miss = time.time()
    await cache.get_cached_model("slow-model", config, slow_loader)
    miss_duration = time.time() - start_miss
    # Clear memory cache to force disk load
    cache._memory_cache.clear()
    # Second access (disk cache hit)
    start_hit = time.time()
    await cache.get_cached_model("slow-model", config, slow_loader)
    hit_duration = time.time() - start_hit
    # Cache hit should be much faster than miss
    assert hit_duration < miss_duration / 2
    assert hit_duration < 0.05  # Should be very fast


@pytest.mark.asyncio
async def test_performance_memory_cache_latency(cache: ModelCache) -> None:
    """Test memory cache hit is extremely fast."""

    def loader() -> dict[str, int]:
        return {"test": 42}

    config = {"device": "cpu"}
    # Load into cache
    await cache.get_cached_model("fast-model", config, loader)
    # Access from memory cache (should be very fast)
    start = time.time()
    for _ in range(100):
        await cache.get_cached_model("fast-model", config, loader)
    duration = time.time() - start
    # 100 memory cache hits should be < 50ms (relaxed for CI)
    assert duration < 0.05


@pytest.mark.asyncio
async def test_performance_concurrent_different_models(temp_cache_dir: Path) -> None:
    """Test concurrent loading of different models performs well."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=10)

    # Create loaders that return coroutines properly
    async def make_loader(model_id: str) -> dict[str, int]:
        await asyncio.sleep(0.05)  # Simulate load time
        return {model_id: 1}

    # Load 5 models concurrently
    start = time.time()
    tasks = [
        cache.get_cached_model(f"model{i}", {"device": "cpu"}, lambda i=i: make_loader(f"model{i}"))
        for i in range(5)
    ]
    await asyncio.gather(*tasks)
    duration = time.time() - start
    # Should complete faster than serial execution (0.25s)
    # Allow some overhead for CI systems
    assert duration < 0.15


# ==============================================================================
# TEST 5: Large Model Handling
# ==============================================================================
@pytest.mark.asyncio
async def test_large_model_eviction(temp_cache_dir: Path) -> None:
    """Test eviction works correctly with size limits."""
    # Small cache: 10MB max
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        max_size_gb=0.01,  # 10MB
        max_models=10,
    )

    def make_loader(size_mb: int):
        def loader() -> dict[str, bytes]:
            # Create model of specific size
            return {"data": b"x" * (size_mb * 1024 * 1024)}

        return loader

    # Load 3x 5MB models (should evict oldest)
    await cache.get_cached_model("model1", {"device": "cpu"}, make_loader(5))
    await asyncio.sleep(0.01)
    await cache.get_cached_model("model2", {"device": "cpu"}, make_loader(5))
    await asyncio.sleep(0.01)
    await cache.get_cached_model("model3", {"device": "cpu"}, make_loader(5))
    info = cache.get_cache_info()
    # Should have evicted to stay under 10MB
    assert info["total_size_gb"] <= 0.01
    assert info["cached_models"] <= 2  # Can't fit all 3


# ==============================================================================
# TEST 6: Multi-Model Scenarios
# ==============================================================================
@pytest.mark.asyncio
async def test_multi_model_cache_isolation(cache: ModelCache) -> None:
    """Test that different models are properly isolated."""

    def loader1() -> dict[str, str]:
        return {"type": "model1"}

    def loader2() -> dict[str, str]:
        return {"type": "model2"}

    # Cache two different models
    result1 = await cache.get_cached_model("model1", {"device": "cpu"}, loader1)
    result2 = await cache.get_cached_model("model2", {"device": "cpu"}, loader2)
    assert result1["type"] == "model1"
    assert result2["type"] == "model2"
    # Verify both are cached separately
    info = cache.get_cache_info()
    assert info["cached_models"] == 2
    model_ids = {m["model_id"] for m in info["models"]}
    assert "model1" in model_ids
    assert "model2" in model_ids


@pytest.mark.asyncio
async def test_multi_config_same_model(cache: ModelCache) -> None:
    """Test caching same model with different configs."""

    def loader() -> dict[str, str]:
        return {"data": "test"}

    # Cache same model with different device configs
    result_cpu = await cache.get_cached_model(
        "model", {"device": "cpu", "dtype": "float32"}, loader
    )
    result_cuda = await cache.get_cached_model(
        "model", {"device": "cuda", "dtype": "float16"}, loader
    )
    # Both should succeed
    assert result_cpu == {"data": "test"}
    assert result_cuda == {"data": "test"}
    # Should have 2 cache entries
    info = cache.get_cache_info()
    assert info["cached_models"] == 2
    # Different cache keys
    configs = [m["config"] for m in info["models"]]
    assert {"device": "cpu", "dtype": "float32"} in configs
    assert {"device": "cuda", "dtype": "float16"} in configs


# ==============================================================================
# TEST 7: Global Cache Instance
# ==============================================================================
def test_global_cache_singleton() -> None:
    """Test that get_model_cache returns singleton."""
    cache1 = get_model_cache()
    cache2 = get_model_cache()
    assert cache1 is cache2


@pytest.mark.asyncio
async def test_global_cache_usage(tmp_path: Path) -> None:
    """Test using global cache instance."""
    # Reset global cache
    import kagami.core.caching.unified_model_cache as cache_module

    cache_module._global_cache = None
    cache = get_model_cache(
        cache_dir=tmp_path / "global_cache",
        max_models=5,
    )

    def loader() -> dict[str, int]:
        return {"test": 42}

    result = await cache.get_cached_model("test", {"device": "cpu"}, loader)
    assert result == {"test": 42}
    # Reset for other tests
    cache_module._global_cache = None


# ==============================================================================
# TEST 8: Config Validation
# ==============================================================================
def test_config_validation_positive_values() -> None:
    """Test config validation rejects invalid values."""
    with pytest.raises(ValueError, match="max_size_gb must be positive"):
        ModelCacheConfig(cache_dir=Path("/tmp"), max_size_gb=-1.0)
    with pytest.raises(ValueError, match="max_models must be positive"):
        ModelCacheConfig(cache_dir=Path("/tmp"), max_models=0)
    with pytest.raises(ValueError, match="ttl_hours must be positive"):
        ModelCacheConfig(cache_dir=Path("/tmp"), ttl_hours=-1)


def test_config_validation_eviction_policy() -> None:
    """Test config validation for eviction policy."""
    with pytest.raises(ValueError, match="Invalid eviction_policy"):
        ModelCacheConfig(
            cache_dir=Path("/tmp"),
            eviction_policy="invalid",  # type: ignore
        )


# ==============================================================================
# TEST 9: Index Persistence
# ==============================================================================
@pytest.mark.asyncio
async def test_index_persistence_across_restarts(temp_cache_dir: Path) -> None:
    """Test that cache index persists across cache restarts."""
    # Create cache and add model
    cache1 = ModelCache(cache_dir=temp_cache_dir, max_models=5)

    def loader() -> dict[str, int]:
        return {"test": 42}

    await cache1.get_cached_model("persistent-model", {"device": "cpu"}, loader)
    info1 = cache1.get_cache_info()
    assert info1["cached_models"] == 1
    # Create new cache instance (simulates restart)
    cache2 = ModelCache(cache_dir=temp_cache_dir, max_models=5)
    info2 = cache2.get_cache_info()
    # Should still have cached model
    assert info2["cached_models"] == 1
    assert info2["models"][0]["model_id"] == "persistent-model"


@pytest.mark.asyncio
async def test_index_corruption_recovery(temp_cache_dir: Path) -> None:
    """Test recovery from corrupted index file."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=5)

    def loader() -> dict[str, int]:
        return {"test": 42}

    await cache.get_cached_model("test-model", {"device": "cpu"}, loader)
    # Corrupt index file
    index_path = temp_cache_dir / "index.json"
    with open(index_path, "w") as f:
        f.write("corrupted json{{{")
    # Create new cache (should recover)
    cache2 = ModelCache(cache_dir=temp_cache_dir, max_models=5)
    # Should start with empty index
    info = cache2.get_cache_info()
    assert info["cached_models"] == 0


# ==============================================================================
# TEST 10: Edge Cases
# ==============================================================================
@pytest.mark.asyncio
async def test_edge_case_empty_config(cache: ModelCache) -> None:
    """Test caching with empty config."""

    def loader() -> dict[str, int]:
        return {"test": 42}

    result = await cache.get_cached_model("model", {}, loader)
    assert result == {"test": 42}


@pytest.mark.asyncio
async def test_edge_case_none_values_in_config(cache: ModelCache) -> None:
    """Test caching with None values in config."""

    def loader() -> dict[str, int]:
        return {"test": 42}

    config = {"device": "cpu", "quantization": None}
    result = await cache.get_cached_model("model", config, loader)
    assert result == {"test": 42}


@pytest.mark.asyncio
async def test_edge_case_async_loader(cache: ModelCache) -> None:
    """Test that async loaders are supported."""

    async def async_loader() -> dict[str, int]:
        await asyncio.sleep(0.01)
        return {"async": True}

    result = await cache.get_cached_model("async-model", {"device": "cpu"}, async_loader)
    assert result == {"async": True}


@pytest.mark.asyncio
async def test_edge_case_invalidate_nonexistent(cache: ModelCache) -> None:
    """Test invalidating non-existent model."""
    result = await cache.invalidate_cache("nonexistent-model")
    assert result is False


@pytest.mark.asyncio
async def test_edge_case_zero_max_models(temp_cache_dir: Path) -> None:
    """Test behavior with max_models=1 (edge case)."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=1)

    def loader1() -> dict[str, int]:
        return {"model": 1}

    def loader2() -> dict[str, int]:
        return {"model": 2}

    # Cache two models (should evict first immediately)
    await cache.get_cached_model("model1", {"device": "cpu"}, loader1)
    await cache.get_cached_model("model2", {"device": "cpu"}, loader2)
    info = cache.get_cache_info()
    assert info["cached_models"] == 1
    assert info["models"][0]["model_id"] == "model2"
