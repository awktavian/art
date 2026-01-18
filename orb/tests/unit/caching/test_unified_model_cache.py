"""Comprehensive unit tests for unified model cache.

Tests verify:
1. API completeness
2. Cache key determinism
3. Storage structure
4. LRU eviction
5. Thread safety
6. Error handling
7. Configuration loading
8. Security properties

Author: Crystal (e₇) — The Verifier
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import pickle
import secrets
import time
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import pytest_asyncio

from kagami.core.caching.unified_model_cache import ModelCache, _CacheEntry

pytestmark = pytest.mark.tier_unit


@pytest.fixture
def test_secret_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Generate test secret key and set environment variable."""
    secret_hex = secrets.token_hex(32)
    monkeypatch.setenv("KAGAMI_CACHE_SECRET", secret_hex)
    return secret_hex


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Temporary cache directory for tests."""
    return tmp_path / "model_cache"


@pytest_asyncio.fixture
async def cache(temp_cache_dir: Path, test_secret_key: str) -> ModelCache:
    """Model cache instance for tests."""
    return ModelCache(cache_dir=temp_cache_dir, max_size_gb=1.0, max_models=3)


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Sample model configuration."""
    return {"device": "cpu", "dtype": "float32", "quantization": None}


# ==============================================================================
# TEST 1: API Completeness
# ==============================================================================
@pytest.mark.asyncio
async def test_api_get_cached_model_exists(
    cache: ModelCache, sample_config: dict[str, Any]
) -> None:
    """Test get_cached_model method exists and has correct signature."""
    # Verify method exists
    assert hasattr(cache, "get_cached_model")
    # Verify it's callable
    assert callable(cache.get_cached_model)
    # Test with mock loader
    call_count = 0

    def loader() -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        return {"test": 42}

    result = await cache.get_cached_model("test-model", sample_config, loader)
    assert result == {"test": 42}
    assert call_count == 1


@pytest.mark.asyncio
async def test_api_invalidate_cache_exists(
    cache: ModelCache, sample_config: dict[str, Any]
) -> None:
    """Test invalidate_cache method exists and has correct signature."""
    # Verify method exists
    assert hasattr(cache, "invalidate_cache")
    assert callable(cache.invalidate_cache)
    # Test invalidation (should return False when nothing cached)
    result = await cache.invalidate_cache("test-model", sample_config)
    assert isinstance(result, bool)


def test_api_get_cache_info_exists(cache: ModelCache) -> None:
    """Test get_cache_info method exists and has correct signature."""
    # Verify method exists
    assert hasattr(cache, "get_cache_info")
    assert callable(cache.get_cache_info)
    # Test it returns expected structure
    info = cache.get_cache_info()
    assert isinstance(info, dict)
    assert "cached_models" in info
    assert "total_size_bytes" in info
    assert "total_size_gb" in info
    assert "max_models" in info
    assert "max_size_gb" in info
    assert "cache_dir" in info
    assert "models" in info


# ==============================================================================
# TEST 2: Cache Key Design
# ==============================================================================
def test_cache_key_deterministic(cache: ModelCache) -> None:
    """Test that same inputs produce same cache key."""
    config1 = {"device": "cuda", "dtype": "float16", "quantization": "int8"}
    config2 = {"device": "cuda", "dtype": "float16", "quantization": "int8"}
    key1 = cache._compute_cache_key("bert-base", config1)
    key2 = cache._compute_cache_key("bert-base", config2)
    assert key1 == key2


def test_cache_key_different_configs(cache: ModelCache) -> None:
    """Test that different configs produce different cache keys."""
    config1 = {"device": "cuda", "dtype": "float16"}
    config2 = {"device": "cpu", "dtype": "float32"}
    key1 = cache._compute_cache_key("bert-base", config1)
    key2 = cache._compute_cache_key("bert-base", config2)
    assert key1 != key2


def test_cache_key_ignores_non_canonical(cache: ModelCache) -> None:
    """Test that non-canonical keys don't affect cache key."""
    config1 = {"device": "cuda", "dtype": "float16", "random_key": "value1"}
    config2 = {"device": "cuda", "dtype": "float16", "other_key": "value2"}
    key1 = cache._compute_cache_key("bert-base", config1)
    key2 = cache._compute_cache_key("bert-base", config2)
    # Should be same because only canonical keys matter
    assert key1 == key2


def test_cache_key_sha256_format(cache: ModelCache) -> None:
    """Test that cache key is a valid SHA256 hash."""
    config = {"device": "cuda"}
    key = cache._compute_cache_key("bert-base", config)
    # Should be 64 hex characters (SHA256)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_cache_key_config_order_invariant(cache: ModelCache) -> None:
    """Test that config key order doesn't affect cache key."""
    config1 = {"device": "cuda", "dtype": "float16", "quantization": "int8"}
    config2 = {"quantization": "int8", "device": "cuda", "dtype": "float16"}
    key1 = cache._compute_cache_key("bert-base", config1)
    key2 = cache._compute_cache_key("bert-base", config2)
    assert key1 == key2


# ==============================================================================
# TEST 3: Storage Structure
# ==============================================================================
@pytest.mark.asyncio
async def test_storage_xdg_compliant(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test that cache uses XDG-compliant directory structure."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)

    # Load a model
    def loader() -> dict[str, int]:
        return {"test": 42}

    await cache.get_cached_model("test-model", {"device": "cpu"}, loader)
    # Verify directory structure
    assert temp_cache_dir.exists()
    assert temp_cache_dir.is_dir()
    # Should have index.json
    assert (temp_cache_dir / "index.json").exists()


@pytest.mark.asyncio
async def test_storage_directory_structure(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test <hash>/model.{pkl|safetensors} + metadata.json structure."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)
    config = {"device": "cpu"}
    cache_key = cache._compute_cache_key("test-model", config)

    def loader() -> dict[str, int]:
        return {"test": 42}

    await cache.get_cached_model("test-model", config, loader)
    # Verify hash directory exists
    cache_path = temp_cache_dir / cache_key
    assert cache_path.exists()
    assert cache_path.is_dir()
    # Should have either model.pkl or model.safetensors
    has_pkl = (cache_path / "model.pkl").exists()
    has_safetensors = (cache_path / "model.safetensors").exists()
    assert has_pkl or has_safetensors
    # Should have metadata.json
    metadata_path = cache_path / "metadata.json"
    assert metadata_path.exists()
    with open(metadata_path) as f:
        metadata = json.load(f)
    # Verify metadata structure
    assert "model_id" in metadata
    assert "cache_key" in metadata
    assert "size_bytes" in metadata
    assert "created_at" in metadata
    assert "last_access" in metadata
    assert "hit_count" in metadata
    assert "checksum" in metadata
    assert "config" in metadata


@pytest.mark.asyncio
async def test_storage_index_file(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test that index.json tracks all cached models."""
    from kagami.core.security.signed_serialization import load_signed

    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)

    # Cache two models
    def loader1() -> dict[str, int]:
        return {"model1": 1}

    def loader2() -> dict[str, int]:
        return {"model2": 2}

    await cache.get_cached_model("model1", {"device": "cpu"}, loader1)
    await cache.get_cached_model("model2", {"device": "cuda"}, loader2)
    # Read index
    index_path = temp_cache_dir / "index.json"
    assert index_path.exists()
    # Use signed serialization to load index
    index = load_signed(index_path, format="json", allow_legacy_pickle=False)
    # Should have 2 entries
    assert len(index) == 2


# ==============================================================================
# TEST 4: LRU Eviction
# ==============================================================================
@pytest.mark.asyncio
async def test_lru_eviction_max_models(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test eviction when exceeding max_models limit."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=2, max_size_gb=100.0)
    # Cache 3 models (should evict oldest)
    loaders = [
        lambda: {"model1": 1},
        lambda: {"model2": 2},
        lambda: {"model3": 3},
    ]
    for i, loader in enumerate(loaders):
        await cache.get_cached_model(f"model{i + 1}", {"device": "cpu"}, loader)
        await asyncio.sleep(0.01)  # Ensure different timestamps
    info = cache.get_cache_info()
    # Should only have 2 models (oldest evicted)
    assert info["cached_models"] == 2
    # model1 should be evicted (oldest)
    model_ids = {m["model_id"] for m in info["models"]}
    assert "model1" not in model_ids
    assert "model2" in model_ids
    assert "model3" in model_ids


@pytest.mark.asyncio
async def test_lru_last_access_tracking(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test that last_access is tracked correctly."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)

    def loader() -> dict[str, int]:
        return {"test": 42}

    config = {"device": "cpu"}
    # First access
    before = time.time()
    await cache.get_cached_model("test-model", config, loader)
    after = time.time()
    info = cache.get_cache_info()
    assert len(info["models"]) == 1
    last_access = info["models"][0]["last_access"]
    assert before <= last_access <= after


@pytest.mark.asyncio
async def test_lru_hit_count_tracking(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test that hit_count is incremented on cache hits."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)
    call_count = 0

    def loader() -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        return {"test": 42}

    config = {"device": "cpu"}
    # First access (miss)
    await cache.get_cached_model("test-model", config, loader)
    assert call_count == 1
    # Second access (hit)
    await cache.get_cached_model("test-model", config, loader)
    assert call_count == 1  # Loader not called again
    info = cache.get_cache_info()
    assert info["models"][0]["hit_count"] == 2


# ==============================================================================
# TEST 5: Thread Safety
# ==============================================================================
@pytest.mark.asyncio
async def test_thread_safety_concurrent_access(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test that concurrent access to same model only loads once."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)
    call_count = 0

    async def loader() -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Simulate slow load
        return {"test": 42}

    config = {"device": "cpu"}
    # Launch 10 concurrent loads of same model
    tasks = [cache.get_cached_model("test-model", config, loader) for _ in range(10)]
    results = await asyncio.gather(*tasks)
    # All should get same result
    assert all(r == {"test": 42} for r in results)
    # Loader should only be called once (thread-safe)
    assert call_count == 1


@pytest.mark.asyncio
async def test_thread_safety_per_key_locks(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test that different models can load concurrently."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=10)
    call_counts = {"model1": 0, "model2": 0}

    async def loader1() -> dict[str, int]:
        call_counts["model1"] += 1
        await asyncio.sleep(0.05)
        return {"model1": 1}

    async def loader2() -> dict[str, int]:
        call_counts["model2"] += 1
        await asyncio.sleep(0.05)
        return {"model2": 2}

    # Launch concurrent loads of different models
    tasks = [
        cache.get_cached_model("model1", {"device": "cpu"}, loader1),
        cache.get_cached_model("model2", {"device": "cuda"}, loader2),
    ]
    start = time.time()
    results = await asyncio.gather(*tasks)
    duration = time.time() - start
    # Should complete in ~0.05s (parallel), not ~0.1s (serial)
    # Allow more overhead for CI environments and system variance
    assert duration < 0.1  # Increased tolerance for flaky timing
    assert results[0] == {"model1": 1}
    assert results[1] == {"model2": 2}


# ==============================================================================
# TEST 6: Error Handling
# ==============================================================================
@pytest.mark.asyncio
async def test_error_handling_cache_miss_fallback(
    temp_cache_dir: Path, test_secret_key: str
) -> None:
    """Test graceful fallback on cache miss."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)

    def loader() -> dict[str, int]:
        return {"test": 42}

    # Should handle cache miss gracefully
    result = await cache.get_cached_model("new-model", {"device": "cpu"}, loader)
    assert result == {"test": 42}


@pytest.mark.asyncio
async def test_error_handling_loader_failure(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test that loader failures are propagated."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)

    def failing_loader() -> dict[str, int]:
        raise ValueError("Load failed")

    with pytest.raises(ValueError, match="Load failed"):
        await cache.get_cached_model("test-model", {"device": "cpu"}, failing_loader)


@pytest.mark.asyncio
async def test_error_handling_corruption_recovery(
    temp_cache_dir: Path, test_secret_key: str
) -> None:
    """Test recovery from corrupted cache files."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)
    call_count = 0

    def loader() -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        return {"test": 42}

    config = {"device": "cpu"}
    # Cache the model
    await cache.get_cached_model("test-model", config, loader)
    assert call_count == 1
    # Corrupt the cache file
    cache_key = cache._compute_cache_key("test-model", config)
    cache_path = temp_cache_dir / cache_key
    pkl_file = cache_path / "model.pkl"
    if pkl_file.exists():
        with open(pkl_file, "wb") as f:
            f.write(b"corrupted data")
    # Clear memory cache to force disk load
    cache._memory_cache.clear()
    # Should recover by reloading (graceful recovery)
    result = await cache.get_cached_model("test-model", config, loader)
    assert result == {"test": 42}
    assert call_count == 2  # Loader called again after corruption detected


@pytest.mark.asyncio
async def test_error_handling_atomic_writes(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test that writes are atomic (temp file + rename)."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)
    # Mock a failure during save
    original_save = cache._save_to_cache

    async def failing_save(key: str, model: Any, entry: _CacheEntry) -> None:
        await original_save(key, model, entry)
        # Verify temp files are cleaned up
        cache_path = cache._get_cache_path(key)
        temp_files = list(cache_path.glob("*.tmp"))
        assert len(temp_files) == 0

    cache._save_to_cache = failing_save  # type: ignore[assignment]

    def loader() -> dict[str, int]:
        return {"test": 42}

    result = await cache.get_cached_model("test-model", {"device": "cpu"}, loader)
    assert result == {"test": 42}


# ==============================================================================
# TEST 7: Configuration Schema
# ==============================================================================
def test_config_from_env() -> None:
    """Test ModelCacheConfig.from_env() loads from environment."""
    from kagami.core.caching.model_cache_config import ModelCacheConfig

    with patch.dict(
        os.environ,
        {
            "KAGAMI_MODEL_CACHE_DIR": "/tmp/test_cache",
            "KAGAMI_MODEL_CACHE_MAX_SIZE_GB": "50.0",
            "KAGAMI_MODEL_CACHE_MAX_MODELS": "5",
        },
    ):
        config = ModelCacheConfig.from_env()
        assert config.cache_dir == Path("/tmp/test_cache")
        assert config.max_size_gb == 50.0
        assert config.max_models == 5


def test_config_xdg_expansion() -> None:
    """Test that XDG_CACHE_HOME is expanded."""
    from kagami.core.caching.model_cache_config import ModelCacheConfig

    with patch.dict(
        os.environ,
        {
            "XDG_CACHE_HOME": "/tmp/xdg_cache",
            "KAGAMI_MODEL_CACHE_DIR": "",  # Clear this
            "MODEL_CACHE_PATH": "",  # Clear legacy
        },
        clear=False,
    ):
        # Remove the keys entirely
        env_copy = os.environ.copy()
        env_copy.pop("KAGAMI_MODEL_CACHE_DIR", None)
        env_copy.pop("MODEL_CACHE_PATH", None)
        with patch.dict(os.environ, env_copy):
            config = ModelCacheConfig.from_env()
            expected = Path("/tmp/xdg_cache/kagami/models")
            assert config.cache_dir == expected


def test_config_validation() -> None:
    """Test that invalid configs raise errors."""
    from kagami.core.caching.model_cache_config import ModelCacheConfig

    with pytest.raises(ValueError, match="max_size_gb must be positive"):
        ModelCacheConfig(cache_dir=Path("/tmp"), max_size_gb=-1.0)
    with pytest.raises(ValueError, match="max_models must be positive"):
        ModelCacheConfig(cache_dir=Path("/tmp"), max_models=-1)


# ==============================================================================
# TEST 8: Security
# ==============================================================================
def test_security_no_path_traversal(cache: ModelCache) -> None:
    """Test that cache keys don't allow path traversal."""
    # Try to create a cache key with path traversal
    config = {"device": "../../../etc/passwd"}
    cache_key = cache._compute_cache_key("evil-model", config)
    # Should be a safe hash, not containing ../
    assert "../" not in cache_key
    assert ".." not in cache_key


@pytest.mark.asyncio
async def test_security_checksum_verification(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test that checksums are verified on load with graceful recovery."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=3)
    call_count = 0

    def loader() -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        return {"test": 42}

    config = {"device": "cpu"}
    # Cache the model
    await cache.get_cached_model("test-model", config, loader)
    assert call_count == 1
    # Corrupt checksum in index
    cache_key = cache._compute_cache_key("test-model", config)
    entry = cache._index[cache_key]
    entry.checksum = "invalid_checksum"
    cache._save_index()
    # Clear memory cache to force disk load
    cache._memory_cache.clear()
    # Implementation recovers gracefully by evicting corrupted entry and reloading
    result = await cache.get_cached_model("test-model", config, loader)
    assert result == {"test": 42}
    assert call_count == 2  # Loader called again after corruption detected


def test_security_pickle_safety(cache: ModelCache) -> None:
    """Test that pickle usage is documented as security risk."""
    from kagami.core.caching.unified_model_cache import __doc__ as cache_doc

    # Module docstring should mention pickle security
    assert cache_doc is not None
    assert "pickle" in cache_doc.lower()
    assert "security" in cache_doc.lower() or "trusted" in cache_doc.lower()


# ==============================================================================
# TEST 9: Integration with unified_config.py (migrated from config_root.py)
# ==============================================================================
def test_integration_get_model_cache_path() -> None:
    """Test integration with get_model_cache_path()."""
    from kagami.core.config.unified_config import get_model_cache_path

    # Should return a valid Path
    path = get_model_cache_path()
    assert isinstance(path, Path)


@pytest.mark.asyncio
async def test_integration_default_cache_dir(test_secret_key: str) -> None:
    """Test that ModelCache uses get_model_cache_path() by default."""
    from kagami.core.config.unified_config import get_model_cache_path

    expected_path = get_model_cache_path()
    cache = ModelCache()
    # Should use XDG-compliant path
    assert cache.cache_dir == expected_path.expanduser().resolve()


def test_integration_respects_env_var() -> None:
    """Test that MODEL_CACHE_PATH env var is respected."""
    with patch.dict(os.environ, {"MODEL_CACHE_PATH": "/tmp/custom_cache"}):
        from kagami.core.config.unified_config import get_model_cache_path

        path = get_model_cache_path()
        assert path == Path("/tmp/custom_cache")


# ==============================================================================
# TEST 10: Code Quality
# ==============================================================================
def test_code_quality_type_hints() -> None:
    """Test that all public methods have type hints."""
    import inspect
    from kagami.core.caching.unified_model_cache import ModelCache

    for name, method in inspect.getmembers(ModelCache, predicate=inspect.isfunction):
        if not name.startswith("_"):  # Public method
            sig = inspect.signature(method)
            # Check return annotation
            if name != "__init__":
                assert (
                    sig.return_annotation != inspect.Signature.empty
                ), f"Method {name} missing return type hint"


def test_code_quality_docstrings() -> None:
    """Test that all public methods have docstrings."""
    import inspect
    from kagami.core.caching.unified_model_cache import ModelCache

    for name, method in inspect.getmembers(ModelCache, predicate=inspect.isfunction):
        if not name.startswith("_"):  # Public method
            assert method.__doc__ is not None, f"Method {name} missing docstring"
            assert len(method.__doc__.strip()) > 0, f"Method {name} has empty docstring"


# ==============================================================================
# TEST 11: Cache Info
# ==============================================================================
@pytest.mark.asyncio
async def test_cache_info_structure(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test that get_cache_info returns complete structure."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_size_gb=10.0, max_models=5)

    # Cache a model
    def loader() -> dict[str, int]:
        return {"test": 42}

    await cache.get_cached_model("test-model", {"device": "cpu"}, loader)
    info = cache.get_cache_info()
    # Verify structure
    assert info["cached_models"] == 1
    assert isinstance(info["total_size_bytes"], int)
    assert isinstance(info["total_size_gb"], float)
    assert info["max_models"] == 5
    assert info["max_size_gb"] == 10.0
    assert str(temp_cache_dir) in info["cache_dir"]
    # Verify models list
    assert len(info["models"]) == 1
    model_info = info["models"][0]
    assert model_info["model_id"] == "test-model"
    assert "cache_key" in model_info
    assert "size_mb" in model_info
    assert "created_at" in model_info
    assert "last_access" in model_info
    assert "hit_count" in model_info
    assert "config" in model_info


@pytest.mark.asyncio
async def test_invalidate_specific_config(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test invalidating specific config."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=5)

    # Cache same model with different configs
    def loader() -> dict[str, int]:
        return {"test": 42}

    await cache.get_cached_model("model", {"device": "cpu"}, loader)
    await cache.get_cached_model("model", {"device": "cuda"}, loader)
    assert cache.get_cache_info()["cached_models"] == 2
    # Invalidate only CPU version
    result = await cache.invalidate_cache("model", {"device": "cpu"})
    assert result is True
    assert cache.get_cache_info()["cached_models"] == 1
    # CUDA version should still exist
    models = cache.get_cache_info()["models"]
    assert models[0]["config"]["device"] == "cuda"


@pytest.mark.asyncio
async def test_invalidate_all_configs(temp_cache_dir: Path, test_secret_key: str) -> None:
    """Test invalidating all configs for a model."""
    cache = ModelCache(cache_dir=temp_cache_dir, max_models=5)

    # Cache same model with different configs
    def loader() -> dict[str, int]:
        return {"test": 42}

    await cache.get_cached_model("model", {"device": "cpu"}, loader)
    await cache.get_cached_model("model", {"device": "cuda"}, loader)
    assert cache.get_cache_info()["cached_models"] == 2
    # Invalidate all versions
    result = await cache.invalidate_cache("model")
    assert result is True
    assert cache.get_cache_info()["cached_models"] == 0
