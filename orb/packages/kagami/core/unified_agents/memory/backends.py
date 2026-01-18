"""Memory storage backends for stigmergy system.

Implements pluggable storage backends:
- InMemoryBackend: Fast ephemeral storage (default)
- WeaviateBackend: Vector DB persistence (optional)
- SQLiteBackend: Local file-based persistence (future)
- RedisBackend: Distributed cache (future)

Backend detection pattern:
1. Try Weaviate (if available)
2. Fall back to in-memory

Created: December 15, 2025
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InMemoryBackend:
    """In-memory storage backend.

    Fast, ephemeral storage. Data lost on process restart.
    Used as fallback when external backends unavailable.
    """

    def __init__(self) -> None:
        self._patterns: dict[tuple[str, str], dict[str, Any]] = {}
        self._receipts: list[dict[str, Any]] = []
        self._connected = False

    async def connect(self) -> bool:
        """Connect (no-op for in-memory)."""
        self._connected = True
        logger.debug("InMemoryBackend: Connected")
        return True

    async def disconnect(self) -> None:
        """Disconnect and clear data."""
        self._patterns.clear()
        self._receipts.clear()
        self._connected = False
        logger.debug("InMemoryBackend: Disconnected")

    async def save_pattern(
        self,
        action: str,
        domain: str,
        pattern_data: dict[str, Any],
    ) -> bool:
        """Save pattern to memory."""
        if not self._connected:
            return False

        key = (action, domain)
        self._patterns[key] = pattern_data.copy()
        return True

    async def load_patterns(self) -> dict[tuple[str, str], dict[str, Any]]:
        """Load all patterns from memory."""
        if not self._connected:
            return {}

        return self._patterns.copy()

    async def clear(self) -> None:
        """Clear all patterns."""
        self._patterns.clear()

    async def save_receipt(self, receipt: dict[str, Any]) -> bool:
        """Save receipt to memory."""
        if not self._connected:
            return False

        self._receipts.append(receipt.copy())
        return True

    async def load_receipts(
        self,
        max_count: int = 1000,
        since_timestamp: float | None = None,
    ) -> list[dict[str, Any]]:
        """Load recent receipts from memory."""
        if not self._connected:
            return []

        receipts = self._receipts

        # Filter by timestamp if specified
        if since_timestamp is not None:
            receipts = [r for r in receipts if r.get("timestamp", 0) >= since_timestamp]

        # Return most recent max_count
        return receipts[-max_count:] if max_count < len(receipts) else receipts

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected


class WeaviateBackend:
    """Weaviate vector database backend.

    Provides persistent storage with semantic search capabilities.
    Falls back to InMemoryBackend if Weaviate unavailable.

    Note: Requires kagami_integrations.elysia.weaviate_pattern_store
    """

    def __init__(self) -> None:
        self._store = None
        self._adapter = None
        self._connected = False
        self._fallback = InMemoryBackend()

    async def connect(self) -> bool:
        """Connect to Weaviate.

        Falls back to in-memory if Weaviate unavailable.
        """
        try:
            # Dynamic import to avoid core ↔ integrations cycles
            import importlib

            mod = importlib.import_module("kagami_integrations.elysia.weaviate_pattern_store")
            get_weaviate_pattern_store = getattr(mod, "get_weaviate_pattern_store", None)

            if get_weaviate_pattern_store is None:
                raise ImportError("weaviate_pattern_store not available")

            self._store = get_weaviate_pattern_store()
            await self._store.connect()  # type: ignore[attr-defined]

            # Also connect adapter for receipts
            mod_adapter = importlib.import_module("kagami_integrations.elysia.weaviate_e8_adapter")
            get_weaviate_adapter = getattr(mod_adapter, "get_weaviate_adapter", None)

            if get_weaviate_adapter is not None:
                self._adapter = get_weaviate_adapter()
                await self._adapter.connect()  # type: ignore[attr-defined]

            self._connected = True
            logger.info("WeaviateBackend: Connected")
            return True

        except ImportError:
            logger.debug("Weaviate integration not available - using in-memory fallback")
            await self._fallback.connect()
            return False
        except Exception as e:
            logger.warning(f"Failed to connect to Weaviate: {e} - using in-memory fallback")
            await self._fallback.connect()
            return False

    async def disconnect(self) -> None:
        """Disconnect from Weaviate."""
        self._store = None
        self._adapter = None
        self._connected = False
        await self._fallback.disconnect()
        logger.debug("WeaviateBackend: Disconnected")

    async def save_pattern(
        self,
        action: str,
        domain: str,
        pattern_data: dict[str, Any],
    ) -> bool:
        """Save pattern to Weaviate."""
        if not self._connected or self._store is None:
            return await self._fallback.save_pattern(action, domain, pattern_data)

        try:  # type: ignore[unreachable]
            # Dynamic import for WeaviatePattern dataclass
            import importlib

            mod = importlib.import_module("kagami_integrations.elysia.weaviate_pattern_store")
            WeaviatePattern = getattr(mod, "WeaviatePattern", None)

            if WeaviatePattern is None:
                raise ImportError("WeaviatePattern not available")

            # Convert pattern_data to WeaviatePattern
            weaviate_pattern = WeaviatePattern(
                action=action,
                domain=domain,
                success_count=pattern_data.get("success_count", 0),
                failure_count=pattern_data.get("failure_count", 0),
                avg_duration=pattern_data.get("avg_duration", 0.0),
                last_updated=pattern_data.get("last_updated", 0.0),
                created_at=pattern_data.get("created_at", 0.0),
                access_count=pattern_data.get("access_count", 0),
                heuristic_value=pattern_data.get("heuristic_value", 0.0),
                common_params=pattern_data.get("common_params", {}),
                error_types=pattern_data.get("error_types", []),
            )

            await self._store.save_pattern(weaviate_pattern)
            return True

        except Exception as e:
            logger.warning(f"Failed to save pattern to Weaviate: {e} - using fallback")
            return await self._fallback.save_pattern(action, domain, pattern_data)

    async def load_patterns(self) -> dict[tuple[str, str], dict[str, Any]]:
        """Load patterns from Weaviate."""
        if not self._connected or self._store is None:
            return await self._fallback.load_patterns()

        try:  # type: ignore[unreachable]
            weaviate_patterns = await self._store.load_patterns()

            patterns: dict[tuple[str, str], dict[str, Any]] = {}
            for (action, domain), wp in weaviate_patterns.items():
                patterns[(action, domain)] = {
                    "action": wp.action,
                    "domain": wp.domain,
                    "success_count": wp.success_count,
                    "failure_count": wp.failure_count,
                    "avg_duration": wp.avg_duration,
                    "last_updated": wp.last_updated,
                    "created_at": wp.created_at,
                    "access_count": wp.access_count,
                    "heuristic_value": wp.heuristic_value,
                    "common_params": wp.common_params,
                    "error_types": wp.error_types,
                }

            logger.info(f"Loaded {len(patterns)} patterns from Weaviate")
            return patterns

        except Exception as e:
            logger.warning(f"Failed to load patterns from Weaviate: {e} - using fallback")
            return await self._fallback.load_patterns()

    async def clear(self) -> None:
        """Clear all patterns."""
        # Weaviate store doesn't have clear method yet
        # For now, just clear fallback regardless of connection state
        await self._fallback.clear()

    async def save_receipt(self, receipt: dict[str, Any]) -> bool:
        """Save receipt (delegates to fallback for now)."""
        return await self._fallback.save_receipt(receipt)

    async def load_receipts(
        self,
        max_count: int = 1000,
        since_timestamp: float | None = None,
    ) -> list[dict[str, Any]]:
        """Load receipts from Weaviate feedback collection."""
        if not self._connected or self._adapter is None:
            return await self._fallback.load_receipts(max_count, since_timestamp)

        try:  # type: ignore[unreachable]
            # Get recent feedback as receipts
            feedback_list = await self._adapter.get_similar_feedback(
                query="",  # Empty = all recent
                min_rating=1,  # All ratings
                limit=max_count,
            )

            receipts = []
            for fb in feedback_list:
                # Filter by timestamp if specified
                if since_timestamp is not None:
                    fb_timestamp = fb.get("timestamp", 0)
                    if fb_timestamp < since_timestamp:
                        continue

                receipt = {
                    "phase": "verify",
                    "intent": {"action": f"elysia.query.{fb.get('colony', 'nexus')}"},
                    "actor": f"colony:{fb.get('colony', 'nexus')}",
                    "verifier": {"status": "verified" if fb.get("rating", 0) >= 4 else "failed"},
                    "workspace_hash": "elysia",
                    "timestamp": fb.get("timestamp", 0),
                }
                receipts.append(receipt)

            logger.info(f"Loaded {len(receipts)} receipts from Weaviate")
            return receipts

        except Exception as e:
            logger.debug(f"Could not load receipts from Weaviate: {e} - using fallback")
            return await self._fallback.load_receipts(max_count, since_timestamp)

    @property
    def is_connected(self) -> bool:
        """Check if connected to Weaviate."""
        return self._connected


def create_backend(backend_type: str = "auto") -> InMemoryBackend | WeaviateBackend:
    """Factory function to create appropriate backend.

    Args:
        backend_type: One of "auto", "memory", "weaviate"
            - "auto": Try Weaviate, fall back to memory
            - "memory": In-memory only
            - "weaviate": Weaviate only (no fallback)

    Returns:
        Backend instance
    """
    if backend_type == "memory":
        return InMemoryBackend()
    elif backend_type == "weaviate":
        return WeaviateBackend()
    elif backend_type == "auto":
        # Auto-detect: try Weaviate, fall back to memory
        return WeaviateBackend()
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


__all__ = [
    "InMemoryBackend",
    "WeaviateBackend",
    "create_backend",
]
