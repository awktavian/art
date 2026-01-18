"""Continuous Mind - Always-On Reasoning.

This package implements the architectural shift from REQUEST-RESPONSE to CONTINUOUS.

Key exports:
- ContinuousMind: The main always-on reasoning loop
- SharedWorkingMemory: Persistent context across thoughts
- Thought, Goal: Data structures
"""

from kagami.core.continuous.continuous_mind import (
    ContinuousMind,
    Goal,
    SharedWorkingMemory,
    Thought,
    ThoughtType,
    get_continuous_mind,
)

__all__ = [
    "ContinuousMind",
    "Goal",
    "SharedWorkingMemory",
    "Thought",
    "ThoughtType",
    "get_continuous_mind",
]
