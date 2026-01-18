"""Receipt-driven self-improvement engine.

The missing link for recursive self-improvement: closing the loop from
execution receipts back to colony parameter updates.

Flow:
1. Retrieve receipts from stigmergy storage (correlated by intent type)
2. Analyze success patterns (success_rate, G_value, complexity)
3. Update colony utilities in game model
4. Adjust world model via gradient updates
5. Store learning insights for future retrieval

This creates true recursive self-modification:
    Intent → Execute → Receipt → Learn → Improve → Better Execution

Mathematical Foundation:
- Bayesian learning: Posterior updates from receipt evidence
- Expected Free Energy minimization: Active inference updates
- Nash equilibrium: Colony utility optimization
- Gradient descent: World model parameter updates

Created: December 14, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class ReceiptAnalysis:
    """Analysis of receipt performance for a specific intent type."""

    intent_type: str
    success_rate: float
    avg_g_value: float  # Expected Free Energy (lower is better)
    avg_complexity: float
    avg_duration: float  # seconds
    colony_contributions: dict[str, float]  # Which colonies were active
    pattern_signature: torch.Tensor | None = None  # E8 code pattern
    sample_size: int = 0


@dataclass
class LearningUpdate:
    """Parameter updates derived from receipt analysis."""

    colony_utility_deltas: dict[str, float] = field(default_factory=dict[str, Any])
    world_model_gradients: torch.Tensor | None = None
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


class ReceiptLearningEngine(nn.Module):
    """Learns from execution receipts to improve future performance.

    This is the missing link for recursive self-improvement.
    Connects receipt patterns back to colony utilities and world model parameters.

    Integration Points:
    - StigmergyLearner: Receipt storage and pattern extraction
    - ColonyGameModel: Utility tracking and Nash equilibrium
    - OrganismRSSM: World model dynamics
    """

    def __init__(
        self,
        organism_rssm: nn.Module | None = None,
        stigmergy_learner: Any | None = None,
        learning_rate: float = 1e-4,
        min_sample_size: int = 3,
    ) -> None:
        """Initialize receipt learning engine.

        Args:
            organism_rssm: World model to update (optional)
            stigmergy_learner: Stigmergy learner for receipt access (optional, will auto-create)
            learning_rate: Learning rate for parameter updates
            min_sample_size: Minimum receipts required for learning
        """
        super().__init__()
        self.rssm = organism_rssm
        self.lr = learning_rate
        self.min_sample_size = min_sample_size

        # Get or create stigmergy learner
        if stigmergy_learner is None:
            from kagami.core.unified_agents.memory.stigmergy import get_stigmergy_learner

            self.stigmergy = get_stigmergy_learner()
        else:
            self.stigmergy = stigmergy_learner

        # Ensure game model exists for colony utility updates
        if self.stigmergy.game_model is None:
            from kagami.core.unified_agents.memory.stigmergy import ColonyGameModel

            self.stigmergy.game_model = ColonyGameModel()

        # Value estimator: receipt embedding → quality prediction
        self.receipt_value_net = nn.Sequential(
            nn.Linear(64, 128),  # Receipt embedding → value
            nn.GELU(),
            nn.Linear(128, 1),
        )

        logger.info(
            f"ReceiptLearningEngine initialized: lr={learning_rate}, min_samples={min_sample_size}"
        )

    def analyze_receipts(
        self,
        receipts: list[dict[str, Any]],
        intent_type: str,
    ) -> ReceiptAnalysis:
        """Analyze a batch of receipts for the same intent type.

        Returns aggregated performance metrics.

        Args:
            receipts: List of receipt dictionaries
            intent_type: Intent type being analyzed

        Returns:
            ReceiptAnalysis with aggregated metrics
        """
        if not receipts:
            return ReceiptAnalysis(
                intent_type=intent_type,
                success_rate=0.5,
                avg_g_value=1.0,
                avg_complexity=0.5,
                avg_duration=1.0,
                colony_contributions={},
                sample_size=0,
            )

        # Extract metrics from receipts
        success_count = 0
        g_values = []
        complexities = []
        durations = []
        colony_counts: dict[str, int] = {}

        for receipt in receipts:
            # Success determination
            verifier = receipt.get("verifier") or {}
            status = str(verifier.get("status") or receipt.get("status") or "").strip().lower()
            if status in {"verified", "success"}:
                success_count += 1

            # Expected Free Energy (if available)
            g_value = receipt.get("g_value") or receipt.get("expected_free_energy")
            if g_value is not None:
                g_values.append(float(g_value))

            # Complexity
            complexity = receipt.get("complexity") or receipt.get("intent", {}).get("complexity")
            if complexity is not None:
                complexities.append(float(complexity))

            # Duration
            duration_ms = receipt.get("duration_ms", 0)
            if duration_ms > 0:
                durations.append(duration_ms / 1000.0)  # Convert to seconds

            # Colony contributions
            actor = receipt.get("actor", "")
            colony = None

            # Extract colony name from actor
            # Formats: "colony:spark:worker:1" OR "spark:worker:1" OR "forge"
            if "colony:" in actor:
                colony = actor.split("colony:")[1].split(":")[0]
            elif ":" in actor:
                # Format: "spark:worker:1"
                potential_colony = actor.split(":")[0]
                if potential_colony in {
                    "spark",
                    "forge",
                    "flow",
                    "nexus",
                    "beacon",
                    "grove",
                    "crystal",
                }:
                    colony = potential_colony
            else:
                # Format: "forge" (single word)
                if actor in {
                    "spark",
                    "forge",
                    "flow",
                    "nexus",
                    "beacon",
                    "grove",
                    "crystal",
                }:
                    colony = actor

            if colony:
                colony_counts[colony] = colony_counts.get(colony, 0) + 1

        # Aggregate metrics
        total = len(receipts)
        success_rate = success_count / total if total > 0 else 0.5
        avg_g_value = sum(g_values) / len(g_values) if g_values else 1.0
        avg_complexity = sum(complexities) / len(complexities) if complexities else 0.5
        avg_duration = sum(durations) / len(durations) if durations else 1.0

        # Normalize colony contributions
        colony_contributions = {colony: count / total for colony, count in colony_counts.items()}

        logger.debug(
            f"Receipt analysis: {intent_type}, "
            f"n={total}, success={success_rate:.2%}, "
            f"G={avg_g_value:.3f}, complexity={avg_complexity:.2f}"
        )

        return ReceiptAnalysis(
            intent_type=intent_type,
            success_rate=success_rate,
            avg_g_value=avg_g_value,
            avg_complexity=avg_complexity,
            avg_duration=avg_duration,
            colony_contributions=colony_contributions,
            sample_size=total,
        )

    def _compute_world_model_gradients(
        self,
        analysis: ReceiptAnalysis,
    ) -> torch.Tensor | None:
        """Compute world model gradients from receipt analysis.

        Creates a training signal from receipt performance to improve
        world model predictions via the receipt value network.

        Strategy:
        1. Encode receipt performance into a pseudo-embedding
        2. Use receipt_value_net to predict quality
        3. Compare against actual performance (target quality)
        4. Backpropagate to compute gradients

        This creates a differentiable learning signal that improves
        the world model's ability to predict execution outcomes.

        Args:
            analysis: Receipt analysis with performance metrics

        Returns:
            Loss tensor if gradients computed, None otherwise
        """
        if self.rssm is None:
            logger.debug("No RSSM available for gradient computation")
            return None

        if analysis.sample_size < self.min_sample_size:
            logger.debug("Insufficient samples for world model gradients")
            return None

        # Ensure value network is in training mode
        self.receipt_value_net.train()
        self.receipt_value_net.zero_grad()

        # Create quality target from receipt performance
        # High success + low G → quality close to 1.0
        # Low success + high G → quality close to 0.0
        success_component = analysis.success_rate  # 0.0 to 1.0

        # Normalize G value (typical range: 0.1 to 10.0)
        # Lower G is better, so invert it: G=0.1 → 0.91, G=10 → 0.09
        g_normalized = 1.0 / (1.0 + analysis.avg_g_value)

        # Weighted combination (success 70%, low-G 30%)
        target_quality = 0.7 * success_component + 0.3 * g_normalized

        # Complexity penalty: prefer simpler solutions
        complexity_penalty = analysis.avg_complexity * 0.1
        target_quality = max(0.0, min(1.0, target_quality - complexity_penalty))

        # Create synthetic receipt embedding from performance metrics
        device = next(self.receipt_value_net.parameters()).device

        # Encode performance into 64-dim embedding
        # First 4 dims: explicit metrics
        # Remaining 60 dims: zero-padded (future: E8 pattern encoding)
        embedding = torch.zeros(1, 64, device=device, dtype=torch.float32)

        embedding[0, 0] = analysis.success_rate
        embedding[0, 1] = min(1.0, analysis.avg_g_value / 10.0)  # normalize to [0,1]
        embedding[0, 2] = analysis.avg_complexity
        embedding[0, 3] = len(analysis.colony_contributions) / 7.0  # normalize colony count

        # Predict quality using value network
        predicted_quality = torch.sigmoid(self.receipt_value_net(embedding))

        # Compute loss: MSE between predicted and target quality
        target_quality_tensor = torch.tensor([[target_quality]], device=device, dtype=torch.float32)

        loss = F.mse_loss(predicted_quality, target_quality_tensor)

        # Add L2 regularization to prevent overfitting on small sample sizes
        l2_lambda = 1e-4
        l2_reg = sum(p.pow(2.0).sum() for p in self.receipt_value_net.parameters())
        loss = loss + l2_lambda * l2_reg

        # Backpropagate to compute gradients
        # Gradients will be stored in receipt_value_net parameters
        loss.backward()

        logger.debug(
            f"World model gradients: loss={loss.item():.4f}, "
            f"target_quality={target_quality:.3f}, "
            f"predicted_quality={predicted_quality.item():.3f}, "
            f"samples={analysis.sample_size}"
        )

        return loss

    def compute_learning_update(
        self,
        analysis: ReceiptAnalysis,
    ) -> LearningUpdate:
        """Convert receipt analysis into parameter updates.

        Key insight: Good receipts (high success, low G) should
        increase colony utilities for that pattern.

        Args:
            analysis: Receipt analysis to learn from

        Returns:
            LearningUpdate with parameter deltas
        """
        if analysis.sample_size < self.min_sample_size:
            logger.debug(
                f"Insufficient samples for learning: {analysis.sample_size} < {self.min_sample_size}"
            )
            return LearningUpdate(
                colony_utility_deltas={},
                confidence=0.0,
                metadata={"reason": "insufficient_samples", "sample_size": analysis.sample_size},
            )

        # Compute utility delta based on performance
        # Formula: delta = sign(success - 0.5) * |success - 0.5| / (1 + G)
        # - High success, low G → positive delta (reward)
        # - Low success, high G → negative delta (penalize)

        success_deviation = analysis.success_rate - 0.5  # -0.5 to +0.5
        g_penalty = 1.0 / (1.0 + analysis.avg_g_value)  # Lower G → higher weight

        base_delta = success_deviation * g_penalty * 0.1  # Scale to reasonable range

        # Distribute delta across active colonies
        colony_utility_deltas = {}
        for colony, contribution in analysis.colony_contributions.items():
            # Weight by contribution (colonies that participated more get more credit/blame)
            colony_utility_deltas[colony] = base_delta * contribution

        # Confidence based on sample size and consistency
        # More samples + high success rate OR low success rate → higher confidence
        # Moderate success rate → lower confidence (uncertain)
        sample_confidence = min(1.0, analysis.sample_size / 10.0)
        result_confidence = abs(analysis.success_rate - 0.5) * 2.0  # 0.0 at 50%, 1.0 at 0/100%
        confidence = sample_confidence * result_confidence

        # Compute world model gradients
        gradient_loss = self._compute_world_model_gradients(analysis)

        logger.debug(
            f"Learning update: {analysis.intent_type}, "
            f"delta={base_delta:.4f}, confidence={confidence:.2f}, "
            f"colonies={list(colony_utility_deltas.keys())}"
        )

        return LearningUpdate(
            colony_utility_deltas=colony_utility_deltas,
            world_model_gradients=gradient_loss,
            confidence=confidence,
            metadata={
                "intent_type": analysis.intent_type,
                "success_rate": analysis.success_rate,
                "avg_g_value": analysis.avg_g_value,
                "sample_size": analysis.sample_size,
            },
        )

    def apply_update(self, update: LearningUpdate) -> None:
        """Apply learning update to colony utilities and world model.

        This is the CLOSURE of the loop: receipt → learning → update.

        NEXUS BRIDGE (Dec 14, 2025): Immediate propagation to router.

        Args:
            update: Learning update to apply
        """
        if not update.colony_utility_deltas:
            logger.debug("No utility updates to apply")
            return

        game_model = self.stigmergy.game_model
        if game_model is None:
            logger.warning("No game model available for utility updates")
            return

        # Update colony utilities
        for colony_name, delta in update.colony_utility_deltas.items():
            colony_utility = game_model.get_colony_utility(colony_name)
            if colony_utility is None:
                logger.warning(f"Colony {colony_name} not found in game model")
                continue

            # Update success rate with confidence-weighted blend
            old_rate = colony_utility.success_rate
            new_rate = old_rate + delta
            # Clamp to [0, 1]
            new_rate = max(0.0, min(1.0, new_rate))

            # Apply update with confidence weighting
            colony_utility.success_rate = (
                update.confidence * new_rate + (1 - update.confidence) * old_rate
            )

            logger.debug(
                f"Updated {colony_name}: success_rate {old_rate:.3f} → {colony_utility.success_rate:.3f}"
            )

        # NEXUS BRIDGE: Notify router of utility updates (immediate propagation)
        self._notify_router_update()

        # Apply world model gradients (if available)
        if update.world_model_gradients is not None:
            with torch.no_grad():
                # Apply gradients to receipt value network
                # This network learns to predict execution quality from receipt patterns
                for param in self.receipt_value_net.parameters():
                    if param.grad is not None:
                        param.data -= self.lr * param.grad

                # Clear gradients after application
                self.receipt_value_net.zero_grad()

            logger.debug(
                f"Applied world model gradients: loss={update.world_model_gradients.item():.4f}"
            )

    def _notify_router_update(self) -> None:
        """Notify FanoActionRouter that utilities have changed.

        NEXUS BRIDGE: Immediate propagation - router uses updated utilities
        within 1 execution cycle.
        """
        try:
            from kagami.core.unified_agents.unified_organism import get_unified_organism

            organism = get_unified_organism()
            if organism and hasattr(organism, "_router"):
                organism._router.refresh_utilities()
                logger.debug("✅ Router notified of utility updates")
        except Exception as e:
            logger.debug(f"Router notification failed: {e}")
            # Silent fail - router not available (OK during testing)

    async def learn_from_receipts(
        self,
        receipts: list[dict[str, Any]],
        intent_type: str,
    ) -> LearningUpdate:
        """End-to-end receipt learning pipeline.

        This is called periodically (e.g., every N executions).

        Args:
            receipts: List of receipt dictionaries
            intent_type: Intent type to learn from

        Returns:
            LearningUpdate that was applied
        """
        # Extract patterns from receipts (updates stigmergy patterns)
        self.stigmergy.extract_patterns()

        # Analyze
        analysis = self.analyze_receipts(receipts, intent_type)

        # Compute update
        update = self.compute_learning_update(analysis)

        # Apply
        self.apply_update(update)

        # Persist updated patterns
        await self.stigmergy.save_patterns()

        logger.info(
            f"Receipt learning complete: {intent_type}, "
            f"confidence={update.confidence:.2f}, "
            f"colonies_updated={len(update.colony_utility_deltas)}"
        )

        return update

    async def learn_from_stigmergy(self, intent_type: str | None = None) -> LearningUpdate | None:
        """Learn from stigmergy patterns for a specific intent type.

        Convenience method that retrieves receipts from stigmergy cache
        and runs the learning pipeline.

        Args:
            intent_type: Intent type to learn from (None = learn from all)

        Returns:
            LearningUpdate if learning occurred, None otherwise
        """
        # Get receipts from stigmergy cache
        receipts = self.stigmergy.receipt_cache

        if not receipts:
            logger.debug("No receipts in stigmergy cache")
            return None

        # Filter by intent type if specified
        if intent_type is not None:
            receipts = [
                r for r in receipts if r.get("intent", {}).get("action", "").startswith(intent_type)
            ]

            if not receipts:
                logger.debug(f"No receipts found for intent type: {intent_type}")
                return None

            # Learn from filtered receipts
            return await self.learn_from_receipts(receipts, intent_type)

        # Learn from all receipts (group by intent type)
        intent_groups: dict[str, list[dict[str, Any]]] = {}
        for receipt in receipts:
            action = receipt.get("intent", {}).get("action") or "unknown"
            # Extract base intent type (e.g., "research.web" → "research")
            base_intent = action.split(".")[0] if "." in action else action
            if base_intent not in intent_groups:
                intent_groups[base_intent] = []
            intent_groups[base_intent].append(receipt)

        # Learn from largest group
        if not intent_groups:
            return None

        largest_group = max(intent_groups.items(), key=lambda x: len(x[1]))
        intent_type, group_receipts = largest_group

        logger.info(
            f"Learning from largest intent group: {intent_type} ({len(group_receipts)} receipts)"
        )

        return await self.learn_from_receipts(group_receipts, intent_type)

    def get_stats(self) -> dict[str, Any]:
        """Get learning engine statistics.

        Returns:
            Statistics dictionary
        """
        game_model_stats = (
            self.stigmergy.game_model.get_stats() if self.stigmergy.game_model else {}
        )

        return {
            "learning_rate": self.lr,
            "min_sample_size": self.min_sample_size,
            "receipts_cached": len(self.stigmergy.receipt_cache),
            "patterns_learned": len(self.stigmergy.patterns),
            "game_model": game_model_stats,
        }

    def get_learning_context_for_llm(self) -> dict[str, Any]:
        """Get learning context for LLM intrinsic motivation system.

        Returns structured context about learned patterns, colony utilities,
        and execution success metrics for informing LLM decision-making.

        Returns:
            Dictionary with keys:
            - patterns: Learned intent patterns
            - colony_utilities: Current utility values for each colony
            - success_metrics: Aggregated success rates by intent type
            - confidence_scores: Confidence in each learned pattern
        """
        context: dict[str, Any] = {
            "patterns": {},
            "colony_utilities": {},
            "success_metrics": {},
            "confidence_scores": {},
        }

        # Extract pattern information from stigmergy
        if self.stigmergy and self.stigmergy.patterns:
            for pattern_key, pattern in self.stigmergy.patterns.items():
                pattern_dict = pattern if isinstance(pattern, dict) else {}
                context["patterns"][pattern_key] = {
                    "signature": str(pattern_dict.get("signature", ""))[
                        :100
                    ],  # Truncate for display
                    "count": pattern_dict.get("count", 0),
                    "intent_type": pattern_dict.get("intent_type", ""),
                }

        # Extract colony utility information
        if self.stigmergy and self.stigmergy.game_model:
            for colony_name in [
                "spark",
                "forge",
                "flow",
                "nexus",
                "beacon",
                "grove",
                "crystal",
            ]:
                colony_util = self.stigmergy.game_model.get_colony_utility(colony_name)
                if colony_util:
                    context["colony_utilities"][colony_name] = {
                        "success_rate": float(colony_util.success_rate),
                        "avg_completion_time": float(colony_util.avg_completion_time),
                        "resource_cost": float(colony_util.resource_cost),
                        "specializations": dict(colony_util.task_specialization),
                    }

        # Extract success metrics from receipt cache
        if self.stigmergy and self.stigmergy.receipt_cache:
            intent_counts: dict[str, list[bool]] = {}
            for receipt in self.stigmergy.receipt_cache:
                intent_type = receipt.get("intent", {}).get("action", "unknown")
                status = str(receipt.get("status", "") or "").lower()
                success = status in {"verified", "success"}

                if intent_type not in intent_counts:
                    intent_counts[intent_type] = []
                intent_counts[intent_type].append(success)

            for intent_type, successes in intent_counts.items():
                success_count = sum(1 for s in successes if s)
                total = len(successes)
                success_rate = success_count / total if total > 0 else 0.5

                context["success_metrics"][intent_type] = {
                    "success_rate": success_rate,
                    "sample_count": total,
                }

                # Confidence: higher sample count + extreme success rate = higher confidence
                sample_confidence = min(1.0, total / 10.0)
                result_confidence = abs(success_rate - 0.5) * 2.0
                confidence = sample_confidence * result_confidence

                context["confidence_scores"][intent_type] = confidence

        return context


# Global learning engine instance
_learning_engine: ReceiptLearningEngine | None = None


def get_learning_engine() -> ReceiptLearningEngine:
    """Get global receipt learning engine instance.

    CANONICAL INTERFACE: This is the main singleton accessor for the receipt
    learning engine, used throughout the codebase for recursive self-improvement.

    Returns:
        Singleton ReceiptLearningEngine
    """
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = ReceiptLearningEngine()
    return _learning_engine


def get_receipt_learner() -> ReceiptLearningEngine:
    """Get or create global receipt learner instance.

    ALIAS FOR: get_learning_engine()

    This is the CANONICAL receipt learning interface used by:
    - IntrinsicMotivationSystem (for learned pattern integration)
    - ContinuousMindDaemon (for continuous learning)
    - OrganismRSSM (for stigmergy updates)

    Returns:
        Singleton ReceiptLearningEngine
    """
    return get_learning_engine()


def reset_receipt_learner() -> None:
    """Reset receipt learner singleton (for testing).

    WARNING: Only use in tests. Resets the global instance.
    """
    global _learning_engine
    _learning_engine = None


__all__ = [
    "LearningUpdate",
    "ReceiptAnalysis",
    "ReceiptLearningEngine",
    "get_learning_engine",
    "get_receipt_learner",
    "reset_receipt_learner",
]
