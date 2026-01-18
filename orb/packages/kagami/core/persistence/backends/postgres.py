# pyright: reportGeneralTypeIssues=false
"""PostgreSQL storage backend for Kagami persistence.

CREATED: December 28, 2025
PURPOSE: Durable SQL storage with ACID guarantees.

Uses existing kagami.core.database infrastructure for CockroachDB/PostgreSQL.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.database import get_async_session
from kagami.core.database.models import AppData  # Reuse existing table
from kagami.core.persistence.backends.protocol import (
    KeyNotFoundError,
    StorageBackend,
    StorageConfig,
)


class PostgreSQLBackend(StorageBackend):
    """PostgreSQL storage backend using existing database."""

    def __init__(self, config: StorageConfig):
        """Initialize PostgreSQL backend."""
        super().__init__(config)
        # Uses kagami.core.database connection pool

    async def save(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save data to PostgreSQL."""
        async with get_async_session() as session:
            # Generate version
            version_id = f"v{int(time.time() * 1000000)}"
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

            # Store in AppData table
            app_data = AppData(
                app_id=key if not self.config.enable_versioning else f"{key}:{version_id}",
                data_type="persistence_state",
                data_value={"metadata": metadata},
                binary_data=data,
            )
            session.add(app_data)
            await session.commit()

            # Prune old versions
            if self.config.enable_versioning:
                await self._prune_versions(session, key)

            return version_id

    async def load(
        self,
        key: str,
        version: str | None = None,
    ) -> tuple[bytes, dict[str, Any]]:
        """Load data from PostgreSQL."""
        async with get_async_session() as session:
            if version:
                pass
            else:
                # Get latest version
                if self.config.enable_versioning:
                    stmt = (
                        select(AppData)
                        .where(AppData.app_id.like(f"{key}:v%"))
                        .order_by(AppData.created_at.desc())
                        .limit(1)
                    )
                else:
                    stmt = select(AppData).where(AppData.app_id == key)

                result = await session.execute(stmt)
                app_data = result.scalar_one_or_none()

            if not version:
                if app_data is None:
                    raise KeyNotFoundError(f"Key not found: {key}")
            else:
                stmt = select(AppData).where(AppData.app_id == f"{key}:{version}")
                result = await session.execute(stmt)
                app_data = result.scalar_one_or_none()
                if app_data is None:
                    raise KeyNotFoundError(f"Version not found: {key}:{version}")

            data = app_data.binary_data
            metadata = app_data.data_value.get("metadata", {})

            # Verify checksum
            if "checksum" in metadata:
                actual = hashlib.sha256(data).hexdigest()
                if actual != metadata["checksum"]:
                    raise ValueError(f"Checksum mismatch: {key}")

            return data, metadata

    async def delete(self, key: str, version: str | None = None) -> bool:
        """Delete data from PostgreSQL."""
        async with get_async_session() as session:
            if version:
                stmt = sql_delete(AppData).where(AppData.app_id == f"{key}:{version}")
            else:
                stmt = sql_delete(AppData).where(AppData.app_id.like(f"{key}%"))
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        async with get_async_session() as session:
            stmt = select(func.count()).select_from(AppData).where(AppData.app_id.like(f"{key}%"))
            result = await session.execute(stmt)
            count = result.scalar()
            return count > 0

    async def list_keys(
        self,
        prefix: str | None = None,
        limit: int | None = None,
    ) -> list[str]:
        """List all keys."""
        async with get_async_session() as session:
            if prefix:
                stmt = select(AppData.app_id).where(AppData.app_id.like(f"{prefix}%"))
            else:
                stmt = select(AppData.app_id)

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            app_ids = result.scalars().all()

            # Extract base keys (remove version suffix)
            keys = set()
            for app_id in app_ids:
                if ":" in app_id:
                    base_key = app_id.split(":")[0]
                else:
                    base_key = app_id
                keys.add(base_key)

            return sorted(keys)

    async def list_versions(self, key: str) -> list[str]:
        """List all versions."""
        async with get_async_session() as session:
            stmt = (
                select(AppData.app_id)
                .where(AppData.app_id.like(f"{key}:v%"))
                .order_by(AppData.created_at.desc())
            )
            result = await session.execute(stmt)
            app_ids = result.scalars().all()

            # Extract version IDs
            versions = []
            for app_id in app_ids:
                if ":" in app_id:
                    version = app_id.split(":")[-1]
                    versions.append(version)

            return versions

    async def get_metadata(self, key: str, version: str | None = None) -> dict[str, Any]:
        """Get metadata."""
        async with get_async_session() as session:
            if version:
                app_id = f"{key}:{version}"
            else:
                # Get latest
                stmt = (
                    select(AppData)
                    .where(AppData.app_id.like(f"{key}%"))
                    .order_by(AppData.created_at.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                app_data = result.scalar_one_or_none()
                if app_data is None:
                    raise KeyNotFoundError(f"Key not found: {key}")
                return app_data.data_value.get("metadata", {})

            stmt = select(AppData).where(AppData.app_id == app_id)
            result = await session.execute(stmt)
            app_data = result.scalar_one_or_none()

            if app_data is None:
                raise KeyNotFoundError(f"Key not found: {key}")

            return app_data.data_value.get("metadata", {})

    async def get_size(self, key: str, version: str | None = None) -> int:
        """Get size."""
        metadata = await self.get_metadata(key, version)
        return metadata.get("size", 0)

    async def _prune_versions(self, session: AsyncSession, key: str) -> None:
        """Prune old versions."""
        # Count versions
        stmt = select(func.count()).select_from(AppData).where(AppData.app_id.like(f"{key}:v%"))
        result = await session.execute(stmt)
        count = result.scalar()

        if count <= self.config.max_versions:
            return

        # Delete oldest versions
        to_delete = count - self.config.max_versions
        stmt = (
            select(AppData.app_id)
            .where(AppData.app_id.like(f"{key}:v%"))
            .order_by(AppData.created_at.asc())
            .limit(to_delete)
        )
        result = await session.execute(stmt)
        old_ids = result.scalars().all()

        # Batch delete old versions in single statement (proper transaction use)
        if old_ids:
            stmt = sql_delete(AppData).where(AppData.app_id.in_(old_ids))
            await session.execute(stmt)
