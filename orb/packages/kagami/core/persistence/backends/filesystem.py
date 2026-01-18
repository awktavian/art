"""Filesystem storage backend for Kagami persistence.

CREATED: December 28, 2025
PURPOSE: Local filesystem storage with versioning and metadata.

Features:
- Simple directory-based storage
- Automatic versioning with timestamps
- Metadata stored as JSON sidecar files
- Fast for local development and testing
- No external dependencies

Storage Layout:
    data_dir/
        checkpoint_001/
            data.bin          # Binary data
            metadata.json     # Metadata
            checksum.txt      # SHA256 hash
        checkpoint_001.v001/  # Version 1
            data.bin
            metadata.json
            checksum.txt
        checkpoint_001.v002/  # Version 2
            ...
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

from kagami.core.persistence.backends.protocol import (
    KeyNotFoundError,
    StorageBackend,
    StorageConfig,
)


class FilesystemBackend(StorageBackend):
    """Filesystem storage backend."""

    def __init__(self, config: StorageConfig):
        """Initialize filesystem backend.

        Config params:
            data_dir: Root directory for storage (required)
        """
        super().__init__(config)

        data_dir = config.params.get("data_dir")
        if not data_dir:
            raise ValueError("data_dir required in config.params")

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def save(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save data to filesystem."""
        # Sanitize key to valid filename
        safe_key = self._sanitize_key(key)

        # Generate version ID (timestamp)
        version_id = f"v{int(time.time() * 1000000)}"

        # Create versioned directory
        if self.config.enable_versioning:
            key_dir = self.data_dir / f"{safe_key}.{version_id}"
        else:
            key_dir = self.data_dir / safe_key

        key_dir.mkdir(parents=True, exist_ok=True)

        # Compute checksum
        checksum = hashlib.sha256(data).hexdigest()

        # Write data file
        data_path = key_dir / "data.bin"
        await asyncio.to_thread(data_path.write_bytes, data)

        # Write metadata
        metadata = metadata or {}
        metadata.update(
            {
                "version": version_id,
                "checksum": checksum,
                "size": len(data),
                "timestamp": time.time(),
            }
        )
        metadata_path = key_dir / "metadata.json"
        await asyncio.to_thread(metadata_path.write_text, json.dumps(metadata, indent=2))

        # Write checksum
        checksum_path = key_dir / "checksum.txt"
        await asyncio.to_thread(checksum_path.write_text, checksum)

        # Update latest symlink
        if self.config.enable_versioning:
            latest_link = self.data_dir / safe_key
            if latest_link.is_symlink():
                latest_link.unlink()
            latest_link.symlink_to(key_dir.name)

        # Prune old versions
        if self.config.enable_versioning:
            await self._prune_versions(safe_key)

        return version_id

    async def load(
        self,
        key: str,
        version: str | None = None,
    ) -> tuple[bytes, dict[str, Any]]:
        """Load data from filesystem."""
        safe_key = self._sanitize_key(key)

        # Resolve key directory
        if version:
            key_dir = self.data_dir / f"{safe_key}.{version}"
        else:
            # Load latest (follow symlink if exists)
            latest_link = self.data_dir / safe_key
            if latest_link.is_symlink():
                key_dir = self.data_dir / latest_link.readlink()
            else:
                key_dir = latest_link

        if not key_dir.exists():
            raise KeyNotFoundError(f"Key not found: {key}")

        # Load data
        data_path = key_dir / "data.bin"
        if not data_path.exists():
            raise KeyNotFoundError(f"Data file not found: {key}")

        data = await asyncio.to_thread(data_path.read_bytes)

        # Load metadata
        metadata_path = key_dir / "metadata.json"
        if metadata_path.exists():
            metadata_text = await asyncio.to_thread(metadata_path.read_text)
            metadata = json.loads(metadata_text)
        else:
            metadata = {}

        # Verify checksum
        if "checksum" in metadata:
            actual_checksum = hashlib.sha256(data).hexdigest()
            if actual_checksum != metadata["checksum"]:
                raise ValueError(f"Checksum mismatch for key: {key}")

        return data, metadata

    async def delete(self, key: str, version: str | None = None) -> bool:
        """Delete data from filesystem."""
        safe_key = self._sanitize_key(key)

        if version:
            # Delete specific version
            key_dir = self.data_dir / f"{safe_key}.{version}"
            if key_dir.exists():
                await asyncio.to_thread(shutil.rmtree, key_dir)
                return True
            return False
        else:
            # Delete all versions
            deleted = False
            for path in self.data_dir.glob(f"{safe_key}*"):
                if path.is_dir():
                    await asyncio.to_thread(shutil.rmtree, path)
                    deleted = True
                elif path.is_symlink():
                    path.unlink()
                    deleted = True
            return deleted

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        safe_key = self._sanitize_key(key)
        latest_link = self.data_dir / safe_key

        # Check latest symlink or directory
        if latest_link.exists():
            return True

        # Check for any version
        for path in self.data_dir.glob(f"{safe_key}*"):
            if path.is_dir():
                return True

        return False

    async def list_keys(
        self,
        prefix: str | None = None,
        limit: int | None = None,
    ) -> list[str]:
        """List all keys with optional prefix."""
        keys = set()

        # Iterate through directories
        for path in self.data_dir.iterdir():
            if path.is_symlink():
                # Latest symlink (unsanitize key)
                key = self._unsanitize_key(path.name)
                if not prefix or key.startswith(prefix):
                    keys.add(key)
            elif path.is_dir():
                # Versioned directory - extract base key
                name = path.name
                if "." in name:
                    base_key = name.rsplit(".", 1)[0]
                else:
                    base_key = name
                key = self._unsanitize_key(base_key)
                if not prefix or key.startswith(prefix):
                    keys.add(key)

        result = sorted(keys)
        if limit:
            result = result[:limit]
        return result

    async def list_versions(self, key: str) -> list[str]:
        """List all versions of a key."""
        safe_key = self._sanitize_key(key)
        versions = []

        for path in self.data_dir.glob(f"{safe_key}.v*"):
            if path.is_dir():
                # Extract version from directory name
                version = path.name.split(".")[-1]
                versions.append(version)

        # Sort by timestamp (newest first)
        versions.sort(reverse=True)
        return versions

    async def get_metadata(self, key: str, version: str | None = None) -> dict[str, Any]:
        """Get metadata without loading data."""
        safe_key = self._sanitize_key(key)

        if version:
            key_dir = self.data_dir / f"{safe_key}.{version}"
        else:
            latest_link = self.data_dir / safe_key
            if latest_link.is_symlink():
                key_dir = self.data_dir / latest_link.readlink()
            else:
                key_dir = latest_link

        if not key_dir.exists():
            raise KeyNotFoundError(f"Key not found: {key}")

        metadata_path = key_dir / "metadata.json"
        if not metadata_path.exists():
            return {}

        metadata_text = await asyncio.to_thread(metadata_path.read_text)
        return json.loads(metadata_text)

    async def get_size(self, key: str, version: str | None = None) -> int:
        """Get size of stored data."""
        metadata = await self.get_metadata(key, version)
        return metadata.get("size", 0)

    def _sanitize_key(self, key: str) -> str:
        """Convert key to safe filename."""
        # Replace slashes with underscores
        safe = key.replace("/", "_").replace("\\", "_")
        # Remove other unsafe characters
        safe = "".join(c for c in safe if c.isalnum() or c in "._-")
        return safe

    def _unsanitize_key(self, safe_key: str) -> str:
        """Convert safe filename back to key (best effort)."""
        # This is lossy - can't perfectly reverse sanitization
        # Just return as-is for now
        return safe_key

    async def _prune_versions(self, safe_key: str) -> None:
        """Prune old versions beyond max_versions."""
        versions = await self.list_versions(self._unsanitize_key(safe_key))

        if len(versions) <= self.config.max_versions:
            return

        # Delete oldest versions in parallel
        to_delete = versions[self.config.max_versions :]
        if to_delete:
            await asyncio.gather(
                *[self.delete(self._unsanitize_key(safe_key), version) for version in to_delete],
                return_exceptions=True,
            )
