"""Unified Perception Module - LeCun Cognitive Architecture Component.

This module provides the unified interface for all sensory processing in the system.

Exports:
- PerceptionModule: Main unified perception interface
- PerceptionConfig: Configuration dataclass
- get_perception_module: Singleton accessor
"""

from kagami.core.perception.perception_module import (
    PerceptionConfig,
    PerceptionModule,
    get_perception_module,
    reset_perception_module,
)

__all__ = [
    "PerceptionConfig",
    "PerceptionModule",
    "get_perception_module",
    "reset_perception_module",
]
