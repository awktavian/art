from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from kagami_api.rbac import Permission, require_permission
from kagami_api.routes.user.auth import get_current_user
from kagami_api.security import Principal

get_reconnection_manager: Any | None = None
ADVANCED_AVAILABLE = False

try:
    from kagami.core.rooms.reconnection import get_reconnection_manager as _get_reconnection_manager

    get_reconnection_manager = _get_reconnection_manager
    ADVANCED_AVAILABLE = True
except ImportError:
    pass


def _validate_client_ownership(client_id: str, user: Principal) -> None:
    """Validate that client_id belongs to the authenticated user.

    Security: Prevents session hijacking by ensuring users can only reconnect
    to their own client sessions.

    Args:
        client_id: The client ID from the request payload
        user: The authenticated principal

    Raises:
        HTTPException: 403 if client_id does not belong to the user
    """
    # Client ID must either:
    # 1. Match the user's subject (username) exactly
    # 2. Match the user's stable user_id (UUID) exactly
    # 3. Be prefixed with the user's identifier (for multi-device: "user123:device1")
    user_identifiers = {user.sub}
    if user.user_id:
        user_identifiers.add(user.user_id)

    # Direct match
    if client_id in user_identifiers:
        return

    # Prefix match (multi-device pattern: "user_id:device_id" or "username:device_id")
    for identifier in user_identifiers:
        if client_id.startswith(f"{identifier}:"):
            return

    raise HTTPException(
        status_code=403,
        detail="Client ID does not belong to authenticated user",
    )


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(tags=["rooms"])

    @router.post("/reconnect", dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))])  # type: ignore[func-returns-value]
    async def handle_reconnection(
        payload: dict[str, Any],
        user: Principal = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Handle client reconnection with state catchup."""
        if not ADVANCED_AVAILABLE or not get_reconnection_manager:
            raise HTTPException(501, detail="Reconnection manager not available")
        room_id = str(payload.get("room_id", "")).strip()
        client_id = str(payload.get("client_id", "")).strip()
        last_ack_seq = int(payload.get("last_ack_seq", 0))
        if not room_id or not client_id:
            raise HTTPException(400, detail="room_id and client_id required")

        # Security: Validate client_id ownership before processing
        _validate_client_ownership(client_id, user)

        manager = get_reconnection_manager()
        result = await manager.handle_reconnection(room_id, client_id, last_ack_seq)
        return result.to_dict()  # type: ignore[no-any-return]

    @router.post(
        "/ops/apply",
        dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))],  # type: ignore[func-returns-value]
    )
    async def apply_room_ops(
        payload: dict[str, Any],
        user: Principal = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Apply CRDT room operations via HTTP.

        Payload:
          {
            "room_id": "room-123",
            "client_id": "user-xyz",   # optional, defaults to authenticated user's subject
            "ops": [ {type, path, value, ...}, ... ],
            "include_snapshot": false
          }
        """
        room_id = str(payload.get("room_id", "")).strip()
        if not room_id:
            raise HTTPException(status_code=400, detail="room_id required")
        ops = payload.get("ops") or payload.get("operations") or []
        if not isinstance(ops, list) or not ops:
            raise HTTPException(status_code=400, detail="ops required")
        include_snapshot = bool(payload.get("include_snapshot", False))

        # Security: If client_id is provided, validate ownership; otherwise use authenticated user
        provided_client_id = str(payload.get("client_id", "")).strip()
        if provided_client_id:
            _validate_client_ownership(provided_client_id, user)
            client_id = provided_client_id
        else:
            # Default to authenticated user's identifier (prefer user_id if available)
            client_id = user.user_id or user.sub

        from kagami_api.rooms.state_service import apply_crdt_operations

        snap, applied = await apply_crdt_operations(room_id, ops, default_client_id=client_id)
        resp: dict[str, Any] = {
            "success": True,
            "room_id": room_id,
            "current_seq": getattr(snap, "seq", 0),
            "applied": [{"seq": x.get("seq")} for x in applied],
        }
        if include_snapshot:
            resp["state"] = getattr(snap, "state", {})
        return resp

    return router
