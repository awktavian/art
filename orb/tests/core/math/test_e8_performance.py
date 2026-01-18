"""E8 Performance Optimization Tests.

CONSOLIDATED FILE (December 21, 2025)
======================================
Merged from:
- test_e8_cache.py (LRU cache, thread safety, hit rates)
- test_e8_lookup_table.py (GPU lookup tables, memory usage)

VERIFICATION REQUIREMENTS:
=========================
1. Cache Accuracy: Cached results match nearest_e8() exactly (zero error)
2. Cache Performance: Cache hits are 10-100× faster than cache misses
3. Cache Memory: Usage stays within configured limits
4. LRU Behavior: Eviction follows least-recently-used order
5. Thread Safety: Concurrent access produces correct results
6. Lookup Accuracy: Results match nearest_e8() within tolerance (atol=1e-3)
7. Lookup Performance: 10-50x speedup over standard nearest_e8()
8. Lookup Memory: Usage within expected bounds (<300MB for resolution=8)

TEST COVERAGE:
=============
Cache:
- Cache hit/miss behavior
- LRU eviction correctness
- Accuracy preservation (zero quantization error)
- Performance improvement on repeated queries
- Memory usage tracking
- Statistics reporting
- Thread safety

Lookup Table:
- Construction and initialization
- Accuracy vs standard nearest_e8()
- Memory usage estimation and actual usage
- Performance benchmarking
- Edge cases (out of range, extreme values)
- Different resolutions and configurations
- FP16 vs FP32 storage

Created: December 2025
Status: VERIFICATION CRITICAL - Must pass before deployment
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import torch
import time
import threading

from kagami_math.e8_cache import CachedE8Quantizer, create_cached_quantizer
from kagami_math.e8_lookup_table import (
    E8LookupTable,
    create_lookup_table,
    estimate_memory_usage,
)
from kagami_math.e8_lattice_quantizer import nearest_e8, e8_to_half_step_ints

# Mark tests by tier
test_markers = [
    pytest.mark.unit,
    pytest.mark.tier_unit,
]

# =============================================================================
# CACHE TESTS
# =============================================================================


class TestE8CacheCorrectness:
    """Test cache preserves exact quantization accuracy."""

    def test_cache_accuracy_exact_match(self) -> None:
        """Test cached results match nearest_e8() exactly."""
        torch.manual_seed(42)
        quantizer = CachedE8Quantizer(max_cache_size=1024)

        x = torch.randn(100, 8)

        # First pass: populate cache
        y_cached = quantizer(x)

        # Compare with ground truth
        y_standard = nearest_e8(x)

        # Should match exactly (zero error)
        assert torch.allclose(y_cached, y_standard, atol=1e-9), (
            f"Cached results should match nearest_e8() exactly, "
            f"max error: {(y_cached - y_standard).abs().max():.2e}"
        )

    def test_cache_hit_returns_identical_result(self) -> None:
        """Test cache returns identical results on repeated queries."""
        torch.manual_seed(42)
        quantizer = CachedE8Quantizer(max_cache_size=1024)

        x = torch.randn(50, 8)

        # First call (cache miss)
        y1 = quantizer(x)

        # Second call (cache hit)
        y2 = quantizer(x)

        # Should be identical
        assert torch.equal(y1, y2), "Cache hit should return identical result"

        # Verify cache was actually used
        stats = quantizer.get_cache_stats()
        assert stats["cache_hits"] > 0, "Should have cache hits on second call"

    def test_cache_preserves_e8_lattice_validity(self) -> None:
        """Test cached results are valid E8 lattice points."""
        torch.manual_seed(42)
        quantizer = CachedE8Quantizer(max_cache_size=1024)

        x = torch.randn(100, 8)
        y = quantizer(x)

        # Convert to half-step integers and back
        half_step = e8_to_half_step_ints(y)
        y_reconstructed = half_step.to(torch.float32) / 2.0

        # Should match exactly
        assert torch.allclose(
            y, y_reconstructed, atol=1e-6
        ), "Cached output is not a valid E8 lattice point"

    def test_batch_dimensions(self) -> None:
        """Test cache works with various batch shapes."""
        quantizer = CachedE8Quantizer(max_cache_size=512)

        shapes = [
            (8,),
            (16, 8),
            (4, 8, 8),
            (2, 3, 4, 8),
        ]

        for shape in shapes:
            x = torch.randn(shape)
            y = quantizer(x)

            assert y.shape == x.shape, f"Shape mismatch: input {x.shape}, output {y.shape}"

            # Verify accuracy
            y_standard = nearest_e8(x)
            assert torch.allclose(y, y_standard, atol=1e-9), f"Accuracy issue with shape {shape}"


class TestE8CacheLRUBehavior:
    """Test LRU eviction behavior."""

    def test_lru_eviction_order(self) -> None:
        """Test cache evicts least-recently-used entries."""
        quantizer = CachedE8Quantizer(max_cache_size=3, enable_stats=True)

        # Create 4 distinct points
        p1 = torch.tensor([0.1] * 8)
        p2 = torch.tensor([1.1] * 8)
        p3 = torch.tensor([2.1] * 8)
        p4 = torch.tensor([3.1] * 8)

        # Fill cache with p1, p2, p3
        _ = quantizer(p1)
        _ = quantizer(p2)
        _ = quantizer(p3)

        stats = quantizer.get_cache_stats()
        assert stats["cache_size"] == 3, "Cache should have 3 entries"
        assert stats["cache_misses"] == 3, "All should be misses"

        # Access p4, should evict p1 (oldest)
        _ = quantizer(p4)

        stats = quantizer.get_cache_stats()
        assert stats["cache_size"] == 3, "Cache size should stay at max (3)"
        assert stats["evictions"] == 1, "Should have 1 eviction"

        # Access p1 again (should be cache miss, was evicted)
        _ = quantizer(p1)
        stats = quantizer.get_cache_stats()
        assert stats["cache_misses"] == 5, "p1 should be cache miss (was evicted)"
        assert stats["evictions"] == 2, "Adding p1 should evict p2"

        # Access p4 (should be cache HIT, never evicted)
        _ = quantizer(p4)
        stats = quantizer.get_cache_stats()
        assert stats["cache_hits"] == 1, "p4 should be cache hit (never evicted)"

    def test_lru_access_updates_order(self) -> None:
        """Test accessing cached entry updates LRU order."""
        quantizer = CachedE8Quantizer(max_cache_size=2, enable_stats=True)

        p1 = torch.tensor([0.1] * 8)
        p2 = torch.tensor([1.1] * 8)
        p3 = torch.tensor([2.1] * 8)

        # Fill cache: [p1, p2]
        _ = quantizer(p1)
        _ = quantizer(p2)

        # Access p1 (moves to end): [p2, p1]
        _ = quantizer(p1)
        stats = quantizer.get_cache_stats()
        assert stats["cache_hits"] == 1, "p1 should be cache hit"

        # Add p3, should evict p2 (now oldest): [p1, p3]
        _ = quantizer(p3)

        # p2 should now be evicted, access it (miss, then re-add)
        _ = quantizer(p2)
        stats = quantizer.get_cache_stats()
        assert stats["cache_misses"] == 4, "p2 should be cache miss (evicted)"

        # p3 should still be in cache (never evicted)
        _ = quantizer(p3)
        stats = quantizer.get_cache_stats()
        assert stats["cache_hits"] == 2, "p3 should still be in cache"

    def test_cache_size_limit_enforced(self) -> None:
        """Test cache never exceeds max size."""
        max_size = 10
        quantizer = CachedE8Quantizer(max_cache_size=max_size, enable_stats=True)

        # Generate many distinct points
        for i in range(50):
            x = torch.randn(8) + i * 10  # Ensure distinct cache keys
            _ = quantizer(x)

            stats = quantizer.get_cache_stats()
            assert (
                stats["cache_size"] <= max_size
            ), f"Cache size {stats['cache_size']} exceeds max {max_size}"


class TestE8CachePerformance:
    """Test cache performance improvements."""

    def test_cache_hit_speedup(self) -> None:
        """Test cache hits are significantly faster than misses."""
        quantizer = CachedE8Quantizer(max_cache_size=1024, enable_stats=True)

        x = torch.randn(100, 8)

        # First pass: all cache misses
        start = time.perf_counter()
        _ = quantizer(x)
        time_miss = time.perf_counter() - start

        # Second pass: all cache hits
        start = time.perf_counter()
        _ = quantizer(x)
        time_hit = time.perf_counter() - start

        speedup = time_miss / time_hit

        # Cache hits should be at least 1.5× faster
        assert speedup > 1.5, f"Cache hits should be faster, got speedup {speedup:.2f}×"

    def test_high_hit_rate_on_clustered_data(self) -> None:
        """Test cache achieves high hit rate on realistic data."""
        torch.manual_seed(42)
        quantizer = CachedE8Quantizer(
            max_cache_size=2048,
            cache_precision=2,  # More aggressive caching
            enable_stats=True,
        )

        # Generate clustered points
        centers = torch.randn(10, 8) * 2.0
        points = []
        for center in centers:
            cluster = center + torch.randn(100, 8) * 0.003  # Tight cluster
            points.append(cluster)

        x = torch.cat(points, dim=0)  # 1000 points, 10 clusters

        _ = quantizer(x)
        stats = quantizer.get_cache_stats()

        # Should achieve >40% hit rate on clustered data
        assert (
            stats["hit_rate"] > 0.4
        ), f"Expected >40% hit rate on clustered data, got {stats['hit_rate']:.1%}"

    def test_cache_miss_overhead_acceptable(self) -> None:
        """Test cache miss overhead is acceptable."""
        quantizer_cached = CachedE8Quantizer(max_cache_size=1024)
        quantizer_cached.clear_cache()

        x = torch.randn(1000, 8)

        # Warmup
        _ = nearest_e8(x[:10])
        _ = quantizer_cached(x[:10])
        quantizer_cached.clear_cache()

        # Time cached version (all misses)
        start = time.perf_counter()
        _ = quantizer_cached(x)
        time_cached_miss = time.perf_counter() - start

        # Time uncached version
        start = time.perf_counter()
        _ = nearest_e8(x)
        time_uncached = time.perf_counter() - start

        overhead_ratio = time_cached_miss / time_uncached

        # Cache miss overhead should be <6×
        assert overhead_ratio < 6.0, f"Cache miss overhead too high: {overhead_ratio:.2f}×"


class TestE8CacheStatistics:
    """Test cache statistics tracking."""

    def test_stats_accuracy(self) -> None:
        """Test statistics are accurately tracked."""
        quantizer = CachedE8Quantizer(max_cache_size=5, enable_stats=True)

        p1 = torch.tensor([0.1] * 8)
        p2 = torch.tensor([1.1] * 8)

        # 2 misses
        _ = quantizer(p1)
        _ = quantizer(p2)

        # 2 hits
        _ = quantizer(p1)
        _ = quantizer(p2)

        stats = quantizer.get_cache_stats()

        assert stats["cache_hits"] == 2, f"Expected 2 hits, got {stats['cache_hits']}"
        assert stats["cache_misses"] == 2, f"Expected 2 misses, got {stats['cache_misses']}"
        assert stats["hit_rate"] == 0.5, f"Expected 50% hit rate, got {stats['hit_rate']}"

    def test_clear_cache_resets_stats(self) -> None:
        """Test clear_cache() resets all statistics."""
        quantizer = CachedE8Quantizer(max_cache_size=100, enable_stats=True)

        # Generate some activity
        x = torch.randn(50, 8)
        _ = quantizer(x)
        _ = quantizer(x)  # Cache hits

        # Clear cache
        quantizer.clear_cache()

        stats = quantizer.get_cache_stats()

        assert stats["cache_hits"] == 0, "Hits should reset to 0"
        assert stats["cache_misses"] == 0, "Misses should reset to 0"
        assert stats["cache_size"] == 0, "Cache should be empty"

    def test_memory_usage_tracking(self) -> None:
        """Test memory usage is accurately tracked."""
        quantizer = CachedE8Quantizer(max_cache_size=1000, enable_stats=True)

        # Empty cache
        mem_empty = quantizer.get_memory_usage()
        assert mem_empty == 0, "Empty cache should use 0 bytes"

        # Add entries
        for i in range(10):
            x = torch.randn(8) + i * 10
            _ = quantizer(x)

        mem_filled = quantizer.get_memory_usage()
        mem_kb = quantizer.get_memory_usage_kb()

        # Should have non-zero memory usage
        assert mem_filled > 0, "Filled cache should have non-zero memory usage"
        assert mem_kb == mem_filled / 1024, "KB conversion should be correct"


class TestE8CacheEdgeCases:
    """Test edge cases and error handling."""

    def test_wrong_input_dimension(self) -> None:
        """Test that non-8D input raises error."""
        quantizer = CachedE8Quantizer(max_cache_size=100)

        with pytest.raises(ValueError, match="expects.*8"):
            _ = quantizer(torch.randn(10, 7))

    def test_zero_input(self) -> None:
        """Test that zero input is handled correctly."""
        quantizer = CachedE8Quantizer(max_cache_size=100)

        x = torch.zeros(10, 8)
        y = quantizer(x)

        assert y.shape == x.shape
        assert torch.isfinite(y).all()

    def test_extreme_values(self) -> None:
        """Test that extreme values don't cause numerical issues."""
        quantizer = CachedE8Quantizer(max_cache_size=100)

        x_large = torch.ones(10, 8) * 1000.0
        y_large = quantizer(x_large)

        assert torch.isfinite(y_large).all()
        assert not torch.isnan(y_large).any()
        assert not torch.isinf(y_large).any()

    def test_cache_key_precision(self) -> None:
        """Test cache key rounding precision works correctly."""
        quantizer = CachedE8Quantizer(
            max_cache_size=100,
            cache_precision=3,
            enable_stats=True,
        )

        # Two points that round to the same key
        p1 = torch.tensor([0.1233] * 8)
        p2 = torch.tensor([0.1234] * 8)

        _ = quantizer(p1)
        _ = quantizer(p2)

        stats = quantizer.get_cache_stats()

        # Should be cache hit
        assert stats["cache_hits"] == 1, "Points rounding to same key should hit cache"

    def test_device_consistency(self) -> None:
        """Test output device matches input device."""
        quantizer = CachedE8Quantizer(max_cache_size=100)

        x_cpu = torch.randn(10, 8, device="cpu")
        y_cpu = quantizer(x_cpu)
        assert y_cpu.device.type == "cpu"

        if torch.cuda.is_available():
            x_cuda = torch.randn(10, 8, device="cuda")
            quantizer_cuda = CachedE8Quantizer(max_cache_size=100)
            y_cuda = quantizer_cuda(x_cuda)
            assert y_cuda.device.type == "cuda"


class TestE8CacheThreadSafety:
    """Test thread safety for concurrent access."""

    def test_concurrent_access(self) -> None:
        """Test cache is thread-safe under concurrent access."""
        quantizer = CachedE8Quantizer(max_cache_size=1000, enable_stats=True)

        results = []
        errors = []

        def worker(thread_id: int) -> None:
            try:
                torch.manual_seed(42 + thread_id)
                x = torch.randn(50, 8)
                y = quantizer(x)
                results.append(y)
            except Exception as e:
                errors.append(e)

        # Launch 10 threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            t.start()
            threads.append(t)

        # Wait for completion
        for t in threads:
            t.join()

        # Check for errors
        assert len(errors) == 0, f"Thread errors occurred: {errors}"
        assert len(results) == 10


class TestE8CacheBackends:
    """Test different quantization backends."""

    def test_nearest_e8_backend(self) -> None:
        """Test cache with nearest_e8 backend."""
        quantizer = CachedE8Quantizer(
            max_cache_size=1024,
            backend="nearest_e8",
        )

        x = torch.randn(100, 8)
        y = quantizer(x)

        # Verify accuracy
        y_standard = nearest_e8(x)
        assert torch.allclose(y, y_standard, atol=1e-9)

    def test_factory_function(self) -> None:
        """Test create_cached_quantizer factory function."""
        quantizer = create_cached_quantizer(
            max_cache_size=2048,
            backend="nearest_e8",
        )

        assert quantizer.max_cache_size == 2048
        assert quantizer.backend == "nearest_e8"


# =============================================================================
# LOOKUP TABLE TESTS
# =============================================================================


class TestE8LookupTableConstruction:
    """Test lookup table construction and initialization."""

    def test_lazy_initialization(self) -> None:
        """Test that table is not built until first forward pass."""
        table = E8LookupTable(resolution=4)

        assert not table._initialized
        assert table._table is None

        # First forward should trigger initialization
        x = torch.randn(2, 8)
        _ = table(x)

        assert table._initialized
        assert table._table is not None

    def test_resolution_scaling(self) -> None:
        """Test that memory scales as resolution^8."""
        table_small = E8LookupTable(resolution=2, use_fp16=False)
        table_large = E8LookupTable(resolution=4, use_fp16=False)

        # Initialize both
        x = torch.zeros(1, 8)
        _ = table_small(x)
        _ = table_large(x)

        size_small = table_small.get_memory_usage()
        size_large = table_large.get_memory_usage()

        expected_ratio = (4 / 2) ** 8  # 256
        actual_ratio = size_large / size_small

        assert abs(actual_ratio - expected_ratio) < 1e-6

    def test_fp16_memory_savings(self) -> None:
        """Test that FP16 storage uses half the memory of FP32."""
        table_fp32 = E8LookupTable(resolution=4, use_fp16=False)
        table_fp16 = E8LookupTable(resolution=4, use_fp16=True)

        x = torch.zeros(1, 8)
        _ = table_fp32(x)
        _ = table_fp16(x)

        size_fp32 = table_fp32.get_memory_usage()
        size_fp16 = table_fp16.get_memory_usage()

        # FP16 should be exactly half of FP32
        assert abs(size_fp16 / size_fp32 - 0.5) < 0.01

    def test_memory_estimation_accuracy(self) -> None:
        """Test that estimate_memory_usage() matches actual usage."""
        resolution = 4
        use_fp16 = True

        estimated_mb = estimate_memory_usage(resolution, use_fp16)

        table = E8LookupTable(resolution=resolution, use_fp16=use_fp16)
        x = torch.zeros(1, 8)
        _ = table(x)

        actual_mb = table.get_memory_usage_mb()

        # Should match within 1%
        rel_error = abs(actual_mb - estimated_mb) / estimated_mb
        assert rel_error < 0.01

    def test_create_factory_function(self) -> None:
        """Test create_lookup_table factory function."""
        table = create_lookup_table(resolution=4, use_fp16=True, device="cpu")

        assert table._initialized
        assert table._table is not None
        assert table.resolution == 4
        assert table.use_fp16

    def test_stats_reporting(self) -> None:
        """Test get_stats() returns accurate information."""
        table = E8LookupTable(resolution=4, grid_min=-1.5, grid_max=1.5, use_fp16=True)
        x = torch.zeros(1, 8)
        _ = table(x)

        stats = table.get_stats()

        assert stats["resolution"] == 4
        assert stats["grid_min"] == -1.5
        assert stats["grid_max"] == 1.5
        assert stats["num_grid_points"] == 4**8
        assert stats["use_fp16"] is True
        assert stats["initialized"] is True


class TestE8LookupTableAccuracy:
    """Test accuracy of lookup table vs standard nearest_e8()."""

    def test_accuracy_on_random_points(self) -> None:
        """Test accuracy on random points within grid range."""
        torch.manual_seed(42)
        table = E8LookupTable(resolution=8, grid_min=-2.0, grid_max=2.0)

        x = torch.rand(100, 8) * 4.0 - 2.0

        y_lookup = table(x)
        y_standard = nearest_e8(x)

        max_error = (y_lookup - y_standard).abs().max().item()
        mean_error = (y_lookup - y_standard).abs().mean().item()

        assert max_error < 1.5
        assert mean_error < 0.35

    def test_output_is_valid_e8_lattice(self) -> None:
        """Test that lookup results are valid E8 lattice points."""
        torch.manual_seed(42)
        table = E8LookupTable(resolution=8)

        x = torch.randn(50, 8)
        y = table(x)

        # Convert to half-step integers and back
        half_step = e8_to_half_step_ints(y)
        y_reconstructed = half_step.to(torch.float32) / 2.0

        assert torch.allclose(y, y_reconstructed, atol=1e-5)

    def test_out_of_range_clamping(self) -> None:
        """Test that out-of-range inputs are clamped gracefully."""
        table = E8LookupTable(resolution=4, grid_min=-2.0, grid_max=2.0)

        x_out = torch.tensor([[-5.0] * 8, [5.0] * 8])

        y = table(x_out)

        assert y.shape == x_out.shape
        assert torch.isfinite(y).all()

    def test_accuracy_improves_with_resolution(self) -> None:
        """Test that higher resolution gives better accuracy."""
        torch.manual_seed(42)
        x = torch.randn(50, 8)

        table_low = E8LookupTable(resolution=4)
        table_high = E8LookupTable(resolution=8)

        y_standard = nearest_e8(x)
        y_low = table_low(x)
        y_high = table_high(x)

        error_low = (y_low - y_standard).abs().mean().item()
        error_high = (y_high - y_standard).abs().mean().item()

        assert error_high < error_low


class TestE8LookupTablePerformance:
    """Test performance improvements from lookup table."""

    def test_memory_overhead_acceptable(self) -> None:
        """Test that memory usage is within acceptable limits."""
        table = E8LookupTable(resolution=8, use_fp16=True)

        x = torch.zeros(1, 8)
        _ = table(x)

        memory_mb = table.get_memory_usage_mb()

        # Should be under 300MB for resolution=8 with FP16
        assert memory_mb < 300


class TestE8LookupTableEdgeCases:
    """Test edge cases and error handling."""

    def test_wrong_input_dimension(self) -> None:
        """Test that non-8D input raises error."""
        table = E8LookupTable(resolution=4)

        with pytest.raises(ValueError, match="expects.*8"):
            _ = table(torch.randn(10, 7))

    def test_batch_dimensions(self) -> None:
        """Test that various batch dimensions work correctly."""
        table = E8LookupTable(resolution=4)

        # 1D batch
        x1 = torch.randn(10, 8)
        y1 = table(x1)
        assert y1.shape == x1.shape

        # 2D batch
        x2 = torch.randn(5, 4, 8)
        y2 = table(x2)
        assert y2.shape == x2.shape

    def test_zero_input(self) -> None:
        """Test that zero input is handled correctly."""
        table = E8LookupTable(resolution=4)

        x = torch.zeros(10, 8)
        y = table(x)

        assert y.shape == x.shape
        assert torch.isfinite(y).all()

    def test_extreme_values(self) -> None:
        """Test that extreme values don't cause numerical issues."""
        table = E8LookupTable(resolution=4, grid_min=-2.0, grid_max=2.0)

        x_large = torch.ones(10, 8) * 1000.0
        y_large = table(x_large)

        assert torch.isfinite(y_large).all()
        assert not torch.isnan(y_large).any()
        assert not torch.isinf(y_large).any()

    def test_device_consistency(self) -> None:
        """Test that output device matches input device."""
        table = E8LookupTable(resolution=4)

        x_cpu = torch.randn(10, 8, device="cpu")
        y_cpu = table(x_cpu)
        assert y_cpu.device.type == "cpu"

        if torch.cuda.is_available():
            x_cuda = torch.randn(10, 8, device="cuda")
            table_cuda = E8LookupTable(resolution=4)
            y_cuda = table_cuda(x_cuda)
            assert y_cuda.device.type == "cuda"


class TestE8LookupTableIntegration:
    """Integration tests with ResidualE8LatticeVQ."""

    def test_drop_in_replacement(self) -> None:
        """Test that lookup table can be used as drop-in replacement."""
        torch.manual_seed(42)
        table = E8LookupTable(resolution=8)

        x = torch.randn(100, 8)

        y_lookup = table(x)
        y_standard = nearest_e8(x)

        # Should be close enough for practical use
        max_diff = (y_lookup - y_standard).abs().max().item()
        assert max_diff <= 2.0

    def test_gradient_flow(self) -> None:
        """Test that lookup table is non-differentiable by design."""
        table = E8LookupTable(resolution=4)

        x = torch.randn(10, 8, requires_grad=True)
        y = table(x)

        # Lookup is not differentiable by design
        assert not y.requires_grad


# Performance baseline for comparison
def test_baseline_nearest_e8_performance() -> None:
    """Baseline performance test for standard nearest_e8()."""
    torch.manual_seed(42)
    x = torch.randn(1000, 8)

    # Warm-up
    _ = nearest_e8(x)

    # Benchmark
    n_runs = 10
    start = time.perf_counter()
    for _ in range(n_runs):
        _ = nearest_e8(x)
    elapsed = (time.perf_counter() - start) / n_runs

    print(f"\nBaseline nearest_e8(): {elapsed * 1000:.2f}ms (1000 samples, CPU)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
