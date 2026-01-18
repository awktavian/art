"""Unified Realtime Service — THE single entry point for voice+video.

ALL real-time communication flows through this service:
- Bidirectional ConvAI (VAD, turn-taking, interruption, tool calls)
- Phone calls (Twilio Media Streams → ElevenLabs ConvAI)
- Video calls (LiveKit WebRTC)
- Streaming (RTMP to OBS/YouTube)

Architecture:
```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       UNIFIED REALTIME SERVICE                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ENTRY POINTS (all go through ConvAI)                                        │
│   ════════════════════════════════════                                        │
│                                                                               │
│   conversation()     call()              video_call()       stream()          │
│        │                │                     │                │              │
│        │                │                     │                │              │
│        └────────────────┼─────────────────────┼────────────────┘              │
│                         │                     │                               │
│                         ▼                     ▼                               │
│              ┌─────────────────────────────────────────┐                      │
│              │      ELEVENLABS CONVERSATIONAL AI        │                      │
│              │                                          │                      │
│              │  ┌────────┐  ┌────────┐  ┌────────────┐ │                      │
│              │  │  VAD   │  │  Turn  │  │ Interrupt  │ │                      │
│              │  │ Detect │  │ Taking │  │  Handler   │ │                      │
│              │  └────────┘  └────────┘  └────────────┘ │                      │
│              │                                          │                      │
│              │  ┌──────────────────────────────────┐   │                      │
│              │  │    Tim's Cloned Voice (Real)     │   │                      │
│              │  │    Agent: agent_3801keds...      │   │                      │
│              │  └──────────────────────────────────┘   │                      │
│              │                                          │                      │
│              │  ┌──────────────────────────────────┐   │                      │
│              │  │         Tool Calling              │   │                      │
│              │  │  • Smart home (lights, TV, etc)  │   │                      │
│              │  │  • Calendar, email, messages     │   │                      │
│              │  │  • Knowledge base, memory        │   │                      │
│              │  └──────────────────────────────────┘   │                      │
│              └──────────────────────────────────────────┘                      │
│                                │                                              │
│              ┌─────────────────┼─────────────────┐                            │
│              │                 │                 │                            │
│              ▼                 ▼                 ▼                            │
│        ┌──────────┐      ┌──────────┐      ┌──────────┐                      │
│        │  TWILIO  │      │ LIVEKIT  │      │   OBS    │                      │
│        │  Media   │      │  WebRTC  │      │  RTMP    │                      │
│        │  Streams │      │  SIP     │      │  Egress  │                      │
│        └──────────┘      └──────────┘      └──────────┘                      │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

Usage:
    from kagami.core.services.voice.realtime import get_realtime_service

    service = await get_realtime_service()

    # Start bidirectional conversation (local audio I/O)
    session = await service.conversation()

    # Phone call with bidirectional ConvAI
    session = await service.call("+16613105469")

    # Video call via LiveKit with ConvAI
    session = await service.video_call("tim-room")

    # Stream to OBS/YouTube
    await service.stream("rtmp://localhost:1935/live")

Created: January 8, 2026
Colony: Nexus (e₄) — Integration Hub
鏡
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CallType(str, Enum):
    """Type of call."""

    PHONE = "phone"  # PSTN via Twilio
    VIDEO = "video"  # WebRTC via LiveKit
    AUDIO = "audio"  # Audio-only via LiveKit


class CallState(str, Enum):
    """Call state."""

    IDLE = "idle"
    DIALING = "dialing"
    RINGING = "ringing"
    CONNECTED = "connected"
    ENDED = "ended"
    FAILED = "failed"


@dataclass
class RealtimeSession:
    """Active realtime session."""

    session_id: str
    call_type: CallType
    state: CallState = CallState.IDLE
    remote_identity: str = ""
    started_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class UnifiedRealtimeService:
    """THE unified realtime service for ALL voice+video.

    All communication flows through ElevenLabs ConvAI:
    - Bidirectional real-time conversation
    - VAD (Voice Activity Detection)
    - Turn-taking and interruption handling
    - Tool calling to Kagami backend
    - Tim's cloned voice

    Transport layers:
    - Twilio Media Streams (PSTN phone)
    - LiveKit WebRTC (video, browser)
    - Direct audio (local mic/speaker)
    """

    def __init__(self):
        self._initialized = False
        self._convai_factory = None  # Factory to create ConvAI sessions
        self._livekit = None
        self._twilio_client = None
        self._active_sessions: dict[str, RealtimeSession] = {}
        self._convai_sessions: dict[str, Any] = {}  # ConvAI instances per session

        # Callbacks
        self._on_state_change: list[Callable[[str, CallState], None]] = []
        self._on_transcript: list[Callable[[str, str, bool], None]] = []
        self._on_response: list[Callable[[str, str], None]] = []
        self._on_audio: list[Callable[[str, bytes], None]] = []

    async def initialize(self) -> bool:
        """Initialize all realtime services."""
        if self._initialized:
            return True

        try:
            from kagami.core.security import get_secret

            # Verify ElevenLabs credentials
            api_key = get_secret("elevenlabs_api_key")
            agent_id = get_secret("elevenlabs_agent_id")

            if not api_key or not agent_id:
                logger.error("ElevenLabs credentials not configured")
                logger.error("  Set: elevenlabs_api_key, elevenlabs_agent_id")
                return False

            logger.info("✅ ElevenLabs ConvAI configured")

            # Initialize LiveKit
            try:
                from kagami.core.services.voice.livekit_integration import (
                    LiveKitService,
                )

                self._livekit = LiveKitService()
                if await self._livekit.initialize():
                    logger.info("✅ LiveKit initialized")
                else:
                    logger.warning("LiveKit not available")
                    self._livekit = None
            except Exception as e:
                logger.warning(f"LiveKit not available: {e}")
                self._livekit = None

            # Initialize Twilio
            account_sid = get_secret("twilio_account_sid")
            auth_token = get_secret("twilio_auth_token")

            if account_sid and auth_token:
                from twilio.rest import Client

                self._twilio_client = Client(account_sid, auth_token)
                logger.info("✅ Twilio initialized")
            else:
                logger.warning("Twilio credentials not available")

            self._initialized = True
            logger.info("✅ UnifiedRealtimeService ready")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize realtime service: {e}")
            return False

    def _create_convai_session(
        self,
        session_id: str,
        on_audio: Callable[[bytes], None] | None = None,
    ):
        """Create a new ConvAI session with callbacks bound to session."""
        from kagami.core.services.voice.conversational_ai import (
            ConversationConfig,
            ConversationState,
            ElevenLabsConversationalAI,
        )

        def on_state(state: ConversationState):
            # Map ConvAI state to CallState
            state_map = {
                ConversationState.IDLE: CallState.IDLE,
                ConversationState.CONNECTING: CallState.DIALING,
                ConversationState.LISTENING: CallState.CONNECTED,
                ConversationState.THINKING: CallState.CONNECTED,
                ConversationState.SPEAKING: CallState.CONNECTED,
                ConversationState.INTERRUPTED: CallState.CONNECTED,
                ConversationState.ENDED: CallState.ENDED,
            }
            call_state = state_map.get(state, CallState.CONNECTED)

            if session_id in self._active_sessions:
                self._active_sessions[session_id].state = call_state
            self._notify_state_change(session_id, call_state)

        def on_transcript(text: str, is_final: bool):
            for callback in self._on_transcript:
                try:
                    callback(session_id, text, is_final)
                except Exception as e:
                    logger.error(f"Transcript callback error: {e}")

        def on_response(text: str):
            for callback in self._on_response:
                try:
                    callback(session_id, text)
                except Exception as e:
                    logger.error(f"Response callback error: {e}")

        def on_audio_cb(audio_data: bytes):
            # Notify all audio callbacks
            for callback in self._on_audio:
                try:
                    callback(session_id, audio_data)
                except Exception as e:
                    logger.error(f"Audio callback error: {e}")
            # Also call session-specific callback
            if on_audio:
                on_audio(audio_data)

        config = ConversationConfig(
            on_state_change=on_state,
            on_transcript=on_transcript,
            on_response=on_response,
            on_audio=on_audio_cb,
        )

        return ElevenLabsConversationalAI(config)

    # =========================================================================
    # Bidirectional Conversation (THE CORE)
    # =========================================================================

    async def conversation(
        self,
        on_audio: Callable[[bytes], None] | None = None,
        on_transcript: Callable[[str, bool], None] | None = None,
        on_response: Callable[[str], None] | None = None,
    ) -> RealtimeSession | None:
        """Start a bidirectional conversation with ConvAI.

        This is the core method - all other methods build on this.
        Uses VAD, turn-taking, interruption handling.

        Args:
            on_audio: Callback for audio output (for local playback)
            on_transcript: Callback for user transcripts
            on_response: Callback for agent responses

        Returns:
            RealtimeSession with ConvAI handle
        """
        if not self._initialized:
            await self.initialize()

        session_id = f"conv-{id(self)}-{len(self._active_sessions)}"

        try:
            # Create ConvAI config with callbacks
            from kagami.core.services.voice.conversational_ai import (
                ConversationConfig,
                ConversationState,
                ElevenLabsConversationalAI,
            )

            def state_cb(state: ConversationState):
                state_map = {
                    ConversationState.IDLE: CallState.IDLE,
                    ConversationState.CONNECTING: CallState.DIALING,
                    ConversationState.LISTENING: CallState.CONNECTED,
                    ConversationState.THINKING: CallState.CONNECTED,
                    ConversationState.SPEAKING: CallState.CONNECTED,
                    ConversationState.INTERRUPTED: CallState.CONNECTED,
                    ConversationState.ENDED: CallState.ENDED,
                }
                call_state = state_map.get(state, CallState.CONNECTED)
                if session_id in self._active_sessions:
                    self._active_sessions[session_id].state = call_state
                self._notify_state_change(session_id, call_state)

            def transcript_cb(text: str, is_final: bool):
                if on_transcript:
                    on_transcript(text, is_final)
                for cb in self._on_transcript:
                    try:
                        cb(session_id, text, is_final)
                    except Exception as e:
                        logger.error(f"Transcript callback error: {e}")

            def response_cb(text: str):
                if on_response:
                    on_response(text)
                for cb in self._on_response:
                    try:
                        cb(session_id, text)
                    except Exception as e:
                        logger.error(f"Response callback error: {e}")

            def audio_cb(audio_data: bytes):
                if on_audio:
                    on_audio(audio_data)
                for cb in self._on_audio:
                    try:
                        cb(session_id, audio_data)
                    except Exception as e:
                        logger.error(f"Audio callback error: {e}")

            config = ConversationConfig(
                on_state_change=state_cb,
                on_transcript=transcript_cb,
                on_response=response_cb,
                on_audio=audio_cb,
            )

            convai = ElevenLabsConversationalAI(config)

            if not await convai.initialize():
                logger.error("Failed to initialize ConvAI")
                return None

            # Start the conversation
            conv_session = await convai.start()

            if not conv_session:
                logger.error("Failed to start ConvAI session")
                return None

            # Create realtime session
            session = RealtimeSession(
                session_id=session_id,
                call_type=CallType.AUDIO,
                state=CallState.CONNECTED,
            )
            session.metadata["convai"] = convai
            session.metadata["conv_session"] = conv_session

            self._active_sessions[session_id] = session
            self._convai_sessions[session_id] = convai

            logger.info(f"🎙️ Conversation started: {session_id}")
            return session

        except Exception as e:
            logger.error(f"Conversation failed: {e}")
            return None

    async def send_audio(self, session_id: str, audio_data: bytes) -> bool:
        """Send audio to an active conversation.

        Args:
            session_id: Session ID
            audio_data: PCM 16-bit 16kHz audio

        Returns:
            True if sent successfully
        """
        convai = self._convai_sessions.get(session_id)
        if not convai:
            logger.error(f"No ConvAI session: {session_id}")
            return False

        await convai.send_audio(audio_data)
        return True

    async def send_text(self, session_id: str, text: str) -> bool:
        """Send text to an active conversation (bypasses STT).

        Args:
            session_id: Session ID
            text: Text message

        Returns:
            True if sent successfully
        """
        convai = self._convai_sessions.get(session_id)
        if not convai:
            logger.error(f"No ConvAI session: {session_id}")
            return False

        await convai.send_text(text)
        return True

    # =========================================================================
    # Audio Generation (ElevenLabs LIVESTREAMING - NO FALLBACKS)
    # =========================================================================

    async def _generate_and_host_audio(self, text: str) -> str | None:
        """Generate audio with ElevenLabs and upload to GCS for Twilio.

        Uses ElevenLabs streaming API, then uploads to Google Cloud Storage
        for Twilio to fetch via public URL.

        Args:
            text: Text to synthesize

        Returns:
            Public URL to audio file, or None if failed
        """
        try:
            import uuid

            import httpx

            from kagami.core.security import get_secret

            api_key = get_secret("elevenlabs_api_key")
            voice_id = get_secret("elevenlabs_voice_id") or "mVI4sVQ8lmFpGDyfy6sQ"

            if not api_key:
                logger.error("ElevenLabs API key not configured")
                return None

            # Generate MP3 audio (better quality for calls)
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "xi-api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    params={
                        "output_format": "mp3_44100_128",
                        "optimize_streaming_latency": 3,
                    },
                    json={
                        "text": text,
                        "model_id": "eleven_v3",
                        "voice_settings": {
                            "stability": 0.5,
                            "similarity_boost": 0.8,
                            "speed": 1.0,
                        },
                    },
                    timeout=60.0,
                )

                if response.status_code != 200:
                    logger.error(f"ElevenLabs error: {response.status_code}")
                    return None

                audio_data = response.content
                logger.info(f"🎙️ Generated {len(audio_data)} bytes MP3 audio")

            # Upload to GCS (kagami-media-public bucket)
            try:
                from google.cloud import storage

                bucket_name = "kagami-media-public"
                blob_name = f"voice/calls/{uuid.uuid4()}.mp3"

                storage_client = storage.Client()
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)

                blob.upload_from_string(audio_data, content_type="audio/mpeg")
                blob.make_public()

                public_url = blob.public_url
                logger.info(f"🎙️ Audio uploaded: {public_url}")
                return public_url

            except ImportError:
                logger.error("google-cloud-storage not installed")
                return None
            except Exception as e:
                logger.error(f"GCS upload failed: {e}")
                return None

        except Exception as e:
            logger.error(f"Audio generation failed: {e}")
            return None

    async def _generate_elevenlabs_audio_ulaw(self, text: str) -> bytes | None:
        """Generate audio using ElevenLabs streaming API in μ-law format.

        Uses ElevenLabs streaming endpoint with ulaw_8000 output format
        which is directly compatible with Twilio - NO CONVERSION NEEDED.

        Args:
            text: Text to synthesize

        Returns:
            Audio bytes in μ-law 8kHz format, or None if generation fails
        """
        try:
            import httpx

            from kagami.core.security import get_secret

            api_key = get_secret("elevenlabs_api_key")
            voice_id = get_secret("elevenlabs_voice_id") or "mVI4sVQ8lmFpGDyfy6sQ"

            if not api_key:
                logger.error("ElevenLabs API key not configured")
                return None

            # Use streaming endpoint with ulaw_8000 for Twilio compatibility
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "xi-api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    params={
                        "output_format": "ulaw_8000",  # Direct Twilio format!
                        "optimize_streaming_latency": 3,  # Max latency optimization
                    },
                    json={
                        "text": text,
                        "model_id": "eleven_v3",  # Fastest model
                        "voice_settings": {
                            "stability": 0.5,
                            "similarity_boost": 0.8,
                            "speed": 1.0,
                        },
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.error(f"ElevenLabs streaming error: {response.status_code}")
                    return None

                audio_data = response.content
                logger.info(f"🎙️ Generated {len(audio_data)} bytes μ-law audio")
                return audio_data

        except Exception as e:
            logger.error(f"ElevenLabs livestream failed: {e}")
            return None

    async def _stream_to_twilio_websocket(
        self,
        text: str,
        stream_sid: str,
        websocket,
    ) -> bool:
        """Stream ElevenLabs audio directly to Twilio WebSocket.

        Uses ElevenLabs WebSocket streaming API for real-time, ultra-low
        latency audio delivery to Twilio Media Streams.

        Args:
            text: Text to synthesize
            stream_sid: Twilio stream SID
            websocket: Twilio WebSocket connection

        Returns:
            True if streaming successful
        """
        try:
            import json

            import websockets

            from kagami.core.security import get_secret

            api_key = get_secret("elevenlabs_api_key")
            voice_id = get_secret("elevenlabs_voice_id") or "mVI4sVQ8lmFpGDyfy6sQ"

            # Connect to ElevenLabs WebSocket streaming endpoint
            ws_url = (
                f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
                f"?model_id=eleven_v3"
                f"&output_format=ulaw_8000"
                f"&optimize_streaming_latency=4"
            )

            headers = {"xi-api-key": api_key}

            async with websockets.connect(ws_url, additional_headers=headers) as eleven_ws:
                # Initialize connection
                await eleven_ws.send(
                    json.dumps(
                        {
                            "text": " ",  # Initial space to start
                            "voice_settings": {
                                "stability": 0.5,
                                "similarity_boost": 0.8,
                            },
                            "generation_config": {
                                "chunk_length_schedule": [50],  # Fast chunks
                            },
                        }
                    )
                )

                # Send full text
                await eleven_ws.send(
                    json.dumps(
                        {
                            "text": text,
                        }
                    )
                )

                # Signal end of text
                await eleven_ws.send(
                    json.dumps(
                        {
                            "text": "",
                        }
                    )
                )

                # Stream audio chunks to Twilio
                async for message in eleven_ws:
                    data = json.loads(message)

                    if "audio" in data:
                        # Forward audio to Twilio
                        await websocket.send_json(
                            {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": data["audio"],  # Already base64
                                },
                            }
                        )

                    if data.get("isFinal"):
                        break

                logger.info("🎙️ Livestream to Twilio complete")
                return True

        except Exception as e:
            logger.error(f"Twilio livestream failed: {e}")
            return False

    # =========================================================================
    # Phone Calls
    # =========================================================================

    async def call(
        self,
        phone_number: str,
        message: str | None = None,
        bidirectional: bool = True,
        webhook_url: str | None = None,
    ) -> RealtimeSession | None:
        """Make a phone call with ElevenLabs ConvAI.

        Args:
            phone_number: E.164 format (+1234567890)
            message: Optional initial message (one-way only)
            bidirectional: If True, use ConvAI with VAD (requires webhook)
            webhook_url: Public URL for Twilio Media Streams callback

        Returns:
            Session object if successful
        """
        if not self._initialized:
            await self.initialize()

        session_id = f"call-{phone_number[-4:]}-{id(self)}"

        try:
            from kagami.core.security import get_secret

            # Create session
            session = RealtimeSession(
                session_id=session_id,
                call_type=CallType.PHONE,
                state=CallState.DIALING,
                remote_identity=phone_number,
            )
            self._active_sessions[session_id] = session
            self._notify_state_change(session_id, CallState.DIALING)

            from_number = get_secret("twilio_phone_number")
            if not from_number:
                logger.error("No Twilio phone number configured")
                return None

            if bidirectional and webhook_url:
                # =====================================================
                # BIDIRECTIONAL MODE: Twilio Media Streams → ConvAI
                # Real-time VAD, turn-taking, tool calls
                # =====================================================
                agent_id = get_secret("elevenlabs_agent_id")

                # TwiML to connect Media Streams to our WebSocket
                # Extract base URL (remove path if present)
                from urllib.parse import urlparse

                parsed = urlparse(webhook_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")

                twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}/ws/voice/twilio">
            <Parameter name="session_id" value="{session_id}"/>
            <Parameter name="agent_id" value="{agent_id}"/>
        </Stream>
    </Connect>
</Response>'''

                session.metadata["bidirectional"] = True
                session.metadata["webhook_url"] = webhook_url
                logger.info(f"📞 Bidirectional call via {webhook_url}")

            else:
                # =====================================================
                # ONE-WAY MODE: Generate audio and play
                # Simpler, no webhook required
                # =====================================================
                text_to_speak = message or "Hey! This is Kagami."
                audio_url = await self._generate_and_host_audio(text_to_speak)

                if audio_url:
                    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
</Response>"""
                    session.metadata["bidirectional"] = False
                else:
                    logger.error("ElevenLabs audio generation failed - NO FALLBACK")
                    session.state = CallState.FAILED
                    self._notify_state_change(session_id, CallState.FAILED)
                    return None

            # Make the call with recording enabled
            if self._twilio_client:
                call = self._twilio_client.calls.create(
                    to=phone_number,
                    from_=from_number,
                    twiml=twiml,
                    record=True,  # Enable call recording
                    recording_status_callback=f"{webhook_url}/voice/recording-status"
                    if webhook_url
                    else None,
                )

                session.state = CallState.RINGING
                session.metadata["twilio_sid"] = call.sid
                self._notify_state_change(session_id, CallState.RINGING)

                logger.info(f"📞 Call initiated: {call.sid}")
                return session

        except Exception as e:
            logger.error(f"Call failed: {e}")
            if session_id in self._active_sessions:
                self._active_sessions[session_id].state = CallState.FAILED
                self._notify_state_change(session_id, CallState.FAILED)

        return None

    # =========================================================================
    # Video Calls
    # =========================================================================

    async def video_call(
        self,
        room_name: str | None = None,
        participant: str | None = None,
    ) -> RealtimeSession | None:
        """Start a video call via LiveKit.

        Args:
            room_name: Optional room name (auto-generated if not provided)
            participant: Optional participant to invite

        Returns:
            Session with room info
        """
        if not self._initialized:
            await self.initialize()

        if not self._livekit:
            logger.error("LiveKit not available")
            return None

        room_name = room_name or f"kagami-{id(self)}"
        session_id = f"video-{room_name}"

        try:
            session = RealtimeSession(
                session_id=session_id,
                call_type=CallType.VIDEO,
                state=CallState.CONNECTING,
                remote_identity=participant or "",
            )
            self._active_sessions[session_id] = session

            # Create room
            await self._livekit.create_room(room_name)

            # Generate access token
            token = await self._livekit.generate_access_token(
                room_name=room_name,
                participant_name="Kagami",
            )

            session.state = CallState.CONNECTED
            session.metadata["room_name"] = room_name
            session.metadata["token"] = token
            session.metadata["url"] = self._livekit.config.url

            self._notify_state_change(session_id, CallState.CONNECTED)
            logger.info(f"📹 Video room created: {room_name}")

            return session

        except Exception as e:
            logger.error(f"Video call failed: {e}")
            return None

    # =========================================================================
    # Streaming
    # =========================================================================

    async def stream(
        self,
        rtmp_url: str,
        room_name: str | None = None,
    ) -> str | None:
        """Start streaming to RTMP endpoint.

        Args:
            rtmp_url: RTMP URL (e.g., rtmp://localhost:1935/live)
            room_name: Optional room to stream from

        Returns:
            Egress ID if successful
        """
        if not self._initialized:
            await self.initialize()

        if not self._livekit:
            logger.error("LiveKit not available")
            return None

        try:
            room_name = room_name or f"kagami-stream-{id(self)}"

            egress_id = await self._livekit.start_rtmp_stream(
                room_name=room_name,
                rtmp_urls=[rtmp_url],
            )

            logger.info(f"📺 Stream started: {egress_id}")
            return egress_id

        except Exception as e:
            logger.error(f"Stream failed: {e}")
            return None

    # =========================================================================
    # Session Management
    # =========================================================================

    async def end_session(self, session_id: str) -> bool:
        """End an active session."""
        session = self._active_sessions.get(session_id)
        if not session:
            return False

        try:
            # End ConvAI session if active
            convai = self._convai_sessions.get(session_id)
            if convai:
                await convai.stop()
                del self._convai_sessions[session_id]

            if session.call_type == CallType.PHONE:
                # End Twilio call
                if self._twilio_client and "twilio_sid" in session.metadata:
                    try:
                        self._twilio_client.calls(session.metadata["twilio_sid"]).update(
                            status="completed"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to end Twilio call: {e}")

            elif session.call_type == CallType.VIDEO:
                # End LiveKit room
                if self._livekit and "room_name" in session.metadata:
                    await self._livekit.delete_room(session.metadata["room_name"])

            session.state = CallState.ENDED
            self._notify_state_change(session_id, CallState.ENDED)

            del self._active_sessions[session_id]
            logger.info(f"🔚 Session ended: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to end session: {e}")
            return False

    def get_active_sessions(self) -> list[RealtimeSession]:
        """Get all active sessions."""
        return list(self._active_sessions.values())

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_state_change(self, callback: Callable[[str, CallState], None]) -> None:
        """Register state change callback.

        Args:
            callback: Function(session_id, state)
        """
        self._on_state_change.append(callback)

    def on_transcript(self, callback: Callable[[str, str, bool], None]) -> None:
        """Register transcript callback.

        Args:
            callback: Function(session_id, text, is_final)
        """
        self._on_transcript.append(callback)

    def on_response(self, callback: Callable[[str, str], None]) -> None:
        """Register response callback.

        Args:
            callback: Function(session_id, text)
        """
        self._on_response.append(callback)

    def on_audio(self, callback: Callable[[str, bytes], None]) -> None:
        """Register audio callback.

        Args:
            callback: Function(session_id, audio_bytes)
        """
        self._on_audio.append(callback)

    def _notify_state_change(self, session_id: str, state: CallState) -> None:
        """Notify state change callbacks."""
        for callback in self._on_state_change:
            try:
                callback(session_id, state)
            except Exception as e:
                logger.error(f"State callback error: {e}")


# =============================================================================
# Factory Functions
# =============================================================================


_service: UnifiedRealtimeService | None = None


async def get_realtime_service() -> UnifiedRealtimeService:
    """Get or create the unified realtime service singleton."""
    global _service
    if _service is None:
        _service = UnifiedRealtimeService()
        await _service.initialize()
    return _service


def reset_realtime_service() -> None:
    """Reset the realtime service singleton."""
    global _service
    _service = None


# =============================================================================
# Convenience Functions
# =============================================================================


async def conversation(
    on_audio: Callable[[bytes], None] | None = None,
) -> RealtimeSession | None:
    """Start a bidirectional conversation with ConvAI.

    Uses VAD, turn-taking, Tim's cloned voice.

    Args:
        on_audio: Callback for audio output

    Returns:
        RealtimeSession with ConvAI
    """
    service = await get_realtime_service()
    return await service.conversation(on_audio=on_audio)


async def call(
    phone_or_name: str,
    message: str | None = None,
    bidirectional: bool = True,
    webhook_url: str | None = None,
) -> RealtimeSession | None:
    """Make a phone call to a number or contact.

    Args:
        phone_or_name: E.164 phone (+1234567890) OR contact name ("tim", "bella")
        message: Message to speak (one-way mode only)
        bidirectional: Use ConvAI with VAD (default True, auto-detects ngrok)
        webhook_url: Public URL for Twilio Media Streams (auto-detected from ngrok)

    Returns:
        RealtimeSession if successful

    Examples:
        await call("+16613105469")  # Direct phone number
        await call("tim")           # Resolves from contacts
        await call("bella")         # Resolves from contacts
    """
    # Resolve contact name to phone number if not E.164 format
    if not phone_or_name.startswith("+"):
        from kagami.core.contacts import get_phone

        phone_number = get_phone(phone_or_name)
        if not phone_number:
            # Fallback to secrets
            from kagami.core.security import get_secret

            phone_number = get_secret(f"{phone_or_name.lower()}_phone_number")

        if not phone_number:
            logger.error(f"Could not resolve phone for: {phone_or_name}")
            return None

        logger.info(f"📞 Resolved {phone_or_name} → {phone_number[:6]}***")
    else:
        phone_number = phone_or_name

    # Auto-detect ngrok URL if bidirectional and no webhook provided
    if bidirectional and not webhook_url:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get("http://localhost:4040/api/tunnels", timeout=2.0)
                tunnels = resp.json().get("tunnels", [])
                if tunnels:
                    webhook_url = tunnels[0]["public_url"]
                    logger.info(f"📡 Auto-detected ngrok: {webhook_url}")
        except Exception as e:
            logger.warning(f"Could not auto-detect ngrok: {e}")
            # Fall back to one-way mode
            if not message:
                message = "Hey! This is Kagami. Ngrok isn't running for bidirectional calls."
            bidirectional = False

    service = await get_realtime_service()
    return await service.call(
        phone_number,
        message=message,
        bidirectional=bidirectional,
        webhook_url=webhook_url,
    )


async def call_contact(
    name: str,
    message: str | None = None,
    bidirectional: bool = True,
) -> RealtimeSession | None:
    """Call a contact by name - auto-resolves phone from contacts system.

    Auto-detects:
        - Phone number from contacts (assets/characters/{name}/metadata.json)
        - Ngrok webhook URL
        - Uses bidirectional ConvAI mode by default

    Args:
        name: Contact name (e.g., "tim", "bella") or identity_id
        message: Optional message (only used if ngrok unavailable)
        bidirectional: Use ConvAI with VAD (default True)

    Returns:
        RealtimeSession if successful

    Example:
        await call_contact("tim")  # Calls Tim
        await call_contact("bella")  # Calls Bella
    """
    from kagami.core.contacts import get_phone

    # Try to get phone from contacts
    phone = get_phone(name)

    if not phone:
        # Fallback to secrets for backwards compatibility
        from kagami.core.security import get_secret

        phone = get_secret(f"{name.lower()}_phone_number")

    if not phone:
        logger.error(f"No phone number found for contact: {name}")
        return None

    logger.info(f"📞 Calling {name} at {phone[:6]}***")
    return await call(phone, message=message, bidirectional=bidirectional)


async def call_owner(message: str | None = None) -> RealtimeSession | None:
    """Call the owner (convenience function).

    Args:
        message: Optional message (only used if ngrok unavailable)

    Returns:
        RealtimeSession if successful
    """
    from kagami.core.contacts import get_owner

    owner = get_owner()
    if not owner:
        logger.error("No owner configured in contacts")
        return None

    return await call_contact(owner.name, message=message)


async def video_call(room_name: str | None = None) -> RealtimeSession | None:
    """Start a video call via LiveKit.

    Args:
        room_name: Optional room name

    Returns:
        RealtimeSession with room info
    """
    service = await get_realtime_service()
    return await service.video_call(room_name)


__all__ = [
    # Types
    "CallState",
    "CallType",
    "RealtimeSession",
    # Main Service
    "UnifiedRealtimeService",
    # Convenience Functions
    "call",
    "call_contact",
    "call_owner",
    "conversation",
    "get_realtime_service",
    "reset_realtime_service",
    "video_call",
]
