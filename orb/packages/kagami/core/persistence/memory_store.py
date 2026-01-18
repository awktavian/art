"""Memory and stigmergy persistence.

CREATED: December 28, 2025
PURPOSE: Persist collective memory patterns and stigmergy traces.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from kagami.core.persistence.backends.protocol import StorageBackend
from kagami.core.persistence.serializers import JSONSerializer


@dataclass
class StigmergySnapshot:
    """Snapshot of stigmergy patterns."""

    patterns: dict[str, Any]  # action -> pattern data
    density: float
    cooperation_metric: float
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


class MemoryStore:
    """Store for memory and stigmergy."""

    def __init__(self, backend: StorageBackend):
        self.backend = backend
        self.serializer = JSONSerializer(indent=2)

    async def save_stigmergy(
        self,
        snapshot_id: str,
        patterns: dict[str, Any],
        density: float,
        cooperation_metric: float,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save stigmergy snapshot."""
        snapshot = {
            "patterns": patterns,
            "density": density,
            "cooperation_metric": cooperation_metric,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }

        data = self.serializer.serialize(snapshot)
        key = f"stigmergy/{snapshot_id}"
        return await self.backend.save(key, data, metadata)

    async def load_stigmergy(
        self,
        snapshot_id: str,
        version: str | None = None,
    ) -> StigmergySnapshot:
        """Load stigmergy snapshot."""
        key = f"stigmergy/{snapshot_id}"
        data, _ = await self.backend.load(key, version)
        snapshot = self.serializer.deserialize(data)

        return StigmergySnapshot(
            patterns=snapshot["patterns"],
            density=snapshot["density"],
            cooperation_metric=snapshot["cooperation_metric"],
            timestamp=snapshot["timestamp"],
            metadata=snapshot.get("metadata", {}),
        )

    async def list_snapshots(self, limit: int | None = None) -> list[str]:
        """List stigmergy snapshots."""
        keys = await self.backend.list_keys(prefix="stigmergy/", limit=limit)
        return [k.replace("stigmergy/", "") for k in keys]
