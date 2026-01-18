"""Redis storage backend for Kagami persistence.

CREATED: December 28, 2025
PURPOSE: Fast in-memory cache layer for state persistence.

Features:
- Sub-second access times
- Perfect for recent state caching
- TTL-based automatic expiration
- Pub/sub for state change notifications
- Requires redis-py (pip install redis)

Usage:
    config = StorageConfig(
        backend_type=BackendType.REDIS,
        params={
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "password": None,
            "ttl_seconds": 3600,  # 1 hour default
        }
    )
    backend = RedisBackend(config)
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

try:
    import redis.asyncio as redis

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

from kagami.core.persistence.backends.protocol import (
    KeyNotFoundError,
    StorageBackend,
    StorageConfig,
    StorageConnectionError,
)


class RedisBackend(StorageBackend):
    """Redis storage backend for fast caching."""

    def __init__(self, config: StorageConfig):
        """Initialize Redis backend."""
        super().__init__(config)

        if not HAS_REDIS:
            raise ImportError("redis not installed. pip install redis")

        # Extract connection params
        params = config.params
        self.host = params.get("host", "localhost")
        self.port = params.get("port", 6379)
        self.db = params.get("db", 0)
        self.password = params.get("password")
        self.ttl_seconds = params.get("ttl_seconds", 3600)

        # Create Redis client
        self.client: redis.Redis | None = None

    async def _ensure_connected(self) -> redis.Redis:
        """Ensure Redis connection is established."""
        if self.client is None:
            try:
                self.client = await redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=False,  # Binary mode
                )
                await self.client.ping()
            except Exception as e:
                raise StorageConnectionError(f"Failed to connect to Redis: {e}") from e
        return self.client

    async def save(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save data to Redis."""
        client = await self._ensure_connected()

        # Generate version ID
        version_id = f"v{int(time.time() * 1000000)}"

        # Compute checksum
        checksum = hashlib.sha256(data).hexdigest()

        # Prepare metadata
        metadata = metadata or {}
        metadata.update(
            {
                "version": version_id,
                "checksum": checksum,
                "size": len(data),
                "timestamp": time.time(),
            }
        )

        # Redis keys
        if self.config.enable_versioning:
            data_key = f"{key}:{version_id}:data"
            meta_key = f"{key}:{version_id}:meta"
        else:
            data_key = f"{key}:data"
            meta_key = f"{key}:meta"

        # Save data and metadata
        await client.set(data_key, data, ex=self.ttl_seconds)
        await client.set(meta_key, json.dumps(metadata), ex=self.ttl_seconds)

        # Update latest pointer
        if self.config.enable_versioning:
            await client.set(f"{key}:latest", version_id, ex=self.ttl_seconds)

            # Add to version list[Any]
            await client.lpush(f"{key}:versions", version_id)
            await client.expire(f"{key}:versions", self.ttl_seconds)

            # Prune old versions
            await self._prune_versions(key)

        return version_id

    async def load(
        self,
        key: str,
        version: str | None = None,
    ) -> tuple[bytes, dict[str, Any]]:
        """Load data from Redis."""
        client = await self._ensure_connected()

        # Resolve version
        if version is None and self.config.enable_versioning:
            version = await client.get(f"{key}:latest")
            if version:
                version = version.decode("utf-8")

        # Construct keys
        if version:
            data_key = f"{key}:{version}:data"
            meta_key = f"{key}:{version}:meta"
        else:
            data_key = f"{key}:data"
            meta_key = f"{key}:meta"

        # Load data
        data = await client.get(data_key)
        if data is None:
            raise KeyNotFoundError(f"Key not found: {key}")

        # Load metadata
        meta_bytes = await client.get(meta_key)
        if meta_bytes:
            metadata = json.loads(meta_bytes.decode("utf-8"))
        else:
            metadata = {}

        # Verify checksum
        if "checksum" in metadata:
            actual = hashlib.sha256(data).hexdigest()
            if actual != metadata["checksum"]:
                raise ValueError(f"Checksum mismatch: {key}")

        return data, metadata

    async def delete(self, key: str, version: str | None = None) -> bool:
        """Delete data from Redis."""
        client = await self._ensure_connected()

        if version:
            # Delete specific version
            data_key = f"{key}:{version}:data"
            meta_key = f"{key}:{version}:meta"
            deleted = await client.delete(data_key, meta_key)
            return deleted > 0
        else:
            # Delete all versions
            pattern = f"{key}:*"
            cursor = 0
            deleted = False
            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)
                if keys:
                    await client.delete(*keys)
                    deleted = True
                if cursor == 0:
                    break
            return deleted

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        client = await self._ensure_connected()
        if self.config.enable_versioning:
            return await client.exists(f"{key}:latest") > 0
        return await client.exists(f"{key}:data") > 0

    async def list_keys(
        self,
        prefix: str | None = None,
        limit: int | None = None,
    ) -> list[str]:
        """List all keys with optional prefix."""
        client = await self._ensure_connected()

        # Scan for keys
        pattern = (
            f"{prefix or ''}*:latest" if self.config.enable_versioning else f"{prefix or ''}*:data"
        )
        keys = set()
        cursor = 0

        while True:
            cursor, batch = await client.scan(cursor, match=pattern, count=100)
            for key_bytes in batch:
                key_str = key_bytes.decode("utf-8")
                # Extract base key
                base_key = key_str.split(":")[0]
                keys.add(base_key)

            if cursor == 0 or (limit and len(keys) >= limit):
                break

        result = sorted(keys)
        if limit:
            result = result[:limit]
        return result

    async def list_versions(self, key: str) -> list[str]:
        """List all versions of a key."""
        client = await self._ensure_connected()
        versions_key = f"{key}:versions"
        versions_bytes = await client.lrange(versions_key, 0, -1)
        return [v.decode("utf-8") for v in versions_bytes]

    async def get_metadata(self, key: str, version: str | None = None) -> dict[str, Any]:
        """Get metadata without loading data."""
        client = await self._ensure_connected()

        if version is None and self.config.enable_versioning:
            version = await client.get(f"{key}:latest")
            if version:
                version = version.decode("utf-8")

        if version:
            meta_key = f"{key}:{version}:meta"
        else:
            meta_key = f"{key}:meta"

        meta_bytes = await client.get(meta_key)
        if meta_bytes is None:
            raise KeyNotFoundError(f"Key not found: {key}")

        return json.loads(meta_bytes.decode("utf-8"))

    async def get_size(self, key: str, version: str | None = None) -> int:
        """Get size of stored data."""
        metadata = await self.get_metadata(key, version)
        return metadata.get("size", 0)

    async def close(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            self.client = None

    async def _prune_versions(self, key: str) -> None:
        """Prune old versions beyond max_versions."""
        client = await self._ensure_connected()
        versions_key = f"{key}:versions"

        # Get version count
        count = await client.llen(versions_key)
        if count <= self.config.max_versions:
            return

        # Delete oldest versions
        to_delete = count - self.config.max_versions
        for _ in range(to_delete):
            old_version_bytes = await client.rpop(versions_key)
            if old_version_bytes:
                old_version = old_version_bytes.decode("utf-8")
                await self.delete(key, old_version)
