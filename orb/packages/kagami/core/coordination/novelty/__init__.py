"""Novelty generation and measurement systems.

This package provides:
- Conceptual distance metrics for true novelty measurement
- Divergent thinking engine for paradigm shifts
- Analogical transfer across distant domains

Consolidated into coordination module (December 2025).
"""

from kagami.core.coordination.novelty.analogical_transfer import (
    AnalogicalTransferEngine,
    Analogy,
)
from kagami.core.coordination.novelty.conceptual_distance import (
    ConceptualDistanceMetric,
    NoveltyScore,
    SimpleNoveltyMetric,
)

__all__ = [
    # Analogical transfer
    "AnalogicalTransferEngine",
    "Analogy",
    # Conceptual distance
    "ConceptualDistanceMetric",
    "NoveltyScore",
    "SimpleNoveltyMetric",
]
