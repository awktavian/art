"""Aperiodic Thought Generation System.

Fixes LZC crisis (0.076 → 0.85+) via:
- Novelty constraints (no repetition)
- 13 coherence rules (maintain quality)
- Adaptive temperature (PID control)

Inspired by Einstein "hat" aperiodic tiling (2023).

Usage:
    from kagami.core.aperiodic import apply_aperiodic_filter
    selected = apply_aperiodic_filter(["response1", "response2"], correlation_id="abc123")
"""

from kagami.core.aperiodic.history import ThoughtHistory
from kagami.core.aperiodic.similarity_filter import filter_by_novelty
from kagami.core.aperiodic.wrapper import apply_aperiodic_filter, update_lzc_metrics

__all__ = [
    "ThoughtHistory",
    "apply_aperiodic_filter",
    "filter_by_novelty",
    "update_lzc_metrics",
]
