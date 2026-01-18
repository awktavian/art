"""
Metacognitive Awareness: Know What You Know (and Don't Know)

Implements confidence assessment, uncertainty quantification, and calibration.
Enables K os to report honest confidence and detect knowledge gaps.

Implementation Status: ✅ COMPLETE (Evolution Track - Week 1)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import torch
from sqlalchemy import text

from kagami.core.database.async_connection import get_async_db_session
from kagami.core.world_model.calibration import TemperatureScaler

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceAssessment:
    """Confidence in a prediction or decision"""

    confidence: float  # 0.0-1.0
    basis: str  # Why this confidence? (e.g., "10 samples", "novel situation")
    uncertainty_sources: list[str]  # What makes us uncertain?
    should_defer: bool  # Should defer to human/expert?
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class CalibrationPoint:
    """Single calibration data point"""

    predicted_confidence: float
    actual_success: bool
    task_type: str
    timestamp: float
    correlation_id: str


@dataclass
class CalibrationStats:
    """Calibration statistics over time"""

    avg_predicted_confidence: float
    actual_success_rate: float
    calibration_error: float  # |predicted - actual|
    overconfidence: float  # positive if overconfident
    sample_count: int
    well_calibrated: bool  # Within 10% tolerance


class MetacognitiveLayer:
    """
    Metacognitive awareness for K os.

    Features:
    - Confidence assessment for predictions/decisions
    - Uncertainty quantification
    - Calibration tracking (predicted vs actual)
    - Knowledge gap detection
    - Deference to human expertise

    Usage:
        metacog = MetacognitiveLayer()

        # Assess confidence
        conf = await metacog.assess_confidence(
            prediction="Will succeed in 1200ms",
            basis_samples=10,
            novelty=0.2
        )

        # Record actual outcome
        await metacog.record_outcome(
            predicted_confidence=conf.confidence,
            actual_success=True,
            task_type="intent.execute"
        )

        # Check calibration
        stats = await metacog.get_calibration_stats(hours=24)
    """

    def __init__(self, use_temperature_scaling: bool = True) -> None:
        """Initialize metacognitive layer.

        Args:
            use_temperature_scaling: Enable temperature scaling for post-hoc calibration (default: True)
        """
        self.calibration_history: list[CalibrationPoint] = []
        self.use_temperature_scaling = use_temperature_scaling

        # Temperature scaler (for post-hoc calibration)
        if use_temperature_scaling:
            self.temperature_scaler = TemperatureScaler()
            self._calibration_pending: list[Any] = []  # Accumulate data for calibration
            self._calibration_interval = 100  # Recalibrate every N outcomes
            self._outcomes_since_calibration = 0
            logger.info("✅ Temperature scaling enabled for confidence calibration")

    async def assess_confidence(
        self,
        basis_samples: int = 0,
        novelty: float = 0.0,
        complexity: float = 0.5,
        past_success_rate: float | None = None,
        task_type: str = "unknown",
    ) -> ConfidenceAssessment:
        """
        Assess confidence in current prediction/decision.

        Args:
            basis_samples: Number of past similar experiences
            novelty: How novel is this situation? (0.0-1.0)
            complexity: Task complexity (0.0-1.0)
            past_success_rate: Success rate on similar tasks
            task_type: Type of task

        Returns:
            ConfidenceAssessment with confidence score and reasoning
        """
        uncertainty_sources = []

        # Base confidence from sample size
        if basis_samples == 0:
            base_confidence = 0.1
            uncertainty_sources.append("no_past_experience")
        elif basis_samples < 5:
            base_confidence = 0.3 + (basis_samples / 5) * 0.3
            uncertainty_sources.append("limited_experience")
        else:
            base_confidence = min(0.6 + (basis_samples / 50) * 0.3, 0.9)

        # Adjust for novelty
        novelty_penalty = novelty * 0.3
        if novelty > 0.5:
            uncertainty_sources.append("high_novelty")

        # Adjust for complexity
        complexity_penalty = complexity * 0.2
        if complexity > 0.7:
            uncertainty_sources.append("high_complexity")

        # Adjust for past success rate
        if past_success_rate is not None:
            success_adjustment = (past_success_rate - 0.5) * 0.2
            if past_success_rate < 0.5:
                uncertainty_sources.append("low_past_success")
        else:
            success_adjustment = 0.0
            uncertainty_sources.append("no_success_history")

        # Final confidence (raw)
        raw_confidence = max(
            0.0,
            min(
                1.0,
                base_confidence - novelty_penalty - complexity_penalty + success_adjustment,
            ),
        )

        # Apply temperature scaling if enabled
        if self.use_temperature_scaling:
            confidence_tensor = torch.tensor([raw_confidence])
            calibrated_logits = self.temperature_scaler(
                torch.logit(torch.clamp(confidence_tensor, 1e-7, 1 - 1e-7))
            )
            confidence = float(torch.sigmoid(calibrated_logits).item())  # type: ignore[arg-type]
        else:
            confidence = raw_confidence

        # Should defer to human?
        should_defer = (
            confidence < 0.3  # Very uncertain
            or novelty > 0.8  # Very novel
            or (complexity > 0.8 and confidence < 0.5)  # Complex and uncertain
        )

        # Basis explanation
        if basis_samples == 0:
            basis = "No past experience with this task"
        elif basis_samples < 5:
            basis = f"Limited experience ({basis_samples} samples)"
        else:
            basis = f"Based on {basis_samples} past experiences"

        if past_success_rate is not None:
            basis += f", {past_success_rate:.0%} historical success rate"

        return ConfidenceAssessment(
            confidence=confidence,
            basis=basis,
            uncertainty_sources=uncertainty_sources,
            should_defer=should_defer,
            metadata={
                "basis_samples": basis_samples,
                "novelty": novelty,
                "complexity": complexity,
                "past_success_rate": past_success_rate,
                "task_type": task_type,
            },
        )

    async def record_outcome(
        self,
        predicted_confidence: float,
        actual_success: bool,
        task_type: str,
        correlation_id: str,
    ) -> None:
        """Record actual outcome for calibration tracking"""
        point = CalibrationPoint(
            predicted_confidence=predicted_confidence,
            actual_success=actual_success,
            task_type=task_type,
            timestamp=time.time(),
            correlation_id=correlation_id,
        )

        # Store in database (auto-create table like phi_tracker when missing)
        try:
            from sqlalchemy import text

            from kagami.core.database.async_connection import get_async_db_session

            async def _insert(session: Any) -> None:
                await session.execute(
                    text(
                        """
                    INSERT INTO calibration_points
                    (predicted_confidence, actual_success, task_type, timestamp, correlation_id)
                    VALUES (:predicted_confidence, :actual_success, :task_type, :timestamp, :correlation_id)
                    """
                    ),
                    {
                        "predicted_confidence": point.predicted_confidence,
                        "actual_success": point.actual_success,
                        "task_type": point.task_type,
                        "timestamp": point.timestamp,
                        "correlation_id": point.correlation_id,
                    },
                )

            async def _ensure_calibration_table(session: Any) -> None:
                try:
                    # Determine dialect for compatible types
                    dialect = "unknown"
                    try:
                        bind = getattr(session, "bind", None)
                        if bind is not None and hasattr(bind, "dialect"):
                            dialect = str(getattr(bind.dialect, "name", "unknown"))
                    except Exception:
                        pass

                    is_pg = dialect in ("postgresql", "cockroachdb")

                    await session.execute(
                        text(
                            f"""
                        CREATE TABLE IF NOT EXISTS calibration_points (
                            id INTEGER PRIMARY KEY{" GENERATED BY DEFAULT AS IDENTITY" if is_pg else ""},
                            predicted_confidence {"DOUBLE PRECISION" if is_pg else "REAL"} NOT NULL,
                            actual_success BOOLEAN NOT NULL,
                            task_type VARCHAR(255) NOT NULL,
                            timestamp {"DOUBLE PRECISION" if is_pg else "REAL"} NOT NULL,
                            correlation_id VARCHAR(255) NOT NULL
                        )
                        """
                        )
                    )
                    # Indexes
                    await session.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS idx_calib_timestamp ON calibration_points(timestamp)"
                        )
                    )
                    await session.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS idx_calib_task_type ON calibration_points(task_type)"
                        )
                    )
                    await session.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS idx_calib_correlation ON calibration_points(correlation_id)"
                        )
                    )
                except Exception as create_err:
                    logger.debug(f"ensure_calibration_table failed: {create_err}")

            async with get_async_db_session() as session:
                try:
                    await _insert(session)
                    await session.commit()
                except Exception as e_insert:
                    msg = str(e_insert).lower()
                    if "no such table" in msg or "undefined table" in msg:
                        await _ensure_calibration_table(session)
                        await _insert(session)
                        await session.commit()
                    else:
                        logger.debug(f"Calibration DB insert failed: {e_insert}")
        except Exception as e:
            # Memory-only mode (quiet degradation for dev/test)
            logger.debug(f"Calibration DB unavailable, using memory-only: {e}")

        # Cache in memory
        self.calibration_history.append(point)
        if len(self.calibration_history) > 1000:
            self.calibration_history = self.calibration_history[-1000:]

        # Accumulate for temperature scaling calibration
        if self.use_temperature_scaling:
            self._calibration_pending.append(point)
            self._outcomes_since_calibration += 1

            # Recalibrate periodically
            if self._outcomes_since_calibration >= self._calibration_interval:
                await self._recalibrate_temperature()
                self._outcomes_since_calibration = 0

        logger.debug(
            f"Recorded outcome: predicted={predicted_confidence:.2f}, "
            f"actual={'success' if actual_success else 'failure'}"
        )

    async def _recalibrate_temperature(self) -> None:
        """Recalibrate temperature scaler using accumulated data."""
        if not self.use_temperature_scaling or len(self._calibration_pending) < 20:
            return

        # Convert to tensors
        confidences = torch.tensor([p.predicted_confidence for p in self._calibration_pending])
        accuracies = torch.tensor([float(p.actual_success) for p in self._calibration_pending])

        try:
            # Recalibrate
            self.temperature_scaler.calibrate(confidences, accuracies, num_epochs=50, lr=0.01)
            logger.info(
                f"✅ Temperature recalibrated with {len(self._calibration_pending)} samples, T={self.temperature_scaler.temperature.item():.3f}"
            )

            # Keep recent data for next calibration
            if len(self._calibration_pending) > 200:
                self._calibration_pending = self._calibration_pending[-100:]

        except Exception as e:
            logger.warning(f"Temperature calibration failed: {e}")

    async def get_calibration_stats(
        self,
        hours: int = 24,
        task_type: str | None = None,
    ) -> CalibrationStats:
        """Get calibration statistics"""
        cutoff = time.time() - (hours * 3600)

        # Retrieve from database
        try:
            async with get_async_db_session() as session:
                query = "SELECT * FROM calibration_points WHERE timestamp > :cutoff"
                params = {"cutoff": cutoff}

                if task_type:
                    query += " AND task_type = :task_type"
                    params["task_type"] = task_type  # type: ignore[assignment]

                result = await session.execute(text(query), params)
                rows = result.fetchall()

                points = [
                    CalibrationPoint(
                        predicted_confidence=float(row[0]),
                        actual_success=bool(row[1]),
                        task_type=str(row[2]),
                        timestamp=row[3],
                        correlation_id=str(row[4]),
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.warning(f"Failed to retrieve calibration points from DB: {e}")
            # Fall back to in-memory
            points = [
                p
                for p in self.calibration_history
                if p.timestamp > cutoff and (task_type is None or p.task_type == task_type)
            ]

        if len(points) < 5:
            return CalibrationStats(
                avg_predicted_confidence=0.0,
                actual_success_rate=0.0,
                calibration_error=0.0,
                overconfidence=0.0,
                sample_count=len(points),
                well_calibrated=False,
            )

        # Compute statistics
        avg_predicted = sum(p.predicted_confidence for p in points) / len(points)
        actual_success = sum(1 for p in points if p.actual_success) / len(points)
        calibration_error = abs(avg_predicted - actual_success)
        overconfidence = avg_predicted - actual_success  # Positive if overconfident

        well_calibrated = calibration_error <= 0.1  # Within 10%

        return CalibrationStats(
            avg_predicted_confidence=avg_predicted,
            actual_success_rate=actual_success,
            calibration_error=calibration_error,
            overconfidence=overconfidence,
            sample_count=len(points),
            well_calibrated=well_calibrated,
        )

    async def detect_knowledge_gaps(self, task_type: str) -> dict[str, Any]:
        """Detect knowledge gaps for a task type"""
        # Get recent performance
        stats = await self.get_calibration_stats(hours=168, task_type=task_type)  # 1 week

        if stats.sample_count < 5:
            return {
                "has_gap": True,
                "reason": "insufficient_experience",
                "sample_count": stats.sample_count,
                "recommendation": f"Need more experience with {task_type} (only {stats.sample_count} samples)",
            }

        if stats.calibration_error > 0.2:
            return {
                "has_gap": True,
                "reason": "poor_calibration",
                "calibration_error": stats.calibration_error,
                "recommendation": f"Confidence poorly calibrated for {task_type} (error: {stats.calibration_error:.1%})",
            }

        if stats.actual_success_rate < 0.5:
            return {
                "has_gap": True,
                "reason": "low_success_rate",
                "success_rate": stats.actual_success_rate,
                "recommendation": f"Low success rate on {task_type} ({stats.actual_success_rate:.1%}), consider alternative approach",
            }

        return {
            "has_gap": False,
            "reason": "none",
            "recommendation": f"Performing well on {task_type} ({stats.actual_success_rate:.1%} success)",
        }


# Singleton instance
_metacog_layer: MetacognitiveLayer | None = None


def get_metacognitive_layer() -> MetacognitiveLayer:
    """Get global metacognitive layer instance"""
    global _metacog_layer
    if _metacog_layer is None:
        _metacog_layer = MetacognitiveLayer()
    return _metacog_layer
