"""Example: How to integrate all performance optimizations.

This example demonstrates how to use all optimization features together
to achieve maximum performance improvement.

Colony: Nexus (e₄) - Integration
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_1_basic_caching():
    """Example 1: Basic caching with Redis."""
    from kagami.core.caching.redis_cache import RedisCache, CacheConfig

    # Initialize cache
    config = CacheConfig(
        host="localhost",
        default_ttl=3600,
        enable_memory_tier=True,
    )
    cache = RedisCache(config)
    await cache.initialize()

    # Simulate expensive operation
    async def expensive_operation(key: str) -> dict[str, Any]:
        await asyncio.sleep(1.0)  # 1 second operation
        return {"result": f"data_{key}"}

    # First call: cache miss (slow)
    logger.info("First call (uncached)...")
    result = await cache.get("key1")
    if result is None:
        result = await expensive_operation("key1")
        await cache.set("key1", result)
    logger.info(f"Result: {result}")

    # Second call: cache hit (fast)
    logger.info("Second call (cached)...")
    result = await cache.get("key1")
    logger.info(f"Result: {result}")

    # Get stats
    stats = await cache.get_stats()
    logger.info(f"Cache stats: Hit rate = {stats['hit_rate']:.1%}")

    await cache.close()


async def example_2_cached_decorator():
    """Example 2: Using @cached decorator."""
    from kagami.core.caching.redis_cache import cached

    @cached(ttl=3600, key_prefix="user")
    async def get_user(user_id: int) -> dict[str, Any]:
        logger.info(f"Fetching user {user_id} from database...")
        await asyncio.sleep(1.0)
        return {"id": user_id, "name": f"User {user_id}"}

    # First call: slow
    logger.info("First call...")
    user = await get_user(123)
    logger.info(f"User: {user}")

    # Second call: fast (cached)
    logger.info("Second call...")
    user = await get_user(123)
    logger.info(f"User: {user}")


async def example_3_batch_processing():
    """Example 3: Batch processing for Gaussian Splatting."""
    from kagami.forge.modules.generation.batch_processor import (
        get_gaussian_processor,
        Priority,
    )

    processor = await get_gaussian_processor()

    # Submit multiple tasks
    prompts = [
        "fantasy warrior",
        "sci-fi robot",
        "medieval castle",
        "futuristic city",
    ]

    logger.info(f"Submitting {len(prompts)} tasks...")
    task_ids = []
    for prompt in prompts:
        task_id = await processor.submit(prompt, priority=Priority.HIGH)
        task_ids.append(task_id)
        logger.info(f"  Submitted: {task_id}")

    # Wait for processing
    await asyncio.sleep(5.0)

    # Get stats
    stats = await processor.get_stats()
    logger.info(f"Batch stats: Throughput = {stats['avg_throughput']:.2f} items/s")

    await processor.stop()


async def example_4_llm_batching():
    """Example 4: LLM request batching."""
    from kagami.core.services.llm.request_batcher import batched_llm_request

    # Submit multiple LLM requests concurrently
    prompts = [
        "What is AI?",
        "Explain machine learning",
        "What is AI?",  # Duplicate - will be deduplicated
    ]

    logger.info(f"Submitting {len(prompts)} LLM requests...")

    # All requests submitted concurrently will be batched
    responses = await asyncio.gather(*[batched_llm_request(prompt) for prompt in prompts])

    for prompt, response in zip(prompts, responses, strict=False):
        logger.info(f"Prompt: {prompt[:30]}...")
        logger.info(f"Response: {response[:50]}...")


async def example_5_database_profiling():
    """Example 5: Database query profiling."""
    from kagami.core.database.query_optimizer import QueryProfiler, profile_query

    profiler = QueryProfiler(enable_profiling=True)

    # Profile queries
    @profile_query(profiler)
    async def get_users() -> list[dict]:
        logger.info("Executing query...")
        await asyncio.sleep(0.5)
        return [{"id": 1, "name": "User 1"}]

    # Execute multiple queries
    for _ in range(5):
        await get_users()

    # Get slow queries
    slow_queries = await profiler.get_slow_queries(min_time=0.3)
    logger.info(f"Found {len(slow_queries)} slow queries")

    # Get recommendations
    recommendations = await profiler.get_recommendations()
    logger.info("Index recommendations:")
    for rec in recommendations:
        logger.info(f"  CREATE INDEX ON {rec['table_name']}({', '.join(rec['columns'])})")

    # Get stats
    stats = await profiler.get_stats()
    logger.info(f"Profiler stats: {stats}")


async def example_6_progressive_rendering():
    """Example 6: Progressive rendering."""
    from kagami.forge.progressive_renderer import (
        progressive_render,
        RenderQuality,
        RenderResult,
    )

    # Callback for intermediate results
    async def on_result(result: RenderResult):
        logger.info(f"Stage {result.stage.value} completed in {result.render_time:.2f}s")

    # Start progressive rendering
    logger.info("Starting progressive rendering...")
    state = await progressive_render(
        prompt="fantasy warrior character",
        quality=RenderQuality.PRODUCTION,
        callback=on_result,
    )

    logger.info(f"Rendering completed in {state.elapsed_time:.2f}s")
    logger.info(f"Completed stages: {len(state.results)}")


async def example_7_performance_monitoring():
    """Example 7: Performance monitoring and metrics."""
    from kagami.core.performance.optimization_monitor import (
        get_optimization_metrics,
        get_performance_report,
    )

    # Get current metrics
    logger.info("Current metrics:")
    metrics = await get_optimization_metrics()

    logger.info(f"  Cache hit rate: {metrics['cache']['hit_rate']:.1%}")
    logger.info(f"  Batch throughput: {metrics['batch_processing']['throughput']:.2f} items/s")
    logger.info(f"  LLM dedup rate: {metrics['llm']['dedup_rate']:.1%}")

    # Get performance report
    logger.info("\nPerformance report:")
    report = await get_performance_report()

    logger.info("Recommendations:")
    for rec in report["recommendations"]:
        logger.info(f"  - {rec}")


async def example_8_full_integration():
    """Example 8: Full integration of all optimizations."""
    from kagami.core.caching.redis_cache import get_global_cache, cached
    from kagami.forge.modules.generation.batch_processor import get_gaussian_processor
    from kagami.core.services.llm.request_batcher import batched_llm_request
    from kagami.core.performance.optimization_monitor import get_global_monitor

    logger.info("=" * 80)
    logger.info("FULL INTEGRATION EXAMPLE")
    logger.info("=" * 80)

    # 1. Initialize all optimizations
    logger.info("\n1. Initializing optimizations...")
    cache = await get_global_cache()
    processor = await get_gaussian_processor()
    monitor = await get_global_monitor()
    logger.info("   ✓ All optimizations initialized")

    # 2. Use cached LLM calls
    logger.info("\n2. Making cached LLM calls...")

    @cached(ttl=3600, key_prefix="llm")
    async def generate_concept(prompt: str) -> str:
        return await batched_llm_request(prompt)

    # First call: slow
    concept1 = await generate_concept("Create a fantasy character")
    logger.info(f"   Concept: {concept1[:50]}...")

    # Second call: fast (cached)
    concept2 = await generate_concept("Create a fantasy character")
    logger.info(f"   Concept (cached): {concept2[:50]}...")

    # 3. Submit batch generation
    logger.info("\n3. Submitting batch generation...")
    task_ids = []
    for i in range(3):
        task_id = await processor.submit(f"character_{i}")
        task_ids.append(task_id)
    logger.info(f"   ✓ Submitted {len(task_ids)} tasks")

    # 4. Monitor performance
    logger.info("\n4. Checking performance metrics...")
    stats = await processor.get_stats()
    logger.info(f"   Batch throughput: {stats['avg_throughput']:.2f} items/s")

    cache_stats = await cache.get_stats()
    logger.info(f"   Cache hit rate: {cache_stats['hit_rate']:.1%}")

    # 5. Generate report
    logger.info("\n5. Performance report:")
    from kagami.core.performance.optimization_monitor import get_performance_report

    report = await get_performance_report()

    logger.info("\n   Metrics summary:")
    logger.info(f"   - Cache hit rate: {report['cache']['avg_hit_rate']:.1%}")
    logger.info(
        f"   - Batch throughput: {report['batch_processing']['avg_throughput']:.2f} items/s"
    )
    logger.info(f"   - LLM dedup rate: {report['llm']['avg_dedup_rate']:.1%}")

    logger.info("\n   Recommendations:")
    for rec in report["recommendations"]:
        logger.info(f"   - {rec}")

    # Cleanup
    await cache.close()
    await processor.stop()
    await monitor.stop()

    logger.info("\n" + "=" * 80)
    logger.info("INTEGRATION COMPLETE")
    logger.info("=" * 80)


async def example_9_before_after_comparison():
    """Example 9: Before/After performance comparison."""
    import time

    logger.info("=" * 80)
    logger.info("BEFORE/AFTER COMPARISON")
    logger.info("=" * 80)

    # Simulate expensive operations
    async def expensive_operation(i: int) -> dict:
        await asyncio.sleep(0.5)
        return {"id": i, "result": f"data_{i}"}

    # BEFORE: No optimizations
    logger.info("\nBEFORE (no optimizations):")
    start = time.time()
    results = []
    for i in range(10):
        result = await expensive_operation(i)
        results.append(result)
    before_time = time.time() - start
    logger.info(f"  Time: {before_time:.2f}s")
    logger.info(f"  Throughput: {len(results) / before_time:.2f} items/s")

    # AFTER: With caching
    logger.info("\nAFTER (with caching):")
    from kagami.core.caching.redis_cache import RedisCache

    cache = RedisCache(namespace="comparison")
    await cache.initialize()

    start = time.time()
    results = []
    for i in range(10):
        # First half: cache misses
        # Second half: cache hits (repeat keys)
        key = f"item_{i % 5}"
        result = await cache.get(key)
        if result is None:
            result = await expensive_operation(i)
            await cache.set(key, result)
        results.append(result)
    after_time = time.time() - start
    logger.info(f"  Time: {after_time:.2f}s")
    logger.info(f"  Throughput: {len(results) / after_time:.2f} items/s")

    # Calculate improvement
    improvement = ((before_time - after_time) / before_time) * 100
    speedup = before_time / after_time

    logger.info("\nIMPROVEMENT:")
    logger.info(f"  Speedup: {speedup:.2f}x")
    logger.info(f"  Time saved: {improvement:.1f}%")

    cache_stats = await cache.get_stats()
    logger.info(f"  Cache hit rate: {cache_stats['hit_rate']:.1%}")

    await cache.close()

    logger.info("\n" + "=" * 80)


# Main function to run all examples
async def main():
    """Run all examples."""
    examples = [
        ("Basic Caching", example_1_basic_caching),
        ("Cached Decorator", example_2_cached_decorator),
        ("Batch Processing", example_3_batch_processing),
        ("LLM Batching", example_4_llm_batching),
        ("Database Profiling", example_5_database_profiling),
        ("Progressive Rendering", example_6_progressive_rendering),
        ("Performance Monitoring", example_7_performance_monitoring),
        ("Full Integration", example_8_full_integration),
        ("Before/After Comparison", example_9_before_after_comparison),
    ]

    for name, example in examples:
        logger.info("\n" + "=" * 80)
        logger.info(f"EXAMPLE: {name}")
        logger.info("=" * 80)
        try:
            await example()
        except Exception as e:
            logger.error(f"Example failed: {e}", exc_info=True)
        await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(main())
