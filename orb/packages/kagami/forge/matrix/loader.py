"""Component Loader for Forge Matrix.

Imports Forge modules with explicit unavailability tracking.

This layer exists so ForgeMatrix can still run (and tests can execute) even when
optional heavy dependencies are missing. When an import fails, the error is
recorded in ``_MODULE_IMPORT_ERRORS`` and the corresponding symbol is set[Any] to
``None``. Operations requiring unavailable modules will fail fast with clear errors.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Track import errors for registry diagnostics
_MODULE_IMPORT_ERRORS: dict[str, Exception] = {}


def _mark_import_error(key: str, exc: Exception) -> None:
    _MODULE_IMPORT_ERRORS[key] = exc
    logger.debug("Forge module import failed for %s: %s", key, exc)


# Optional imports: each symbol is set[Any] to None if unavailable -------------------
PersonalityEngine: Any = None
try:
    from kagami.forge.modules.behavior_ai.personality_engine import (
        PersonalityEngine as _PersonalityEngine,
    )

    PersonalityEngine = _PersonalityEngine
except Exception as e:  # pragma: no cover - depends on optional deps
    _mark_import_error("personality_engine", e)

ExportManager: Any = None
try:
    from kagami.forge.modules.export.manager import ExportManager as _ExportManager

    ExportManager = _ExportManager
except Exception as e:  # pragma: no cover
    _mark_import_error("export_manager", e)

GenesisPhysicsWrapper: Any = None
try:
    from kagami.forge.modules.genesis_physics_wrapper import (
        GenesisPhysicsWrapper as _GenesisPhysicsWrapper,
    )

    GenesisPhysicsWrapper = _GenesisPhysicsWrapper
except Exception as e:  # pragma: no cover
    _mark_import_error("physics_engine", e)

BackstorySynthesizer: Any = None
try:
    from kagami.forge.modules.narrative.backstory_synthesizer import (
        BackstorySynthesizer as _BackstorySynthesizer,
    )

    BackstorySynthesizer = _BackstorySynthesizer
except Exception as e:  # pragma: no cover
    _mark_import_error("narrative", e)

RiggingModule: Any = None
try:
    from kagami.forge.modules.rigging import RiggingModule as _RiggingModule

    RiggingModule = _RiggingModule
except Exception as e:  # pragma: no cover
    _mark_import_error("rigging", e)

CharacterVisualProfiler: Any = None
try:
    from kagami.forge.modules.visual_design.character_profiler import (
        CharacterVisualProfiler as _CharacterVisualProfiler,
    )

    CharacterVisualProfiler = _CharacterVisualProfiler
except Exception as e:  # pragma: no cover
    _mark_import_error("character_profiler", e)

IntelligentVisualDesigner: Any = None
try:
    from kagami.forge.modules.visual_design.intelligent_visual_designer import (
        IntelligentVisualDesigner as _IntelligentVisualDesigner,
    )

    IntelligentVisualDesigner = _IntelligentVisualDesigner
except Exception as e:  # pragma: no cover
    _mark_import_error("visual_designer", e)

WorldComposer: Any = None
WorldComposeOptions: Any = None
try:
    from kagami.forge.modules.world.world_composer import (
        WorldComposeOptions as _WorldComposeOptions,
    )
    from kagami.forge.modules.world.world_composer import (
        WorldComposer as _WorldComposer,
    )

    WorldComposer = _WorldComposer
    WorldComposeOptions = _WorldComposeOptions
except Exception as e:  # pragma: no cover
    _mark_import_error("world_composer", e)

WorldGenerationModule: Any = None
try:
    from kagami.forge.modules.world.world_generation import (
        WorldGenerationModule as _WorldGenerationModule,
    )

    WorldGenerationModule = _WorldGenerationModule
except Exception as e:  # pragma: no cover
    _mark_import_error("world_generation", e)

AnimationModule: Any = None
try:
    from kagami.forge.modules.animation import AnimationModule as _AnimationModule

    AnimationModule = _AnimationModule
except Exception as e:  # pragma: no cover
    _mark_import_error("animation", e)

LRUFileCache: Any = None
try:
    from kagami.forge.modules.world.world_cache import LRUFileCache as _LRUFileCache

    LRUFileCache = _LRUFileCache
except Exception as e:  # pragma: no cover
    _mark_import_error("world_cache", e)

__all__ = [
    "_MODULE_IMPORT_ERRORS",
    "AnimationModule",
    "BackstorySynthesizer",
    "CharacterVisualProfiler",
    "ExportManager",
    "GenesisPhysicsWrapper",
    "IntelligentVisualDesigner",
    "LRUFileCache",
    "PersonalityEngine",
    "RiggingModule",
    "WorldComposeOptions",
    "WorldComposer",
    "WorldGenerationModule",
]
