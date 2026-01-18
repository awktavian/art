"""Unified memory types for K os.

Consolidates Experience and memory types across:
- learning_instinct.py
- distributed_replay.py
- continual_learning_enhanced.py
- prioritized_replay.py (both versions)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ============================================================================
# Canonical Experience Type
# ============================================================================


@dataclass
class Experience:
    """Universal experience/transition for learning.

    Used across:
    - Reinforcement learning
    - Continual learning
    - Replay buffers
    - Instinct learning
    """

    state: Any
    action: Any
    reward: float
    next_state: Any
    done: bool
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    priority: float = 1.0  # For prioritized replay
    embedding: Any = None  # Optional state embedding


@dataclass
class MemorySnapshot:
    """Snapshot of memory state for persistence."""

    experiences: list[Experience]
    metadata: dict[str, Any]
    timestamp: float
    total_count: int


@dataclass
class ReplayConfig:
    """Configuration for replay buffers."""

    capacity: int = 10000
    prioritized: bool = True
    alpha: float = 0.6  # Prioritization exponent
    beta: float = 0.4  # Importance sampling exponent
    beta_increment: float = 0.001  # Beta annealing
    min_priority: float = 1e-6


__all__ = [
    "Experience",
    "MemorySnapshot",
    "ReplayConfig",
]
