"""Strategy Optimizer - Meta-learning which reasoning strategies work best.

Tracks which ReasoningStrategy (REACT, SELF_CONSISTENCY, TOT, etc.) performs
best for different problem types, enabling the system to learn optimal strategy
selection over time.

This is meta-learning: learning which learning approach works best.
"""

import logging
import time
from collections import defaultdict
from typing import Any

from kagami.core.learning.meta.strategies import ReasoningStrategy

logger = logging.getLogger(__name__)


class StrategyOptimizer:
    """Learn which reasoning strategies work best for which problems.

    Tracks:
    - Problem type → Strategy used → Outcome quality
    - Builds statistical model of strategy effectiveness
    - Recommends optimal strategy for new problems

    This enables K os to learn from experience which reasoning
    approaches work best, improving decision quality over time.
    """

    def __init__(self) -> None:
        self._strategy_history: list[dict[str, Any]] = []
        self._strategy_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "total_quality": 0.0, "avg_quality": 0.0}
        )
        self._problem_type_cache: dict[str, str] = {}

    async def record_strategy_outcome(
        self,
        problem_type: str,
        strategy: ReasoningStrategy | str,
        outcome_quality: float,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record which strategy was used and how well it worked.

        Args:
            problem_type: Type of problem (optimization, planning, verification, etc.)
            strategy: Which ReasoningStrategy was used
            outcome_quality: 0.0-1.0 score of how well it worked
            context: Additional context for analysis
        """
        strategy_name = strategy.name if hasattr(strategy, "name") else str(strategy)
        record = {
            "problem_type": problem_type,
            "strategy": strategy_name,
            "quality": float(outcome_quality),
            "timestamp": time.time(),
            "features": self._extract_features(context or {}),
        }
        self._strategy_history.append(record)
        key = f"{problem_type}_{strategy_name}"
        stats = self._strategy_stats[key]
        stats["count"] += 1
        stats["total_quality"] += outcome_quality
        stats["avg_quality"] = stats["total_quality"] / stats["count"]
        if stats["count"] >= 5:
            logger.debug(
                f"📊 Strategy stats: {problem_type} + {strategy_name} = {stats['avg_quality']:.2f} avg quality ({stats['count']} samples)"
            )
        if len(self._strategy_history) > 10000:
            self._strategy_history = self._strategy_history[-10000:]

    async def recommend_strategy(
        self, problem_type: str, context: dict[str, Any] | None = None
    ) -> ReasoningStrategy:
        """Recommend best strategy based on past performance.

        Args:
            problem_type: Type of problem to solve
            context: Additional context for recommendation

        Returns:
            ReasoningStrategy most likely to succeed
        """
        candidates = []
        for key, stats in self._strategy_stats.items():
            if key.startswith(f"{problem_type}_") and stats["count"] >= 3:
                strategy_name = key.split("_", 1)[1]
                candidates.append((strategy_name, stats["avg_quality"], stats["count"]))
        if not candidates:
            logger.debug(f"No meta-learning data for {problem_type}, using default REACT_K1")
            return ReasoningStrategy.REACT_K1
        import math

        scored = [(name, quality * math.sqrt(count)) for name, quality, count in candidates]
        best_strategy_name = max(scored, key=lambda x: x[1])[0]
        try:
            recommended = ReasoningStrategy[best_strategy_name]
            logger.info(
                f"📈 Meta-learning recommends {recommended.name} for {problem_type} (avg quality: {self._strategy_stats[f'{problem_type}_{best_strategy_name}']['avg_quality']:.2f})"
            )
            return recommended
        except KeyError:
            logger.warning(f"Unknown strategy {best_strategy_name}, using default")
            return ReasoningStrategy.REACT_K1

    def get_strategy_statistics(self, min_samples: int = 3) -> dict[str, dict[str, Any]]:
        """Get strategy performance statistics.

        Returns:
            Dict of problem_strategy_key → performance stats
        """
        return {
            key: stats
            for key, stats in self._strategy_stats.items()
            if stats["count"] >= min_samples
        }

    def get_best_strategies_by_problem(self) -> dict[str, tuple[str, float]]:
        """Get best performing strategy for each problem type.

        Returns:
            Dict of problem_type → (best_strategy, avg_quality)
        """
        by_problem: dict[str, list[tuple[str, float]]] = defaultdict(list[Any])
        for key, stats in self._strategy_stats.items():
            if stats["count"] >= 3:
                problem_type, strategy_name = key.split("_", 1)
                by_problem[problem_type].append((strategy_name, stats["avg_quality"]))
        best_strategies = {}
        for problem_type, strategies in by_problem.items():
            best_strategy, best_quality = max(strategies, key=lambda x: x[1])
            best_strategies[problem_type] = (best_strategy, best_quality)
        return best_strategies

    def _extract_features(self, context: dict[str, Any]) -> dict[str, Any]:
        """Extract relevant features from context for analysis."""
        return {
            "complexity": len(str(context)),
            "has_code": "code" in str(context).lower(),
            "has_plan": "plan" in str(context).lower(),
            "has_math": any(
                word in str(context).lower() for word in ["math", "calculate", "prove"]
            ),
            "novelty": context.get("novelty", 0.5) if isinstance(context, dict) else 0.5,
        }


_strategy_optimizer: StrategyOptimizer | None = None


def get_strategy_optimizer() -> StrategyOptimizer:
    """Get or create the global strategy optimizer."""
    global _strategy_optimizer
    if _strategy_optimizer is None:
        _strategy_optimizer = StrategyOptimizer()
    return _strategy_optimizer


__all__ = ["StrategyOptimizer", "get_strategy_optimizer"]
