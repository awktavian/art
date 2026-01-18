"""Hub Management Routes.

OTA updates, fleet management, hub provisioning, CRDT sync, and audio streaming.

Colony: Nexus (e₄) → Fleet coordination
"""

from fastapi import APIRouter

from .audio_stream import router as audio_router
from .crdt import router as crdt_router
from .fleet import router as fleet_router
from .ota import router as ota_router

router = APIRouter(prefix="/hub", tags=["hub"])

router.include_router(ota_router)
router.include_router(fleet_router)
router.include_router(crdt_router)
router.include_router(audio_router)

__all__ = ["router"]
