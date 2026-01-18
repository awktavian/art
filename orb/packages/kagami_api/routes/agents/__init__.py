"""Agent API Routes — Live Agent Runtime.

REST and WebSocket endpoints for markdown agents:
- GET /v1/agents — List all agents
- GET /v1/agents/{id} — Get agent state
- GET /v1/agents/{id}/render — Get HTML render
- POST /v1/agents/{id}/query — Query the agent
- POST /v1/agents/{id}/action — Trigger an action
- GET /v1/agents/{id}/secrets — Get found secrets
- POST /v1/agents/{id}/learn — Submit learning feedback
- WS /v1/ws/agent/{id} — Real-time bidirectional events
- WS /v1/voice/{id} — Per-agent voice interaction
- WS /v1/video/{id}/overlay — Real-time OBS overlays

Colony: Nexus (e4) — Integration
Created: January 7, 2026
鏡
"""

from fastapi import APIRouter

from kagami_api.routes.agents.core import router as agents_router
from kagami_api.routes.agents.video import router as video_router
from kagami_api.routes.agents.voice import router as voice_router
from kagami_api.routes.agents.websocket import router as ws_router


def get_router() -> APIRouter:
    """Get combined agents router with all endpoints."""
    router = APIRouter()

    # Include all agent-related routers
    router.include_router(agents_router)
    router.include_router(ws_router)
    router.include_router(voice_router)
    router.include_router(video_router)

    return router


# For direct access
router = get_router()

__all__ = [
    "agents_router",
    "ws_router",
    "voice_router",
    "video_router",
    "router",
    "get_router",
]
