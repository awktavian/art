import logging
import time
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from kagami.core.events import get_unified_bus
from kagami.core.learning_integration import get_learning_integration
from kagami.core.safety import enforce_tier1
from kagami.core.schemas.schemas.validation import ARImageRequest, ARPositionRequest
from kagami_observability.metrics import AR_ACK_LATENCY_MS, AR_FRAMES

from kagami_api.rbac import Permission, require_permission

logger = logging.getLogger(__name__)
from kagami.ar.core.ar_system import ARMode, KagamiARSystem

_AR_AVAILABLE = True


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/ar", tags=["ar"])

    # AR system instance managed within router closure
    _ar_system_instance: KagamiARSystem | None = None

    async def get_ar_system_async() -> KagamiARSystem:
        """Dependency injection provider for AR system instance.

        Returns initialized AR system instance, creating it if needed.
        Uses closure-scoped variable instead of global singleton.
        """
        nonlocal _ar_system_instance

        if _ar_system_instance is None:
            # Try to get from ar_manager first
            try:
                from kagami.ar.integration import ar_manager

                if getattr(ar_manager, "ar_system", None) is not None:
                    _ar_system_instance = ar_manager.ar_system
                    logger.info("AR system acquired from ar_manager")
            except Exception as e:
                logger.warning(f"Could not acquire AR system from ar_manager: {e}")

            # Fallback to creating new instance
            if _ar_system_instance is None:
                _ar_system_instance = KagamiARSystem(ARMode.DESKTOP)
                logger.info("Created new AR system instance in DESKTOP mode")

        # Ensure initialization
        if not getattr(_ar_system_instance, "is_initialized", False):
            try:
                await _ar_system_instance.initialize()
                logger.info("AR system initialized successfully")
            except Exception as e:
                logger.error(f"AR system initialization error: {e}")
                raise HTTPException(status_code=503, detail="AR system failed to initialize") from e

        return _ar_system_instance

    @router.post("/summon", dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))])  # type: ignore[func-returns-value]
    @enforce_tier1("rate_limit")
    async def summon_mascot(
        request: ARPositionRequest, ar: KagamiARSystem = Depends(get_ar_system_async)
    ) -> dict[str, Any]:
        """Summon an AR mascot at the specified position."""
        mascot_name = request.mascot
        position = request.position
        context: dict[str, Any] = {}

        # Check if mascot is already active
        if mascot_name in ar.active_mascots:
            raise HTTPException(status_code=409, detail=f"{mascot_name} already active")

        success = await ar.summon_mascot(mascot_name, position)
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to summon {mascot_name}")

        # Log observation
        get_learning_integration().observe(
            f"{mascot_name.lower()}_app",
            "ar_summon",
            {
                "context": context,
                "position": position,
                "scene_objects": len(context.get("objects", [])),
            },
            {"ar_mode": ar.mode.value},
        )

        # Publish event (log but don't fail on error)
        try:
            bus = get_unified_bus()
            await bus.publish_with_trace(  # type: ignore[attr-defined]
                topic="intent.execute",
                event={
                    "type": "intent",
                    "topic": "intent.execute",
                    "source": "ar",
                    "action": "EXECUTE",
                    "target": "ar.summon",
                    "metadata": {"mascot": mascot_name, "position": position},
                },
                correlation_id=None,
                source="ar",
            )
        except Exception as e:
            logger.warning(f"Failed to publish ar.summon event: {e}")

        return {
            "success": True,
            "mascot": mascot_name,
            "message": f"{mascot_name} summoned successfully",
        }

    @router.post("/dismiss", dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))])  # type: ignore[func-returns-value]
    @enforce_tier1("rate_limit")
    async def dismiss_mascot(
        request: ARPositionRequest, ar: KagamiARSystem = Depends(get_ar_system_async)
    ) -> dict[str, Any]:
        """Dismiss an active AR mascot from the scene."""
        mascot_name = request.mascot

        # Check if mascot is active
        if mascot_name not in ar.active_mascots:
            raise HTTPException(status_code=404, detail=f"{mascot_name} not active")

        ok = await ar.dismiss_mascot(mascot_name)
        if not ok:
            raise HTTPException(status_code=500, detail=f"Failed to dismiss {mascot_name}")

        # Publish event (log but don't fail on error)
        try:
            bus = get_unified_bus()
            await bus.publish_with_trace(  # type: ignore[attr-defined]
                topic="intent.execute",
                event={
                    "type": "intent",
                    "topic": "intent.execute",
                    "source": "ar",
                    "action": "EXECUTE",
                    "target": "ar.dismiss",
                    "metadata": {"mascot": mascot_name},
                },
                correlation_id=None,
                source="ar",
            )
        except Exception as e:
            logger.warning(f"Failed to publish ar.dismiss event: {e}")

        return {"success": True, "mascot": mascot_name, "message": f"{mascot_name} dismissed"}

    @router.post("/analyze", dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))])  # type: ignore[func-returns-value]
    @enforce_tier1("process")
    async def analyze_scene(
        request: ARImageRequest, ar: KagamiARSystem = Depends(get_ar_system_async)
    ) -> dict[str, Any]:
        """
        Enhanced scene analysis with scene graph generation

        Accepts either:
        - image: base64 encoded image data
        - scene: legacy object list for backward compatibility
        """
        image_data = request.image_data

        if not image_data:
            try:
                AR_FRAMES.labels("bad_request").inc()
            except Exception as e:
                logger.debug(f"Failed to increment AR_FRAMES metric: {e}")
            raise HTTPException(status_code=400, detail="image_data is required")

        try:
            context: dict[str, Any] = {}
            t0 = time.perf_counter()
            analysis = await ar.analyze_scene(image_data, context)

            # Record metrics (log but don't fail on error)
            try:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                AR_ACK_LATENCY_MS.observe(max(0.0, float(elapsed_ms)))
                AR_FRAMES.labels("success" if analysis.get("success") else "error").inc()
            except Exception as e:
                logger.debug(f"Failed to record AR metrics: {e}")

            return cast(dict[str, Any], analysis)  # type: ignore[redundant-cast]

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Scene analysis failed: {e}")
            return {"success": False, "error": str(e), "objects_detected": 0}

    _DEPTH_MODEL = None
    _DEPTH_TRANSFORM = None
    _DEPTH_DEVICE = None

    class JoinSpaceRequest(ARImageRequest):
        space_id: str
        visibility: str | None = None

    class LeaveSpaceRequest(ARImageRequest):
        space_id: str

    return router
