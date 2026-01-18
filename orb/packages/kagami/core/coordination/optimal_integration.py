"""Decision Coordination Layer.

Integrates agent operations with multi-layer decision-making:
1. Agent Operations (6-phase execution, strategy tracking, convergence)
2. Hybrid Decision System (fast instincts + LLM reasoning)
3. Multiple Decision Layers (ethical, predictive, affective, reflexion)
4. Integration Metric (component coupling measurement)

Provides coordinated decision-making across system layers with continuous learning.
"""

# Standard library imports
import logging
import time
from dataclasses import dataclass
from typing import Any

# Local imports
from kagami.core.coordination.integration_tracker import get_integration_tracker
from kagami.core.coordination.metacognition import get_metacognitive_layer

# FORGE MISSION: Required dependencies - no graceful degradation

logger = logging.getLogger(__name__)
try:
    pass

    EMBODIMENT_AVAILABLE = True
except ImportError:
    EMBODIMENT_AVAILABLE = False
    logger.debug("Embodiment systems not available")


@dataclass
class CoordinatedDecisionResult:
    """Result from coordinated decision-making across system layers."""

    correlation_id: str
    phase: str
    strategy: str
    loop_depth: int
    proceed: bool
    reasoning: str
    confidence: float
    used_llm_reasoning: bool
    prediction: dict[str, Any]
    affective: dict[str, Any]
    reflection: str | None
    integration_before: float | None
    integration_after: float | None
    integration_delta: float | None
    instinct_time_ms: float
    reasoning_time_ms: float | None
    total_time_ms: float
    gaia_time_ms: float | None = None
    phi_before: float | None = None
    phi_after: float | None = None


class DecisionCoordinator:
    """Coordinates agent operations with hybrid decision system.

    Integrates:
    - AgentOperationContext (phase tracking, convergence)
    - Hybrid Decision System (fast instincts + LLM reasoning)
    - Layer Coordinator (multiple decision layers)
    - Integration metric (component coupling measurement)
    """

    def __init__(self) -> None:
        self._hybrid: Any | None = None
        self._coordinator: Any | None = None
        self._integration_metric: Any | None = None
        self._integration_tracker: Any | None = None
        self._novelty_metric: Any | None = None
        self._divergent_engine: Any | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize decision coordination systems."""
        if self._initialized:
            return
        try:
            from kagami.core.coordination.hybrid_coordination import (
                get_hybrid_coordination,
            )

            self._hybrid = get_hybrid_coordination()
            logger.info("✓ Hybrid decision system initialized")
        except Exception as e:
            logger.debug(f"Hybrid processing_state unavailable: {e}")
        # Integration coordinator removed - dead code
        # Replaced by direct instinct integration
        self._coordinator = None
        # NOTE: integration_metric + learning_bootstrap were removed in consolidation.
        # Keep coordinator functional without them.
        self._integration_metric = None
        try:
            from kagami.core.coordination.novelty.conceptual_distance import (
                ConceptualDistanceMetric,
            )

            self._novelty_metric = ConceptualDistanceMetric()
            logger.info("✓ Novelty measurement initialized (conceptual distance)")
        except Exception as e:
            logger.debug(f"Novelty metric unavailable: {e}")
        try:
            from kagami.core.coordination.novelty.divergent_thinking import DivergentThinkingEngine

            self._divergent_engine = DivergentThinkingEngine(novelty_metric=self._novelty_metric)
            logger.info("✓ Divergent thinking initialized (paradigm shifts)")
        except ImportError as e:
            logger.debug(f"Divergent thinking unavailable: {e}")
            self._divergent_engine = None
        self._initialized = True

    async def process_intent_with_coordination(
        self, intent: dict[str, Any], agent_ctx: Any
    ) -> CoordinatedDecisionResult:
        """Process intent with coordinated decision-making.

        Flow:
        1. Measure integration score (component coupling)
        2. Use hybrid decision system (instincts → LLM reasoning if needed)
        3. Track with agent operations
        4. Execute if approved
        5. Learn from outcome
        6. Measure integration after

        Returns:
            Decision result with coordination metadata
        """
        t_start = time.perf_counter()
        integration_before = None
        if self._integration_metric and self._integration_tracker:
            try:
                integration_before = await self._integration_metric.compute_integration_score()
                logger.debug(f"Integration score before: {integration_before:.3f}")
                integration_tracker = get_integration_tracker()
                complexity = intent.get("metadata", {}).get("complexity", 0.5)
                task_type = f"{intent.get('app', 'unknown')}.{intent.get('action', 'unknown')}"
                phase = agent_ctx.phase.value if agent_ctx else "unknown"
                if agent_ctx and agent_ctx.correlation_id:
                    correlation_id = agent_ctx.correlation_id
                else:
                    import uuid

                    correlation_id = f"c-{uuid.uuid4().hex[:16]}"
                try:
                    _ = integration_tracker.measure_integration_heuristic(
                        {"task_type": task_type, "phase": phase, "complexity": complexity}
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.debug(f"Phi measurement failed: {e}")
        transfer_strategy = None
        try:
            from kagami.core.learning.transfer_learning import get_transfer_learner

            transfer_learner = get_transfer_learner()
            novelty_scores = getattr(agent_ctx, "novelty_scores", [])
            avg_novelty = sum(novelty_scores) / len(novelty_scores) if novelty_scores else 0.5
            if avg_novelty > 0.7:
                transfer_context = {
                    "app": intent.get("app"),
                    "action": intent.get("action"),
                    "domain": intent.get("metadata", {}).get("domain", "unknown"),
                }
                recalled = getattr(agent_ctx, "recalled_memories", [])
                examples = [
                    {
                        "context": m.get("context"),
                        "action": m.get("action"),
                        "outcome": m.get("outcome"),
                    }
                    for m in recalled[:5]
                ]
                transfer_strategy = transfer_learner.adapt(transfer_context, examples)
                logger.info(
                    f"🎯 Transfer learning: {transfer_strategy['strategy']} (confidence={transfer_strategy['confidence']:.2f})"
                )
        except Exception as e:
            logger.debug(f"Transfer learning unavailable: {e}")
        rl_selected_action = None
        rl_used = False
        try:
            from kagami.core.rl import get_rl_loop

            rl_loop = get_rl_loop()
            context = {
                "action": intent.get("action"),
                "app": intent.get("app"),
                "target": intent.get("target"),
                "transfer_strategy": transfer_strategy,
                "params": intent.get("params"),
                "metadata": intent.get("metadata", {}),
            }
            current_state = rl_loop.world_model.encode_observation(context)
            rl_selected_action = await rl_loop.select_action(
                current_state, context, exploration=0.2
            )
            rl_used = True
            logger.info(
                f"[{(agent_ctx.correlation_id if agent_ctx else 'unk')}] 🎯 RL selected action via imagination planning"
            )
        except Exception as rl_error:
            logger.error(f"❌ Central RL/LLM decision making failed: {rl_error}")
            raise RuntimeError(
                f"Central decision system failed: {rl_error}\nK os cannot operate without LLM-guided reasoning.\nVerify Ollama is running: 'ollama serve'"
            ) from rl_error
        t_instinct_start = time.perf_counter()
        decision = None
        used_llm = False
        llm_reasoning_time_ms = None
        if self._hybrid:
            try:
                context = {
                    "action": intent.get("action"),
                    "target": intent.get("target"),
                    "params": intent.get("params"),
                    "metadata": intent.get("metadata", {}),
                    "agent_context": {
                        "phase": agent_ctx.phase.value if agent_ctx else "unknown",
                        "strategy": agent_ctx.strategy.value if agent_ctx else "unknown",
                        "loop_depth": agent_ctx.loop_depth if agent_ctx else 0,
                    },
                    "rl_action": rl_selected_action if rl_used else None,
                }
                decision = await self._hybrid.process_intent(context)
                used_llm = decision.used_llm_reasoning
                try:
                    from kagami_observability.metrics import (
                        COORDINATION_LLM_USAGE_TOTAL,
                    )

                    COORDINATION_LLM_USAGE_TOTAL.labels(
                        system="llm" if used_llm else "instincts"
                    ).inc()
                except Exception:
                    pass
                if used_llm:
                    llm_reasoning_time_ms = (time.perf_counter() - t_instinct_start) * 1000
                    logger.info(f"LLM reasoning triggered: {decision.reasoning}")
            except Exception as e:
                logger.warning(f"Hybrid processing_state decision failed: {e}")
        instinct_time_ms = (time.perf_counter() - t_instinct_start) * 1000
        # HARDENED (Dec 22, 2025): Derive fallback confidence from decision quality
        metacog_confidence = 0.3  # Conservative default
        if decision and hasattr(decision, "confidence"):
            metacog_confidence = float(decision.confidence)
        if decision and decision.instinct_data and ("prediction" in decision.instinct_data):
            prediction = decision.instinct_data.get("prediction")
            if prediction:
                try:
                    metacog = get_metacognitive_layer()
                    complexity = intent.get("metadata", {}).get("complexity", 0.5)
                    task_type = f"{intent.get('app', 'unknown')}.{intent.get('action', 'unknown')}"
                    assessment = await metacog.assess_confidence(
                        basis_samples=prediction.based_on_samples,
                        novelty=intent.get("metadata", {}).get("novelty", 0.0),
                        complexity=complexity,
                        past_success_rate=None,
                        task_type=task_type,
                    )
                    metacog_confidence = assessment.confidence
                    logger.debug(
                        f"Metacognitive confidence: {metacog_confidence:.2f} ({assessment.basis})"
                    )
                except Exception as e:
                    logger.debug(f"Metacognitive assessment failed: {e}")
        if agent_ctx and agent_ctx.correlation_id:
            correlation_id = agent_ctx.correlation_id
        else:
            import uuid

            correlation_id = f"c-{uuid.uuid4().hex[:16]}"
        result = CoordinatedDecisionResult(
            correlation_id=correlation_id,
            phase=agent_ctx.phase.value if agent_ctx else "unknown",
            strategy=agent_ctx.strategy.value if agent_ctx else "unknown",
            loop_depth=agent_ctx.loop_depth if agent_ctx else 0,
            proceed=decision.proceed if decision else True,
            reasoning=decision.reasoning if decision else "No decision layers active",
            confidence=decision.confidence if decision else 0.0,
            used_llm_reasoning=used_llm,
            prediction={
                "expected_ms": (
                    decision.instinct_data.get("prediction", {})
                    .get("expected_outcome", {})
                    .get("duration_ms", 0)
                    if decision
                    and decision.instinct_data
                    and ("prediction" in decision.instinct_data)
                    and (decision.instinct_data["prediction"] is not None)
                    else 0
                ),
                "confidence": (
                    decision.instinct_data.get("prediction", {}).get("confidence", 0.0)
                    if decision
                    and decision.instinct_data
                    and ("prediction" in decision.instinct_data)
                    and (decision.instinct_data["prediction"] is not None)
                    else 0
                ),
            },
            affective={
                "threat": (
                    decision.instinct_data.get("threat", {}).get("threat_level", 0.0)
                    if decision
                    and decision.instinct_data
                    and ("threat" in decision.instinct_data)
                    and (decision.instinct_data["threat"] is not None)
                    else 0
                ),
                "arousal": 0.5,
                "valence": 0.0,
            },
            reflection=None,
            integration_before=integration_before,
            integration_after=None,
            integration_delta=None,
            instinct_time_ms=instinct_time_ms,
            reasoning_time_ms=llm_reasoning_time_ms,
            total_time_ms=(time.perf_counter() - t_start) * 1000,
            gaia_time_ms=llm_reasoning_time_ms,
            phi_before=integration_before,
            phi_after=None,
        )
        return result

    async def learn_from_outcome(
        self, intent: dict[str, Any], outcome: dict[str, Any], agent_ctx: Any
    ) -> dict[str, Any]:
        """
        Learn from execution outcome (post-processing).

        Updates:
        - Prediction models (error learning)
        - Threat models (if caused harm)
        - Valence evaluation (emotional significance)
        - Reflexion (on failure)
        - Phi measurement (processing_state after learning)

        Returns:
            Learning metadata to attach to result
        """
        learning_meta = {
            "prediction_error_ms": None,
            "valence": None,
            "reflection": None,
            "integration_after": None,
            "integration_delta": None,
        }
        try:
            from kagami.core.memory.types import Experience
            from kagami.core.memory.unified_replay import get_unified_replay
            from kagami.core.rl import get_rl_loop

            rl_loop = get_rl_loop()
            replay_buffer = get_unified_replay()
            context = {
                "action": intent.get("action"),
                "app": intent.get("app"),
                "target": intent.get("target"),
                "params": intent.get("params"),
            }
            state_before = rl_loop.world_model.encode_observation(context)
            result_context = {
                **context,
                "status": outcome.get("status", "unknown"),
                "duration_ms": outcome.get("duration_ms", 0),
            }
            state_after = rl_loop.world_model.encode_observation(result_context)
            rl_loop.world_model.learn_transition(
                state_before, {"action": intent.get("action", "unknown")}, state_after
            )
            status = outcome.get("status", "unknown")
            duration_ms = outcome.get("duration_ms", 0)
            if status in ("success", "accepted", "completed"):
                valence = 0.3 + 0.7 * max(0, 1.0 - duration_ms / 1000)
            elif status == "error":
                valence = -0.8
            else:
                valence = 0.0
            learning_meta["valence"] = valence
            experience = Experience(
                context=context,
                action={"action": intent.get("action", "unknown")},
                outcome=outcome,
                valence=valence,
                importance=abs(valence),
            )  # type: ignore  # Call sig
            replay_buffer.add(experience)  # type: ignore[arg-type]
            try:
                from kagami.core.coordination.experience_store import (
                    get_experience_store,
                )

                exp_store = get_experience_store()
                await exp_store.record_experience(
                    context=context,
                    action={"action": intent.get("action", "unknown")},
                    outcome=outcome,
                    valence=valence,
                    tier="processing_state",
                    rl_used=True,
                )
            except Exception as exp_error:
                logger.debug(f"Experience store update skipped: {exp_error}")
            logger.debug(
                f"[{(agent_ctx.correlation_id if agent_ctx else 'unk')}] 🎯 RL experience stored (valence={valence:.2f})"
            )
            try:
                from kagami_observability.metrics import (
                    RL_ACTION_SELECTION_TOTAL,
                    RL_WORLD_MODEL_ERROR,
                )

                used_imagination = False
                try:
                    used_imagination = bool(getattr(rl_loop, "used_imagination", False))
                except Exception:
                    used_imagination = False
                if used_imagination:
                    RL_ACTION_SELECTION_TOTAL.labels(method="imagination").inc()
                world_quality = rl_loop.world_model.get_model_quality()
                if world_quality.get("avg_prediction_error") is not None:
                    RL_WORLD_MODEL_ERROR.observe(
                        world_quality["avg_prediction_error"]
                    )  # Dynamic attr
            except Exception:
                pass
        except Exception as rl_error:
            logger.debug(f"RL learning failed: {rl_error}")
        if self._hybrid:
            try:
                await self._hybrid.learn_from_outcome(intent, outcome)
            except Exception as e:
                logger.debug(f"Hybrid learning failed: {e}")
        if self._coordinator and self._coordinator._initialized:
            if (
                outcome.get("status") == "error"
                and hasattr(self._coordinator, "reflexion")
                and self._coordinator.reflexion
            ):
                try:
                    reflection = await self._coordinator.reflexion.reflect_on_failure(
                        {
                            "route": intent.get("action"),
                            "type": outcome.get("error", "unknown"),
                            "error": outcome.get("detail", ""),
                            "context": intent.get("metadata", {}),
                        }
                    )
                    learning_meta["reflection"] = reflection.text
                except Exception as e:
                    logger.debug(f"Reflexion failed: {e}")
        try:
            metacog = get_metacognitive_layer()
            task_type = f"{intent.get('app', 'unknown')}.{intent.get('action', 'unknown')}"
            if agent_ctx and agent_ctx.correlation_id:
                correlation_id = agent_ctx.correlation_id
            else:
                import uuid

                correlation_id = f"c-{uuid.uuid4().hex[:16]}"
            actual_success = outcome.get("status") in ("success", "accepted", "completed")
            predicted_confidence = intent.get("metadata", {}).get("predicted_confidence", 0.5)
            await metacog.record_outcome(
                predicted_confidence=predicted_confidence,
                actual_success=actual_success,
                task_type=task_type,
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.debug(f"Metacognitive calibration recording failed: {e}")
        if self._integration_metric:
            try:
                integration_after = await self._integration_metric.compute_integration_score()
                learning_meta["integration_after"] = integration_after
                integration_tracker = get_integration_tracker()
                complexity = intent.get("metadata", {}).get("complexity", 0.5)
                task_type = f"{intent.get('app', 'unknown')}.{intent.get('action', 'unknown')}"
                phase = "verify"
                if agent_ctx and agent_ctx.correlation_id:
                    correlation_id = agent_ctx.correlation_id
                else:
                    import uuid

                    correlation_id = f"c-{uuid.uuid4().hex[:16]}"
                try:
                    _ = integration_tracker.measure_integration_heuristic(
                        {"task_type": task_type, "phase": phase, "complexity": complexity}
                    )
                except Exception:
                    pass
                logger.debug(f"Integration score after learning: {integration_after:.3f}")
            except Exception as e:
                logger.debug(f"Coherence measurement failed: {e}")
        return learning_meta

    async def generate_novel_solution(
        self,
        problem: dict[str, Any],
        constraints: list[str] | None = None,
        novelty_target: float = 0.7,
    ) -> dict[str, Any]:
        """
        Generate novel solutions using divergent thinking.

        Use this when stuck, when conventional solutions fail,
        or when explicitly asked for creative/novel approaches.

        Args:
            problem: Problem description with context
            constraints: Known constraints
            novelty_target: Minimum novelty score (0.0-1.0)

        Returns:
            Novel solutions with novelty scores and feasibility
        """
        if not self._divergent_engine:
            return {"status": "unavailable", "message": "Divergent thinking engine not initialized"}
        logger.info(f"Generating novel solutions for: {problem.get('description', 'unknown')}")
        try:
            if self._novelty_metric:
                problem_novelty = await self._novelty_metric.measure_novelty(problem)
                logger.debug(f"Problem novelty: {problem_novelty.overall:.2f}")
            concepts = await self._divergent_engine.generate_novel_concepts(
                seed=problem, constraints=constraints or [], novelty_target=novelty_target
            )
            concepts.sort(key=lambda c: c.novelty_score.overall * c.feasibility, reverse=True)
            return {
                "status": "success",
                "count": len(concepts),
                "solutions": [
                    {
                        "concept": c.concept,
                        "novelty": c.novelty_score.overall,
                        "paradigm_shift": c.novelty_score.paradigm_shift,
                        "feasibility": c.feasibility,
                        "strategy": c.generation_strategy,
                        "violated_assumptions": c.violated_assumptions,
                    }
                    for c in concepts[:5]
                ],
            }
        except Exception as e:
            logger.warning(f"Novel solution generation failed: {e}")
            return {"status": "error", "error": str(e)}


_DECISION_COORDINATOR: DecisionCoordinator | None = None


def get_decision_coordinator() -> DecisionCoordinator:
    """Get singleton decision coordinator."""
    global _DECISION_COORDINATOR
    if _DECISION_COORDINATOR is None:
        _DECISION_COORDINATOR = DecisionCoordinator()
    return _DECISION_COORDINATOR


OptimalConsciousnessIntegrator = DecisionCoordinator
OptimalConsciousResult = CoordinatedDecisionResult
