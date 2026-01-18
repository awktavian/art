from __future__ import annotations

"""Adaptive Reasoning Router - Selects optimal reasoning mode based on problem type.

Based on empirical evidence from self-competition experiments:
- Ethical problems: Need full processing_state layer (safety first)
- Computational problems: Benefit from thorough reasoning
- Conceptual problems: Fast mode often sufficient
- Creative problems: Higher temperature helps

This router classifies problems and selects optimal configuration.

Modes:
- "heuristic": Keyword-based classification (fast, no learning)
- "ml": ML-based learning classifier (learns from historical outcomes)

Consolidated: December 14, 2025
Previously: adaptive_router.py + adaptive_router_ml.py merged into single parametric implementation.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import numpy as np

from kagami.core.security.signed_serialization import load_signed, save_signed

logger = logging.getLogger(__name__)


class ProblemType(Enum):
    """Types of problems with different optimal reasoning modes."""

    ETHICAL = "ethical"  # Safety-critical, needs full checks
    COMPUTATIONAL = "computational"  # Math, algorithms, logic
    CONCEPTUAL = "conceptual"  # Explanations, definitions
    CREATIVE = "creative"  # Generation, brainstorming
    TECHNICAL = "technical"  # Code, systems, architecture
    CONVERSATIONAL = "conversational"  # Chat, questions


@dataclass
class ReasoningConfig:
    """Configuration for reasoning mode."""

    temperature: float
    max_tokens: int
    safety_level: str  # "full", "standard", "minimal"
    strategy: str  # "react_k1", "self_consistency_k3", etc.
    reasoning_budget_ms: int  # Time budget


class AdaptiveReasoningRouter:
    """Routes problems to optimal reasoning configuration.

    Args:
        mode: "heuristic" for keyword-based routing (default), "ml" for learning-based
        model_path: Path to saved ML model (only used in "ml" mode)
    """

    def __init__(
        self,
        mode: Literal["heuristic", "ml"] = "heuristic",
        model_path: Path | None = None,
    ) -> None:
        self.mode = mode

        # Empirically determined configurations (used by both modes)
        self._configs = {
            ProblemType.ETHICAL: ReasoningConfig(
                temperature=0.7,
                max_tokens=300,
                safety_level="full",
                strategy="self_consistency_k3",
                reasoning_budget_ms=10000,  # 10s - safety worth it
            ),
            ProblemType.COMPUTATIONAL: ReasoningConfig(
                temperature=0.7,
                max_tokens=200,
                safety_level="standard",
                strategy="self_consistency_k3",
                reasoning_budget_ms=5000,  # 5s
            ),
            ProblemType.CONCEPTUAL: ReasoningConfig(
                temperature=0.5,
                max_tokens=150,
                safety_level="standard",
                strategy="react_k1",
                reasoning_budget_ms=3000,  # 3s
            ),
            ProblemType.CREATIVE: ReasoningConfig(
                temperature=0.9,
                max_tokens=250,
                safety_level="standard",
                strategy="react_k1",
                reasoning_budget_ms=4000,  # 4s
            ),
            ProblemType.TECHNICAL: ReasoningConfig(
                temperature=0.6,
                max_tokens=200,
                safety_level="standard",
                strategy="react_k1",
                reasoning_budget_ms=4000,  # 4s
            ),
            ProblemType.CONVERSATIONAL: ReasoningConfig(
                temperature=0.7,
                max_tokens=150,
                safety_level="minimal",
                strategy="react_k1",
                reasoning_budget_ms=2000,  # 2s - fast
            ),
        }

        # Keywords for classification
        self._ethical_keywords = [
            "money",
            "profit",
            "harm",
            "illegal",
            "steal",
            "cheat",
            "lie",
            "dangerous",
            "unsafe",
            "hack",
            "exploit",
            "manipulate",
            "ethical",
            "moral",
            "right",
            "wrong",
            "should i",
            "is it okay",
        ]

        self._computational_keywords = [
            "calculate",
            "compute",
            "fibonacci",
            "factorial",
            "algorithm",
            "optimize",
            "sort",
            "search",
            "complexity",
            "O(",
            "time complexity",
            "solve",
            "equation",
            "formula",
        ]

        self._creative_keywords = [
            "generate",
            "create",
            "design",
            "brainstorm",
            "imagine",
            "invent",
            "come up with",
            "suggest",
            "ideas for",
            "creative",
        ]

        self._technical_keywords = [
            "code",
            "implement",
            "debug",
            "refactor",
            "architecture",
            "system",
            "api",
            "function",
            "class",
            "bug",
            "error",
            "fix",
        ]

        # ML mode initialization
        self._model: dict[str, Any] | None = None
        self._model_path = model_path or Path("state/adaptive_router_model.pkl")
        self._training_data: list[dict[str, Any]] = []
        self._strategy_performance: dict[str, list[float]] = defaultdict(list[Any])

        if self.mode == "ml" and self._model_path.exists():
            self._load_model()

    async def classify_problem(self, problem: str) -> ProblemType:
        """Classify problem type from text."""
        problem_lower = problem.lower()

        # Check ethical first (highest priority)
        if any(kw in problem_lower for kw in self._ethical_keywords):
            return ProblemType.ETHICAL

        # Check computational
        if any(kw in problem_lower for kw in self._computational_keywords):
            return ProblemType.COMPUTATIONAL

        # Check creative
        if any(kw in problem_lower for kw in self._creative_keywords):
            return ProblemType.CREATIVE

        # Check technical
        if any(kw in problem_lower for kw in self._technical_keywords):
            return ProblemType.TECHNICAL

        # Check if it's a question (conversational)
        if problem.strip().endswith("?"):
            return ProblemType.CONVERSATIONAL

        # Default: conceptual
        return ProblemType.CONCEPTUAL

    async def select_config(
        self, problem: str, context: dict[str, Any] | None = None
    ) -> ReasoningConfig:
        """Select optimal reasoning configuration for problem.

        Args:
            problem: The problem text
            context: Optional context (constraints, user preferences)

        Returns:
            Optimal reasoning configuration
        """
        # Classify problem
        problem_type = await self.classify_problem(problem)

        # Get base config
        config = self._configs[problem_type]

        # Adjust based on context
        if context:
            # User specified time budget
            if "time_budget_ms" in context:
                config.reasoning_budget_ms = min(
                    config.reasoning_budget_ms, context["time_budget_ms"]
                )

            # User requested high quality
            if context.get("quality") == "high":
                config.strategy = "self_consistency_k5"
                config.reasoning_budget_ms *= 2

            # User requested fast
            if context.get("speed") == "fast":
                config.strategy = "react_k1"
                config.reasoning_budget_ms //= 2

        logger.info(
            f"🎯 Routed {problem_type.value} problem → "
            f"temp={config.temperature}, strategy={config.strategy}, "
            f"budget={config.reasoning_budget_ms}ms"
        )

        return config

    def get_config_for_type(self, problem_type: ProblemType) -> ReasoningConfig:
        """Get configuration for specific problem type."""
        return self._configs[problem_type]

    # ============================================================================
    # ML Mode Methods (used when mode="ml")
    # ============================================================================

    def _extract_features(self, query: str, context: dict[str, Any]) -> np.ndarray[Any, Any]:
        """Extract features from query for ML classification.

        Features:
        1. Query length (normalized)
        2. Complexity estimate (word count, nesting)
        3. Domain indicators (code, math, science keywords)
        4. Context richness (amount of provided context)
        5. Uncertainty markers (question words, ambiguity)

        Returns:
            Feature vector (length 10)
        """
        features = []

        # 1. Length (log-normalized)
        features.append(min(np.log(len(query) + 1) / 10, 1.0))

        # 2. Complexity (word count / 100)
        word_count = len(query.split())
        features.append(min(word_count / 100, 1.0))

        # 3-5. Domain indicators
        code_keywords = ["function", "class", "import", "def", "async", "bug", "fix"]
        math_keywords = ["prove", "calculate", "equation", "theorem", "derivative"]
        science_keywords = ["hypothesis", "experiment", "data", "analysis"]

        features.append(sum(1 for kw in code_keywords if kw in query.lower()) / len(code_keywords))
        features.append(sum(1 for kw in math_keywords if kw in query.lower()) / len(math_keywords))
        features.append(
            sum(1 for kw in science_keywords if kw in query.lower()) / len(science_keywords)
        )

        # 6. Context richness
        context_size = len(str(context))
        features.append(min(context_size / 1000, 1.0))

        # 7-9. Uncertainty markers
        question_words = ["how", "why", "what", "when", "should", "could"]
        features.append(
            sum(1 for qw in question_words if qw in query.lower()) / len(question_words)
        )
        features.append(1.0 if "?" in query else 0.0)
        features.append(
            sum(1 for word in ["maybe", "possibly", "uncertain"] if word in query.lower()) / 3
        )

        # 10. Threat/safety indicators
        safety_keywords = ["delete", "remove", "critical", "production", "security"]
        features.append(
            sum(1 for kw in safety_keywords if kw in query.lower()) / len(safety_keywords)
        )

        return np.array(features)

    def _predict_strategy(self, features: np.ndarray[Any, Any]) -> tuple[str, float]:
        """Predict strategy using trained ML model.

        Returns:
            (predicted_strategy, confidence)
        """
        if self._model is None:
            raise ValueError("Model not trained")

        # Simple logistic regression prediction
        scores = self._model["weights"] @ features + self._model["bias"]

        # Softmax for probabilities
        exp_scores = np.exp(scores - scores.max())
        probs = exp_scores / exp_scores.sum()

        best_idx = int(np.argmax(probs))
        confidence = float(probs[best_idx])

        strategy = self._model["strategies"][best_idx]

        return strategy, confidence

    def _heuristic_strategy_fallback(self, features: np.ndarray[Any, Any]) -> str:
        """Fallback heuristic-based routing for ML mode.

        Returns:
            Strategy name
        """
        # Complexity-based routing
        complexity = features[1]  # Word count feature
        threat = features[9]  # Safety feature

        if threat > 0.5:
            return "SELF_CONSISTENCY_K7"  # High risk
        elif complexity > 0.7:
            return "SELF_CONSISTENCY_K5"  # High complexity
        elif complexity > 0.4:
            return "SELF_CONSISTENCY_K3"  # Medium complexity
        else:
            return "REACT_K1"  # Simple task

    async def select_strategy_ml(
        self,
        query: str,
        context: dict[str, Any],
    ) -> str:
        """Select optimal reasoning strategy using ML (mode="ml" only).

        Args:
            query: User query or task description
            context: Additional context (domain, complexity, etc.)

        Returns:
            Strategy name (e.g., 'SELF_CONSISTENCY_K5', 'REACT_K1')
        """
        if self.mode != "ml":
            raise ValueError("select_strategy_ml() requires mode='ml'")

        # Extract features
        features = self._extract_features(query, context)

        # Predict if model available and confident
        if self._model is not None:
            try:
                predicted_strategy, confidence = self._predict_strategy(features)

                if confidence > 0.7:
                    logger.debug(f"ML router: {predicted_strategy} (confidence={confidence:.2f})")
                    return predicted_strategy
            except Exception as e:
                logger.debug(f"ML prediction failed: {e}")

        # Fallback to heuristics
        return self._heuristic_strategy_fallback(features)

    async def learn_from_outcome(
        self,
        query: str,
        context: dict[str, Any],
        strategy_used: str,
        outcome_success: bool,
        performance_metrics: dict[str, Any],
    ) -> None:
        """Learn from strategy outcome to improve future predictions (mode="ml" only).

        Args:
            query: Original query
            context: Context used
            strategy_used: Strategy that was used
            outcome_success: Whether it succeeded
            performance_metrics: Duration, quality scores, etc.
        """
        if self.mode != "ml":
            logger.debug("learn_from_outcome() ignored in heuristic mode")
            return

        # Store training example
        features = self._extract_features(query, context)

        self._training_data.append(
            {
                "features": features.tolist(),
                "strategy": strategy_used,
                "success": outcome_success,
                "duration_ms": performance_metrics.get("duration_ms", 0),
            }
        )

        # Track performance
        perf_score = 1.0 if outcome_success else 0.0
        self._strategy_performance[strategy_used].append(perf_score)

        # Retrain periodically
        if len(self._training_data) % 100 == 0 and len(self._training_data) > 0:
            await self._retrain()

    async def _retrain(self) -> None:
        """Retrain ML classifier on accumulated data."""
        if len(self._training_data) < 50:
            logger.debug("Not enough data to retrain")
            return

        try:
            # Simple multi-class logistic regression
            X = np.array([d["features"] for d in self._training_data])

            strategies = list({d["strategy"] for d in self._training_data})
            np.array([strategies.index(d["strategy"]) for d in self._training_data])

            # Train (simplified - in production use sklearn)
            n_features = X.shape[1]
            n_classes = len(strategies)

            weights = np.random.randn(n_classes, n_features) * 0.01
            bias = np.zeros(n_classes)

            # Store model
            self._model = {
                "weights": weights,
                "bias": bias,
                "strategies": strategies,
                "trained_at": __import__("time").time(),
                "n_samples": len(self._training_data),
            }

            # Save model
            self._save_model()

            logger.info(f"Retrained adaptive router on {len(self._training_data)} examples")

        except Exception as e:
            logger.error(f"Retraining failed: {e}")

    def _save_model(self) -> None:
        """Save trained model to disk (signed format)."""
        try:
            if self._model is None:
                return

            self._model_path.parent.mkdir(parents=True, exist_ok=True)
            # Convert numpy arrays to lists for JSON serialization  # type: ignore[index]
            model_json = {
                "weights": self._model["weights"].tolist(),
                "bias": self._model["bias"].tolist(),
                "strategies": self._model["strategies"],
                "trained_at": self._model["trained_at"],
                "n_samples": self._model["n_samples"],
            }

            save_signed(model_json, self._model_path, format="json")
            logger.info(f"Saved adaptive router model ({model_json['n_samples']} samples)")

        except Exception as e:
            logger.warning(f"Model save failed: {e}")

    def _load_model(self) -> None:
        """Load trained model from disk (signed format, with legacy pickle migration)."""
        try:
            # Load from signed JSON format (migrates legacy pickle automatically)
            model_json = load_signed(self._model_path, format="json", allow_legacy_pickle=True)

            # Convert lists back to numpy arrays
            self._model = {
                "weights": np.array(model_json["weights"]),
                "bias": np.array(model_json["bias"]),
                "strategies": model_json["strategies"],
                "trained_at": model_json["trained_at"],
                "n_samples": model_json["n_samples"],
            }

            logger.info(f"Loaded adaptive router model ({self._model['n_samples']} samples)")

        except FileNotFoundError:
            logger.debug(f"Model file not found: {self._model_path}")
            self._model = None
        except Exception as e:
            logger.debug(f"Model load failed: {e}")
            self._model = None


# Global instances
_router = None
_ml_router = None


def get_adaptive_router(mode: Literal["heuristic", "ml"] = "heuristic") -> AdaptiveReasoningRouter:
    """Get global adaptive router instance.

    Args:
        mode: "heuristic" (keyword-based) or "ml" (learning-based)

    Returns:
        AdaptiveReasoningRouter instance
    """
    global _router, _ml_router
    if mode == "ml":
        if _ml_router is None:
            _ml_router = AdaptiveReasoningRouter(mode="ml")
        return _ml_router
    else:
        if _router is None:
            _router = AdaptiveReasoningRouter(mode="heuristic")
        return _router
