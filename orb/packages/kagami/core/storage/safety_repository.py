"""Safety state repository with CBF integration.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.database.models import SafetyStateSnapshot, ThreatClassification
from kagami.core.storage.base import BaseRepository, CacheStrategy

logger = logging.getLogger(__name__)


class SafetyRepository(BaseRepository[SafetyStateSnapshot]):
    """Repository for safety state snapshots.

    Storage architecture:
    - Primary: CockroachDB (relational, audit)
    - L2 Cache: Redis (fast safety checks)

    Cache strategy: WRITE_THROUGH
    - Critical reads for safety checks
    - Time-sensitive data
    - Immediate consistency required

    CRITICAL: Enforces h(x) >= 0 invariant
    """

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
    ):
        """Initialize safety repository.

        Args:
            db_session: CockroachDB session
            redis_client: Optional Redis client for L2 cache
        """
        super().__init__(
            storage_backend=db_session,
            cache_strategy=CacheStrategy.WRITE_THROUGH,
            ttl=60,  # 1 minute (time-sensitive)
            l1_max_size=500,
            redis_client=redis_client,
        )
        self.db_session = db_session
        logger.info("SafetyRepository initialized")

    # ========== Safety Operations ==========

    async def record_safety_event(
        self,
        correlation_id: str,
        barrier_value: float,
        state: dict[str, float],
        action_type: str,
        operation: str | None = None,
        scenario: str | None = None,
        attack_type: str | None = None,
    ) -> SafetyStateSnapshot:
        """Record safety-critical event.

        INVARIANT: h(x) >= 0 for all safe states

        Args:
            correlation_id: Correlation ID
            barrier_value: CBF barrier value h(x)
            state: State vector components
            action_type: Action taken (allow, refuse, degrade)
            operation: Optional operation name
            scenario: Optional threat scenario
            attack_type: Optional attack type

        Returns:
            Saved safety snapshot

        Raises:
            ValueError: If state vector is invalid
        """
        # Validate state vector
        required_keys = ["threat", "uncertainty", "complexity", "predictive_risk"]
        if not all(k in state for k in required_keys):
            raise ValueError(f"State vector missing required keys: {required_keys}")

        snapshot = SafetyStateSnapshot(
            correlation_id=correlation_id,
            threat=state["threat"],
            uncertainty=state["uncertainty"],
            complexity=state["complexity"],
            predictive_risk=state["predictive_risk"],
            barrier_value=barrier_value,
            action_type=action_type,
            operation=operation,
            scenario=scenario,
            attack_type=attack_type,
        )

        # Immediate write (no caching for safety-critical data)
        await self._write_to_storage(str(snapshot.id), snapshot)

        # Log safety violations
        if barrier_value < 0:
            logger.warning(
                f"SAFETY VIOLATION: h(x)={barrier_value:.4f} < 0 "
                f"[correlation_id={correlation_id}, action={action_type}]"
            )

        return snapshot

    async def get_recent_violations(
        self,
        hours: int = 24,
        min_severity: float = 0.0,
        limit: int = 100,
    ) -> list[SafetyStateSnapshot]:
        """Query recent safety violations.

        Args:
            hours: Lookback window in hours
            min_severity: Minimum severity (barrier_value < this)
            limit: Max results

        Returns:
            List of safety violations
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        stmt = (
            select(SafetyStateSnapshot)
            .where(
                SafetyStateSnapshot.barrier_value < min_severity,
                SafetyStateSnapshot.ts >= cutoff_time,
            )
            .order_by(SafetyStateSnapshot.barrier_value.asc())  # Most severe first
            .limit(limit)
        )

        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_correlation_id(
        self,
        correlation_id: str,
    ) -> list[SafetyStateSnapshot]:
        """Get all safety snapshots for a correlation ID.

        Args:
            correlation_id: Correlation ID

        Returns:
            List of safety snapshots
        """
        stmt = select(SafetyStateSnapshot).where(
            SafetyStateSnapshot.correlation_id == correlation_id
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_by_action(
        self,
        action_type: str,
        hours: int = 24,
        limit: int = 100,
    ) -> list[SafetyStateSnapshot]:
        """Get recent snapshots by action type.

        Args:
            action_type: Action type (allow, refuse, degrade)
            hours: Lookback window in hours
            limit: Max results

        Returns:
            List of safety snapshots
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        stmt = (
            select(SafetyStateSnapshot)
            .where(
                SafetyStateSnapshot.action_type == action_type,
                SafetyStateSnapshot.ts >= cutoff_time,
            )
            .order_by(SafetyStateSnapshot.ts.desc())
            .limit(limit)
        )

        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def compute_safety_stats(
        self,
        hours: int = 24,
    ) -> dict[str, Any]:
        """Compute safety statistics for monitoring.

        Args:
            hours: Lookback window in hours

        Returns:
            Safety statistics dict[str, Any]
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        stmt = select(SafetyStateSnapshot).where(SafetyStateSnapshot.ts >= cutoff_time)
        result = await self.db_session.execute(stmt)
        snapshots = list(result.scalars().all())

        if not snapshots:
            return {
                "total": 0,
                "violations": 0,
                "violation_rate": 0.0,
                "avg_barrier_value": 0.0,
                "min_barrier_value": 0.0,
            }

        violations = [s for s in snapshots if s.barrier_value < 0]
        barrier_values = [s.barrier_value for s in snapshots]

        return {
            "total": len(snapshots),
            "violations": len(violations),
            "violation_rate": len(violations) / len(snapshots),
            "avg_barrier_value": sum(barrier_values) / len(barrier_values),
            "min_barrier_value": min(barrier_values),
            "max_barrier_value": max(barrier_values),
        }

    # ========== Storage Operations (L3) ==========

    async def _fetch_from_storage(self, key: str) -> SafetyStateSnapshot | None:
        """Fetch safety snapshot from CockroachDB.

        Args:
            key: Snapshot ID

        Returns:
            SafetyStateSnapshot or None
        """
        try:
            snapshot_id = UUID(key)
            stmt = select(SafetyStateSnapshot).where(SafetyStateSnapshot.id == snapshot_id)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"SafetyStateSnapshot fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: SafetyStateSnapshot) -> None:
        """Write safety snapshot to CockroachDB.

        Args:
            key: Snapshot ID
            value: SafetyStateSnapshot to store
        """
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"SafetyStateSnapshot write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete safety snapshot from CockroachDB.

        Args:
            key: Snapshot ID

        Returns:
            True if deleted
        """
        try:
            snapshot_id = UUID(key)
            stmt = select(SafetyStateSnapshot).where(SafetyStateSnapshot.id == snapshot_id)
            result = await self.db_session.execute(stmt)
            snapshot = result.scalar_one_or_none()

            if snapshot is not None:
                await self.db_session.delete(snapshot)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"SafetyStateSnapshot delete failed: {e}")
            return False


class ThreatRepository(BaseRepository[ThreatClassification]):
    """Repository for threat classification storage."""

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
    ):
        """Initialize threat repository.

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
        logger.info("ThreatRepository initialized")

    async def record_threat(
        self,
        correlation_id: str,
        scenario: str | None = None,
        scenario_confidence: float | None = None,
        attack_type: str | None = None,
        attack_confidence: float | None = None,
    ) -> ThreatClassification:
        """Record threat classification.

        Args:
            correlation_id: Correlation ID
            scenario: Detected scenario
            scenario_confidence: Confidence score
            attack_type: Detected attack type
            attack_confidence: Confidence score

        Returns:
            Saved threat classification
        """
        threat = ThreatClassification(
            correlation_id=correlation_id,
            scenario=scenario,
            scenario_confidence=scenario_confidence,
            attack_type=attack_type,
            attack_confidence=attack_confidence,
        )

        await self._write_to_storage(str(threat.id), threat)
        return threat

    async def _fetch_from_storage(self, key: str) -> ThreatClassification | None:
        """Fetch threat from storage."""
        try:
            threat_id = UUID(key)
            stmt = select(ThreatClassification).where(ThreatClassification.id == threat_id)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"ThreatClassification fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: ThreatClassification) -> None:
        """Write threat to storage."""
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"ThreatClassification write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete threat from storage."""
        try:
            threat_id = UUID(key)
            stmt = select(ThreatClassification).where(ThreatClassification.id == threat_id)
            result = await self.db_session.execute(stmt)
            threat = result.scalar_one_or_none()

            if threat is not None:
                await self.db_session.delete(threat)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"ThreatClassification delete failed: {e}")
            return False


__all__ = [
    "SafetyRepository",
    "ThreatRepository",
]
