"""K os Design Patterns

Core stigmergy pattern implementation for ant-colony optimization.
Used by the unified agents and receipts system.
"""

from .base_pattern import (
    BETA_PRIOR_ALPHA,
    BETA_PRIOR_BETA,
    DEFAULT_DECAY_RATE,
    DEFAULT_HEURISTIC_WEIGHT,
    DEFAULT_PHEROMONE_WEIGHT,
    DEFAULT_UCB_C,
    BasePattern,
)

__all__ = [
    "BETA_PRIOR_ALPHA",
    "BETA_PRIOR_BETA",
    "DEFAULT_DECAY_RATE",
    "DEFAULT_HEURISTIC_WEIGHT",
    "DEFAULT_PHEROMONE_WEIGHT",
    "DEFAULT_UCB_C",
    # Stigmergy pattern
    "BasePattern",
]
