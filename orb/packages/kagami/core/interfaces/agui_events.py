from __future__ import annotations

"""AGUI event helpers used by core subsystems.

Why this exists:
- `kagami.core.spatial.unified_scene_graph.UnifiedSceneGraph` wants to push scene graph
  updates to any registered UI sessions.
- Core cannot depend on `kagami_api.*` without reintroducing core↔api cycles.

So this module provides a tiny, duck-typed emitter that works with:
- FastAPI/Starlette WebSocket-like objects (`send_json`)
- Socket.IO-like objects (`emit`)
- AGUIProtocolAdapter-like objects (`transport.send_event` is too high-level; we treat
  the adapter as a WebSocket-ish session if it exposes `send_event`)

All operations are best-effort. Callers should treat failures as non-fatal.
"""

import json
from typing import Any


async def emit_scene_graph_update(session: Any, entities: list[Any], relations: list[Any]) -> None:
    """Emit a scene graph update to a UI session.

    The payload is intentionally simple JSON so multiple frontends can consume it.

    Args:
        session: A UI session object (duck-typed).
        entities: List of SpatialEntity-like objects.
        relations: List of SpatialRelation-like objects.
    """

    def _entity_to_dict(e: Any) -> dict[str, Any]:
        # SpatialEntity is a dataclass; fall back to attribute reads.
        return {
            "entity_id": getattr(e, "entity_id", None),
            "entity_type": getattr(e, "entity_type", None),
            "position": list(getattr(e, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)),
            "orientation": list(
                getattr(e, "orientation", (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
            ),
            "velocity": list(getattr(e, "velocity", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)),
            "labels": list(getattr(e, "labels", []) or []),
            "properties": dict(getattr(e, "properties", {}) or {}),
            "source": getattr(e, "source", "unknown"),
            "confidence": float(getattr(e, "confidence", 1.0) or 0.0),
            "last_updated": float(getattr(e, "last_updated", 0.0) or 0.0),
        }

    def _relation_to_dict(r: Any) -> dict[str, Any]:
        return {
            "subject_id": getattr(r, "subject_id", None),
            "predicate": getattr(r, "predicate", None),
            "object_id": getattr(r, "object_id", None),
            "confidence": float(getattr(r, "confidence", 0.0) or 0.0),
            "metadata": dict(getattr(r, "metadata", {}) or {}),
        }

    payload = {
        "type": "scene_graph.update",
        "entities": [_entity_to_dict(e) for e in (entities or [])],
        "relations": [_relation_to_dict(r) for r in (relations or [])],
    }

    # Prefer WebSocket-like `send_json`.
    try:
        send_json = getattr(session, "send_json", None)
        if callable(send_json):
            await send_json(payload)
            return
    except Exception:
        pass

    # Socket.IO-like session: `emit(event, data, room=...)`.
    try:
        emit = getattr(session, "emit", None)
        if callable(emit):
            # For Socket.IO we emit an event name + payload.
            await emit("scene_graph.update", payload)
            return
    except Exception:
        pass

    # AGUITransport-like: `send_event(AGUIEvent)` or generic `send_event(dict[str, Any])`.
    try:
        send_event = getattr(session, "send_event", None)
        if callable(send_event):
            try:
                # If it expects an AGUIEvent object, it will likely fail; fall back to dict[str, Any].
                await send_event(payload)
            except TypeError:
                await send_event(payload)
            return
    except Exception:
        pass

    # Last resort: raw `send` for text transports.
    try:
        send = getattr(session, "send", None)
        if callable(send):
            await send(json.dumps(payload))
            return
    except Exception:
        pass


__all__ = ["emit_scene_graph_update"]
