"""Audio Routes — Announcements, Voice Control.

~100 LOC — well within 500 LOC limit.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

# Import command schemas from single source of truth
from kagami_smarthome.schemas.commands import AnnounceCommand

from .core import get_controller

router = APIRouter()


# =============================================================================
# ANNOUNCEMENTS
# =============================================================================


@router.post("/announce")
async def announce(cmd: AnnounceCommand) -> dict[str, Any]:
    """Announce a message via Parler-TTS.

    Audio plays through Mac output → Control4/Denon handles room routing.
    Uses colony voices for distinct personalities.
    """
    controller = await get_controller()
    result = await controller.announce(
        text=cmd.text,
        rooms=cmd.rooms,
        volume=cmd.volume,
        colony=cmd.colony,
    )
    return {"success": result, "text": cmd.text, "rooms": cmd.rooms, "colony": cmd.colony}


@router.post("/announce-all")
async def announce_all(cmd: AnnounceCommand) -> dict[str, Any]:
    """Announce to all rooms (broadcasts through all audio zones)."""
    controller = await get_controller()
    result = await controller.announce_all(
        text=cmd.text,
        volume=cmd.volume,
        colony=cmd.colony,
    )
    return {"success": result, "text": cmd.text, "colony": cmd.colony}


@router.get("/audio/voices")
async def get_available_voices() -> dict[str, Any]:
    """Get available colony voices for announcements."""
    return {
        "voices": ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal", "kagami"],
        "default": "kagami",
        "descriptions": {
            "kagami": "Neutral, balanced - the observer",
            "spark": "Bright, energetic, enthusiastic",
            "forge": "Focused, determined, precise",
            "flow": "Calm, gentle, soothing",
            "nexus": "Warm, connecting, relational",
            "beacon": "Clear, guiding, organized",
            "grove": "Curious, exploratory, thoughtful",
            "crystal": "Precise, analytical, verifying",
        },
    }


@router.get("/audio/stats")
async def get_audio_stats() -> dict[str, Any]:
    """Get audio bridge statistics and latency metrics."""
    controller = await get_controller()
    if hasattr(controller, "_audio_bridge") and controller._audio_bridge:
        return controller._audio_bridge.get_stats()
    return {"initialized": False, "announcements": 0, "avg_latency_ms": 0}
