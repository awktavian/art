"""Memory backend protocol definitions.

Defines abstract interfaces for stigmergy memory storage backends.
Enables pluggable storage: in-memory, SQLite, Redis, Weaviate, etc.

Created: December 15, 2025
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Protocol


class MemoryBackend(Protocol):
    """Protocol for stigmergy memory storage backends.

    All backends must implement:
    - connect() -> bool: Establish connection
    - disconnect() -> None: Clean shutdown
    - save_pattern() -> bool: Persist a pattern
    - load_patterns() -> dict[str, Any]: Load all patterns
    - clear() -> None: Clear all data
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to backend.

        Returns:
            True if connected successfully, False otherwise
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and cleanup resources."""
        ...

    @abstractmethod
    async def save_pattern(
        self,
        action: str,
        domain: str,
        pattern_data: dict[str, Any],
    ) -> bool:
        """Save a single pattern to backend.

        Args:
            action: Action identifier
            domain: Domain/colony identifier
            pattern_data: Pattern attributes (success_count, failure_count, etc.)

        Returns:
            True if saved successfully, False otherwise
        """
        ...

    @abstractmethod
    async def load_patterns(self) -> dict[tuple[str, str], dict[str, Any]]:
        """Load all patterns from backend.

        Returns:
            Dict mapping (action, domain) to pattern data
        """
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Clear all stored patterns."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if backend is currently connected."""
        ...


class ReceiptBackend(Protocol):
    """Protocol for receipt storage backends.

    Receipts are immutable audit logs of agent actions.
    Backends provide temporal querying and pattern extraction.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to backend."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and cleanup."""
        ...

    @abstractmethod
    async def save_receipt(self, receipt: dict[str, Any]) -> bool:
        """Store a receipt.

        Args:
            receipt: Receipt envelope with intent, verifier, etc.

        Returns:
            True if saved successfully
        """
        ...

    @abstractmethod
    async def load_receipts(
        self,
        max_count: int = 1000,
        since_timestamp: float | None = None,
    ) -> list[dict[str, Any]]:
        """Load recent receipts.

        Args:
            max_count: Maximum receipts to load
            since_timestamp: Only load receipts after this time

        Returns:
            List of receipt dicts
        """
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Clear all receipts."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if backend is connected."""
        ...


__all__ = [
    "MemoryBackend",
    "ReceiptBackend",
]
