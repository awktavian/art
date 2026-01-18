from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from kagami_api.rbac import Permission, require_permission


# NOTE: Models MUST be at module level for Pydantic OpenAPI schema generation
# Defining them inside get_router() causes ForwardRef resolution failures
class EnableRoomEncryptionRequest(BaseModel):
    """Request to enable room encryption."""

    room_id: str
    confirm: bool = False


class EnableRoomEncryptionResponse(BaseModel):
    """Response after enabling room encryption."""

    success: bool
    room_id: str
    encryption: dict[str, Any]
    message: str | None = None


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(tags=["rooms"])

    @router.post(
        "/encryption/enable",
        dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))],  # type: ignore[func-returns-value]
    )
    async def enable_room_encryption(
        body: EnableRoomEncryptionRequest,
    ) -> EnableRoomEncryptionResponse:
        """Irreversibly enable encryption-at-rest for a room.

        Behavior:
        - Latches encryption ON (cannot be disabled)
        - Re-persists snapshot immediately so the room becomes encrypted-at-rest now
        - Publishes a HAL-visible event on the unified bus
        - Best-effort notifies Socket.IO room members
        """

        room_id = str(body.room_id or "").strip()
        if not room_id:
            raise HTTPException(status_code=400, detail="room_id required")
        if not body.confirm:
            raise HTTPException(
                status_code=400,
                detail="confirmation required (confirm=true). Enabling encryption is irreversible.",
            )

        from kagami_api.rooms.state_service import (
            get_crdt_meta,
            get_snapshot,
            persist_crdt_meta,
            persist_snapshot,
            set_room_encryption_enabled,
        )

        # 1) Latch room encryption (validates provider)
        await set_room_encryption_enabled(room_id, True)

        # 2) Re-persist snapshot so it becomes encrypted-at-rest immediately
        snap = await get_snapshot(room_id)
        await persist_snapshot(room_id, dict(snap.state or {}))
        # 2b) Re-persist CRDT metadata so it becomes encrypted-at-rest immediately
        try:
            meta = await get_crdt_meta(room_id)
            if meta:
                await persist_crdt_meta(room_id, dict(meta))
        except Exception:
            pass

        # 3) Publish HAL-visible control event (bridged to AGUI sessions)
        try:
            from kagami.core.events import get_unified_bus

            bus = get_unified_bus()
            await bus.publish(
                "hal.display.control",
                {
                    "type": "hal.display.control",
                    "command": "room_encryption_enabled",
                    "room_id": room_id,
                    "enabled": True,
                    "immutable": True,
                    "timestamp": time.time(),
                },
            )
        except Exception:
            pass

        # Optional: physical confirmation if haptics are available
        try:
            from kagami_hal.adapters.common.haptic import get_haptic_controller_async

            h = await get_haptic_controller_async()
            await h.notification()
        except Exception:
            pass

        # 4) Best-effort notify Socket.IO room members
        try:
            from kagami_api.socketio_server import get_socketio_server

            sio = get_socketio_server()
            if sio is not None:
                await sio.emit(
                    "room.encryption.enabled",
                    {
                        "room_id": room_id,
                        "enabled": True,
                        "immutable": True,
                        "timestamp": time.time(),
                    },
                    room=room_id,
                    namespace="/",
                )
        except Exception:
            pass

        return EnableRoomEncryptionResponse(
            success=True,
            room_id=room_id,
            encryption={"enabled": True, "immutable": True},
            message="Room encryption enabled (irreversible)",
        )

    return router
