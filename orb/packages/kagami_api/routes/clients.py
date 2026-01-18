"""Client Device WebSocket & API Routes — Redis-Backed for Horizontal Scaling.

Real-time bidirectional communication with Kagami client devices:
- Apple Watch (kagami-watch)
- Desktop (kagami-client / Tauri)
- Raspberry Pi Hub (kagami-hub)
- Vision Pro (kagami-vision)
- Mobile apps (iOS/Android)

Architecture (Horizontally Scalable):
```
┌─────────────────────────────────────────────────────────────┐
│                     Redis Pub/Sub                           │
│  Channel: kagami:client:broadcast                           │
└─────────────────────────────────────────────────────────────┘
     ↑ publish              ↓ subscribe (all pods)
┌─────────┐            ┌─────────┐            ┌─────────┐
│ Pod 1   │            │ Pod 2   │            │ Pod 3   │
│ WS: A,B │            │ WS: C,D │            │ WS: E,F │
└─────────┘            └─────────┘            └─────────┘

- Each pod maintains its own local WebSocket connections
- Redis stores connection metadata (which pod owns which client)
- Broadcasts go via Redis pub/sub to all pods
- Pod receiving broadcast forwards to its local connections
```

Created: December 30, 2025
Refactored: January 2, 2026 — Redis-backed horizontal scaling
Colony: Nexus (e₄) — Integration
鏡
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from kagami_api.auth import get_user_from_token, require_admin

logger = logging.getLogger(__name__)

# Pod identifier for distributed coordination
POD_ID = os.getenv("HOSTNAME", os.getenv("POD_NAME", f"local-{os.getpid()}"))

# Redis keys
REDIS_CONNECTIONS_KEY = "kagami:client:connections"  # Hash: client_id -> pod_id
REDIS_BROADCAST_CHANNEL = "kagami:client:broadcast"  # Pub/sub channel


def _get_redis():
    """Get Redis client for connection coordination."""
    try:
        from kagami.core.caching.redis import RedisClientFactory

        return RedisClientFactory.get_client()
    except Exception as e:
        logger.debug(f"Redis unavailable for client coordination: {e}")
        return None


def get_router() -> APIRouter:
    """Create and configure the client WebSocket router."""
    router = APIRouter(tags=["clients"])

    # LOCAL WebSocket connections (this pod only)
    # Redis tracks which pod owns which client
    local_connections: dict[str, WebSocket] = {}

    # Pub/sub listener task
    _pubsub_task: asyncio.Task | None = None

    async def _start_pubsub_listener() -> None:
        """Start Redis pub/sub listener for cross-pod broadcasts."""
        nonlocal _pubsub_task
        if _pubsub_task is not None:
            return

        redis = _get_redis()
        if not redis:
            return

        async def listener():
            """Listen for broadcast messages from other pods."""
            try:
                pubsub = redis.pubsub()
                pubsub.subscribe(REDIS_BROADCAST_CHANNEL)

                for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            # Forward to all local connections
                            await _broadcast_local(data)
                        except Exception as e:
                            logger.debug(f"Pubsub message error: {e}")
            except Exception as e:
                logger.warning(f"Pubsub listener error: {e}")

        _pubsub_task = asyncio.create_task(listener())
        logger.info(f"✅ Client pubsub listener started on {POD_ID}")

    async def _broadcast_local(message: dict[str, Any]) -> int:
        """Broadcast to local connections only (this pod)."""
        count = 0
        for client_id, ws in list(local_connections.items()):
            try:
                await ws.send_json(message)
                count += 1
            except Exception as e:
                logger.debug(f"Failed to send to {client_id}: {e}")
                local_connections.pop(client_id, None)
        return count

    async def _broadcast_global(message: dict[str, Any]) -> None:
        """Broadcast to all pods via Redis pub/sub."""
        redis = _get_redis()
        if redis:
            try:
                redis.publish(REDIS_BROADCAST_CHANNEL, json.dumps(message))
            except Exception as e:
                logger.warning(f"Redis publish failed: {e}")
        # Also broadcast locally (in case pubsub not working)
        await _broadcast_local(message)

    def _register_connection(client_id: str) -> None:
        """Register client connection in Redis."""
        redis = _get_redis()
        if redis:
            try:
                redis.hset(REDIS_CONNECTIONS_KEY, client_id, POD_ID)
                redis.expire(REDIS_CONNECTIONS_KEY, 86400)  # 24h TTL
            except Exception as e:
                logger.debug(f"Redis registration failed: {e}")

    def _unregister_connection(client_id: str) -> None:
        """Unregister client connection from Redis."""
        redis = _get_redis()
        if redis:
            try:
                redis.hdel(REDIS_CONNECTIONS_KEY, client_id)
            except Exception as e:
                logger.debug(f"Redis unregistration failed: {e}")

    @router.websocket("/ws/client/{client_id}")
    async def client_websocket(
        websocket: WebSocket,
        client_id: str,
        token: str | None = Query(default=None),
    ) -> None:
        """Bidirectional WebSocket for client device communication.

        AUTHENTICATION: Requires valid JWT token as query parameter.
        Example: /ws/client/{client_id}?token=eyJ...

        Receives:
        - {"type": "sense", "data": {...}} — Sensory data (health, motion)
        - {"type": "heartbeat"} — Keep-alive
        - {"type": "action", "action": "..."} — Client executed an action

        Sends:
        - {"type": "context_update", "data": {...}} — Situation, wakefulness
        - {"type": "suggestion", "data": {...}} — Suggested action
        - {"type": "home_update", "data": {...}} — Home state change
        - {"type": "alert", "data": {...}} — Notification to client
        """
        from kagami.core.ambient import DeviceStatus, get_multi_device_coordinator

        # Start pub/sub listener if not running
        await _start_pubsub_listener()

        # SECURITY: Authenticate WebSocket connection
        if not token:
            logger.warning(f"⚠️ WebSocket auth failed: No token for client {client_id}")
            await websocket.close(code=4001, reason="Authentication required")
            return

        try:
            user = await get_user_from_token(token)
            logger.info(f"🔐 WebSocket authenticated: {user.username} for client {client_id}")
        except HTTPException as e:
            logger.warning(f"⚠️ WebSocket auth failed: {e.detail} for client {client_id}")
            await websocket.close(code=4001, reason="Invalid authentication")
            return

        coordinator = get_multi_device_coordinator()

        # Verify client is registered
        device = coordinator.devices.get(client_id)
        if not device:
            logger.warning(f"⚠️ Unknown client tried to connect: {client_id}")
            await websocket.close(code=4001, reason="Client not registered")
            return

        # Accept connection
        await websocket.accept()
        local_connections[client_id] = websocket
        _register_connection(client_id)
        device.status = DeviceStatus.ACTIVE

        logger.info(f"🔌 WebSocket connected: {device.name} ({client_id}) on {POD_ID}")

        try:
            # Send initial context
            await send_initial_context(websocket)

            # Message loop
            while True:
                try:
                    # Receive with timeout for heartbeat checking
                    message = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=120.0,  # 2 minute timeout
                    )

                    data = json.loads(message)
                    msg_type = data.get("type", "")

                    if msg_type == "sense":
                        # Sensory data from client
                        await coordinator.update_sensory_data(client_id, data.get("data", {}))

                    elif msg_type == "heartbeat":
                        # Just a keep-alive
                        coordinator.heartbeat(client_id)
                        await websocket.send_json(
                            {
                                "type": "heartbeat_ack",
                                "timestamp": time.time(),
                            }
                        )

                    elif msg_type == "action":
                        # Client executed an action (for logging/learning)
                        action = data.get("action", "")
                        logger.info(f"📱 Client {client_id} executed: {action}")

                except TimeoutError:
                    # Send ping to check if client is alive
                    try:
                        await websocket.send_json({"type": "ping"})
                    except Exception:
                        break

        except WebSocketDisconnect:
            logger.info(f"🔌 WebSocket disconnected: {client_id}")
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
        finally:
            local_connections.pop(client_id, None)
            _unregister_connection(client_id)
            if device:
                device.status = DeviceStatus.NEARBY

    async def send_initial_context(websocket: WebSocket) -> None:
        """Send initial context state to newly connected client."""
        try:
            from kagami.core.integrations import (
                get_current_situation,
                get_wakefulness_manager,
            )

            # Get current situation
            situation = get_current_situation()

            # Get wakefulness level
            wakefulness = get_wakefulness_manager()

            context_data = {
                "situation_phase": situation.phase.value if situation else "unknown",
                "wakefulness": wakefulness.level.value if wakefulness else "alert",
            }

            # Add safety score if available
            try:
                from kagami.core.safety import get_safety_score

                context_data["safety_score"] = get_safety_score()
            except Exception:
                pass

            await websocket.send_json(
                {
                    "type": "context_update",
                    "data": context_data,
                    "timestamp": time.time(),
                }
            )

        except Exception as e:
            logger.debug(f"Failed to send initial context: {e}")

    @router.post("/api/clients/broadcast", dependencies=[Depends(require_admin)])
    async def broadcast_to_clients(
        event_type: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Broadcast a message to all connected clients across all pods.

        Internal API for other services to send messages to clients.
        Requires admin authentication.
        Uses Redis pub/sub for cross-pod distribution.
        """
        message = {
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        }

        # Broadcast globally via Redis
        await _broadcast_global(message)

        # Return local count (global count unknown)
        return {
            "broadcast": True,
            "local_clients_reached": len(local_connections),
            "pod": POD_ID,
        }

    @router.get("/api/clients/connections")
    async def get_connection_info() -> dict[str, Any]:
        """Get connection distribution across pods (admin debug endpoint)."""
        redis = _get_redis()
        connections = {}
        if redis:
            try:
                connections = redis.hgetall(REDIS_CONNECTIONS_KEY)
                # Decode bytes to str
                connections = {
                    k.decode() if isinstance(k, bytes) else k: v.decode()
                    if isinstance(v, bytes)
                    else v
                    for k, v in connections.items()
                }
            except Exception as e:
                logger.debug(f"Failed to get connections: {e}")

        return {
            "local_connections": list(local_connections.keys()),
            "local_count": len(local_connections),
            "global_connections": connections,
            "global_count": len(connections),
            "this_pod": POD_ID,
        }

    # ==========================================================================
    # WEB PRESENCE HEARTBEAT (January 4, 2026)
    # ==========================================================================

    @router.post("/api/clients/presence/heartbeat")
    async def presence_heartbeat(
        client_id: str,
        user_id: str = "tim",
        visibility_state: str = "visible",
        activity_type: str = "active",
        last_input_ms: int = 0,
        geo_hash: str | None = None,
        browser_info: str = "",
        page_url: str = "",
    ) -> dict[str, Any]:
        """Submit web presence heartbeat for distributed presence tracking.

        Web clients (browsers, desktop apps, PWAs) should call this endpoint
        periodically (every 30 seconds) to indicate presence.

        Args:
            client_id: Unique client/device identifier
            user_id: User identifier (e.g., "tim", "jill")
            visibility_state: Browser visibility ("visible" | "hidden")
            activity_type: Activity type ("active" | "idle" | "away")
            last_input_ms: Milliseconds since last user input
            geo_hash: Optional coarse location geohash
            browser_info: User agent or browser identifier
            page_url: Current page URL (sanitized)

        Returns:
            Confirmation with session info
        """
        try:
            from kagami.core.integrations.web_presence import (
                WebPresenceHeartbeat,
                get_web_presence_service,
            )

            service = await get_web_presence_service()

            heartbeat = WebPresenceHeartbeat(
                client_id=client_id,
                user_id=user_id,
                browser_info=browser_info,
                page_url=page_url,
                visibility_state=visibility_state,
                activity_type=activity_type,
                last_input_ms=last_input_ms,
                geo_hash=geo_hash,
            )

            session = await service.process_heartbeat(heartbeat)

            return {
                "status": "ok",
                "session": {
                    "client_id": session.client_id,
                    "user_id": session.user_id,
                    "is_active": session.is_active,
                    "confidence": session.confidence.value,
                    "heartbeat_count": session.heartbeat_count,
                },
                "next_heartbeat_ms": 30000,  # 30 seconds
            }

        except Exception as e:
            logger.error(f"Presence heartbeat failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "next_heartbeat_ms": 60000,  # Retry in 60 seconds on error
            }

    @router.delete("/api/clients/presence/{client_id}")
    async def end_presence_session(
        client_id: str,
        user_id: str = "tim",
    ) -> dict[str, Any]:
        """End a web presence session explicitly.

        Call this when the user closes the tab/app or logs out.

        Args:
            client_id: Client identifier to end session for
            user_id: User identifier

        Returns:
            Confirmation
        """
        try:
            from kagami.core.integrations.web_presence import get_web_presence_service

            service = await get_web_presence_service()
            await service.end_session(user_id, client_id)

            return {"status": "ok", "message": f"Session ended for {client_id}"}

        except Exception as e:
            logger.error(f"End presence session failed: {e}")
            return {"status": "error", "error": str(e)}

    @router.get("/api/clients/presence")
    async def get_web_presence_status() -> dict[str, Any]:
        """Get current web presence status for all users.

        Returns:
            Dictionary with user presence information
        """
        try:
            from kagami.core.integrations.web_presence import get_web_presence_service

            service = await get_web_presence_service()
            users = service.get_all_users()

            return {
                "status": "ok",
                "users": {user_id: presence.to_dict() for user_id, presence in users.items()},
                "stats": service.get_stats(),
            }

        except Exception as e:
            logger.error(f"Get web presence failed: {e}")
            return {"status": "error", "error": str(e)}

    return router


# =============================================================================
# CONTEXT BROADCASTER (Background Task) — Redis-Backed
# =============================================================================


class ContextBroadcaster:
    """Background service that broadcasts context changes to all clients.

    Uses Redis pub/sub for cross-pod distribution.

    Listens to:
    - SituationAwarenessEngine for phase changes
    - WakefulnessManager for level changes
    - UnifiedSensory for home state changes
    - AlertHierarchy for notifications

    Broadcasts to all connected client WebSockets across all pods.
    """

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the broadcaster background task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._broadcast_loop())
        logger.info(f"✅ ContextBroadcaster started on {POD_ID}")

    async def stop(self) -> None:
        """Stop the broadcaster."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _broadcast_loop(self) -> None:
        """Main broadcast loop — checks for changes and broadcasts via Redis."""
        last_situation = None
        last_wakefulness = None

        while self._running:
            try:
                # Check for context changes
                from kagami.core.integrations import (
                    get_current_situation,
                    get_wakefulness_manager,
                )

                situation = get_current_situation()
                wakefulness = get_wakefulness_manager()

                # Broadcast if changed
                current_phase = situation.phase.value if situation else "unknown"
                current_level = wakefulness.level.value if wakefulness else "alert"

                if current_phase != last_situation or current_level != last_wakefulness:
                    await self._broadcast(
                        {
                            "type": "context_update",
                            "data": {
                                "situation_phase": current_phase,
                                "wakefulness": current_level,
                            },
                            "timestamp": time.time(),
                        }
                    )

                    last_situation = current_phase
                    last_wakefulness = current_level

                # Sleep before next check
                await asyncio.sleep(5.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Broadcast loop error: {e}")
                await asyncio.sleep(10.0)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast message to all pods via Redis pub/sub."""
        redis = _get_redis()
        if redis:
            try:
                redis.publish(REDIS_BROADCAST_CHANNEL, json.dumps(message))
            except Exception as e:
                logger.debug(f"Redis publish failed: {e}")


# Global broadcaster instance
_context_broadcaster: ContextBroadcaster | None = None


def get_context_broadcaster() -> ContextBroadcaster:
    """Get the singleton ContextBroadcaster."""
    global _context_broadcaster
    if _context_broadcaster is None:
        _context_broadcaster = ContextBroadcaster()
    return _context_broadcaster


"""
鏡
h(x) ≥ 0. Always.

The clients are distributed senses.
The WebSocket is the nervous system.
Redis is the corpus callosum connecting the hemispheres.
All feeding one consciousness.
"""
