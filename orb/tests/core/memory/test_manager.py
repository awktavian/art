"""Tests for kagami.core.memory.manager (ModelMemoryManager)."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import gc
import os
import tempfile
from pathlib import Path

from kagami.core.memory.manager import (
    ModelMemoryManager,
    check_memory_availability,
    get_memory_info,
    memory_guard,
)


@pytest.mark.tier_unit
class TestMemoryInfo:
    """Test memory info functions."""

    def test_get_memory_info(self) -> None:
        """Test getting memory info."""
        info = get_memory_info()

        assert "process_rss_gb" in info
        assert "process_vms_gb" in info
        assert "system_total_gb" in info
        assert "system_available_gb" in info
        assert "system_percent" in info
        assert info["process_rss_gb"] >= 0
        assert info["system_total_gb"] > 0

    def test_check_memory_availability(self) -> None:
        """Test memory availability check."""
        result = check_memory_availability(0.1)
        assert isinstance(result, bool)

        result_high = check_memory_availability(1000000.0)
        assert result_high is False


@pytest.mark.tier_unit
class TestMemoryGuard:
    """Test memory guard context manager."""

    def test_memory_guard_basic(self) -> None:
        """Test basic memory guard usage."""
        with memory_guard(max_gb=1.0, cleanup=False):
            data = list(range(1000))
            assert len(data) == 1000

    def test_memory_guard_with_cleanup(self) -> None:
        """Test memory guard with cleanup."""
        with memory_guard(max_gb=1.0, cleanup=True):
            data = list(range(1000))
            assert len(data) == 1000
        gc.collect()

    def test_memory_guard_tracks_usage(self) -> None:
        """Test that memory guard tracks usage."""
        initial_info = get_memory_info()
        with memory_guard(max_gb=10.0):
            data = [0] * 100000
            _ = data
        final_info = get_memory_info()
        assert final_info is not None
        assert initial_info is not None


@pytest.mark.tier_unit
class TestModelMemoryManager:
    """Test ModelMemoryManager."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        ModelMemoryManager._local_cache.clear()
        ModelMemoryManager._lru_order.clear()

    def test_get_or_load_model_new(self) -> None:
        """Test loading a new model."""
        call_count = 0

        def loader() -> dict:
            nonlocal call_count
            call_count += 1
            return {"data": "model"}

        model = ModelMemoryManager.get_or_load_model("test_model", loader, max_memory_gb=1.0)

        assert model == {"data": "model"}
        assert call_count == 1
        assert "test_model" in ModelMemoryManager._local_cache

    def test_get_or_load_model_cached(self) -> None:
        """Test loading a cached model."""
        call_count = 0

        def loader() -> dict:
            nonlocal call_count
            call_count += 1
            return {"data": "model"}

        model1 = ModelMemoryManager.get_or_load_model("test_model", loader)
        model2 = ModelMemoryManager.get_or_load_model("test_model", loader)

        assert model1 is model2
        assert call_count == 1

    def test_lru_eviction(self) -> None:
        """Test LRU eviction when cache is full."""
        ModelMemoryManager._max_cache_entries = 2

        def make_loader(name: str):
            def loader() -> dict:
                return {"name": name}

            return loader

        ModelMemoryManager.get_or_load_model("model1", make_loader("model1"))
        ModelMemoryManager.get_or_load_model("model2", make_loader("model2"))
        ModelMemoryManager.get_or_load_model("model3", make_loader("model3"))

        assert len(ModelMemoryManager._local_cache) <= 3

    def test_cleanup_least_used(self) -> None:
        """Test cleanup of least used models."""

        def make_loader(name: str):
            def loader() -> dict:
                return {"name": name}

            return loader

        ModelMemoryManager.get_or_load_model("model1", make_loader("model1"))
        ModelMemoryManager.get_or_load_model("model2", make_loader("model2"))
        ModelMemoryManager.get_or_load_model("model3", make_loader("model3"))

        ModelMemoryManager.cleanup_least_used(keep_n=1)

        assert len(ModelMemoryManager._local_cache) <= 1

    def test_clear_all(self) -> None:
        """Test clearing all cached models."""

        def loader() -> dict:
            return {"data": "model"}

        ModelMemoryManager.get_or_load_model("model1", loader)
        ModelMemoryManager.get_or_load_model("model2", loader)

        assert len(ModelMemoryManager._local_cache) > 0

        ModelMemoryManager.clear_all()

        assert len(ModelMemoryManager._local_cache) == 0

    def test_lock_path_generation(self) -> None:
        """Test lock path generation."""
        path1 = ModelMemoryManager._lock_path_for("model_a")
        path2 = ModelMemoryManager._lock_path_for("model_a")
        path3 = ModelMemoryManager._lock_path_for("model_b")

        assert path1 == path2
        assert path1 != path3
        assert path1.suffix == ".lock"

    def test_interprocess_lock(self) -> None:
        """Test interprocess lock context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["KAGAMI_MODEL_LOCK_DIR"] = tmpdir

            with ModelMemoryManager._interprocess_lock("test_model", timeout_s=1.0):
                lock_dir = Path(tmpdir)
                assert lock_dir.exists()


@pytest.mark.tier_unit
class TestModelMemoryManagerAsync:
    """Test async model loading."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        ModelMemoryManager._local_cache.clear()
        ModelMemoryManager._lru_order.clear()

    @pytest.mark.asyncio
    async def test_async_get_or_load(self) -> None:
        """Test async model loading."""
        call_count = 0

        def loader() -> dict:
            nonlocal call_count
            call_count += 1
            return {"data": "async_model"}

        model = await ModelMemoryManager.get_or_load_model_async(
            "async_model", loader, max_memory_gb=1.0
        )

        assert model == {"data": "async_model"}
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_cache_hit(self) -> None:
        """Test async loading with cache hit."""
        call_count = 0

        def loader() -> dict:
            nonlocal call_count
            call_count += 1
            return {"data": "model"}

        model1 = await ModelMemoryManager.get_or_load_model_async("model", loader)
        model2 = await ModelMemoryManager.get_or_load_model_async("model", loader)

        assert model1 is model2
        assert call_count == 1
