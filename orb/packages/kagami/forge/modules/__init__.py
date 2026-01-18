"""AetherForge AI Modules - Generation, Rigging, Animation, Export, Genesis.

Lazy-import helpers for heavy modules.
"""

from __future__ import annotations

import importlib
from typing import Any


def _lazy_import(path: str) -> Any:
    module_path, name = path.split(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, name)


def get_generation_module() -> Any:
    return _lazy_import("kagami.forge.modules.generation:GenerationModule")


def get_rigging_module() -> Any:
    return _lazy_import("kagami.forge.modules.rigging:RiggingModule")


def get_animation_module() -> Any:
    return _lazy_import("kagami.forge.modules.animation:AnimationModule")


def get_export_module() -> Any:
    return _lazy_import("kagami.forge.modules.export:ExportModule")


def get_realtime_renderer() -> Any:
    """Get real-time Genesis renderer with ATW reprojection."""
    return _lazy_import("kagami.forge.modules.genesis:RealtimeGenesisRenderer")


def get_realtime_config() -> Any:
    """Get real-time renderer configuration."""
    return _lazy_import("kagami.forge.modules.genesis:RealtimeConfig")


def get_material_library() -> Any:
    """Get Genesis material library."""
    return _lazy_import("kagami.forge.modules.genesis:MaterialLibrary")


__all__: list[str] = [
    "get_animation_module",
    "get_export_module",
    "get_generation_module",
    "get_material_library",
    "get_realtime_config",
    "get_realtime_renderer",
    "get_rigging_module",
]
