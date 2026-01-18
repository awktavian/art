"""Agent Video — Real-time OBS overlays and video production.

WebSocket endpoint for video overlay data:
- Speaker badges (who's talking)
- Live/Recording indicators
- Section activity meters
- Word-level highlighting
- Real-time VFX triggers

Protocol:
    Server → Client: JSON overlay data
    Client: Renders overlays in OBS browser source

Colony: Forge (e2) — Building
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

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from kagami.core.agents import get_agent_registry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents-video"])


# =============================================================================
# Overlay Types
# =============================================================================


class OverlayType(str, Enum):
    """Types of overlay updates."""

    SPEAKER_BADGE = "speaker_badge"
    LIVE_INDICATOR = "live_indicator"
    SECTION_METER = "section_meter"
    WORD_HIGHLIGHT = "word_highlight"
    NOTIFICATION = "notification"
    CUSTOM = "custom"


# =============================================================================
# Connection Management
# =============================================================================


@dataclass
class OverlayConnection:
    """Represents a video overlay WebSocket connection."""

    websocket: WebSocket
    agent_id: str
    session_id: str
    connected_at: float = field(default_factory=time.time)

    async def send(self, overlay_type: OverlayType, data: dict[str, Any]) -> None:
        """Send overlay update to client."""
        message = {
            "type": overlay_type.value,
            "timestamp": time.time(),
            **data,
        }
        await self.websocket.send_text(json.dumps(message))


class OverlayManager:
    """Manages video overlay connections."""

    def __init__(self) -> None:
        self.connections: dict[str, list[OverlayConnection]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, agent_id: str, session_id: str
    ) -> OverlayConnection:
        """Add a new overlay connection."""
        await websocket.accept()

        conn = OverlayConnection(
            websocket=websocket,
            agent_id=agent_id,
            session_id=session_id,
        )

        async with self._lock:
            if agent_id not in self.connections:
                self.connections[agent_id] = []
            self.connections[agent_id].append(conn)

        return conn

    async def disconnect(self, conn: OverlayConnection) -> None:
        """Remove a connection."""
        async with self._lock:
            if conn.agent_id in self.connections:
                self.connections[conn.agent_id] = [
                    c for c in self.connections[conn.agent_id] if c.session_id != conn.session_id
                ]

    async def broadcast(
        self, agent_id: str, overlay_type: OverlayType, data: dict[str, Any]
    ) -> None:
        """Broadcast overlay update to all connections for an agent."""
        conns = self.connections.get(agent_id, [])
        await asyncio.gather(
            *[conn.send(overlay_type, data) for conn in conns],
            return_exceptions=True,
        )


# Global overlay manager
overlay_manager = OverlayManager()


# =============================================================================
# WebSocket Endpoint
# =============================================================================


@router.websocket("/v1/video/{agent_id}/overlay")
async def video_overlay_stream(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for real-time OBS overlay data.

    Sends overlay updates that can be rendered by OBS browser source:
    - Speaker badges (name, color, speaking indicator)
    - Live/Recording status
    - Section activity meters (audio-reactive)
    - Word-level highlighting for captions
    - Notification toasts

    Usage in OBS:
    1. Add Browser Source
    2. Point to: https://api.awkronos.com/v1/video/{agent_id}/overlay/render
    3. The page connects to this WebSocket and renders overlays
    """
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        await websocket.close(code=4004, reason=f"Agent not found: {agent_id}")
        return

    session_id = f"overlay_{agent_id}_{int(time.time() * 1000)}"
    conn = await overlay_manager.connect(websocket, agent_id, session_id)

    logger.info(f"🎬 Overlay stream started: {agent_id}/{session_id}")

    # Send initial overlay config
    overlay_config = agent.schema.i_produce.overlays
    await conn.send(
        OverlayType.CUSTOM,
        {
            "action": "init",
            "config": {
                "speaker_badge": overlay_config.speaker_badge,
                "live_indicator": overlay_config.live_indicator,
                "section_meters": overlay_config.section_meters,
                "word_highlight": overlay_config.word_highlight,
            },
            "palette": agent.schema.i_embody.palette.model_dump(),
        },
    )

    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle ping
            if message.get("type") == "ping":
                await conn.send(OverlayType.CUSTOM, {"action": "pong"})

    except WebSocketDisconnect:
        logger.info(f"🎬 Overlay stream ended: {session_id}")
    except Exception as e:
        logger.error(f"🎬 Overlay stream error: {e}")
    finally:
        await overlay_manager.disconnect(conn)


# =============================================================================
# REST Endpoints
# =============================================================================


@router.get("/v1/video/{agent_id}/overlay/render", response_class=HTMLResponse)
async def render_overlay_page(agent_id: str) -> HTMLResponse:
    """Get HTML page for OBS browser source.

    This page connects to the overlay WebSocket and renders overlays.
    Add as Browser Source in OBS pointed to this URL.
    """
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    palette = agent.schema.i_embody.palette

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{agent.schema.i_am.name} Overlay</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: transparent;
            font-family: 'IBM Plex Sans', -apple-system, sans-serif;
            color: {palette.text};
            overflow: hidden;
        }}

        /* Speaker Badge */
        .speaker-badge {{
            position: fixed;
            bottom: 20px;
            left: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 20px;
            background: rgba(0, 0, 0, 0.7);
            border-radius: 8px;
            border-left: 4px solid var(--speaker-color, {palette.accent});
            opacity: 0;
            transform: translateY(20px);
            transition: opacity 0.3s, transform 0.3s;
        }}
        .speaker-badge.visible {{
            opacity: 1;
            transform: translateY(0);
        }}
        .speaker-badge.speaking {{
            border-left-color: {palette.success};
        }}
        .speaker-name {{
            font-size: 18px;
            font-weight: 600;
        }}
        .speaker-title {{
            font-size: 14px;
            color: {palette.muted};
        }}
        .speaking-indicator {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: {palette.muted};
            transition: background 0.2s;
        }}
        .speaker-badge.speaking .speaking-indicator {{
            background: {palette.success};
            animation: pulse 1s infinite;
        }}

        /* Live Indicator */
        .live-indicator {{
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: {palette.error};
            border-radius: 4px;
            font-weight: 700;
            font-size: 14px;
            text-transform: uppercase;
            opacity: 0;
            transition: opacity 0.3s;
        }}
        .live-indicator.visible {{
            opacity: 1;
        }}
        .live-indicator.recording {{
            background: {palette.warning};
        }}
        .live-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: white;
            animation: pulse 1s infinite;
        }}

        /* Section Meters */
        .section-meters {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            display: flex;
            gap: 4px;
            height: 60px;
            align-items: flex-end;
        }}
        .meter-bar {{
            width: 8px;
            background: {palette.accent};
            border-radius: 2px;
            transition: height 0.1s ease-out;
        }}

        /* Word Highlight */
        .word-highlight {{
            position: fixed;
            bottom: 100px;
            left: 50%;
            transform: translateX(-50%);
            padding: 16px 32px;
            background: rgba(0, 0, 0, 0.8);
            border-radius: 8px;
            font-size: 24px;
            text-align: center;
            max-width: 80%;
            opacity: 0;
            transition: opacity 0.2s;
        }}
        .word-highlight.visible {{
            opacity: 1;
        }}
        .word-highlight .current {{
            color: {palette.accent};
            font-weight: 600;
        }}

        /* Notification */
        .notification {{
            position: fixed;
            top: 80px;
            right: 20px;
            padding: 16px 24px;
            background: rgba(0, 0, 0, 0.8);
            border-radius: 8px;
            border-left: 4px solid {palette.accent};
            opacity: 0;
            transform: translateX(100%);
            transition: opacity 0.3s, transform 0.3s;
        }}
        .notification.visible {{
            opacity: 1;
            transform: translateX(0);
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
    </style>
</head>
<body>
    <!-- Speaker Badge -->
    <div class="speaker-badge" id="speaker-badge">
        <div class="speaking-indicator"></div>
        <div>
            <div class="speaker-name" id="speaker-name">Speaker</div>
            <div class="speaker-title" id="speaker-title">Title</div>
        </div>
    </div>

    <!-- Live Indicator -->
    <div class="live-indicator" id="live-indicator">
        <div class="live-dot"></div>
        <span id="live-text">LIVE</span>
    </div>

    <!-- Section Meters -->
    <div class="section-meters" id="section-meters">
        <!-- Dynamically generated -->
    </div>

    <!-- Word Highlight -->
    <div class="word-highlight" id="word-highlight">
        <span id="word-text"></span>
    </div>

    <!-- Notification -->
    <div class="notification" id="notification">
        <span id="notification-text"></span>
    </div>

    <script>
    const AGENT_ID = '{agent_id}';
    const WS_URL = `wss://${{location.host}}/v1/video/${{AGENT_ID}}/overlay`;

    let ws;
    let reconnectTimer;

    function connect() {{
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {{
            console.log('Overlay connected');
        }};

        ws.onmessage = (event) => {{
            const data = JSON.parse(event.data);
            handleOverlay(data);
        }};

        ws.onclose = () => {{
            console.log('Overlay disconnected, reconnecting...');
            reconnectTimer = setTimeout(connect, 3000);
        }};

        ws.onerror = (err) => {{
            console.error('WebSocket error:', err);
        }};
    }}

    function handleOverlay(data) {{
        switch (data.type) {{
            case 'speaker_badge':
                updateSpeakerBadge(data);
                break;
            case 'live_indicator':
                updateLiveIndicator(data);
                break;
            case 'section_meter':
                updateSectionMeters(data);
                break;
            case 'word_highlight':
                updateWordHighlight(data);
                break;
            case 'notification':
                showNotification(data);
                break;
            case 'custom':
                if (data.action === 'init') {{
                    initOverlays(data.config);
                }}
                break;
        }}
    }}

    function updateSpeakerBadge(data) {{
        const badge = document.getElementById('speaker-badge');
        const name = document.getElementById('speaker-name');
        const title = document.getElementById('speaker-title');

        if (data.visible) {{
            name.textContent = data.name || 'Speaker';
            title.textContent = data.title || '';
            badge.style.setProperty('--speaker-color', data.color || '{palette.accent}');
            badge.classList.toggle('speaking', data.speaking || false);
            badge.classList.add('visible');
        }} else {{
            badge.classList.remove('visible');
        }}
    }}

    function updateLiveIndicator(data) {{
        const indicator = document.getElementById('live-indicator');
        const text = document.getElementById('live-text');

        if (data.visible) {{
            text.textContent = data.recording ? 'REC' : 'LIVE';
            indicator.classList.toggle('recording', data.recording || false);
            indicator.classList.add('visible');
        }} else {{
            indicator.classList.remove('visible');
        }}
    }}

    function updateSectionMeters(data) {{
        const container = document.getElementById('section-meters');
        const values = data.values || [];

        // Create/update meter bars
        while (container.children.length < values.length) {{
            const bar = document.createElement('div');
            bar.className = 'meter-bar';
            container.appendChild(bar);
        }}

        for (let i = 0; i < values.length; i++) {{
            const bar = container.children[i];
            const height = Math.max(4, Math.min(60, values[i] * 60));
            bar.style.height = height + 'px';
        }}
    }}

    function updateWordHighlight(data) {{
        const highlight = document.getElementById('word-highlight');
        const text = document.getElementById('word-text');

        if (data.visible && data.words) {{
            // Build HTML with current word highlighted
            const html = data.words.map((word, i) => {{
                if (i === data.currentIndex) {{
                    return `<span class="current">${{word}}</span>`;
                }}
                return word;
            }}).join(' ');

            text.innerHTML = html;
            highlight.classList.add('visible');
        }} else {{
            highlight.classList.remove('visible');
        }}
    }}

    function showNotification(data) {{
        const notification = document.getElementById('notification');
        const text = document.getElementById('notification-text');

        text.textContent = data.message || '';
        notification.classList.add('visible');

        setTimeout(() => {{
            notification.classList.remove('visible');
        }}, data.duration || 3000);
    }}

    function initOverlays(config) {{
        // Hide disabled overlays
        if (!config.speaker_badge) {{
            document.getElementById('speaker-badge').style.display = 'none';
        }}
        if (!config.live_indicator) {{
            document.getElementById('live-indicator').style.display = 'none';
        }}
        if (!config.section_meters) {{
            document.getElementById('section-meters').style.display = 'none';
        }}
        if (!config.word_highlight) {{
            document.getElementById('word-highlight').style.display = 'none';
        }}
    }}

    // Start connection
    connect();

    // Send ping every 30s
    setInterval(() => {{
        if (ws && ws.readyState === WebSocket.OPEN) {{
            ws.send(JSON.stringify({{ type: 'ping' }}));
        }}
    }}, 30000);
    </script>
</body>
</html>"""

    return HTMLResponse(content=html)


@router.get("/v1/video/{agent_id}/scene/{scene_name}")
async def get_scene_config(agent_id: str, scene_name: str) -> dict[str, Any]:
    """Get configuration for a specific scene.

    Args:
        agent_id: Agent identifier.
        scene_name: Scene name.

    Returns:
        Scene configuration.
    """
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # Find scene in agent's config
    for scene in agent.schema.i_produce.obs_integration.scenes:
        if scene.name == scene_name:
            return {
                "name": scene.name,
                "sources": scene.sources,
                "transitions": scene.transitions,
            }

    raise HTTPException(status_code=404, detail=f"Scene not found: {scene_name}")


@router.post("/v1/video/{agent_id}/trigger")
async def trigger_video_effect(agent_id: str, effect: dict[str, Any]) -> dict[str, Any]:
    """Trigger a video effect.

    Broadcasts effect to all connected overlay clients.

    Args:
        agent_id: Agent identifier.
        effect: Effect configuration.

    Returns:
        Trigger result.
    """
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    effect_type = effect.get("type", "notification")

    # Map effect types to overlay types
    overlay_type_map = {
        "speaker": OverlayType.SPEAKER_BADGE,
        "live": OverlayType.LIVE_INDICATOR,
        "meter": OverlayType.SECTION_METER,
        "word": OverlayType.WORD_HIGHLIGHT,
        "notification": OverlayType.NOTIFICATION,
    }

    overlay_type = overlay_type_map.get(effect_type, OverlayType.CUSTOM)
    await overlay_manager.broadcast(agent_id, overlay_type, effect)

    return {"triggered": True, "type": effect_type}


# =============================================================================
# Broadcast Utilities
# =============================================================================


async def update_speaker_badge(
    agent_id: str,
    name: str,
    title: str = "",
    color: str = "",
    speaking: bool = False,
    visible: bool = True,
) -> None:
    """Update speaker badge overlay.

    Args:
        agent_id: Agent identifier.
        name: Speaker name.
        title: Speaker title.
        color: Badge color.
        speaking: Whether currently speaking.
        visible: Whether badge is visible.
    """
    await overlay_manager.broadcast(
        agent_id,
        OverlayType.SPEAKER_BADGE,
        {
            "name": name,
            "title": title,
            "color": color,
            "speaking": speaking,
            "visible": visible,
        },
    )


async def update_live_indicator(
    agent_id: str,
    visible: bool = True,
    recording: bool = False,
) -> None:
    """Update live/recording indicator.

    Args:
        agent_id: Agent identifier.
        visible: Whether indicator is visible.
        recording: True for REC, False for LIVE.
    """
    await overlay_manager.broadcast(
        agent_id,
        OverlayType.LIVE_INDICATOR,
        {"visible": visible, "recording": recording},
    )


async def update_section_meters(agent_id: str, values: list[float]) -> None:
    """Update audio section meters.

    Args:
        agent_id: Agent identifier.
        values: List of meter values (0-1).
    """
    await overlay_manager.broadcast(
        agent_id,
        OverlayType.SECTION_METER,
        {"values": values},
    )


async def update_word_highlight(
    agent_id: str,
    words: list[str],
    current_index: int,
    visible: bool = True,
) -> None:
    """Update word-level highlight for captions.

    Args:
        agent_id: Agent identifier.
        words: List of words.
        current_index: Index of currently highlighted word.
        visible: Whether highlight is visible.
    """
    await overlay_manager.broadcast(
        agent_id,
        OverlayType.WORD_HIGHLIGHT,
        {"words": words, "currentIndex": current_index, "visible": visible},
    )


async def show_notification(
    agent_id: str,
    message: str,
    duration: int = 3000,
) -> None:
    """Show notification toast.

    Args:
        agent_id: Agent identifier.
        message: Notification message.
        duration: Duration in milliseconds.
    """
    await overlay_manager.broadcast(
        agent_id,
        OverlayType.NOTIFICATION,
        {"message": message, "duration": duration},
    )


# =============================================================================
# Router Factory
# =============================================================================


def get_video_router() -> APIRouter:
    """Get the video overlay router."""
    return router


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "router",
    "overlay_manager",
    "update_speaker_badge",
    "update_live_indicator",
    "update_section_meters",
    "update_word_highlight",
    "show_notification",
    "get_video_router",
]
