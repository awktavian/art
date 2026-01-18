"""Storage backend implementations for Kagami persistence.

CREATED: December 28, 2025
PURPOSE: Abstract storage backends for flexible state persistence.

Supported Backends:
- FilesystemBackend: Local JSON/pickle files (fast, simple)
- RedisBackend: In-memory cache (sub-second access)
- PostgreSQLBackend: Durable SQL storage (ACID guarantees)
- CloudBackend: S3/GCS object storage (archive, infinite scale)

All backends implement the StorageBackend protocol for transparent switching.
"""

from kagami.core.persistence.backends.cloud import CloudBackend
from kagami.core.persistence.backends.filesystem import FilesystemBackend
from kagami.core.persistence.backends.gcs_native import GCSNativeBackend
from kagami.core.persistence.backends.postgres import PostgreSQLBackend
from kagami.core.persistence.backends.protocol import (
    BackendType,
    StorageBackend,
    StorageConfig,
)
from kagami.core.persistence.backends.redis_backend import RedisBackend

__all__ = [
    "BackendType",
    "CloudBackend",
    "FilesystemBackend",
    "GCSNativeBackend",
    "PostgreSQLBackend",
    "RedisBackend",
    "StorageBackend",
    "StorageConfig",
]
