"""Integration test for ModelCache + LLM providers.

Tests:
1. ModelCache API integration
2. Cache hit tracking
3. Different configs create different cache entries
4. Cache info is accessible

Author: Forge (e₂) — The Builder

Note: Full LLM provider mocking is complex. These tests focus on the
ModelCache integration layer.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch

from kagami.core.caching.unified_model_cache import ModelCache
from kagami.core.services.llm.llm_providers import TransformersTextClient


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Temporary cache directory for tests."""
    return tmp_path / "model_cache"


@pytest.mark.asyncio
async def test_cache_hit_tracking(temp_cache_dir: Path) -> None:
    """Test that cache hits are tracked correctly."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)

    call_count = 0

    def loader() -> Dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return {"model": "test"}

    config = {"device": "cpu", "dtype": "float32"}

    # First load (miss)
    await cache.get_cached_model("test-model", config, loader)
    assert call_count == 1

    info = cache.get_cache_info()
    assert info["models"][0]["hit_count"] == 1

    # Second load (hit)
    await cache.get_cached_model("test-model", config, loader)
    assert call_count == 1  # Loader not called again

    info = cache.get_cache_info()
    assert info["models"][0]["hit_count"] == 2


@pytest.mark.asyncio
async def test_different_configs_different_cache(temp_cache_dir: Path) -> None:
    """Test that different configs create different cache entries."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=5)

    def loader_cpu() -> Dict[str, Any]:
        return {"model": "cpu_version"}

    def loader_cuda() -> Dict[str, Any]:
        return {"model": "cuda_version"}

    config_cpu = {"device": "cpu", "dtype": "float32"}
    config_cuda = {"device": "cuda", "dtype": "float16"}

    # Load with different configs
    result_cpu = await cache.get_cached_model("test-model", config_cpu, loader_cpu)
    result_cuda = await cache.get_cached_model("test-model", config_cuda, loader_cuda)

    assert result_cpu != result_cuda

    # Should have 2 cache entries
    info = cache.get_cache_info()
    assert info["cached_models"] == 2

    # Both should be for same model_id
    model_ids = [m["model_id"] for m in info["models"]]
    assert model_ids.count("test-model") == 2

    # But different configs
    configs = [m["config"] for m in info["models"]]
    assert config_cpu in configs
    assert config_cuda in configs


@pytest.mark.asyncio
async def test_cache_integration_with_config() -> None:
    """Test that ModelCache config can be loaded from environment."""
    from kagami.core.caching.model_cache_config import ModelCacheConfig

    with patch.dict(
        os.environ,
        {
            "KAGAMI_MODEL_CACHE_MAX_SIZE_GB": "50.0",
            "KAGAMI_MODEL_CACHE_MAX_MODELS": "5",
        },
    ):
        config = ModelCacheConfig.from_env()
        assert config.max_size_gb == 50.0
        assert config.max_models == 5


@pytest.mark.asyncio
async def test_cache_info_accessible_from_resolver() -> None:
    """Test that cached_model_resolver can access ModelCache info."""
    from kagami.core.services.llm.cached_model_resolver import log_available_models
    from kagami.core.caching.unified_model_cache import get_model_cache

    cache = get_model_cache()

    # Add a dummy model to cache
    def loader() -> Dict[str, Any]:
        return {"test": 42}

    await cache.get_cached_model("test-model", {"device": "cpu"}, loader)

    # Should not raise exception
    try:
        log_available_models()
    except Exception as e:
        pytest.fail(f"log_available_models raised exception: {e}")


def test_modelcache_enabled_env_var() -> Any:
    """Test that KAGAMI_MODEL_CACHE_ENABLED env var is respected."""
    from kagami.core.services.llm.llm_providers import _truthy_env

    with patch.dict(os.environ, {"KAGAMI_MODEL_CACHE_ENABLED": "1"}):
        assert _truthy_env("KAGAMI_MODEL_CACHE_ENABLED", "0") is True

    with patch.dict(os.environ, {"KAGAMI_MODEL_CACHE_ENABLED": "0"}):
        assert _truthy_env("KAGAMI_MODEL_CACHE_ENABLED", "1") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
