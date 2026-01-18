#!/usr/bin/env python3
"""Benchmark ModelCache integration with LLM providers.

This script demonstrates the performance improvement from caching
transformers models.

Usage:
    python scripts/benchmark_modelcache.py

Environment Variables:
    KAGAMI_MODEL_CACHE_ENABLED: 1 (default) or 0 to disable
    KAGAMI_TRANSFORMERS_MODEL_DEFAULT: Model to use (default: sshleifer/tiny-gpt2)
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add kagami to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kagami.core.caching.unified_model_cache import get_model_cache
from kagami.core.services.llm.llm_providers import TransformersTextClient


async def benchmark_with_cache():
    """Benchmark LLM loading with ModelCache enabled."""
    print("\n" + "=" * 60)
    print("BENCHMARK: ModelCache ENABLED")
    print("=" * 60)

    os.environ["KAGAMI_MODEL_CACHE_ENABLED"] = "1"
    os.environ["KAGAMI_LLM_ENABLE_BATCHING"] = "0"

    model_name = os.getenv("KAGAMI_TRANSFORMERS_MODEL_DEFAULT", "sshleifer/tiny-gpt2")

    # First run - cache miss
    print(f"\n1. First load (cache miss) - model: {model_name}")
    client1 = TransformersTextClient(model_name)

    start = time.time()
    result1 = await client1.generate_text("Hello", max_tokens=5, temperature=0.0)
    first_duration = time.time() - start

    print(f"   Result: {result1[:50]}...")
    print(f"   Duration: {first_duration:.2f}s")

    # Second run - same client (already loaded)
    print("\n2. Second call on same client (already loaded)")

    start = time.time()
    result2 = await client1.generate_text("World", max_tokens=5, temperature=0.0)
    second_duration = time.time() - start

    print(f"   Result: {result2[:50]}...")
    print(f"   Duration: {second_duration:.2f}s")
    print(f"   Speedup: {first_duration / second_duration:.1f}x")

    # Third run - new client, cache hit
    print("\n3. New client (cache hit from disk)")
    client2 = TransformersTextClient(model_name)

    start = time.time()
    result3 = await client2.generate_text("Test", max_tokens=5, temperature=0.0)
    third_duration = time.time() - start

    print(f"   Result: {result3[:50]}...")
    print(f"   Duration: {third_duration:.2f}s")
    print(f"   Speedup vs first load: {first_duration / third_duration:.1f}x")

    # Show cache stats
    cache = get_model_cache()
    info = cache.get_cache_info()

    print("\n📊 Cache Statistics:")
    print(f"   Cached models: {info['cached_models']}")
    print(f"   Total size: {info['total_size_gb']:.2f}GB / {info['max_size_gb']:.2f}GB")
    print(f"   Cache directory: {info['cache_dir']}")

    for model in info["models"]:
        print(f"\n   Model: {model['model_id']}")
        print(f"     Size: {model['size_mb']:.1f}MB")
        print(f"     Hit count: {model['hit_count']}")
        print(f"     Config: {model['config']}")

    return {
        "first_load": first_duration,
        "second_call": second_duration,
        "new_client": third_duration,
        "cache_info": info,
    }


async def benchmark_without_cache():
    """Benchmark LLM loading without ModelCache (for comparison)."""
    print("\n" + "=" * 60)
    print("BENCHMARK: ModelCache DISABLED (baseline)")
    print("=" * 60)

    os.environ["KAGAMI_MODEL_CACHE_ENABLED"] = "0"
    os.environ["KAGAMI_LLM_ENABLE_BATCHING"] = "0"

    model_name = os.getenv("KAGAMI_TRANSFORMERS_MODEL_DEFAULT", "sshleifer/tiny-gpt2")

    # First run
    print(f"\n1. First load (no cache) - model: {model_name}")
    client1 = TransformersTextClient(model_name)

    start = time.time()
    result1 = await client1.generate_text("Hello", max_tokens=5, temperature=0.0)
    first_duration = time.time() - start

    print(f"   Result: {result1[:50]}...")
    print(f"   Duration: {first_duration:.2f}s")

    # Second run - same client
    print("\n2. Second call on same client")

    start = time.time()
    result2 = await client1.generate_text("World", max_tokens=5, temperature=0.0)
    second_duration = time.time() - start

    print(f"   Result: {result2[:50]}...")
    print(f"   Duration: {second_duration:.2f}s")

    return {
        "first_load": first_duration,
        "second_call": second_duration,
    }


async def main():
    """Run benchmarks and show comparison."""
    print("\n╔════════════════════════════════════════════════════════╗")
    print("║        ModelCache Integration Benchmark               ║")
    print("╚════════════════════════════════════════════════════════╝")

    # Run with cache
    cached_results = await benchmark_with_cache()

    # Run without cache (optional - comment out if slow)
    # uncached_results = await benchmark_without_cache()

    # print("\n" + "=" * 60)
    # print("COMPARISON SUMMARY")
    # print("=" * 60)
    # print(f"\nFirst load:")
    # print(f"  With cache: {cached_results['first_load']:.2f}s")
    # print(f"  Without cache: {uncached_results['first_load']:.2f}s")
    # print(f"  Difference: {abs(cached_results['first_load'] - uncached_results['first_load']):.2f}s")

    print("\n" + "=" * 60)
    print("KEY FINDINGS")
    print("=" * 60)
    print(f"\n✅ First load: {cached_results['first_load']:.2f}s")  # type: ignore[index]
    print(f"✅ Second call (same client): {cached_results['second_call']:.2f}s")  # type: ignore[index]
    print(f"✅ New client (cache hit): {cached_results['new_client']:.2f}s")  # type: ignore[index]

    print("\n📈 Performance improvement:")
    print(
        f"   Speedup (same client): {cached_results['first_load'] / cached_results['second_call']:.1f}x"  # type: ignore[index]
    )
    print(
        f"   Speedup (new client): {cached_results['first_load'] / cached_results['new_client']:.1f}x"  # type: ignore[index]
    )

    if cached_results["new_client"] < cached_results["first_load"] * 0.5:  # type: ignore[index]
        print("\n🎉 SUCCESS: Cache provides >2x speedup for subsequent loads!")
    else:
        print("\n⚠️  Cache overhead may be present, but still functional.")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
