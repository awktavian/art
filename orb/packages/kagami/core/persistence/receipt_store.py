"""Receipt persistence store.

CREATED: December 28, 2025
PURPOSE: Persistent storage for execution receipts (audit trail).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from kagami.core.persistence.backends.protocol import StorageBackend
from kagami.core.persistence.serializers import JSONSerializer


@dataclass
class ReceiptSnapshot:
    """Snapshot of receipt history."""

    receipts: list[dict[str, Any]]
    start_timestamp: float
    end_timestamp: float
    count: int
    metadata: dict[str, Any]


class PersistentReceiptStore:
    """Store for receipt history."""

    def __init__(self, backend: StorageBackend):
        self.backend = backend
        self.serializer = JSONSerializer(indent=2)

    async def save_receipts(
        self,
        snapshot_id: str,
        receipts: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save receipt batch."""
        snapshot = {
            "receipts": receipts,
            "start_timestamp": receipts[0]["timestamp"] if receipts else time.time(),
            "end_timestamp": receipts[-1]["timestamp"] if receipts else time.time(),
            "count": len(receipts),
            "metadata": metadata or {},
        }

        data = self.serializer.serialize(snapshot)
        key = f"receipts/{snapshot_id}"
        return await self.backend.save(key, data, metadata)

    async def load_receipts(
        self,
        snapshot_id: str,
        version: str | None = None,
    ) -> ReceiptSnapshot:
        """Load receipt batch."""
        key = f"receipts/{snapshot_id}"
        data, _metadata = await self.backend.load(key, version)
        snapshot_dict = self.serializer.deserialize(data)

        return ReceiptSnapshot(
            receipts=snapshot_dict["receipts"],
            start_timestamp=snapshot_dict["start_timestamp"],
            end_timestamp=snapshot_dict["end_timestamp"],
            count=snapshot_dict["count"],
            metadata=snapshot_dict.get("metadata", {}),
        )

    async def list_snapshots(self, limit: int | None = None) -> list[str]:
        """List receipt snapshots."""
        keys = await self.backend.list_keys(prefix="receipts/", limit=limit)
        return [k.replace("receipts/", "") for k in keys]
