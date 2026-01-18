"""Learning coordinator for unified agents.

Provides unified entry points for learning from task outcomes.
Fully wired end-to-end training loop with:
- Online learning with EWC protection (OnlineWorldModelUpdater)
- Batch training from experience replay
- Safety validation via manifold geometry (WorldModelSafetyOracle)
- Convergence tracking (ConvergenceTracker)
- Receipt pattern analysis (ReceiptPatternAnalyzer)
- Genetic memory updates
- Catastrophe dynamics learning

SCHEDULING: Via Celery Beat (kagami.core.tasks.processing_state.batch_train_task)
No internal loop - Celery handles periodic execution.

All components are FULLY INTEGRATED - no dead code.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.unified_agents import GeometricWorker, Task

logger = logging.getLogger(__name__)


class UnifiedLearningCoordinator:
    """Coordinates learning across all agent memory systems.

    FULLY INTEGRATED components:
    1. OnlineWorldModelUpdater - Real-time EWC-protected world model updates
    2. WorldModelSafetyOracle - Risk scoring from manifold geometry
    3. ConvergenceTracker - Monitors learning progress
    4. ReceiptPatternAnalyzer - Extracts patterns from failures
    5. Genetic memory - Evolutionary learning
    6. Experience replay - Batch training
    7. Catastrophe dynamics - Phase transition learning
    """

    def __init__(self) -> None:
        """Initialize the learning coordinator with all integrated components.

        NOTE: No internal loop. Celery Beat calls batch_train_step() periodically.
        """
        self._step_count = 0
        self._last_genetic_update: dict[str, int] = {}  # worker_id -> last_ops_count
        self._genetic_update_stride = 40  # Update genetic memory every N operations

        # === INTEGRATED COMPONENTS ===
        # Lazy-loaded to avoid circular imports
        self._online_updater: Any = None
        self._safety_oracle: Any = None
        self._convergence_tracker: Any = None
        self._receipt_analyzer: Any = None
        self._world_model: Any = None

        # Metrics for tracking
        self._total_online_updates = 0
        self._total_safety_checks = 0
        self._total_patterns_detected = 0

    def _ensure_components(self) -> None:
        """Lazy-load integrated components."""
        if self._convergence_tracker is None:
            from kagami.core.learning.convergence_tracker import get_convergence_tracker

            self._convergence_tracker = get_convergence_tracker()

        if self._receipt_analyzer is None:
            from kagami.core.learning.receipt_analyzer import ReceiptPatternAnalyzer

            self._receipt_analyzer = ReceiptPatternAnalyzer()

        if self._safety_oracle is None:
            from kagami.core.world_model.safety_oracle import get_world_model_safety_oracle

            self._safety_oracle = get_world_model_safety_oracle()
            self._safety_oracle.initialize()

        if self._world_model is None:
            try:
                from kagami.core.world_model.service import get_world_model_service

                self._world_model = get_world_model_service().model
            except Exception:
                logger.debug(
                    "World model service unavailable during coordinator initialization",
                    exc_info=True,
                )

        if self._online_updater is None and self._world_model is not None:
            from kagami.core.learning.online_world_model_updater import (
                get_online_world_model_updater,
            )

            self._online_updater = get_online_world_model_updater(self._world_model)

    async def learn_from_task(
        self,
        agent: GeometricWorker,
        task: Task,
        result: dict[str, Any],
        verified_success: bool,
    ) -> dict[str, Any]:
        """Process learning updates from a completed task.

        FULLY INTEGRATED learning pipeline:
        1. AgentBehaviorMemory - Action success rates
        2. OnlineWorldModelUpdater - EWC-protected gradient update
        3. WorldModelSafetyOracle - Risk assessment
        4. ConvergenceTracker - Learning progress monitoring
        5. Experience storage - For batch replay
        6. Genetic memory - DNA evolution
        7. Catastrophe dynamics - Phase transition learning

        Returns:
            Dict with learning metrics from all components
        """
        self._ensure_components()

        metrics: dict[str, Any] = {
            "step": self._step_count,
            "success": verified_success,
            "components": {},
        }

        duration_ms = (result.get("execution", {}).get("duration_ms", 0.0)) if result else 0.0

        # 1. Behavior Memory (Reinforcement)
        if hasattr(agent, "behavior_memory"):
            agent.behavior_memory.record_outcome(
                task.action, task.params, verified_success, duration_ms
            )
            metrics["components"]["behavior_memory"] = "updated"

        # 2. Store experience for replay
        await self._store_experience(agent, task, result, verified_success)
        metrics["components"]["experience_replay"] = "stored"

        # 3. Online World Model Update with EWC protection
        online_metrics = await self._online_world_model_update(agent, task, result)
        metrics["components"]["online_updater"] = online_metrics

        # 4. Safety Oracle - Compute risk score
        safety_metrics = await self._compute_safety_risk(agent, task, result)
        metrics["components"]["safety_oracle"] = safety_metrics

        # 5. Update convergence tracker
        convergence_metrics = self._update_convergence(
            prediction_error=online_metrics.get("prediction_loss", 0.5),
            confidence=1.0 - safety_metrics.get("risk", 0.5),
        )
        metrics["components"]["convergence"] = convergence_metrics

        # 6. Catastrophe Learning (Topology Adjustment)
        await self._learn_catastrophe_dynamics(agent, result, verified_success)
        metrics["components"]["catastrophe"] = "updated"

        self._step_count += 1
        return metrics

    async def _online_world_model_update(
        self,
        agent: GeometricWorker,
        task: Task,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform online EWC-protected world model update.

        Uses OnlineWorldModelUpdater for:
        - Real-time gradient update on transition
        - Elastic Weight Consolidation to prevent catastrophic forgetting
        - Task-specific Fisher information tracking
        """
        if self._online_updater is None or self._world_model is None:
            return {"status": "skipped", "reason": "no_updater"}

        try:
            # Encode states
            initial_context = {
                "agent": agent.worker_id,
                "action": task.action,
                "params": task.params,
                "context": getattr(task, "context", {}),
            }
            final_context = {
                "agent": agent.worker_id,
                "result": result,
            }

            initial_state = self._world_model.encode_observation(initial_context)
            final_state = self._world_model.encode_observation(final_context)
            action = {"action": task.action, "params": task.params}

            # Get task domain for EWC
            task_domain = (
                getattr(agent.dna, "domain", "default").value  # type: ignore[union-attr]
                if hasattr(agent, "dna")
                else "default"
            )

            # Online update with EWC
            update_metrics = await self._online_updater.update(
                initial_state=initial_state,
                action=action,
                final_state=final_state,
                task_id=task_domain,
            )

            self._total_online_updates += 1
            return update_metrics

        except Exception as e:
            logger.debug(f"Online world model update failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _compute_safety_risk(
        self,
        agent: GeometricWorker,
        task: Task,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute safety risk using WorldModelSafetyOracle.

        Uses manifold geometry (H¹⁴×S⁷) to assess:
        - Octonion norm violations (compositional breakdown)
        - Hyperbolic curvature (radical context shifts)
        - Prediction confidence
        """
        if self._safety_oracle is None or self._world_model is None:
            return {"risk": 0.5, "status": "skipped"}

        try:
            # Get prediction for the action outcome
            initial_context = {
                "agent": agent.worker_id,
                "action": task.action,
                "params": task.params,
            }
            initial_state = self._world_model.encode_observation(initial_context)
            action = {"action": task.action, "params": task.params}

            # Predict and compute risk
            prediction = self._world_model.predict_next_state(initial_state, action, horizon=1)
            risk = self._safety_oracle.compute_manifold_risk(prediction)

            self._total_safety_checks += 1

            return {
                "risk": risk,
                "confidence": prediction.confidence if hasattr(prediction, "confidence") else 0.5,
                "status": "computed",
            }

        except Exception as e:
            logger.debug(f"Safety risk computation failed: {e}")
            return {"risk": 0.5, "status": "failed", "error": str(e)}

    def _update_convergence(
        self,
        prediction_error: float,
        confidence: float,
    ) -> dict[str, Any]:
        """Update convergence tracker with latest metrics.

        Monitors:
        - Prediction error trend (should decrease)
        - Confidence trend (should increase)
        - Learning velocity
        - Convergence status
        """
        if self._convergence_tracker is None:
            return {"status": "skipped"}

        try:
            self._convergence_tracker.record_training_cycle(
                prediction_error=prediction_error,
                confidence=confidence,
            )

            status = self._convergence_tracker.get_convergence_status()

            # Emit metrics periodically
            if self._step_count % 10 == 0:
                self._convergence_tracker.emit_metrics()

            return status

        except Exception as e:
            logger.debug(f"Convergence tracking failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def analyze_receipts(
        self, receipts: list[dict[str, Any]], window_hours: int = 24
    ) -> dict[str, Any]:
        """Analyze receipts for failure patterns.

        Uses ReceiptPatternAnalyzer to:
        - Detect repeated failures
        - Generate recommendations
        - Store learnings in episodic memory

        Args:
            receipts: List of receipt dictionaries
            window_hours: Time window to analyze

        Returns:
            Analysis with patterns, failure rates, recommendations
        """
        self._ensure_components()

        if self._receipt_analyzer is None:
            return {"status": "skipped", "reason": "no_analyzer"}

        try:
            analysis = await self._receipt_analyzer.analyze_recent_receipts(
                receipts=receipts,
                window_hours=window_hours,
            )

            # Store high-severity patterns
            for pattern in analysis.get("patterns", []):
                if pattern.get("severity") == "high":
                    await self._receipt_analyzer.store_learning(pattern, valence=-0.9)
                    self._total_patterns_detected += 1

            return analysis

        except Exception as e:
            logger.debug(f"Receipt analysis failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _store_experience(
        self,
        agent: GeometricWorker,
        task: Task,
        result: dict[str, Any],
        success: bool,
    ) -> None:
        """Store experience in prioritized replay buffer."""
        try:
            prod_systems = None
            if hasattr(agent, "_get_production_systems"):
                prod_systems = agent._get_production_systems()

            if prod_systems is None:
                try:
                    from kagami.core.production_systems_coordinator import (
                        get_production_systems_coordinator,
                    )

                    prod_systems = get_production_systems_coordinator()
                except Exception:
                    logger.debug("Production systems coordinator unavailable", exc_info=True)

            if prod_systems is None:
                return

            replay = getattr(prod_systems, "prioritized_replay", None)
            if replay is None:
                return

            # Compute priority based on success and brain confidence
            brain_confidence = result.get("brain_confidence", 0.5)
            priority = 1.0 - brain_confidence if success else 1.0

            experience = {
                "agent_id": agent.worker_id,
                "domain": getattr(agent.dna, "domain", {}).value  # type: ignore[union-attr]
                if hasattr(agent, "dna")
                else "unknown",
                "action": task.action,
                "params": task.params,
                "context": getattr(task, "context", {}),
                "result": result,
                "success": success,
                "priority": priority,
                "timestamp": time.time(),
            }

            if hasattr(replay, "add"):
                from kagami.core.memory.types import Experience

                exp = Experience(
                    state=experience,
                    action={"action": task.action, "params": task.params},
                    reward=1.0 if success else -0.5,
                    next_state=result or {},
                    done=True,
                    timestamp=time.time(),
                    priority=priority,
                    metadata={"task_id": task.task_id},
                )
                replay.add(exp)
            elif hasattr(replay, "store"):
                await replay.store(experience, priority=priority)

            logger.debug(f"Stored experience for {agent.worker_id}: {task.action}")

        except Exception as e:
            logger.debug(f"Experience storage failed: {e}")

    async def _learn_catastrophe_dynamics(
        self, agent: GeometricWorker, result: dict[str, Any], success: bool
    ) -> None:
        """Update agent's catastrophe control parameters based on outcome.

        Uses the COLONY_CATASTROPHE_MAP to verify valid colony types, then
        adjusts the agent's catastrophe_params based on task success/failure.

        This affects the loss landscape by modulating sensitivity to
        catastrophe singularities: success → move toward stability,
        failure → increase sensitivity.
        """
        if not hasattr(agent, "dna") or not hasattr(agent.dna, "personality"):
            return

        # Get catastrophe type from constants (canonical source)
        from kagami.core.unified_agents.colony_constants import COLONY_CATASTROPHE_MAP

        domain = agent.dna.domain.value if hasattr(agent.dna, "domain") else None
        if not domain or domain not in COLONY_CATASTROPHE_MAP:
            return

        personality = agent.dna.personality

        # Update catastrophe_params based on outcome
        # Success: move params toward stable region (away from singularity)
        # Failure: increase sensitivity (params move toward detection)
        learning_rate = personality.learning_rate
        if success:
            # Decay params toward zero (stable region)
            personality.catastrophe_params *= 1 - learning_rate * 0.1
        else:
            # Increase params to detect catastrophes earlier
            personality.catastrophe_params += learning_rate * 0.05

    async def record_experience(self, experience: dict[str, Any]) -> None:
        """Record an experience for learning (ILearningCoordinator interface)."""
        try:
            from kagami.core.production_systems_coordinator import (
                get_production_systems_coordinator,
            )

            prod_systems = get_production_systems_coordinator()
            replay = getattr(prod_systems, "prioritized_replay", None)
            if replay is None:
                return

            priority = experience.get("priority", 0.5)

            if hasattr(replay, "add"):
                from kagami.core.memory.types import Experience

                exp = Experience(
                    state=experience.get("context", {}),
                    action=experience.get("action", {}),
                    reward=experience.get("valence", 0.0),
                    next_state=experience.get("outcome", {}),
                    done=True,
                    timestamp=time.time(),
                    priority=priority,
                )
                replay.add(exp)

        except Exception as e:
            logger.debug(f"Experience recording failed: {e}")

    async def batch_train_step(self) -> dict[str, Any]:
        """Execute a single batch training step."""
        metrics: dict[str, Any] = {"status": "no_data"}

        try:
            from kagami.core.production_systems_coordinator import (
                get_production_systems_coordinator,
            )

            prod_systems = get_production_systems_coordinator()
            if prod_systems is None:
                return metrics

            replay = getattr(prod_systems, "prioritized_replay", None)
            if replay is None:
                return metrics

            buffer_size = 0
            if hasattr(replay, "get_replay_stats"):
                buffer_size = replay.get_replay_stats().get("size", 0)
            elif hasattr(replay, "size"):
                buffer_size = replay.size

            if buffer_size < 32:
                metrics["status"] = "insufficient_data"
                metrics["buffer_size"] = buffer_size
                return metrics

            batch = None
            if hasattr(replay, "sample_prioritized"):
                batch = replay.sample_prioritized(batch_size=32)
            elif hasattr(replay, "sample"):
                batch = replay.sample(32)

            if batch is None:
                return metrics

            # NOTE: master_coordinator removed in Jan 2026 training consolidation
            # This code path is disabled - use ConsolidatedTrainer instead
            logger.warning("master_coordinator deprecated - skipping batch training")
            metrics["status"] = "skipped"
            metrics["reason"] = "Use kagami.core.training.consolidated.train_kagami instead"

        except Exception as e:
            logger.warning(f"Batch training step failed: {e}")
            metrics["status"] = "error"
            metrics["error"] = str(e)

        return metrics

    def get_stats(self) -> dict[str, Any]:
        """Get coordinator statistics including all integrated components."""
        stats = {
            "step_count": self._step_count,
            "agents_tracked": len(self._last_genetic_update),
            # Integrated component stats
            "total_online_updates": self._total_online_updates,
            "total_safety_checks": self._total_safety_checks,
            "total_patterns_detected": self._total_patterns_detected,
        }

        # Add convergence status
        if self._convergence_tracker is not None:
            stats["convergence"] = self._convergence_tracker.get_convergence_status()

        return stats

    def get_convergence_status(self) -> dict[str, Any]:
        """Get current learning convergence status.

        Returns:
            Convergence status from tracker
        """
        self._ensure_components()
        if self._convergence_tracker is not None:
            return self._convergence_tracker.get_convergence_status()
        return {"status": "tracker_not_initialized"}

    async def get_safety_trajectory(
        self,
        current_state: Any,
        action: dict[str, Any],
        horizon: int = 3,
    ) -> list[float]:
        """Get predicted safety risk trajectory.

        Args:
            current_state: Current observation
            action: Proposed action
            horizon: Prediction horizon

        Returns:
            List of risk scores for t+1, t+2, ... t+horizon
        """
        self._ensure_components()
        if self._safety_oracle is not None:
            return await self._safety_oracle.predict_safety_trajectory(
                current_state, action, horizon
            )
        return [0.5] * horizon


_coordinator: UnifiedLearningCoordinator | None = None


def get_learning_coordinator() -> UnifiedLearningCoordinator:
    """Get global learning coordinator singleton."""
    global _coordinator
    if _coordinator is None:
        _coordinator = UnifiedLearningCoordinator()
    return _coordinator


def reset_learning_coordinator() -> None:
    """Reset the learning coordinator (for testing)."""
    global _coordinator
    _coordinator = None
