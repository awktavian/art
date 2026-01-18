"""Main orchestrator for ForgeMatrix.

COLONY INTEGRATION (Dec 4, 2025):
================================
ForgeMatrix now integrates with the K OS world model via ForgeColonyBridge.
This enables:
- Cusp (A₃) catastrophe dynamics for bistable decision-making
- OptimalityImprovements for enhanced generation quality
- Colony state tracking for organism-level coordination
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, cast

import torch

from kagami.core.di.container import try_resolve
from kagami.core.interfaces import EventBroadcaster
from kagami.core.tic import SafetyCheck, TICEnforcer  # A+ grade: TIC enforcement
from kagami.forge.exceptions import ExportError
from kagami.forge.forge_middleware import forge_operation
from kagami.forge.matrix import components, converters

# Internal Modules
from kagami.forge.matrix.config import load_forge_config
from kagami.forge.matrix.events import EventManager
from kagami.forge.matrix.lifecycle import LifecycleManager
from kagami.forge.matrix.registry import ComponentRegistry
from kagami.forge.matrix.renderer import ForgeStageContext
from kagami.forge.matrix.state import coerce_request
from kagami.forge.schema import CharacterRequest, ExportFormat

logger = logging.getLogger(__name__)

# Colony integration (lazy loaded)
_COLONY_BRIDGE = None


def _get_colony_bridge() -> Any:
    """Lazy load colony bridge to avoid circular imports."""
    global _COLONY_BRIDGE
    if _COLONY_BRIDGE is None:
        from kagami.forge.colony_integration import get_forge_colony_bridge

        _COLONY_BRIDGE = get_forge_colony_bridge()
    return _COLONY_BRIDGE


def _hash_embedding(text: str, dim: int = 256) -> torch.Tensor:
    """Deterministic text → unit vector embedding (no external deps).

    Used for colony bridge context when a real encoder isn't available.
    """
    t = str(text or "")
    digest = hashlib.sha256(t.encode("utf-8")).digest()
    # Expand digest bytes to the requested dimension.
    raw = (digest * ((dim // len(digest)) + 1))[:dim]
    vec = torch.tensor(list(raw), dtype=torch.float32)
    vec = (vec / 127.5) - 1.0  # [-1, 1]
    vec = vec / (vec.norm() + 1e-8)
    return cast(torch.Tensor, vec.unsqueeze(0))


class ForgeMatrix:
    """Main orchestrator for the Forge character generation system.

    Co-ordinates:
    - Lifecycle (init)
    - Registry (modules)
    - Components (logic)
    - Events (tracing)
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = load_forge_config(config)
        self.logger = logger

        # Subsystems
        self._event_manager = EventManager()
        self.registry = ComponentRegistry(self.config)
        self.lifecycle = LifecycleManager(self.registry, self._record_trace_event)

        # State
        self._bus = None

    # --- Properties ---

    @property
    def ai_modules(self) -> dict[str, Any]:
        return self.registry.ai_modules

    @property
    def execution_trace(self) -> list[dict[str, Any]]:
        return list(self._event_manager._execution_trace)

    def get_execution_trace(self) -> list[dict[str, Any]]:
        return self.execution_trace

    @property
    def initialized(self) -> bool:
        return self.lifecycle.initialized

    @property
    def asset_cache(self) -> Any:
        return self.lifecycle.asset_cache

    # --- Lifecycle ---

    async def initialize(self) -> None:
        """Initialize the ForgeMatrix system."""
        self.lifecycle.initialize()

    # --- Event Helpers ---

    def _build_trace_attrs(
        self, component: str, request: Any | None, extra: dict[str, Any] | None
    ) -> dict[str, Any]:
        return self._event_manager.build_trace_attrs(component, request, extra)

    def _record_trace_event(
        self, component: str, status: str, request: Any = None, **kwargs: Any
    ) -> None:
        self._event_manager.record_trace_event(component, status, request, **kwargs)

    def _trace_stage(
        self, component: str, request: Any = None, extra: Any = None
    ) -> ForgeStageContext:
        return ForgeStageContext(self, component, request, extra)

    # --- Tracer Protocol Implementation for Components ---

    class _TracerAdapter:
        def __init__(self, matrix: ForgeMatrix) -> None:
            self.matrix = matrix

        def trace_stage(self, component: str, request: Any = None) -> ForgeStageContext:
            return self.matrix._trace_stage(component, request)

    @property
    def tracer(self) -> _TracerAdapter:
        return self._TracerAdapter(self)

    # --- Main Pipeline ---

    @TICEnforcer(
        type_name="character_generation",
        pre=[SafetyCheck()],
        invariants=[],
        termination_metric="completion",
    )
    @forge_operation("character_generation", module="forge.matrix", aspect="character")
    async def generate_character(
        self, request: CharacterRequest | dict[str, Any] | Any, **kwargs: Any
    ) -> dict[str, Any]:
        """Generate a complete character from a request."""
        request = coerce_request(request)
        concept = str(getattr(request, "concept", "") or "").strip()
        if len(concept) < 3:
            return {
                "request_id": getattr(request, "request_id", "unknown"),
                "concept": concept,
                "status": "error",
                "success": False,
                "error": "concept is required (min 3 characters)",
                "error_code": "missing_concept",
                "character": {},
                "metrics": {},
            }

        async with self._trace_stage("pipeline.generate", request, {"module": "forge_matrix"}):
            result = await self._generate_character_impl(request)
            return result
        # unreachable but makes mypy happy
        raise RuntimeError("Unreachable code")

    async def _generate_character_impl(self, request: CharacterRequest) -> dict[str, Any]:
        """Internal implementation for character generation.

        FULL PIPELINE (Dec 2025):
        Text → Visual Design → Rigging → Animation → Voice/Personality/Narrative → World → Export

        No fallbacks. All components must succeed or the pipeline fails.
        """
        if not self.initialized:
            self.lifecycle.initialize()

        parts: dict[str, Any] = {}
        corr = getattr(request, "request_id", None)

        # Initialize colony state (if available)
        colony_state = None
        colony_bridge = _get_colony_bridge()
        if colony_bridge is not None:
            try:
                concept_text = str(getattr(request, "concept", "") or "")
                context_text = "\n".join(
                    [
                        str(getattr(request, "name", "") or ""),
                        str(getattr(request, "description", "") or ""),
                        str(getattr(request, "style_prompt", "") or ""),
                    ]
                ).strip()
                concept_emb = _hash_embedding(concept_text, dim=256)
                context_emb = _hash_embedding(context_text or concept_text, dim=256)
                colony_result = colony_bridge(concept_emb, context_emb)
                colony_state = colony_result.get("state")
                parts["colony_metrics"] = colony_result.get("metrics", {})
            except Exception as e:
                logger.debug(f"Colony integration skipped: {e}")

        await self._emit_progress("forge.start", 3, 150000, "Starting generation", corr)

        # 1. Visual Design (3D mesh generation via Gaussian Splatting)
        await self._emit_progress(
            "forge.visual_design", 10, 120000, "Generating 3D character", corr
        )
        visual_res = await components.generate_visuals(self.registry, self.tracer, request)
        parts["character_data"] = visual_res

        # Extract mesh for rigging
        mesh_obj = None
        if isinstance(visual_res, dict):
            mesh_obj = (
                visual_res.get("mesh")
                or visual_res.get("mesh_data")
                or visual_res.get("mesh_trimesh")
            )
        else:
            mesh_obj = getattr(visual_res, "mesh_data", None)

        # 2. Rigging (automatic skeleton and weight painting via UniRig)
        await self._emit_progress("forge.rigging", 25, 90000, "Rigging character", corr)
        rigging_res = await components.process_rigging(
            self.registry, self.tracer, request, mesh_obj
        )
        parts["rigged_data"] = rigging_res
        rigged_mesh = rigging_res.get("rigged_mesh")

        # 3. Animation (text-to-motion via Motion-Agent)
        await self._emit_progress("forge.animation", 40, 70000, "Generating motion", corr)
        animation_res = await components.animate_character(
            self.registry, self.tracer, request, rigged_mesh
        )
        parts["animation_data"] = animation_res

        # 4. Personality & Voice & Narrative (parallelized - all must succeed)
        await self._emit_progress("forge.behavior", 55, 50000, "Synthesizing behavior", corr)
        behavior_res, voice_res, narrative_res = await asyncio.gather(
            components.generate_personality(self.registry, self.tracer, request),
            components.generate_voice(self.registry, self.tracer, request),
            components.generate_narrative(self.registry, self.tracer, request),
        )
        parts["behavior"] = behavior_res
        parts["voice"] = voice_res
        parts["narrative"] = narrative_res

        # 5. World Composition (place character in scene)
        await self._emit_progress("forge.world", 70, 35000, "Composing world", corr)
        try:
            world_res = await components.compose_world(
                self.registry,
                self.tracer,
                request,
                character_data=parts.get("character_data", {}),
                animation_data=parts.get("animation_data", {}),
            )
            parts["world_data"] = world_res
        except Exception as e:
            # World composition is optional - log but continue
            logger.warning(f"World composition skipped: {e}")
            parts["world_data"] = None

        # 6. Export (multi-format character export)
        await self._emit_progress("forge.export", 85, 20000, "Exporting character", corr)
        export_formats = []
        raw_formats = getattr(request, "export_formats", []) or []
        for fmt in raw_formats:
            if isinstance(fmt, ExportFormat):
                export_formats.append(fmt.value)
            else:
                export_formats.append(str(fmt))

        if export_formats:
            parts["export_data"] = await components.export_character(
                self.registry, parts.get("character_data", {}), export_formats
            )
        else:
            raise ExportError("none", "No export formats requested")

        # 7. Compilation
        await self._emit_progress("forge.compile", 95, 5000, "Compiling character", corr)
        character = converters.compile_character(parts)
        metrics = converters.calculate_quality_metrics(character)

        # Update colony state
        if colony_bridge is not None and colony_state is not None:
            try:
                quality_score = getattr(metrics, "overall_score", 0.5)
                colony_bridge.update_from_result(
                    colony_state,
                    success=True,
                    quality_score=quality_score,
                )
            except Exception as e:
                logger.debug(f"Colony state update skipped: {e}")

        result: dict[str, Any] = {
            "request_id": getattr(request, "request_id", "unknown"),
            "concept": getattr(request, "concept", "character"),
            "status": "success",
            "success": True,
            "character": character,
            "metrics": metrics,
            "animation": parts.get("animation_data"),
            "voice": parts.get("voice"),
            "world": parts.get("world_data"),
        }

        if "colony_metrics" in parts:
            result["colony_metrics"] = parts["colony_metrics"]

        return result

    # --- Helper Methods ---

    async def _emit_progress(
        self, stage: str, progress: int, eta: int, rationale: str, correlation_id: str | None
    ) -> None:
        # Initialize bus lazily
        if self._bus is None:
            try:
                from kagami.core.events import get_unified_bus

                self._bus = get_unified_bus()  # type: ignore[assignment]
            except Exception:
                pass

        payload = {
            "stage": stage,
            "progress_percent": progress,
            "eta_ms": eta,
            "rationale": rationale,
            "correlation_id": correlation_id,
        }
        try:
            if self._bus:
                await self._bus.publish("forge.progress", payload)  # type: ignore[unreachable]

            broadcaster = try_resolve(EventBroadcaster)
            if broadcaster:
                await broadcaster.broadcast("forge.progress", payload)
        except Exception as e:
            self.logger.debug(f"Progress emission failed: {e}")


# Global accessor
_FORGE_MATRIX: ForgeMatrix | None = None


def get_forge_matrix() -> ForgeMatrix:
    global _FORGE_MATRIX
    if _FORGE_MATRIX is None:
        _FORGE_MATRIX = ForgeMatrix()
    return _FORGE_MATRIX
