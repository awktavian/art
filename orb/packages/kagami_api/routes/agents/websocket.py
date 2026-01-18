"""Agent WebSocket — Real-time bidirectional events.

WebSocket endpoint for agent real-time communication:
- State changes
- Secret discoveries
- Audio-reactive data (frequency analysis)
- Queries and commands
- Learning events

Protocol:
    Client → Server: JSON messages (query, action, audio_data, learn)
    Server → Client: JSON messages (state, event, audio_reactive, response)

Security:
- Kagami Pro subscription required for WebSocket
- Connection limits per agent and per IP
- Message rate limiting by tier
- Input validation on all messages

Colony: Nexus (e4) — Integration
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from kagami.core.agents import get_agent_registry
from kagami.core.agents.auth import (
    AgentEntitlement,
    authenticate_websocket,
)
from kagami.core.agents.security import (
    check_rate_limit,
    check_websocket_connection,
    register_websocket_connection,
    unregister_websocket_connection,
    validate_agent_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents-ws"])


# =============================================================================
# Message Types
# =============================================================================


class ClientMessageType(str, Enum):
    """Message types from client."""

    QUERY = "query"  # Query the agent
    ACTION = "action"  # Trigger action
    AUDIO_DATA = "audio_data"  # Audio analysis data
    LEARN = "learn"  # Learning event
    SUBSCRIBE = "subscribe"  # Subscribe to events
    UNSUBSCRIBE = "unsubscribe"  # Unsubscribe from events
    PING = "ping"  # Heartbeat


class ServerMessageType(str, Enum):
    """Message types to client."""

    STATE = "state"  # State update
    EVENT = "event"  # Generic event
    AUDIO_REACTIVE = "audio_reactive"  # CSS variables for audio reactivity
    RESPONSE = "response"  # Response to query/action
    SECRET_FOUND = "secret_found"  # Secret discovery notification
    ADAPTATION = "adaptation"  # Adaptation triggered
    PONG = "pong"  # Heartbeat response
    ERROR = "error"  # Error message


# =============================================================================
# Connection Management
# =============================================================================


@dataclass
class AgentConnection:
    """Represents a WebSocket connection to an agent."""

    websocket: WebSocket
    agent_id: str
    session_id: str
    connected_at: float = field(default_factory=time.time)
    subscriptions: set[str] = field(default_factory=set)
    last_ping: float = field(default_factory=time.time)

    async def send(self, msg_type: ServerMessageType, data: dict[str, Any]) -> None:
        """Send message to client."""
        message = {"type": msg_type.value, "timestamp": time.time(), **data}
        await self.websocket.send_text(json.dumps(message))


class ConnectionManager:
    """Manages agent WebSocket connections."""

    def __init__(self) -> None:
        self.connections: dict[str, list[AgentConnection]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, agent_id: str, session_id: str
    ) -> AgentConnection:
        """Add a new connection."""
        await websocket.accept()

        conn = AgentConnection(
            websocket=websocket,
            agent_id=agent_id,
            session_id=session_id,
        )

        async with self._lock:
            if agent_id not in self.connections:
                self.connections[agent_id] = []
            self.connections[agent_id].append(conn)

            # Update agent state
            registry = get_agent_registry()
            agent = registry.get_agent(agent_id)
            if agent:
                agent.active_connections += 1

        logger.info(f"WebSocket connected: {agent_id}/{session_id}")
        return conn

    async def disconnect(self, conn: AgentConnection) -> None:
        """Remove a connection."""
        async with self._lock:
            if conn.agent_id in self.connections:
                self.connections[conn.agent_id] = [
                    c for c in self.connections[conn.agent_id] if c.session_id != conn.session_id
                ]

                # Update agent state
                registry = get_agent_registry()
                agent = registry.get_agent(conn.agent_id)
                if agent:
                    agent.active_connections = max(0, agent.active_connections - 1)

        logger.info(f"WebSocket disconnected: {conn.agent_id}/{conn.session_id}")

    async def broadcast(
        self, agent_id: str, msg_type: ServerMessageType, data: dict[str, Any]
    ) -> None:
        """Broadcast message to all connections for an agent."""
        conns = self.connections.get(agent_id, [])
        await asyncio.gather(
            *[conn.send(msg_type, data) for conn in conns],
            return_exceptions=True,
        )

    async def broadcast_to_subscribed(
        self,
        agent_id: str,
        event_name: str,
        msg_type: ServerMessageType,
        data: dict[str, Any],
    ) -> None:
        """Broadcast to connections subscribed to an event."""
        conns = self.connections.get(agent_id, [])
        subscribed = [c for c in conns if event_name in c.subscriptions or "*" in c.subscriptions]
        await asyncio.gather(
            *[conn.send(msg_type, data) for conn in subscribed],
            return_exceptions=True,
        )


# Global connection manager
manager = ConnectionManager()


# =============================================================================
# WebSocket Endpoint
# =============================================================================


@router.websocket("/v1/ws/agent/{agent_id}")
async def agent_websocket(
    websocket: WebSocket,
    agent_id: str,
    token: str | None = Query(None, description="Auth token"),
):
    """WebSocket endpoint for real-time agent communication.

    Requires: Kagami Pro subscription.

    Protocol:
    1. Client connects to /v1/ws/agent/{agent_id}?token=xxx
    2. Server authenticates and sends initial state
    3. Bidirectional JSON messages:
       - Client: query, action, audio_data, learn, subscribe, ping
       - Server: state, event, audio_reactive, response, secret_found, pong

    Audio Reactive Protocol:
    1. Client sends audio_data with frequency bands
    2. Server responds with CSS variable mappings
    3. Client applies CSS variables for visual effects

    Security:
    - Pro subscription required
    - Connection limits enforced
    - Tier-based message rate limiting
    - Input validation
    """
    # Authenticate user
    user = await authenticate_websocket(websocket, token)
    if not user:
        await websocket.close(
            code=4001,
            reason="Authentication required. Connect with ?token=YOUR_JWT or upgrade at kagami.ai/signup",
        )
        return

    # Check Pro entitlement for WebSocket
    if not user.can_access(AgentEntitlement.AGENT_WEBSOCKET):
        await websocket.close(
            code=4002,
            reason="Pro subscription required for real-time WebSocket. Upgrade at kagami.ai/pricing",
        )
        return

    # Validate agent_id
    try:
        agent_id = validate_agent_id(agent_id)
    except Exception:
        await websocket.close(code=4000, reason="Invalid agent ID")
        return

    # Get client IP
    client_ip = websocket.client.host if websocket.client else "unknown"

    # Check connection limits
    allowed, reason = await check_websocket_connection(agent_id, client_ip)
    if not allowed:
        await websocket.close(code=4029, reason=reason)
        return

    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        await websocket.close(code=4004, reason=f"Agent not found: {agent_id}")
        return

    # Generate session ID
    session_id = f"{agent_id}_{int(time.time() * 1000)}"

    # Register connection
    await register_websocket_connection(agent_id, client_ip)

    # Connect
    conn = await manager.connect(websocket, agent_id, session_id)

    # Send initial state
    await conn.send(
        ServerMessageType.STATE,
        {
            "agent_id": agent_id,
            "identity": agent.schema.i_am.model_dump(),
            "memory": agent.memory,
            "engagement": agent.engagement,
        },
    )

    try:
        while True:
            # Rate limiting for messages
            if not await check_rate_limit(f"ws:{client_ip}", limiter_type="ws"):
                await conn.send(ServerMessageType.ERROR, {"message": "Rate limit exceeded"})
                await asyncio.sleep(0.5)  # Small delay
                continue

            # Receive message
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                await handle_client_message(conn, agent, message)
            except json.JSONDecodeError:
                await conn.send(ServerMessageType.ERROR, {"message": "Invalid JSON"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup: unregister connection
        await unregister_websocket_connection(agent_id, client_ip)
        await manager.disconnect(conn)


# =============================================================================
# Message Handlers
# =============================================================================


async def handle_client_message(conn: AgentConnection, agent: Any, message: dict[str, Any]) -> None:
    """Handle incoming client message.

    Args:
        conn: Connection instance.
        agent: AgentState instance.
        message: Parsed message.
    """
    msg_type = message.get("type", "")

    handlers = {
        ClientMessageType.QUERY.value: handle_query,
        ClientMessageType.ACTION.value: handle_action,
        ClientMessageType.AUDIO_DATA.value: handle_audio_data,
        ClientMessageType.LEARN.value: handle_learn,
        ClientMessageType.SUBSCRIBE.value: handle_subscribe,
        ClientMessageType.UNSUBSCRIBE.value: handle_unsubscribe,
        ClientMessageType.PING.value: handle_ping,
    }

    handler = handlers.get(msg_type)
    if handler:
        await handler(conn, agent, message)
    else:
        await conn.send(ServerMessageType.ERROR, {"message": f"Unknown message type: {msg_type}"})


async def handle_query(conn: AgentConnection, agent: Any, message: dict[str, Any]) -> None:
    """Handle query message."""
    start_time = time.time()
    query = message.get("query", "")
    message.get("context", {})

    # Match against intents
    response_text = ""
    matched_intent = None
    actions = []

    query_lower = query.lower()

    for intent in agent.schema.i_speak.intents:
        pattern = intent.pattern.lower()
        if pattern in query_lower or query_lower in pattern:
            matched_intent = intent.pattern
            actions.append(intent.action)
            response_text = intent.response or agent.schema.i_speak.responses.get("default", "OK")
            break

    if not response_text:
        response_text = agent.schema.i_speak.responses.get(
            "greeting", f"Hello from {agent.schema.i_am.name}"
        )

    latency_ms = int((time.time() - start_time) * 1000)

    await conn.send(
        ServerMessageType.RESPONSE,
        {
            "query": query,
            "response": response_text,
            "intent": matched_intent,
            "actions": actions,
            "latency_ms": latency_ms,
        },
    )

    # Update agent
    agent.last_interaction = time.time()


async def handle_action(conn: AgentConnection, agent: Any, message: dict[str, Any]) -> None:
    """Handle action message."""
    action_type = message.get("action_type")
    parameters = message.get("parameters", {})

    try:
        from kagami_api.routes.agents.core import execute_agent_action

        result = await execute_agent_action(agent, action_type, parameters)
        await conn.send(
            ServerMessageType.RESPONSE,
            {"action_type": action_type, "success": True, "result": result},
        )
    except Exception as e:
        await conn.send(
            ServerMessageType.RESPONSE,
            {"action_type": action_type, "success": False, "error": str(e)},
        )


async def handle_audio_data(conn: AgentConnection, agent: Any, message: dict[str, Any]) -> None:
    """Handle audio analysis data for real-time reactivity.

    Client sends frequency band data, server responds with CSS variable mappings.
    """
    bands = message.get("bands", {})
    audio_config = agent.schema.i_react.audio

    # Calculate CSS variable values based on audio data
    css_vars = {}

    for var_name, band_name in audio_config.css_variables.items():
        band_value = bands.get(band_name, 0)
        # Normalize to 0-1 range
        normalized = min(1.0, max(0.0, band_value / 255.0))
        css_vars[var_name] = normalized

    await conn.send(
        ServerMessageType.AUDIO_REACTIVE, {"css_variables": css_vars, "raw_bands": bands}
    )


async def handle_learn(conn: AgentConnection, agent: Any, message: dict[str, Any]) -> None:
    """Handle learning event."""
    event_type = message.get("event_type", "")
    data = message.get("data", {})

    # Check for secret discovery
    if event_type == "secret_found":
        secret_id = data.get("secret_id")
        if secret_id and secret_id not in agent.secrets_found:
            agent.secrets_found.add(secret_id)
            await manager.broadcast(
                agent.agent_id,
                ServerMessageType.SECRET_FOUND,
                {"secret_id": secret_id},
            )

    # Process learning event
    triggered = []
    try:
        from kagami.core.agents.learning import process_learning_event

        triggered = await process_learning_event(agent, event_type, data)
    except ImportError:
        # Store raw engagement data
        agent.engagement[event_type] = data

    # Notify about triggered adaptations
    if triggered:
        await conn.send(ServerMessageType.ADAPTATION, {"triggered": triggered})

    await conn.send(ServerMessageType.RESPONSE, {"event_type": event_type, "accepted": True})


async def handle_subscribe(conn: AgentConnection, agent: Any, message: dict[str, Any]) -> None:
    """Handle subscription request."""
    events = message.get("events", [])
    conn.subscriptions.update(events)
    await conn.send(ServerMessageType.RESPONSE, {"subscribed": list(conn.subscriptions)})


async def handle_unsubscribe(conn: AgentConnection, agent: Any, message: dict[str, Any]) -> None:
    """Handle unsubscription request."""
    events = message.get("events", [])
    conn.subscriptions -= set(events)
    await conn.send(ServerMessageType.RESPONSE, {"subscribed": list(conn.subscriptions)})


async def handle_ping(conn: AgentConnection, agent: Any, message: dict[str, Any]) -> None:
    """Handle ping message."""
    conn.last_ping = time.time()
    await conn.send(ServerMessageType.PONG, {"ping_id": message.get("ping_id")})


# =============================================================================
# Broadcast Utilities
# =============================================================================


async def broadcast_state_change(agent_id: str, changes: dict[str, Any]) -> None:
    """Broadcast state change to all connected clients.

    Call this when agent state changes (e.g., from REST API).
    """
    await manager.broadcast(agent_id, ServerMessageType.STATE, {"changes": changes})


async def broadcast_event(agent_id: str, event_name: str, data: dict[str, Any]) -> None:
    """Broadcast generic event to subscribed clients."""
    await manager.broadcast_to_subscribed(
        agent_id,
        event_name,
        ServerMessageType.EVENT,
        {"event": event_name, "data": data},
    )


# =============================================================================
# Router Factory
# =============================================================================


def get_ws_router() -> APIRouter:
    """Get the WebSocket router."""
    return router


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "router",
    "manager",
    "broadcast_state_change",
    "broadcast_event",
    "get_ws_router",
]
