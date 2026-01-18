"""Component generation logic for ForgeMatrix.

No fallbacks. All components are required for full pipeline operation.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Protocol

from kagami.forge.exceptions import ModuleInitializationError, ModuleNotAvailableError
from kagami.forge.matrix.performance import monitor_performance
from kagami.forge.schema import CharacterRequest

logger = logging.getLogger(__name__)


class ComponentRegistryProtocol(Protocol):
    def is_available(self, name: str) -> bool: ...
    def get_module(self, name: str) -> Any: ...


class TracerProtocol(Protocol):
    def trace_stage(self, component: str, request: Any = None) -> Any: ...


@monitor_performance("personality_generation")
async def generate_personality(
    registry: ComponentRegistryProtocol, tracer: TracerProtocol, request: CharacterRequest
) -> dict[str, Any]:
    """Generate character personality. No fallbacks - fails fast if unavailable."""
    return await _execute_required(
        registry,
        tracer,
        "personality_engine",
        "component.personality",
        request,
        lambda m, r: m.generate(r),
    )


@monitor_performance("voice_synthesis")
async def generate_voice(
    registry: ComponentRegistryProtocol, tracer: TracerProtocol, request: CharacterRequest
) -> dict[str, Any]:
    """Generate character voice. No fallbacks - fails fast if unavailable."""
    return await _execute_required(
        registry,
        tracer,
        "voice",
        "component.voice",
        request,
        lambda m, r: m.generate(r),
    )


@monitor_performance("llm_inference")
async def generate_narrative(
    registry: ComponentRegistryProtocol, tracer: TracerProtocol, request: CharacterRequest
) -> dict[str, Any]:
    """Generate character narrative. No fallbacks - fails fast if unavailable."""

    async def _narrative_op(module: Any, req: CharacterRequest) -> Any:
        res = await module.generate(req)
        if is_dataclass(res) and not isinstance(res, type):
            return asdict(res)
        return res

    return await _execute_required(
        registry,
        tracer,
        "narrative",
        "component.narrative",
        request,
        _narrative_op,
    )


async def process_rigging(
    registry: ComponentRegistryProtocol,
    tracer: TracerProtocol,
    request: CharacterRequest,
    mesh_obj: Any,
) -> dict[str, Any]:
    """Process character rigging. No fallbacks - fails fast if unavailable."""
    if not registry.is_available("rigging"):
        raise ModuleNotAvailableError("rigging")

    if mesh_obj is None:
        raise ModuleInitializationError("rigging", "No mesh available for rigging")

    async with tracer.trace_stage("stage.rigging", request):
        rigging = registry.get_module("rigging")
        rig_in = {
            "generation": {
                "mesh": mesh_obj,
                "metadata": {"prompt": getattr(request, "concept", "")},
                "rigging_hints": {},
            }
        }
        rig_res = await rigging.process(rig_in)
        rigged_mesh = getattr(rig_res, "data", None)
        if rigged_mesh is None:
            raise RuntimeError("Rigging returned no mesh data")
        return {
            "skeleton": getattr(rigged_mesh, "skeleton", None),
            "weights": getattr(rigged_mesh, "weights", None),
            "rigged_mesh": rigged_mesh,
        }


@monitor_performance("animation_generation")
async def animate_character(
    registry: ComponentRegistryProtocol,
    tracer: TracerProtocol,
    request: CharacterRequest,
    rigged_mesh: Any,
) -> dict[str, Any]:
    """Generate character animation from concept."""
    if not registry.is_available("animation"):
        raise ModuleNotAvailableError("animation")

    if rigged_mesh is None:
        raise ModuleInitializationError("animation", "Rigged mesh required for animation")

    async with tracer.trace_stage("stage.animation", request):
        animation = registry.get_module("animation")
        # Extract motion prompt from request concept
        concept = getattr(request, "concept", "")
        motion_prompt = f"A character {concept} walking and moving naturally"

        anim_input = {
            "text_prompt": motion_prompt,
            "motion_length": 3.0,  # Default 3 second animation
        }
        result = await animation.process(anim_input)
        if result.status.value != "completed":
            raise RuntimeError(f"Animation generation failed: {result.error}")

        return {
            "animation_data": result.data.get("animation_data"),
            "motion_sequence": result.data.get("motion_sequence"),
            "performance_stats": result.data.get("performance_stats"),
        }


async def export_character(
    registry: ComponentRegistryProtocol, character_data: dict[str, Any], formats: list[str]
) -> dict[str, Any]:
    """Export character data."""
    if not registry.is_available("export_manager"):
        raise ModuleNotAvailableError("export_manager")

    manager = registry.get_module("export_manager")
    results = {}
    for fmt in formats:
        try:
            results[fmt] = await manager.export(character_data, format=fmt)
        except Exception as e:
            logger.error(f"Export {fmt} failed: {e}")
            raise
    return results


@monitor_performance("visual_design")
async def generate_visuals(
    registry: ComponentRegistryProtocol, tracer: TracerProtocol, request: CharacterRequest
) -> Any:
    """Generate visual components. No fallbacks - fails fast if unavailable."""
    if not registry.is_available("character_profiler"):
        raise ModuleNotAvailableError("character_profiler")

    module = registry.get_module("character_profiler")
    async with tracer.trace_stage("stage.visual_design", request):
        result = await module.generate(request)
        if result is None or (hasattr(result, "success") and not result.success):
            error = getattr(result, "error", "Unknown error") if result else "No result"
            raise RuntimeError(f"Visual design generation failed: {error}")
        return result


@monitor_performance("world_composition")
async def compose_world(
    registry: ComponentRegistryProtocol,
    tracer: TracerProtocol,
    request: CharacterRequest,
    character_data: dict[str, Any],
    animation_data: dict[str, Any],
) -> dict[str, Any]:
    """Compose world with character placed in scene. No fallbacks."""
    if not registry.is_available("world_composer"):
        raise ModuleNotAvailableError("world_composer")

    async with tracer.trace_stage("stage.world_composition", request):
        composer = registry.get_module("world_composer")
        world_gen = (
            registry.get_module("world_generation")
            if registry.is_available("world_generation")
            else None
        )

        # Generate world environment first
        world_dir = None
        if world_gen:
            world_result = await world_gen.generate(
                prompt=getattr(request, "concept", ""),
                style=getattr(request, "style", None),
            )
            if world_result and world_result.get("success"):
                world_dir = world_result.get("output_dir")

        if world_dir is None:
            raise RuntimeError("World generation failed or unavailable")

        # Compose world with character
        from kagami.forge.modules.world.world_composer import WorldComposeOptions

        options = WorldComposeOptions(
            scene_type="character_studio",
            duration=animation_data.get("motion_sequence", {}).get("duration", 3.0)
            if isinstance(animation_data.get("motion_sequence"), dict)
            else 3.0,
            fps=60,
            motion_type="custom",
            export_usd=True,
        )

        result = await composer.compose(
            character_data=character_data,
            world_dir=world_dir,
            options=options,
        )

        if not result.success:
            raise RuntimeError(f"World composition failed: {result.error}")

        return {
            "session_id": result.session_id,
            "world_assets": result.world_assets,
            "character_id": result.character_id,
            "export_path": result.export_path,
            "performance": result.performance,
        }


# --- Helper ---


async def _execute_required(
    registry: ComponentRegistryProtocol,
    tracer: TracerProtocol,
    module_name: str,
    trace_name: str,
    request: CharacterRequest,
    operation: Any,
) -> Any:
    """Execute a required module operation. Fails fast if module unavailable or operation fails."""
    if not registry.is_available(module_name):
        raise ModuleNotAvailableError(module_name)

    module = registry.get_module(module_name)
    async with tracer.trace_stage(trace_name, request):
        return await operation(module, request)


# Export everything
__all__ = [
    "animate_character",
    "compose_world",
    "export_character",
    "generate_narrative",
    "generate_personality",
    "generate_visuals",
    "generate_voice",
    "process_rigging",
]
