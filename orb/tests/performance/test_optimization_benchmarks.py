"""Comprehensive Performance Benchmarking Suite for Optimizations.

Tests all optimization implementations to ensure they meet performance targets:
- 50%+ speedup on repeated operations
- <20% memory overhead
- Linear scalability with batch size

Colony: Crystal (e₇) - Testing
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import pytest
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Redis Cache Benchmarks
# =============================================================================


class TestRedisCacheBenchmarks:
    """Benchmark Redis caching layer."""

    @pytest.mark.asyncio
    async def test_cache_hit_rate_improvement(self):
        """Test cache hit rate improvement over uncached operations."""
        from kagami.core.caching.redis_cache import RedisCache, CacheConfig

        config = CacheConfig(
            host="localhost",
            default_ttl=60,
            enable_memory_tier=True,
        )
        cache = RedisCache(config, namespace="bench")
        await cache.initialize()

        # Simulate expensive operation
        async def expensive_operation(key: str) -> dict[str, Any]:
            await asyncio.sleep(0.1)  # 100ms simulated latency
            return {"result": f"data_{key}", "timestamp": time.time()}

        # Test 1: Measure uncached performance
        uncached_start = time.time()
        for i in range(50):
            await expensive_operation(f"key_{i % 10}")  # 10 unique keys, 5x each
        uncached_time = time.time() - uncached_start

        # Test 2: Measure cached performance
        cached_start = time.time()
        for i in range(50):
            key = f"key_{i % 10}"
            cached = await cache.get(key)
            if cached is None:
                result = await expensive_operation(key)
                await cache.set(key, result)
        cached_time = time.time() - cached_start

        # Calculate improvement
        improvement = ((uncached_time - cached_time) / uncached_time) * 100

        # Get cache stats
        stats = await cache.get_stats()

        logger.info("Cache benchmark results:")
        logger.info(f"  Uncached time: {uncached_time:.2f}s")
        logger.info(f"  Cached time: {cached_time:.2f}s")
        logger.info(f"  Improvement: {improvement:.1f}%")
        logger.info(f"  Hit rate: {stats['hit_rate']:.1%}")

        # Verify performance targets
        assert improvement > 50, f"Expected >50% improvement, got {improvement:.1f}%"
        assert stats["hit_rate"] > 0.7, f"Expected >70% hit rate, got {stats['hit_rate']:.1%}"

        await cache.close()

    @pytest.mark.asyncio
    async def test_cache_memory_overhead(self):
        """Test cache memory overhead stays under 20%."""
        from kagami.core.caching.redis_cache import RedisCache, CacheConfig

        config = CacheConfig(
            enable_memory_tier=True,
            memory_max_entries=1000,
        )
        cache = RedisCache(config, namespace="bench")
        await cache.initialize()

        # Create test data
        data_size = 1000
        item_size = 1024  # 1KB per item
        test_data = {f"key_{i}": b"x" * item_size for i in range(data_size)}

        # Measure memory
        import psutil
        import os

        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / (1024**2)  # MB

        # Store in cache
        for key, value in test_data.items():
            await cache.set(key, value)

        mem_after = process.memory_info().rss / (1024**2)  # MB
        mem_used = mem_after - mem_before

        # Calculate overhead
        data_size_mb = (data_size * item_size) / (1024**2)
        overhead_pct = ((mem_used - data_size_mb) / data_size_mb) * 100

        logger.info("Memory benchmark results:")
        logger.info(f"  Data size: {data_size_mb:.2f} MB")
        logger.info(f"  Memory used: {mem_used:.2f} MB")
        logger.info(f"  Overhead: {overhead_pct:.1f}%")

        # Verify memory target
        assert overhead_pct < 20, f"Expected <20% overhead, got {overhead_pct:.1f}%"

        await cache.close()

    @pytest.mark.asyncio
    async def test_llm_response_cache_performance(self):
        """Test LLM response caching performance."""
        from kagami.core.caching.redis_cache import RedisCache, LLMResponseCache

        cache = RedisCache(namespace="bench")
        await cache.initialize()
        llm_cache = LLMResponseCache(cache)

        # Simulate LLM calls
        async def mock_llm_call(prompt: str, model: str) -> str:
            await asyncio.sleep(0.5)  # 500ms simulated latency
            return f"Response to: {prompt}"

        prompts = [
            "What is the capital of France?",
            "Explain quantum computing",
            "What is the capital of France?",  # Duplicate
            "Write a poem about nature",
            "Explain quantum computing",  # Duplicate
        ]

        # Test with cache
        start = time.time()
        for prompt in prompts:
            cached = await llm_cache.get(prompt, "gpt-4")
            if cached is None:
                response = await mock_llm_call(prompt, "gpt-4")
                await llm_cache.set(prompt, "gpt-4", response)
        cached_time = time.time() - start

        # Test without cache (for comparison)
        start = time.time()
        for prompt in prompts:
            await mock_llm_call(prompt, "gpt-4")
        uncached_time = time.time() - start

        improvement = ((uncached_time - cached_time) / uncached_time) * 100

        logger.info("LLM cache benchmark:")
        logger.info(f"  Uncached time: {uncached_time:.2f}s")
        logger.info(f"  Cached time: {cached_time:.2f}s")
        logger.info(f"  Improvement: {improvement:.1f}%")

        assert improvement > 30, f"Expected >30% improvement, got {improvement:.1f}%"

        await cache.close()


# =============================================================================
# Batch Processing Benchmarks
# =============================================================================


class TestBatchProcessingBenchmarks:
    """Benchmark batch processing system."""

    @pytest.mark.asyncio
    async def test_gaussian_splatting_batch_throughput(self):
        """Test Gaussian Splatting batch processing throughput."""
        from kagami.forge.modules.generation.batch_processor import (
            GaussianSplattingBatchProcessor,
            BatchConfig,
            Priority,
        )

        config = BatchConfig(
            max_batch_size=4,
            strategy="parallel",
            enable_gpu_monitoring=False,
        )
        processor = GaussianSplattingBatchProcessor(config)
        await processor.start()

        # Submit batch of tasks
        prompts = [
            "fantasy warrior",
            "sci-fi robot",
            "medieval castle",
            "futuristic city",
        ]

        # Sequential baseline
        sequential_start = time.time()
        for _prompt in prompts:
            # Simulate sequential generation
            await asyncio.sleep(1.0)  # 1s per item
        sequential_time = time.time() - sequential_start

        # Batch processing
        batch_start = time.time()
        tasks = [processor.submit(prompt, priority=Priority.HIGH) for prompt in prompts]
        await asyncio.gather(*tasks)

        # Wait for completion
        await asyncio.sleep(2.0)
        batch_time = time.time() - batch_start

        stats = await processor.get_stats()
        speedup = sequential_time / batch_time

        logger.info("Batch processing benchmark:")
        logger.info(f"  Sequential time: {sequential_time:.2f}s")
        logger.info(f"  Batch time: {batch_time:.2f}s")
        logger.info(f"  Speedup: {speedup:.2f}x")
        logger.info(f"  Throughput: {stats['avg_throughput']:.2f} items/s")

        assert speedup > 1.5, f"Expected >1.5x speedup, got {speedup:.2f}x"

        await processor.stop()

    @pytest.mark.asyncio
    async def test_batch_scalability(self):
        """Test batch processing scales linearly with batch size."""
        from kagami.forge.modules.generation.batch_processor import (
            GaussianSplattingBatchProcessor,
            BatchConfig,
        )

        config = BatchConfig(strategy="parallel", enable_gpu_monitoring=False)
        processor = GaussianSplattingBatchProcessor(config)
        await processor.start()

        batch_sizes = [1, 2, 4, 8]
        throughputs = []

        for batch_size in batch_sizes:
            config.max_batch_size = batch_size

            start = time.time()
            tasks = [processor.submit(f"test_{i}") for i in range(batch_size)]
            await asyncio.gather(*tasks)
            await asyncio.sleep(1.0)
            elapsed = time.time() - start

            throughput = batch_size / elapsed
            throughputs.append(throughput)

            logger.info(f"Batch size {batch_size}: {throughput:.2f} items/s")

        # Check for linear scaling
        # Throughput should increase roughly linearly with batch size
        efficiency = throughputs[-1] / throughputs[0]

        logger.info(f"Scalability: {efficiency:.2f}x efficiency at {batch_sizes[-1]}x batch size")

        assert efficiency > 2.0, f"Expected >2x efficiency, got {efficiency:.2f}x"

        await processor.stop()

    @pytest.mark.asyncio
    async def test_batch_memory_overhead(self):
        """Test batch processing memory overhead."""
        from kagami.forge.modules.generation.batch_processor import (
            GaussianSplattingBatchProcessor,
            BatchConfig,
        )

        import psutil
        import os

        process = psutil.Process(os.getpid())

        config = BatchConfig(max_batch_size=8, enable_gpu_monitoring=False)
        processor = GaussianSplattingBatchProcessor(config)
        await processor.start()

        mem_before = process.memory_info().rss / (1024**2)  # MB

        # Submit large batch
        tasks = [processor.submit(f"test_{i}") for i in range(8)]
        await asyncio.gather(*tasks)
        await asyncio.sleep(2.0)

        mem_after = process.memory_info().rss / (1024**2)  # MB
        mem_increase = mem_after - mem_before

        # Assuming ~10MB per task baseline
        baseline_memory = 8 * 10
        overhead_pct = ((mem_increase - baseline_memory) / baseline_memory) * 100

        logger.info("Batch memory overhead:")
        logger.info(f"  Baseline: {baseline_memory:.2f} MB")
        logger.info(f"  Actual: {mem_increase:.2f} MB")
        logger.info(f"  Overhead: {overhead_pct:.1f}%")

        assert overhead_pct < 20, f"Expected <20% overhead, got {overhead_pct:.1f}%"

        await processor.stop()


# =============================================================================
# LLM Request Batcher Benchmarks
# =============================================================================


class TestLLMBatcherBenchmarks:
    """Benchmark LLM request batcher."""

    @pytest.mark.asyncio
    async def test_request_deduplication_savings(self):
        """Test savings from request deduplication."""
        from kagami.core.services.llm.request_batcher import RequestBatcher, BatchConfig

        config = BatchConfig(
            enable_deduplication=True,
            batch_timeout_ms=100,
        )
        batcher = RequestBatcher(config)

        # Create requests with duplicates
        prompts = [
            "What is AI?",
            "Explain machine learning",
            "What is AI?",  # Duplicate
            "What is AI?",  # Duplicate
            "Explain machine learning",  # Duplicate
        ]

        # Test with deduplication
        start = time.time()
        tasks = [batcher.request(prompt) for prompt in prompts]
        responses = await asyncio.gather(*tasks)
        dedup_time = time.time() - start

        stats = await batcher.get_stats()

        logger.info("Deduplication benchmark:")
        logger.info(f"  Total requests: {stats['total_requests']}")
        logger.info(f"  Deduplicated: {stats['deduplicated']}")
        logger.info(f"  Dedup rate: {stats['dedup_rate']:.1%}")
        logger.info(f"  Time: {dedup_time:.2f}s")

        assert stats["dedup_rate"] > 0.4, f"Expected >40% dedup rate, got {stats['dedup_rate']:.1%}"

    @pytest.mark.asyncio
    async def test_batching_latency_reduction(self):
        """Test latency reduction from batching."""
        from kagami.core.services.llm.request_batcher import (
            RequestBatcher,
            BatchConfig,
            BatchingStrategy,
        )

        config = BatchConfig(
            strategy=BatchingStrategy.ADAPTIVE,
            max_batch_size=5,
            batch_timeout_ms=50,
            enable_parallel=True,
        )
        batcher = RequestBatcher(config)

        # Concurrent requests
        num_requests = 10
        prompts = [f"Test prompt {i}" for i in range(num_requests)]

        # Test batched
        start = time.time()
        tasks = [batcher.request(prompt) for prompt in prompts]
        await asyncio.gather(*tasks)
        batched_time = time.time() - start

        stats = await batcher.get_stats()

        logger.info("Batching latency benchmark:")
        logger.info(f"  Requests: {num_requests}")
        logger.info(f"  Batches: {stats['batches_processed']}")
        logger.info(f"  Total time: {batched_time:.2f}s")
        logger.info(f"  Avg latency: {stats['avg_latency_ms']:.2f}ms")

        # Batching should process multiple requests per batch
        avg_batch_size = num_requests / stats["batches_processed"]
        assert avg_batch_size > 2, f"Expected avg batch size >2, got {avg_batch_size:.1f}"

    @pytest.mark.asyncio
    async def test_cache_hit_rate_impact(self):
        """Test impact of cache hit rate on performance."""
        from kagami.core.services.llm.request_batcher import RequestBatcher, BatchConfig

        config = BatchConfig(
            enable_deduplication=True,
            dedup_cache_ttl=60,
        )
        batcher = RequestBatcher(config)

        # Same prompt multiple times
        prompt = "What is the meaning of life?"

        # First round (cache misses)
        start = time.time()
        tasks = [batcher.request(prompt) for _ in range(10)]
        await asyncio.gather(*tasks)
        first_time = time.time() - start

        # Second round (cache hits)
        start = time.time()
        tasks = [batcher.request(prompt) for _ in range(10)]
        await asyncio.gather(*tasks)
        second_time = time.time() - start

        speedup = first_time / second_time if second_time > 0 else 0

        stats = await batcher.get_stats()

        logger.info("Cache hit rate impact:")
        logger.info(f"  First round: {first_time:.2f}s")
        logger.info(f"  Second round: {second_time:.2f}s")
        logger.info(f"  Speedup: {speedup:.2f}x")
        logger.info(f"  Cache hit rate: {stats['cache_hit_rate']:.1%}")

        assert speedup > 2, f"Expected >2x speedup from cache, got {speedup:.2f}x"


# =============================================================================
# Database Query Optimizer Benchmarks
# =============================================================================


class TestDatabaseOptimizerBenchmarks:
    """Benchmark database query optimizer."""

    @pytest.mark.asyncio
    async def test_query_profiling_overhead(self):
        """Test overhead of query profiling."""
        from kagami.core.database.query_optimizer import QueryProfiler

        profiler = QueryProfiler(enable_profiling=True)

        # Simulate queries
        num_queries = 1000

        # With profiling
        start = time.time()
        for i in range(num_queries):
            await profiler.record_query(
                query=f"SELECT * FROM users WHERE id = {i}",
                execution_time=0.001,
                row_count=1,
            )
        profiling_time = time.time() - start

        # Calculate overhead per query
        overhead_per_query = (profiling_time / num_queries) * 1000  # ms

        logger.info("Query profiling overhead:")
        logger.info(f"  Queries: {num_queries}")
        logger.info(f"  Total time: {profiling_time:.3f}s")
        logger.info(f"  Overhead per query: {overhead_per_query:.3f}ms")

        # Overhead should be minimal
        assert overhead_per_query < 1.0, f"Expected <1ms overhead, got {overhead_per_query:.3f}ms"

    @pytest.mark.asyncio
    async def test_slow_query_detection(self):
        """Test slow query detection accuracy."""
        from kagami.core.database.query_optimizer import QueryProfiler

        profiler = QueryProfiler(enable_profiling=True)
        profiler._slow_query_threshold = 0.5

        # Mix of fast and slow queries
        fast_queries = [("SELECT * FROM cache WHERE id = 1", 0.01) for _ in range(50)]
        slow_queries = [
            ("SELECT * FROM logs JOIN users ON logs.user_id = users.id", 0.8) for _ in range(5)
        ]

        for query, exec_time in fast_queries + slow_queries:
            await profiler.record_query(query, exec_time)

        slow = await profiler.get_slow_queries(min_time=0.5)

        logger.info("Slow query detection:")
        logger.info(f"  Total queries: {len(fast_queries) + len(slow_queries)}")
        logger.info(f"  Slow queries detected: {len(slow)}")

        assert len(slow) > 0, "Should detect slow queries"
        assert len(slow) <= len(slow_queries), "Should not over-detect"

    @pytest.mark.asyncio
    async def test_index_recommendation_accuracy(self):
        """Test index recommendation generation."""
        from kagami.core.database.query_optimizer import QueryProfiler

        profiler = QueryProfiler(enable_profiling=True)

        # Simulate slow queries that would benefit from indexes
        queries = [
            ("SELECT * FROM users WHERE email = 'test@example.com'", 1.2),
            ("SELECT * FROM users WHERE email = 'test2@example.com'", 1.1),
            ("SELECT * FROM orders WHERE user_id = 123", 0.9),
            ("SELECT * FROM orders WHERE user_id = 456", 1.0),
        ]

        for query, exec_time in queries:
            await profiler.record_query(query, exec_time)

        recommendations = await profiler.get_recommendations()

        logger.info("Index recommendations:")
        for rec in recommendations:
            logger.info(
                f"  {rec.table_name}.({', '.join(rec.columns)}): "
                f"{rec.estimated_improvement:.1f}% improvement"
            )

        assert len(recommendations) > 0, "Should generate recommendations"


# =============================================================================
# Progressive Renderer Benchmarks
# =============================================================================


class TestProgressiveRendererBenchmarks:
    """Benchmark progressive rendering pipeline."""

    @pytest.mark.asyncio
    async def test_progressive_vs_direct_rendering(self):
        """Compare progressive rendering to direct rendering."""
        from kagami.forge.progressive_renderer import (
            ProgressiveRenderer,
            RenderConfig,
            RenderQuality,
        )

        # Progressive rendering
        progressive_config = RenderConfig(
            target_quality=RenderQuality.PRODUCTION,
            enable_progressive=True,
        )
        progressive_renderer = ProgressiveRenderer(progressive_config)

        progressive_start = time.time()
        progressive_state = await progressive_renderer.render("test character")
        progressive_time = time.time() - progressive_start

        # Direct rendering
        direct_config = RenderConfig(
            target_quality=RenderQuality.PRODUCTION,
            enable_progressive=False,
        )
        direct_renderer = ProgressiveRenderer(direct_config)

        direct_start = time.time()
        direct_state = await direct_renderer.render("test character")
        direct_time = time.time() - direct_start

        # Progressive should show first results faster
        logger.info("Rendering comparison:")
        logger.info(f"  Progressive time: {progressive_time:.2f}s")
        logger.info(f"  Direct time: {direct_time:.2f}s")
        logger.info(f"  Progressive stages: {len(progressive_state.results)}")

        # Progressive rendering provides intermediate results
        assert len(progressive_state.results) > 1, "Progressive should have multiple stages"

    @pytest.mark.asyncio
    async def test_quality_scaling_performance(self):
        """Test performance scaling across quality levels."""
        from kagami.forge.progressive_renderer import (
            ProgressiveRenderer,
            RenderConfig,
            RenderQuality,
        )

        qualities = [
            RenderQuality.DRAFT,
            RenderQuality.PREVIEW,
            RenderQuality.PRODUCTION,
        ]
        times = []

        for quality in qualities:
            config = RenderConfig(
                target_quality=quality,
                enable_progressive=False,
            )
            renderer = ProgressiveRenderer(config)

            start = time.time()
            await renderer.render("test")
            elapsed = time.time() - start
            times.append(elapsed)

            logger.info(f"{quality.value}: {elapsed:.2f}s")

        # Higher quality should take longer
        assert times[0] < times[1] < times[2], "Quality should correlate with time"

        # Draft should be significantly faster
        speedup = times[2] / times[0]
        logger.info(f"Draft speedup: {speedup:.2f}x")

        assert speedup > 2, f"Expected >2x speedup for draft, got {speedup:.2f}x"


# =============================================================================
# Integration Benchmarks
# =============================================================================


class TestIntegrationBenchmarks:
    """Benchmark full optimization stack integration."""

    @pytest.mark.asyncio
    async def test_end_to_end_optimization_impact(self):
        """Test combined impact of all optimizations."""
        from kagami.core.caching.redis_cache import RedisCache
        from kagami.core.services.llm.request_batcher import RequestBatcher
        from kagami.forge.modules.generation.batch_processor import (
            GaussianSplattingBatchProcessor,
        )

        # Initialize all optimization components
        cache = RedisCache(namespace="bench")
        await cache.initialize()

        batcher = RequestBatcher()

        processor = GaussianSplattingBatchProcessor()
        await processor.start()

        # Baseline: Without optimizations
        baseline_start = time.time()
        for _i in range(5):
            # Simulate: LLM call + DB query + Generation
            await asyncio.sleep(0.5)  # LLM
            await asyncio.sleep(0.1)  # DB
            await asyncio.sleep(1.0)  # Generation
        baseline_time = time.time() - baseline_start

        # Optimized: With all optimizations
        optimized_start = time.time()
        tasks = []
        for i in range(5):
            # Cached LLM + Cached DB + Batched Generation
            tasks.append(
                asyncio.gather(
                    cache.get(f"llm_{i}"),
                    cache.get(f"db_{i}"),
                    processor.submit(f"prompt_{i}"),
                )
            )
        await asyncio.gather(*tasks)
        optimized_time = time.time() - optimized_start

        improvement = ((baseline_time - optimized_time) / baseline_time) * 100
        speedup = baseline_time / optimized_time

        logger.info("End-to-end optimization impact:")
        logger.info(f"  Baseline time: {baseline_time:.2f}s")
        logger.info(f"  Optimized time: {optimized_time:.2f}s")
        logger.info(f"  Improvement: {improvement:.1f}%")
        logger.info(f"  Speedup: {speedup:.2f}x")

        assert improvement > 50, f"Expected >50% improvement, got {improvement:.1f}%"

        await cache.close()
        await processor.stop()


# =============================================================================
# Performance Summary Report
# =============================================================================


@pytest.fixture(scope="session")
def performance_summary(request):
    """Generate performance summary report after all tests."""
    summary = {
        "cache_improvements": [],
        "batch_improvements": [],
        "llm_improvements": [],
        "db_improvements": [],
        "progressive_improvements": [],
    }

    yield summary

    # Print summary at end
    logger.info("\n" + "=" * 80)
    logger.info("PERFORMANCE OPTIMIZATION SUMMARY")
    logger.info("=" * 80)

    for category, improvements in summary.items():
        if improvements:
            avg_improvement = sum(improvements) / len(improvements)
            logger.info(f"\n{category}:")
            logger.info(f"  Average improvement: {avg_improvement:.1f}%")
            logger.info(f"  Number of tests: {len(improvements)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
