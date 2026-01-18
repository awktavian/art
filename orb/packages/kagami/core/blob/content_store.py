"""Content-Addressed Blob Store — Integrity-Verified Storage.

Provides content-addressed storage with SHA-256 hashing for data integrity.
All data is verified on read to detect corruption or tampering.

Features:
- Content addressing (SHA-256 hash = address)
- Integrity verification on every read
- Chunked storage for large blobs
- AES-256-GCM encryption at rest
- LRU caching for frequently accessed blobs
- Async/await interface

Architecture:
```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTENT STORE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   store(data) ──▶ SHA-256 ──▶ chunk ──▶ encrypt ──▶ persist    │
│                      │                                          │
│                      ▼                                          │
│                    hash                                         │
│                      │                                          │
│   get(hash) ◀── decrypt ◀── reassemble ◀── verify ◀── load    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Colony: Crystal (D₅) — Verification and integrity
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class StorageBackend(Enum):
    """Storage backend types."""

    FILESYSTEM = auto()
    MEMORY = auto()
    S3 = auto()
    GCS = auto()


@dataclass
class ContentStoreConfig:
    """Content store configuration.

    Attributes:
        storage_path: Base path for filesystem storage.
        backend: Storage backend type.
        encryption_key: 32-byte AES-256 key (hex-encoded).
        chunk_size: Size of chunks for large blobs (bytes).
        verify_on_read: Verify hash on every read.
        max_blob_size: Maximum blob size (bytes).
        cache_size: LRU cache size (number of blobs).
        gc_interval: Garbage collection interval (seconds).
        gc_max_age: Maximum age for unreferenced blobs (seconds).
    """

    storage_path: str = ""
    backend: StorageBackend = StorageBackend.FILESYSTEM
    encryption_key: str = ""
    chunk_size: int = 1024 * 1024  # 1MB chunks
    verify_on_read: bool = True
    max_blob_size: int = 100 * 1024 * 1024  # 100MB
    cache_size: int = 1000
    gc_interval: float = 3600.0  # 1 hour
    gc_max_age: float = 7 * 24 * 3600.0  # 7 days

    def __post_init__(self) -> None:
        """Load from environment."""
        if not self.storage_path:
            self.storage_path = os.environ.get(
                "KAGAMI_BLOB_STORAGE_PATH", str(Path.home() / ".kagami" / "blobs")
            )

        if not self.encryption_key:
            self.encryption_key = os.environ.get("KAGAMI_BLOB_ENCRYPTION_KEY", "")
            if not self.encryption_key:
                # Generate ephemeral key for development
                self.encryption_key = os.urandom(32).hex()
                logger.warning(
                    "⚠️ Using ephemeral blob encryption key. "
                    "Set KAGAMI_BLOB_ENCRYPTION_KEY for persistence."
                )

        self.chunk_size = int(os.environ.get("KAGAMI_BLOB_CHUNK_SIZE", str(self.chunk_size)))

        self.verify_on_read = os.environ.get("KAGAMI_BLOB_VERIFY_ON_READ", "true").lower() == "true"

    @property
    def encryption_key_bytes(self) -> bytes:
        """Get encryption key as bytes."""
        return bytes.fromhex(self.encryption_key)


@dataclass
class BlobMetadata:
    """Metadata for a stored blob.

    Attributes:
        hash: SHA-256 content hash (hex).
        size: Original data size (bytes).
        chunks: Number of chunks (1 for small blobs).
        content_type: MIME type or data type.
        created_at: Creation timestamp.
        accessed_at: Last access timestamp.
        encrypted: Whether blob is encrypted.
        compression: Compression algorithm used.
        custom: Custom metadata dictionary.
    """

    hash: str
    size: int
    chunks: int = 1
    content_type: str = "application/octet-stream"
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    encrypted: bool = True
    compression: str | None = None
    custom: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "hash": self.hash,
            "size": self.size,
            "chunks": self.chunks,
            "content_type": self.content_type,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "encrypted": self.encrypted,
            "compression": self.compression,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlobMetadata:
        """Deserialize from dictionary."""
        return cls(
            hash=data["hash"],
            size=data["size"],
            chunks=data.get("chunks", 1),
            content_type=data.get("content_type", "application/octet-stream"),
            created_at=data.get("created_at", time.time()),
            accessed_at=data.get("accessed_at", time.time()),
            encrypted=data.get("encrypted", True),
            compression=data.get("compression"),
            custom=data.get("custom", {}),
        )


class BlobIntegrityError(Exception):
    """Raised when blob integrity verification fails."""

    pass


class BlobNotFoundError(Exception):
    """Raised when blob is not found."""

    pass


class BlobTooLargeError(Exception):
    """Raised when blob exceeds size limit."""

    pass


# =============================================================================
# Storage Backends
# =============================================================================


class StorageBackendBase(ABC):
    """Abstract base for storage backends."""

    @abstractmethod
    async def store_chunk(self, hash: str, chunk_index: int, data: bytes) -> None:
        """Store a chunk."""
        ...

    @abstractmethod
    async def get_chunk(self, hash: str, chunk_index: int) -> bytes:
        """Get a chunk."""
        ...

    @abstractmethod
    async def delete_blob(self, hash: str, chunks: int) -> None:
        """Delete all chunks for a blob."""
        ...

    @abstractmethod
    async def exists(self, hash: str) -> bool:
        """Check if blob exists."""
        ...

    @abstractmethod
    async def store_metadata(self, metadata: BlobMetadata) -> None:
        """Store blob metadata."""
        ...

    @abstractmethod
    async def get_metadata(self, hash: str) -> BlobMetadata | None:
        """Get blob metadata."""
        ...

    @abstractmethod
    async def list_blobs(self) -> list[str]:
        """List all blob hashes."""
        ...


class FilesystemBackend(StorageBackendBase):
    """Filesystem storage backend."""

    def __init__(self, base_path: str) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        (self.base_path / "metadata").mkdir(exist_ok=True)
        (self.base_path / "chunks").mkdir(exist_ok=True)

    def _chunk_path(self, hash: str, chunk_index: int) -> Path:
        """Get path for a chunk file."""
        # Use hash prefix for directory sharding
        prefix = hash[:2]
        dir_path = self.base_path / "chunks" / prefix
        dir_path.mkdir(exist_ok=True)
        return dir_path / f"{hash}.{chunk_index}"

    def _metadata_path(self, hash: str) -> Path:
        """Get path for metadata file."""
        prefix = hash[:2]
        dir_path = self.base_path / "metadata" / prefix
        dir_path.mkdir(exist_ok=True)
        return dir_path / f"{hash}.json"

    async def store_chunk(self, hash: str, chunk_index: int, data: bytes) -> None:
        """Store a chunk to filesystem."""
        path = self._chunk_path(hash, chunk_index)

        # Atomic write
        temp_path = path.with_suffix(".tmp")
        temp_path.write_bytes(data)
        temp_path.rename(path)

    async def get_chunk(self, hash: str, chunk_index: int) -> bytes:
        """Get a chunk from filesystem."""
        path = self._chunk_path(hash, chunk_index)
        if not path.exists():
            raise BlobNotFoundError(f"Chunk not found: {hash}.{chunk_index}")
        return path.read_bytes()

    async def delete_blob(self, hash: str, chunks: int) -> None:
        """Delete all chunks for a blob."""
        for i in range(chunks):
            path = self._chunk_path(hash, i)
            if path.exists():
                path.unlink()

        metadata_path = self._metadata_path(hash)
        if metadata_path.exists():
            metadata_path.unlink()

    async def exists(self, hash: str) -> bool:
        """Check if blob exists."""
        metadata_path = self._metadata_path(hash)
        return metadata_path.exists()

    async def store_metadata(self, metadata: BlobMetadata) -> None:
        """Store blob metadata."""
        path = self._metadata_path(metadata.hash)

        # Atomic write
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(metadata.to_dict(), indent=2))
        temp_path.rename(path)

    async def get_metadata(self, hash: str) -> BlobMetadata | None:
        """Get blob metadata."""
        path = self._metadata_path(hash)
        if not path.exists():
            return None

        data = json.loads(path.read_text())
        return BlobMetadata.from_dict(data)

    async def list_blobs(self) -> list[str]:
        """List all blob hashes."""
        hashes = []
        metadata_dir = self.base_path / "metadata"

        for prefix_dir in metadata_dir.iterdir():
            if prefix_dir.is_dir():
                for meta_file in prefix_dir.glob("*.json"):
                    hashes.append(meta_file.stem)

        return hashes


class MemoryBackend(StorageBackendBase):
    """In-memory storage backend for testing."""

    def __init__(self) -> None:
        self.chunks: dict[str, bytes] = {}
        self.metadata: dict[str, BlobMetadata] = {}

    async def store_chunk(self, hash: str, chunk_index: int, data: bytes) -> None:
        """Store a chunk in memory."""
        key = f"{hash}.{chunk_index}"
        self.chunks[key] = data

    async def get_chunk(self, hash: str, chunk_index: int) -> bytes:
        """Get a chunk from memory."""
        key = f"{hash}.{chunk_index}"
        if key not in self.chunks:
            raise BlobNotFoundError(f"Chunk not found: {key}")
        return self.chunks[key]

    async def delete_blob(self, hash: str, chunks: int) -> None:
        """Delete all chunks for a blob."""
        for i in range(chunks):
            key = f"{hash}.{i}"
            self.chunks.pop(key, None)
        self.metadata.pop(hash, None)

    async def exists(self, hash: str) -> bool:
        """Check if blob exists."""
        return hash in self.metadata

    async def store_metadata(self, metadata: BlobMetadata) -> None:
        """Store blob metadata."""
        self.metadata[metadata.hash] = metadata

    async def get_metadata(self, hash: str) -> BlobMetadata | None:
        """Get blob metadata."""
        return self.metadata.get(hash)

    async def list_blobs(self) -> list[str]:
        """List all blob hashes."""
        return list(self.metadata.keys())


# =============================================================================
# Content Store
# =============================================================================


class ContentStore:
    """Content-addressed blob store with encryption and verification.

    Example:
        >>> config = ContentStoreConfig()
        >>> store = ContentStore(config)
        >>> await store.initialize()
        >>>
        >>> # Store data
        >>> hash = await store.store(b"hello world", content_type="text/plain")
        >>> print(f"Stored as: {hash}")
        >>>
        >>> # Retrieve data
        >>> data = await store.get(hash)
        >>> print(data)  # b"hello world"
        >>>
        >>> # Store JSON
        >>> hash = await store.store_json({"key": "value"})
        >>> obj = await store.get_json(hash)
    """

    def __init__(self, config: ContentStoreConfig | None = None) -> None:
        self.config = config or ContentStoreConfig()
        self._backend: StorageBackendBase | None = None
        self._aesgcm: AESGCM | None = None
        self._cache: dict[str, bytes] = {}  # Simple LRU simulation
        self._cache_order: list[str] = []
        self._gc_task: asyncio.Task | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the content store."""
        if self._initialized:
            return

        # Initialize encryption
        self._aesgcm = AESGCM(self.config.encryption_key_bytes)

        # Initialize backend
        if self.config.backend == StorageBackend.FILESYSTEM:
            self._backend = FilesystemBackend(self.config.storage_path)
        elif self.config.backend == StorageBackend.MEMORY:
            self._backend = MemoryBackend()
        else:
            raise ValueError(f"Unsupported backend: {self.config.backend}")

        # Start GC task
        if self.config.gc_interval > 0:
            self._gc_task = asyncio.create_task(self._gc_loop())

        self._initialized = True
        logger.info(f"✅ ContentStore initialized ({self.config.backend.name})")

    async def shutdown(self) -> None:
        """Shutdown the content store."""
        if self._gc_task:
            self._gc_task.cancel()
            try:
                await self._gc_task
            except asyncio.CancelledError:
                pass

        self._cache.clear()
        self._cache_order.clear()
        self._initialized = False

    async def store(
        self,
        data: bytes,
        content_type: str = "application/octet-stream",
        custom_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store data and return content hash.

        Args:
            data: Data to store.
            content_type: MIME type.
            custom_metadata: Additional metadata.

        Returns:
            SHA-256 hash (hex) of the data.

        Raises:
            BlobTooLargeError: If data exceeds max size.
        """
        if not self._initialized:
            await self.initialize()

        if len(data) > self.config.max_blob_size:
            raise BlobTooLargeError(
                f"Data size {len(data)} exceeds max {self.config.max_blob_size}"
            )

        # Compute content hash
        content_hash = hashlib.sha256(data).hexdigest()

        # Check if already exists
        if await self._backend.exists(content_hash):
            logger.debug(f"Blob already exists: {content_hash[:12]}...")
            return content_hash

        # Chunk and encrypt
        chunks = self._chunk_data(data)

        for i, chunk in enumerate(chunks):
            encrypted_chunk = self._encrypt(chunk, content_hash, i)
            await self._backend.store_chunk(content_hash, i, encrypted_chunk)

        # Store metadata
        metadata = BlobMetadata(
            hash=content_hash,
            size=len(data),
            chunks=len(chunks),
            content_type=content_type,
            custom=custom_metadata or {},
        )
        await self._backend.store_metadata(metadata)

        # Add to cache
        self._cache_put(content_hash, data)

        logger.debug(
            f"Stored blob: {content_hash[:12]}... ({len(data)} bytes, {len(chunks)} chunks)"
        )
        return content_hash

    async def get(self, hash: str) -> bytes:
        """Get data by content hash.

        Args:
            hash: SHA-256 hash (hex).

        Returns:
            Original data bytes.

        Raises:
            BlobNotFoundError: If blob doesn't exist.
            BlobIntegrityError: If verification fails.
        """
        if not self._initialized:
            await self.initialize()

        # Check cache
        if hash in self._cache:
            self._cache_touch(hash)
            return self._cache[hash]

        # Get metadata
        metadata = await self._backend.get_metadata(hash)
        if not metadata:
            raise BlobNotFoundError(f"Blob not found: {hash}")

        # Load and decrypt chunks
        chunks = []
        for i in range(metadata.chunks):
            encrypted_chunk = await self._backend.get_chunk(hash, i)
            chunk = self._decrypt(encrypted_chunk, hash, i)
            chunks.append(chunk)

        # Reassemble
        data = b"".join(chunks)

        # Verify integrity
        if self.config.verify_on_read:
            computed_hash = hashlib.sha256(data).hexdigest()
            if computed_hash != hash:
                raise BlobIntegrityError(f"Hash mismatch: expected {hash}, got {computed_hash}")

        # Update access time
        metadata.accessed_at = time.time()
        await self._backend.store_metadata(metadata)

        # Cache
        self._cache_put(hash, data)

        return data

    async def store_json(
        self,
        obj: Any,
        custom_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store JSON-serializable object.

        Args:
            obj: JSON-serializable object.
            custom_metadata: Additional metadata.

        Returns:
            Content hash.
        """
        data = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
        return await self.store(
            data,
            content_type="application/json",
            custom_metadata=custom_metadata,
        )

    async def get_json(self, hash: str) -> Any:
        """Get JSON object by hash.

        Args:
            hash: Content hash.

        Returns:
            Deserialized JSON object.
        """
        data = await self.get(hash)
        return json.loads(data.decode())

    async def delete(self, hash: str) -> bool:
        """Delete blob by hash.

        Args:
            hash: Content hash.

        Returns:
            True if deleted, False if not found.
        """
        if not self._initialized:
            await self.initialize()

        metadata = await self._backend.get_metadata(hash)
        if not metadata:
            return False

        await self._backend.delete_blob(hash, metadata.chunks)

        # Remove from cache
        if hash in self._cache:
            del self._cache[hash]
            self._cache_order.remove(hash)

        logger.debug(f"Deleted blob: {hash[:12]}...")
        return True

    async def exists(self, hash: str) -> bool:
        """Check if blob exists.

        Args:
            hash: Content hash.

        Returns:
            True if exists.
        """
        if not self._initialized:
            await self.initialize()

        return await self._backend.exists(hash)

    async def get_metadata(self, hash: str) -> BlobMetadata | None:
        """Get blob metadata.

        Args:
            hash: Content hash.

        Returns:
            Blob metadata or None.
        """
        if not self._initialized:
            await self.initialize()

        return await self._backend.get_metadata(hash)

    async def list_blobs(self) -> list[str]:
        """List all blob hashes.

        Returns:
            List of content hashes.
        """
        if not self._initialized:
            await self.initialize()

        return await self._backend.list_blobs()

    # Alias for convenience
    async def list(self) -> list[str]:
        """Alias for list_blobs()."""
        return await self.list_blobs()

    async def verify(self, hash: str) -> bool:
        """Verify blob integrity.

        Re-computes hash from stored data and compares.

        Args:
            hash: Content hash to verify.

        Returns:
            True if integrity verified, False otherwise.
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Get the data (this already verifies if verify_on_read is True)
            data = await self.get(hash)

            # Re-compute hash
            computed_hash = hashlib.sha256(data).hexdigest()
            return computed_hash == hash

        except (BlobNotFoundError, BlobIntegrityError):
            return False
        except Exception as e:
            logger.warning(f"Verification failed for {hash[:12]}...: {e}")
            return False

    async def get_stats(self) -> dict[str, Any]:
        """Get store statistics.

        Returns:
            Statistics dictionary.
        """
        if not self._initialized:
            await self.initialize()

        blobs = await self.list_blobs()
        total_size = 0

        for hash in blobs:
            metadata = await self._backend.get_metadata(hash)
            if metadata:
                total_size += metadata.size

        return {
            "blob_count": len(blobs),
            "total_size_bytes": total_size,
            "cache_size": len(self._cache),
            "backend": self.config.backend.name,
            "storage_path": self.config.storage_path,
        }

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _chunk_data(self, data: bytes) -> list[bytes]:
        """Split data into chunks."""
        if len(data) <= self.config.chunk_size:
            return [data]

        chunks = []
        for i in range(0, len(data), self.config.chunk_size):
            chunks.append(data[i : i + self.config.chunk_size])

        return chunks

    def _encrypt(self, data: bytes, hash: str, chunk_index: int) -> bytes:
        """Encrypt a chunk with AES-256-GCM.

        Uses hash + chunk_index as associated data for authentication.
        """
        # Generate nonce (12 bytes)
        nonce = os.urandom(12)

        # Associated data: hash + chunk index
        aad = f"{hash}:{chunk_index}".encode()

        # Encrypt
        ciphertext = self._aesgcm.encrypt(nonce, data, aad)

        # Return nonce + ciphertext
        return nonce + ciphertext

    def _decrypt(self, encrypted: bytes, hash: str, chunk_index: int) -> bytes:
        """Decrypt a chunk with AES-256-GCM."""
        # Extract nonce and ciphertext
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]

        # Associated data
        aad = f"{hash}:{chunk_index}".encode()

        # Decrypt
        return self._aesgcm.decrypt(nonce, ciphertext, aad)

    def _cache_put(self, hash: str, data: bytes) -> None:
        """Add to cache with LRU eviction."""
        if hash in self._cache:
            self._cache_touch(hash)
            return

        # Evict if full
        while len(self._cache) >= self.config.cache_size:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]

        self._cache[hash] = data
        self._cache_order.append(hash)

    def _cache_touch(self, hash: str) -> None:
        """Move to end of LRU list."""
        if hash in self._cache_order:
            self._cache_order.remove(hash)
            self._cache_order.append(hash)

    async def _gc_loop(self) -> None:
        """Garbage collection loop."""
        while True:
            try:
                await asyncio.sleep(self.config.gc_interval)
                await self._run_gc()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"GC error: {e}")

    async def _run_gc(self) -> None:
        """Run garbage collection."""
        cutoff = time.time() - self.config.gc_max_age
        deleted = 0

        blobs = await self.list_blobs()
        for hash in blobs:
            metadata = await self._backend.get_metadata(hash)
            if metadata and metadata.accessed_at < cutoff:
                await self.delete(hash)
                deleted += 1

        if deleted > 0:
            logger.info(f"GC: deleted {deleted} expired blobs")


# =============================================================================
# Factory Functions
# =============================================================================


_content_store: ContentStore | None = None


async def get_content_store(config: ContentStoreConfig | None = None) -> ContentStore:
    """Get or create the singleton content store.

    Args:
        config: Store configuration.

    Returns:
        ContentStore instance.

    Example:
        >>> store = await get_content_store()
        >>> hash = await store.store(b"data")
    """
    global _content_store

    if _content_store is None:
        _content_store = ContentStore(config)
        await _content_store.initialize()

    return _content_store


async def shutdown_content_store() -> None:
    """Shutdown the content store."""
    global _content_store

    if _content_store:
        await _content_store.shutdown()
        _content_store = None


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
