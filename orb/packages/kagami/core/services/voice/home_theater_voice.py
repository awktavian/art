"""Home Theater Voice Input — Control4 Remote → Mac Studio Voice Pipeline.

Enables voice interaction with Kagami through the home theater system:
- Monitors Denon AVR input selection via telnet
- When "Mac" input is selected, activates Mac Studio microphone
- Streams audio to STT pipeline, processes commands
- Responds through KEF Reference speakers

Architecture:
```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    HOME THEATER VOICE INPUT                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     AUTHENTICATION LAYER                             │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │   │
│   │  │ Denon Input  │  │ Network      │  │ Physical Presence        │   │   │
│   │  │ = "Mac"      │──│ = Local LAN  │──│ = Trusted Access         │   │   │
│   │  └──────────────┘  └──────────────┘  └──────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│   ┌─────────────────────────────────▼─────────────────────────────────┐     │
│   │                      VOICE CAPTURE                                 │     │
│   │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐  │     │
│   │  │ Mac Studio    │  │ Voice Activity│  │ Audio Buffer          │  │     │
│   │  │ Microphone    │──│ Detection     │──│ (speech segments)     │  │     │
│   │  └───────────────┘  └───────────────┘  └───────────────────────┘  │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                     │                                        │
│   ┌─────────────────────────────────▼─────────────────────────────────┐     │
│   │                       VOICE PIPELINE                               │     │
│   │  Microphone ──► VAD ──► STT (Whisper) ──► Kagami ──► TTS (Parler) │     │
│   │                                              │                     │     │
│   │                                              ▼                     │     │
│   │                               Denon HDMI → KEF Reference 5.2.4     │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

Security Model:
- **Physical Presence Auth**: Selecting "Mac" input on Control4 remote proves
  physical presence in the home. Equivalent to phone caller ID auth.
- **Local Network Only**: Input monitoring only accepts commands from local network.
- **No External Access**: This service does not expose any external endpoints.

Created: January 2026
Colony: Flow (e₃) — Real-time sensing
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from kagami_smarthome.integrations.denon import DenonIntegration

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class VoiceInputState(str, Enum):
    """Voice input service state."""

    DISABLED = "disabled"  # Service not running
    MONITORING = "monitoring"  # Watching Denon input, mic inactive
    LISTENING = "listening"  # Mic active, capturing audio
    PROCESSING = "processing"  # Processing captured audio
    RESPONDING = "responding"  # Playing TTS response


@dataclass
class HomeTheaterVoiceConfig:
    """Configuration for home theater voice input."""

    # Input trigger
    trigger_input: str = "Mac"  # Denon input name that activates mic
    trigger_input_code: str = "MPLAY"  # Denon telnet code for Mac (HDMI 6)

    # Polling
    input_poll_interval: float = 1.0  # How often to check Denon input (seconds)

    # Audio capture
    sample_rate: int = 16000  # Whisper prefers 16kHz
    channels: int = 1  # Mono for speech
    chunk_size: int = 1024  # Frames per buffer

    # Voice Activity Detection
    vad_energy_threshold: float = 0.01  # RMS energy threshold for speech
    vad_silence_duration: float = 1.5  # Seconds of silence to end utterance
    vad_min_speech_duration: float = 0.3  # Minimum speech duration

    # Safety
    max_listen_duration: float = 30.0  # Max seconds per utterance
    cooldown_after_response: float = 1.0  # Seconds before listening again

    # Network security
    allowed_networks: list[str] = field(default_factory=lambda: ["192.168.1.0/24", "127.0.0.0/8"])


# =============================================================================
# Voice Session (similar to phone CallSession)
# =============================================================================


@dataclass
class VoiceSession:
    """Active voice interaction session.

    Equivalent to CallSession in phone answering machine.
    Authentication is based on input source (physical presence) rather than caller ID.
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input_source: str = "Mac"  # Which Denon input triggered this

    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None

    # Authentication (physical presence)
    is_authenticated: bool = True  # If triggered by valid input, they're authed
    auth_method: str = "denon_input"  # How they authenticated

    # Conversation
    transcript: list[dict[str, str]] = field(default_factory=list)
    current_utterance: str = ""

    # Metrics
    audio_duration_ms: float = 0.0
    processing_time_ms: float = 0.0
    latency_ms: list[float] = field(default_factory=list)

    @property
    def turns(self) -> int:
        return len(self.transcript)

    def add_turn(self, role: str, text: str, latency: float | None = None) -> None:
        """Add conversation turn."""
        self.transcript.append(
            {
                "role": role,
                "text": text,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        if latency:
            self.latency_ms.append(latency)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API."""
        return {
            "session_id": self.session_id,
            "input_source": self.input_source,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "turns": self.turns,
            "auth_method": self.auth_method,
            "duration_seconds": (
                (self.ended_at or datetime.utcnow()) - self.started_at
            ).total_seconds(),
            "avg_latency_ms": (
                sum(self.latency_ms) / len(self.latency_ms) if self.latency_ms else 0
            ),
        }


# =============================================================================
# Home Theater Voice Service
# =============================================================================


class HomeTheaterVoiceService:
    """Voice input service for home theater system.

    Monitors Denon input selection and activates Mac Studio microphone when
    "Mac" input is selected. Uses physical presence (input selection) as
    authentication, similar to caller ID in the phone answering machine.

    Security Model:
    - Physical presence required (must use Control4 remote in living room)
    - Local network only (no external endpoints)
    - Input validation (only specific input triggers activation)
    """

    def __init__(self, config: HomeTheaterVoiceConfig | None = None) -> None:
        """Initialize the service.

        Args:
            config: Service configuration. Uses defaults if not provided.
        """
        self.config = config or HomeTheaterVoiceConfig()
        self._state = VoiceInputState.DISABLED

        # External services (lazy loaded)
        self._denon: DenonIntegration | None = None
        self._microphone: Any = None  # MacOSMicrophone
        self._voice_pipeline: Any = None  # UnifiedVoicePipeline
        self._tts: Any = None  # Voice effector

        # State
        self._active_session: VoiceSession | None = None
        self._session_history: list[VoiceSession] = []
        self._last_input: str = ""
        self._input_change_time: float = 0.0

        # Tasks
        self._monitor_task: asyncio.Task | None = None
        self._capture_task: asyncio.Task | None = None

        # Audio buffer
        self._audio_buffer: list[np.ndarray] = []
        self._last_speech_time: float = 0.0

        # Callbacks
        self._on_listening_start: Callable[[], None] | None = None
        self._on_listening_stop: Callable[[], None] | None = None
        self._on_command: Callable[[str, str], None] | None = None

        # Initialized flag
        self._initialized = False

    # =========================================================================
    # Initialization
    # =========================================================================

    async def initialize(self) -> bool:
        """Initialize all required services.

        Returns:
            True if initialization successful.
        """
        if self._initialized:
            return True

        logger.info("🎙️ Initializing Home Theater Voice Service...")

        # Initialize microphone
        try:
            from kagami_hal.adapters.macos.microphone import MacOSMicrophone

            self._microphone = MacOSMicrophone()
            success = await self._microphone.initialize(
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                chunk_size=self.config.chunk_size,
            )
            if not success:
                logger.warning("Microphone initialization failed")
                return False
            logger.info("✅ Microphone initialized")
        except ImportError:
            logger.warning("MacOSMicrophone not available")
            return False
        except Exception as e:
            logger.error(f"Microphone init error: {e}")
            return False

        # Initialize voice pipeline (STT)
        try:
            from kagami.core.voice import get_voice_pipeline

            self._voice_pipeline = await get_voice_pipeline()
            logger.info("✅ Voice pipeline initialized")
        except Exception as e:
            logger.warning(f"Voice pipeline not available: {e}")

        # Initialize TTS
        try:
            from kagami.core.effectors.voice import get_voice_effector

            self._tts = await get_voice_effector()
            logger.info("✅ TTS initialized")
        except Exception as e:
            logger.warning(f"TTS not available: {e}")

        self._initialized = True
        logger.info("✅ Home Theater Voice Service ready")
        return True

    def set_denon(self, denon: DenonIntegration) -> None:
        """Set Denon integration reference.

        Args:
            denon: Denon integration from SmartHomeController.
        """
        self._denon = denon
        logger.debug("Denon integration connected")

    # =========================================================================
    # Service Control
    # =========================================================================

    async def start(self) -> bool:
        """Start the voice input service.

        Begins monitoring Denon input selection.

        Returns:
            True if started successfully.
        """
        if not self._initialized:
            if not await self.initialize():
                return False

        if self._state != VoiceInputState.DISABLED:
            logger.warning("Service already running")
            return True

        if not self._denon:
            logger.error("Denon integration not set. Call set_denon() first.")
            return False

        self._state = VoiceInputState.MONITORING
        self._monitor_task = asyncio.create_task(
            self._input_monitor_loop(),
            name="home_theater_voice_monitor",
        )

        logger.info("🎙️ Home Theater Voice Service started (monitoring input)")
        return True

    async def stop(self) -> None:
        """Stop the voice input service."""
        self._state = VoiceInputState.DISABLED

        # Cancel tasks
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
            self._capture_task = None

        # Stop microphone
        if self._microphone:
            await self._microphone.stop_streaming()

        # End active session
        if self._active_session:
            await self._end_session()

        logger.info("🎙️ Home Theater Voice Service stopped")

    # =========================================================================
    # Input Monitoring
    # =========================================================================

    async def _input_monitor_loop(self) -> None:
        """Monitor Denon input selection.

        When "Mac" input is selected, activate microphone.
        When input changes away from "Mac", deactivate microphone.
        """
        logger.info(f"Monitoring Denon for input '{self.config.trigger_input}'...")

        while self._state != VoiceInputState.DISABLED:
            try:
                if not self._denon or not self._denon.is_connected:
                    await asyncio.sleep(self.config.input_poll_interval)
                    continue

                # Query current input
                current_input = await self._get_denon_input()

                # Check for input change
                if current_input != self._last_input:
                    logger.info(f"Denon input changed: {self._last_input} → {current_input}")
                    self._last_input = current_input
                    self._input_change_time = time.time()

                    # Check if trigger input selected
                    if self._is_trigger_input(current_input):
                        await self._activate_voice_input()
                    else:
                        await self._deactivate_voice_input()

                await asyncio.sleep(self.config.input_poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Input monitor error: {e}")
                await asyncio.sleep(self.config.input_poll_interval * 2)

    async def _get_denon_input(self) -> str:
        """Get current Denon input selection.

        Returns:
            Current input name (e.g., "Mac", "Apple TV").
        """
        if not self._denon:
            return ""

        try:
            # Query source via telnet
            response = await self._denon._query("SI?")
            if response:
                for line in response.split("\r"):
                    if line.startswith("SI"):
                        source_code = line[2:].strip()
                        # Map to friendly name
                        return self._denon._input_map.get(source_code, source_code)
        except Exception as e:
            logger.debug(f"Failed to get Denon input: {e}")

        return self._denon._source

    def _is_trigger_input(self, input_name: str) -> bool:
        """Check if input matches trigger.

        Args:
            input_name: Current input name.

        Returns:
            True if this input should trigger voice activation.
        """
        return input_name.lower() == self.config.trigger_input.lower()

    # =========================================================================
    # Voice Activation
    # =========================================================================

    async def _activate_voice_input(self) -> None:
        """Activate voice input (microphone + STT).

        Called when trigger input is selected.
        This is the authentication point - selecting the input proves physical presence.
        """
        if self._state == VoiceInputState.LISTENING:
            return  # Already active

        logger.info("🎙️ Activating voice input (Mac input selected)")

        # Create new session
        self._active_session = VoiceSession(
            input_source=self.config.trigger_input,
            is_authenticated=True,
            auth_method="denon_input_selection",
        )

        # Start microphone streaming
        if self._microphone:
            await self._microphone.start_streaming()

        self._state = VoiceInputState.LISTENING

        # Start capture task
        self._capture_task = asyncio.create_task(
            self._audio_capture_loop(),
            name="home_theater_voice_capture",
        )

        # Callback
        if self._on_listening_start:
            self._on_listening_start()

        # Play activation sound or announcement
        await self._announce_ready()

    async def _deactivate_voice_input(self) -> None:
        """Deactivate voice input.

        Called when input changes away from trigger.
        """
        if self._state == VoiceInputState.DISABLED:
            return

        if self._state == VoiceInputState.LISTENING:
            logger.info("🎙️ Deactivating voice input")

            # Cancel capture
            if self._capture_task:
                self._capture_task.cancel()
                try:
                    await self._capture_task
                except asyncio.CancelledError:
                    pass
                self._capture_task = None

            # Stop microphone
            if self._microphone:
                await self._microphone.stop_streaming()

            # End session
            await self._end_session()

            # Callback
            if self._on_listening_stop:
                self._on_listening_stop()

        self._state = VoiceInputState.MONITORING

    # =========================================================================
    # Audio Capture & Processing
    # =========================================================================

    async def _audio_capture_loop(self) -> None:
        """Capture audio and detect speech.

        Uses Voice Activity Detection (VAD) to segment speech.
        When speech is detected, buffers audio.
        When silence follows speech, processes the utterance.
        """
        logger.info("Audio capture loop started")

        self._audio_buffer = []
        self._last_speech_time = time.time()
        in_speech = False
        speech_start_time = 0.0

        while self._state == VoiceInputState.LISTENING:
            try:
                # Get audio chunk
                if not self._microphone:
                    await asyncio.sleep(0.1)
                    continue

                async for chunk in self._microphone.stream_audio():
                    if self._state != VoiceInputState.LISTENING:
                        break

                    # Voice Activity Detection
                    is_speech = self._detect_voice_activity(chunk)

                    if is_speech:
                        if not in_speech:
                            # Speech started
                            in_speech = True
                            speech_start_time = time.time()
                            logger.debug("Speech detected...")

                        self._audio_buffer.append(chunk)
                        self._last_speech_time = time.time()

                        # Check max duration
                        if time.time() - speech_start_time > self.config.max_listen_duration:
                            logger.warning("Max listen duration reached")
                            await self._process_utterance()
                            in_speech = False
                            self._audio_buffer = []
                    else:
                        if in_speech:
                            # Check if silence duration exceeded
                            silence_duration = time.time() - self._last_speech_time
                            if silence_duration > self.config.vad_silence_duration:
                                # Speech ended
                                speech_duration = time.time() - speech_start_time
                                if speech_duration >= self.config.vad_min_speech_duration:
                                    await self._process_utterance()
                                else:
                                    logger.debug(
                                        f"Speech too short ({speech_duration:.2f}s), ignoring"
                                    )
                                in_speech = False
                                self._audio_buffer = []

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audio capture error: {e}")
                await asyncio.sleep(0.1)

    def _detect_voice_activity(self, audio_chunk: np.ndarray) -> bool:
        """Simple energy-based Voice Activity Detection.

        Args:
            audio_chunk: Audio samples (float32, normalized to [-1, 1]).

        Returns:
            True if speech is detected.
        """
        if audio_chunk is None or len(audio_chunk) == 0:
            return False

        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_chunk**2))

        return rms > self.config.vad_energy_threshold

    async def _process_utterance(self) -> None:
        """Process captured utterance through STT and respond."""
        if not self._audio_buffer or not self._active_session:
            return

        self._state = VoiceInputState.PROCESSING
        start_time = time.time()

        # Combine audio chunks
        audio_data = np.concatenate(self._audio_buffer)
        self._audio_buffer = []

        logger.info(f"Processing utterance ({len(audio_data) / self.config.sample_rate:.1f}s)...")

        # Transcribe
        transcript = await self._transcribe_audio(audio_data)

        if not transcript:
            logger.debug("No transcript from utterance")
            self._state = VoiceInputState.LISTENING
            return

        logger.info(f"📝 Heard: '{transcript}'")

        # Record in session
        processing_time = (time.time() - start_time) * 1000
        self._active_session.add_turn("user", transcript, processing_time)
        self._active_session.current_utterance = transcript

        # Process command
        response = await self._process_command(transcript)

        if response:
            logger.info(f"💬 Response: '{response}'")
            self._active_session.add_turn("kagami", response)

            # Speak response
            self._state = VoiceInputState.RESPONDING
            await self._speak_response(response)

            # Cooldown before listening again
            await asyncio.sleep(self.config.cooldown_after_response)

        # Callback
        if self._on_command:
            self._on_command(transcript, response or "")

        # Resume listening
        self._state = VoiceInputState.LISTENING

    async def _transcribe_audio(self, audio_data: np.ndarray) -> str | None:
        """Transcribe audio to text.

        Args:
            audio_data: Audio samples as numpy array.

        Returns:
            Transcribed text or None.
        """
        if not self._voice_pipeline:
            logger.warning("Voice pipeline not available")
            return None

        try:
            # Convert to bytes (16-bit PCM)
            audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()

            # Write to temp file (Whisper prefers files)
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                # Write WAV header
                import wave

                with wave.open(f.name, "wb") as wav:
                    wav.setnchannels(self.config.channels)
                    wav.setsampwidth(2)  # 16-bit
                    wav.setframerate(self.config.sample_rate)
                    wav.writeframes(audio_bytes)

                audio_path = Path(f.name)

            # Transcribe
            result = await self._voice_pipeline.process_input(
                audio_data=audio_path,
                language="en",
            )

            # Cleanup
            audio_path.unlink(missing_ok=True)

            if result.success:
                return result.transcript
            return None

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None

    async def _process_command(self, transcript: str) -> str | None:
        """Process voice command and generate response.

        Routes to Kagami for processing.

        Args:
            transcript: Transcribed user speech.

        Returns:
            Response text or None.
        """
        # Import here to avoid circular imports
        try:
            from kagami.core.ambient.voice_interface import get_voice_interface

            voice_interface = await get_voice_interface()
            result = await voice_interface.process_voice_command(
                text=transcript,
                source="home_theater",
                room="living room",
            )

            if result and result.get("response"):
                return result["response"]

        except ImportError:
            logger.warning("Voice interface not available")
        except Exception as e:
            logger.error(f"Command processing failed: {e}")

        # Fallback: use simple echo for testing
        return f"I heard: {transcript}"

    async def _speak_response(self, text: str) -> None:
        """Speak response through home theater speakers.

        Args:
            text: Text to speak.
        """
        if not self._tts:
            logger.warning("TTS not available")
            return

        try:
            # Use Living Room (Denon → KEF)
            await self._tts.speak(
                text,
                rooms=["living room"],
                colony="kagami",
            )
        except Exception as e:
            logger.error(f"TTS failed: {e}")

    async def _announce_ready(self) -> None:
        """Announce that voice input is ready."""
        # Play a subtle audio cue instead of speaking
        # This avoids the awkward "I'm listening" announcement
        try:
            if self._tts:
                await self._tts.play_earcon("listening_start")
        except Exception:
            # Earcon optional, don't fail
            pass

    async def _end_session(self) -> None:
        """End the current voice session."""
        if not self._active_session:
            return

        self._active_session.ended_at = datetime.utcnow()
        self._session_history.append(self._active_session)

        logger.info(
            f"Voice session ended: {self._active_session.turns} turns, "
            f"{self._active_session.to_dict()['duration_seconds']:.1f}s"
        )

        self._active_session = None

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_listening_start(self, callback: Callable[[], None]) -> None:
        """Register callback for when listening starts."""
        self._on_listening_start = callback

    def on_listening_stop(self, callback: Callable[[], None]) -> None:
        """Register callback for when listening stops."""
        self._on_listening_stop = callback

    def on_command(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for processed commands.

        Args:
            callback: Function(transcript, response) called when command processed.
        """
        self._on_command = callback

    # =========================================================================
    # Status & API
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get service status."""
        return {
            "initialized": self._initialized,
            "state": self._state.value,
            "trigger_input": self.config.trigger_input,
            "current_input": self._last_input,
            "is_listening": self._state == VoiceInputState.LISTENING,
            "active_session": self._active_session.to_dict() if self._active_session else None,
            "total_sessions": len(self._session_history),
            "denon_connected": self._denon is not None and self._denon.is_connected,
            "microphone_ready": self._microphone is not None,
            "stt_ready": self._voice_pipeline is not None,
            "tts_ready": self._tts is not None,
        }

    def get_session_history(self, limit: int = 50) -> list[dict]:
        """Get recent session history."""
        return [s.to_dict() for s in self._session_history[-limit:]]

    @property
    def state(self) -> VoiceInputState:
        """Get current state."""
        return self._state

    @property
    def is_listening(self) -> bool:
        """Check if actively listening."""
        return self._state == VoiceInputState.LISTENING


# =============================================================================
# Factory
# =============================================================================

_home_theater_voice: HomeTheaterVoiceService | None = None


async def get_home_theater_voice(
    config: HomeTheaterVoiceConfig | None = None,
) -> HomeTheaterVoiceService:
    """Get singleton home theater voice service.

    Args:
        config: Optional configuration. Uses defaults if not provided.

    Returns:
        HomeTheaterVoiceService instance.
    """
    global _home_theater_voice
    if _home_theater_voice is None:
        _home_theater_voice = HomeTheaterVoiceService(config)
    return _home_theater_voice


def reset_home_theater_voice() -> None:
    """Reset singleton (for testing)."""
    global _home_theater_voice
    if _home_theater_voice:
        # Only stop if there's a running event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_home_theater_voice.stop())
        except RuntimeError:
            # No running event loop, just reset
            pass
    _home_theater_voice = None


__all__ = [
    "HomeTheaterVoiceConfig",
    "HomeTheaterVoiceService",
    "VoiceInputState",
    "VoiceSession",
    "get_home_theater_voice",
    "reset_home_theater_voice",
]
