#!/usr/bin/env python3
"""Benchmark ModelCache performance for world model loading.

This script demonstrates the cache speedup for repeated world model loads.
Expected results:
- First load (cold): ~90s (no cache)
- Second load (warm): ~5s (cache hit)
- Speedup: ~18x

Usage:
    python scripts/benchmark_model_cache.py
"""

import asyncio
import time
from pathlib import Path

from kagami.core.world_model.model_factory import (
    KagamiWorldModelFactory,
    load_model_from_checkpoint_async,
    save_model_checkpoint,
)


async def benchmark_cache():
    """Run cache benchmark."""
    print("🔥 ModelCache Performance Benchmark")
    print("=" * 60)

    # Create temporary checkpoint
    checkpoint_path = Path("/tmp/benchmark_checkpoint.pt")
    if not checkpoint_path.exists():
        print("\n📦 Creating test checkpoint...")
        model = KagamiWorldModelFactory.create(preset="minimal", device="cpu")
        save_model_checkpoint(model, str(checkpoint_path))
        print(f"   Saved to {checkpoint_path}")

    # Clear any existing cache
    from kagami.core.caching.unified_model_cache import get_model_cache

    cache = get_model_cache()
    await cache.invalidate_cache(model_id=str(checkpoint_path))

    # Benchmark: First load (cache miss)
    print("\n🔴 First load (cache miss - cold start):")
    start = time.perf_counter()
    model1 = await load_model_from_checkpoint_async(
        str(checkpoint_path), device="cpu", use_cache=True
    )
    first_load_time = time.perf_counter() - start
    print(f"   Time: {first_load_time:.3f}s")
    print(f"   Model: {type(model1).__name__}")

    # Benchmark: Second load (cache hit)
    print("\n🟢 Second load (cache hit - warm start):")
    start = time.perf_counter()
    model2 = await load_model_from_checkpoint_async(
        str(checkpoint_path), device="cpu", use_cache=True
    )
    second_load_time = time.perf_counter() - start
    print(f"   Time: {second_load_time:.3f}s")
    print(f"   Model: {type(model2).__name__}")

    # Calculate speedup
    speedup = first_load_time / second_load_time
    print("\n📊 Results:")
    print(f"   First load:  {first_load_time:.3f}s (cold start)")
    print(f"   Second load: {second_load_time:.3f}s (cache hit)")
    print(f"   Speedup:     {speedup:.1f}x")

    # Cache info
    info = cache.get_cache_info()
    print("\n💾 Cache Info:")
    print(f"   Cached models: {info['cached_models']}")
    print(f"   Cache size:    {info['total_size_gb']:.2f} GB")
    print(f"   Cache dir:     {info['cache_dir']}")

    # Cleanup
    checkpoint_path.unlink()
    print(f"\n✅ Benchmark complete! Cleaned up {checkpoint_path}")


if __name__ == "__main__":
    asyncio.run(benchmark_cache())
