"""Receipt repository with dual-write (CockroachDB + Weaviate + Redis + etcd).

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.database.models import Receipt
from kagami.core.storage.base import BaseRepository, CacheStrategy
from kagami.core.storage.routing import get_storage_router

logger = logging.getLogger(__name__)


class ReceiptRepository(BaseRepository[Receipt]):
    """Repository for Receipt storage with multi-backend strategy.

    Storage architecture:
    - Primary: CockroachDB (transactional, audit log)
    - Secondary: Weaviate (semantic search)
    - L2 Cache: Redis (fast lookup)
    - Sync: etcd (cross-instance learning)

    Cache strategy: READ_THROUGH
    - High read:write ratio
    - Receipts are immutable after creation
    - Fast lookups for analytics and learning
    """

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
        etcd_client: Any | None = None,
    ):
        """Initialize receipt repository.

        Args:
            db_session: CockroachDB session
            redis_client: Optional Redis client for L2 cache
            etcd_client: Optional etcd client for cross-instance sync
        """
        super().__init__(
            storage_backend=db_session,
            cache_strategy=CacheStrategy.READ_THROUGH,
            ttl=300,  # 5 minutes
            l1_max_size=1000,
            redis_client=redis_client,
        )
        self.db_session = db_session
        self.etcd_client = etcd_client
        self._router = get_storage_router()

        logger.info("ReceiptRepository initialized")

    # ========== Primary Operations ==========

    async def get_by_id(self, receipt_id: UUID | str) -> Receipt | None:
        """Get receipt by ID.

        Args:
            receipt_id: Receipt UUID

        Returns:
            Receipt or None
        """
        if isinstance(receipt_id, str):
            receipt_id = UUID(receipt_id)

        return await self.get(str(receipt_id))

    async def get_by_correlation_id(self, correlation_id: str) -> list[Receipt]:
        """Get all receipts for a correlation ID (PLAN, EXECUTE, VERIFY).

        Args:
            correlation_id: Correlation ID

        Returns:
            List of receipts (typically 3)
        """
        stmt = select(Receipt).where(Receipt.correlation_id == correlation_id)
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_receipt_chain(self, correlation_id: str) -> list[Receipt]:
        """Get receipt chain by traversing parent_receipt_id links.

        Reconstructs the DAG from child to root by following parent_receipt_id.
        Returns receipts in order: PLAN → EXECUTE → VERIFY (root to leaf).

        Args:
            correlation_id: Starting correlation ID

        Returns:
            Ordered list[Any] of receipts from root (PLAN) to leaf (VERIFY)
        """
        # Get all receipts for this correlation_id
        receipts = await self.get_by_correlation_id(correlation_id)

        if not receipts:
            return []

        # Build parent → child mapping
        receipt_map = {str(r.id): r for r in receipts}
        children_map: dict[str | None, list[Receipt]] = {}

        for receipt in receipts:
            parent_id = receipt.parent_receipt_id
            if parent_id not in children_map:
                children_map[parent_id] = []  # type: ignore[index]
            children_map[parent_id].append(receipt)  # type: ignore[index]

        # Find root (receipt with no parent or parent not in set[Any])
        root_candidates = [
            r
            for r in receipts
            if r.parent_receipt_id is None or r.parent_receipt_id not in receipt_map
        ]

        if not root_candidates:
            # Fallback: sort by timestamp
            logger.warning(
                f"No root receipt found for correlation_id={correlation_id}, "
                f"falling back to timestamp sort"
            )
            receipts.sort(key=lambda r: r.ts if r.ts else datetime.min)
            return receipts

        # Start from root and traverse
        root = root_candidates[0]
        chain: list[Receipt] = [root]

        # BFS traversal to maintain order
        current_id = str(root.id)
        while current_id in children_map:
            children = children_map[current_id]
            # Sort children by timestamp to ensure stable order
            children.sort(key=lambda r: r.ts if r.ts else datetime.min)
            for child in children:
                chain.append(child)
                current_id = str(child.id)

        return chain

    async def save_receipt(self, receipt: Receipt) -> Receipt:
        """Save receipt with multi-backend strategy.

        OPTIMIZED (Dec 20, 2025): Parallel writes to all backends for better throughput.

        1. Persist to CockroachDB (primary)
        2. Cache in Redis (L2)
        3. Index in Weaviate (semantic search)
        4. Sync to etcd (cross-instance learning)

        Args:
            receipt: Receipt to save

        Returns:
            Saved receipt

        Raises:
            IntegrityError: If duplicate receipt (same correlation_id, phase, ts)
                           is silently handled and existing receipt returned
        """

        # 1. Primary: CockroachDB (with duplicate handling)
        try:
            await self.set(str(receipt.id), receipt)
        except IntegrityError as e:
            # Check if this is the correlation_id uniqueness constraint
            error_msg = str(e)
            is_duplicate = (
                "idx_receipts_correlation_uniqueness" in error_msg
                or "duplicate key" in error_msg.lower()
            )
            if is_duplicate:
                logger.warning(
                    f"Duplicate receipt detected: correlation_id={receipt.correlation_id} "
                    f"phase={receipt.phase} ts={receipt.ts} (returning existing receipt)"
                )
                # Return existing receipt from database
                existing_receipts = await self.get_by_correlation_id(
                    receipt.correlation_id,  # type: ignore[arg-type]
                )
                # Find the one matching phase and timestamp
                for existing in existing_receipts:
                    if existing.phase == receipt.phase and existing.ts == receipt.ts:
                        return existing
                # If not found, return the first one (shouldn't happen but defensive)
                if existing_receipts:
                    return existing_receipts[0]
                # Last resort: return the input receipt
                return receipt
            # Re-raise if it's a different integrity error
            raise

        # 2-4. PARALLEL writes to secondary backends (non-blocking)
        # Use gather with return_exceptions=True to avoid failing on secondary backend errors
        async def _safe_weaviate_index() -> None:
            try:
                await self._index_in_weaviate(receipt)
            except Exception as e:
                logger.warning(f"Weaviate indexing failed: {e}")

        async def _safe_etcd_sync() -> None:
            if self.etcd_client is not None:
                try:
                    await self._sync_to_etcd(receipt)
                except Exception as e:
                    logger.warning(f"etcd sync failed: {e}")

        # Parallel execution of secondary writes (non-blocking)
        await asyncio.gather(
            _safe_weaviate_index(),
            _safe_etcd_sync(),
            return_exceptions=True,
        )

        return receipt

    async def search_semantic(
        self,
        query: str,
        limit: int = 50,
        colony_filter: str | None = None,
        tenant_id: str | None = None,
    ) -> list[Receipt]:
        """Semantic search for receipts via Weaviate.

        Args:
            query: Search query
            limit: Max results
            colony_filter: Optional colony filter
            tenant_id: Optional tenant filter

        Returns:
            List of matching receipts
        """
        try:
            results = await self._router.search_semantic(
                query=query,
                limit=limit,
                colony_filter=colony_filter,
                kind_filter="receipt",
                tenant_id=tenant_id,
            )

            # Enrich with full data from CockroachDB if needed
            receipt_ids = [r.get("source_id") for r in results if r.get("source_id")]

            if not receipt_ids:
                return []

            stmt = select(Receipt).where(Receipt.correlation_id.in_(receipt_ids))
            result = await self.db_session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def find_by_phase(
        self,
        phase: str,
        limit: int = 100,
    ) -> list[Receipt]:
        """Find receipts by phase (PLAN, EXECUTE, VERIFY).

        Args:
            phase: Phase name
            limit: Max results

        Returns:
            List of receipts
        """
        stmt = select(Receipt).where(Receipt.phase == phase).limit(limit)
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_action(
        self,
        action: str,
        limit: int = 100,
    ) -> list[Receipt]:
        """Find receipts by action.

        Args:
            action: Action name
            limit: Max results

        Returns:
            List of receipts
        """
        stmt = select(Receipt).where(Receipt.action == action).limit(limit)
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_status(
        self,
        status: str,
        limit: int = 100,
    ) -> list[Receipt]:
        """Find receipts by status.

        Args:
            status: Status string
            limit: Max results

        Returns:
            List of receipts
        """
        stmt = select(Receipt).where(Receipt.status == status).limit(limit)
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def find_recent(
        self,
        limit: int = 100,
        hours: int = 24,
    ) -> list[Receipt]:
        """Find recent receipts (most recent first).

        Args:
            limit: Max results
            hours: Lookback window in hours (default 24)

        Returns:
            List of receipts ordered by timestamp descending
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        stmt = select(Receipt).where(Receipt.ts >= cutoff).order_by(Receipt.ts.desc()).limit(limit)
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    # ========== Storage Operations (L3) ==========

    async def _fetch_from_storage(self, key: str) -> Receipt | None:
        """Fetch receipt from CockroachDB.

        Args:
            key: Receipt ID

        Returns:
            Receipt or None
        """
        try:
            receipt_id = UUID(key)
            stmt = select(Receipt).where(Receipt.id == receipt_id)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Receipt fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: Receipt) -> None:
        """Write receipt to CockroachDB.

        Args:
            key: Receipt ID
            value: Receipt to store
        """
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Receipt write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete receipt from CockroachDB.

        Args:
            key: Receipt ID

        Returns:
            True if deleted
        """
        try:
            receipt_id = UUID(key)
            stmt = select(Receipt).where(Receipt.id == receipt_id)
            result = await self.db_session.execute(stmt)
            receipt = result.scalar_one_or_none()

            if receipt is not None:
                await self.db_session.delete(receipt)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Receipt delete failed: {e}")
            return False

    # ========== Multi-Backend Sync ==========

    async def _index_in_weaviate(self, receipt: Receipt) -> None:
        """Index receipt in Weaviate for semantic search.

        Args:
            receipt: Receipt to index
        """
        receipt_dict = {
            "correlation_id": receipt.correlation_id,
            "phase": receipt.phase,
            "action": receipt.action or "unknown",
            "status": receipt.status or "unknown",
            "event_name": receipt.action or "unknown",
            "colony": "nexus",  # Default, override if available in intent
        }

        await self._router.store_receipt_to_weaviate(receipt_dict)

    async def _sync_to_etcd(self, receipt: Receipt) -> None:
        """Sync receipt to etcd for cross-instance learning.

        Args:
            receipt: Receipt to sync
        """
        if self.etcd_client is None:
            return

        key = f"/receipts/{receipt.correlation_id}/{receipt.phase}"
        value = await self._serialize(receipt)

        try:
            await self.etcd_client.put(key, value)
        except Exception as e:
            logger.debug(f"etcd sync failed: {e}")

    # ========== Serialization ==========

    async def _serialize(self, value: Receipt) -> str:
        """Serialize receipt for caching.

        Args:
            value: Receipt to serialize

        Returns:
            JSON string
        """
        import json

        return json.dumps(
            {
                "id": str(value.id),
                "correlation_id": value.correlation_id,
                "parent_receipt_id": value.parent_receipt_id,
                "phase": value.phase,
                "action": value.action,
                "app": value.app,
                "status": value.status,
                "intent": value.intent,
                "event": value.event,
                "data": value.data,
                "metrics": value.metrics,
                "duration_ms": value.duration_ms,
                "ts": value.ts.isoformat() if value.ts else None,
            },
            default=str,
        )

    async def _deserialize(self, data: str) -> Receipt:
        """Deserialize receipt from cache.

        Args:
            data: Serialized receipt

        Returns:
            Receipt object
        """
        import json
        from datetime import datetime

        receipt_dict = json.loads(data)

        # Convert ISO timestamp back to datetime
        if receipt_dict.get("ts"):
            receipt_dict["ts"] = datetime.fromisoformat(receipt_dict["ts"])

        return Receipt(**receipt_dict)


__all__ = ["ReceiptRepository"]
