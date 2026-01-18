"""Training run repository for ML training tracking.

Created: December 28, 2025
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.database.models import TrainingCheckpoint, TrainingRun
from kagami.core.storage.base import BaseRepository, CacheStrategy

logger = logging.getLogger(__name__)


class TrainingRunRepository(BaseRepository[TrainingRun]):
    """Repository for TrainingRun storage.

    Storage architecture:
    - Primary: CockroachDB (transactional)
    - L2 Cache: Redis (fast lookup)

    Cache strategy: READ_THROUGH
    - Frequent reads for monitoring
    - Infrequent writes (updates per epoch/step)
    - Eventual consistency acceptable
    """

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
    ):
        """Initialize training run repository.

        Args:
            db_session: CockroachDB session
            redis_client: Optional Redis client for L2 cache
        """
        super().__init__(
            storage_backend=db_session,
            cache_strategy=CacheStrategy.READ_THROUGH,
            ttl=300,  # 5 minutes
            l1_max_size=100,
            redis_client=redis_client,
        )
        self.db_session = db_session
        logger.info("TrainingRunRepository initialized")

    # ========== Primary Operations ==========

    async def get_by_id(self, run_id: UUID | str) -> TrainingRun | None:
        """Get training run by ID.

        Args:
            run_id: Training run UUID

        Returns:
            TrainingRun or None
        """
        if isinstance(run_id, str):
            try:
                run_id = UUID(run_id)
            except ValueError:
                # If not a UUID, try run_id lookup
                return await self.get_by_run_id(run_id)

        return await self.get(str(run_id))

    async def get_by_run_id(self, run_id: str) -> TrainingRun | None:
        """Get training run by run_id string.

        Args:
            run_id: Run identifier

        Returns:
            TrainingRun or None
        """
        stmt = select(TrainingRun).where(TrainingRun.run_id == run_id)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        user_id: UUID | None = None,
        tenant_id: str | None = None,
        status: str | None = None,
        run_type: str | None = None,
        limit: int = 100,
    ) -> list[TrainingRun]:
        """List training runs with filters.

        Args:
            user_id: Optional user filter
            tenant_id: Optional tenant filter
            status: Optional status filter
            run_type: Optional run type filter
            limit: Max results

        Returns:
            List of training runs
        """
        stmt = select(TrainingRun)

        if user_id:
            stmt = stmt.where(TrainingRun.user_id == user_id)
        if tenant_id:
            stmt = stmt.where(TrainingRun.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(TrainingRun.status == status)
        if run_type:
            stmt = stmt.where(TrainingRun.run_type == run_type)

        stmt = stmt.order_by(TrainingRun.created_at.desc()).limit(limit)
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_runs(
        self, user_id: UUID | None = None, limit: int = 50
    ) -> list[TrainingRun]:
        """Get currently running training runs.

        Args:
            user_id: Optional user filter
            limit: Max results

        Returns:
            List of active training runs
        """
        stmt = select(TrainingRun).where(TrainingRun.status == "running")

        if user_id:
            stmt = stmt.where(TrainingRun.user_id == user_id)

        stmt = stmt.order_by(TrainingRun.started_at.desc()).limit(limit)
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def create_run(self, run: TrainingRun) -> TrainingRun:
        """Create new training run.

        Args:
            run: Training run to create

        Returns:
            Created training run
        """
        await self.set(str(run.id), run)
        return run

    async def update_run(self, run: TrainingRun) -> TrainingRun:
        """Update training run.

        Args:
            run: Training run to update

        Returns:
            Updated training run
        """
        await self.set(str(run.id), run)
        return run

    async def update_progress(
        self,
        run_id: str,
        current_step: int,
        current_epoch: int | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> bool:
        """Update training progress.

        Args:
            run_id: Run identifier
            current_step: Current training step
            current_epoch: Current epoch (optional)
            metrics: Latest metrics (optional)

        Returns:
            True if updated
        """
        run = await self.get_by_run_id(run_id)
        if not run:
            return False

        run.current_step = current_step
        if current_epoch is not None:
            run.current_epoch = current_epoch

        if metrics:
            # Merge metrics
            run_metrics = run.metrics or {}
            run_metrics.update(metrics)
            run.metrics = run_metrics

        # Calculate progress
        if run.total_steps and run.total_steps > 0:
            run.progress = min(current_step / run.total_steps, 1.0)

        await self.update_run(run)
        return True

    async def mark_completed(
        self, run_id: str, final_metrics: dict[str, Any] | None = None
    ) -> bool:
        """Mark training run as completed.

        Args:
            run_id: Run identifier
            final_metrics: Final metrics (optional)

        Returns:
            True if marked completed
        """
        from datetime import datetime

        run = await self.get_by_run_id(run_id)
        if not run:
            return False

        run.status = "completed"
        run.progress = 1.0
        run.completed_at = datetime.utcnow()

        if final_metrics:
            run.final_loss = final_metrics.get("loss")
            run.best_accuracy = final_metrics.get("accuracy")

        await self.update_run(run)
        return True

    async def mark_failed(
        self, run_id: str, error_message: str, error_traceback: str | None = None
    ) -> bool:
        """Mark training run as failed.

        Args:
            run_id: Run identifier
            error_message: Error message
            error_traceback: Error traceback (optional)

        Returns:
            True if marked failed
        """
        from datetime import datetime

        run = await self.get_by_run_id(run_id)
        if not run:
            return False

        run.status = "failed"
        run.error_message = error_message
        run.error_traceback = error_traceback
        run.completed_at = datetime.utcnow()

        await self.update_run(run)
        return True

    # ========== Storage Operations (L3) ==========

    async def _fetch_from_storage(self, key: str) -> TrainingRun | None:
        """Fetch training run from CockroachDB.

        Args:
            key: Training run ID

        Returns:
            TrainingRun or None
        """
        try:
            run_id = UUID(key)
            stmt = select(TrainingRun).where(TrainingRun.id == run_id)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Training run fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: TrainingRun) -> None:
        """Write training run to CockroachDB.

        Args:
            key: Training run ID
            value: Training run to store
        """
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Training run write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete training run from CockroachDB.

        Args:
            key: Training run ID

        Returns:
            True if deleted
        """
        try:
            run_id = UUID(key)
            stmt = select(TrainingRun).where(TrainingRun.id == run_id)
            result = await self.db_session.execute(stmt)
            run = result.scalar_one_or_none()

            if run:
                await self.db_session.delete(run)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Training run delete failed: {e}")
            return False


class TrainingCheckpointRepository(BaseRepository[TrainingCheckpoint]):
    """Repository for TrainingCheckpoint storage."""

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
    ):
        """Initialize training checkpoint repository.

        Args:
            db_session: CockroachDB session
            redis_client: Optional Redis client for L2 cache
        """
        super().__init__(
            storage_backend=db_session,
            cache_strategy=CacheStrategy.READ_THROUGH,
            ttl=600,  # 10 minutes
            l1_max_size=200,
            redis_client=redis_client,
        )
        self.db_session = db_session
        logger.info("TrainingCheckpointRepository initialized")

    async def get_checkpoints_for_run(
        self, run_id: str, limit: int = 50
    ) -> list[TrainingCheckpoint]:
        """Get checkpoints for a training run.

        Args:
            run_id: Run identifier
            limit: Max results

        Returns:
            List of checkpoints
        """
        stmt = (
            select(TrainingCheckpoint)
            .where(TrainingCheckpoint.run_id == run_id)
            .order_by(TrainingCheckpoint.step.desc())
            .limit(limit)
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_best_checkpoint(self, run_id: str) -> TrainingCheckpoint | None:
        """Get best checkpoint for a training run.

        Args:
            run_id: Run identifier

        Returns:
            Best checkpoint or None
        """
        stmt = select(TrainingCheckpoint).where(
            TrainingCheckpoint.run_id == run_id,
            TrainingCheckpoint.is_best == True,  # noqa: E712
        )
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_checkpoint(self, checkpoint: TrainingCheckpoint) -> TrainingCheckpoint:
        """Create new checkpoint.

        Args:
            checkpoint: Checkpoint to create

        Returns:
            Created checkpoint
        """
        await self.set(str(checkpoint.id), checkpoint)
        return checkpoint

    async def _fetch_from_storage(self, key: str) -> TrainingCheckpoint | None:
        """Fetch checkpoint from storage."""
        try:
            checkpoint_id = UUID(key)
            stmt = select(TrainingCheckpoint).where(TrainingCheckpoint.id == checkpoint_id)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Checkpoint fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: TrainingCheckpoint) -> None:
        """Write checkpoint to storage."""
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Checkpoint write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete checkpoint from storage."""
        try:
            checkpoint_id = UUID(key)
            stmt = select(TrainingCheckpoint).where(TrainingCheckpoint.id == checkpoint_id)
            result = await self.db_session.execute(stmt)
            checkpoint = result.scalar_one_or_none()

            if checkpoint:
                await self.db_session.delete(checkpoint)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Checkpoint delete failed: {e}")
            return False


__all__ = ["TrainingCheckpointRepository", "TrainingRunRepository"]
