from __future__ import annotations

"""World/Rooms API routes (modular structure).

Provides:
- GET /api/rooms - List active rooms
- POST /api/rooms/reconnect - Handle reconnection
- POST /api/rooms/session/start - Start world session
- Encryption and sync endpoints

Sub-modules (Dec 15, 2025 cleanup):
- encryption: Encryption endpoints
- sessions: World sessions
- sync: World synchronization
Note: anchors module removed as obsolete (no external usage detected)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from kagami_api.rbac import Permission, require_permission
from kagami_api.socketio_server import get_rooms_summary

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    # Lazy import sub-routers
    from . import encryption, sessions, sync

    router = APIRouter(prefix="/api/rooms", tags=["rooms"])

    # Define endpoints
    @router.get("", dependencies=[Depends(require_permission(Permission.SYSTEM_READ))])  # type: ignore[func-returns-value]
    async def list_rooms(
        request: Request,
        q: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> JSONResponse:
        """List active rooms with member counts.

        Args:
            q: Optional substring filter for room IDs.
            page: Page number (1-indexed).
            per_page: Number of items per page.

        Returns:
            JSON with rooms list. Returns 207 if partial failures occur.
        """
        query = (q or "").strip().lower()
        all_items: list[dict[str, Any]] = []
        partial_errors = 0
        sio_rooms = get_rooms_summary("/")

        for item in list(sio_rooms):
            try:
                rid = item.get("room_id")
                members_count = int(item.get("members") or 0)
                if query and str(rid).lower().find(query) < 0:
                    continue
                all_items.append(
                    {
                        "room_id": rid,
                        "members": members_count,
                        "tick": 0,
                        "locked": False,
                        "visibility": "public",
                        "geo": None,
                    }
                )
            except Exception as e:
                partial_errors += 1
                logger.warning(f"list_rooms: skipped room due to error: {e}")
                continue

        # Apply pagination
        total = len(all_items)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_items = all_items[start_idx:end_idx]
        has_more = end_idx < total

        resp_status = 200 if partial_errors == 0 else 207
        body: dict[str, Any] = {
            "rooms": paginated_items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "has_more": has_more,
        }
        if partial_errors:
            body["error"] = {
                "type": "partial",
                "skipped": partial_errors,
                "message": "Some rooms could not be listed",
            }
        return JSONResponse(body, status_code=resp_status)

    # Include sub-routers (Dec 15, 2025: removed anchors as obsolete, support both patterns)
    for module in [encryption, sessions, sync]:
        if hasattr(module, "get_router"):
            router.include_router(module.get_router())
        else:
            router.include_router(module.router)

    return router


# Re-export models for backward compatibility (explicit imports, Dec 15 2025 security fix)
from .models import (
    AddObjectRequest,
    AnchorUpsertRequest,
    ApplySessionRequest,
    ApplySessionResponse,
    AppManifestRequest,
    AugmentRequest,
    ComposeRequest,
    ComposeResponse,
    CreateWorldRequest,
    HoloportRequest,
    ListSpacesResponse,
    SessionStartRequest,
    SessionStartResponse,
    WorldExportRequest,
    WorldGenRequest,
    WorldGenResponse,
    WorldJobResult,
    WorldMotionRequest,
    WorldMotionResponse,
)

__all__ = [
    "AddObjectRequest",
    "AnchorUpsertRequest",
    "AppManifestRequest",
    "ApplySessionRequest",
    "ApplySessionResponse",
    "AugmentRequest",
    "ComposeRequest",
    "ComposeResponse",
    "CreateWorldRequest",
    "HoloportRequest",
    "ListSpacesResponse",
    "SessionStartRequest",
    "SessionStartResponse",
    "WorldExportRequest",
    "WorldGenRequest",
    "WorldGenResponse",
    "WorldJobResult",
    "WorldMotionRequest",
    "WorldMotionResponse",
    "get_router",
]
