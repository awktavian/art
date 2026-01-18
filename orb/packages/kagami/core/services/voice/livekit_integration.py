"""LiveKit Integration for Bidirectional Voice/Video AI.

Provides:
- SIP trunk integration for phone calls
- WebRTC for browser/mobile video
- RTMP egress for OBS recording
- AI agent framework integration

Colony: Nexus (e4) — Integration
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    """Low-level connection type for LiveKit.

    This is the transport mechanism, not the call type.
    For user-facing call types, see realtime.CallType.
    """

    PSTN = "pstn"  # Traditional phone via SIP
    WEBRTC = "webrtc"  # Browser/mobile via WebRTC
    SIP_DIRECT = "sip"  # Direct SIP endpoint


# Alias for backwards compatibility (will be removed)
CallType = ConnectionType


class StreamType(Enum):
    """Output stream type."""

    RTMP = "rtmp"  # OBS, YouTube, Twitch
    HLS = "hls"  # Web playback
    RECORDING = "recording"  # File recording


@dataclass
class LiveKitConfig:
    """LiveKit configuration."""

    # Server
    url: str = field(default_factory=lambda: os.getenv("LIVEKIT_URL", "wss://kagami.livekit.cloud"))
    api_key: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_SECRET", ""))

    # SIP Trunk for phone integration
    sip_trunk_id: str = field(default_factory=lambda: os.getenv("LIVEKIT_SIP_TRUNK_ID", ""))

    # Egress (OBS integration)
    rtmp_url: str = field(default_factory=lambda: os.getenv("LIVEKIT_RTMP_URL", ""))

    @property
    def is_configured(self) -> bool:
        """Check if LiveKit is properly configured."""
        return bool(self.url and self.api_key and self.api_secret)

    @property
    def has_sip(self) -> bool:
        """Check if SIP trunk is configured for phone calls."""
        return bool(self.sip_trunk_id)


@dataclass
class CallSession:
    """Active call session."""

    room_name: str
    participant_identity: str
    call_type: CallType
    phone_number: str | None = None
    started_at: float = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class LiveKitService:
    """LiveKit service for voice/video AI.

    Provides bidirectional communication via:
    - Phone (PSTN) via SIP trunk
    - Browser/mobile via WebRTC
    - OBS/streaming via RTMP egress
    """

    def __init__(self, config: LiveKitConfig | None = None):
        self.config = config or LiveKitConfig()
        self._room_service = None
        self._sip_service = None
        self._egress_service = None
        self._initialized = False
        self._active_sessions: dict[str, CallSession] = {}

    async def initialize(self) -> bool:
        """Initialize LiveKit services."""
        if not self.config.is_configured:
            logger.warning(
                "LiveKit not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET"
            )
            return False

        try:
            from livekit import api

            self._room_service = api.RoomServiceClient(
                self.config.url.replace("wss://", "https://").replace("ws://", "http://"),
                self.config.api_key,
                self.config.api_secret,
            )

            self._sip_service = api.SIPServiceClient(
                self.config.url.replace("wss://", "https://").replace("ws://", "http://"),
                self.config.api_key,
                self.config.api_secret,
            )

            self._egress_service = api.EgressServiceClient(
                self.config.url.replace("wss://", "https://").replace("ws://", "http://"),
                self.config.api_key,
                self.config.api_secret,
            )

            self._initialized = True
            logger.info("LiveKit service initialized")
            return True

        except ImportError:
            logger.error("LiveKit SDK not installed. Run: pip install livekit livekit-agents")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize LiveKit: {e}")
            return False

    # =========================================================================
    # Phone Integration (SIP/PSTN)
    # =========================================================================

    async def make_outbound_call(
        self,
        phone_number: str,
        room_name: str | None = None,
        participant_identity: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CallSession | None:
        """Place an outbound phone call.

        Args:
            phone_number: E.164 format (+1234567890)
            room_name: Optional room name (auto-generated if not provided)
            participant_identity: Optional identity for the caller
            metadata: Additional metadata for the call

        Returns:
            CallSession if successful, None otherwise
        """
        if not self._initialized:
            await self.initialize()

        if not self.config.has_sip:
            logger.error("SIP trunk not configured. Set LIVEKIT_SIP_TRUNK_ID")
            return None

        try:
            import secrets
            import time

            from livekit import api

            room_name = room_name or f"call-{secrets.token_hex(8)}"
            participant_identity = participant_identity or phone_number

            # Create the call
            await self._sip_service.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=room_name,
                    sip_trunk_id=self.config.sip_trunk_id,
                    sip_call_to=phone_number,
                    participant_identity=participant_identity,
                    wait_until_answered=True,
                )
            )

            session = CallSession(
                room_name=room_name,
                participant_identity=participant_identity,
                call_type=CallType.PSTN,
                phone_number=phone_number,
                started_at=time.time(),
                metadata=metadata or {},
            )

            self._active_sessions[room_name] = session
            logger.info(f"Outbound call placed to {phone_number[:6]}***")

            return session

        except Exception as e:
            logger.error(f"Failed to place outbound call: {e}")
            return None

    async def transfer_call(
        self,
        room_name: str,
        participant_identity: str,
        transfer_to: str,
    ) -> bool:
        """Transfer an active call to another number.

        Args:
            room_name: The room containing the call
            participant_identity: Identity of participant to transfer
            transfer_to: Phone number or SIP URI to transfer to

        Returns:
            True if transfer initiated successfully
        """
        if not self._initialized:
            return False

        try:
            from livekit import api

            # Format transfer destination
            if transfer_to.startswith("+"):
                transfer_to = f"tel:{transfer_to}"
            elif not transfer_to.startswith("sip:"):
                transfer_to = f"tel:{transfer_to}"

            await self._sip_service.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=room_name,
                    participant_identity=participant_identity,
                    transfer_to=transfer_to,
                )
            )

            logger.info(f"Call transferred to {transfer_to}")
            return True

        except Exception as e:
            logger.error(f"Failed to transfer call: {e}")
            return False

    # =========================================================================
    # Room Management
    # =========================================================================

    async def create_room(
        self,
        name: str,
        empty_timeout: int = 300,  # 5 minutes
        max_participants: int = 10,
    ) -> dict[str, Any] | None:
        """Create a new room for calls/meetings.

        Args:
            name: Room name
            empty_timeout: Seconds before empty room is closed
            max_participants: Maximum participants allowed

        Returns:
            Room info dict if successful
        """
        if not self._initialized:
            await self.initialize()

        try:
            from livekit import api

            room = await self._room_service.create_room(
                api.CreateRoomRequest(
                    name=name,
                    empty_timeout=empty_timeout,
                    max_participants=max_participants,
                )
            )

            return {
                "name": room.name,
                "sid": room.sid,
                "creation_time": room.creation_time,
            }

        except Exception as e:
            logger.error(f"Failed to create room: {e}")
            return None

    async def generate_token(
        self,
        room_name: str,
        participant_identity: str,
        can_publish: bool = True,
        can_subscribe: bool = True,
        ttl: int = 3600,  # 1 hour
    ) -> str | None:
        """Generate access token for a participant.

        Args:
            room_name: Room to join
            participant_identity: Unique identity for participant
            can_publish: Allow publishing audio/video
            can_subscribe: Allow subscribing to others
            ttl: Token time-to-live in seconds

        Returns:
            JWT access token string
        """
        if not self.config.is_configured:
            return None

        try:
            from livekit import api

            token = api.AccessToken(
                self.config.api_key,
                self.config.api_secret,
            )

            token.with_identity(participant_identity)
            token.with_ttl(ttl)
            token.with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=can_publish,
                    can_subscribe=can_subscribe,
                )
            )

            return token.to_jwt()

        except Exception as e:
            logger.error(f"Failed to generate token: {e}")
            return None

    # =========================================================================
    # OBS/Streaming Integration (Egress)
    # =========================================================================

    async def start_rtmp_stream(
        self,
        room_name: str,
        rtmp_urls: list[str] | None = None,
        layout: str = "speaker",
    ) -> str | None:
        """Start streaming room to RTMP (OBS, YouTube, Twitch).

        Args:
            room_name: Room to stream
            rtmp_urls: RTMP destination URLs (uses config if not provided)
            layout: Video layout (speaker, grid, single-speaker)

        Returns:
            Egress ID if successful
        """
        if not self._initialized:
            await self.initialize()

        urls = rtmp_urls or ([self.config.rtmp_url] if self.config.rtmp_url else [])
        if not urls:
            logger.error("No RTMP URLs configured")
            return None

        try:
            from livekit import api

            stream_output = api.StreamOutput(
                protocol=api.StreamProtocol.RTMP,
                urls=urls,
            )

            egress = await self._egress_service.start_room_composite_egress(
                api.RoomCompositeEgressRequest(
                    room_name=room_name,
                    layout=layout,
                    stream=stream_output,
                )
            )

            logger.info(f"Started RTMP stream for room {room_name}")
            return egress.egress_id

        except Exception as e:
            logger.error(f"Failed to start RTMP stream: {e}")
            return None

    async def start_recording(
        self,
        room_name: str,
        output_path: str | None = None,
        layout: str = "speaker",
    ) -> str | None:
        """Start recording a room to file.

        Args:
            room_name: Room to record
            output_path: S3/GCS path or local file path
            layout: Video layout

        Returns:
            Egress ID if successful
        """
        if not self._initialized:
            await self.initialize()

        try:
            import time

            from livekit import api

            output_path = output_path or f"recordings/{room_name}-{int(time.time())}.mp4"

            file_output = api.EncodedFileOutput(
                filepath=output_path,
                output=api.FileOutput(),
            )

            egress = await self._egress_service.start_room_composite_egress(
                api.RoomCompositeEgressRequest(
                    room_name=room_name,
                    layout=layout,
                    file=file_output,
                )
            )

            logger.info(f"Started recording for room {room_name}")
            return egress.egress_id

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return None

    async def stop_egress(self, egress_id: str) -> bool:
        """Stop an active egress (stream or recording).

        Args:
            egress_id: ID of the egress to stop

        Returns:
            True if stopped successfully
        """
        if not self._initialized:
            return False

        try:
            from livekit import api

            await self._egress_service.stop_egress(api.StopEgressRequest(egress_id=egress_id))

            logger.info(f"Stopped egress {egress_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop egress: {e}")
            return False

    # =========================================================================
    # Status
    # =========================================================================

    async def get_active_rooms(self) -> list[dict[str, Any]]:
        """Get list of active rooms."""
        if not self._initialized:
            await self.initialize()

        try:
            from livekit import api

            rooms = await self._room_service.list_rooms(api.ListRoomsRequest())

            return [
                {
                    "name": room.name,
                    "sid": room.sid,
                    "num_participants": room.num_participants,
                    "creation_time": room.creation_time,
                }
                for room in rooms.rooms
            ]

        except Exception as e:
            logger.error(f"Failed to list rooms: {e}")
            return []

    def get_status(self) -> dict[str, Any]:
        """Get service status."""
        return {
            "initialized": self._initialized,
            "configured": self.config.is_configured,
            "has_sip": self.config.has_sip,
            "has_rtmp": bool(self.config.rtmp_url),
            "active_sessions": len(self._active_sessions),
            "url": self.config.url if self.config.is_configured else None,
        }


# =============================================================================
# Factory Function
# =============================================================================


_livekit_service: LiveKitService | None = None


def get_livekit_service() -> LiveKitService:
    """Get LiveKit service singleton."""
    global _livekit_service
    if _livekit_service is None:
        _livekit_service = LiveKitService()
    return _livekit_service


__all__ = [
    "CallSession",
    "CallType",
    "ConnectionType",
    "LiveKitConfig",
    "LiveKitService",
    "StreamType",
    "get_livekit_service",
]
