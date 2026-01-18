"""Storage repository layer for KagamiOS.

This module provides protocol-based repositories with multi-tier caching,
storage routing, and Markov blanket compliance.

Architecture:
    - L1: In-memory LRU cache
    - L2: Redis cache
    - L3: Primary storage (CockroachDB/Weaviate/etcd)

Created: December 15, 2025
"""

from kagami.core.storage.base import BaseRepository, CacheStrategy
from kagami.core.storage.knowledge_repository import KnowledgeRepository
from kagami.core.storage.protocols import Repository

# Import repositories
from kagami.core.storage.receipt_repository import ReceiptRepository
from kagami.core.storage.routing import (
    DataCategory,
    StorageBackend,
    StorageConfig,
    UnifiedStorageRouter,
    get_storage_router,
)
from kagami.core.storage.safety_repository import SafetyRepository, ThreatRepository
from kagami.core.storage.user_repository import (
    APIKeyRepository,
    SessionRepository,
    UserRepository,
)
from kagami.core.storage.world_model_repository import (
    EFERepository,
    WorldModelRepository,
)

__all__ = [
    "APIKeyRepository",
    # Base
    "BaseRepository",
    "CacheStrategy",
    "DataCategory",
    "EFERepository",
    "KnowledgeRepository",
    # Repositories
    "ReceiptRepository",
    # Protocols
    "Repository",
    "SafetyRepository",
    "SessionRepository",
    # Routing
    "StorageBackend",
    "StorageConfig",
    "ThreatRepository",
    "UnifiedStorageRouter",
    "UserRepository",
    "WorldModelRepository",
    "get_storage_router",
]
