"""Storage backend protocol for Kagami persistence.

CREATED: December 28, 2025
PURPOSE: Define common interface for all storage backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class BackendType(str, Enum):
    """Storage backend types."""

    FILESYSTEM = "filesystem"
    REDIS = "redis"
    POSTGRESQL = "postgresql"
    CLOUD = "cloud"  # S3/GCS


@dataclass
class StorageConfig:
    """Configuration for storage backend."""

    backend_type: BackendType
    params: dict[str, Any]

    # Common options
    compression_enabled: bool = True
    encryption_enabled: bool = False
    encryption_key: bytes | None = None

    # Retry and timeout
    max_retries: int = 3
    timeout_seconds: float = 30.0

    # Versioning
    enable_versioning: bool = True
    max_versions: int = 10


class StorageBackend(ABC):
    """Abstract base class for storage backends.

    All backends must implement these methods for transparent backend switching.
    """

    def __init__(self, config: StorageConfig):
        """Initialize backend with configuration."""
        self.config = config

    @abstractmethod
    async def save(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save data to storage.

        Args:
            key: Storage key (path/identifier)
            data: Binary data to save
            metadata: Optional metadata

        Returns:
            Version ID or checksum of saved data

        Raises:
            StorageError: If save fails
        """
        ...

    @abstractmethod
    async def load(
        self,
        key: str,
        version: str | None = None,
    ) -> tuple[bytes, dict[str, Any]]:
        """Load data from storage.

        Args:
            key: Storage key
            version: Optional version ID (None = latest)

        Returns:
            Tuple of (data, metadata)

        Raises:
            StorageError: If load fails
            KeyError: If key not found
        """
        ...

    @abstractmethod
    async def delete(self, key: str, version: str | None = None) -> bool:
        """Delete data from storage.

        Args:
            key: Storage key
            version: Optional version ID (None = all versions)

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists.

        Args:
            key: Storage key

        Returns:
            True if exists
        """
        ...

    @abstractmethod
    async def list_keys(
        self,
        prefix: str | None = None,
        limit: int | None = None,
    ) -> list[str]:
        """List all keys with optional prefix filter.

        Args:
            prefix: Key prefix filter
            limit: Maximum number of keys

        Returns:
            List of keys
        """
        ...

    @abstractmethod
    async def list_versions(self, key: str) -> list[str]:
        """List all versions of a key.

        Args:
            key: Storage key

        Returns:
            List of version IDs (newest first)
        """
        ...

    @abstractmethod
    async def get_metadata(self, key: str, version: str | None = None) -> dict[str, Any]:
        """Get metadata for a key without loading data.

        Args:
            key: Storage key
            version: Optional version ID

        Returns:
            Metadata dictionary
        """
        ...

    @abstractmethod
    async def get_size(self, key: str, version: str | None = None) -> int:
        """Get size of stored data in bytes.

        Args:
            key: Storage key
            version: Optional version ID

        Returns:
            Size in bytes
        """
        ...

    async def close(self) -> None:  # noqa: B027
        """Close backend and release resources.

        Optional: Override if backend needs cleanup.
        """
        pass


class StorageError(Exception):
    """Base exception for storage backend errors."""

    pass


class KeyNotFoundError(StorageError, KeyError):
    """Key not found in storage."""

    pass


class VersionNotFoundError(StorageError):
    """Version not found for key."""

    pass


class StorageFullError(StorageError):
    """Storage backend is full."""

    pass


class StorageConnectionError(StorageError):
    """Failed to connect to storage backend."""

    pass
