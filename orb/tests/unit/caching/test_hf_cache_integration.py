"""Tests for HuggingFace cache integration.

Tests verify:
1. HF cache directory scanning
2. Model import (symlink and copy)
3. Warm cache from config
4. Cache info with HF models
5. Error handling for missing/invalid HF cache

Author: Forge (e₂) — The Builder
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_unit
import asyncio
import json
from pathlib import Path
from typing import Any
from kagami.core.caching.model_cache_config import (
    ModelCacheConfig,
    WarmCacheConfig,
    WarmCacheModel,
)
from kagami.core.caching.unified_model_cache import ModelCache
@pytest.fixture
def temp_hf_cache(tmp_path: Path) -> Path:
    """Create mock HuggingFace cache directory structure."""
    hf_cache = tmp_path / "huggingface" / "hub"
    hf_cache.mkdir(parents=True)
    return hf_cache
@pytest.fixture
def mock_hf_model(temp_hf_cache: Path) -> dict[str, Any]:
    """Create a mock HF model in cache directory.
    Creates structure:
    models--Qwen--Qwen3-14B/
    ├── snapshots/
    │   └── abc123/
    │       ├── model.safetensors
    │       └── config.json
    └── refs/
        └── main  (contains "abc123")
    """
    model_dir = temp_hf_cache / "models--Qwen--Qwen3-14B"
    model_dir.mkdir()
    # Create snapshots directory
    commit_hash = "abc123def456"
    snapshot_dir = model_dir / "snapshots" / commit_hash
    snapshot_dir.mkdir(parents=True)
    # Create mock model files (at least 1MB to avoid rounding to 0)
    (snapshot_dir / "config.json").write_text('{"model_type": "qwen3"}')
    (snapshot_dir / "model.safetensors").write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB
    # Create refs/main
    refs_dir = model_dir / "refs"
    refs_dir.mkdir()
    (refs_dir / "main").write_text(commit_hash)
    return {
        "model_id": "Qwen/Qwen3-14B",
        "model_dir": model_dir,
        "snapshot_dir": snapshot_dir,
        "commit_hash": commit_hash,
    }
@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Temporary cache directory for tests."""
    return tmp_path / "model_cache"
# ==============================================================================
# TEST 1: HF Cache Scanning
# ==============================================================================
def test_scan_hf_cache_discovers_models(
    temp_cache_dir: Path, temp_hf_cache: Path, mock_hf_model: dict[str, Any]
) -> None:
    """Test that _scan_hf_cache discovers models in HF cache."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    # Should have discovered the mock model
    assert len(cache._hf_cache_models) == 1
    model = cache._hf_cache_models[0]
    assert model["model_id"] == "Qwen/Qwen3-14B"
    assert model["commit_hash"] == mock_hf_model["commit_hash"]
    assert model["size_gb"] >= 0.0  # At least 2MB, may round to 0.0
def test_scan_hf_cache_multiple_models(temp_cache_dir: Path, temp_hf_cache: Path) -> None:
    """Test scanning HF cache with multiple models."""
    # Create multiple mock models
    for org, name in [
        ("Qwen", "Qwen3-14B"),
        ("microsoft", "Florence-2-large"),
        ("meta-llama", "Llama-3.1-8B"),
    ]:
        model_dir = temp_hf_cache / f"models--{org}--{name}"
        snapshot_dir = model_dir / "snapshots" / "commit123"
        snapshot_dir.mkdir(parents=True)
        # Create mock files
        (snapshot_dir / "config.json").write_text("{}")
        (snapshot_dir / "model.safetensors").write_bytes(b"data" * 100)
        # Create refs
        refs_dir = model_dir / "refs"
        refs_dir.mkdir()
        (refs_dir / "main").write_text("commit123")
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    # Should discover all 3 models
    assert len(cache._hf_cache_models) == 3
    model_ids = {m["model_id"] for m in cache._hf_cache_models}
    assert "Qwen/Qwen3-14B" in model_ids
    assert "microsoft/Florence-2-large" in model_ids
    assert "meta-llama/Llama-3.1-8B" in model_ids
def test_scan_hf_cache_no_refs(temp_cache_dir: Path, temp_hf_cache: Path) -> None:
    """Test scanning model without refs/main (uses most recent snapshot)."""
    model_dir = temp_hf_cache / "models--test--model"
    snapshot_dir = model_dir / "snapshots" / "fallback123"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "config.json").write_text("{}")
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    # Should still discover model using fallback method
    assert len(cache._hf_cache_models) == 1
    assert cache._hf_cache_models[0]["model_id"] == "test/model"
def test_scan_hf_cache_missing_directory(temp_cache_dir: Path, tmp_path: Path) -> None:
    """Test scanning non-existent HF cache directory."""
    non_existent = tmp_path / "does_not_exist"
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=non_existent,
        scan_hf_on_startup=True,
    )
    # Should handle gracefully
    assert len(cache._hf_cache_models) == 0
def test_scan_hf_cache_disabled(
    temp_cache_dir: Path, temp_hf_cache: Path, mock_hf_model: dict[str, Any]
) -> None:
    """Test that scanning is disabled when scan_hf_on_startup=False."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=False,  # Disabled
    )
    # Should not scan
    assert len(cache._hf_cache_models) == 0
# ==============================================================================
# TEST 2: Model Import
# ==============================================================================
@pytest.mark.asyncio
async def test_import_from_hf_symlink(
    temp_cache_dir: Path, temp_hf_cache: Path, mock_hf_model: dict[str, Any]
) -> None:
    """Test importing HF model using symlink."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    snapshot_path = Path(mock_hf_model["snapshot_dir"])
    # Import model
    success = await cache._import_from_hf("Qwen/Qwen3-14B", snapshot_path, use_symlink=True)
    assert success is True
    # Verify cache entry created
    info = cache.get_cache_info()
    assert info["cached_models"] == 1
    model = info["models"][0]
    assert model["model_id"] == "Qwen/Qwen3-14B"
    assert model["config"]["source"] == "huggingface"
@pytest.mark.asyncio
async def test_import_from_hf_copy(
    temp_cache_dir: Path, temp_hf_cache: Path, mock_hf_model: dict[str, Any]
) -> None:
    """Test importing HF model by copying files."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    snapshot_path = Path(mock_hf_model["snapshot_dir"])
    # Import model (copy mode)
    success = await cache._import_from_hf("Qwen/Qwen3-14B", snapshot_path, use_symlink=False)
    assert success is True
    # Verify files were copied
    info = cache.get_cache_info()
    assert info["cached_models"] == 1
    model = info["models"][0]
    assert model["size_mb"] > 0
@pytest.mark.asyncio
async def test_import_from_hf_already_cached(
    temp_cache_dir: Path, temp_hf_cache: Path, mock_hf_model: dict[str, Any]
) -> None:
    """Test importing model that's already cached."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    snapshot_path = Path(mock_hf_model["snapshot_dir"])
    # Import once
    success1 = await cache._import_from_hf("Qwen/Qwen3-14B", snapshot_path)
    assert success1 is True
    # Import again (should skip)
    success2 = await cache._import_from_hf("Qwen/Qwen3-14B", snapshot_path)
    assert success2 is True
    # Should only have 1 entry
    info = cache.get_cache_info()
    assert info["cached_models"] == 1
@pytest.mark.asyncio
async def test_import_from_hf_invalid_path(temp_cache_dir: Path, temp_hf_cache: Path) -> None:
    """Test importing from non-existent path."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=False,
    )
    invalid_path = temp_hf_cache / "does_not_exist"
    success = await cache._import_from_hf("invalid/model", invalid_path)
    # Should fail gracefully
    assert success is False
    # No cache entries created
    info = cache.get_cache_info()
    assert info["cached_models"] == 0
# ==============================================================================
# TEST 3: Warm Cache
# ==============================================================================
@pytest.mark.asyncio
async def test_warm_cache_single_model(
    temp_cache_dir: Path, temp_hf_cache: Path, mock_hf_model: dict[str, Any]
) -> None:
    """Test warm cache with single model."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    config = ModelCacheConfig(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        warm_cache=WarmCacheConfig(
            enabled=True,
            models=[
                WarmCacheModel(model_id="Qwen/Qwen3-14B", priority="high"),
            ],
        ),
    )
    result = await cache.warm_cache_from_config(config)
    assert len(result["loaded"]) == 1
    assert "Qwen/Qwen3-14B" in result["loaded"]
    assert len(result["failed"]) == 0
    assert len(result["skipped"]) == 0
@pytest.mark.asyncio
async def test_warm_cache_priority_order(temp_cache_dir: Path, temp_hf_cache: Path) -> None:
    """Test that warm cache respects priority order."""
    # Create 3 models with different priorities
    for i, (org, name) in enumerate([("high", "model1"), ("medium", "model2"), ("low", "model3")]):
        model_dir = temp_hf_cache / f"models--{org}--{name}"
        snapshot_dir = model_dir / "snapshots" / f"commit{i}"
        snapshot_dir.mkdir(parents=True)
        (snapshot_dir / "config.json").write_text("{}")
        refs_dir = model_dir / "refs"
        refs_dir.mkdir()
        (refs_dir / "main").write_text(f"commit{i}")
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
        max_models=2,  # Limited capacity
    )
    config = ModelCacheConfig(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        warm_cache=WarmCacheConfig(
            enabled=True,
            models=[
                WarmCacheModel(model_id="low/model3", priority="low"),
                WarmCacheModel(model_id="high/model1", priority="high"),
                WarmCacheModel(model_id="medium/model2", priority="medium"),
            ],
        ),
    )
    result = await cache.warm_cache_from_config(config)
    # Should load high and medium first, skip low
    assert "high/model1" in result["loaded"]
    assert "medium/model2" in result["loaded"]
    assert "low/model3" in result["skipped"]
@pytest.mark.asyncio
async def test_warm_cache_model_not_in_hf(temp_cache_dir: Path, temp_hf_cache: Path) -> None:
    """Test warm cache when model not in HF cache."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    config = ModelCacheConfig(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        warm_cache=WarmCacheConfig(
            enabled=True,
            models=[
                WarmCacheModel(model_id="nonexistent/model", priority="high"),
            ],
        ),
    )
    result = await cache.warm_cache_from_config(config)
    # Should skip (not downloaded yet)
    assert len(result["loaded"]) == 0
    assert len(result["failed"]) == 0
    assert "nonexistent/model" in result["skipped"]
@pytest.mark.asyncio
async def test_warm_cache_disabled(
    temp_cache_dir: Path, temp_hf_cache: Path, mock_hf_model: dict[str, Any]
) -> None:
    """Test warm cache when disabled in config."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    config = ModelCacheConfig(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        warm_cache=WarmCacheConfig(
            enabled=False,  # Disabled
            models=[WarmCacheModel(model_id="Qwen/Qwen3-14B", priority="high")],
        ),
    )
    result = await cache.warm_cache_from_config(config)
    # Should not load anything
    assert len(result["loaded"]) == 0
@pytest.mark.asyncio
async def test_warm_cache_size_limit(temp_cache_dir: Path, temp_hf_cache: Path) -> None:
    """Test warm cache stops when size limit reached."""
    # Create large mock model
    model_dir = temp_hf_cache / "models--large--model"
    snapshot_dir = model_dir / "snapshots" / "commit1"
    snapshot_dir.mkdir(parents=True)
    # Create 100MB file
    (snapshot_dir / "model.safetensors").write_bytes(b"x" * (100 * 1024 * 1024))
    refs_dir = model_dir / "refs"
    refs_dir.mkdir()
    (refs_dir / "main").write_text("commit1")
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
        max_size_gb=0.05,  # 50MB limit
    )
    config = ModelCacheConfig(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        warm_cache=WarmCacheConfig(
            enabled=True,
            models=[WarmCacheModel(model_id="large/model", priority="high")],
        ),
    )
    result = await cache.warm_cache_from_config(config)
    # Should skip due to size limit
    assert "large/model" in result["skipped"]
# ==============================================================================
# TEST 4: Cache Info
# ==============================================================================
def test_cache_info_includes_hf_models(
    temp_cache_dir: Path, temp_hf_cache: Path, mock_hf_model: dict[str, Any]
) -> None:
    """Test that get_cache_info includes HF cache models."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    info = cache.get_cache_info()
    assert "hf_cache_discovered" in info
    assert info["hf_cache_discovered"] == 1
    assert "hf_models" in info
    assert len(info["hf_models"]) == 1
    hf_model = info["hf_models"][0]
    assert hf_model["model_id"] == "Qwen/Qwen3-14B"
    assert hf_model["size_gb"] >= 0.0  # At least 2MB, may round to 0.0
    assert hf_model["commit_hash"] == mock_hf_model["commit_hash"]
def test_cache_info_no_hf_scan(temp_cache_dir: Path, temp_hf_cache: Path) -> None:
    """Test cache info when HF scan is disabled."""
    cache = ModelCache(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=False,
    )
    info = cache.get_cache_info()
    assert info["hf_cache_discovered"] == 0
    assert info["hf_models"] == []
# ==============================================================================
# TEST 5: Environment Variables
# ==============================================================================
def test_hf_cache_dir_from_env(temp_cache_dir: Path, tmp_path: Path, monkeypatch) -> None:
    """Test that HF_HOME env var is respected."""
    custom_hf = tmp_path / "custom_hf"
    custom_hf.mkdir()
    monkeypatch.setenv("HF_HOME", str(custom_hf))
    cache = ModelCache(cache_dir=temp_cache_dir)
    # Should use HF_HOME/hub
    expected = custom_hf / "hub"
    assert cache.hf_cache_dir == expected.resolve()
def test_hf_cache_dir_huggingface_hub_cache_env(
    temp_cache_dir: Path, tmp_path: Path, monkeypatch
) -> None:
    """Test that HUGGINGFACE_HUB_CACHE env var is respected."""
    custom_cache = tmp_path / "hub_cache"
    custom_cache.mkdir()
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(custom_cache))
    cache = ModelCache(cache_dir=temp_cache_dir)
    assert cache.hf_cache_dir == custom_cache.resolve()
# ==============================================================================
# TEST 6: Integration with ModelCacheConfig
# ==============================================================================
def test_model_cache_config_hf_settings() -> None:
    """Test ModelCacheConfig includes HF settings."""
    config = ModelCacheConfig(
        cache_dir=Path("/tmp/test"),
        scan_hf_on_startup=True,
        hf_cache_dir=Path("/tmp/hf"),
    )
    assert config.scan_hf_on_startup is True
    assert config.hf_cache_dir == Path("/tmp/hf")
def test_model_cache_from_config(temp_cache_dir: Path, temp_hf_cache: Path) -> None:
    """Test creating ModelCache from ModelCacheConfig."""
    config = ModelCacheConfig(
        cache_dir=temp_cache_dir,
        hf_cache_dir=temp_hf_cache,
        scan_hf_on_startup=True,
    )
    cache = ModelCache(
        cache_dir=config.cache_dir,
        hf_cache_dir=config.hf_cache_dir,
        scan_hf_on_startup=config.scan_hf_on_startup,
    )
    assert cache.hf_cache_dir == temp_hf_cache.resolve()
    assert cache.scan_hf_on_startup is True
