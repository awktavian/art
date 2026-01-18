"""Content-addressed blob storage module.

Provides integrity-verified storage with SHA-256 content addressing.

Created: January 2026
"""

from kagami.core.blob.content_store import (
    BlobIntegrityError,
    BlobMetadata,
    BlobNotFoundError,
    BlobTooLargeError,
    ContentStore,
    ContentStoreConfig,
    FilesystemBackend,
    MemoryBackend,
    StorageBackend,
    StorageBackendBase,
    get_content_store,
    shutdown_content_store,
)

__all__ = [
    "BlobIntegrityError",
    "BlobMetadata",
    "BlobNotFoundError",
    "BlobTooLargeError",
    "ContentStore",
    "ContentStoreConfig",
    "FilesystemBackend",
    "MemoryBackend",
    "StorageBackend",
    "StorageBackendBase",
    "get_content_store",
    "shutdown_content_store",
]
