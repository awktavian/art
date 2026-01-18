"""K OS Caching Package

Multi-layer caching system for performance optimization.

This package provides caching functionality:
- base.py: CacheProtocol, BaseCacheConfig, decorators (@cached, @async_cached)
- backends.py: MemoryBackend, RedisBackend, CompositeBackend
- memory_cache.py: Simple in-memory cache with LRU and TTL
- unified.py: Unified cache interface (L1/L2 with Redis)
- redis/: Redis client factory and connection pooling
- redis_keys.py: Centralized Redis key namespace management
- intent_cache.py: Intent caching for LLM
- response_cache.py: HTTP response caching
- storage_routing.py: Storage tier routing
- adaptive_config.py: Environment-aware adaptive configuration

RECOMMENDED USAGE (New Code):
=============================
For new cache implementations, use the base infrastructure:

    from kagami.core.caching import (
        CacheProtocol,
        BaseCache,
        BaseCacheConfig,
        MemoryBackend,
        CompositeBackend,
        cached,
        async_cached,
    )

    # Use MemoryBackend for simple in-memory caching
    cache = MemoryBackend(MemoryCacheConfig(max_size=1000))

    # Use CompositeBackend for L1 memory + L2 Redis
    cache = await create_composite_cache(namespace="myservice")

    # Use decorators for function caching
    @async_cached(cache=my_cache, ttl=3600)
    async def expensive_operation(x: int) -> dict:
        ...

LEGACY USAGE (Existing Code):
=============================
For simple in-memory caching, use:
    from kagami.core.caching import MemoryCache, CacheManager
    cache = MemoryCache(name="my_cache", max_size=100, default_ttl=3600)

For Redis access, use:
    from kagami.core.caching.redis import RedisClientFactory
    redis = RedisClientFactory.get_client(purpose='default')

For Redis key generation, use:
    from kagami.core.caching.redis_keys import RedisKeys
    key = RedisKeys.receipt("correlation_id", "PLAN")

For adaptive configuration, use:
    from kagami.core.caching.adaptive_config import get_adaptive_settings
    settings = get_adaptive_settings()

"""

# Core caching interfaces - NEW base infrastructure
# Adaptive configuration
from .adaptive_config import (
    AdaptiveCacheSettings,
    AdaptiveConfigManager,
    EnvironmentProfile,
    ResourceMonitor,
    ResourceSnapshot,
    get_adaptive_settings,
    get_resource_snapshot,
    reconfigure_caches,
)
from .backends import (
    CompositeBackend,
    CompositeCacheConfig,
    MemoryBackend,
    MemoryCacheConfig,
    RedisBackend,
    RedisCacheConfig,
    create_composite_cache,
    create_memory_cache,
    create_redis_cache,
)
from .base import (
    BaseCache,
    BaseCacheConfig,
    CacheEntry,
    CacheProtocol,
    CacheStats,
    CacheTier,
    EvictionPolicy,
    async_cached,
    cached,
    generate_cache_key,
)
from .intent_cache import (
    IntentCache,
    get_intent_cache,
)
from .memory_cache import (
    CacheManager,
    MemoryCache,
    _generate_cache_key,
)
from .redis_keys import RedisKeys
from .response_cache import (
    CacheConfig,
    ResponseCache,
    ResponseCacheModule,
    hash_key,
)
from .unified import (
    UnifiedCache,
    get_unified_cache,
)

__all__ = [
    # === Legacy (still supported) ===
    # Adaptive Configuration
    "AdaptiveCacheSettings",
    "AdaptiveConfigManager",
    # === NEW Base Infrastructure ===
    # Base classes and protocols
    "BaseCache",
    "BaseCacheConfig",
    "CacheConfig",
    "CacheEntry",
    "CacheManager",
    "CacheProtocol",
    "CacheStats",
    "CacheTier",
    # Backends
    "CompositeBackend",
    "CompositeCacheConfig",
    "EnvironmentProfile",
    "EvictionPolicy",
    # Intent
    "IntentCache",
    "MemoryBackend",
    # Memory Cache (simple in-memory LRU+TTL)
    "MemoryCache",
    "MemoryCacheConfig",
    "RedisBackend",
    "RedisCacheConfig",
    # Redis Keys
    "RedisKeys",
    "ResourceMonitor",
    "ResourceSnapshot",
    # Response
    "ResponseCache",
    "ResponseCacheModule",
    # Unified
    "UnifiedCache",
    "_generate_cache_key",
    # Decorators
    "async_cached",
    "cached",
    # Factory functions
    "create_composite_cache",
    "create_memory_cache",
    "create_redis_cache",
    "generate_cache_key",
    "get_adaptive_settings",
    "get_intent_cache",
    "get_resource_snapshot",
    "get_unified_cache",
    "hash_key",
    "reconfigure_caches",
]
