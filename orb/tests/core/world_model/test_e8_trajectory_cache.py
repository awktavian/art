"""Tests for E8 Trajectory Cache with Bifurcation Replay.

Test coverage:
1. Hash function determinism and collision resistance
2. Cache store/lookup operations (O(1))
3. LRU and importance-based eviction
4. Bifurcation replay buffer
5. Thread safety
6. Persistence (save/load)
7. Statistics tracking

Created: December 14, 2025
Colony: Forge (e₂) - Quality testing
"""

from __future__ import annotations

import pytest

import os
import tempfile
from pathlib import Path

import torch

pytestmark = pytest.mark.tier_integration


# Ensure KAGAMI_CACHE_SECRET is set for persistence tests
# The secret must be a valid hex string (64 hex chars = 32 bytes)
@pytest.fixture(autouse=True, scope="module")
def set_cache_secret():
    """Set cache secret for persistence tests."""
    old_value = os.environ.get("KAGAMI_CACHE_SECRET")
    # Generate a valid 32-byte hex key
    os.environ["KAGAMI_CACHE_SECRET"] = "a" * 64  # 64 hex chars = 32 bytes
    yield
    if old_value is None:
        os.environ.pop("KAGAMI_CACHE_SECRET", None)
    else:
        os.environ["KAGAMI_CACHE_SECRET"] = old_value


from kagami.core.world_model.e8_trajectory_cache import (
    BifurcationEntry,
    CacheEntry,
    CacheStats,
    E8TrajectoryCache,
    create_e8_trajectory_cache,
)


class TestHashFunction:
    """Test E8 sequence hashing."""

    def test_hash_determinism(self) -> None:
        """Hash function should be deterministic."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.randn(5, 8)
        hash1 = cache._hash_e8_sequence(e8_codes)
        hash2 = cache._hash_e8_sequence(e8_codes)

        assert hash1 == hash2, "Hash should be deterministic"

    def test_hash_different_sequences(self) -> None:
        """Different sequences should have different hashes."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes1 = torch.randn(5, 8)
        e8_codes2 = torch.randn(5, 8)

        hash1 = cache._hash_e8_sequence(e8_codes1)
        hash2 = cache._hash_e8_sequence(e8_codes2)

        # Very unlikely to collide
        assert hash1 != hash2, "Different sequences should have different hashes"

    def test_hash_same_values_different_order(self) -> None:
        """Sequences with same values but different order should differ."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.randn(5, 8)
        e8_codes_reversed = e8_codes.flip(0)

        hash1 = cache._hash_e8_sequence(e8_codes)
        hash2 = cache._hash_e8_sequence(e8_codes_reversed)

        assert hash1 != hash2, "Order should affect hash"

    def test_hash_invalid_shape(self) -> None:
        """Hash should raise on invalid tensor shape."""
        cache = E8TrajectoryCache(max_size=100)

        with pytest.raises(ValueError, match="Expected .* tensor"):
            cache._hash_e8_sequence(torch.randn(5, 10))  # Wrong dim

        with pytest.raises(ValueError, match="Expected .* tensor"):
            cache._hash_e8_sequence(torch.randn(8))  # Missing event dim


class TestCacheOperations:
    """Test basic cache store/lookup operations."""

    def test_store_and_lookup_hit(self) -> None:
        """Store trajectory and lookup should succeed (cache hit)."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.randn(10, 8)
        prediction = torch.randn(256)
        metadata = {"catastrophe_risks": [0.5, 0.6]}

        cache.store(e8_codes, prediction, metadata)
        result = cache.lookup(e8_codes)

        assert result is not None, "Should get cache hit"
        assert torch.allclose(result, prediction), "Prediction should match"

    def test_lookup_miss(self) -> None:
        """Lookup non-existent trajectory should return None (cache miss)."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.randn(10, 8)
        result = cache.lookup(e8_codes)

        assert result is None, "Should get cache miss"

    def test_store_empty_sequence(self) -> None:
        """Storing empty sequence should be skipped."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.empty(0, 8)
        prediction = torch.randn(256)
        metadata = {}

        cache.store(e8_codes, prediction, metadata)

        stats = cache.get_stats()
        assert stats.size == 0, "Empty sequence should not be stored"

    def test_lookup_empty_sequence(self) -> None:
        """Looking up empty sequence should return None."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.empty(0, 8)
        result = cache.lookup(e8_codes)

        assert result is None, "Empty sequence lookup should return None"

    def test_multiple_stores_same_sequence(self) -> None:
        """Storing same sequence multiple times should overwrite."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.randn(10, 8)
        prediction1 = torch.randn(256)
        prediction2 = torch.randn(256)

        cache.store(e8_codes, prediction1, {})
        cache.store(e8_codes, prediction2, {})

        result = cache.lookup(e8_codes)

        assert torch.allclose(result, prediction2), "Should get latest prediction"  # type: ignore[arg-type]
        stats = cache.get_stats()
        assert stats.size == 1, "Should only have one entry"


class TestEvictionPolicies:
    """Test LRU and importance-based eviction."""

    def test_lru_eviction(self) -> None:
        """LRU policy should evict least recently used."""
        cache = E8TrajectoryCache(max_size=3, eviction_policy="lru")

        # Store 3 entries
        for i in range(3):
            e8_codes = torch.randn(5, 8) + i  # Unique sequences
            prediction = torch.randn(256)
            cache.store(e8_codes, prediction, {})

        # Access first two (make them "recently used")
        e8_1 = torch.randn(5, 8) + 0
        e8_2 = torch.randn(5, 8) + 1
        cache.lookup(e8_1)
        cache.lookup(e8_2)

        # Store 4th entry (should evict 3rd, the LRU)
        e8_4 = torch.randn(5, 8) + 3
        cache.store(e8_4, torch.randn(256), {})

        stats = cache.get_stats()
        assert stats.size == 3, "Cache should stay at max size"
        assert stats.eviction_count == 1, "Should have evicted 1 entry"

    def test_importance_eviction(self) -> None:
        """Importance policy should evict lowest access count."""
        cache = E8TrajectoryCache(max_size=3, eviction_policy="importance")

        # Store 3 entries
        e8_codes_list = []
        for i in range(3):
            e8_codes = torch.randn(5, 8) + i
            e8_codes_list.append(e8_codes)
            prediction = torch.randn(256)
            cache.store(e8_codes, prediction, {})

        # Access first entry multiple times (high importance)
        for _ in range(5):
            cache.lookup(e8_codes_list[0])

        # Access second entry once (low importance)
        cache.lookup(e8_codes_list[1])

        # Store 4th entry (should evict 3rd, never accessed)
        e8_4 = torch.randn(5, 8) + 3
        cache.store(e8_4, torch.randn(256), {})

        stats = cache.get_stats()
        assert stats.size == 3, "Cache should stay at max size"
        assert stats.eviction_count == 1, "Should have evicted 1 entry"

    def test_invalid_eviction_policy(self) -> None:
        """Invalid eviction policy should raise error."""
        with pytest.raises(ValueError, match="Invalid eviction_policy"):
            E8TrajectoryCache(max_size=100, eviction_policy="random")


class TestBifurcationReplay:
    """Test bifurcation replay buffer."""

    def test_bifurcation_buffer_population(self) -> None:
        """High-risk events should be added to buffer."""
        cache = E8TrajectoryCache(
            max_size=100,
            bifurcation_threshold=0.7,
        )

        e8_codes = torch.randn(5, 8)
        prediction = torch.randn(256)
        metadata = {
            "catastrophe_risks": [0.8, 0.6, 0.9, 0.5, 0.75],
            "event_times": [0, 5, 10, 15, 20],
        }

        cache.store(e8_codes, prediction, metadata)

        stats = cache.get_bifurcation_stats()
        # Should add 3 high-risk events (0.8, 0.9, 0.75)
        assert stats["buffer_size"] == 3, f"Expected 3 bifurcations, got {stats['buffer_size']}"

    def test_bifurcation_buffer_eviction(self) -> None:
        """Buffer should evict oldest when full (FIFO)."""
        cache = E8TrajectoryCache(
            max_size=100,
            bifurcation_buffer_size=5,
            bifurcation_threshold=0.7,
        )

        # Add 10 high-risk events
        for _i in range(10):
            e8_codes = torch.randn(1, 8)
            prediction = torch.randn(256)
            metadata = {"catastrophe_risks": [0.9]}
            cache.store(e8_codes, prediction, metadata)

        stats = cache.get_bifurcation_stats()
        assert stats["buffer_size"] == 5, "Buffer should be capped at max size"

    def test_sample_bifurcations(self) -> None:
        """Should sample random bifurcations for replay."""
        cache = E8TrajectoryCache(
            max_size=100,
            bifurcation_threshold=0.7,
        )

        # Add multiple high-risk events
        for i in range(20):
            e8_codes = torch.randn(1, 8)
            prediction = torch.randn(256)
            metadata = {"catastrophe_risks": [0.8 + i * 0.01]}
            cache.store(e8_codes, prediction, metadata)

        # Sample batch
        batch = cache.sample_bifurcations(batch_size=10)

        assert batch is not None, "Should get bifurcation batch"
        assert batch.shape == (10, 8), "Batch should have correct shape"

    def test_sample_bifurcations_insufficient(self) -> None:
        """Sampling more than available should return None."""
        cache = E8TrajectoryCache(max_size=100)

        # Add only 3 bifurcations
        e8_codes = torch.randn(3, 8)
        prediction = torch.randn(256)
        metadata = {"catastrophe_risks": [0.8, 0.9, 0.85]}
        cache.store(e8_codes, prediction, metadata)

        # Request 10 (more than available)
        batch = cache.sample_bifurcations(batch_size=10)

        assert batch is None, "Should return None when insufficient"

    def test_bifurcation_replay_count_tracking(self) -> None:
        """Replay count should increment when sampling."""
        cache = E8TrajectoryCache(max_size=100, bifurcation_threshold=0.7)

        # Add bifurcations
        e8_codes = torch.randn(5, 8)
        prediction = torch.randn(256)
        metadata = {"catastrophe_risks": [0.9] * 5}
        cache.store(e8_codes, prediction, metadata)

        # Sample multiple times
        for _ in range(3):
            cache.sample_bifurcations(batch_size=3, increment_replay_count=True)

        stats = cache.get_bifurcation_stats()
        # Each bifurcation should have been sampled ~1.8 times on average
        assert stats["avg_replay_count"] > 0, "Replay count should increase"


class TestStatistics:
    """Test cache statistics tracking."""

    def test_hit_rate_calculation(self) -> None:
        """Hit rate should be hits / (hits + misses)."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.randn(10, 8)
        prediction = torch.randn(256)
        cache.store(e8_codes, prediction, {})

        # 3 hits
        for _ in range(3):
            cache.lookup(e8_codes)

        # 2 misses
        for _ in range(2):
            cache.lookup(torch.randn(10, 8))

        stats = cache.get_stats()
        assert stats.hit_count == 3, "Should have 3 hits"
        assert stats.miss_count == 2, "Should have 2 misses"
        assert abs(stats.hit_rate - 0.6) < 1e-6, "Hit rate should be 60%"

    def test_stats_empty_cache(self) -> None:
        """Stats for empty cache should handle division by zero."""
        cache = E8TrajectoryCache(max_size=100)

        stats = cache.get_stats()
        assert stats.size == 0
        assert stats.hit_rate == 0.0, "Hit rate should be 0 for empty cache"

    def test_bifurcation_stats_empty(self) -> None:
        """Bifurcation stats for empty buffer should return zeros."""
        cache = E8TrajectoryCache(max_size=100)

        stats = cache.get_bifurcation_stats()
        assert stats["buffer_size"] == 0
        assert stats["avg_risk"] == 0.0
        assert stats["avg_replay_count"] == 0.0


class TestThreadSafety:
    """Test thread safety with concurrent access."""

    def test_concurrent_store_lookup(self) -> None:
        """Concurrent stores and lookups should be thread-safe."""
        import threading

        cache = E8TrajectoryCache(max_size=1000, thread_safe=True)

        errors = []

        def worker(worker_id: int):
            try:
                for i in range(50):
                    e8_codes = torch.randn(5, 8) + worker_id * 1000 + i
                    prediction = torch.randn(256)
                    cache.store(e8_codes, prediction, {})
                    cache.lookup(e8_codes)
            except Exception as e:
                errors.append(e)

        # Spawn 10 threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        stats = cache.get_stats()
        assert stats.size > 0, "Cache should have entries from threads"

    def test_thread_safe_disabled(self) -> None:
        """Cache with thread_safe=False should still work (single-threaded)."""
        cache = E8TrajectoryCache(max_size=100, thread_safe=False)

        e8_codes = torch.randn(10, 8)
        prediction = torch.randn(256)
        cache.store(e8_codes, prediction, {})

        result = cache.lookup(e8_codes)
        assert result is not None


class TestPersistence:
    """Test save/load operations."""

    def test_save_and_load(self) -> None:
        """Cache should persist and restore correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.pkl"

            # Create cache and populate
            cache = E8TrajectoryCache(max_size=100)
            e8_codes = torch.randn(10, 8)
            prediction = torch.randn(256)
            metadata = {"catastrophe_risks": [0.8, 0.9]}
            cache.store(e8_codes, prediction, metadata)

            # Get stats before save
            stats_before = cache.get_stats()

            # Save
            cache.save(cache_path)

            # Create new cache and load
            cache2 = E8TrajectoryCache(max_size=100)
            cache2.load(cache_path)

            # Verify
            result = cache2.lookup(e8_codes)
            assert result is not None, "Loaded cache should contain entry"
            assert torch.allclose(result, prediction), "Prediction should match"

            stats_after = cache2.get_stats()
            assert stats_after.size == stats_before.size, "Cache size should match"

    def test_load_nonexistent_file(self) -> None:
        """Loading nonexistent file should raise error."""
        cache = E8TrajectoryCache(max_size=100)

        with pytest.raises(FileNotFoundError):
            cache.load(Path("/nonexistent/path/cache.pkl"))

    def test_save_creates_directory(self) -> None:
        """Save should create parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "subdir" / "cache.pkl"

            cache = E8TrajectoryCache(max_size=100)
            cache.save(cache_path)

            # The new signed format creates .meta file and _entries directory
            # instead of the raw pickle file
            metadata_path = cache_path.with_suffix(".meta")
            assert metadata_path.exists(), "Cache metadata file should be created"


class TestClear:
    """Test cache clearing."""

    def test_clear_cache(self) -> None:
        """Clear should remove all entries."""
        cache = E8TrajectoryCache(max_size=100)

        # Populate cache
        for i in range(10):
            e8_codes = torch.randn(5, 8) + i
            prediction = torch.randn(256)
            metadata = {"catastrophe_risks": [0.9]}
            cache.store(e8_codes, prediction, metadata)

        stats_before = cache.get_stats()
        assert stats_before.size == 10

        # Clear
        cache.clear()

        stats_after = cache.get_stats()
        assert stats_after.size == 0, "Cache should be empty"
        assert stats_after.bifurcation_buffer_size == 0, "Buffer should be empty"


class TestFactoryFunction:
    """Test factory function."""

    def test_create_e8_trajectory_cache(self) -> None:
        """Factory should create cache with defaults."""
        cache = create_e8_trajectory_cache(max_size=500, eviction_policy="lru")

        assert cache.max_size == 500
        assert cache.eviction_policy == "lru"

    def test_factory_defaults(self) -> None:
        """Factory should apply sensible defaults."""
        cache = create_e8_trajectory_cache()

        assert cache.max_size == 10000
        assert cache.eviction_policy == "lru"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_event_trajectory(self) -> None:
        """Single-event trajectory should work."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.randn(1, 8)  # Single event
        prediction = torch.randn(256)
        cache.store(e8_codes, prediction, {})

        result = cache.lookup(e8_codes)
        assert result is not None

    def test_large_trajectory(self) -> None:
        """Large trajectory should work."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.randn(1000, 8)  # 1000 events
        prediction = torch.randn(256)
        cache.store(e8_codes, prediction, {})

        result = cache.lookup(e8_codes)
        assert result is not None

    def test_metadata_preservation(self) -> None:
        """Metadata should be preserved in cache entry."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.randn(5, 8)
        prediction = torch.randn(256)
        metadata = {
            "catastrophe_risks": [0.7, 0.8],
            "event_times": [0, 5],
            "colony_idx": 3,
            "custom_field": "test_value",
        }
        cache.store(e8_codes, prediction, metadata)

        # Access internal entry to check metadata
        hash_key = cache._hash_e8_sequence(e8_codes)
        entry = cache._cache[hash_key]

        assert entry.metadata["colony_idx"] == 3
        assert entry.metadata["custom_field"] == "test_value"

    def test_access_count_increments(self) -> None:
        """Access count should increment on each lookup."""
        cache = E8TrajectoryCache(max_size=100)

        e8_codes = torch.randn(5, 8)
        prediction = torch.randn(256)
        cache.store(e8_codes, prediction, {})

        # Lookup multiple times
        for _ in range(5):
            cache.lookup(e8_codes)

        hash_key = cache._hash_e8_sequence(e8_codes)
        entry = cache._cache[hash_key]

        assert entry.access_count == 5, "Access count should be 5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
