"""Component Registry for Forge Matrix.

Manages lifecycle and dependencies of Forge modules.
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.forge.matrix.loader import (
    _MODULE_IMPORT_ERRORS,
    AnimationModule,
    BackstorySynthesizer,
    CharacterVisualProfiler,
    ExportManager,
    GenesisPhysicsWrapper,
    IntelligentVisualDesigner,
    PersonalityEngine,
    RiggingModule,
    WorldComposer,
    WorldGenerationModule,
)

logger = logging.getLogger(__name__)


# Module dependency graph
# NOTE: "voice" removed (Jan 2026) - Use kagami.core.services.voice.kagami_voice instead
MODULE_DEPENDENCIES: dict[str, set[str]] = {
    "visual_designer": set(),
    "character_profiler": {"visual_designer"},
    "rigging": {"character_profiler"},
    "animation": {"rigging"},
    "personality_engine": set(),
    "narrative": {"personality_engine"},
    "export_manager": {"rigging", "animation"},
    "physics_engine": {"rigging"},
    "world_generation": set(),
    "world_composer": {"world_generation", "physics_engine", "animation"},
}


class ComponentRegistry:
    """Registry for Forge components with dependency tracking."""

    def __init__(self, config: dict[str, Any]):
        """Initialize component registry.

        Args:
            config: Forge configuration
        """
        self.config = config
        self.ai_modules: dict[str, Any] = {}
        self.import_errors: dict[str, Exception] = dict(_MODULE_IMPORT_ERRORS)

    def initialize_all(self, trace_callback: Any = None) -> None:
        """Initialize all available modules.

        Args:
            trace_callback: Optional callback for trace events
        """
        modules_to_init = [
            ("visual_designer", IntelligentVisualDesigner),
            ("character_profiler", CharacterVisualProfiler),
            ("rigging", RiggingModule),
            ("animation", AnimationModule),
            ("personality_engine", PersonalityEngine),
            ("narrative", BackstorySynthesizer),
            ("export_manager", ExportManager),
            ("physics_engine", GenesisPhysicsWrapper),
            ("world_generation", WorldGenerationModule),
            ("world_composer", WorldComposer),
        ]

        for module_name, module_class in modules_to_init:
            # Loader sets missing symbols to None and records import errors.
            if module_class is None:
                import_error = self.import_errors.get(module_name) or ImportError(
                    f"Module class for '{module_name}' not available"
                )
                self.import_errors[module_name] = import_error
                if trace_callback:
                    trace_callback(
                        f"module.{module_name}.instantiate",
                        "skipped",
                        reason="import_error",
                        error=f"{type(import_error).__name__}: {import_error}",
                    )
                continue
            self._init_module(module_name, module_class, trace_callback)

    def _init_module(
        self, module_name: str, module_class: type, trace_callback: Any = None
    ) -> None:
        """Initialize a single module.

        Args:
            module_name: Module identifier
            module_class: Module class to instantiate
            trace_callback: Optional trace callback
        """
        getattr(module_class, "__name__", str(module_class))

        # Check for import errors
        import_error = self.import_errors.get(module_name)
        if import_error is not None:
            error_text = f"{type(import_error).__name__}: {import_error}"
            logger.warning(f"⚠️  Module {module_name} unavailable: {error_text}")
            if trace_callback:
                trace_callback(
                    f"module.{module_name}.instantiate",
                    "skipped",
                    reason="import_error",
                    error=error_text,
                )
            return

        # Initialize module
        try:
            module_config = self.config.get("modules", {}).get(module_name, {})

            if module_name == "animation":
                instance = module_class(module_name)
            elif module_name == "rigging":
                instance = module_class(module_config)
            elif module_name == "world_composer":
                # WorldComposer requires physics and export_manager
                physics = self.ai_modules.get("physics_engine")
                export_mgr = self.ai_modules.get("export_manager")
                instance = module_class(physics=physics, export_manager=export_mgr)
            else:
                instance = module_class()

            self.ai_modules[module_name] = instance
            logger.debug(f"✅ Initialized {module_name}")

            if trace_callback:
                trace_callback(f"module.{module_name}.instantiate", "success")

        except Exception as e:
            logger.error(f"Failed to initialize {module_name}: {e}", exc_info=True)
            if trace_callback:
                trace_callback(f"module.{module_name}.instantiate", "error", error=str(e))

    def get_module(self, name: str) -> Any | None:
        """Get initialized module by name.

        Args:
            name: Module name

        Returns:
            Module instance or None if not available
        """
        return self.ai_modules.get(name)

    def is_available(self, name: str) -> bool:
        """Check if module is available.

        Args:
            name: Module name

        Returns:
            True if module is initialized
        """
        return name in self.ai_modules


__all__ = ["MODULE_DEPENDENCIES", "ComponentRegistry"]
