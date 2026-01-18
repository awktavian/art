# Standard library imports
import importlib
import json
import logging
import time
from pathlib import (
    Path,
)
from typing import Any

# Local imports
from kagami.core.async_utils import safe_create_task
from kagami.core.coordination.emotional_expression import (
    current_system_feeling,
)
from kagami.core.instincts.learning_instinct import get_learning_instinct

"""
Central Experience Store - Single Source of Truth for System Experiences

This is the WIRING that connects:
- RL decision making (LLMGuidedActor._reasoning_traces)
- Learning instinct (LearningInstinct._episodes)
- Emotional expression (EmotionalExpressionEngine._recent_valences)
- Replay buffer (prioritized_replay)
- Capsule persistence (state/capsule.json)

PRINCIPLE: Every experience flows through here. No isolated memory pools.
"""


logger = logging.getLogger(__name__)


class CentralExperienceStore:
    """Single source of truth for all system experiences.

    Wires together:
    - Recent experiences (for /api/self/feeling)
    - Emotional engine (for feeling computation)
    - Learning instinct (episodic memory)
    - Replay buffer (RL training)
    - Capsule persistence (survive restarts)
    """

    def __init__(self) -> None:
        self._recent_experiences: list[dict[str, Any]] = []
        self._max_recent = 20
        self._capsule_path = Path("state/capsule.json")
        self._load_from_capsule()

    def _load_from_capsule(self) -> None:
        """Load recent experiences from capsule.json on startup."""
        try:
            if self._capsule_path.exists():
                if self._capsule_path.suffix == ".tmp":
                    return
                with open(self._capsule_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self._recent_experiences = data.get("recent_experiences", [])[
                        -self._max_recent :
                    ]
                    logger.info(f"Loaded {len(self._recent_experiences)} experiences from capsule")
        except Exception as e:
            logger.warning(f"Could not load experiences from capsule: {e}")

    async def record_experience(  # type: ignore[no-untyped-def]
        self,
        context: dict[str, Any],
        action: dict[str, Any],
        outcome: dict[str, Any],
        valence: float,
        **kwargs,
    ) -> None:
        """Record experience in ALL subsystems.

        This is the central wiring point that connects everything.

        Args:
            context: Operation context (action, app, target, params)
            action: Action taken (with tier/reasoning info)
            outcome: Result (status, duration_ms, etc)
            valence: Emotional weight (-1.0 to +1.0)
            **kwargs: Additional metadata (tier, llm_used, reasoning_trace, etc)
        """

        def _serialize(obj: Any) -> Any:
            if hasattr(obj, "__dict__"):
                return {k: _serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
            elif isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            elif isinstance(obj, (list[Any], tuple[Any, ...])):
                return [_serialize(item) for item in obj]
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            else:
                return str(obj)

        correlation_id = (
            context.get("correlation_id")
            or action.get("correlation_id")
            or kwargs.get("correlation_id")
            or f"exp_{int(time.time() * 1000)}"
        )
        experience = {
            "correlation_id": correlation_id,
            "context": _serialize(context),
            "action": _serialize(action),
            "outcome": _serialize(outcome),
            "valence": valence,
            "timestamp": time.time(),
            **{k: _serialize(v) for k, v in kwargs.items()},
        }
        self._recent_experiences.append(experience)
        if len(self._recent_experiences) > self._max_recent:
            self._recent_experiences.pop(0)
        try:
            from kagami.core.coordination.emotional_expression import (
                get_emotional_engine,
            )

            engine = get_emotional_engine()
            engine._recent_valences.append(valence)
            if len(engine._recent_valences) > 20:
                engine._recent_valences.pop(0)
            if valence < -0.5:
                engine._consecutive_failures += 1
            elif valence > 0.5:
                engine._consecutive_failures = 0
            engine._total_experiences += 1
            if "prediction_error_ms" in outcome:
                engine._recent_prediction_errors.append(outcome["prediction_error_ms"])
                if len(engine._recent_prediction_errors) > 20:
                    engine._recent_prediction_errors.pop(0)
            if "threat_score" in outcome:
                engine._recent_threat_scores.append(outcome["threat_score"])
                if len(engine._recent_threat_scores) > 20:
                    engine._recent_threat_scores.pop(0)
            if "novelty" in outcome:
                engine._recent_novelty_scores.append(outcome["novelty"])
                if len(engine._recent_novelty_scores) > 20:
                    engine._recent_novelty_scores.pop(0)
        except Exception as e:
            logger.warning(f"Could not update emotional engine: {e}")
        if abs(valence) > 0.7:
            try:
                learning = get_learning_instinct()
                await learning.remember(context=context, outcome=outcome, valence=valence)
            except Exception as e:
                logger.warning(f"Could not store in learning instinct: {e}")
        # ============================================================
        # UNIFIED REPLAY BUFFER (Dec 6, 2025)
        # ============================================================
        # Consolidated from 6 separate replay implementations
        try:
            from kagami.core.memory.unified_replay import (
                UnifiedExperience,
                get_unified_replay,
            )

            sfk_module = importlib.import_module("kagami.core.learning.semantic_flow_kernel")
            SemanticFlowKernel = sfk_module.SemanticFlowKernel

            replay = get_unified_replay()

            # Base priority from prediction error or valence magnitude
            base_priority = outcome.get("prediction_error_ms", abs(valence) * 100)

            # Compute semantic flow multiplier (bounded, see implementation)
            agent_ref = kwargs.get("agent")
            from kagami.core.unified_agents import get_unified_organism

            organism_ref = get_unified_organism()
            _ = organism_ref.colonies

            multiplier = SemanticFlowKernel.compute_experience_multiplier(
                context=context,
                outcome=outcome,
                agent=agent_ref,
                organism=organism_ref,
                t=1.0,
                source="experience_store",
            )

            priority = float(base_priority or 1.0) * float(multiplier or 1.0)

            # Create unified experience (replaces old dict[str, Any] format)
            unified_exp = UnifiedExperience(
                experience_type="generic",
                context=context,
                action=action,
                outcome=outcome,
                valence=valence,
                priority=priority,
                td_error=priority,  # Use priority as td_error proxy
                surprisal=outcome.get("novelty", 0.0),
                coherence=1.0 - outcome.get("prediction_error_ms", 0.0) / 1000.0,
            )
            replay.add(unified_exp, priority=priority)
        except Exception as e:
            logger.warning(f"Could not store in replay buffer: {e}")
        # Trigger background enrichment tasks
        if len(self._recent_experiences) % 10 == 0:
            safe_create_task(self._save_to_capsule(), name="_save_to_capsule")
            safe_create_task(
                self._enrich_knowledge_systems(experience), name="_enrich_knowledge_systems"
            )

    async def _save_to_capsule(self) -> None:
        """Save recent experiences to capsule.json."""
        try:
            data: dict[str, Any]
            if not self._capsule_path.exists():
                logger.warning("Capsule file doesn't exist, creating with experiences only")
                data = {"recent_experiences": self._recent_experiences}
            else:
                try:
                    with open(self._capsule_path, encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
                data["recent_experiences"] = self._recent_experiences
            tmp_path = self._capsule_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_path.replace(self._capsule_path)
            logger.debug(f"Saved {len(self._recent_experiences)} experiences to capsule")
        except Exception as e:
            logger.warning(f"Could not save experiences to capsule: {e}")

    async def _enrich_knowledge_systems(self, experience: dict[str, Any]) -> None:
        """Enrich knowledge graph, relationships, and semantic memory from experience.

        This is the WIRING that makes the hive remember what it learns.
        """
        try:
            # 1. Add to knowledge graph
            await self._add_to_knowledge_graph(experience)

            # 2. Store in semantic memory
            await self._store_semantic_memory(experience)

            # 4. Trigger consolidation every 50 experiences
            if len(self._recent_experiences) % 50 == 0:
                safe_create_task(self._consolidate_memories(), name="_consolidate_memories")

        except Exception as e:
            logger.debug(f"Knowledge enrichment failed: {e}")

    async def _add_to_knowledge_graph(self, experience: dict[str, Any]) -> None:
        """Add experience to knowledge graph as a node."""
        try:
            from kagami_knowledge.knowledge_graph import get_knowledge_graph

            from kagami.core.services.embedding_service import get_embedding_service

            kg = get_knowledge_graph()
            emb_svc = get_embedding_service()

            context = experience.get("context", {})
            outcome = experience.get("outcome", {})

            # Create knowledge from experience
            action = context.get("action", "unknown")
            app = context.get("app", "unknown")
            status = outcome.get("status", "unknown")

            topic = f"{app}_{action}"
            content = f"Action: {action} by {app} resulted in {status}"

            # Get embedding for semantic connections
            embedding = emb_svc.embed_text(content)

            # Determine importance
            valence = abs(experience.get("valence", 0.5))

            await kg.add_knowledge(
                topic=topic,
                content=content,
                embedding=embedding,
                category=app,
                importance=valence,
            )

            logger.debug(f"📚 Added knowledge: {topic}")

        except Exception as e:
            logger.debug(f"Knowledge graph update failed: {e}")

    async def _store_semantic_memory(self, experience: dict[str, Any]) -> None:
        """Store experience in semantic memory."""
        try:
            import json
            from pathlib import Path

            semantic_path = Path("var/memory/semantic.json")
            semantic_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing
            if semantic_path.exists():
                with open(semantic_path) as f:
                    data = json.load(f)
            else:
                data = {"memories": []}

            # Create memory entry
            context = experience.get("context", {})
            outcome = experience.get("outcome", {})

            memory = {
                "content": f"{context.get('app', 'unknown')} performed {context.get('action', 'unknown')}",
                "type": "experiential",
                "timestamp": experience.get("timestamp", time.time()),
                "valence": experience.get("valence", 0.0),
                "context": context,
                "outcome": outcome,
            }

            data["memories"].append(memory)

            # Keep only recent memories (last 1000)
            if len(data["memories"]) > 1000:
                data["memories"] = data["memories"][-1000:]

            # Save
            with open(semantic_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"💭 Stored semantic memory ({len(data['memories'])} total)")

        except Exception as e:
            logger.debug(f"Semantic memory storage failed: {e}")

    async def _consolidate_memories(self) -> None:
        """Trigger memory consolidation."""
        try:
            from kagami.core.memory.consolidation import get_memory_consolidation

            consolidator = get_memory_consolidation()
            result = await consolidator.consolidate_memories()

            if result.get("status") == "success":
                logger.info(
                    f"💾 Consolidated {result.get('consolidated', 0)} memories into {result.get('clusters', 0)} clusters"
                )

        except Exception as e:
            logger.debug(f"Memory consolidation failed: {e}")

    def get_current_feeling(self) -> Any:
        """Get current emotional state using emotional engine with real data."""

        return current_system_feeling()

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about recent experiences."""
        if not self._recent_experiences:
            return {"count": 0, "positive": 0, "negative": 0, "neutral": 0, "avg_valence": 0.0}
        valences = [e["valence"] for e in self._recent_experiences]
        return {
            "count": len(self._recent_experiences),
            "positive": len([v for v in valences if v > 0.3]),
            "negative": len([v for v in valences if v < -0.3]),
            "neutral": len([v for v in valences if -0.3 <= v <= 0.3]),
            "avg_valence": sum(valences) / len(valences) if valences else 0.0,
            "recent_trend": (
                (
                    "improving"
                    if sum(valences[-5:]) > sum(valences[-10:-5])
                    else "declining"
                    if sum(valences[-5:]) < sum(valences[-10:-5])
                    else "stable"
                )
                if len(valences) >= 10
                else "insufficient_data"
            ),
        }


_experience_store: CentralExperienceStore | None = None


def get_experience_store() -> CentralExperienceStore:
    """Get singleton experience store instance."""
    global _experience_store
    if _experience_store is None:
        _experience_store = CentralExperienceStore()
    return _experience_store
