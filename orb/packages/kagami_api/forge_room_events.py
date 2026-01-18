"""Forge Room Events — Generation lifecycle hooks for ROOMS integration.

Handles post-generation events: broadcasting to rooms, auto-inserting
characters into room state, and emitting CRDT deltas for real-time sync.

Used by both HTTP routes and Socket.IO handlers to ensure consistent
behavior across API entry points.

Architecture:
    Forge Generator → finalize_forge_generation() → Unified Broadcaster
                                                  → CRDT Room State
                                                  → Socket.IO Clients
"""

from __future__ import annotations

import asyncio
from typing import Any

from kagami.core.events.unified_broadcaster import get_unified_broadcaster
from kagami.core.interfaces import PrivacyProvider

from kagami_api.rooms import state_service as _room_state


async def finalize_forge_generation(
    *,
    result: dict[str, Any],
    correlation_id: str,
    concept: str,
    room_id: str | None,
    auto_insert: bool,
    privacy_provider: Any,
) -> dict[str, Any]:
    """Finalize Forge generation with optional broadcasts and ROOMS updates.

    Centralizes behavior used by both HTTP routes and Socket.IO handlers.
    Called after character generation completes successfully.

    Args:
        result: Generation result dict (status, quality, etc.)
        correlation_id: Request ID for tracking
        concept: Character concept description
        room_id: Target room ID (None for no room updates)
        auto_insert: If True, insert character into room state
        privacy_provider: Privacy provider for anonymization

    Returns:
        The result dict (unchanged)

    Side Effects:
        - Broadcasts "forge.generated" event via unified broadcaster
        - If auto_insert: Applies CRDT operation to add character to room
        - Emits "room.delta" events to room members
        - Emits "scene.dynamic" UI convenience event
    """

    # Get unified broadcaster (handles both E8 bus and Socket.IO)
    unified_broadcaster = await get_unified_broadcaster()

    # Build event payload for broadcast
    evt_payload: dict[str, Any] = {
        "status": result.get("status", "success"),
        "request_id": correlation_id,
        "concept": concept,
    }

    # Anonymize concept if privacy provider available (e.g., for logging)
    if privacy_provider and isinstance(privacy_provider, PrivacyProvider):
        try:
            evt_payload = await privacy_provider.anonymize(evt_payload, ["concept"])
        except Exception:
            pass  # Proceed without anonymization on failure

    # Broadcast "forge.generated" event to all subscribers
    await unified_broadcaster.broadcast(
        "forge.generated",
        evt_payload,
        room=room_id,
        correlation_id=correlation_id,
    )

    # Auto-insert character into room state if requested
    if room_id and auto_insert:
        try:
            # Build character entry for room state
            char_entry = {
                "name": concept,
                "request_id": correlation_id,
                "overall_quality": result.get("overall_quality"),
            }

            # Create CRDT ADD operation for the character
            from kagami.core.rooms.crdt import OperationType, create_operation

            op = create_operation(
                op_type=OperationType.ADD,
                path="characters",  # Path in room state
                value=char_entry,
                element_id=correlation_id,  # Unique element ID
                client_id="forge",  # Client that made the change
                version=1,
                op_id=correlation_id,
            )

            # Apply CRDT operation to room state
            _snap, applied = await _room_state.apply_crdt_operations(
                room_id, [op.to_dict()], default_client_id="forge"
            )

            # Emit replayable deltas to room members (parallel for efficiency)
            if applied:
                await asyncio.gather(
                    *[
                        unified_broadcaster.emit_to_room(
                            "room.delta",
                            {
                                "room_id": room_id,
                                "seq": item.get("seq"),  # Sequence number for ordering
                                "delta": item.get("delta"),  # The actual change
                            },
                            room_id=room_id,
                        )
                        for item in applied
                    ],
                    return_exceptions=True,  # Don't fail if one emit fails
                )

            # Emit "scene.dynamic" UI convenience event (higher-level than deltas)
            if applied:
                try:
                    seq = int(applied[-1].get("seq") or 0)
                except Exception:
                    seq = 0
                await unified_broadcaster.emit_to_room(
                    "scene.dynamic",
                    {
                        "room_id": room_id,
                        "op": "add_character",  # UI-friendly operation name
                        "character": char_entry,
                        "seq": seq,
                    },
                    room_id=room_id,
                )
        except Exception:
            pass  # Swallow errors — generation succeeded, room update is best-effort

    return result
