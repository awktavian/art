"""Colony state repository with CRDT synchronization.

Created: December 28, 2025
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.database.models import ColonyState
from kagami.core.storage.base import BaseRepository, CacheStrategy

logger = logging.getLogger(__name__)


class ColonyStateRepository(BaseRepository[ColonyState]):
    """Repository for ColonyState storage with CRDT synchronization.

    Storage architecture:
    - Primary: CockroachDB (transactional)
    - L2 Cache: Redis (fast lookup)
    - Sync: etcd (CRDT state synchronization)

    Cache strategy: WRITE_THROUGH
    - Frequent reads for coordination
    - Moderate writes for state updates
    - Immediate consistency for colony coordination
    """

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
        etcd_client: Any | None = None,
    ):
        """Initialize colony state repository.

        Args:
            db_session: CockroachDB session
            redis_client: Optional Redis client for L2 cache
            etcd_client: Optional etcd client for CRDT sync
        """
        super().__init__(
            storage_backend=db_session,
            cache_strategy=CacheStrategy.WRITE_THROUGH,
            ttl=60,  # 1 minute (frequent updates)
            l1_max_size=100,
            redis_client=redis_client,
        )
        self.db_session = db_session
        self.etcd_client = etcd_client
        logger.info("ColonyStateRepository initialized")

    # ========== Primary Operations ==========

    async def get_by_id(self, state_id: UUID | str) -> ColonyState | None:
        """Get colony state by ID.

        Args:
            state_id: Colony state UUID

        Returns:
            ColonyState or None
        """
        if isinstance(state_id, str):
            state_id = UUID(state_id)

        return await self.get(str(state_id))

    async def get_by_colony_instance(self, colony_id: str, instance_id: str) -> ColonyState | None:
        """Get colony state by colony and instance ID.

        Args:
            colony_id: Colony identifier (e.g., "spark", "forge")
            instance_id: Instance identifier (e.g., "spark-001")

        Returns:
            ColonyState or None
        """
        stmt = select(ColonyState).where(
            ColonyState.colony_id == colony_id,
            ColonyState.instance_id == instance_id,
        )
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_colonies(self, colony_id: str | None = None) -> list[ColonyState]:
        """Get active colony states.

        Args:
            colony_id: Optional colony filter

        Returns:
            List of active colony states
        """
        stmt = select(ColonyState).where(ColonyState.is_active == True)  # noqa: E712

        if colony_id:
            stmt = stmt.where(ColonyState.colony_id == colony_id)

        stmt = stmt.order_by(ColonyState.timestamp.desc())
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_colony_instances(self, colony_id: str) -> list[ColonyState]:
        """Get all instances of a colony.

        Args:
            colony_id: Colony identifier

        Returns:
            List of colony state instances
        """
        stmt = (
            select(ColonyState)
            .where(ColonyState.colony_id == colony_id)
            .order_by(ColonyState.timestamp.desc())
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def save_colony_state(self, state: ColonyState) -> ColonyState:
        """Save colony state with etcd synchronization.

        Args:
            state: Colony state to save

        Returns:
            Saved colony state
        """
        # Save to primary storage
        await self.set(str(state.id), state)

        # Sync to etcd if available
        if self.etcd_client:
            await self._sync_to_etcd(state)

        return state

    async def update_heartbeat(self, colony_id: str, instance_id: str) -> bool:
        """Update last heartbeat timestamp for a colony instance.

        Args:
            colony_id: Colony identifier
            instance_id: Instance identifier

        Returns:
            True if updated successfully
        """
        from datetime import datetime

        state = await self.get_by_colony_instance(colony_id, instance_id)
        if state:
            state.last_heartbeat_at = datetime.utcnow()
            await self.save_colony_state(state)
            return True
        return False

    async def mark_inactive(self, colony_id: str, instance_id: str) -> bool:
        """Mark a colony instance as inactive.

        Args:
            colony_id: Colony identifier
            instance_id: Instance identifier

        Returns:
            True if marked inactive
        """
        state = await self.get_by_colony_instance(colony_id, instance_id)
        if state:
            state.is_active = False
            await self.save_colony_state(state)
            return True
        return False

    # ========== Storage Operations (L3) ==========

    async def _fetch_from_storage(self, key: str) -> ColonyState | None:
        """Fetch colony state from CockroachDB.

        Args:
            key: Colony state ID

        Returns:
            ColonyState or None
        """
        try:
            state_id = UUID(key)
            stmt = select(ColonyState).where(ColonyState.id == state_id)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Colony state fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: ColonyState) -> None:
        """Write colony state to CockroachDB.

        Args:
            key: Colony state ID
            value: Colony state to store
        """
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Colony state write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete colony state from CockroachDB.

        Args:
            key: Colony state ID

        Returns:
            True if deleted
        """
        try:
            state_id = UUID(key)
            stmt = select(ColonyState).where(ColonyState.id == state_id)
            result = await self.db_session.execute(stmt)
            state = result.scalar_one_or_none()

            if state:
                await self.db_session.delete(state)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Colony state delete failed: {e}")
            return False

    # ========== CRDT Synchronization ==========

    async def _sync_to_etcd(self, state: ColonyState) -> None:
        """Sync colony state to etcd for CRDT coordination.

        Args:
            state: Colony state to sync
        """
        if not self.etcd_client:
            return

        key = f"/colonies/{state.colony_id}/{state.instance_id}"
        value = await self._serialize(state)

        try:
            await self.etcd_client.put(key, value)
        except Exception as e:
            logger.debug(f"etcd sync failed: {e}")

    # ========== Serialization ==========

    async def _serialize(self, value: ColonyState) -> str:
        """Serialize colony state for caching.

        Args:
            value: Colony state to serialize

        Returns:
            JSON string
        """
        import json

        return json.dumps(
            {
                "id": str(value.id),
                "colony_id": value.colony_id,
                "instance_id": value.instance_id,
                "node_id": value.node_id,
                "z_state": value.z_state,
                "z_dim": value.z_dim,
                "timestamp": value.timestamp,
                "vector_clock": value.vector_clock,
                "action_history": value.action_history,
                "last_action": value.last_action,
                "fano_neighbors": value.fano_neighbors,
                "is_active": value.is_active,
                "last_heartbeat_at": (
                    value.last_heartbeat_at.isoformat() if value.last_heartbeat_at else None
                ),
                "state_metadata": value.state_metadata,
            },
            default=str,
        )

    async def _deserialize(self, data: str) -> ColonyState:
        """Deserialize colony state from cache.

        Args:
            data: Serialized colony state

        Returns:
            ColonyState object
        """
        import json
        from datetime import datetime

        state_dict = json.loads(data)

        # Convert ISO timestamp back to datetime
        if state_dict.get("last_heartbeat_at"):
            state_dict["last_heartbeat_at"] = datetime.fromisoformat(
                state_dict["last_heartbeat_at"]
            )

        return ColonyState(**state_dict)


__all__ = ["ColonyStateRepository"]
