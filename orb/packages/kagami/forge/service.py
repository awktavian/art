"""Unified Forge Service Layer.

Provides a single entry point for all Forge operations, abstracting away
the complexity of ForgeMatrix, modules, and cross-cutting concerns.

This service handles:
- Character generation (text-to-3D, image-to-3D)
- Animation generation (facial, gestures, motion)
- Validation and content safety
- Response standardization
- Metrics and receipt emission

Usage:
    service = get_forge_service()
    result = await service.generate_character(concept="warrior", quality="draft")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kagami_observability.metrics import (
    API_ERRORS,
    CHARACTER_GENERATIONS,
)

from kagami.forge.exceptions import (
    ForgeError,
    ModuleInitializationError,
    ModuleNotAvailableError,
)
from kagami.forge.matrix import ForgeMatrix, get_forge_matrix
from kagami.forge.schema import ExportFormat, QualityLevel
from kagami.forge.semantic_cache import get_semantic_cache

logger = logging.getLogger(__name__)


class ForgeOperation(str, Enum):
    """Available Forge operations (service-level).

    Note: This is distinct from ForgeCapability in kagami.core.interfaces.forge_types
    which defines provider-level capabilities (TEXT_GENERATION, IMAGE_GENERATION, etc.).
    """

    CHARACTER_GENERATION = "character.generate"
    IMAGE_TO_CHARACTER = "character.from_image"
    ANIMATION_FACIAL = "animation.facial"
    ANIMATION_GESTURE = "animation.gesture"
    ANIMATION_MOTION = "animation.motion"
    GENESIS_VIDEO = "genesis.video"
    VALIDATION = "validation"
    CONTENT_SAFETY = "content_safety"


@dataclass
class ForgeRequest:
    """Unified request structure for Forge operations.

    All Forge operations accept this standardized request format.
    """

    capability: ForgeOperation
    params: dict[str, Any] = field(default_factory=dict[str, Any])
    quality_mode: str = "preview"
    export_formats: list[str] = field(default_factory=list[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    correlation_id: str | None = None
    idempotency_key: str | None = None

    @property
    def quality_level(self) -> QualityLevel:
        """Convert quality_mode string to QualityLevel enum."""
        mapping = {
            "preview": QualityLevel.LOW,
            "draft": QualityLevel.MEDIUM,
            "final": QualityLevel.HIGH,
        }
        return mapping.get(self.quality_mode, QualityLevel.LOW)

    @property
    def export_format_enums(self) -> list[ExportFormat]:
        """Convert export format strings to ExportFormat enums."""
        result = []
        for fmt in self.export_formats:
            try:
                result.append(ExportFormat(fmt))
            except ValueError:
                continue
        return result


@dataclass
class ForgeResponse:
    """Standardized response from Forge operations.

    All Forge operations return this consistent format.
    """

    success: bool
    capability: str
    data: dict[str, Any] = field(default_factory=dict[str, Any])
    correlation_id: str | None = None
    duration_ms: int = 0
    cached: bool = False
    error: str | None = None
    error_code: str | None = None
    receipt: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "capability": self.capability,
            "data": self.data,
            "duration_ms": self.duration_ms,
        }
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.cached:
            result["cached"] = True
        if self.error:
            result["error"] = self.error
            if self.error_code:
                result["error_code"] = self.error_code
        if self.receipt:
            result["receipt"] = self.receipt
        return result


class ForgeService:
    """Unified service layer for Forge operations.

    Provides high-level methods for all Forge capabilities with
    consistent error handling, metrics, and response formats.
    """

    def __init__(self, matrix: ForgeMatrix | None = None) -> None:
        self._matrix = matrix
        self._initialized = False

    @property
    def matrix(self) -> ForgeMatrix:
        """Lazy-load ForgeMatrix."""
        if self._matrix is None:
            self._matrix = get_forge_matrix()
        return self._matrix

    async def initialize(self) -> None:
        """Initialize the Forge service and underlying matrix."""
        if not self._initialized:
            await self.matrix.initialize()
            self._initialized = True

    async def execute(self, request: ForgeRequest) -> ForgeResponse:
        """Execute a Forge operation based on capability.

        This is the main entry point for all Forge operations.

        Args:
            request: Unified ForgeRequest with capability and params

        Returns:
            Standardized ForgeResponse
        """
        t0 = time.perf_counter()
        if self._requires_matrix(request.capability):
            await self.initialize()

        try:
            handler = self._get_handler(request.capability)
            result = await handler(request)
            duration_ms = int((time.perf_counter() - t0) * 1000)
            result.duration_ms = duration_ms
            result.correlation_id = request.correlation_id
            return result  # type: ignore[no-any-return]

        except ModuleNotAvailableError as e:
            return self._error_response(
                request,
                str(e),
                "module_unavailable",
                time.perf_counter() - t0,
            )
        except ModuleInitializationError as e:
            return self._error_response(
                request,
                str(e),
                "module_init_failed",
                time.perf_counter() - t0,
            )
        except ForgeError as e:
            return self._error_response(
                request,
                str(e),
                "forge_error",
                time.perf_counter() - t0,
            )
        except Exception as e:
            logger.error(f"Forge operation failed: {e}", exc_info=True)
            self._record_error(request.capability, e)
            return self._error_response(
                request,
                str(e),
                "internal_error",
                time.perf_counter() - t0,
            )

    def _get_handler(self, capability: ForgeOperation) -> Any:
        """Get handler function for capability."""
        handlers = {
            ForgeOperation.CHARACTER_GENERATION: self._handle_character_generation,
            ForgeOperation.IMAGE_TO_CHARACTER: self._handle_image_to_character,
            ForgeOperation.ANIMATION_FACIAL: self._handle_animation_facial,
            ForgeOperation.ANIMATION_GESTURE: self._handle_animation_gesture,
            ForgeOperation.ANIMATION_MOTION: self._handle_animation_motion,
            ForgeOperation.GENESIS_VIDEO: self._handle_genesis_video,
        }
        handler = handlers.get(capability)
        if not handler:
            raise ForgeError(f"Unknown capability: {capability}")
        return handler

    # --- Capability Handlers ---

    async def _handle_character_generation(self, request: ForgeRequest) -> ForgeResponse:
        """Handle character generation from text concept."""
        concept = request.params.get("concept", "")
        if not concept:
            return ForgeResponse(
                success=False,
                capability=request.capability.value,
                error="concept is required",
                error_code="missing_concept",
            )

        # Try semantic cache first
        cache = get_semantic_cache()

        async def _generate(c: str) -> dict[str, Any]:
            from kagami.forge.schema import CharacterRequest

            char_request = CharacterRequest(
                request_id=request.correlation_id or "",
                concept=c,
                personality_brief=request.params.get("personality_brief"),
                backstory_brief=request.params.get("backstory_brief"),
                export_formats=request.export_format_enums,
                quality_level=request.quality_level,
                metadata=request.metadata,
            )
            return await self.matrix.generate_character(char_request)  # type: ignore[no-any-return]

        result, cached = await cache.get_or_generate(concept, _generate)

        # Record metrics
        quality_label = request.quality_mode
        if cached:
            try:
                CHARACTER_GENERATIONS.labels("success_cached", quality_label).inc()
            except Exception:
                logger.debug("Failed to record cached character generation metric", exc_info=True)
        else:
            try:
                CHARACTER_GENERATIONS.labels("success", quality_label).inc()
            except Exception:
                logger.debug("Failed to record character generation metric", exc_info=True)

        return ForgeResponse(
            success=True,
            capability=request.capability.value,
            data=result,
            cached=cached,
        )

    async def _handle_image_to_character(self, request: ForgeRequest) -> ForgeResponse:
        """Handle character generation from image."""
        image_path = request.params.get("image_path")
        if not image_path:
            return ForgeResponse(
                success=False,
                capability=request.capability.value,
                error="image_path is required",
                error_code="missing_image",
            )

        if self.matrix is None:
            return ForgeResponse(  # type: ignore[unreachable]
                success=False,
                capability=request.capability.value,
                error="Forge matrix not initialized",
                error_code="matrix_unavailable",
            )

        result = await self.matrix.generate_character_from_image(  # type: ignore[attr-defined]
            image_path=image_path,
            personality_brief=request.params.get("personality_brief"),
            backstory_brief=request.params.get("backstory_brief"),
            quality_level=request.quality_mode,
            metadata=request.metadata,
        )

        return ForgeResponse(
            success=True,
            capability=request.capability.value,
            data={"character": result},
        )

    async def _handle_animation_facial(self, request: ForgeRequest) -> ForgeResponse:
        """Handle facial animation generation."""
        animation_type = request.params.get("type", "blinks")
        duration = float(request.params.get("duration", 10.0))

        from kagami.forge.modules.motion.facial_animator import FacialAnimator

        animator = FacialAnimator()

        if animation_type == "blinks":
            # blink_rate is blinks per minute (default 20 bpm is normal human rate)
            blink_rate = int(request.params.get("blink_rate", 20))
            animation = await animator.generate_blinks(duration=duration, blink_rate=blink_rate)
        elif animation_type == "expressions":
            emotion = request.params.get("emotion", "neutral")
            intensity = float(request.params.get("intensity", 0.8))
            animation = await animator.generate_expression(  # type: ignore[assignment]
                emotion=emotion, intensity=intensity
            )
        else:
            return ForgeResponse(
                success=False,
                capability=request.capability.value,
                error=f"Unknown animation type: {animation_type}",
                error_code="unknown_animation_type",
            )

        return ForgeResponse(
            success=True,
            capability=request.capability.value,
            data={"animation": animation, "type": animation_type, "duration": duration},
        )

    async def _handle_animation_gesture(self, request: ForgeRequest) -> ForgeResponse:
        """Handle gesture animation generation."""
        gesture_type = request.params.get("type", "idle")
        duration = float(request.params.get("duration", 10.0))
        energy_level = float(request.params.get("energy_level", 0.3))

        from kagami.forge.modules.motion.gesture_engine import GestureEngine

        engine = GestureEngine()

        # Build character traits from energy level for gesture generation
        character_traits = {"energy_level": energy_level, "expressiveness": energy_level}

        if gesture_type == "idle":
            animation = await engine.generate_idle_gestures(
                duration=duration, character_traits=character_traits
            )
        else:
            # For non-idle gestures, use generate_from_speech with gesture type context
            animation = await engine.generate_from_speech(
                speech_data={
                    "text": f"Perform a {gesture_type} gesture",
                    "emphasis_words": [gesture_type],
                    "duration": duration,
                    "prosody": {"pitch_contour": [], "energy": []},
                }
            )

        return ForgeResponse(
            success=True,
            capability=request.capability.value,
            data={
                "animation": animation,
                "type": gesture_type,
                "duration": duration,
                "energy_level": energy_level,
            },
        )

    async def _handle_animation_motion(self, request: ForgeRequest) -> ForgeResponse:
        """Handle motion animation generation."""
        motion_prompt = request.params.get("prompt", "")
        duration = float(request.params.get("duration", 5.0))

        if not motion_prompt:
            return ForgeResponse(
                success=False,
                capability=request.capability.value,
                error="prompt is required for motion generation",
                error_code="missing_prompt",
            )

        from kagami.forge.modules.animation import AnimationModule

        module = AnimationModule("motion")
        await module.initialize()

        # AnimationModule uses process() with a dict[str, Any] containing text_prompt and motion_length
        result = await module.process(
            {
                "text_prompt": motion_prompt,
                "motion_length": duration,
            }
        )

        return ForgeResponse(
            success=True,
            capability=request.capability.value,
            data={
                "motion": result.data if hasattr(result, "data") else result,
                "prompt": motion_prompt,
                "duration": duration,
            },
        )

    async def _handle_genesis_video(self, request: ForgeRequest) -> ForgeResponse:
        """Generate a Genesis-simulated video for creators.

        Params accepted:
        - Either a full spec dict[str, Any] (VideoSpec-compatible) in request.params,
          or a nested dict[str, Any] under request.params["spec"].
        - Supports template mode: {"template": "...", "output_dir": "...", ...}
        """
        if "spec" in request.params:
            if not isinstance(request.params.get("spec"), dict):
                return ForgeResponse(
                    success=False,
                    capability=request.capability.value,
                    error="spec must be an object",
                    error_code="invalid_spec",
                )
            payload = request.params["spec"]
        else:
            payload = request.params
        if not isinstance(payload, dict):
            return ForgeResponse(
                success=False,
                capability=request.capability.value,
                error="params must be an object",
                error_code="invalid_params",
            )

        try:
            from kagami.forge.creator_api import generate_genesis_video

            data = await generate_genesis_video(payload)
            return ForgeResponse(
                success=True,
                capability=request.capability.value,
                data=data,
            )
        except ModuleNotAvailableError as e:
            # Surface as standard module_unavailable error for clients.
            return ForgeResponse(
                success=False,
                capability=request.capability.value,
                error=str(e),
                error_code="module_unavailable",
            )
        except Exception as e:
            return ForgeResponse(
                success=False,
                capability=request.capability.value,
                error=str(e),
                error_code="genesis_video_failed",
            )

    @staticmethod
    def _requires_matrix(capability: ForgeOperation) -> bool:
        """Return True if this capability requires ForgeMatrix initialization."""
        return capability in (
            ForgeOperation.CHARACTER_GENERATION,
            ForgeOperation.IMAGE_TO_CHARACTER,
        )

    # --- Helper Methods ---

    def _error_response(
        self,
        request: ForgeRequest,
        error: str,
        error_code: str,
        duration: float,
    ) -> ForgeResponse:
        """Create standardized error response."""
        # Handle both enum and string capability values
        capability_str = (
            request.capability.value
            if hasattr(request.capability, "value")
            else str(request.capability)
        )
        return ForgeResponse(
            success=False,
            capability=capability_str,
            error=error,
            error_code=error_code,
            duration_ms=int(duration * 1000),
            correlation_id=request.correlation_id,
        )

    def _record_error(self, capability: ForgeOperation | str, error: Exception) -> None:
        """Record error metrics."""
        # Handle both enum and string capability values
        capability_str = capability.value if hasattr(capability, "value") else str(capability)
        try:
            API_ERRORS.labels(
                endpoint=f"forge.{capability_str}",
                error_type=type(error).__name__,
            ).inc()
        except Exception:
            logger.debug("Failed to record error metric for %s", capability_str, exc_info=True)

    # --- Convenience Methods ---

    async def generate_character(
        self,
        concept: str,
        *,
        quality_mode: str = "preview",
        export_formats: list[str] | None = None,
        personality_brief: str | None = None,
        backstory_brief: str | None = None,
        correlation_id: str | None = None,
    ) -> ForgeResponse:
        """Convenience method for character generation.

        Args:
            concept: Text description of character
            quality_mode: preview, draft, or final
            export_formats: List of export formats (fbx, gltf, etc.)
            personality_brief: Optional personality description
            backstory_brief: Optional backstory
            correlation_id: Optional correlation ID for tracing

        Returns:
            ForgeResponse with generated character data
        """
        request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={
                "concept": concept,
                "personality_brief": personality_brief,
                "backstory_brief": backstory_brief,
            },
            quality_mode=quality_mode,
            export_formats=export_formats or [],
            correlation_id=correlation_id,
        )
        return await self.execute(request)

    async def generate_animation(  # type: ignore[no-untyped-def]
        self,
        animation_type: str,
        *,
        duration: float = 10.0,
        correlation_id: str | None = None,
        **kwargs,
    ) -> ForgeResponse:
        """Convenience method for animation generation.

        Args:
            animation_type: Type of animation (blinks, idle, motion, etc.)
            duration: Animation duration in seconds
            correlation_id: Optional correlation ID for tracing
            **kwargs: Additional animation-specific parameters

        Returns:
            ForgeResponse with animation data
        """
        # Determine capability based on animation type
        if animation_type in ("blinks", "expressions"):
            capability = ForgeOperation.ANIMATION_FACIAL
        elif animation_type in ("idle", "gesture"):
            capability = ForgeOperation.ANIMATION_GESTURE
        else:
            capability = ForgeOperation.ANIMATION_MOTION

        request = ForgeRequest(
            capability=capability,
            params={"type": animation_type, "duration": duration, **kwargs},
            correlation_id=correlation_id,
        )
        return await self.execute(request)


# --- Singleton Access ---

_FORGE_SERVICE: ForgeService | None = None


def get_forge_service() -> ForgeService:
    """Get or create the global ForgeService instance."""
    global _FORGE_SERVICE
    if _FORGE_SERVICE is None:
        _FORGE_SERVICE = ForgeService()
    return _FORGE_SERVICE


__all__ = [
    "ForgeOperation",
    "ForgeRequest",
    "ForgeResponse",
    "ForgeService",
    "get_forge_service",
]
