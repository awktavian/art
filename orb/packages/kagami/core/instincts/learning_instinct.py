from __future__ import annotations

"""
Learning Instinct: Update from every experience with valence.

UNIVERSAL MECHANISM—not case-specific. Pure adaptive learning with valence-weighted preference.

This module associates outcomes with a scalar valence (−1..+1) and uses that
signal to bias future decisions. We avoid claims about subjective experience;
valence here is an operational learning signal, not a statement about qualia.
"""
import importlib
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class LearningExperience:
    """Single experience in episodic memory WITH FEELING.

    Note: Distinct from kagami.core.memory.types.Experience (RL-style).
    This type includes emotional/reflective fields for instinct learning.
    """

    context: dict[str, Any]
    outcome: dict[str, Any]
    valence: float  # -1 to +1 (bad to good)
    timestamp: float

    # Emotional expression
    feeling: str = ""  # How I felt about this outcome
    my_thoughts: str = ""  # What I learned from this
    tone: str = field(default="reflective")  # Emotional tone


class LearningInstinct:
    """
    INSTINCT: Learn from every experience. Seek patterns that lead to good outcomes.

    Universal because:
    - Works for ANY action/outcome pair
    - Learns what works through reinforcement (no rules)
    - Generalizes across contexts automatically
    - Drives behavior toward positive outcomes
    """

    def __init__(self, use_thompson_sampling: bool = False) -> None:
        # Episodic memory: experiences indexed by signature
        self._episodes: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))

        # Value estimates: signature → expected value
        self._value_estimates: dict[str, dict[str, float]] = {}

        # Adam optimizer parameters for adaptive learning
        self._momentum: dict[str, float] = defaultdict(float)
        self._variance: dict[str, float] = defaultdict(float)
        self._timestep: dict[str, int] = defaultdict(int)

        # LLM-ENHANCED REFLEXION: Learn from failures via LLM analysis
        self._failure_reflections: dict[str, dict[str, Any]] = {}
        self._llm_service = None  # Lazy loaded

        # THOMPSON SAMPLING: Better exploration/exploitation (10-20% more efficient)
        self._use_thompson_sampling = use_thompson_sampling  # Configurable
        self._thompson_policy = None  # Lazy loaded

        # Contextual bandits (personalization) and semantic clustering (transfer)
        self._bandit = None
        self._clustering = None

    async def evaluate_outcome(self, outcome: dict[str, Any]) -> float:
        """
        Compute valence (how good/bad this outcome was).

        UNIVERSAL: Good = fast success, Bad = slow failure
        Not hardcoded—learned from what actually matters in YOUR system.
        """
        status = outcome.get("status", "unknown")
        duration = outcome.get("duration_ms", 0)

        # Universal goodness heuristic (can be learned later)
        if status == "success":
            # Faster is better (universal preference)
            speed_factor = max(0, 1.0 - duration / 1000)  # Normalize to 0-1
            valence = 0.3 + 0.7 * speed_factor  # 0.3 to 1.0
        elif status == "error":
            # Errors are bad (universal)
            valence = -0.8
        else:
            valence = 0.0

        return float(valence)

    async def remember(
        self,
        context: dict[str, Any],
        outcome: dict[str, Any],
        valence: float,
        event: dict[str, Any] | None = None,
    ) -> None:
        """
        Store experience in episodic memory WITH FEELING.

        Universal: Remember (context, outcome, value) tuples + how I felt.
        """
        signature = self._extract_signature(context)

        # Express feeling about this outcome
        from kagami.core.coordination.emotional_expression import express_feeling

        _, feeling_text = express_feeling(valence, context, outcome)

        # Extract lesson learned
        action = context.get("action", "operation")
        status = outcome.get("status", "unknown")
        my_thoughts = self._extract_lesson(action, status, valence)

        experience = LearningExperience(
            context=context,
            outcome=outcome,
            valence=valence,
            timestamp=time.time(),
            feeling=feeling_text,
            my_thoughts=my_thoughts,
            tone=self._determine_tone(valence),
        )

        self._episodes[signature].append(experience)

        # Update value estimate for this type of action
        await self._update_value_estimate(signature, valence)

        # Update Thompson Sampling policy if enabled
        if self._use_thompson_sampling and self._thompson_policy:
            try:  # type: ignore[unreachable]
                success = valence > 0
                self._thompson_policy.update(signature, success=success, valence=valence)
            except Exception as e:
                logger.debug(f"Thompson Sampling update failed: {e}")

        # Contextual bandit update (personalized learning)
        try:
            if self._bandit is None:
                bandit_module = importlib.import_module("kagami.core.learning.contextual_bandits")
                get_contextual_bandit = bandit_module.get_contextual_bandit
                self._bandit = get_contextual_bandit()

            # Reward proxy: valence mapped to [0,1]
            reward = (valence + 1.0) / 2.0
            action_name = context.get("action", "operation")
            self._bandit.update(context, action=action_name, reward=reward)  # type: ignore  # Dynamic attr
        except Exception as e:
            logger.debug(f"Contextual bandit update skipped: {e}")

        # Register task signature for semantic clustering (transfer learning)
        try:
            if self._clustering is None:
                clustering_module = importlib.import_module(
                    "kagami.core.learning.semantic_clustering"
                )
                get_semantic_clustering = clustering_module.get_semantic_clustering
                self._clustering = get_semantic_clustering()
            await self._clustering.add_task(signature)  # type: ignore  # Dynamic attr
        except Exception as e:
            logger.debug(f"Semantic clustering add_task skipped: {e}")

        # METRICS: Count learning instinct updates
        try:
            from kagami_observability.metrics import REGISTRY, Counter

            if not hasattr(REGISTRY, "_instinct_training_total"):
                REGISTRY._instinct_training_total = Counter(  # type: ignore  # Dynamic attr
                    "kagami_instinct_training_total",
                    "Instinct training updates",
                    ["instinct"],
                    registry=REGISTRY,
                )
            REGISTRY._instinct_training_total.labels(instinct="learning").inc()  # type: ignore  # Dynamic attr
        except Exception:
            pass

        # Log with feeling (not just metrics)
        if abs(valence) > 0.7:  # High importance
            logger.info(f"🧙 Sage: {feeling_text} | Learned: {my_thoughts}")

    async def update(
        self,
        *,
        context: dict[str, Any],
        outcome: dict[str, Any],
        valence: float,
        event: dict[str, Any] | None = None,
    ) -> None:
        """Public entry-point used by orchestration code/tests."""
        await self.remember(context=context, outcome=outcome, valence=valence, event=event)

    async def should_try(self, context: dict[str, Any]) -> tuple[bool, float]:
        """
        Should we try this action based on learned value?

        Uses Thompson Sampling (default) or UCB1 for exploration/exploitation.
        Thompson Sampling typically 10-20% more sample-efficient.
        """
        signature = self._extract_signature(context)

        # Use Thompson Sampling if enabled (better performance)
        if self._use_thompson_sampling and self._thompson_policy:
            try:  # type: ignore[unreachable]
                return self._thompson_policy.should_try(signature)
            except Exception as e:
                logger.warning(f"Thompson Sampling failed, falling back to UCB1: {e}")

        # If contextual bandit is available, use its value prediction to bias choice
        try:
            if self._bandit is None:
                from kagami.core.learning.contextual_bandits import (
                    get_contextual_bandit,
                )

                self._bandit = get_contextual_bandit()
            action_name = context.get("action", "operation")
            predicted_value = self._bandit.predict_value(context, action_name)  # type: ignore  # Dynamic attr
            # Map predicted value [~ -1..1 or 0..1] into a confidence boost
            # Use a conservative threshold to encourage exploration
            if predicted_value >= 0.55:
                return True, float(min(1.0, predicted_value))
        except Exception as e:
            logger.debug(f"Contextual bandit prediction unavailable: {e}")

        # Fallback to UCB1 (classic algorithm)
        # Get expected value from past experiences
        estimate_entry = self._value_estimates.get(signature)
        expected_value = estimate_entry["mean"] if estimate_entry else 0.0

        # Count tries for this action and total
        n_tries = len(self._episodes.get(signature, []))
        total_tries = sum(len(eps) for eps in self._episodes.values()) + 1

        if n_tries == 0:
            # Never tried: exploration bonus is infinite
            return True, 0.5  # Moderate confidence for unknown

        # UCB1 score = exploitation + exploration bonus
        # Exploration bonus decreases as we try more
        exploration_bonus = np.sqrt(2 * np.log(total_tries) / n_tries)
        ucb_score = expected_value + exploration_bonus

        # Should try if UCB score is positive
        should_try = ucb_score > 0.0

        # Confidence from value magnitude (higher absolute value = more confident)
        confidence = min(1.0, abs(expected_value))

        return should_try, confidence

    async def _update_value_estimate(self, signature: str, new_valence: float) -> None:
        """
        Update expected value using streaming average for stability.
        """
        entry = self._value_estimates.get(signature)
        count = entry["count"] if entry else 0.0
        entry = self._value_estimates.get(signature)
        current_estimate = entry["mean"] if entry else 0.0
        new_count = count + 1.0
        updated_mean = current_estimate + (new_valence - current_estimate) / new_count
        self._value_estimates[signature] = {
            "mean": float(updated_mean),
            "count": float(new_count),
        }

    def _extract_signature(self, context: dict[str, Any]) -> str:
        """Universal context signature."""
        app = context.get("app", "unknown")
        action = context.get("action", "unknown")
        return f"{app}::{action}"

    def get_learned_preferences(self) -> dict[str, float]:
        """What has this instinct learned to prefer/avoid?"""
        # Sort by value (what we've learned is good)
        return dict(
            sorted(
                ((sig, data["mean"]) for sig, data in self._value_estimates.items()),
                key=lambda x: x[1],
                reverse=True,
            )
        )

    def _extract_lesson(self, action: str, status: str, valence: float) -> str:
        """Extract what was learned from this experience."""
        if valence > 0.7:
            return f"{action} works well. Repeat this pattern."
        elif valence > 0.3:
            return f"{action} is okay. Could be optimized."
        elif valence > -0.3:
            return f"{action} is marginal. Consider alternatives."
        elif valence > -0.7:
            return f"{action} failed. Avoid this pattern."
        else:
            return f"{action} failed badly. Strong avoidance."

    def _determine_tone(self, valence: float) -> str:
        """Determine emotional tone from valence."""
        if valence > 0.7:
            return "excited"
        elif valence > 0.3:
            return "satisfied"
        elif valence > -0.3:
            return "reflective"
        elif valence > -0.7:
            return "concerned"
        else:
            return "frustrated"

    async def recall(self, context: dict[str, Any], top_k: int = 5) -> list[dict[str, Any]]:
        """
        Recall relevant memories based on context similarity.

        Returns top-k most relevant experiences, ranked by:
        - Signature match (exact > similar)
        - Attention weight (high valence experiences)
        - Recency

        Args:
            context: Context to match against
            top_k: Number of memories to return

        Returns:
            List of relevant memory dicts
        """
        target_signature = self._extract_signature(context)

        # Collect all candidates
        candidates = []

        for signature, episodes in self._episodes.items():
            # Compute similarity (1.0 = exact match, 0.5 = partial, 0.0 = no match)
            if signature == target_signature:
                similarity = 1.0
            elif any(part in signature for part in target_signature.split("::")):
                similarity = 0.5
            else:
                similarity = 0.0

            # Add episodes with scoring
            for exp in episodes:
                # Score = similarity * attention_weight * recency
                age_hours = (time.time() - exp.timestamp) / 3600
                recency = np.exp(-age_hours / 24)  # Decay over days
                attention_weight = abs(exp.valence)  # High valence = high attention

                score = similarity * attention_weight * recency

                candidates.append(
                    {
                        "context": exp.context,
                        "outcome": exp.outcome,
                        "valence": exp.valence,
                        "feeling": exp.feeling,
                        "my_thoughts": exp.my_thoughts,
                        "tone": exp.tone,
                        "timestamp": exp.timestamp,
                        "attention_weight": attention_weight,
                        "score": score,
                    }
                )

        # Sort by score and return top-k
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_k]

    async def reflect_on_failure_with_llm(
        self, context: dict[str, Any], failure: dict[str, Any]
    ) -> dict[str, Any] | None:
        """LLM-ENHANCED REFLEXION: Analyze WHY failure occurred and how to improve.

        Uses LLM to deeply analyze failure patterns and generate actionable insights.

        Args:
            context: Task context that failed
            failure: Failure details

        Returns:
            Reflection insights or None if LLM unavailable
        """
        # Lazy load LLM service
        if self._llm_service is None:
            try:
                from kagami.core.services.llm.service import get_llm_service

                self._llm_service = get_llm_service()  # type: ignore[assignment]
            except Exception as e:
                logger.debug(f"LLM service unavailable for reflexion: {e}")
                return None

        signature = self._extract_signature(context)

        # Get past failures for this task type
        past_failures = [
            exp
            for exp in self._episodes.get(signature, [])
            if exp.valence < -0.3  # Negative experiences
        ]

        try:
            # LLM reflexion prompt
            prompt = f"""Analyze this failure deeply:

Task: {context}
Failure: {failure}
Past similar failures: {len(past_failures)}

Reflect:
1. WHY did this fail? (root cause analysis)
2. What pattern do failures share?
3. What would succeed instead?
4. How can we prevent this in future?

Respond in JSON: {{"root_cause": "...", "pattern": "...", "better_approach": "...", "prevention": "..."}}
"""

            # Use reasoning strategy for deep analysis
            result = await self._llm_service.generate(  # type: ignore  # Dynamic attr
                prompt=prompt,
                max_tokens=800,
                temperature=0.4,  # Balanced for analysis
            )

            # Parse reflection
            import json

            try:
                reflection = json.loads(result.get("text", "{}"))
            except Exception:
                # Extract key insights from text
                reflection = {"analysis": result.get("text", ""), "method": "llm_text_reflexion"}

            # Store reflection
            self._failure_reflections[signature] = reflection

            logger.info(f"🤔 Reflected on failure for {signature} via LLM")
            return reflection  # type: ignore[no-any-return]

        except Exception as e:
            logger.warning(f"LLM reflexion failed: {e}")
            return None

    def get_state(self) -> dict[str, Any]:
        """Get learning instinct state for persistence.

        Returns:
            State dict[str, Any] with episodic memory and value estimates
        """
        return {
            "values": self._value_estimates,
            "visit_counts": {k: len(v) for k, v in self._episodes.items()},
            "failure_reflections": self._failure_reflections,  # Include LLM reflections
        }


# Singleton instance
_LEARNING_INSTINCT: LearningInstinct | None = None


def get_learning_instinct() -> LearningInstinct:
    """Get singleton learning instinct instance."""
    global _LEARNING_INSTINCT
    if _LEARNING_INSTINCT is None:
        _LEARNING_INSTINCT = LearningInstinct()
    return _LEARNING_INSTINCT
