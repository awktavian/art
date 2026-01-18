"""SmartHome Learning Bridge — Connects SmartHome receipts to organism learning loop.

Flow:
1. SmartHome action -> Receipt emitted
2. Receipt stored in stigmergy
3. ReceiptLearningEngine analyzes patterns
4. World model updated via gradient descent
5. RoutineOptimizerGoal proposes improvements
6. User approves -> Routine params updated

This closes the loop:
    Action -> Receipt -> Learn -> Improve -> Better Action

Created: December 31, 2025
h(x) >= 0 always.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.context.context_engine import HomeContext
    from kagami_smarthome.routines.adaptive_routine import RoutineResult

logger = logging.getLogger(__name__)

# Global bridge instance
_learning_bridge: SmartHomeLearningBridge | None = None


@dataclass
class LearningUpdate:
    """Update from learning engine."""

    routine_id: str
    colony_utility_deltas: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class SmartHomeLearningBridge:
    """Connects SmartHome receipts to organism world model.

    Flow:
    1. SmartHome action -> Receipt emitted
    2. Receipt stored in stigmergy
    3. ReceiptLearningEngine analyzes patterns
    4. World model updated via gradient descent
    5. RoutineOptimizerGoal proposes improvements
    6. User approves -> Routine params updated

    This closes the loop:
        Action -> Receipt -> Learn -> Improve -> Better Action
    """

    def __init__(self):
        self._learning_engine = None
        self._world_model = None
        self._initialized = False
        self._learning_updates: list[LearningUpdate] = []

    async def initialize(self) -> None:
        """Initialize bridge to organism learning."""
        try:
            # Try to import organism learning components
            from kagami.core.world_model.rssm_core import get_organism_rssm

            self._world_model = get_organism_rssm()

            try:
                from kagami.core.training.learning.receipt_learning import ReceiptLearningEngine

                self._learning_engine = ReceiptLearningEngine(
                    organism_rssm=self._world_model,
                    learning_rate=1e-4,
                    min_sample_size=5,
                )
            except ImportError:
                logger.debug("ReceiptLearningEngine not available")

            self._initialized = True
            logger.info("SmartHome learning bridge initialized")

        except Exception as e:
            logger.warning(f"Learning bridge init failed (non-fatal): {e}")

    async def learn_from_routine_execution(
        self,
        routine_id: str,
        context: HomeContext,
        result: RoutineResult,
        user_feedback: str | None = None,  # "good", "bad", None
    ) -> LearningUpdate | None:
        """Learn from a routine execution.

        Called after every routine execution to:
        1. Analyze success/failure patterns
        2. Update world model predictions
        3. Adjust routine parameters

        Args:
            routine_id: ID of the executed routine
            context: Home context at execution time
            result: Routine execution result
            user_feedback: Optional user feedback ("good", "bad", or None)

        Returns:
            LearningUpdate if learning occurred, None otherwise
        """
        if not self._initialized:
            await self.initialize()

        if not self._learning_engine:
            return None

        # Build observation for world model
        observation = self._build_observation(context, result)

        try:
            # Get learning update from engine
            analysis = await self._learning_engine.analyze_receipts(
                intent_type=f"smarthome.routine.{routine_id}",
                time_window_hours=168,  # 1 week
            )

            if analysis and analysis.sample_size >= 5:
                # Generate parameter update suggestions
                update = self._learning_engine.compute_update(analysis)

                # Create LearningUpdate
                learning_update = LearningUpdate(
                    routine_id=routine_id,
                    colony_utility_deltas=update.colony_utility_deltas
                    if hasattr(update, "colony_utility_deltas")
                    else {},
                    confidence=update.confidence if hasattr(update, "confidence") else 0.5,
                    metadata={
                        "sample_size": analysis.sample_size,
                        "observation": observation,
                    },
                )

                # Apply feedback boost if user provided it
                if user_feedback == "good":
                    learning_update.confidence *= 1.5
                elif user_feedback == "bad":
                    learning_update.confidence *= 0.5

                # Store for RoutineOptimizerGoal to process
                await self._store_learning_update(routine_id, learning_update)

                return learning_update

        except Exception as e:
            logger.debug(f"Learning failed for routine {routine_id}: {e}")

        return None

    def _build_observation(
        self,
        context: HomeContext,
        result: RoutineResult,
    ) -> dict[str, Any]:
        """Build world model observation from routine execution."""
        return {
            "circadian_phase": context.circadian_phase.value,
            "presence": context.owner_home,
            "activity": context.detected_activity or "unknown",
            "routine_id": result.routine_id,
            "success": result.success,
            "action_count": len(result.actions),
            "timestamp": context.time.timestamp(),
        }

    async def _store_learning_update(
        self,
        routine_id: str,
        update: LearningUpdate,
    ) -> None:
        """Store update for RoutineOptimizerGoal."""
        self._learning_updates.append(update)

        # Emit receipt for learning update
        try:
            from kagami.core.receipts.facade import URF, emit_receipt

            emit_receipt(
                URF.generate_correlation_id(),
                "smarthome.learning.update",
                event_data={
                    "routine_id": routine_id,
                    "confidence": update.confidence,
                    "metadata": update.metadata,
                },
            )
        except ImportError:
            logger.debug(f"Learning update stored for {routine_id}")

    def get_pending_updates(self, min_confidence: float = 0.5) -> list[LearningUpdate]:
        """Get pending learning updates above confidence threshold."""
        return [u for u in self._learning_updates if u.confidence >= min_confidence]

    def clear_updates(self) -> None:
        """Clear processed learning updates."""
        self._learning_updates.clear()


async def get_learning_bridge() -> SmartHomeLearningBridge:
    """Get or create learning bridge."""
    global _learning_bridge
    if _learning_bridge is None:
        _learning_bridge = SmartHomeLearningBridge()
        await _learning_bridge.initialize()
    return _learning_bridge


__all__ = [
    "LearningUpdate",
    "SmartHomeLearningBridge",
    "get_learning_bridge",
]
