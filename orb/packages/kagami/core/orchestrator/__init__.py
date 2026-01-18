"""Orchestration entry points.

This package exposes two orchestrators:
- **IntentOrchestrator**: user-facing intent routing
- **UnifiedOrchestrator**: internal LeCun-style control loop

Implementation note:
This module uses *lazy attribute resolution* to avoid import cycles in the
orchestrator/training/learning stack. Public API remains stable for callers.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "E8JEPAConfig",  # Replaces deprecated HJEPAConfig
    "EgoModel",
    "EgoModelConfig",
    "EntityMemory",
    "EntityMemoryConfig",
    "ExecutionMode",
    "ExecutionResult",
    # Re-exports from world_model (canonical sources)
    "HierarchicalJEPA",
    # User-facing intent orchestrator
    "IntentOrchestrator",
    "OrchestratorConfig",
    # Internal LeCun JEPA control loop
    "UnifiedOrchestrator",
    "get_ego_model",
    "get_entity_memory",
    "get_hierarchical_jepa",
    "get_orchestrator",
    "reset_orchestrator",
]


def __getattr__(name: str) -> Any:  # pragma: no cover
    """Lazy-resolve orchestrator exports to avoid import cycles."""
    import importlib

    # Orchestrators
    if name in {
        "IntentOrchestrator",
    }:
        mod = importlib.import_module("kagami.core.orchestrator.core")
        return getattr(mod, name)

    if name in {
        "UnifiedOrchestrator",
        "OrchestratorConfig",
        "ExecutionMode",
        "ExecutionResult",
        "get_orchestrator",
        "reset_orchestrator",
    }:
        mod = importlib.import_module("kagami.core.orchestrator.unified_orchestrator")
        return getattr(mod, name)

    # Canonical world-model re-exports
    if name in {"HierarchicalJEPA", "E8JEPAConfig", "get_hierarchical_jepa"}:
        mod = importlib.import_module("kagami.core.world_model.hierarchical_jepa")
        return getattr(mod, name)

    if name in {"EgoModel", "EgoModelConfig", "get_ego_model"}:
        mod = importlib.import_module("kagami.core.world_model.ego_model")
        return getattr(mod, name)

    if name in {"EntityMemory", "EntityMemoryConfig", "get_entity_memory"}:
        mod = importlib.import_module("kagami.core.world_model.entity_memory")
        return getattr(mod, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
