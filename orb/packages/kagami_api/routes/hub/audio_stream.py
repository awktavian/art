"""Low-Latency Audio Streaming Routes.

WebSocket endpoints for ultra-low-latency audio delivery to Hub devices.

PROTOCOL:
=========

1. Hub connects to /hub/audio/stream
2. Server sends all earcons for caching
3. Hub ready to receive audio events

Message types:
- earcon: Play cached sound by name (<20ms)
- audio_event: Full audio data (<50ms)
- stream_start/chunk/end: Chunked streaming (<100ms)
- stop: Stop playback
- volume: Set volume

Created: January 4, 2026
Colony: ⚒️ Forge (e₂) — Low-latency infrastructure
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from kagami_api.security.websocket import (
    WS_AUTH_TIMEOUT_SECONDS,
    WS_CLOSE_UNAUTHORIZED,
    authenticate_ws,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Connected Hub devices
_connected_hubs: dict[str, WebSocket] = {}
_hub_info: dict[str, dict[str, Any]] = {}


@router.websocket("/audio/stream")
async def audio_stream_websocket(websocket: WebSocket) -> None:
    """WebSocket for low-latency audio streaming to Hub devices.

    Protocol:
    1. Connect with auth token (query param or first frame)
    2. Receive earcon cache messages
    3. Receive audio events and stream chunks
    4. Send ack/status messages back

    Query params:
    - token: JWT auth token
    - hub_id: Hub device identifier
    """
    # Extract params
    token = websocket.query_params.get("token")
    hub_id = websocket.query_params.get("hub_id", "unknown")

    # Accept connection first (for first-frame auth)
    await websocket.accept()

    # Authenticate
    auth_info = None
    if token:
        try:
            from kagami_api.security import SecurityFramework

            principal = SecurityFramework.verify_token(token)
            auth_info = {
                "user_id": principal.sub,
                "roles": principal.roles,
            }
        except Exception:
            pass

    # Try first-frame auth if no query param auth
    if not auth_info:
        try:
            auth_msg = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=WS_AUTH_TIMEOUT_SECONDS,
            )
            if auth_msg.get("type") == "auth":
                result = await authenticate_ws(websocket, auth_msg)
                if result:
                    auth_info = result
        except TimeoutError:
            pass
        except Exception as e:
            logger.warning(f"First-frame auth error: {e}")

    if not auth_info:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Unauthorized")
        return

    # Register hub
    _connected_hubs[hub_id] = websocket
    _hub_info[hub_id] = {
        "connected_at": time.time(),
        "user_id": auth_info.get("user_id"),
        "earcons_cached": False,
    }

    logger.info(f"✓ Hub '{hub_id}' connected for audio streaming")

    try:
        # Send earcon cache
        await _send_earcon_cache(websocket, hub_id)

        # Subscribe to audio events
        from kagami.core.audio.event_bus import get_audio_bus

        bus = await get_audio_bus()

        # Create handlers that forward to this websocket
        async def handle_earcon(msg: dict[str, Any]) -> None:
            await _send_message(websocket, msg)

        async def handle_event(msg: dict[str, Any]) -> None:
            await _send_message(websocket, msg)

        async def handle_control(msg: dict[str, Any]) -> None:
            await _send_message(websocket, msg)

        async def handle_cache(msg: dict[str, Any]) -> None:
            await _send_message(websocket, msg)

        await bus.subscribe_earcons(handle_earcon)
        await bus.subscribe_events(handle_event)
        await bus.subscribe_control(handle_control)
        await bus.subscribe_cache(handle_cache)

        # Handle incoming messages from hub
        while True:
            try:
                data = await websocket.receive_json()
                await _handle_hub_message(hub_id, data)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Hub message error: {e}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Audio stream error: {e}")
    finally:
        # Cleanup
        _connected_hubs.pop(hub_id, None)
        _hub_info.pop(hub_id, None)
        logger.info(f"✗ Hub '{hub_id}' disconnected")


async def _send_earcon_cache(websocket: WebSocket, hub_id: str) -> None:
    """Send all earcons to hub for caching."""
    try:
        from kagami.core.audio.earcon_cache import get_earcon_cache
        from kagami.core.audio.protocol import encode_pcm_f32

        cache = await get_earcon_cache()

        for earcon in cache.list_all():
            msg = {
                "type": "cache_earcon",
                "name": earcon.name,
                "audio_data": encode_pcm_f32(earcon.audio),
                "metadata": {
                    "sample_rate": earcon.sample_rate,
                    "channels": earcon.channels,
                    "duration_ms": earcon.duration_ms,
                },
                "timestamp": time.time() * 1000,
            }
            await websocket.send_json(msg)
            # Small delay to not overwhelm
            await asyncio.sleep(0.005)

        _hub_info[hub_id]["earcons_cached"] = True
        _hub_info[hub_id]["earcons_count"] = len(cache.list_earcons())

        logger.info(f"Sent {len(cache.list_earcons())} earcons to hub '{hub_id}'")

    except Exception as e:
        logger.error(f"Failed to send earcon cache: {e}")


async def _send_message(websocket: WebSocket, message: dict[str, Any]) -> None:
    """Send message to websocket with error handling."""
    try:
        await websocket.send_json(message)
    except Exception as e:
        logger.warning(f"Failed to send message: {e}")


async def _handle_hub_message(hub_id: str, data: dict[str, Any]) -> None:
    """Handle incoming message from hub."""
    msg_type = data.get("type")

    if msg_type == "ack":
        # Acknowledgment of received audio
        logger.debug(f"Hub '{hub_id}' ack: {data.get('request_id')}")

    elif msg_type == "status":
        # Hub status update
        _hub_info[hub_id].update(data.get("status", {}))

    elif msg_type == "playback_complete":
        # Audio playback completed
        logger.debug(f"Hub '{hub_id}' completed: {data.get('request_id')}")

    elif msg_type == "error":
        # Hub reported error
        logger.warning(f"Hub '{hub_id}' error: {data.get('error')}")

    elif msg_type == "ping":
        # Keepalive
        ws = _connected_hubs.get(hub_id)
        if ws:
            await ws.send_json({"type": "pong", "timestamp": time.time() * 1000})


# =============================================================================
# HTTP ENDPOINTS
# =============================================================================


@router.get("/audio/hubs")
async def get_connected_hubs() -> dict[str, Any]:
    """Get list of connected hub devices."""
    return {
        "hubs": [
            {
                "hub_id": hub_id,
                "connected_at": info.get("connected_at"),
                "earcons_cached": info.get("earcons_cached", False),
                "earcons_count": info.get("earcons_count", 0),
            }
            for hub_id, info in _hub_info.items()
        ],
        "count": len(_connected_hubs),
    }


@router.post("/audio/broadcast/earcon/{name}")
async def broadcast_earcon(
    name: str,
    priority: int = 2,
    volume: float = 1.0,
    room: str | None = None,
) -> dict[str, Any]:
    """Broadcast earcon to all connected hubs.

    Args:
        name: Earcon name
        priority: 1=low, 2=normal, 3=high, 4=urgent
        volume: Volume (0.0-1.0)
        room: Target room (None for all)
    """
    from kagami.core.audio.event_bus import play_earcon
    from kagami.core.audio.protocol import AudioPriority

    request_id = await play_earcon(
        name,
        AudioPriority(priority),
        volume,
        room,
    )

    return {
        "success": True,
        "request_id": request_id,
        "earcon": name,
        "hubs_connected": len(_connected_hubs),
    }


@router.post("/audio/broadcast/stop")
async def broadcast_stop(
    stream_id: str | None = None,
    reason: str = "api",
) -> dict[str, Any]:
    """Stop audio playback on all connected hubs.

    Args:
        stream_id: Specific stream to stop (None for all)
        reason: Stop reason
    """
    from kagami.core.audio.event_bus import get_audio_bus

    bus = await get_audio_bus()
    await bus.stop_playback(stream_id, reason)

    return {
        "success": True,
        "stream_id": stream_id,
        "reason": reason,
        "hubs_connected": len(_connected_hubs),
    }


@router.get("/audio/stats")
async def get_audio_bus_stats() -> dict[str, Any]:
    """Get audio bus statistics."""
    from kagami.core.audio.event_bus import get_audio_bus

    bus = await get_audio_bus()
    return bus.get_stats()


@router.get("/audio/earcons")
async def get_earcon_cache_info() -> dict[str, Any]:
    """Get earcon cache information."""
    from kagami.core.audio.earcon_cache import get_earcon_cache

    cache = await get_earcon_cache()
    return cache.get_stats()


__all__ = ["router"]
