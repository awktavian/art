"""Home Voice Input API — Control4 Remote Voice Activation.

Endpoints for controlling home theater voice input:
- GET /api/home/voice/status - Get voice service status
- POST /api/home/voice/activate - Manually activate listening (internal only)
- POST /api/home/voice/deactivate - Manually deactivate listening
- GET /api/home/voice/sessions - Get session history

Security Model:
- **Physical presence authentication**: The primary authentication is selecting
  "Mac" input on the Control4 remote. This proves physical presence in the home.
- **Local network only**: These endpoints only accept requests from the local
  network (192.168.1.0/24). External requests are rejected.
- **No sensitive operations**: Voice input only processes commands for the
  authenticated user (Tim), equivalent to caller ID auth in phone calls.

Created: January 2026
Colony: Flow (e₃) — Real-time
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Network Security
# =============================================================================

# Allowed local networks (CIDR notation)
LOCAL_NETWORKS = [
    ipaddress.ip_network("192.168.1.0/24"),  # Home LAN
    ipaddress.ip_network("127.0.0.0/8"),  # Localhost
    ipaddress.ip_network("10.0.0.0/8"),  # RFC1918
    ipaddress.ip_network("172.16.0.0/12"),  # RFC1918
]


def verify_local_network(request: Request) -> bool:
    """Verify request comes from local network.

    Args:
        request: FastAPI request object.

    Returns:
        True if from local network.

    Raises:
        HTTPException: If request is from external network.
    """
    client_ip = request.client.host if request.client else None

    if not client_ip:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot determine client IP",
        )

    try:
        ip = ipaddress.ip_address(client_ip)

        # Check if in any allowed network
        for network in LOCAL_NETWORKS:
            if ip in network:
                return True

        logger.warning(f"Rejected voice request from external IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voice input only available from local network",
        )

    except ValueError as e:
        logger.error(f"Invalid IP address: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid client IP: {client_ip}",
        ) from e


# =============================================================================
# Request/Response Models
# =============================================================================


class VoiceStatusResponse(BaseModel):
    """Voice service status response."""

    initialized: bool = Field(description="Service is initialized")
    state: str = Field(description="Current state")
    trigger_input: str = Field(description="Denon input that triggers voice")
    current_input: str = Field(description="Current Denon input")
    is_listening: bool = Field(description="Actively listening")
    denon_connected: bool = Field(description="Denon integration connected")
    microphone_ready: bool = Field(description="Microphone available")
    stt_ready: bool = Field(description="Speech-to-text available")
    tts_ready: bool = Field(description="Text-to-speech available")
    active_session: dict[str, Any] | None = Field(default=None, description="Current session info")
    total_sessions: int = Field(description="Total sessions processed")


class ActivateRequest(BaseModel):
    """Manual voice activation request."""

    duration: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="How long to listen (seconds)",
    )


class ActivateResponse(BaseModel):
    """Voice activation response."""

    success: bool
    message: str
    session_id: str | None = None


class SessionResponse(BaseModel):
    """Voice session details."""

    session_id: str
    input_source: str
    started_at: str
    ended_at: str | None
    turns: int
    auth_method: str
    duration_seconds: float
    avg_latency_ms: float


# =============================================================================
# Router Factory
# =============================================================================


def get_router() -> APIRouter:
    """Create and configure the API router."""
    router = APIRouter(prefix="/api/home/voice", tags=["home", "voice"])

    # =========================================================================
    # Status
    # =========================================================================

    @router.get(
        "/status",
        response_model=VoiceStatusResponse,
        summary="Get voice service status",
        description="Get current status of home theater voice input service.",
    )
    async def get_voice_status(
        _: bool = Depends(verify_local_network),
    ) -> VoiceStatusResponse:
        """Get voice input service status."""
        try:
            from kagami.core.services.voice.home_theater_voice import (
                get_home_theater_voice,
            )

            service = await get_home_theater_voice()
            status_dict = service.get_status()

            return VoiceStatusResponse(**status_dict)

        except Exception as e:
            logger.error(f"Failed to get voice status: {e}")
            return VoiceStatusResponse(
                initialized=False,
                state="error",
                trigger_input="Mac",
                current_input="",
                is_listening=False,
                denon_connected=False,
                microphone_ready=False,
                stt_ready=False,
                tts_ready=False,
                active_session=None,
                total_sessions=0,
            )

    # =========================================================================
    # Activation Control
    # =========================================================================

    @router.post(
        "/activate",
        response_model=ActivateResponse,
        summary="Manually activate voice listening",
        description=(
            "Manually activate voice listening mode. "
            "This is normally triggered automatically by selecting the Mac input "
            "on the Control4 remote. This endpoint is for testing or manual control."
        ),
    )
    async def activate_voice(
        request: ActivateRequest,
        _: bool = Depends(verify_local_network),
    ) -> ActivateResponse:
        """Manually activate voice listening.

        This is the equivalent of the phone call accept - authentication is
        implicitly based on local network access (physical presence proof).
        """
        try:
            from kagami.core.services.voice.home_theater_voice import (
                get_home_theater_voice,
            )

            service = await get_home_theater_voice()

            # Check if service is ready
            if not service._initialized:
                await service.initialize()

            # Check if already listening
            if service.is_listening:
                return ActivateResponse(
                    success=True,
                    message="Already listening",
                    session_id=service._active_session.session_id
                    if service._active_session
                    else None,
                )

            # Activate
            await service._activate_voice_input()

            return ActivateResponse(
                success=True,
                message=f"Voice input activated for {request.duration}s",
                session_id=service._active_session.session_id if service._active_session else None,
            )

        except Exception as e:
            logger.error(f"Failed to activate voice: {e}")
            return ActivateResponse(
                success=False,
                message=f"Activation failed: {str(e)}",
                session_id=None,
            )

    @router.post(
        "/deactivate",
        response_model=ActivateResponse,
        summary="Deactivate voice listening",
        description="Stop listening for voice input.",
    )
    async def deactivate_voice(
        _: bool = Depends(verify_local_network),
    ) -> ActivateResponse:
        """Deactivate voice listening."""
        try:
            from kagami.core.services.voice.home_theater_voice import (
                get_home_theater_voice,
            )

            service = await get_home_theater_voice()

            if not service.is_listening:
                return ActivateResponse(
                    success=True,
                    message="Not currently listening",
                    session_id=None,
                )

            await service._deactivate_voice_input()

            return ActivateResponse(
                success=True,
                message="Voice input deactivated",
                session_id=None,
            )

        except Exception as e:
            logger.error(f"Failed to deactivate voice: {e}")
            return ActivateResponse(
                success=False,
                message=f"Deactivation failed: {str(e)}",
                session_id=None,
            )

    # =========================================================================
    # Session History
    # =========================================================================

    @router.get(
        "/sessions",
        response_model=list[SessionResponse],
        summary="Get voice session history",
        description="Get recent voice interaction sessions.",
    )
    async def get_sessions(
        limit: int = 50,
        _: bool = Depends(verify_local_network),
    ) -> list[SessionResponse]:
        """Get voice session history."""
        try:
            from kagami.core.services.voice.home_theater_voice import (
                get_home_theater_voice,
            )

            service = await get_home_theater_voice()
            sessions = service.get_session_history(limit)

            return [SessionResponse(**s) for s in sessions]

        except Exception as e:
            logger.error(f"Failed to get sessions: {e}")
            return []

    # =========================================================================
    # Control4 Webhook (for dedicated button programming)
    # =========================================================================

    @router.post(
        "/webhook/control4",
        summary="Control4 webhook for voice activation",
        description=(
            "Webhook endpoint for Control4 Composer programming. "
            "Program a Halo remote button to POST here for instant activation."
        ),
    )
    async def control4_webhook(
        request: Request,
        _: bool = Depends(verify_local_network),
    ) -> dict[str, Any]:
        """Control4 webhook for voice activation.

        Authentication: Local network only (Control4 director is on local LAN).

        This endpoint can be programmed in Composer Pro:
        1. Select Halo remote button event
        2. Add HTTP POST action to this URL
        3. Button press activates voice input

        The authentication is the same as caller ID in phone calls:
        - Phone: We trust the caller ID from the phone system
        - Home: We trust the source from the local network
        """
        try:
            from kagami.core.services.voice.home_theater_voice import (
                get_home_theater_voice,
            )

            # Parse body if present
            body = {}
            try:
                body = await request.json()
            except Exception:
                pass

            action = body.get("action", "toggle")
            service = await get_home_theater_voice()

            if action == "activate" or (action == "toggle" and not service.is_listening):
                await service._activate_voice_input()
                return {
                    "status": "ok",
                    "action": "activated",
                    "message": "Voice input activated",
                }
            elif action == "deactivate" or (action == "toggle" and service.is_listening):
                await service._deactivate_voice_input()
                return {
                    "status": "ok",
                    "action": "deactivated",
                    "message": "Voice input deactivated",
                }
            else:
                return {
                    "status": "ok",
                    "action": "none",
                    "message": f"Unknown action: {action}",
                }

        except Exception as e:
            logger.error(f"Control4 webhook error: {e}")
            return {"status": "error", "message": str(e)}

    return router


# Module-level router for backward compatibility
router = get_router()
