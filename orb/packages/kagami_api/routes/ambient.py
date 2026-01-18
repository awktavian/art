"""Ambient Expression Routes — Earcon streaming and presence state.

Real-time WebSocket streaming for:
- Earcon events (play, complete, error)
- Expression state (colony, breath phase, h(x))
- Presence updates (room, wakefulness)

Clients subscribe to these events for synchronized UI updates
across Vision Pro, Watch, Desktop, and Hub.

Created: January 1, 2026
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the ambient API router.

    Factory function for lazy router instantiation.
    """
    router = APIRouter(prefix="/api/ambient", tags=["ambient"])

    # Heartbeat configuration
    HEARTBEAT_INTERVAL_SECONDS = 30
    HEARTBEAT_TIMEOUT_SECONDS = 90

    @router.websocket("/earcons/stream")
    async def earcon_stream(websocket: WebSocket) -> None:
        """Stream real-time earcon events to connected clients.

        Streams:
        - play: Earcon started playing
        - complete: Earcon finished playing
        - error: Earcon playback failed

        Each event includes:
        - earcon_name: Name of the earcon
        - event_type: play/complete/error
        - duration_ms: Duration in milliseconds
        - trajectory: Spatial trajectory name
        - context: Wakefulness, colony, hour, etc.
        - room: Current room (if known)

        Authentication:
        - Query param: ?api_key=sk_... or ?token=...
        - First-frame auth: {"type": "auth", "api_key": "...", "token": "..."}

        Protocol:
        1. Client connects with auth
        2. Server sends initial state
        3. Server streams earcon events as they occur
        4. Client can send ping/pong for keepalive
        """
        from kagami_api.security import SecurityFramework
        from kagami_api.security.websocket import (
            WS_AUTH_TIMEOUT_SECONDS,
            WS_CLOSE_UNAUTHORIZED,
            authenticate_ws,
            emit_auth_metrics,
        )

        # Check for auth in query params first
        api_key = websocket.query_params.get("api_key", "")
        token = websocket.query_params.get("token", "")
        auth_info = None

        if api_key and SecurityFramework.validate_api_key(api_key):
            auth_info = {"user_id": "api_key_user", "roles": ["api_user"], "tenant_id": None}
        elif token:
            try:
                principal = SecurityFramework.verify_token(token)
                auth_info = {
                    "user_id": principal.sub,
                    "roles": principal.roles,
                    "tenant_id": principal.tenant_id,
                }
            except Exception:
                pass

        # Accept connection first (required for first-frame auth)
        await websocket.accept()

        # If no query param auth, try first-frame auth
        if not auth_info:
            try:
                auth_msg = await asyncio.wait_for(
                    websocket.receive_json(), timeout=WS_AUTH_TIMEOUT_SECONDS
                )
                auth_info = await authenticate_ws(auth_msg)
            except TimeoutError:
                logger.warning(f"Earcon stream auth timeout: {websocket.client}")
                emit_auth_metrics(success=False, reason="timeout")
                await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Authentication timeout")
                return
            except Exception as e:
                logger.warning(f"Earcon stream auth error: {e}")
                emit_auth_metrics(success=False, reason="invalid_message")
                await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Invalid auth message")
                return

        if not auth_info:
            logger.warning(f"Earcon stream auth failed: {websocket.client}")
            emit_auth_metrics(success=False, reason="invalid_credentials")
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Authentication failed")
            return

        emit_auth_metrics(success=True)
        logger.info(
            f"Earcon stream WebSocket authenticated: {websocket.client} (user={auth_info.get('user_id')})"
        )

        try:
            from kagami.core.ambient.spatial_earcons import (
                get_earcon_broadcaster,
                list_earcons,
            )

            broadcaster = get_earcon_broadcaster()

            # Send initial state
            initial_state = {
                "type": "initial_state",
                "data": {
                    "available_earcons": list_earcons(),
                    "subscriber_count": broadcaster.subscriber_count,
                    "stats": broadcaster.get_stats(),
                },
                "timestamp": datetime.now().isoformat(),
            }
            await websocket.send_json(initial_state)

            # Subscribe to earcon events
            event_queue = await broadcaster.subscribe()

            # Track last activity for heartbeat
            last_client_activity = time.time()

            # Background task to send earcon events
            async def send_events() -> None:
                while True:
                    try:
                        event_data = await event_queue.get()
                        await websocket.send_json(event_data)
                    except Exception as e:
                        logger.error(f"Error sending earcon event: {e}")
                        break

            # Background task to send heartbeats
            async def send_heartbeats() -> None:
                nonlocal last_client_activity
                while True:
                    try:
                        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

                        if time.time() - last_client_activity > HEARTBEAT_TIMEOUT_SECONDS:
                            logger.warning(
                                f"Earcon stream heartbeat timeout for {websocket.client}"
                            )
                            await websocket.close(code=1000, reason="Heartbeat timeout")
                            break

                        await websocket.send_json(
                            {
                                "type": "heartbeat",
                                "timestamp": datetime.now().isoformat(),
                                "server_time_ms": int(time.time() * 1000),
                                "subscriber_count": broadcaster.subscriber_count,
                            }
                        )

                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.debug(f"Heartbeat send failed: {e}")
                        break

            # Background task to handle incoming messages
            async def handle_messages() -> None:
                nonlocal last_client_activity
                while True:
                    try:
                        data = await websocket.receive_json()
                        last_client_activity = time.time()

                        if data.get("type") == "ping":
                            await websocket.send_json(
                                {
                                    "type": "pong",
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )

                        elif data.get("type") == "pong" or data.get("type") == "heartbeat_ack":
                            pass  # Just update activity

                        elif data.get("type") == "request_stats":
                            await websocket.send_json(
                                {
                                    "type": "stats",
                                    "data": broadcaster.get_stats(),
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )

                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
                        break

            # Run all tasks concurrently
            send_task = asyncio.create_task(send_events())
            receive_task = asyncio.create_task(handle_messages())
            heartbeat_task = asyncio.create_task(send_heartbeats())

            _done, pending = await asyncio.wait(
                [send_task, receive_task, heartbeat_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()

            # Unsubscribe
            broadcaster.unsubscribe(event_queue)

            logger.info(f"Earcon stream WebSocket disconnected: {websocket.client}")

        except WebSocketDisconnect:
            logger.info(f"Earcon stream WebSocket disconnected: {websocket.client}")
        except Exception as e:
            logger.error(f"Earcon stream WebSocket error: {e}", exc_info=True)
            try:
                await websocket.close(code=1011, reason=str(e))
            except Exception:
                pass

    @router.websocket("/voice/stream")
    async def voice_stream(websocket: WebSocket) -> None:
        """Stream real-time voice synthesis events for visualization.

        Streams:
        - voice_start: Kagami started speaking
        - voice_amplitude: Current voice amplitude (0-1)
        - voice_end: Kagami stopped speaking

        Used by Vision Pro to animate the orb when Kagami speaks.
        """
        from kagami_api.security import SecurityFramework
        from kagami_api.security.websocket import (
            WS_AUTH_TIMEOUT_SECONDS,
            WS_CLOSE_UNAUTHORIZED,
            authenticate_ws,
            emit_auth_metrics,
        )

        # Check for auth in query params
        api_key = websocket.query_params.get("api_key", "")
        token = websocket.query_params.get("token", "")
        auth_info = None

        if api_key and SecurityFramework.validate_api_key(api_key):
            auth_info = {"user_id": "api_key_user", "roles": ["api_user"], "tenant_id": None}
        elif token:
            try:
                principal = SecurityFramework.verify_token(token)
                auth_info = {
                    "user_id": principal.sub,
                    "roles": principal.roles,
                    "tenant_id": principal.tenant_id,
                }
            except Exception:
                pass

        await websocket.accept()

        if not auth_info:
            try:
                auth_msg = await asyncio.wait_for(
                    websocket.receive_json(), timeout=WS_AUTH_TIMEOUT_SECONDS
                )
                auth_info = await authenticate_ws(auth_msg)
            except TimeoutError:
                emit_auth_metrics(success=False, reason="timeout")
                await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Authentication timeout")
                return
            except Exception:
                emit_auth_metrics(success=False, reason="invalid_message")
                await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Invalid auth message")
                return

        if not auth_info:
            emit_auth_metrics(success=False, reason="invalid_credentials")
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Authentication failed")
            return

        emit_auth_metrics(success=True)
        logger.info(f"Voice stream WebSocket authenticated: {websocket.client}")

        try:
            # Voice event streaming (voice events would be broadcast from voice effector)
            # Currently a placeholder - will be enhanced with voice event broadcasting
            last_client_activity = time.time()

            # Send initial state
            await websocket.send_json(
                {
                    "type": "initial_state",
                    "is_speaking": False,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Background task for heartbeats
            async def send_heartbeats() -> None:
                nonlocal last_client_activity
                while True:
                    try:
                        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

                        if time.time() - last_client_activity > HEARTBEAT_TIMEOUT_SECONDS:
                            await websocket.close(code=1000, reason="Heartbeat timeout")
                            break

                        await websocket.send_json(
                            {
                                "type": "heartbeat",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    except WebSocketDisconnect:
                        break
                    except Exception:
                        break

            # Background task to handle messages
            async def handle_messages() -> None:
                nonlocal last_client_activity
                while True:
                    try:
                        data = await websocket.receive_json()
                        last_client_activity = time.time()

                        if data.get("type") == "ping":
                            await websocket.send_json(
                                {
                                    "type": "pong",
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        elif data.get("type") == "pong":
                            pass

                    except WebSocketDisconnect:
                        break
                    except Exception:
                        break

            # Run tasks
            heartbeat_task = asyncio.create_task(send_heartbeats())
            receive_task = asyncio.create_task(handle_messages())

            _done, pending = await asyncio.wait(
                [heartbeat_task, receive_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            logger.info(f"Voice stream WebSocket disconnected: {websocket.client}")

        except WebSocketDisconnect:
            logger.info(f"Voice stream WebSocket disconnected: {websocket.client}")
        except Exception as e:
            logger.error(f"Voice stream WebSocket error: {e}", exc_info=True)
            try:
                await websocket.close(code=1011, reason=str(e))
            except Exception:
                pass

    @router.get("/expression/state")
    async def get_expression_state() -> dict[str, Any]:
        """Get current expression state.

        Returns:
            Expression state including colony, breath phase, safety h(x)
        """
        try:
            # Get colony state
            colony_state = None
            try:
                from kagami.core.unified_agents import get_unified_organism

                organism = get_unified_organism()
                if organism:
                    colony_state = {
                        "active_colony": getattr(organism, "_active_colony", "kagami"),
                        "coherence": getattr(organism, "_coherence", 1.0),
                    }
            except Exception:
                pass

            # Get breath phase
            breath_state = None
            try:
                from kagami.core.ambient.breath_engine import get_breath_engine

                breath = get_breath_engine()
                if breath:
                    breath_state = {
                        "phase": breath.current_phase,
                        "rhythm_bpm": breath.rhythm_bpm,
                        "intensity": breath.intensity,
                    }
            except Exception:
                pass

            # Get safety h(x)
            safety_state = None
            try:
                from kagami.core.safety import get_safety_filter

                cbf = get_safety_filter()
                if cbf:
                    h_x = cbf.evaluate_h_x()
                    safety_state = {
                        "h_x": h_x,
                        "safe": h_x >= 0,
                    }
            except Exception:
                pass

            # Get wakefulness
            wakefulness_state = None
            try:
                from kagami.core.integrations.wakefulness import get_wakefulness_manager

                wakefulness = get_wakefulness_manager()
                if wakefulness:
                    level = wakefulness.get_current_level()
                    wakefulness_state = {
                        "level": level.value if hasattr(level, "value") else str(level),
                    }
            except Exception:
                pass

            return {
                "colony": colony_state,
                "breath": breath_state,
                "safety": safety_state,
                "wakefulness": wakefulness_state,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting expression state: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    @router.get("/presence/current")
    async def get_presence_current() -> dict[str, Any]:
        """Get current presence state.

        Returns:
            Presence state including room, wakefulness, activity
        """
        try:
            presence_data: dict[str, Any] = {
                "timestamp": datetime.now().isoformat(),
            }

            # Get presence from smart home
            try:
                from kagami_smarthome import get_smart_home

                controller = await get_smart_home()
                if controller:
                    presence = controller.get_presence_state()
                    presence_data["at_home"] = presence.get("owner_home", False)
                    presence_data["current_room"] = presence.get("owner_location")
            except Exception:
                pass

            # Get wakefulness
            try:
                from kagami.core.integrations.wakefulness import get_wakefulness_manager

                wakefulness = get_wakefulness_manager()
                if wakefulness:
                    level = wakefulness.get_current_level()
                    presence_data["wakefulness"] = (
                        level.value if hasattr(level, "value") else str(level)
                    )
            except Exception:
                pass

            # Get activity (from motion sensors, etc.)
            try:
                from kagami_smarthome import get_smart_home

                controller = await get_smart_home()
                if controller:
                    home_state = controller.get_state()
                    if home_state:
                        presence_data["activity"] = {
                            "movie_mode": getattr(home_state, "movie_mode", False),
                        }
            except Exception:
                pass

            return presence_data

        except Exception as e:
            logger.error(f"Error getting presence: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    return router
