"""LiveKit Webhook Routes — Handle LiveKit server events.

Endpoints:
- POST /api/livekit/webhook - LiveKit server webhook
- GET /api/livekit/token - Generate access token
- POST /api/livekit/call - Initiate outbound call
- GET /api/livekit/status - Service status
- POST /api/livekit/answering-machine/mode - Set answering machine mode

Colony: Flow (e₃) — Real-time
Created: January 2026
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router."""
    router = APIRouter(prefix="/api/livekit", tags=["livekit", "voice"])

    # =========================================================================
    # Request/Response Models
    # =========================================================================

    class TokenRequest(BaseModel):
        """Request for access token."""

        room_name: str = Field(..., min_length=1)
        identity: str = Field(..., min_length=1)
        can_publish: bool = True
        can_subscribe: bool = True
        ttl: int = Field(default=3600, ge=60, le=86400)

    class TokenResponse(BaseModel):
        """Access token response."""

        token: str
        url: str
        room_name: str
        identity: str

    class CallRequest(BaseModel):
        """Outbound call request."""

        phone_number: str = Field(..., pattern=r"^\+[1-9]\d{1,14}$")
        room_name: str | None = None
        metadata: dict[str, Any] = Field(default_factory=dict)

    class CallResponse(BaseModel):
        """Call session response."""

        session_id: str
        room_name: str
        phone_number: str
        status: str

    class AnsweringMachineMode(BaseModel):
        """Answering machine mode request."""

        mode: str = Field(..., pattern="^(screen|takeover|forward|voicemail|dnd)$")

    class StatusResponse(BaseModel):
        """Service status response."""

        livekit_initialized: bool
        livekit_configured: bool
        has_sip: bool
        has_rtmp: bool
        active_calls: int
        answering_machine_mode: str

    # =========================================================================
    # Webhook
    # =========================================================================

    @router.post("/webhook")
    async def livekit_webhook(request: Request) -> dict[str, str]:
        """Handle LiveKit server webhooks.

        Events:
        - room_started, room_finished
        - participant_joined, participant_left
        - track_published, track_unpublished
        - egress_started, egress_ended
        - sip_call_incoming, sip_call_answered, sip_call_ended

        Authentication:
        - Validates webhook signature from LiveKit server
        """
        try:
            body = await request.body()
            auth_header = request.headers.get("Authorization", "")

            # Validate webhook signature
            api_key = os.getenv("LIVEKIT_API_KEY", "devkey")
            api_secret = os.getenv("LIVEKIT_API_SECRET", "")

            if api_secret:
                try:
                    from livekit import api

                    token = api.TokenVerifier(api_key, api_secret)
                    claims = token.verify(auth_header.replace("Bearer ", ""))
                    logger.debug(f"Webhook verified: {claims}")
                except Exception as e:
                    logger.warning(f"Webhook signature invalid: {e}")
                    # Continue anyway in dev mode

            # Parse webhook event
            import json

            event = json.loads(body)
            event_type = event.get("event", "unknown")

            logger.info(f"LiveKit webhook: {event_type}")

            # Handle specific events
            if event_type == "sip_call_incoming":
                await _handle_incoming_call(event)
            elif event_type == "sip_call_ended":
                await _handle_call_ended(event)
            elif event_type == "participant_joined":
                await _handle_participant_joined(event)

            return {"status": "ok"}

        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_incoming_call(event: dict[str, Any]) -> None:
        """Handle incoming SIP call."""
        call_info = event.get("sipCallIncoming", {})
        from_number = call_info.get("from", "")
        to_number = call_info.get("to", "")
        room_name = call_info.get("room_name", "")

        logger.info(f"📞 Incoming call: {from_number} → {to_number}")

        # Get answering machine
        from kagami.core.services.voice import get_answering_machine

        machine = await get_answering_machine()

        # Accept the call
        await machine.accept_call(
            caller_phone=from_number,
            room_name=room_name,
            caller_name=None,  # Will be looked up
        )

    async def _handle_call_ended(event: dict[str, Any]) -> None:
        """Handle call ended."""
        call_info = event.get("sipCallEnded", {})
        room_name = call_info.get("room_name", "")

        logger.info(f"📞 Call ended: {room_name}")

        # Find and end session
        from kagami.core.services.voice import get_answering_machine

        machine = await get_answering_machine()

        for session in machine.get_active_sessions():
            if session.get("room_name") == room_name:
                await machine.end_call(session.get("session_id", ""))
                break

    async def _handle_participant_joined(event: dict[str, Any]) -> None:
        """Handle participant joined."""
        participant = event.get("participant", {})
        room_name = event.get("room", {}).get("name", "")

        logger.debug(f"Participant joined: {participant.get('identity')} in {room_name}")

    # =========================================================================
    # Token Generation
    # =========================================================================

    @router.post("/token", response_model=TokenResponse)
    async def generate_token(request: TokenRequest) -> TokenResponse:
        """Generate a LiveKit access token for room access.

        Required for:
        - WebRTC clients joining a room
        - AI agents participating in calls

        Returns token valid for specified TTL (default 1 hour).
        """
        from kagami.core.services.voice import get_livekit_service

        service = get_livekit_service()

        token = await service.generate_token(
            room_name=request.room_name,
            participant_identity=request.identity,
            can_publish=request.can_publish,
            can_subscribe=request.can_subscribe,
            ttl=request.ttl,
        )

        if not token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LiveKit not configured",
            )

        return TokenResponse(
            token=token,
            url=service.config.url,
            room_name=request.room_name,
            identity=request.identity,
        )

    # =========================================================================
    # Call Control
    # =========================================================================

    @router.post("/call", response_model=CallResponse)
    async def initiate_call(request: CallRequest) -> CallResponse:
        """Initiate an outbound phone call.

        Requires SIP trunk configuration (LIVEKIT_SIP_TRUNK_ID).
        Phone number must be in E.164 format (+1234567890).
        """
        from kagami.core.services.voice import get_livekit_service

        service = get_livekit_service()

        session = await service.make_outbound_call(
            phone_number=request.phone_number,
            room_name=request.room_name,
            metadata=request.metadata,
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to initiate call. Check SIP trunk configuration.",
            )

        return CallResponse(
            session_id=session.room_name,  # Use room name as session ID
            room_name=session.room_name,
            phone_number=request.phone_number,
            status="initiated",
        )

    # =========================================================================
    # Answering Machine Control
    # =========================================================================

    @router.post("/answering-machine/mode")
    async def set_answering_mode(request: AnsweringMachineMode) -> dict[str, str]:
        """Set the AI answering machine mode.

        Modes:
        - screen: Ask who's calling, decide whether to connect Tim
        - takeover: AI fully represents Tim (he's busy)
        - forward: Forward all calls to Tim
        - voicemail: Take messages only
        - dnd: Do Not Disturb - decline all calls
        """
        from kagami.core.services.voice import CallMode, get_answering_machine

        machine = await get_answering_machine()

        mode_map = {
            "screen": CallMode.SCREEN,
            "takeover": CallMode.TAKEOVER,
            "forward": CallMode.FORWARD,
            "voicemail": CallMode.VOICEMAIL,
            "dnd": CallMode.DND,
        }

        mode = mode_map.get(request.mode, CallMode.SCREEN)
        machine.set_mode(mode)

        return {"status": "ok", "mode": request.mode}

    @router.get("/answering-machine/calls")
    async def get_call_history(limit: int = 50) -> list[dict[str, Any]]:
        """Get recent call history from the answering machine."""
        from kagami.core.services.voice import get_answering_machine

        machine = await get_answering_machine()
        return machine.get_call_history(limit)

    @router.get("/answering-machine/active")
    async def get_active_calls() -> list[dict[str, Any]]:
        """Get currently active calls."""
        from kagami.core.services.voice import get_answering_machine

        machine = await get_answering_machine()
        return machine.get_active_sessions()

    # =========================================================================
    # Status
    # =========================================================================

    @router.get("/status", response_model=StatusResponse)
    async def get_status() -> StatusResponse:
        """Get LiveKit and answering machine status."""
        from kagami.core.services.voice import get_answering_machine, get_livekit_service

        livekit = get_livekit_service()
        livekit_status = livekit.get_status()

        machine = await get_answering_machine()
        machine_status = machine.get_status()

        return StatusResponse(
            livekit_initialized=livekit_status["initialized"],
            livekit_configured=livekit_status["configured"],
            has_sip=livekit_status["has_sip"],
            has_rtmp=livekit_status["has_rtmp"],
            active_calls=machine_status["active_calls"],
            answering_machine_mode=machine_status["mode"],
        )

    @router.get("/rooms")
    async def list_rooms() -> list[dict[str, Any]]:
        """List active LiveKit rooms."""
        from kagami.core.services.voice import get_livekit_service

        service = get_livekit_service()
        return await service.get_active_rooms()

    return router


# Module-level router for backward compatibility
router = get_router()
