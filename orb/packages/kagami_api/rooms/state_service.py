from __future__ import annotations

"""
Proxy for kagami.core.rooms.state_service to maintain API compatibility.
Moved logic to Core to break Core->API circular dependency.
"""

from kagami.core.rooms.state_service import (
    RoomSnapshot,
    append_delta,
    apply_crdt_operations,
    get_all_cursors_3d,
    get_anchors,
    get_crdt_meta,
    get_current_seq,
    get_next_seq,
    get_physics_entities,
    get_recent_deltas,
    get_snapshot,
    is_room_encryption_enabled,
    list_members,
    persist_crdt_meta,
    persist_snapshot,
    remove_member,
    set_room_encryption_enabled,
    update_anchor,
    update_cursor_3d,
    update_physics_entities,
    upsert_member,
)

__all__ = [
    "RoomSnapshot",
    "append_delta",
    "apply_crdt_operations",
    "get_all_cursors_3d",
    "get_anchors",
    "get_crdt_meta",
    "get_current_seq",
    "get_next_seq",
    "get_physics_entities",
    "get_recent_deltas",
    "get_snapshot",
    "is_room_encryption_enabled",
    "list_members",
    "persist_crdt_meta",
    "persist_snapshot",
    "remove_member",
    "set_room_encryption_enabled",
    "update_anchor",
    "update_cursor_3d",
    "update_physics_entities",
    "upsert_member",
]
