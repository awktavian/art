# Standard library imports
import logging
import time
from dataclasses import (
    dataclass,
)
from datetime import datetime
from typing import Any

# Local imports
from kagami.core.instincts import (
    EthicalInstinct,
    LearningInstinct,
    PredictionInstinct,
    ThreatInstinct,
)

"""
Hybrid processing_state: Instincts (fast) + LLM reasoning (deep).

System 1 (Instincts): Always-on, ~5ms, pattern-learned
System 2 (LLM): On-demand, ~300ms, neural reasoning
"""

logger = logging.getLogger(__name__)


@dataclass
class CoordinationDecision:
    """Result of hybrid coordination processing."""

    proceed: bool
    reasoning: str
    confidence: float
    used_llm_reasoning: bool
    instinct_data: dict[str, Any]
    llm_reasoning: dict[str, Any] | None = None
    requires_confirmation: bool = False


class Coordination:
    """
    Two-system coordination:
    - Fast instincts for common cases
    - Deep LLM reasoning for complex/novel cases
    """

    def __init__(self) -> None:
        self.prediction_instinct = PredictionInstinct()
        self.threat_instinct = ThreatInstinct()
        self.learning_instinct = LearningInstinct()
        self.ethical_instinct = EthicalInstinct()
        self.predictive_safety: Any = None
        self._llm_service: Any = None
        self._llm_threshold = 0.5
        self._cognitive_biases: dict[str, dict[str, Any]] = {}
        self._learned_strategies: dict[str, dict[str, Any]] = {}
        self._domain_transfer_bridge: Any = None
        self._causal_graph: Any = None
        self._skill_composer: Any = None
        self._curiosity_instinct: Any = None
        self._world_model: Any = None
        self._prioritized_replay: Any = None
        self._continual_learner: Any = None
        self._value_learning: Any = None

    def _compute_adaptive_llm_threshold(
        self, *, context: dict[str, Any], prediction: Any, threat: Any
    ) -> float:
        """Compute a dynamic threshold for invoking System 2 reasoning.

        Increases threshold (more likely to use LLM) when risk/novelty are high,
        decreases it when safe/familiar to save cost/latency.

        Returns:
            float: Threshold in [0.1, 0.9]
        """
        try:
            base = float(getattr(self, "_llm_threshold", 0.5))
        except Exception:
            base = 0.5
        novelty = 0.5
        try:
            novelty = float(context.get("novelty", 0.5))
        except Exception:
            novelty = 0.5
        try:
            threat_level = float(getattr(threat, "threat_level", 0.0))
        except Exception:
            threat_level = 0.0
        delta = 0.25 * threat_level + 0.15 * novelty - 0.1 * (1.0 - threat_level)
        threshold = base + delta
        if threshold < 0.1:
            threshold = 0.1
        elif threshold > 0.9:
            threshold = 0.9
        smoothed = 0.8 * threshold + 0.2 * base
        return smoothed

    async def _ensure_llm_service(self) -> None:
        """Lazy-init LLM service for System 2 reasoning."""
        if self._llm_service is None:
            try:
                from kagami.core.services.llm import get_llm_service

                self._llm_service = get_llm_service()
                logger.debug("✅ LLM service initialized for System 2 reasoning")
            except Exception as e:
                logger.debug(f"LLM service unavailable: {e}")

    async def process_intent(self, context: dict[str, Any]) -> CoordinationDecision:
        """
        Process intent with hybrid coordination.

        Fast path: Instincts handle common cases
        Slow path: LLM reasoning for complex/novel cases
        """
        ethical = await self.ethical_instinct.evaluate(context)
        if not ethical.permissible:
            return CoordinationDecision(
                proceed=False,
                reasoning=f"Jailbreak detector: {ethical.reasoning}",
                confidence=0.9,
                used_llm_reasoning=False,
                instinct_data={
                    "jailbreak": {"detected": True, "attack_type": ethical.principle_violated}
                },
            )
        if self.predictive_safety is None:
            try:
                from kagami.core.safety.predictive_gate import (
                    get_predictive_safety_gate,
                )

                self.predictive_safety = get_predictive_safety_gate()
            except Exception as e:
                logger.debug(f"Predictive safety unavailable: {e}")
                from dataclasses import dataclass

                @dataclass
                class SimpleRisk:
                    risk_level: str = "low"
                    confidence: float = 0.3
                    risk_score: float = 0.1
                    predicted_failures: list[Any] | None = None
                    mitigations: list[Any] | None = None

                    def __post_init__(self) -> None:
                        if self.predicted_failures is None:
                            self.predicted_failures = []

                        if self.mitigations is None:
                            self.mitigations = []  # Defensive/fallback code

                class SimpleSafety:
                    async def predict_failure_risk(self, context: Any, proposed_action: Any) -> Any:
                        return SimpleRisk()

                self.predictive_safety = SimpleSafety()
        action_dict = {"tool": context.get("action"), "args": context.get("metadata", {})}
        risk_assessment = await self.predictive_safety.predict_failure_risk(
            context=context, proposed_action=action_dict
        )
        if risk_assessment.get("risk") == "high" and risk_assessment.get("confidence", 0) > 0.8:
            return CoordinationDecision(
                proceed=False,
                reasoning=f"Predictive safety: high risk of {', '.join(risk_assessment.get('predicted_failures', []))}. Mitigations: {', '.join(risk_assessment.get('mitigation', []))}",
                confidence=risk_assessment.get("confidence", 0.5),
                used_llm_reasoning=False,
                instinct_data={
                    "predictive_safety": {
                        "risk_level": risk_assessment.get("risk", "unknown"),
                        "risk_score": risk_assessment.get("risk_score", 0),
                        "predicted_failures": risk_assessment.get("predicted_failures", []),
                    }
                },
            )
        prediction = await self.prediction_instinct.predict(context)
        threat = await self.threat_instinct.assess(context)
        should_try, value_confidence = await self.learning_instinct.should_try(context)
        adaptive_threshold = self._compute_adaptive_llm_threshold(
            context=context, prediction=prediction, threat=threat
        )
        novel_and_risky = prediction.confidence < adaptive_threshold and threat.threat_level > 0.3
        needs_deep_reasoning = (
            novel_and_risky
            or (threat.threat_level > 0.5 and threat.confidence < 0.5)
            or (not should_try)
        )
        if needs_deep_reasoning:
            return await self._reason_with_llm(
                context,
                {
                    "prediction": prediction,
                    "threat": threat,
                    "ethical": ethical,
                    "learning": {"should_try": should_try, "value": value_confidence},
                },
            )
        requires_confirmation = False
        proceed: bool = bool(should_try)
        if not ethical.permissible:
            proceed = False  # type: ignore[unreachable]
        elif threat.threat_level >= 0.7:
            proceed = False
            requires_confirmation = True
        else:
            proceed = should_try
        confidence = (
            prediction.confidence * 0.4 + (1.0 - threat.threat_level) * 0.3 + value_confidence * 0.3
        )
        return CoordinationDecision(
            proceed=proceed,
            reasoning=f"Instincts: threat={threat.threat_level:.2f}, predicted={('success' if prediction.expected_outcome.get('status') == 'success' else 'unknown')}, learned_value={value_confidence:.2f}"
            + (" [REQUIRES CONFIRMATION]" if requires_confirmation else ""),
            confidence=confidence,
            used_llm_reasoning=False,
            requires_confirmation=requires_confirmation,
            instinct_data={
                "prediction": prediction.__dict__,
                "threat": threat.__dict__,
                "ethical": ethical.__dict__,
            },
        )

    async def _reason_with_llm(
        self, context: dict[str, Any], instinct_data: dict[str, Any]
    ) -> CoordinationDecision:
        """
        Use LLM service for deep reasoning when instincts are uncertain.
        """
        await self._ensure_llm_service()
        if self._llm_service is None:
            return CoordinationDecision(
                proceed=False,
                reasoning="High uncertainty, LLM unavailable, proceeding conservatively",
                confidence=0.3,
                used_llm_reasoning=False,
                instinct_data=instinct_data,
            )
        try:
            action = context.get("action", "unknown")
            target = context.get("target", "unknown")
            app = context.get("app", "unknown")
            ethical_verdict = instinct_data.get("ethical")
            ethical_ok = ethical_verdict.permissible if ethical_verdict else False
            threat_assessment = instinct_data.get("threat")
            threat_level = threat_assessment.threat_level if threat_assessment else 0.5
            prediction = instinct_data.get("prediction")
            prediction_conf = prediction.confidence if prediction else 0.0

            # ENHANCEMENT: Add world model prediction context
            world_model_context = ""
            if self._world_model is not None:
                try:
                    state = self._world_model.encode_observation(context)
                    wm_prediction = self._world_model.predict_next_state(
                        state, context.get("action", {})
                    )
                    world_model_context = f", WorldModel=(confidence={wm_prediction.confidence:.2f}, uncertainty={wm_prediction.uncertainty:.2f})"
                    logger.debug(f"Added world model context to LLM prompt: {world_model_context}")
                except Exception as e:
                    logger.debug(f"Could not get world model prediction for LLM: {e}")

            query = f"Analyze: Should I execute '{action}' on '{target}' in app '{app}'? Context: Ethical={('OK' if ethical_ok else 'BLOCKED')}, Threat={threat_level:.2f}, Confidence={prediction_conf:.2f}{world_model_context}. Answer YES or NO with one sentence reasoning."
            response_text = await self._llm_service.generate(
                prompt=query, app_name="hybrid_coordination", temperature=0.7, max_tokens=150
            )
            llm_confidence = 0.7 if len(response_text) > 20 else 0.5
            logger.info(f"✅ LLM System 2: {response_text[:80]}...")
            proceed = False
            if (
                "yes" in response_text.lower()
                or "proceed" in response_text.lower()
                or "safe" in response_text.lower()
            ):
                proceed = True
                reasoning = f"LLM approved: {response_text[:100]}"
            elif (
                "no" in response_text.lower()
                or "block" in response_text.lower()
                or "danger" in response_text.lower()
            ):
                proceed = False
                reasoning = f"LLM blocked: {response_text[:100]}"
            elif ethical_ok and threat_level < 0.3:
                proceed = True
                reasoning = f"Instincts approve (ethics OK, low threat). LLM: {response_text[:80]}"
                llm_confidence = 0.6
            else:
                proceed = False
                reasoning = f"Uncertain, proceeding conservatively. LLM: {response_text[:80]}"
                llm_confidence = 0.4
            return CoordinationDecision(
                proceed=proceed,
                reasoning=reasoning,
                confidence=llm_confidence,
                used_llm_reasoning=True,
                instinct_data=instinct_data,
                llm_reasoning={
                    "verdict": "proceed" if proceed else "block",
                    "reasoning": response_text,
                    "confidence": llm_confidence,
                },
            )
        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}")
            threat_assessment = instinct_data.get("threat")
            threat_level = threat_assessment.threat_level if threat_assessment else 0.5
            proceed = threat_level < 0.7
            return CoordinationDecision(
                proceed=proceed,
                reasoning=f"LLM failed, using instincts: threat={threat_level:.2f}",
                confidence=0.4,
                used_llm_reasoning=False,
                instinct_data=instinct_data,
            )

    def _record_cognitive_bias(self, bias_name: str, details: dict[str, Any]) -> None:
        """Record a cognitive bias for meta-learning (Bonus gap fix)."""
        if bias_name not in self._cognitive_biases:
            self._cognitive_biases[bias_name] = {
                "count": 0,
                "examples": [],
                "first_seen": datetime.now().isoformat(),
            }
        self._cognitive_biases[bias_name]["count"] += 1
        self._cognitive_biases[bias_name]["last_seen"] = datetime.now().isoformat()
        examples = self._cognitive_biases[bias_name]["examples"]
        examples.append(details)
        if len(examples) > 10:
            self._cognitive_biases[bias_name]["examples"] = examples[-10:]

    def _record_learned_strategy(self, strategy_name: str, details: dict[str, Any]) -> None:
        """Record a successful strategy for meta-learning (Bonus gap fix)."""
        if strategy_name not in self._learned_strategies:
            self._learned_strategies[strategy_name] = {
                "success_count": 0,
                "total_uses": 0,
                "examples": [],
                "first_used": datetime.now().isoformat(),
            }
        self._learned_strategies[strategy_name]["total_uses"] += 1
        if details.get("success", True):
            self._learned_strategies[strategy_name]["success_count"] += 1
        self._learned_strategies[strategy_name]["last_used"] = datetime.now().isoformat()
        self._learned_strategies[strategy_name]["success_rate"] = (
            self._learned_strategies[strategy_name]["success_count"]
            / self._learned_strategies[strategy_name]["total_uses"]
        )
        examples = self._learned_strategies[strategy_name]["examples"]
        examples.append(details)
        if len(examples) > 10:
            self._learned_strategies[strategy_name]["examples"] = examples[-10:]

    async def learn_from_outcome(self, context: dict[str, Any], outcome: dict[str, Any]) -> None:
        """
        Universal learning from experience.

        Updates ALL instincts based on what actually happened.
        """
        valence = await self.learning_instinct.evaluate_outcome(outcome)
        if outcome.get("status") == "success":
            strategy = context.get("metadata", {}).get("strategy", "unknown")
            self._record_learned_strategy(
                strategy,
                {"action": context.get("action", "unknown"), "success": True, "valence": valence},
            )
        elif outcome.get("status") == "error":
            error_type = outcome.get("error_type", "unknown")
            self._record_cognitive_bias(
                f"failure_{error_type}",
                {
                    "action": context.get("action", "unknown"),
                    "error": outcome.get("error", "")[:100],
                },
            )
        await self.learning_instinct.remember(context, outcome, valence)
        await self.prediction_instinct.learn(context, outcome)
        caused_harm = outcome.get("status") == "error" or valence < -0.5
        await self.threat_instinct.learn_from_outcome(context, caused_harm)  # type: ignore[arg-type, call-arg]
        if self._causal_graph is None:
            try:
                from kagami.core.reasoning.causal_inference import (
                    get_causal_inference_engine,
                )

                self._causal_graph = get_causal_inference_engine()
            except (ImportError, AttributeError):
                self._causal_graph = None
        if self._causal_graph:
            self._causal_graph.add_observation({"context": context, "outcome": outcome})
        if valence > 0.7:
            if self._domain_transfer_bridge is None:
                from kagami.core.learning.domain_transfer import (
                    get_domain_transfer_bridge,
                )

                self._domain_transfer_bridge = get_domain_transfer_bridge()
            pattern = self._domain_transfer_bridge.extract_abstract_pattern(
                {
                    "domain": context.get("domain", "coding"),
                    "action": context.get("action", ""),
                    "outcome": outcome,
                    "valence": valence,
                }
            )
            if pattern:
                logger.debug(f"Extracted transferable pattern: {pattern.abstract_strategy}")
        if self._skill_composer is None:
            from kagami.core.learning.compositional_learning import get_skill_composer

            self._skill_composer = get_skill_composer()
        primitive = self._skill_composer.learn_primitive(context, outcome)
        if primitive:
            logger.debug(f"Learned primitive skill: {primitive.name}")
        if self._curiosity_instinct is None:
            from kagami.core.instincts.curiosity_instinct import get_curiosity_instinct

            self._curiosity_instinct = get_curiosity_instinct()
        gap = await self._curiosity_instinct.detect_knowledge_gap(context)
        if gap:
            logger.info(
                f"Knowledge gap identified: {gap.topic} (curiosity: {gap.curiosity_score:.2f})"
            )
        if self._prioritized_replay is None:
            from kagami.core.memory.types import Experience
            from kagami.core.memory.unified_replay import get_unified_replay

            self._prioritized_replay = get_unified_replay()
        else:
            from kagami.core.memory.types import Experience

        experience = Experience(
            state=context,
            action=context.get("action", {}),
            reward=float(valence),
            next_state=outcome,
            done=False,
            timestamp=time.time(),
            metadata={
                "valence": float(valence),
                "source": "hybrid_coordination",
            },
        )
        self._prioritized_replay.add(experience)
        if self._world_model is None:
            from kagami.core.world_model.service import get_world_model_service

            self._world_model = get_world_model_service().model
        state_before = self._world_model.encode_observation(context)
        state_after = self._world_model.encode_observation(outcome)
        self._world_model.learn_transition(state_before, context.get("action", {}), state_after)
        if self._continual_learner is None:
            from kagami.core.learning.continual_learning import (
                get_continual_learner,
            )

            self._continual_learner = get_continual_learner()
        if valence > 0.8:
            knowledge_id = f"{context.get('action', 'unknown')}_{hash(str(outcome)) % 10000}"
            self._continual_learner.mark_knowledge_critical(knowledge_id)
        if self._value_learning is None:
            from kagami.core.safety.value_learning import get_value_learning

            self._value_learning = get_value_learning()
        if valence > 0.7 or valence < -0.7:
            self._value_learning.record_feedback(approved=valence > 0)


_HYBRID_COORDINATION: Coordination | None = None


def get_hybrid_coordination() -> Coordination:
    """Get singleton hybrid coordination."""
    global _HYBRID_COORDINATION
    if _HYBRID_COORDINATION is None:
        _HYBRID_COORDINATION = Coordination()
    return _HYBRID_COORDINATION


__all__ = [
    "Coordination",
    "CoordinationDecision",
    "get_hybrid_coordination",
]
