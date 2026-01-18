"""🎤 Voice WebSocket Endpoint — Real-time bidirectional voice streaming.

This module provides:
- WebSocket endpoint for audio streaming
- Integration with Whisper STT
- Integration with ElevenLabs TTS
- Intent execution through organism

Protocol:
    Client → Server: PCM audio chunks (16kHz, 16-bit, mono)
    Server → Client: JSON messages (transcripts, responses) or audio (TTS)

Message Types:
    - transcript: Partial transcript update
    - final_transcript: Complete transcript, processing started
    - response: Text response from Kagami
    - audio: TTS audio response (binary)
    - error: Error message

Colony: Nexus (e4) — Integration
Created: January 5, 2026
鏡
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import struct
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])


class VoiceMessageType(str, Enum):
    """Types of voice WebSocket messages."""

    TRANSCRIPT = "transcript"
    FINAL_TRANSCRIPT = "final_transcript"
    RESPONSE = "response"
    AUDIO = "audio"
    ERROR = "error"
    END_OF_SPEECH = "end_of_speech"


@dataclass
class VoiceSession:
    """Tracks state for a voice session."""

    websocket: WebSocket
    audio_buffer: bytearray
    start_time: float
    last_audio_time: float
    is_processing: bool = False
    transcript: str = ""

    @property
    def duration_ms(self) -> int:
        """Get session duration in milliseconds."""
        return int((time.time() - self.start_time) * 1000)


# Active voice sessions
_active_sessions: dict[str, VoiceSession] = {}


@router.websocket("/ws/voice")
async def voice_stream(websocket: WebSocket):
    """WebSocket endpoint for bidirectional voice streaming.

    Protocol:
        1. Client connects and sends audio chunks (16kHz PCM, 16-bit mono)
        2. Server accumulates audio and runs STT
        3. Server sends partial transcripts as they're available
        4. On end-of-speech, server runs intent through organism
        5. Server sends response text and TTS audio
        6. Connection can remain open for multi-turn conversation
    """
    await websocket.accept()

    session_id = f"voice_{int(time.time() * 1000)}"
    session = VoiceSession(
        websocket=websocket,
        audio_buffer=bytearray(),
        start_time=time.time(),
        last_audio_time=time.time(),
    )
    _active_sessions[session_id] = session

    logger.info(f"🎤 Voice session started: {session_id}")

    try:
        while True:
            # Receive data (can be binary audio or JSON control messages)
            data = await websocket.receive()

            if "bytes" in data:
                # Audio data
                await handle_audio_data(session, data["bytes"])

            elif "text" in data:
                # Control message
                message = json.loads(data["text"])
                await handle_control_message(session, message)

    except WebSocketDisconnect:
        logger.info(f"🎤 Voice session ended: {session_id}")

    except Exception as e:
        logger.error(f"🎤 Voice session error: {e}")
        await send_error(session, str(e))

    finally:
        _active_sessions.pop(session_id, None)


async def handle_audio_data(session: VoiceSession, audio_bytes: bytes) -> None:
    """Handle incoming audio data chunk.

    Args:
        session: Voice session state
        audio_bytes: PCM audio data (16kHz, 16-bit mono)
    """
    session.audio_buffer.extend(audio_bytes)
    session.last_audio_time = time.time()

    # Check if we have enough audio for streaming transcription
    # (~1 second of audio at 16kHz, 16-bit = 32000 bytes)
    if len(session.audio_buffer) >= 32000 and not session.is_processing:
        # Start streaming transcription in background
        asyncio.create_task(run_streaming_stt(session))


async def handle_control_message(session: VoiceSession, message: dict) -> None:
    """Handle control messages from client.

    Args:
        session: Voice session state
        message: Parsed JSON message
    """
    msg_type = message.get("type")

    if msg_type == VoiceMessageType.END_OF_SPEECH:
        # Client signaled end of speech, process the full audio
        await process_complete_utterance(session)

    else:
        logger.warning(f"Unknown voice message type: {msg_type}")


async def run_streaming_stt(session: VoiceSession) -> None:
    """Run streaming speech-to-text on buffered audio.

    Updates session transcript and sends partial results to client.
    """
    if session.is_processing:
        return

    session.is_processing = True

    try:
        # Convert buffer to audio file
        audio_data = bytes(session.audio_buffer)

        # Run Whisper STT
        transcript = await transcribe_audio(audio_data)

        if transcript and transcript != session.transcript:
            session.transcript = transcript

            # Send partial transcript
            await send_message(
                session,
                VoiceMessageType.TRANSCRIPT,
                {"text": transcript},
            )

    except Exception as e:
        logger.error(f"Streaming STT error: {e}")

    finally:
        session.is_processing = False


async def process_complete_utterance(session: VoiceSession) -> None:
    """Process complete utterance after end-of-speech signal.

    Steps:
        1. Run final STT on full audio
        2. Execute intent through organism
        3. Generate TTS response
        4. Send response text and audio to client
    """
    logger.info(f"🎤 Processing complete utterance ({len(session.audio_buffer)} bytes)")

    try:
        # Final transcription
        audio_data = bytes(session.audio_buffer)
        transcript = await transcribe_audio(audio_data)

        if not transcript:
            await send_error(session, "Could not transcribe audio")
            return

        # Send final transcript
        await send_message(
            session,
            VoiceMessageType.FINAL_TRANSCRIPT,
            {"text": transcript},
        )

        # Execute intent through organism
        response_text, intent = await execute_voice_intent(transcript)

        # Send text response
        await send_message(
            session,
            VoiceMessageType.RESPONSE,
            {
                "text": response_text,
                "intent": intent,
                "latency_ms": session.duration_ms,
            },
        )

        # Generate and send TTS audio
        tts_audio = await generate_tts(response_text)
        if tts_audio:
            await session.websocket.send_bytes(tts_audio)

        # Clear buffer for next utterance
        session.audio_buffer.clear()
        session.transcript = ""

    except Exception as e:
        logger.error(f"Error processing utterance: {e}")
        await send_error(session, str(e))


async def transcribe_audio(audio_data: bytes) -> str | None:
    """Transcribe audio using Whisper.

    Args:
        audio_data: PCM audio (16kHz, 16-bit mono)

    Returns:
        Transcribed text or None if failed
    """
    try:
        from kagami.core.services.stt import get_stt_service

        stt = get_stt_service()

        # Save to temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
            write_wav(f, audio_data)

        # Transcribe
        transcript = await stt.transcribe(wav_path)

        # Cleanup
        os.unlink(wav_path)

        return transcript

    except ImportError:
        # Fallback: Try OpenAI Whisper API directly
        return await transcribe_with_openai(audio_data)

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return None


async def transcribe_with_openai(audio_data: bytes) -> str | None:
    """Fallback transcription using OpenAI Whisper API.

    Args:
        audio_data: PCM audio data

    Returns:
        Transcribed text or None
    """
    try:
        import openai

        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
            write_wav(f, audio_data)

        # Call OpenAI API
        with open(wav_path, "rb") as audio_file:
            client = openai.OpenAI()
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
            )

        os.unlink(wav_path)
        return response.text

    except Exception as e:
        logger.error(f"OpenAI transcription error: {e}")
        return None


def write_wav(
    file, pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, bits: int = 16
) -> None:
    """Write PCM data to WAV file.

    Args:
        file: File object to write to
        pcm_data: Raw PCM audio data
        sample_rate: Sample rate in Hz
        channels: Number of channels
        bits: Bits per sample
    """
    # WAV header
    data_size = len(pcm_data)
    file_size = data_size + 36

    file.write(b"RIFF")
    file.write(struct.pack("<I", file_size))
    file.write(b"WAVE")
    file.write(b"fmt ")
    file.write(struct.pack("<I", 16))  # fmt chunk size
    file.write(struct.pack("<H", 1))  # PCM format
    file.write(struct.pack("<H", channels))
    file.write(struct.pack("<I", sample_rate))
    file.write(struct.pack("<I", sample_rate * channels * bits // 8))  # byte rate
    file.write(struct.pack("<H", channels * bits // 8))  # block align
    file.write(struct.pack("<H", bits))
    file.write(b"data")
    file.write(struct.pack("<I", data_size))
    file.write(pcm_data)


async def execute_voice_intent(transcript: str) -> tuple[str, str]:
    """Execute voice intent through Kagami organism.

    Args:
        transcript: Transcribed text

    Returns:
        Tuple of (response_text, intent_name)
    """
    try:
        from kagami.core.unified_agents import get_unified_organism

        organism = get_unified_organism()
        if organism is None:
            return ("I'm still waking up...", "error")

        # Build context for voice input
        context = {
            "source": "voice",
            "modality": "speech",
            "timestamp": datetime.now().isoformat(),
            "character": "You are Kagami (鏡), Tim's household assistant. Quick, warm, dry humor.",
            "identity": "kagami",
        }

        # Execute intent
        result = await organism.execute_intent(transcript, context=context)

        # Extract response
        response_text = "done ✓"
        intent_name = "unknown"

        if result:
            if hasattr(result, "output") and result.output:
                response_text = str(result.output)
            elif hasattr(result, "result") and result.result:
                response_text = str(result.result)
            elif isinstance(result, dict):
                response_text = result.get("output") or result.get("result") or "done ✓"
                intent_name = result.get("intent", "unknown")

        return (response_text, intent_name)

    except Exception as e:
        logger.error(f"Intent execution error: {e}")
        return (f"err: {str(e)[:50]}", "error")


async def generate_tts(text: str) -> bytes | None:
    """Generate TTS audio using ElevenLabs.

    Args:
        text: Text to synthesize

    Returns:
        WAV audio bytes or None if failed
    """
    try:
        from kagami.core.effectors.voice import get_voice_service

        voice_service = get_voice_service()
        audio_bytes = await voice_service.synthesize(
            text=text,
            voice_id="kagami",  # Custom Kagami voice
            output_format="wav",
        )
        return audio_bytes

    except ImportError:
        # Fallback: Try ElevenLabs API directly
        return await synthesize_with_elevenlabs(text)

    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None


async def synthesize_with_elevenlabs(text: str) -> bytes | None:
    """Fallback TTS using ElevenLabs API directly.

    Args:
        text: Text to synthesize

    Returns:
        Audio bytes or None
    """
    try:
        import aiohttp

        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            logger.warning("ElevenLabs API key not set")
            return None

        # Use a default voice
        voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_v3",  # ALWAYS V3
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.8,
                    },
                },
            ) as response,
        ):
            if response.status == 200:
                return await response.read()
            else:
                error = await response.text()
                logger.error(f"ElevenLabs error: {error}")
                return None

    except Exception as e:
        logger.error(f"ElevenLabs API error: {e}")
        return None


async def send_message(session: VoiceSession, msg_type: VoiceMessageType, data: dict) -> None:
    """Send JSON message to client.

    Args:
        session: Voice session
        msg_type: Message type
        data: Message data
    """
    message = {"type": msg_type.value, **data}
    await session.websocket.send_text(json.dumps(message))


async def send_error(session: VoiceSession, error: str) -> None:
    """Send error message to client.

    Args:
        session: Voice session
        error: Error message
    """
    await send_message(session, VoiceMessageType.ERROR, {"message": error})


# =============================================================================
# API Router Export
# =============================================================================


def get_voice_router() -> APIRouter:
    """Get the voice WebSocket router."""
    return router


"""
鏡

Voice flows like water.
Intent rises like mist.
Action falls like rain.

h(x) >= 0. Always.
"""
