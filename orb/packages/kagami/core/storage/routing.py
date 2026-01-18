"""Storage routing for optimal backend selection.

This module re-exports the UnifiedStorageRouter from services layer
for the repository pattern.

Moved from caching to services (December 2025) to fix layer violation:
caching (L1) should not import from services (L5) or consensus (L4).

Created: December 15, 2025
"""

from kagami.core.services.storage_routing import (
    STORAGE_ROUTING,
    DataCategory,
    StorageBackend,
    StorageConfig,
    UnifiedStorageRouter,
    get_storage_router,
)

__all__ = [
    "STORAGE_ROUTING",
    "DataCategory",
    "StorageBackend",
    "StorageConfig",
    "UnifiedStorageRouter",
    "get_storage_router",
]
