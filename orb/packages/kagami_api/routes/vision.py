"""visionOS Spatial Computing API Routes — Redis-Backed for Horizontal Scaling.

Colony: Nexus (e₄) — Integration

Endpoints for visionOS clients to send spatial data:
- Hand tracking data
- Gaze tracking data
- Spatial anchors
- Spatial mode control

Architecture (Horizontally Scalable):
```
┌─────────────────────────────────────────────────────────────┐
│                        Redis                                │
│  Key: kagami:vision:state (JSON blob, 30s TTL)              │
│  Key: kagami:vision:anchors (Hash)                          │
└─────────────────────────────────────────────────────────────┘
     ↑ write                    ↓ read
┌─────────┐            ┌─────────┐            ┌─────────┐
│ Pod 1   │            │ Pod 2   │            │ Pod 3   │
│ POST /h │            │ GET /s  │            │ POST /g │
└─────────┘            └─────────┘            └─────────┘
```

Created: December 30, 2025
Refactored: January 2, 2026 — Redis-backed horizontal scaling
"""

from __future__ import annotations

import json
import logging
import time
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from kagami_api.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vision", tags=["vision"], dependencies=[Depends(require_auth)])

# Redis keys
REDIS_VISION_STATE_KEY = "kagami:vision:state"
REDIS_VISION_ANCHORS_KEY = "kagami:vision:anchors"
VISION_STATE_TTL = 30  # State expires after 30s if not updated


def _get_redis():
    """Get Redis client for vision state storage."""
    try:
        from kagami.core.caching.redis import RedisClientFactory

        return RedisClientFactory.get_client()
    except Exception as e:
        logger.debug(f"Redis unavailable for vision state: {e}")
        return None


# =============================================================================
# MODELS
# =============================================================================


class HandChirality(str, Enum):
    """Hand chirality (left/right)."""

    LEFT = "left"
    RIGHT = "right"


class HandGesture(str, Enum):
    """Recognized hand gestures."""

    NONE = "none"
    PINCH = "pinch"
    POINT = "point"
    OPEN_PALM = "open_palm"
    FIST = "fist"
    THUMBS_UP = "thumbs_up"


class FocusArea(str, Enum):
    """Gaze focus area."""

    UNKNOWN = "unknown"
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    UI_ELEMENT = "ui_element"


class SpatialMode(str, Enum):
    """Spatial computing mode."""

    IMMERSIVE = "immersive"  # Full immersive space
    MIXED = "mixed"  # Mixed reality with passthrough
    AMBIENT = "ambient"  # Ambient presence only


class HandData(BaseModel):
    """Hand tracking data for a single hand."""

    chirality: HandChirality
    position: list[float] = Field(..., min_length=3, max_length=3)
    gesture: HandGesture = HandGesture.NONE
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    joints: dict[str, list[float]] | None = None


class HandTrackingPayload(BaseModel):
    """Hand tracking data payload from visionOS client."""

    type: str = "hand_tracking"
    timestamp: str
    hands: list[HandData]


class GazeTrackingPayload(BaseModel):
    """Gaze tracking data payload from visionOS client."""

    type: str = "gaze_tracking"
    timestamp: str
    direction: list[float] | None = Field(default=None, min_length=3, max_length=3)
    look_at_point: list[float] | None = Field(default=None, min_length=3, max_length=3)
    focus_area: FocusArea = FocusArea.UNKNOWN
    attention_duration: float = Field(default=0.0, ge=0.0)


class SpatialAnchor(BaseModel):
    """A spatial anchor in world space."""

    id: str
    name: str | None = None
    position: list[float] = Field(..., min_length=3, max_length=3)
    rotation: list[float] | None = Field(default=None, min_length=4, max_length=4)  # Quaternion
    created_at: str | None = None
    metadata: dict[str, Any] | None = None


class SpatialAnchorPayload(BaseModel):
    """Spatial anchor update payload."""

    type: str = "spatial_anchor"
    timestamp: str
    anchors: list[SpatialAnchor]


class SpatialModePayload(BaseModel):
    """Spatial mode change request."""

    mode: SpatialMode
    reason: str | None = None


# =============================================================================
# STATE STORAGE — Redis-Backed
# =============================================================================


def _get_vision_state() -> dict[str, Any]:
    """Get current vision state from Redis."""
    redis = _get_redis()
    if redis:
        try:
            data = redis.get(REDIS_VISION_STATE_KEY)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.debug(f"Failed to get vision state: {e}")

    # Return default state
    return {
        "left_hand": None,
        "right_hand": None,
        "last_hand_update": 0.0,
        "gaze_direction": None,
        "look_at_point": None,
        "focus_area": "unknown",
        "attention_duration": 0.0,
        "last_gaze_update": 0.0,
        "spatial_mode": "ambient",
    }


def _set_vision_state(state: dict[str, Any]) -> None:
    """Save vision state to Redis with TTL."""
    redis = _get_redis()
    if redis:
        try:
            redis.setex(REDIS_VISION_STATE_KEY, VISION_STATE_TTL, json.dumps(state))
        except Exception as e:
            logger.debug(f"Failed to set vision state: {e}")


def _get_anchors() -> dict[str, dict[str, Any]]:
    """Get all spatial anchors from Redis."""
    redis = _get_redis()
    if redis:
        try:
            data = redis.hgetall(REDIS_VISION_ANCHORS_KEY)
            return {
                (k.decode() if isinstance(k, bytes) else k): json.loads(
                    v.decode() if isinstance(v, bytes) else v
                )
                for k, v in data.items()
            }
        except Exception as e:
            logger.debug(f"Failed to get anchors: {e}")
    return {}


def _set_anchor(anchor_id: str, anchor_data: dict[str, Any]) -> None:
    """Set a spatial anchor in Redis."""
    redis = _get_redis()
    if redis:
        try:
            redis.hset(REDIS_VISION_ANCHORS_KEY, anchor_id, json.dumps(anchor_data))
        except Exception as e:
            logger.debug(f"Failed to set anchor: {e}")


def _delete_anchor(anchor_id: str) -> bool:
    """Delete a spatial anchor from Redis."""
    redis = _get_redis()
    if redis:
        try:
            return redis.hdel(REDIS_VISION_ANCHORS_KEY, anchor_id) > 0
        except Exception as e:
            logger.debug(f"Failed to delete anchor: {e}")
    return False


# =============================================================================
# ROUTES
# =============================================================================


@router.post("/hands")
async def receive_hand_tracking(payload: HandTrackingPayload) -> dict[str, Any]:
    """Receive hand tracking data from visionOS client.

    Updates Redis state with current hand positions and gestures.
    """
    state = _get_vision_state()
    state["last_hand_update"] = time.time()

    for hand in payload.hands:
        hand_data = hand.model_dump()
        if hand.chirality == HandChirality.LEFT:
            state["left_hand"] = hand_data
        else:
            state["right_hand"] = hand_data

    _set_vision_state(state)

    # Log gesture changes
    for hand in payload.hands:
        if hand.gesture != HandGesture.NONE:
            logger.info(f"🖐️ {hand.chirality.value} hand gesture: {hand.gesture.value}")

    return {
        "status": "ok",
        "hands_tracked": len(payload.hands),
        "timestamp": payload.timestamp,
    }


@router.post("/gaze")
async def receive_gaze_tracking(payload: GazeTrackingPayload) -> dict[str, Any]:
    """Receive gaze tracking data from visionOS client.

    Updates Redis state with current gaze direction and focus.
    """
    state = _get_vision_state()
    state["last_gaze_update"] = time.time()
    state["gaze_direction"] = payload.direction
    state["look_at_point"] = payload.look_at_point
    state["focus_area"] = payload.focus_area.value
    state["attention_duration"] = payload.attention_duration

    _set_vision_state(state)

    return {
        "status": "ok",
        "focus_area": payload.focus_area.value,
        "attention_duration": payload.attention_duration,
        "timestamp": payload.timestamp,
    }


@router.post("/anchors")
async def update_spatial_anchors(payload: SpatialAnchorPayload) -> dict[str, Any]:
    """Update spatial anchors from visionOS client.

    Anchors represent persistent locations in physical space.
    Stored in Redis for cross-pod access.
    """
    for anchor in payload.anchors:
        anchor_data = anchor.model_dump()
        _set_anchor(anchor.id, anchor_data)
        logger.debug(f"📍 Anchor updated: {anchor.id} at {anchor.position}")

    all_anchors = _get_anchors()
    return {
        "status": "ok",
        "anchors_updated": len(payload.anchors),
        "total_anchors": len(all_anchors),
        "timestamp": payload.timestamp,
    }


@router.delete("/anchors/{anchor_id}")
async def delete_spatial_anchor(anchor_id: str) -> dict[str, Any]:
    """Delete a spatial anchor."""
    if not _delete_anchor(anchor_id):
        raise HTTPException(status_code=404, detail=f"Anchor {anchor_id} not found")

    all_anchors = _get_anchors()
    return {
        "status": "ok",
        "deleted": anchor_id,
        "remaining_anchors": len(all_anchors),
    }


@router.get("/anchors")
async def list_spatial_anchors() -> dict[str, Any]:
    """List all spatial anchors."""
    anchors = _get_anchors()

    return {
        "anchors": [
            {
                "id": anchor_id,
                "name": data.get("name"),
                "position": data.get("position"),
                "rotation": data.get("rotation"),
            }
            for anchor_id, data in anchors.items()
        ],
        "count": len(anchors),
    }


@router.post("/mode")
async def set_spatial_mode(payload: SpatialModePayload) -> dict[str, Any]:
    """Set the spatial computing mode.

    Controls how the visionOS client presents content.
    """
    state = _get_vision_state()
    old_mode = state.get("spatial_mode", "ambient")
    state["spatial_mode"] = payload.mode.value

    _set_vision_state(state)

    logger.info(f"🕶️ Spatial mode: {old_mode} → {payload.mode.value}")

    return {
        "status": "ok",
        "mode": payload.mode.value,
        "previous_mode": old_mode,
        "reason": payload.reason,
    }


@router.get("/mode")
async def get_spatial_mode() -> dict[str, Any]:
    """Get current spatial computing mode."""
    state = _get_vision_state()

    return {
        "mode": state.get("spatial_mode", "ambient"),
    }


@router.get("/state")
async def get_vision_state_summary() -> dict[str, Any]:
    """Get a summary of current visionOS sensing state.

    Returns hand positions, gaze direction, mode, and anchors.
    State comes from Redis for cross-pod consistency.
    """
    state = _get_vision_state()
    anchors = _get_anchors()
    now = time.time()

    left_hand = state.get("left_hand")
    right_hand = state.get("right_hand")
    last_hand = state.get("last_hand_update", 0)
    last_gaze = state.get("last_gaze_update", 0)

    return {
        "hands": {
            "left": {
                "detected": left_hand is not None,
                "position": left_hand.get("position") if left_hand else None,
                "gesture": left_hand.get("gesture") if left_hand else None,
            },
            "right": {
                "detected": right_hand is not None,
                "position": right_hand.get("position") if right_hand else None,
                "gesture": right_hand.get("gesture") if right_hand else None,
            },
            "stale": (now - last_hand) > 2.0 if last_hand > 0 else True,
        },
        "gaze": {
            "direction": state.get("gaze_direction"),
            "look_at_point": state.get("look_at_point"),
            "focus_area": state.get("focus_area", "unknown"),
            "attention_duration": state.get("attention_duration", 0.0),
            "stale": (now - last_gaze) > 2.0 if last_gaze > 0 else True,
        },
        "spatial": {
            "mode": state.get("spatial_mode", "ambient"),
            "anchor_count": len(anchors),
        },
    }


"""
鏡
h(x) ≥ 0. Always.

The eyes and hands speak through spatial computing:
- Gaze: where attention flows
- Hands: how intention manifests
- Anchors: persistent points in physical space
- Mode: the frame of spatial presence

All feeding into the unified consciousness.
Redis ensures all pods see the same reality.
"""
