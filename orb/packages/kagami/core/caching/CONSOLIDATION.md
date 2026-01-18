# Cache Consolidation Plan

**Date:** January 11, 2026
**Status:** Phase 1 Complete - Base Infrastructure Created

## Overview

This document outlines the cache consolidation strategy for K OS. After analyzing 10+ cache implementations, we've created a unified base infrastructure and identified which caches should be consolidated vs. remain specialized.

## New Infrastructure

### Created Files

1. **`base.py`** - Core abstractions
   - `CacheProtocol` - Abstract interface all caches should implement
   - `BaseCache` - Abstract base class with common functionality
   - `BaseCacheConfig` - Configuration dataclass
   - `CacheStats` - Unified statistics
   - `CacheEntry` - Entry with metadata (TTL, access count, etc.)
   - `@cached` / `@async_cached` - Function caching decorators

2. **`backends.py`** - Concrete implementations
   - `MemoryBackend` - Fast in-memory LRU cache
   - `RedisBackend` - Redis-backed distributed cache
   - `CompositeBackend` - Multi-tier (L1 memory + L2 Redis)

### Usage

```python
from kagami.core.caching import (
    MemoryBackend,
    MemoryCacheConfig,
    CompositeBackend,
    async_cached,
)

# Simple memory cache
cache = MemoryBackend(MemoryCacheConfig(max_size=1000, default_ttl=3600))
await cache.set("key", "value")

# Composite L1+L2 cache
cache = await create_composite_cache(namespace="myservice")

# Decorator for function caching
@async_cached(cache=my_cache, ttl=3600)
async def expensive_operation(x: int) -> dict:
    ...
```

## Cache Inventory

### Caches to Consolidate (Migrate to Base Infrastructure)

| Current Implementation | Location | Migration Strategy |
|----------------------|----------|-------------------|
| `MemoryCache` | `memory_cache.py` | Replace with `MemoryBackend` wrapper |
| `ResponseCache` | `response_cache.py` | Extend `CompositeBackend` with response-specific features |
| `SafetyClassificationCache` | `safety/safety_cache.py` | Use `MemoryBackend` with custom key hashing |
| `SenseCache` (x2) | `sensory/cache.py`, `sensory/sense_cache.py` | Merge into single `MemoryBackend` instance |
| `LLMResponseCache` | `redis_cache.py` | Use `RedisBackend` with specialized wrapper |

### Caches to Keep Specialized

| Implementation | Location | Reason |
|---------------|----------|--------|
| `CachedE8Quantizer` | `kagami_math/e8_cache.py` | Tensor-specific, tight coupling with E8 lattice math, GPU memory management |
| `E8TrajectoryCache` | `world_model/e8_trajectory_cache.py` | Specialized for bifurcation replay, tensor hashing, training loop integration |
| `EmbeddingCentroidCache` | `safety/embedding_cache.py` | Semantic similarity matching, centroid clustering, not key-value |
| `EarconCacheService` | `audio/earcon_cache.py` | Audio file preloading, file I/O, not generic caching |
| `SemanticCache` | `forge/semantic_cache.py` | Embedding-based similarity, not key-value |
| `UnifiedModelCache` | `caching/unified_model_cache.py` | ML model checkpoint management, disk + memory tiers |

## Migration Priority

### Phase 1: Base Infrastructure (COMPLETE)
- [x] Create `CacheProtocol` interface
- [x] Create `BaseCache` abstract class
- [x] Create `BaseCacheConfig` dataclass
- [x] Create `CacheStats` unified statistics
- [x] Create `@cached` / `@async_cached` decorators
- [x] Create `MemoryBackend`
- [x] Create `RedisBackend`
- [x] Create `CompositeBackend`

### Phase 2: Critical Path Migrations (Future Work)
- [ ] Update `UnifiedCache` to use `CompositeBackend` internally
- [ ] Update `MemoryCache` to wrap `MemoryBackend`
- [ ] Add protocol compliance to `SafetyClassificationCache`

### Phase 3: Full Consolidation (Future Work)
- [ ] Merge duplicate `SenseCache` implementations
- [ ] Update `ResponseCache` to extend base classes
- [ ] Add consistent metrics/observability

## Specialized Cache Notes

### E8 Caches (Keep Specialized)

The E8 lattice caches are tightly coupled to tensor operations:

```python
# CachedE8Quantizer uses tensor-specific hashing
def _compute_cache_key(self, point: Tensor) -> tuple[int, ...]:
    scale = 10**self.cache_precision
    rounded_ints = torch.round(point.detach() * scale).cpu().to(torch.int64).numpy()
    return tuple(rounded_ints.tolist())
```

This requires tensor awareness and GPU memory management that doesn't fit the generic `CacheProtocol`.

### Semantic Caches (Keep Specialized)

Both `EmbeddingCentroidCache` and `SemanticCache` use embedding similarity:

```python
# EmbeddingCentroidCache uses cosine similarity
def _find_nearest_centroid(self, embedding: np.ndarray) -> tuple[int, float] | None:
    similarities = self._centroid_matrix @ embedding
    best_idx = int(np.argmax(similarities))
    return (best_idx, float(similarities[best_idx]))
```

This is fundamentally different from key-value caching.

### EarconCacheService (Keep Specialized)

This is really a file preloader with cache-like patterns:

```python
async def _load_or_synthesize(self, name: str) -> None:
    # Check orchestral directory first (preferred)
    orchestral_file = ORCHESTRAL_DIR / f"{name}.wav"
    if orchestral_file.exists():
        audio, sr = sf.read(orchestral_file, dtype="float32")
        ...
```

The file I/O and audio format handling is domain-specific.

## Common Patterns Extracted

### 1. Statistics Tracking

All caches now share `CacheStats`:

```python
@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
```

### 2. Thread Safety Pattern

All backends use the same lock pattern:

```python
def _acquire_lock(self) -> bool:
    if self._lock:
        return self._lock.acquire()
    return True

def _release_lock(self) -> None:
    if self._lock:
        self._lock.release()
```

### 3. Key Namespacing

All backends support namespace prefixing:

```python
def _make_key(self, key: K) -> str:
    key_str = str(key) if not isinstance(key, str) else key
    if self.config.namespace:
        return f"{self.config.namespace}:{key_str}"
    return key_str
```

### 4. TTL Clamping

TTL values are clamped to configured bounds:

```python
effective_ttl = max(self.config.min_ttl, min(effective_ttl, self.config.max_ttl))
```

## Deprecation Strategy

No existing caches are deprecated immediately. The base infrastructure is additive:

1. **New code** should use `MemoryBackend`, `RedisBackend`, or `CompositeBackend`
2. **Existing code** continues to work unchanged
3. **Gradual migration** as caches are touched for other reasons

## Testing Recommendations

When migrating a cache to the base infrastructure:

1. Verify hit rate stays consistent (compare `CacheStats`)
2. Verify TTL behavior matches expectations
3. Load test to ensure no performance regression
4. Check thread safety under concurrent access

## Metrics

All caches using the base infrastructure automatically get:

- `cache_hits_total{cache_name, tier}`
- `cache_misses_total{cache_name, tier}`
- `cache_evictions_total{cache_name}`
- `cache_size{cache_name}`
- `cache_get_latency_seconds{cache_name}`
- `cache_set_latency_seconds{cache_name}`

## Summary

- **10+ cache implementations** analyzed
- **3 new backend classes** created (Memory, Redis, Composite)
- **5 caches** identified for consolidation
- **6 caches** remain specialized (domain-specific requirements)
- **Phase 1 complete** - Base infrastructure ready for use
