"""Orb API Routes — Cross-Client State Synchronization.

This module provides REST and WebSocket endpoints for orb state
management and cross-client interaction events.

Endpoints:
    GET  /api/orb/state      - Get current orb state
    POST /api/orb/interaction - Report an orb interaction
    WS   /api/orb/stream     - Real-time state updates

Colony: Nexus (e₄) — API integration layer

Example:
    # Get current state
    GET /api/orb/state
    Response: {
        "active_colony": "forge",
        "activity": "responding",
        "safety_score": 0.85,
        "color": {"hex": "#FFB347", "name": "Forge Amber"}
    }

    # Report interaction
    POST /api/orb/interaction
    Body: {"client": "vision_pro", "action": "tap", "context": {...}}

Created: January 5, 2026
Author: Byzantine Consensus
License: MIT
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from kagami.core.orb import (
    OrbInteractionEvent,
    OrbState,
    OrbStateChangedEvent,
    create_orb_interaction,
    get_orb_state,
)
from kagami.core.orb.events import ClientType, InteractionAction
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orb", tags=["orb"])

# =============================================================================
# WebSocket Connection Manager
# =============================================================================


class OrbConnectionManager:
    """Manages WebSocket connections for orb state broadcasts.

    Maintains a set of active connections and broadcasts state
    updates and interaction events to all connected clients.
    """

    def __init__(self) -> None:
        """Initialize connection manager."""
        self.active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection.

        Args:
            websocket: New WebSocket connection
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"Orb WebSocket connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: WebSocket to remove
        """
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"Orb WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast_state(self, state: OrbState) -> None:
        """Broadcast orb state to all connected clients.

        Args:
            state: Current orb state to broadcast
        """
        message = {
            "type": "orb_state",
            **state.to_dict(),
        }
        await self._broadcast(message)

    async def broadcast_interaction(self, event: OrbInteractionEvent) -> None:
        """Broadcast interaction event to all connected clients.

        Args:
            event: Interaction event to broadcast
        """
        await self._broadcast(event.to_websocket_message())

    async def broadcast_state_changed(self, event: OrbStateChangedEvent) -> None:
        """Broadcast state changed event to all connected clients.

        Args:
            event: State changed event to broadcast
        """
        await self._broadcast(event.to_websocket_message())

    async def _broadcast(self, message: dict[str, Any]) -> int:
        """Broadcast message to all connections.

        Handles disconnected clients gracefully by removing them
        from the active connection pool.

        Args:
            message: JSON-serializable message

        Returns:
            Number of clients successfully notified
        """
        async with self._lock:
            disconnected: set[WebSocket] = set()
            success_count = 0
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                    success_count += 1
                except Exception as e:
                    logger.debug(f"Removing disconnected orb client: {e}")
                    disconnected.add(connection)
            if disconnected:
                self.active_connections -= disconnected
                logger.info(f"Removed {len(disconnected)} disconnected orb clients")
            return success_count


# Global connection manager
orb_manager = OrbConnectionManager()


# =============================================================================
# Request/Response Models
# =============================================================================


class OrbInteractionRequest(BaseModel):
    """Request body for orb interaction endpoint."""

    client: str = Field(
        ...,
        description="Client platform (vision_pro, hub, desktop, etc.)",
        examples=["vision_pro"],
    )
    action: str = Field(
        ...,
        description="Interaction type (tap, long_press, gaze_dwell, etc.)",
        examples=["tap"],
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (scene, room, time_of_day, etc.)",
        examples=[{"scene": "movie_mode", "room": "living_room"}],
    )


class OrbStateResponse(BaseModel):
    """Response body for orb state endpoint."""

    active_colony: str | None = Field(
        None,
        description="Currently active colony (or null for idle)",
    )
    activity: str = Field(
        "idle",
        description="Current activity state",
    )
    safety_score: float = Field(
        1.0,
        description="h(x) safety score (0.0-1.0)",
    )
    connection: str = Field(
        "connected",
        description="Connection state to API",
    )
    active_colonies: list[str] = Field(
        default_factory=list,
        description="All currently active colonies",
    )
    color: dict[str, Any] = Field(
        ...,
        description="Display color information",
    )
    timestamp: float = Field(
        ...,
        description="Unix timestamp of state update",
    )


class OrbInteractionResponse(BaseModel):
    """Response body for orb interaction endpoint."""

    success: bool = Field(True, description="Whether interaction was processed")
    event_id: str = Field(..., description="Unique event identifier")
    broadcast_count: int = Field(..., description="Number of clients notified")


# =============================================================================
# REST Endpoints
# =============================================================================


@router.get("/state", response_model=OrbStateResponse)
async def get_state() -> OrbStateResponse:
    """Get the current orb state.

    Returns the canonical orb state that all clients should display.
    Includes active colony, activity, safety score, and display color.

    Returns:
        Current orb state

    Example:
        >>> GET /api/orb/state
        {
            "active_colony": "forge",
            "activity": "responding",
            "safety_score": 0.85,
            "color": {"hex": "#FFB347", "name": "Forge Amber"}
        }
    """
    state = get_orb_state()
    return OrbStateResponse(
        active_colony=state.active_colony,
        activity=state.activity.value,
        safety_score=state.safety_score,
        connection=state.connection.value,
        active_colonies=state.active_colonies,
        color={
            "hex": state.color.hex,
            "rgb": state.color.rgb,
            "name": state.color.description,
        },
        timestamp=state.timestamp,
    )


@router.post("/interaction", response_model=OrbInteractionResponse)
async def report_interaction(request: OrbInteractionRequest) -> OrbInteractionResponse:
    """Report an orb interaction from a client.

    When a user interacts with the orb on any client (VisionOS tap,
    Hub voice wake, Desktop click), this endpoint broadcasts the
    interaction to all other clients.

    Args:
        request: Interaction details

    Returns:
        Confirmation with event ID and broadcast count

    Example:
        >>> POST /api/orb/interaction
        >>> {"client": "vision_pro", "action": "tap", "context": {"scene": "movie_mode"}}
        {"success": true, "event_id": "uuid...", "broadcast_count": 3}
    """
    try:
        client = ClientType(request.client)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid client type: {request.client}. "
            f"Valid types: {[c.value for c in ClientType]}",
        ) from e

    try:
        action = InteractionAction(request.action)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action type: {request.action}. "
            f"Valid types: {[a.value for a in InteractionAction]}",
        ) from e

    event = create_orb_interaction(
        client=client,
        action=action,
        context=request.context,
    )

    # Broadcast to all connected clients
    await orb_manager.broadcast_interaction(event)

    logger.info(
        f"Orb interaction: {event.client.value} → {event.action.value} "
        f"(broadcast to {len(orb_manager.active_connections)} clients)"
    )

    return OrbInteractionResponse(
        success=True,
        event_id=event.event_id,
        broadcast_count=len(orb_manager.active_connections),
    )


@router.get("/colors")
async def get_colony_colors() -> dict[str, Any]:
    """Get all colony colors.

    Returns the canonical color definitions for all colonies.
    Useful for client initialization and validation.

    Returns:
        Dictionary of colony colors

    Example:
        >>> GET /api/orb/colors
        {
            "spark": {"hex": "#FF6B35", "name": "Phoenix Orange"},
            "forge": {"hex": "#FFB347", "name": "Forge Amber"},
            ...
        }
    """
    from kagami.core.orb.colors import COLONY_COLORS

    return {
        name: {
            "hex": color.hex,
            "rgb": color.rgb,
            "name": color.description,
        }
        for name, color in COLONY_COLORS.items()
    }


# =============================================================================
# WebSocket Endpoint
# =============================================================================


@router.websocket("/stream")
async def orb_stream(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time orb state updates.

    Clients connect to receive:
        - orb_state: Full state updates
        - orb_interaction: Interaction events from other clients
        - orb_state_changed: Colony change notifications

    The connection is kept alive with periodic state broadcasts.

    Example:
        >>> ws = websocket.connect("ws://localhost:8001/api/orb/stream")
        >>> async for msg in ws:
        ...     if msg["type"] == "orb_interaction":
        ...         # Flash LED on Hub
        ...     elif msg["type"] == "orb_state":
        ...         # Update display color
    """
    await orb_manager.connect(websocket)

    # Send initial state
    state = get_orb_state()
    await websocket.send_json(
        {
            "type": "orb_state",
            **state.to_dict(),
        }
    )

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_json()

            # Handle client-initiated interactions
            if data.get("type") == "interaction":
                event = OrbInteractionEvent.from_websocket_message(data)
                await orb_manager.broadcast_interaction(event)
                logger.debug(f"WebSocket interaction: {event.action.value}")

    except WebSocketDisconnect:
        await orb_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Orb WebSocket error: {e}")
        await orb_manager.disconnect(websocket)


# =============================================================================
# Integration Functions
# =============================================================================


async def broadcast_orb_state_update(state: OrbState) -> None:
    """Broadcast an orb state update to all clients.

    Called by other parts of the system when state changes.

    Args:
        state: New orb state to broadcast

    Example:
        >>> from kagami_api.routes.orb import broadcast_orb_state_update
        >>> await broadcast_orb_state_update(new_state)
    """
    await orb_manager.broadcast_state(state)


async def broadcast_colony_change(
    previous: str | None,
    new: str | None,
    trigger: str = "api",
) -> None:
    """Broadcast a colony change event.

    Called when the active colony changes.

    Args:
        previous: Previous colony (or None)
        new: New colony (or None)
        trigger: What caused the change
    """
    from kagami.core.orb.events import create_state_changed_event

    event = create_state_changed_event(previous, new, trigger)
    await orb_manager.broadcast_state_changed(event)


def get_connection_count() -> int:
    """Get the number of connected orb clients.

    Returns:
        Number of active WebSocket connections
    """
    return len(orb_manager.active_connections)
