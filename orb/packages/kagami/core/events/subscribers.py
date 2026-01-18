from __future__ import annotations

"""Experience Bus Subscribers - Background learning from operation outcomes.

These run asynchronously after operations complete, updating memory without
blocking the hot path.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MemoryIndexer:
    """Stores operation outcomes in episodic memory."""

    def __init__(self) -> None:
        self._learning_instinct = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize learning instinct connection."""
        if self._initialized:
            return

        try:
            from kagami.core.instincts.learning_instinct import LearningInstinct

            self._learning_instinct = LearningInstinct()  # type: ignore[assignment]
            self._initialized = True
            logger.info("✅ MemoryIndexer: Learning instinct connected")
        except Exception as e:
            logger.warning(f"⚠️  MemoryIndexer: Learning instinct unavailable: {e}")

    async def handle_outcome(self, event: Any) -> None:
        """Store an experience outcome in episodic memory.

        Args:
            event: E8Event from UnifiedE8Bus (topic: experience.*)
        """
        if not self._initialized:
            await self.initialize()

        if not self._learning_instinct:
            return

        try:  # type: ignore[unreachable]
            payload = getattr(event, "payload", {}) or {}
            success = bool(payload.get("success", False))
            valence = float(payload.get("valence", 0.0))
            # Store in episodic memory with valence
            await self._learning_instinct.remember(
                context={
                    "operation": payload.get("operation", ""),
                    "app": payload.get("app", "unknown"),
                    "problem_type": payload.get("problem_type", "unknown"),
                    "strategy": payload.get("strategy_used", payload.get("strategy", "unknown")),
                    "temperature": payload.get("temperature", None),
                },
                outcome={
                    "success": success,
                    "duration_ms": float(payload.get("duration_ms", 0.0)),
                    "prediction_error_ms": float(payload.get("prediction_error_ms", 0.0)),
                    "status": "success" if success else "error",
                },
                valence=valence,
            )

            logger.debug(
                "💾 Indexed: %s (valence=%.2f)",
                payload.get("operation", "unknown"),
                valence,
            )

        except Exception as e:
            logger.debug(f"Memory indexing failed: {e}")


class PatternBuilder:
    """Builds procedural patterns from repeated successes."""

    def __init__(self) -> None:
        self._prediction_instinct = None
        self._pattern_cache: dict[str, dict[str, Any]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize prediction instinct connection."""
        if self._initialized:
            return

        try:
            from kagami.core.instincts.prediction_instinct import PredictionInstinct

            self._prediction_instinct = PredictionInstinct()  # type: ignore[assignment]
            self._initialized = True
            logger.info("✅ PatternBuilder: Prediction instinct connected")
        except Exception as e:
            logger.warning(f"⚠️  PatternBuilder: Prediction instinct unavailable: {e}")

    async def handle_outcome(self, event: Any) -> None:
        """Update procedural patterns from an experience outcome.

        Args:
            event: E8Event from UnifiedE8Bus (topic: experience.*)
        """
        if not self._initialized:
            await self.initialize()

        if not self._prediction_instinct:
            return

        try:  # type: ignore[unreachable]
            payload = getattr(event, "payload", {}) or {}
            success = bool(payload.get("success", False))
            operation = payload.get("operation", "")
            # Learn from actual outcome
            await self._prediction_instinct.learn(
                context={
                    "app": payload.get("app", "unknown"),
                    "action": operation,
                    "metadata": {"complexity": "normal"},
                },
                actual_outcome={
                    "duration_ms": float(payload.get("duration_ms", 0.0)),
                    "status": "success" if success else "error",
                },
            )

            logger.debug(
                "📊 Pattern learned: %s (%.0fms)",
                operation,
                float(payload.get("duration_ms", 0.0)),
            )

        except Exception as e:
            logger.debug(f"Pattern building failed: {e}")


class ThreatLearner:
    """Learns failure patterns for predictive safety."""

    def __init__(self) -> None:
        self._failure_patterns: list[dict[str, Any]] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize threat learning."""
        self._initialized = True
        logger.info("✅ ThreatLearner: Initialized")

    async def handle_outcome(self, event: Any) -> None:
        """Learn from failures to predict future risks.

        Args:
            event: E8Event from UnifiedE8Bus (topic: experience.*)
        """
        if not self._initialized:
            await self.initialize()

        payload = getattr(event, "payload", {}) or {}

        # Only learn from failures
        if bool(payload.get("success", False)):
            return

        try:
            # Store failure pattern
            valence = float(payload.get("valence", 0.0))
            pattern = {
                "operation": payload.get("operation", "unknown"),
                "problem_type": payload.get("problem_type", "unknown"),
                "strategy": payload.get("strategy_used", payload.get("strategy", "unknown")),
                "errors": payload.get("verification_errors", payload.get("errors", [])),
                "severity": abs(valence),
                "timestamp": payload.get("timestamp", getattr(event, "timestamp", None)),
            }

            self._failure_patterns.append(pattern)

            # Keep last 200 failures
            if len(self._failure_patterns) > 200:
                self._failure_patterns = self._failure_patterns[-200:]

            logger.info(
                "🛡️  Threat learned: %s failure (severity=%.2f)",
                pattern["operation"],
                pattern["severity"],
            )

        except Exception as e:
            logger.debug(f"Threat learning failed: {e}")

    def get_failure_count(self, operation: str) -> int:
        """Get count of failures for operation type."""
        return sum(1 for p in self._failure_patterns if p["operation"] == operation)


def register_all_subscribers(bus: Any) -> None:
    """Register all built-in subscribers to experience bus.

    Args:
        bus: UnifiedE8Bus instance
    """
    # Memory indexer
    indexer = MemoryIndexer()
    bus.subscribe("experience.*", indexer.handle_outcome)

    # Pattern builder
    builder = PatternBuilder()
    bus.subscribe("experience.*", builder.handle_outcome)

    # Threat learner
    learner = ThreatLearner()
    bus.subscribe("experience.*", learner.handle_outcome)

    logger.info("✅ Registered 3 subscribers: MemoryIndexer, PatternBuilder, ThreatLearner")
