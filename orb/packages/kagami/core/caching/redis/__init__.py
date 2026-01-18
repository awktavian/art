"""K OS Redis Package.

Unified Redis client management for ephemeral/real-time data.

HARDENED (Dec 22, 2025): Real Redis is MANDATORY. No fake fallbacks.

STORAGE ARCHITECTURE (Dec 7, 2025):
===================================
Redis is now focused on ephemeral/real-time operations only:
- Caching (L2 multi-tier cache)
- Pub/sub messaging
- Rate limiting
- Session state
- Distributed locks

For persistent/semantic storage, use:
- Weaviate: Vector search, RAG, patterns, stigmergy
- CockroachDB: Relational, transactional data

RedisFS and RedisVectorStore have been REMOVED.
Use kagami.core.caching.storage_routing.UnifiedStorageRouter for routing.

This package provides:
- factory.py: Client factory and connection pooling
- pool_monitor.py: Connection pool monitoring
"""

from kagami.core.caching.redis.factory import RedisClientFactory
from kagami.core.caching.redis.pool_monitor import RedisPoolMonitor

__all__ = [
    # Factory
    "RedisClientFactory",
    # Monitoring
    "RedisPoolMonitor",
]
