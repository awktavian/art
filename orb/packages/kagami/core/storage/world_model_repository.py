"""World model prediction repository.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.database.models import ExpectedFreeEnergy, WorldModelPrediction
from kagami.core.storage.base import BaseRepository, CacheStrategy

logger = logging.getLogger(__name__)


class WorldModelRepository(BaseRepository[WorldModelPrediction]):
    """Repository for world model predictions.

    Storage architecture:
    - Primary: CockroachDB (relational, audit)
    - L2 Cache: Redis (fast lookups)

    Cache strategy: READ_THROUGH
    - Historical analysis
    - Append-only pattern
    - High read:write ratio for learning
    """

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
    ):
        """Initialize world model repository.

        Args:
            db_session: CockroachDB session
            redis_client: Optional Redis client for L2 cache
        """
        super().__init__(
            storage_backend=db_session,
            cache_strategy=CacheStrategy.READ_THROUGH,
            ttl=180,  # 3 minutes
            l1_max_size=500,
            redis_client=redis_client,
        )
        self.db_session = db_session
        logger.info("WorldModelRepository initialized")

    async def record_prediction(
        self,
        correlation_id: str,
        predicted_state: dict[str, Any],
        prediction_horizon: int,
        prediction_confidence: float,
        action_taken: str | None = None,
        model_version: str | None = None,
    ) -> WorldModelPrediction:
        """Record world model prediction.

        Args:
            correlation_id: Correlation ID
            predicted_state: Predicted state dict[str, Any]
            prediction_horizon: Prediction horizon steps
            prediction_confidence: Confidence score [0, 1]
            action_taken: Optional action name
            model_version: Optional model version

        Returns:
            Saved prediction
        """
        prediction = WorldModelPrediction(
            correlation_id=correlation_id,
            predicted_state=predicted_state,
            prediction_horizon=prediction_horizon,
            prediction_confidence=prediction_confidence,
            action_taken=action_taken,
            model_version=model_version,
        )

        await self._write_to_storage(str(prediction.id), prediction)
        return prediction

    async def update_with_actual(
        self,
        prediction_id: UUID | str,
        actual_state: dict[str, Any],
        prediction_error: float,
        surprise: float | None = None,
    ) -> WorldModelPrediction | None:
        """Update prediction with actual observed outcome.

        Args:
            prediction_id: Prediction ID
            actual_state: Actual observed state
            prediction_error: L2 error
            surprise: Optional surprise value

        Returns:
            Updated prediction or None
        """
        if isinstance(prediction_id, str):
            prediction_id = UUID(prediction_id)

        prediction = await self._fetch_from_storage(str(prediction_id))

        if prediction is None:
            logger.warning(f"Prediction {prediction_id} not found")
            return None

        prediction.actual_state = actual_state  # type: ignore[assignment]
        prediction.actual_observed = True  # type: ignore[assignment]
        prediction.prediction_error = prediction_error  # type: ignore[assignment]
        prediction.surprise = surprise  # type: ignore[assignment]
        prediction.observation_ts = datetime.utcnow()  # type: ignore[assignment]

        await self._write_to_storage(str(prediction_id), prediction)

        # Invalidate cache
        await self._invalidate_caches(self._cache_key(str(prediction_id)))

        return prediction

    async def get_recent_predictions(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> list[WorldModelPrediction]:
        """Get recent predictions.

        Args:
            hours: Lookback window in hours
            limit: Max results

        Returns:
            List of predictions
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        stmt = (
            select(WorldModelPrediction)
            .where(WorldModelPrediction.ts >= cutoff_time)
            .order_by(WorldModelPrediction.ts.desc())
            .limit(limit)
        )

        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_correlation_id(
        self,
        correlation_id: str,
    ) -> list[WorldModelPrediction]:
        """Get predictions by correlation ID.

        Args:
            correlation_id: Correlation ID

        Returns:
            List of predictions
        """
        stmt = select(WorldModelPrediction).where(
            WorldModelPrediction.correlation_id == correlation_id
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def compute_prediction_stats(
        self,
        hours: int = 24,
    ) -> dict[str, Any]:
        """Compute prediction error statistics.

        Args:
            hours: Lookback window in hours

        Returns:
            Statistics dict[str, Any]
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        stmt = select(WorldModelPrediction).where(
            WorldModelPrediction.ts >= cutoff_time,
            WorldModelPrediction.actual_observed == True,  # noqa: E712
        )

        result = await self.db_session.execute(stmt)
        predictions = list(result.scalars().all())

        if not predictions:
            return {
                "total": 0,
                "avg_error": 0.0,
                "max_error": 0.0,
                "avg_confidence": 0.0,
            }

        errors = [p.prediction_error for p in predictions if p.prediction_error is not None]
        confidences = [
            p.prediction_confidence for p in predictions if p.prediction_confidence is not None
        ]

        return {
            "total": len(predictions),
            "observed": len([p for p in predictions if p.actual_observed]),
            "avg_error": sum(errors) / len(errors) if errors else 0.0,
            "max_error": max(errors) if errors else 0.0,
            "min_error": min(errors) if errors else 0.0,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        }

    # ========== Storage Operations (L3) ==========

    async def _fetch_from_storage(self, key: str) -> WorldModelPrediction | None:
        """Fetch prediction from CockroachDB."""
        try:
            prediction_id = UUID(key)
            stmt = select(WorldModelPrediction).where(WorldModelPrediction.id == prediction_id)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"WorldModelPrediction fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: WorldModelPrediction) -> None:
        """Write prediction to CockroachDB."""
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"WorldModelPrediction write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete prediction from CockroachDB."""
        try:
            prediction_id = UUID(key)
            stmt = select(WorldModelPrediction).where(WorldModelPrediction.id == prediction_id)
            result = await self.db_session.execute(stmt)
            prediction = result.scalar_one_or_none()

            if prediction is not None:
                await self.db_session.delete(prediction)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"WorldModelPrediction delete failed: {e}")
            return False


class EFERepository(BaseRepository[ExpectedFreeEnergy]):
    """Repository for Expected Free Energy tracking."""

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
    ):
        """Initialize EFE repository.

        Args:
            db_session: CockroachDB session
            redis_client: Optional Redis client for L2 cache
        """
        super().__init__(
            storage_backend=db_session,
            cache_strategy=CacheStrategy.READ_THROUGH,
            ttl=300,  # 5 minutes
            l1_max_size=500,
            redis_client=redis_client,
        )
        self.db_session = db_session
        logger.info("EFERepository initialized")

    async def record_efe(
        self,
        correlation_id: str,
        epistemic_value: float,
        pragmatic_value: float,
        risk_value: float,
        total_efe: float,
        action_selected: str | None = None,
        action_candidates: dict[str, Any] | None = None,
    ) -> ExpectedFreeEnergy:
        """Record Expected Free Energy computation.

        Args:
            correlation_id: Correlation ID
            epistemic_value: Information gain
            pragmatic_value: Goal achievement
            risk_value: Safety/uncertainty
            total_efe: Total EFE (lower is better)
            action_selected: Selected action
            action_candidates: All candidate actions

        Returns:
            Saved EFE record
        """
        efe = ExpectedFreeEnergy(
            correlation_id=correlation_id,
            epistemic_value=epistemic_value,
            pragmatic_value=pragmatic_value,
            risk_value=risk_value,
            total_efe=total_efe,
            action_selected=action_selected,
            action_candidates=action_candidates,
        )

        await self._write_to_storage(str(efe.id), efe)
        return efe

    async def _fetch_from_storage(self, key: str) -> ExpectedFreeEnergy | None:
        """Fetch EFE from storage."""
        try:
            efe_id = UUID(key)
            stmt = select(ExpectedFreeEnergy).where(ExpectedFreeEnergy.id == efe_id)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"ExpectedFreeEnergy fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: ExpectedFreeEnergy) -> None:
        """Write EFE to storage."""
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"ExpectedFreeEnergy write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete EFE from storage."""
        try:
            efe_id = UUID(key)
            stmt = select(ExpectedFreeEnergy).where(ExpectedFreeEnergy.id == efe_id)
            result = await self.db_session.execute(stmt)
            efe = result.scalar_one_or_none()

            if efe is not None:
                await self.db_session.delete(efe)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"ExpectedFreeEnergy delete failed: {e}")
            return False


__all__ = [
    "EFERepository",
    "WorldModelRepository",
]
