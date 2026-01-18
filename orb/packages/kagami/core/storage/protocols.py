"""Repository protocol interfaces for type-safe storage operations.

Created: December 15, 2025
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class Repository(Protocol[T]):
    """Base repository protocol for data access.

    All repositories must implement this interface for type safety
    and swappable implementations.
    """

    async def get(self, key: str) -> T | None:
        """Retrieve entity by key.

        Args:
            key: Unique identifier

        Returns:
            Entity or None if not found
        """
        ...

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Store entity with optional TTL.

        Args:
            key: Unique identifier
            value: Entity to store
            ttl: Time-to-live in seconds (optional)
        """
        ...

    async def delete(self, key: str) -> bool:
        """Delete entity by key.

        Args:
            key: Unique identifier

        Returns:
            True if deleted, False if not found
        """
        ...

    async def exists(self, key: str) -> bool:
        """Check if entity exists.

        Args:
            key: Unique identifier

        Returns:
            True if exists, False otherwise
        """
        ...


class SearchableRepository(Protocol[T]):
    """Repository with search capabilities."""

    async def find(self, **filters: Any) -> list[T]:
        """Query entities with filters.

        Args:
            **filters: Query filters

        Returns:
            List of matching entities
        """
        ...

    async def search_semantic(
        self,
        query: str,
        limit: int = 10,
        **kwargs: Any,
    ) -> list[T]:
        """Semantic search using vector similarity.

        Args:
            query: Search query
            limit: Maximum results
            **kwargs: Additional search parameters

        Returns:
            List of semantically similar entities
        """
        ...


class BatchRepository(Protocol[T]):
    """Repository with batch operations."""

    async def get_many(self, keys: list[str]) -> dict[str, T]:
        """Retrieve multiple entities.

        Args:
            keys: List of identifiers

        Returns:
            Dict mapping keys to entities
        """
        ...

    async def set_many(self, items: dict[str, T], ttl: int | None = None) -> None:
        """Store multiple entities.

        Args:
            items: Dict mapping keys to entities
            ttl: Time-to-live in seconds (optional)
        """
        ...

    async def delete_many(self, keys: list[str]) -> int:
        """Delete multiple entities.

        Args:
            keys: List of identifiers

        Returns:
            Number of entities deleted
        """
        ...


__all__ = [
    "BatchRepository",
    "Repository",
    "SearchableRepository",
]
