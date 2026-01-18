"""Agent Voice — Per-agent voice sessions with i_speak intents.

WebSocket endpoint for voice interaction with specific agents:
- Requires Kagami Pro subscription
- Uses agent's i_speak configuration for intent matching
- Supports agent-specific voice IDs
- Processes intents through agent's action system

Protocol:
    Client → Server: PCM audio chunks (16kHz, 16-bit, mono)
    Server → Client: JSON messages (transcripts, responses) or audio (TTS)

Security:
- Pro subscription required for voice
- Per-user rate limiting

Colony: Nexus (e4) — Integration
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import struct
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from kagami.core.agents import get_agent_registry
from kagami.core.agents.auth import (
    AgentEntitlement,
    authenticate_websocket,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents-voice"])


# =============================================================================
# Message Types
# =============================================================================


class VoiceMessageType(str, Enum):
    """Types of voice WebSocket messages."""

    TRANSCRIPT = "transcript"
    FINAL_TRANSCRIPT = "final_transcript"
    RESPONSE = "response"
    AUDIO = "audio"
    INTENT_MATCHED = "intent_matched"
    ACTION_EXECUTED = "action_executed"
    ERROR = "error"
    END_OF_SPEECH = "end_of_speech"


# =============================================================================
# Voice Session
# =============================================================================


@dataclass
class AgentVoiceSession:
    """Tracks state for an agent voice session."""

    websocket: WebSocket
    agent_id: str
    session_id: str
    audio_buffer: bytearray
    start_time: float
    last_audio_time: float
    is_processing: bool = False
    transcript: str = ""
    voice_id: str = "kagami_female_1"

    @property
    def duration_ms(self) -> int:
        """Get session duration in milliseconds."""
        return int((time.time() - self.start_time) * 1000)


# Active sessions
_active_sessions: dict[str, AgentVoiceSession] = {}


# =============================================================================
# WebSocket Endpoint
# =============================================================================


@router.websocket("/v1/voice/{agent_id}")
async def agent_voice_stream(
    websocket: WebSocket,
    agent_id: str,
    token: str | None = Query(None, description="Auth token"),
):
    """WebSocket endpoint for voice interaction with a specific agent.

    Requires: Kagami Pro subscription.

    Uses the agent's i_speak configuration:
    - voice_id: ElevenLabs voice to use
    - wake_phrase: Optional wake phrase
    - intents: Patterns to match
    - responses: Named response templates

    Protocol:
        1. Client connects to /v1/voice/{agent_id}?token=xxx
        2. Client sends audio chunks (16kHz PCM)
        3. Server transcribes and matches intents
        4. Server executes matched actions
        5. Server sends response text and TTS audio
    """
    # Authenticate user
    user = await authenticate_websocket(websocket, token)
    if not user:
        await websocket.close(
            code=4001,
            reason="Authentication required. Connect with ?token=YOUR_JWT or sign up at kagami.ai/signup",
        )
        return

    # Check Pro entitlement for voice
    if not user.can_access(AgentEntitlement.AGENT_VOICE):
        await websocket.close(
            code=4002,
            reason="Pro subscription required for voice interaction. Upgrade at kagami.ai/pricing",
        )
        return

    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        await websocket.close(code=4004, reason=f"Agent not found: {agent_id}")
        return

    await websocket.accept()

    session_id = f"voice_{agent_id}_{int(time.time() * 1000)}"
    session = AgentVoiceSession(
        websocket=websocket,
        agent_id=agent_id,
        session_id=session_id,
        audio_buffer=bytearray(),
        start_time=time.time(),
        last_audio_time=time.time(),
        voice_id=agent.schema.i_speak.voice_id,
    )
    _active_sessions[session_id] = session

    logger.info(f"🎤 Agent voice session started: {agent_id}/{session_id}")

    # Send greeting
    greeting = agent.schema.i_speak.responses.get(
        "greeting", f"{agent.schema.i_am.name} listening."
    )
    await send_message(session, VoiceMessageType.RESPONSE, {"text": greeting})

    try:
        while True:
            data = await websocket.receive()

            if "bytes" in data:
                await handle_audio_data(session, agent, data["bytes"])
            elif "text" in data:
                message = json.loads(data["text"])
                await handle_control_message(session, agent, message)

    except WebSocketDisconnect:
        logger.info(f"🎤 Agent voice session ended: {session_id}")
    except Exception as e:
        logger.error(f"🎤 Agent voice session error: {e}")
        await send_error(session, str(e))
    finally:
        _active_sessions.pop(session_id, None)


# =============================================================================
# Message Handlers
# =============================================================================


async def handle_audio_data(session: AgentVoiceSession, agent: Any, audio_bytes: bytes) -> None:
    """Handle incoming audio data chunk."""
    session.audio_buffer.extend(audio_bytes)
    session.last_audio_time = time.time()

    # Start streaming STT when we have enough audio (~1 second)
    if len(session.audio_buffer) >= 32000 and not session.is_processing:
        asyncio.create_task(run_streaming_stt(session))


async def handle_control_message(session: AgentVoiceSession, agent: Any, message: dict) -> None:
    """Handle control messages from client."""
    msg_type = message.get("type")

    if msg_type == VoiceMessageType.END_OF_SPEECH.value:
        await process_complete_utterance(session, agent)


async def run_streaming_stt(session: AgentVoiceSession) -> None:
    """Run streaming speech-to-text on buffered audio."""
    if session.is_processing:
        return

    session.is_processing = True

    try:
        audio_data = bytes(session.audio_buffer)
        transcript = await transcribe_audio(audio_data)

        if transcript and transcript != session.transcript:
            session.transcript = transcript
            await send_message(session, VoiceMessageType.TRANSCRIPT, {"text": transcript})

    except Exception as e:
        logger.error(f"Streaming STT error: {e}")
    finally:
        session.is_processing = False


async def process_complete_utterance(session: AgentVoiceSession, agent: Any) -> None:
    """Process complete utterance after end-of-speech signal."""
    logger.info(f"🎤 Processing utterance ({len(session.audio_buffer)} bytes)")

    try:
        # Final transcription
        audio_data = bytes(session.audio_buffer)
        transcript = await transcribe_audio(audio_data)

        if not transcript:
            await send_error(session, "Could not transcribe audio")
            return

        await send_message(session, VoiceMessageType.FINAL_TRANSCRIPT, {"text": transcript})

        # Match intents and execute
        response_text, intent, actions = await match_and_execute_intent(agent, transcript)

        # Send intent match if found
        if intent:
            await send_message(
                session,
                VoiceMessageType.INTENT_MATCHED,
                {"intent": intent, "transcript": transcript},
            )

        # Execute actions
        for action in actions:
            try:
                from kagami_api.routes.agents.core import execute_agent_action

                result = await execute_agent_action(agent, action.get("type"), action)
                await send_message(
                    session,
                    VoiceMessageType.ACTION_EXECUTED,
                    {"action": action, "result": result},
                )
            except Exception as e:
                logger.error(f"Action execution failed: {e}")

        # Send response
        await send_message(
            session,
            VoiceMessageType.RESPONSE,
            {
                "text": response_text,
                "intent": intent,
                "latency_ms": session.duration_ms,
            },
        )

        # Generate and send TTS
        tts_audio = await generate_tts(response_text, session.voice_id)
        if tts_audio:
            await session.websocket.send_bytes(tts_audio)

        # Clear for next utterance
        session.audio_buffer.clear()
        session.transcript = ""

    except Exception as e:
        logger.error(f"Error processing utterance: {e}")
        await send_error(session, str(e))


# =============================================================================
# Intent Matching
# =============================================================================


async def match_and_execute_intent(
    agent: Any, transcript: str
) -> tuple[str, str | None, list[dict]]:
    """Match transcript against agent's i_speak intents.

    Args:
        agent: AgentState instance.
        transcript: Transcribed text.

    Returns:
        Tuple of (response_text, matched_intent, actions_to_execute).
    """
    transcript_lower = transcript.lower()
    i_speak = agent.schema.i_speak

    for intent in i_speak.intents:
        pattern = intent.pattern.lower()

        # Handle {variable} placeholders
        if "{" in pattern:
            # Convert to regex
            regex_pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>\\S+)", re.escape(pattern))
            regex_pattern = regex_pattern.replace(r"\ ", " ")  # Unescape spaces

            match = re.search(regex_pattern, transcript_lower)
            if match:
                # Extract captured variables
                variables = match.groupdict()

                # Substitute variables in action
                action = intent.action.copy()
                for key, value in action.items():
                    if isinstance(value, str):
                        for var_name, var_value in variables.items():
                            action[key] = value.replace(f"{{{var_name}}}", var_value)

                # Get response
                response_template = intent.response or i_speak.responses.get("default", "Done.")
                for var_name, var_value in variables.items():
                    response_template = response_template.replace(f"{{{var_name}}}", var_value)

                return (response_template, intent.pattern, [action])

        elif pattern in transcript_lower:
            response = intent.response or i_speak.responses.get("default", "Done.")
            return (response, intent.pattern, [intent.action])

    # No match - return fallback
    fallback = i_speak.responses.get("fallback", "I didn't understand. Try again?")
    return (fallback, None, [])


# =============================================================================
# Audio Processing
# =============================================================================


async def transcribe_audio(audio_data: bytes) -> str | None:
    """Transcribe audio using Whisper."""
    try:
        from kagami.core.services.stt import get_stt_service

        stt = get_stt_service()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
            write_wav(f, audio_data)

        transcript = await stt.transcribe(wav_path)
        os.unlink(wav_path)
        return transcript

    except ImportError:
        return await transcribe_with_openai(audio_data)
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return None


async def transcribe_with_openai(audio_data: bytes) -> str | None:
    """Fallback transcription using OpenAI Whisper API."""
    try:
        import openai

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
            write_wav(f, audio_data)

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
    """Write PCM data to WAV file."""
    data_size = len(pcm_data)
    file_size = data_size + 36

    file.write(b"RIFF")
    file.write(struct.pack("<I", file_size))
    file.write(b"WAVE")
    file.write(b"fmt ")
    file.write(struct.pack("<I", 16))
    file.write(struct.pack("<H", 1))
    file.write(struct.pack("<H", channels))
    file.write(struct.pack("<I", sample_rate))
    file.write(struct.pack("<I", sample_rate * channels * bits // 8))
    file.write(struct.pack("<H", channels * bits // 8))
    file.write(struct.pack("<H", bits))
    file.write(b"data")
    file.write(struct.pack("<I", data_size))
    file.write(pcm_data)


async def generate_tts(text: str, voice_id: str) -> bytes | None:
    """Generate TTS audio using ElevenLabs."""
    try:
        from kagami.core.effectors.voice import get_voice_service

        voice_service = get_voice_service()
        return await voice_service.synthesize(
            text=text,
            voice_id=voice_id,
            output_format="wav",
        )
    except ImportError:
        return await synthesize_with_elevenlabs(text, voice_id)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None


async def synthesize_with_elevenlabs(text: str, voice_id: str) -> bytes | None:
    """Fallback TTS using ElevenLabs API directly."""
    try:
        import aiohttp

        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            return None

        # Map custom voice IDs to ElevenLabs IDs
        voice_map = {
            "kagami_female_1": os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
        }
        el_voice_id = voice_map.get(voice_id, voice_id)

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{el_voice_id}",
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    # Turbo v2.5: Best expressiveness for real-time (~250ms)
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
            return None

    except Exception as e:
        logger.error(f"ElevenLabs API error: {e}")
        return None


# =============================================================================
# Utilities
# =============================================================================


async def send_message(session: AgentVoiceSession, msg_type: VoiceMessageType, data: dict) -> None:
    """Send JSON message to client."""
    message = {"type": msg_type.value, **data}
    await session.websocket.send_text(json.dumps(message))


async def send_error(session: AgentVoiceSession, error: str) -> None:
    """Send error message to client."""
    await send_message(session, VoiceMessageType.ERROR, {"message": error})


# =============================================================================
# Router Factory
# =============================================================================


def get_voice_router() -> APIRouter:
    """Get the agent voice router."""
    return router
