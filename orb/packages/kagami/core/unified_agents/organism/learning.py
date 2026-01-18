"""Learning Module - Receipt learning, knowledge graph, adaptation.

Responsibilities:
- Receipt learning from stigmergy
- Knowledge graph consultation and update
- World model feedback from receipts
- Continuous learning integration
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LearningMixin:
    """Mixin providing learning capabilities for UnifiedOrganism."""

    # These attributes are set by the main UnifiedOrganism class
    _router: Any
    _continuous_mind: Any
    _last_learning_time: float
    config: Any

    async def _trigger_receipt_learning(self, intent: str) -> None:
        """Trigger learning from recent receipts.

        NEXUS BRIDGE: Connects receipt patterns -> colony utility updates.

        This method is called periodically during execution to:
        1. Retrieve recent receipt patterns from stigmergy learner
        2. Analyze success/failure rates per colony
        3. Update colony game model utilities
        4. Improve future routing decisions

        Args:
            intent: Recent intent type for context
        """
        try:
            from kagami.core.unified_agents.geometric_worker import COLONY_NAMES

            # Get stigmergy learner from router
            if not hasattr(self._router, "_stigmergy_learner"):
                logger.debug("Stigmergy learner not available for receipt learning")
                return

            stigmergy = self._router._stigmergy_learner
            if stigmergy.game_model is None:
                logger.debug("Colony game model not available for learning")
                return

            # Get recent patterns (receipt-compatible format)
            intent_type = intent.split(".")[0] if "." in intent else intent
            receipts = stigmergy.get_patterns(intent_type=intent_type, limit=100)

            if not receipts:
                logger.debug(f"No receipts found for intent type: {intent_type}")
                return

            # Analyze receipts per colony
            colony_performance: dict[str, dict[str, Any]] = {
                name: {"success": 0, "total": 0} for name in COLONY_NAMES
            }

            for receipt in receipts:
                actor = receipt.get("actor", "")
                if actor and ":" in actor:
                    actor = actor.split(":", 1)[0]

                colony = actor.lower() if actor.lower() in COLONY_NAMES else None
                if colony is None:
                    colony = receipt.get("workspace_hash", "").lower()
                    if colony not in COLONY_NAMES:
                        continue

                status = receipt.get("verifier", {}).get("status", "")
                is_success = status in {"verified", "success"}

                colony_performance[colony]["total"] += 1
                if is_success:
                    colony_performance[colony]["success"] += 1

            # Update colony utilities based on performance
            for colony, perf in colony_performance.items():
                if perf["total"] == 0:
                    continue

                success_rate = perf["success"] / perf["total"]
                delta = success_rate - 0.5
                stigmergy.game_model.update_utility(colony, delta)

            # Update world model with receipt outcomes
            await self._update_world_model_from_receipts(colony_performance, receipts)

            # Log learning event
            now = time.time()
            time_since_last = now - self._last_learning_time
            self._last_learning_time = now

            updated = sum(1 for p in colony_performance.values() if p["total"] > 0)
            logger.info(
                f"Learning from {len(receipts)} recent experiences with {intent_type} "
                f"({updated} colonies updated, {time_since_last:.1f}s since last learning)"
            )

        except (AttributeError, KeyError, ValueError) as e:
            logger.warning(f"Couldn't learn from recent receipts: {e}", exc_info=True)

    async def _update_world_model_from_receipts(
        self,
        colony_performance: dict[str, dict[str, Any]],
        receipts: list[dict[str, Any]],
    ) -> None:
        """Update world model with receipt outcomes.

        COHERENCY: Closes feedback loop from execution to world model.

        Args:
            colony_performance: Dict mapping colony names to success/total counts
            receipts: List of receipt dicts from stigmergy learner
        """
        try:
            from kagami.core.unified_agents.geometric_worker import COLONY_NAMES
            from kagami.core.world_model.colony_rssm import get_organism_rssm
            from kagami.core.world_model.service import get_world_model_service

            wm_service = get_world_model_service()
            if not wm_service.is_available:
                return

            rssm = get_organism_rssm()
            if rssm is None:
                return

            import torch
            import torch.nn.functional as F

            from kagami.core.unified_agents.octonion_state import OctonionState

            # Build target S7 phase from colony success rates
            s7_target = torch.zeros(7)
            for i, colony in enumerate(COLONY_NAMES):
                perf = colony_performance.get(colony, {"success": 0, "total": 0})
                if perf["total"] > 0:
                    s7_target[i] = perf["success"] / perf["total"]
                else:
                    s7_target[i] = 0.5

            s7_target = F.normalize(s7_target, dim=-1)

            # Create training experiences from receipts
            experiences = []
            for receipt in receipts[:10]:
                intent = receipt.get("intent", {})
                observation = {
                    "type": intent.get("type", "unknown"),
                    "params": intent.get("params", {}),
                }

                actor = receipt.get("actor", "")
                colony_idx = 0
                for i, name in enumerate(COLONY_NAMES):
                    if name in actor.lower():
                        colony_idx = i
                        break

                action = OctonionState.from_colony_index(colony_idx)

                status = receipt.get("verifier", {}).get("status", "")
                reward = 1.0 if status in {"verified", "success"} else -0.5

                experiences.append(
                    {
                        "observation": observation,
                        "action": action.e8_code,
                        "reward": reward,
                        "s7_target": s7_target,
                    }
                )

            if len(experiences) >= 5:
                logger.debug(
                    f"World model update from {len(experiences)} receipts, "
                    f"s7_target={s7_target.tolist()}"
                )

                if hasattr(wm_service, "add_experiences"):
                    wm_service.add_experiences(experiences)

        except Exception as e:
            logger.debug(f"World model update from receipts failed: {e}")

    async def _get_recent_receipts(
        self,
        intent_type: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve recent receipts for a given intent type.

        Args:
            intent_type: Intent type to filter by
            limit: Maximum receipts to retrieve

        Returns:
            List of receipt dicts
        """
        if not hasattr(self._router, "_stigmergy_learner"):
            return []

        stigmergy = self._router._stigmergy_learner
        return stigmergy.get_patterns(intent_type=intent_type, limit=limit)

    async def _consult_knowledge_graph(
        self,
        intent: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Consult knowledge graph for action recommendations.

        NEXUS BRIDGE: Connects knowledge graph reasoning to execution planning.

        Args:
            intent: Intent to execute
            context: Execution context

        Returns:
            List of action recommendations from KG
        """
        try:
            from kagami_knowledge.reasoning_engine import get_reasoning_engine

            reasoning_engine = get_reasoning_engine()
            recommendations = await reasoning_engine.infer_action(intent, context)

            kg_suggestions = []
            for rec in recommendations:
                kg_suggestions.append(
                    {
                        "action": rec.action,
                        "confidence": rec.confidence,
                        "rationale": rec.rationale,
                        "success_rate": rec.success_rate,
                        "required_tools": rec.required_tools,
                        "potential_pitfalls": rec.potential_pitfalls,
                    }
                )

            return kg_suggestions

        except (ImportError, AttributeError, RuntimeError) as e:
            logger.debug(f"Knowledge graph consultation failed: {e}")
            return []

    async def update_knowledge_graph(
        self,
        receipts: list[dict[str, Any]],
    ) -> int:
        """Update knowledge graph from receipts.

        Args:
            receipts: List of receipt dictionaries

        Returns:
            Number of knowledge nodes added
        """
        try:
            from kagami_knowledge.receipt_to_kg import get_receipt_extractor

            extractor = get_receipt_extractor()
            nodes_added = await extractor.populate_kg(receipts)

            logger.info(f"Remembering {nodes_added} new things from recent work")
            return nodes_added

        except (ImportError, AttributeError, RuntimeError) as e:
            logger.warning(f"Couldn't update my knowledge graph: {e}")
            return 0

    async def enable_continuous_learning(
        self,
        poll_interval: float = 0.1,
        batch_size: int = 5,
    ) -> None:
        """Enable continuous background learning from receipts.

        Args:
            poll_interval: Receipt polling interval (seconds)
            batch_size: Max receipts per batch
        """
        if self._continuous_mind is not None:
            logger.warning("Already learning continuously")
            return

        from kagami.core.learning.continuous_mind import create_continuous_mind
        from kagami.core.learning.receipt_learning import get_learning_engine

        learning_engine = get_learning_engine()

        self._continuous_mind = create_continuous_mind(
            learning_engine=learning_engine,
            organism=self,
            poll_interval=poll_interval,
            batch_size=batch_size,
        )

        async def receipt_source() -> list[dict[str, Any]]:
            """Poll stigmergy learner for new receipts."""
            if not hasattr(self._router, "_stigmergy_learner"):
                return []
            stigmergy = self._router._stigmergy_learner
            return list(stigmergy.receipt_cache)

        self._continuous_mind.set_receipt_source(receipt_source)
        await self._continuous_mind.start()

        logger.info(
            f"Always learning now (checking every {poll_interval}s, "
            f"processing up to {batch_size} at a time)"
        )

    async def disable_continuous_learning(self) -> None:
        """Disable continuous learning."""
        if self._continuous_mind is None:
            return

        await self._continuous_mind.stop()
        self._continuous_mind = None
        logger.info("Pausing continuous learning")

    def get_continuous_mind_stats(self) -> dict[str, Any] | None:
        """Get continuous mind statistics.

        Returns:
            Statistics dictionary or None if not enabled
        """
        if self._continuous_mind is None:
            return None

        return self._continuous_mind.get_stats()


__all__ = ["LearningMixin"]
