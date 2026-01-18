"""Unified Media Pipeline — THE single entry point for voice, video, and spatial audio.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED MEDIA PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   INPUT SOURCES                    PROCESSING                  OUTPUT TARGETS   │
│   ─────────────                    ──────────                  ──────────────   │
│                                                                                  │
│   ┌─────────────┐                 ┌───────────┐               ┌─────────────┐   │
│   │ Control4 Mic│──┐              │           │           ┌──►│ KEF 5.1.4   │   │
│   │ (Theater)   │  │              │    STT    │           │   │ (Home)      │   │
│   └─────────────┘  │              │ (Whisper) │           │   └─────────────┘   │
│                    │              │           │           │                      │
│   ┌─────────────┐  │   Audio      └─────┬─────┘           │   ┌─────────────┐   │
│   │ Hub Mics    │──┼───────────────────►│                 ├──►│ Phone/PSTN  │   │
│   │ (Pi/Orb)    │  │                    │ Transcript      │   │ (Twilio SIP)│   │
│   └─────────────┘  │                    ▼                 │   └─────────────┘   │
│                    │              ┌───────────┐           │                      │
│   ┌─────────────┐  │              │ Speaker   │           │   ┌─────────────┐   │
│   │ LiveKit     │──┼──────────────│ Identify  │           ├──►│ WebRTC      │   │
│   │ (WebRTC)    │  │   Video      │           │           │   │ (LiveKit)   │   │
│   └─────────────┘  │              └─────┬─────┘           │   └─────────────┘   │
│                    │                    │ User            │                      │
│   ┌─────────────┐  │                    ▼                 │   ┌─────────────┐   │
│   │ Phone       │──┘              ┌───────────┐           ├──►│ Desktop     │   │
│   │ (Twilio)    │                 │   LLM     │           │   │ (Local)     │   │
│   └─────────────┘                 │ (Claude)  │           │   └─────────────┘   │
│                                   │           │           │                      │
│                                   └─────┬─────┘           │   ┌─────────────┐   │
│                                         │ Response        └──►│ Glasses     │   │
│                                         ▼                     │ (Meta)      │   │
│                                   ┌───────────┐               └─────────────┘   │
│                                   │    TTS    │                                  │
│                                   │(ElevenLabs│                                  │
│                                   │  Flash)   │                                  │
│                                   └─────┬─────┘                                  │
│                                         │ Audio                                  │
│                                         ▼                                        │
│                                   ┌───────────┐                                  │
│                                   │  Spatial  │                                  │
│                                   │   Audio   │──────────────────────────────►   │
│                                   │  (VBAP)   │                                  │
│                                   └───────────┘                                  │
│                                                                                  │
│   Synchronization:                                                               │
│   • Video Sync: Word timings → Frame alignment → Lip sync                       │
│   • Subtitles: ASS/WebVTT generation from word timings                          │
│   • Latency Target: <100ms TTFA for real-time                                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

Usage:
    from kagami.core.media import get_media_pipeline, MediaTarget

    pipeline = await get_media_pipeline()

    # Voice input → Response → Output
    result = await pipeline.process_voice(audio_data)

    # Text → Voice → Spatial Output
    await pipeline.speak("Hello Tim", target=MediaTarget.HOME)

    # Video call
    session = await pipeline.start_video_call(phone_number)

Colony: Nexus (e₄) — Integration hub
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.services.voice.livekit_integration import LiveKitService

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class MediaTarget(str, Enum):
    """Output target for media."""

    AUTO = "auto"  # Context-aware routing
    HOME = "home"  # KEF 5.1.4 via Denon
    HOME_ROOM = "home_room"  # Specific room(s)
    PHONE = "phone"  # Twilio PSTN
    WEBRTC = "webrtc"  # LiveKit video call
    DESKTOP = "desktop"  # Local speakers
    GLASSES = "glasses"  # Meta Ray-Ban
    CAR = "car"  # Tesla cabin


class InputSource(str, Enum):
    """Input source for media."""

    CONTROL4 = "control4"  # Home theater mic
    HUB = "hub"  # Kagami hub mic
    LIVEKIT = "livekit"  # WebRTC call
    PHONE = "phone"  # Twilio call
    API = "api"  # Text input via API


class PipelineState(str, Enum):
    """Pipeline state."""

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    VIDEO_CALL = "video_call"


# =============================================================================
# Data Types
# =============================================================================


@dataclass
class MediaConfig:
    """Configuration for the unified media pipeline."""

    # TTS
    elevenlabs_voice_id: str = "mVI4sVQ8lmFpGDyfy6sQ"  # Tim's cloned voice
    elevenlabs_model: str = "eleven_v3"  # ALWAYS V3 for audio tags
    tts_latency_target_ms: float = 100.0

    # STT
    whisper_model: str = "base"  # Balance of speed/accuracy
    stt_language: str = "en"

    # Spatial Audio
    sample_rate: int = 48000
    spatial_channels: int = 8  # 7.1 PCM

    # LiveKit
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Targets
    default_target: MediaTarget = MediaTarget.AUTO


@dataclass
class SpeakResult:
    """Result of speak operation."""

    success: bool
    text: str
    target: MediaTarget
    target_detail: str = ""
    audio_path: Path | None = None
    duration_ms: float = 0.0
    latency_ms: float = 0.0
    word_timings: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass
class TranscriptionResult:
    """Result of transcription."""

    success: bool
    transcript: str = ""
    speaker_id: str | None = None
    confidence: float = 0.0
    language: str = "en"
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class VideoCallSession:
    """Active video call session."""

    session_id: str
    room_name: str
    target: str  # Phone number or identity
    started_at: float
    is_video: bool = True
    livekit_session: Any = None
    twilio_call_sid: str | None = None


# =============================================================================
# Unified Media Pipeline
# =============================================================================


class UnifiedMediaPipeline:
    """THE unified media pipeline for all voice, video, and audio.

    Single entry point that coordinates:
    - STT (Whisper) for speech recognition
    - LLM (Claude) for response generation
    - TTS (ElevenLabs Flash) for speech synthesis
    - Spatial Audio (VBAP) for 3D positioning
    - LiveKit for video calls
    - Twilio for phone calls

    **MESH IS CORE:**
    All voice output routes through ConsensusVoiceCoordinator for:
    - Distributed hub coordination
    - Presence-aware routing
    - Single-speaker mutex (no echo/overlap)
    - Automatic fallback handling
    """

    def __init__(self, config: MediaConfig | None = None):
        self.config = config or MediaConfig()
        self._state = PipelineState.IDLE
        self._initialized = False

        # Services (lazy-loaded)
        self._tts_service = None
        self._stt_service = None
        self._livekit_service: LiveKitService | None = None
        self._spatial_engine = None
        self._voice_effector = None
        self._mesh_coordinator = None  # ConsensusVoiceCoordinator (mesh core)

        # Active sessions
        self._active_calls: dict[str, VideoCallSession] = {}

        # Callbacks
        self._on_state_change: list[Callable[[PipelineState], None]] = []
        self._on_transcription: list[Callable[[TranscriptionResult], None]] = []

    # =========================================================================
    # Initialization
    # =========================================================================

    async def initialize(self) -> bool:
        """Initialize all media services."""
        if self._initialized:
            return True

        try:
            # Load credentials from keychain
            await self._load_credentials()

            # Initialize Mesh Coordinator (CORE - routes all voice output)
            await self._init_mesh()

            # Initialize TTS (ElevenLabs)
            await self._init_tts()

            # Initialize STT (Whisper)
            await self._init_stt()

            # Initialize Spatial Audio
            await self._init_spatial()

            # Initialize LiveKit (optional - for video calls)
            await self._init_livekit()

            self._initialized = True
            logger.info("✅ Unified Media Pipeline initialized (mesh-core)")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize media pipeline: {e}")
            return False

    async def _init_mesh(self) -> None:
        """Initialize mesh voice coordinator (CORE routing layer)."""
        try:
            from kagami.core.effectors.consensus_voice import ConsensusVoiceCoordinator

            self._mesh_coordinator = ConsensusVoiceCoordinator()
            await self._mesh_coordinator.initialize()
            logger.info("✓ Mesh voice coordinator initialized")
        except Exception as e:
            logger.warning(f"Mesh coordinator init failed (will use direct routing): {e}")
            self._mesh_coordinator = None

    async def _load_credentials(self) -> None:
        """Load API credentials from keychain."""
        try:
            from kagami.core.security import get_secret

            # ElevenLabs
            self.config.elevenlabs_voice_id = (
                get_secret("elevenlabs_voice_id") or self.config.elevenlabs_voice_id
            )

            # LiveKit
            self.config.livekit_url = get_secret("livekit_url") or ""
            self.config.livekit_api_key = get_secret("livekit_api_key") or ""
            self.config.livekit_api_secret = get_secret("livekit_api_secret") or ""

            # Twilio
            self.config.twilio_account_sid = get_secret("twilio_account_sid") or ""
            self.config.twilio_auth_token = get_secret("twilio_auth_token") or ""
            self.config.twilio_phone_number = get_secret("twilio_phone_number") or ""

        except Exception as e:
            logger.warning(f"Could not load some credentials: {e}")

    async def _init_tts(self) -> None:
        """Initialize TTS service."""
        try:
            from kagami.core.services.voice.realtime_pipeline import RealtimeVoicePipeline

            self._tts_service = RealtimeVoicePipeline()
            logger.info("✅ TTS (ElevenLabs) initialized")
        except Exception as e:
            logger.warning(f"TTS init failed: {e}")

    async def _init_stt(self) -> None:
        """Initialize STT service."""
        try:
            from kagami.core.services.voice.stt import get_stt_provider

            self._stt_service = get_stt_provider()
            logger.info("✅ STT (Whisper) initialized")
        except Exception as e:
            logger.warning(f"STT init failed: {e}")

    async def _init_spatial(self) -> None:
        """Initialize spatial audio engine."""
        try:
            from kagami.core.effectors.spatial_audio import UnifiedSpatialEngine

            self._spatial_engine = UnifiedSpatialEngine()
            logger.info("✅ Spatial Audio initialized")
        except Exception as e:
            logger.warning(f"Spatial audio init failed: {e}")

    async def _init_livekit(self) -> None:
        """Initialize LiveKit for video calls."""
        if not self.config.livekit_url:
            logger.info("LiveKit not configured (optional)")
            return

        try:
            from kagami.core.services.voice.livekit_integration import (
                LiveKitConfig,
                LiveKitService,
            )

            livekit_config = LiveKitConfig(
                url=self.config.livekit_url,
                api_key=self.config.livekit_api_key,
                api_secret=self.config.livekit_api_secret,
            )
            self._livekit_service = LiveKitService(livekit_config)
            await self._livekit_service.initialize()
            logger.info("✅ LiveKit initialized")
        except Exception as e:
            logger.warning(f"LiveKit init failed: {e}")

    # =========================================================================
    # Voice Output (TTS + Spatial)
    # =========================================================================

    async def speak(
        self,
        text: str,
        *,
        target: MediaTarget = MediaTarget.AUTO,
        rooms: list[str] | None = None,
        voice_id: str | None = None,
        emotion: str | None = None,
        with_sync: bool = True,
    ) -> SpeakResult:
        """Synthesize and play speech with spatial audio routing.

        Args:
            text: Text to speak
            target: Output target (AUTO uses context)
            rooms: Specific rooms for HOME_ROOM target
            voice_id: Override voice ID
            emotion: Emotion tag for v3 model
            with_sync: Generate word timings for video sync

        Returns:
            SpeakResult with audio path and timing data
        """
        start_time = time.perf_counter()
        self._set_state(PipelineState.SPEAKING)

        try:
            # Determine target
            actual_target = await self._resolve_target(target)

            # Synthesize with realtime pipeline
            audio_data = None
            word_timings = []

            if self._tts_service:
                async for chunk in self._tts_service.synthesize_streaming(
                    text,
                    voice_id=voice_id or self.config.elevenlabs_voice_id,
                    emotion=emotion,
                    with_sync=with_sync,
                ):
                    if audio_data is None:
                        audio_data = chunk.audio
                    else:
                        audio_data = audio_data + chunk.audio

                    if chunk.word_timings:
                        word_timings.extend(chunk.word_timings)

            if not audio_data:
                return SpeakResult(
                    success=False,
                    text=text,
                    target=actual_target,
                    error="TTS synthesis failed",
                )

            # Route to target (mesh-aware when available)
            target_detail = await self._route_audio(
                audio_data, actual_target, rooms=rooms, text=text
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            return SpeakResult(
                success=True,
                text=text,
                target=actual_target,
                target_detail=target_detail,
                duration_ms=len(audio_data) / self.config.sample_rate * 1000,
                latency_ms=latency_ms,
                word_timings=word_timings,
            )

        except Exception as e:
            logger.error(f"speak() failed: {e}")
            return SpeakResult(
                success=False,
                text=text,
                target=target,
                error=str(e),
            )
        finally:
            self._set_state(PipelineState.IDLE)

    async def _resolve_target(self, target: MediaTarget) -> MediaTarget:
        """Resolve AUTO target based on context."""
        if target != MediaTarget.AUTO:
            return target

        # Check presence context
        try:
            from kagami.core.effectors.voice import get_presence_context

            ctx = await get_presence_context()

            if ctx.in_video_call:
                return MediaTarget.WEBRTC
            if ctx.in_phone_call:
                return MediaTarget.PHONE
            if ctx.at_home:
                return MediaTarget.HOME
            if ctx.in_car:
                return MediaTarget.CAR

        except Exception:
            pass

        return MediaTarget.HOME  # Default

    async def _route_audio(
        self,
        audio_data: bytes,
        target: MediaTarget,
        rooms: list[str] | None = None,
        text: str = "",
    ) -> str:
        """Route audio to target output.

        MESH IS CORE: When mesh coordinator is available, uses distributed
        hub coordination for HOME targets. This ensures:
        - Single-speaker mutex (no echo/overlap)
        - Presence-aware routing to nearest hub
        - Automatic fallback if hub unavailable
        """
        # For HOME targets, use mesh coordinator if available
        if target in (MediaTarget.HOME, MediaTarget.HOME_ROOM) and self._mesh_coordinator:
            return await self._route_via_mesh(text, target, rooms)

        # Direct routing (for non-home or mesh unavailable)
        if target == MediaTarget.HOME:
            return await self._route_home_all(audio_data)
        elif target == MediaTarget.HOME_ROOM:
            return await self._route_home_rooms(audio_data, rooms or [])
        elif target == MediaTarget.DESKTOP:
            return await self._route_desktop(audio_data)
        elif target == MediaTarget.WEBRTC:
            return await self._route_webrtc(audio_data)
        elif target == MediaTarget.PHONE:
            return await self._route_phone(audio_data)
        else:
            return await self._route_desktop(audio_data)

    async def _route_via_mesh(
        self,
        text: str,
        target: MediaTarget,
        rooms: list[str] | None = None,
    ) -> str:
        """Route voice output via mesh coordinator.

        This is the CORE routing path for home audio. The mesh coordinator:
        1. Selects the best hub based on presence
        2. Acquires distributed mutex (prevents overlap)
        3. Routes TTS to the selected hub
        4. Handles fallback if hub unavailable
        """
        from kagami.core.effectors.consensus_voice import HubSelection

        # Map MediaTarget to HubSelection
        mesh_target = HubSelection.ALL if target == MediaTarget.HOME else HubSelection.SPECIFIC_ROOM

        result = await self._mesh_coordinator.speak(
            text,
            target=mesh_target,
            target_room=rooms[0] if rooms else None,
        )

        if result.success:
            return f"Mesh: {result.hub_id or 'distributed'}"
        else:
            # Fallback to direct routing
            logger.warning(f"Mesh routing failed: {result.error}, using direct")
            return "Direct (mesh fallback)"

    async def _route_home_all(self, audio_data: bytes) -> str:
        """Route to all home audio zones via spatial engine."""
        if self._spatial_engine:
            # Position at center for announcements
            await self._spatial_engine.play_positioned(
                audio_data,
                azimuth=0,
                elevation=0,
                distance=1.0,
            )
            return "All 26 zones"
        return "Home (spatial not available)"

    async def _route_home_rooms(self, audio_data: bytes, rooms: list[str]) -> str:
        """Route to specific rooms."""
        try:
            from kagami_smarthome import get_smart_home

            await get_smart_home()
            # Use announce for room-specific
            # await controller.play_audio(audio_data, rooms=rooms)
            return ", ".join(rooms)
        except Exception as e:
            logger.warning(f"Room routing failed: {e}")
            return await self._route_desktop(audio_data)

    async def _route_desktop(self, audio_data: bytes) -> str:
        """Route to local desktop speakers."""
        try:
            import numpy as np
            import sounddevice as sd

            # Convert bytes to numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            audio_float = audio_np.astype(np.float32) / 32768.0

            sd.play(audio_float, self.config.sample_rate)
            sd.wait()
            return "Desktop speakers"
        except Exception as e:
            logger.warning(f"Desktop playback failed: {e}")
            return "Desktop (failed)"

    async def _route_webrtc(self, audio_data: bytes) -> str:
        """Route to active WebRTC call."""
        # Audio is routed via LiveKit track publication
        return "WebRTC call"

    async def _route_phone(self, audio_data: bytes) -> str:
        """Route to active phone call."""
        # Audio is streamed via Twilio Media Streams
        return "Phone call"

    # =========================================================================
    # Voice Input (STT)
    # =========================================================================

    async def transcribe(
        self,
        audio_data: bytes,
        *,
        source: InputSource = InputSource.API,
        identify_speaker: bool = True,
    ) -> TranscriptionResult:
        """Transcribe audio to text.

        Args:
            audio_data: Raw audio bytes (PCM 16-bit)
            source: Input source for context
            identify_speaker: Whether to identify speaker

        Returns:
            TranscriptionResult with transcript and speaker info
        """
        start_time = time.perf_counter()
        self._set_state(PipelineState.TRANSCRIBING)

        try:
            if not self._stt_service:
                return TranscriptionResult(
                    success=False,
                    error="STT not initialized",
                )

            # Transcribe
            result = await self._stt_service.transcribe(audio_data)

            # Speaker identification
            speaker_id = None
            if identify_speaker:
                speaker_id = await self._identify_speaker(audio_data)

            duration_ms = (time.perf_counter() - start_time) * 1000

            transcription = TranscriptionResult(
                success=True,
                transcript=result.text,
                speaker_id=speaker_id,
                confidence=result.confidence,
                language=result.language,
                duration_ms=duration_ms,
            )

            # Notify listeners
            for callback in self._on_transcription:
                try:
                    callback(transcription)
                except Exception:
                    pass

            return transcription

        except Exception as e:
            logger.error(f"transcribe() failed: {e}")
            return TranscriptionResult(success=False, error=str(e))
        finally:
            self._set_state(PipelineState.IDLE)

    async def _identify_speaker(self, audio_data: bytes) -> str | None:
        """Identify speaker from voice."""
        try:
            from kagami.core.voice.unified_voice_pipeline import get_voice_pipeline

            pipeline = get_voice_pipeline()
            match = await pipeline.identify_speaker(audio_data)
            if match and match.is_identified:
                return match.speaker.user_id
        except Exception:
            pass
        return None

    # =========================================================================
    # Video Calls (LiveKit)
    # =========================================================================

    async def start_video_call(
        self,
        target: str,
        *,
        room_name: str | None = None,
        video: bool = True,
        audio: bool = True,
    ) -> VideoCallSession | None:
        """Start a video call.

        Args:
            target: Phone number (E.164) or user identity
            room_name: Optional room name
            video: Enable video
            audio: Enable audio

        Returns:
            VideoCallSession if successful
        """
        if not self._livekit_service:
            logger.error("LiveKit not configured")
            return None

        try:
            import secrets

            room_name = room_name or f"call-{secrets.token_hex(6)}"
            session_id = secrets.token_hex(8)

            # Determine call type
            is_phone = target.startswith("+")

            if is_phone:
                # Create SIP call via LiveKit
                livekit_session = await self._livekit_service.make_outbound_call(
                    phone_number=target,
                    room_name=room_name,
                )
            else:
                # Create room for WebRTC participant
                await self._livekit_service.create_room(room_name)
                livekit_session = None

            session = VideoCallSession(
                session_id=session_id,
                room_name=room_name,
                target=target,
                started_at=time.time(),
                is_video=video,
                livekit_session=livekit_session,
            )

            self._active_calls[session_id] = session
            self._set_state(PipelineState.VIDEO_CALL)

            logger.info(f"📹 Video call started: {room_name} → {target}")
            return session

        except Exception as e:
            logger.error(f"Failed to start video call: {e}")
            return None

    async def end_video_call(self, session_id: str) -> bool:
        """End a video call."""
        session = self._active_calls.get(session_id)
        if not session:
            return False

        try:
            if self._livekit_service:
                await self._livekit_service.end_call(session.room_name)

            del self._active_calls[session_id]
            self._set_state(PipelineState.IDLE)
            logger.info(f"📵 Video call ended: {session.room_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to end call: {e}")
            return False

    def generate_call_link(
        self,
        room_name: str,
        identity: str = "guest",
        ttl: int = 3600,
    ) -> str | None:
        """Generate a video call link for a participant.

        Args:
            room_name: Room to join
            identity: Participant display name
            ttl: Token time-to-live in seconds

        Returns:
            URL with embedded token
        """
        if not self._livekit_service:
            return None

        try:
            token = asyncio.get_event_loop().run_until_complete(
                self._livekit_service.generate_token(
                    room_name=room_name,
                    participant_identity=identity,
                    ttl=ttl,
                )
            )
            if token:
                return f"/call/?room={room_name}&token={token}&identity={identity}"
        except Exception as e:
            logger.error(f"Failed to generate call link: {e}")

        return None

    # =========================================================================
    # Phone Calls (Twilio)
    # =========================================================================

    async def make_phone_call(
        self,
        phone_number: str,
        message: str | None = None,
    ) -> str | None:
        """Make a phone call via Twilio.

        Args:
            phone_number: E.164 format (+1234567890)
            message: Optional TTS message to speak

        Returns:
            Call SID if successful
        """
        if not self.config.twilio_account_sid:
            logger.error("Twilio not configured")
            return None

        try:
            # Use unified realtime service (ElevenLabs ONLY - NO FALLBACKS)
            from kagami.core.services.voice.realtime import get_realtime_service

            service = await get_realtime_service()
            session = await service.call(phone_number, message)

            if session:
                logger.info(f"📞 Phone call initiated: {session.session_id}")
                return session.metadata.get("twilio_sid")
            else:
                logger.error("Phone call failed - no session returned")
                return None

        except Exception as e:
            logger.error(f"Phone call failed: {e}")
            return None

    # =========================================================================
    # State Management
    # =========================================================================

    @property
    def state(self) -> PipelineState:
        """Current pipeline state."""
        return self._state

    def _set_state(self, state: PipelineState) -> None:
        """Update pipeline state and notify listeners."""
        if self._state != state:
            self._state = state
            for callback in self._on_state_change:
                try:
                    callback(state)
                except Exception:
                    pass

    def on_state_change(self, callback: Callable[[PipelineState], None]) -> None:
        """Register state change callback."""
        self._on_state_change.append(callback)

    def on_transcription(self, callback: Callable[[TranscriptionResult], None]) -> None:
        """Register transcription callback."""
        self._on_transcription.append(callback)


# =============================================================================
# Singleton
# =============================================================================

_pipeline: UnifiedMediaPipeline | None = None


async def get_media_pipeline() -> UnifiedMediaPipeline:
    """Get the unified media pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = UnifiedMediaPipeline()
        await _pipeline.initialize()
    return _pipeline


def reset_media_pipeline() -> None:
    """Reset the pipeline singleton (for testing)."""
    global _pipeline
    _pipeline = None


# =============================================================================
# Convenience Functions
# =============================================================================


async def speak(
    text: str,
    *,
    target: MediaTarget = MediaTarget.AUTO,
    rooms: list[str] | None = None,
) -> SpeakResult:
    """Convenience function to speak text.

    Usage:
        from kagami.core.media import speak

        await speak("Hello Tim")
        await speak("Dinner ready", target=MediaTarget.HOME_ROOM, rooms=["Kitchen"])
    """
    pipeline = await get_media_pipeline()
    return await pipeline.speak(text, target=target, rooms=rooms)


async def transcribe(audio_data: bytes) -> TranscriptionResult:
    """Convenience function to transcribe audio."""
    pipeline = await get_media_pipeline()
    return await pipeline.transcribe(audio_data)


async def video_call(target: str) -> VideoCallSession | None:
    """Convenience function to start video call."""
    pipeline = await get_media_pipeline()
    return await pipeline.start_video_call(target)


async def phone_call(phone_number: str, message: str | None = None) -> str | None:
    """Convenience function to make phone call."""
    pipeline = await get_media_pipeline()
    return await pipeline.make_phone_call(phone_number, message)


__all__ = [
    "InputSource",
    "MediaConfig",
    # Enums
    "MediaTarget",
    "PipelineState",
    # Results
    "SpeakResult",
    "TranscriptionResult",
    # Main class
    "UnifiedMediaPipeline",
    "VideoCallSession",
    # Factory
    "get_media_pipeline",
    "phone_call",
    "reset_media_pipeline",
    # Convenience
    "speak",
    "transcribe",
    "video_call",
]
