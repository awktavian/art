"""Stigmergy Feedback Bridge — Elysia Feedback as Receipt Trails.

Bridges Elysia's user feedback system to Kagami's stigmergic learning,
creating a unified loop where:

1. User rates a query → stored as Elysia feedback (for few-shot retrieval)
2. Same rating emitted as stigmergy receipt (for ACO learning)
3. Updates cooperation metric (superorganism health)
4. Similar future queries → higher ACO probability for successful patterns

Scientific basis:
- Stigmergy: Theraulaz & Bonabeau (1999)
- ACO: Dorigo & Di Caro (1999)
- Superorganism: Reeve & Hölldobler (2007)

Created: December 7, 2025
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FeedbackRecord:
    """Record of user feedback."""

    query_id: str
    query: str
    response: str
    rating: int  # 1-5
    colony: str
    model: str
    timestamp: float
    semantic_pointer: list[float] | None = None


class ElysiaFeedbackBridge:
    """Bridge Elysia feedback to Kagami stigmergy system.

    When user rates a query positively:
    1. Store as Elysia feedback (Weaviate) for few-shot retrieval
    2. Emit as stigmergy receipt for ACO learning
    3. Update cooperation metric (superorganism health)

    This creates a unified learning loop:
    - Positive feedback → reinforced pheromone trail
    - Negative feedback → decayed trail
    - Similar future queries → higher ACO probability

    Usage:
        bridge = ElysiaFeedbackBridge(weaviate_adapter)

        # Record feedback
        result = await bridge.record_feedback(
            query="How does E8 work?",
            response="E8 is the optimal sphere packing...",
            rating=5,
            colony="grove",
            model="gemini-1.5-flash",
        )

        # Get few-shot examples for new query
        examples = await bridge.get_fewshot_examples("What is quantization?")
    """

    def __init__(
        self,
        weaviate_adapter: Any = None,
        min_positive_rating: int = 4,
        decay_rate: float = 0.98,
    ):
        """Initialize feedback bridge.

        Args:
            weaviate_adapter: WeaviateE8Adapter instance
            min_positive_rating: Rating threshold for positive examples
            decay_rate: Stigmergy pheromone decay rate
        """
        self.weaviate = weaviate_adapter
        self.min_positive_rating = min_positive_rating
        self.decay_rate = decay_rate

        # Lazy-loaded stigmergy learner
        self._stigmergy = None
        self._cooperation = None

    def _get_stigmergy(self) -> Any:
        """Lazy-load stigmergy learner."""
        if self._stigmergy is None:
            from kagami.core.unified_agents.memory.stigmergy import get_stigmergy_learner

            self._stigmergy = get_stigmergy_learner()  # type: ignore[assignment]
        return self._stigmergy

    def _get_cooperation(self) -> Any:
        """Lazy-load cooperation metric."""
        if self._cooperation is None:
            from kagami.core.unified_agents.memory.stigmergy import CooperationMetric

            self._cooperation = CooperationMetric()  # type: ignore[assignment]
        return self._cooperation

    async def record_feedback(
        self,
        query: str,
        response: str,
        rating: int,
        colony: str,
        model: str,
        query_id: str | None = None,
        semantic_pointer: list[float] | None = None,
    ) -> dict[str, Any]:
        """Record user feedback, updating both Weaviate and stigmergy.

        Args:
            query: Original user query
            response: Generated response
            rating: User rating (1-5 stars)
            colony: Colony that handled the query
            model: Model used for generation
            query_id: Optional query identifier
            semantic_pointer: Optional embedding of the query

        Returns:
            Dict with update statistics
        """
        timestamp = time.time()
        success = rating >= self.min_positive_rating

        result = {
            "timestamp": timestamp,
            "rating": rating,
            "success": success,
            "patterns_updated": 0,
            "f_star": 0.0,
            "bifurcation": False,
        }

        # Step 1: Store in Weaviate (for few-shot retrieval)
        if self.weaviate:
            try:
                await self.weaviate.store_feedback(
                    query=query,
                    response=response,
                    rating=rating,
                    colony=colony,
                    model=model,
                )
                result["weaviate_stored"] = True
            except Exception as e:
                logger.warning(f"Failed to store feedback in Weaviate: {e}")
                result["weaviate_stored"] = False

        # Step 2: Emit as stigmergy receipt
        stigmergy = self._get_stigmergy()

        receipt = {
            "phase": "verify",
            "intent": {
                "action": f"elysia.query.{colony}",
                "app": "elysia",
                "params": {"model": model},
            },
            "actor": f"colony:{colony}",
            "verifier": {
                "status": "verified" if success else "failed",
            },
            "workspace_hash": "elysia",
            "duration_ms": 0,  # Unknown at feedback time
            "timestamp": timestamp,
            "metadata": {
                "query_preview": query[:100],
                "response_preview": response[:100],
                "rating": rating,
                "model": model,
            },
        }

        # Add semantic pointer if available
        if semantic_pointer:
            receipt["semantic_pointer"] = semantic_pointer

        # Add to receipt cache
        stigmergy.receipt_cache.append(receipt)

        # Extract patterns (ACO update)
        patterns_updated = stigmergy.extract_patterns()
        result["patterns_updated"] = patterns_updated

        # Step 3: Update cooperation metric
        cooperation = self._get_cooperation()

        # Observed cooperation based on colony success rate
        colony_pattern = stigmergy.patterns.get((f"elysia.query.{colony}", "elysia"))
        if colony_pattern:
            observed_cooperation = colony_pattern.bayesian_success_rate
        else:
            observed_cooperation = 0.5

        cooperation.update(observed_cooperation)
        result["f_star"] = cooperation.f_star
        result["cooperation_level"] = cooperation.cooperation_level

        # Step 4: Check for bifurcation (phase transition)
        if cooperation.detect_bifurcation():
            logger.warning(
                f"🌊 Bifurcation detected: f*={cooperation.f_star:.3f}, "
                f"cooperation={cooperation.cooperation_level:.3f}"
            )
            result["bifurcation"] = True

        logger.info(
            f"📝 Feedback recorded: rating={rating}, colony={colony}, "
            f"patterns={patterns_updated}, f*={cooperation.f_star:.3f}"
        )

        return result

    async def get_fewshot_examples(
        self,
        query: str,
        max_examples: int = 3,
        min_rating: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get similar positive feedback for few-shot prompting.

        Args:
            query: Current query to find examples for
            max_examples: Maximum examples to return
            min_rating: Minimum rating (defaults to min_positive_rating)

        Returns:
            List of similar positive feedback examples
        """
        min_rating = min_rating or self.min_positive_rating

        if not self.weaviate:
            return []

        try:
            examples = await self.weaviate.get_similar_feedback(
                query=query,
                min_rating=min_rating,
                limit=max_examples,
            )
            return list(examples)

        except Exception as e:
            logger.warning(f"Failed to get few-shot examples: {e}")
            return []

    def predict_success(
        self,
        action: str,
        colony: str,
        semantic_context: list[float] | None = None,
    ) -> float:
        """Predict success probability using stigmergy patterns.

        Uses ACO probability: p ∝ τ^α × η^β

        Args:
            action: Action name (e.g., "elysia.query.grove")
            colony: Colony name
            semantic_context: Optional semantic pointer

        Returns:
            Success probability [0-1]
        """
        stigmergy = self._get_stigmergy()

        result: float = stigmergy.predict_success_probability(
            action=action,
            domain="elysia",
            semantic_context=semantic_context,
            use_thompson=False,  # Deterministic
        )
        return result

    def select_model_thompson(
        self,
        available_models: list[str],
        colony: str,
    ) -> str:
        """Select model using Thompson Sampling.

        Uses stigmergy patterns to balance exploration/exploitation
        when selecting which model to use.

        Args:
            available_models: List of model names
            colony: Colony name for context

        Returns:
            Selected model name
        """
        stigmergy = self._get_stigmergy()

        # Create (action, domain) tuples for each model
        candidates = [(f"elysia.query.{colony}.{model}", "elysia") for model in available_models]

        # Thompson sampling
        selected = stigmergy.select_action_thompson(
            actions=candidates,
            semantic_context=None,
        )

        # Extract model name from selected action
        action_str: str = selected[0]
        model = action_str.split(".")[-1]
        return model

    def get_cooperation_status(self) -> dict[str, Any]:
        """Get current superorganism cooperation status.

        Returns:
            Dict with cooperation metrics
        """
        cooperation = self._get_cooperation()

        result: dict[str, Any] = {
            "f_star": cooperation.f_star,
            "cooperation_level": cooperation.cooperation_level,
            "within_group_relatedness": cooperation.within_group_relatedness,
            "between_group_relatedness": cooperation.between_group_relatedness,
            "bifurcation_detected": cooperation.detect_bifurcation(),
            "history_length": len(cooperation.cooperation_history),
        }
        return result

    def get_stigmergy_summary(self) -> dict[str, Any]:
        """Get stigmergy pattern summary.

        Returns:
            Dict with pattern statistics
        """
        stigmergy = self._get_stigmergy()
        summary: dict[str, Any] = stigmergy.get_pattern_summary()
        return summary


__all__ = ["ElysiaFeedbackBridge", "FeedbackRecord"]
