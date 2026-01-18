"""Conversational AI — Real-time bidirectional voice with ElevenLabs.

Full-duplex conversation with:
- ElevenLabs Conversational AI (WebSocket)
- Tim's cloned voice (mVI4sVQ8lmFpGDyfy6sQ)
- VAD (Voice Activity Detection)
- Interruption handling
- Turn-taking
- Kagami backend integration (tools, context)

Architecture:
```
                    ┌─────────────────────────────────────────┐
                    │        CONVERSATIONAL AI ENGINE          │
                    ├─────────────────────────────────────────┤
                    │                                          │
  Phone ──┐         │   ┌─────────┐      ┌─────────────┐      │
          │         │   │   VAD   │      │  ElevenLabs │      │
  WebRTC ─┼─ Audio ─┼──►│ + Turn  │─────►│   ConvAI    │      │
          │         │   │ Detect  │      │  WebSocket  │      │
  Hub ────┘         │   └────┬────┘      └──────┬──────┘      │
                    │        │                  │              │
                    │        │ Transcript       │ Audio        │
                    │        ▼                  ▼              │
                    │   ┌─────────────────────────────┐       │
                    │   │      Kagami Backend          │       │
                    │   │  (Tools, Context, Memory)    │       │
                    │   └─────────────────────────────┘       │
                    │                                          │
                    └─────────────────────────────────────────┘
```

Usage:
    from kagami.core.services.voice.conversational_ai import (
        ConversationalAI,
        start_phone_conversation,
        start_webrtc_conversation,
    )

    # Phone call (Twilio Media Streams → ElevenLabs)
    await start_phone_conversation("+16613105469")

    # WebRTC (Browser → ElevenLabs)
    session = await start_webrtc_conversation(room_name="call-123")

Created: January 7, 2026
Colony: Nexus (e₄)
鏡
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import websockets
from websockets import ClientConnection

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

ELEVENLABS_CONVAI_WS = "wss://api.elevenlabs.io/v1/convai/conversation"
SAMPLE_RATE = 16000
CHANNELS = 1
BITS_PER_SAMPLE = 16


class ConversationState(str, Enum):
    """Conversation state."""

    IDLE = "idle"
    CONNECTING = "connecting"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ENDED = "ended"


class AudioFormat(str, Enum):
    """Audio formats."""

    PCM_16000 = "pcm_16000"
    MULAW_8000 = "ulaw_8000"


# =============================================================================
# Data Types
# =============================================================================


@dataclass
class ConversationConfig:
    """Configuration for conversational AI."""

    agent_id: str = ""
    voice_id: str = "mVI4sVQ8lmFpGDyfy6sQ"  # Tim's voice

    # Audio settings
    input_format: AudioFormat = AudioFormat.PCM_16000
    output_format: AudioFormat = AudioFormat.PCM_16000

    # VAD settings
    vad_threshold: float = 0.5
    silence_duration_ms: int = 700  # End of turn after silence

    # Turn settings
    allow_interruption: bool = True
    max_duration_seconds: int = 600

    # Callbacks
    on_state_change: Callable[[ConversationState], None] | None = None
    on_transcript: Callable[[str, bool], None] | None = None  # (text, is_final)
    on_response: Callable[[str], None] | None = None
    on_audio: Callable[[bytes], None] | None = None
    on_tool_call: Callable[[str, dict], Any] | None = None


@dataclass
class ConversationSession:
    """Active conversation session."""

    session_id: str
    conversation_id: str = ""
    state: ConversationState = ConversationState.IDLE
    started_at: float = field(default_factory=time.time)

    # Stats
    user_turns: int = 0
    agent_turns: int = 0
    total_audio_ms: float = 0.0

    # Current turn
    current_transcript: str = ""
    current_response: str = ""


# =============================================================================
# ElevenLabs Conversational AI Client
# =============================================================================


class ElevenLabsConversationalAI:
    """Real-time bidirectional conversation with ElevenLabs.

    Handles:
    - WebSocket connection to ElevenLabs ConvAI
    - Audio streaming (both directions)
    - VAD and turn detection
    - Interruption handling
    - Tool calls to Kagami backend
    """

    def __init__(self, config: ConversationConfig):
        self.config = config
        self._ws: ClientConnection | None = None
        self._session: ConversationSession | None = None
        self._api_key: str = ""
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._running = False
        self._send_task: asyncio.Task | None = None
        self._recv_task: asyncio.Task | None = None

    async def initialize(self) -> bool:
        """Initialize with API key from keychain."""
        try:
            from kagami.core.security import get_secret

            self._api_key = get_secret("elevenlabs_api_key") or ""
            if not self.config.agent_id:
                self.config.agent_id = get_secret("elevenlabs_agent_id") or ""

            if not self._api_key or not self.config.agent_id:
                logger.error("Missing ElevenLabs credentials")
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            return False

    async def start(self) -> ConversationSession | None:
        """Start a conversation session."""
        if not self._api_key:
            if not await self.initialize():
                return None

        self._session = ConversationSession(
            session_id=secrets.token_hex(8),
        )
        self._set_state(ConversationState.CONNECTING)

        try:
            # Connect to ElevenLabs ConvAI WebSocket
            url = f"{ELEVENLABS_CONVAI_WS}?agent_id={self.config.agent_id}"
            headers = {"xi-api-key": self._api_key}

            self._ws = await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=30,
                open_timeout=30,  # Allow time for connection
                close_timeout=10,
            )

            # Send initialization
            await self._send_init()

            self._running = True

            # Start receive loop
            self._recv_task = asyncio.create_task(self._receive_loop())
            # Start send loop (for audio chunks)
            self._send_task = asyncio.create_task(self._send_loop())

            self._set_state(ConversationState.LISTENING)
            logger.info(f"🎙️ Conversation started: {self._session.session_id}")

            return self._session

        except Exception as e:
            logger.error(f"Failed to start conversation: {e}")
            self._set_state(ConversationState.ENDED)
            return None

    async def _send_init(self) -> None:
        """Send conversation initialization with single unified tool.

        Model Selection (ElevenLabs):
        - Turbo v2.5: Real-time conversation (~250ms) - good expressiveness
        - Flash v2.5: Ultra-low latency (~75ms) - less expressive
        - V3 Alpha: Best audio tags (NOT for real-time)

        We use Turbo v2.5 for the best balance of expressiveness + speed.
        """
        if not self._ws:
            return

        # SINGLE TOOL ARCHITECTURE
        # All capabilities encoded in system prompt, routed through one tool
        client_tools = [
            {
                "type": "function",
                "function": {
                    "name": "kagami",
                    "description": """Execute a Kagami command. Use this for ALL home control, digital actions, and queries.

SMART HOME:
- "set lights to 50% in living room"
- "turn off all lights"
- "movie mode" / "goodnight"
- "open shades in bedroom"
- "close all shades"
- "turn on fireplace" / "turn off fireplace"
- "lower the TV" / "raise the TV"
- "lock all doors"
- "announce 'dinner is ready' in kitchen"
- "play focus playlist" / "pause music"

DIGITAL (via Composio):
- "send email to X saying Y"
- "check my unread emails"
- "create calendar event for tomorrow at 3pm"
- "post tweet: Y"
- "create Linear issue: Y"
- "send slack message to #general: Y"

QUERIES:
- "what time is it"
- "what's the home status"
- "who is home"

Always call this tool when the user asks you to DO something.""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The natural language command to execute",
                            },
                        },
                        "required": ["command"],
                    },
                },
            },
        ]

        init_msg = {
            "type": "conversation_initiation_client_data",
            "conversation_initiation_client_data": {
                "conversation_config_override": {
                    "agent": {
                        "prompt": {
                            "prompt": self._get_system_prompt(),
                        },
                        "first_message": self._get_first_message(),
                    },
                    "tts": {
                        "voice_id": self.config.voice_id,
                        # Turbo v2.5: Best balance of expressiveness + real-time latency (~250ms)
                        # Flash v2.5: Ultra-low latency (~75ms) but less expressive
                        # V3: Best audio tags but NOT for real-time (500ms+)
                        "model_id": "eleven_v3",  # ALWAYS V3
                    },
                },
                "client_tools": client_tools,
            },
        }

        await self._ws.send(json.dumps(init_msg))

    def _get_first_message(self) -> str:
        """Get the opening message for the conversation."""
        from .prompts import get_first_message

        return get_first_message()

    def _get_system_prompt(self) -> str:
        """Get Kagami's system prompt - single tool architecture.

        Uses the centralized prompt from prompts.py for consistency
        across all voice interfaces.
        """
        from datetime import datetime

        from .prompts import get_system_prompt

        now = datetime.now()

        # Get the master prompt
        base_prompt = get_system_prompt()

        # Add dynamic context
        context = f"""

## Current Context

**Time:** {now.strftime("%I:%M %p, %A %B %d, %Y")}

## Voice Interaction Notes

Keep responses SHORT - this is voice, not text.
Be natural and conversational.
Execute first, confirm briefly after."""

        return base_prompt + context

    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio chunk to conversation.

        Args:
            audio_data: Raw PCM 16-bit audio at 16kHz
        """
        await self._audio_queue.put(audio_data)

    async def _send_loop(self) -> None:
        """Send audio chunks to WebSocket."""
        while self._running and self._ws:
            try:
                audio_data = await asyncio.wait_for(
                    self._audio_queue.get(),
                    timeout=1.0,
                )

                # Encode as base64 for WebSocket
                audio_b64 = base64.b64encode(audio_data).decode("utf-8")

                msg = {
                    "user_audio_chunk": audio_b64,
                }

                await self._ws.send(json.dumps(msg))

            except TimeoutError:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Send error: {e}")
                break

    async def _receive_loop(self) -> None:
        """Receive and process WebSocket messages."""
        if not self._ws:
            return

        try:
            async for message in self._ws:
                if not self._running:
                    break

                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON: {message[:100]}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Receive error: {e}")
        finally:
            self._set_state(ConversationState.ENDED)

    async def _handle_message(self, data: dict) -> None:
        """Handle incoming WebSocket message."""
        msg_type = data.get("type", "")

        if msg_type == "conversation_initiation_metadata":
            # Conversation started
            event = data.get("conversation_initiation_metadata_event", {})
            if self._session:
                self._session.conversation_id = event.get("conversation_id", "")
            logger.info(
                f"Conversation ID: {self._session.conversation_id if self._session else 'N/A'}"
            )

        elif msg_type == "user_transcript":
            # User's speech transcribed
            event = data.get("user_transcription_event", {})
            transcript = event.get("user_transcript", "")
            is_final = event.get("is_final", False)

            if self._session:
                self._session.current_transcript = transcript
                if is_final:
                    self._session.user_turns += 1

            if self.config.on_transcript:
                self.config.on_transcript(transcript, is_final)

            logger.debug(f"User: {transcript} (final={is_final})")

        elif msg_type == "agent_response":
            # Agent's text response
            event = data.get("agent_response_event", {})
            response = event.get("agent_response", "")

            if self._session:
                self._session.current_response = response
                self._session.agent_turns += 1

            if self.config.on_response:
                self.config.on_response(response)

            self._set_state(ConversationState.SPEAKING)
            logger.info(f"Kagami: {response}")

        elif msg_type == "audio":
            # Audio chunk from agent
            event = data.get("audio_event", {})
            audio_b64 = event.get("audio_base_64", "")

            if audio_b64:
                audio_data = base64.b64decode(audio_b64)

                if self._session:
                    # Estimate duration (16kHz, 16-bit mono)
                    duration_ms = len(audio_data) / (SAMPLE_RATE * 2) * 1000
                    self._session.total_audio_ms += duration_ms

                if self.config.on_audio:
                    # Handle both sync and async callbacks
                    result = self.config.on_audio(audio_data)
                    if asyncio.iscoroutine(result):
                        asyncio.create_task(result)

        elif msg_type == "interruption":
            # User interrupted the agent
            self._set_state(ConversationState.INTERRUPTED)
            logger.debug("User interrupted")

        elif msg_type == "agent_response_correction":
            # Agent corrected its response
            event = data.get("agent_response_correction_event", {})
            corrected = event.get("corrected_agent_response", "")
            logger.debug(f"Correction: {corrected}")

        elif msg_type == "ping":
            # Respond to ping
            event = data.get("ping_event", {})
            event_id = event.get("event_id", 0)
            ping_ms = event.get("ping_ms", 0)

            # Schedule pong
            asyncio.create_task(self._send_pong(event_id, ping_ms))

        elif msg_type == "client_tool_call":
            # Agent wants to call a tool
            await self._handle_tool_call(data)

        elif msg_type == "vad_score":
            # Voice activity detection score
            event = data.get("vad_score_event", {})
            score = event.get("score", 0.0)
            if score > self.config.vad_threshold:
                self._set_state(ConversationState.LISTENING)

        elif msg_type == "internal_tentative_agent_response":
            # Preliminary response (thinking)
            self._set_state(ConversationState.THINKING)

    async def _send_pong(self, event_id: int, ping_ms: int | None) -> None:
        """Send pong response after delay."""
        delay = (ping_ms or 0) / 1000
        if delay > 0:
            await asyncio.sleep(delay)

        if self._ws and self._running:
            pong = {
                "type": "pong",
                "event_id": event_id,
            }
            await self._ws.send(json.dumps(pong))

    async def _handle_tool_call(self, data: dict) -> None:
        """Handle tool call from agent."""
        event = data.get("client_tool_call", {})
        tool_name = event.get("tool_name", "")
        tool_params = event.get("parameters", {})
        tool_call_id = event.get("tool_call_id", "")

        logger.info(f"Tool call: {tool_name}({tool_params})")

        result = None
        if self.config.on_tool_call:
            result = self.config.on_tool_call(tool_name, tool_params)
        else:
            # Default tool handling via Kagami backend
            result = await self._execute_kagami_tool(tool_name, tool_params)

        # Send result back
        if self._ws:
            response = {
                "type": "client_tool_result",
                "tool_call_id": tool_call_id,
                "result": str(result) if result else "Done",
                "is_error": False,
            }
            await self._ws.send(json.dumps(response))

    async def _execute_kagami_tool(self, tool_name: str, params: dict) -> Any:
        """Execute Kagami command via unified MCP router.

        Single entry point - routes all commands through mcp_server.
        """
        try:
            from kagami.core.services.voice.mcp_server import execute_command

            # Single tool architecture
            if tool_name == "kagami":
                command = params.get("command", "")
            else:
                command = tool_name  # Legacy support

            if not command:
                return "No command provided"

            logger.info(f"🪞 Kagami: {command}")
            return await execute_command(command)

        except Exception as e:
            logger.error(f"Command failed: {e}")
            return f"Error: {e}"

    def _set_state(self, state: ConversationState) -> None:
        """Update conversation state."""
        if self._session:
            self._session.state = state

        if self.config.on_state_change:
            self.config.on_state_change(state)

    async def send_text(self, text: str) -> None:
        """Send text message (bypasses STT).

        Sends text directly to the agent as if the user spoke it.
        Triggers the same response flow as voice input.

        Args:
            text: Text message to send
        """
        if not self._ws:
            logger.warning("Cannot send text - no WebSocket connection")
            return

        # ElevenLabs ConvAI user_message format
        msg = {
            "type": "user_message",
            "text": text,
        }
        await self._ws.send(json.dumps(msg))
        logger.debug(f"📤 Sent text: {text[:50]}...")

    async def stop(self) -> None:
        """Stop the conversation."""
        self._running = False

        if self._send_task:
            self._send_task.cancel()
            try:
                await self._send_task
            except asyncio.CancelledError:
                pass

        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        self._set_state(ConversationState.ENDED)

        if self._session:
            logger.info(
                f"Conversation ended: {self._session.user_turns} user turns, "
                f"{self._session.agent_turns} agent turns, "
                f"{self._session.total_audio_ms:.0f}ms audio"
            )


# =============================================================================
# Twilio Integration
# =============================================================================


class TwilioElevenLabsBridge:
    """Bridge between Twilio Media Streams and ElevenLabs ConvAI.

    Handles:
    - Twilio → ElevenLabs: μ-law 8kHz → PCM 16kHz
    - ElevenLabs → Twilio: PCM 16kHz → μ-law 8kHz
    """

    def __init__(self, conversation: ElevenLabsConversationalAI):
        self.conversation = conversation
        self._twilio_ws: Any = None  # Can be FastAPI WebSocket or websockets WebSocket
        self._stream_sid: str = ""

    async def handle_twilio_websocket(self, websocket: Any) -> None:
        """Handle incoming Twilio Media Stream WebSocket.

        Supports both FastAPI WebSocket and websockets library WebSocket.
        """
        self._twilio_ws = websocket

        # Set up audio callback to send back to Twilio
        original_on_audio = self.conversation.config.on_audio

        async def on_audio(audio_data: bytes) -> None:
            # Convert PCM to μ-law and send to Twilio
            ulaw_data = self._pcm_to_ulaw(audio_data)
            await self._send_to_twilio(ulaw_data)

            if original_on_audio:
                original_on_audio(audio_data)

        self.conversation.config.on_audio = on_audio

        try:
            # Handle both FastAPI WebSocket and websockets library WebSocket
            while True:
                try:
                    # Try FastAPI WebSocket method first
                    if hasattr(websocket, "receive_text"):
                        message = await websocket.receive_text()
                    else:
                        # Fall back to websockets library
                        message = await websocket.recv()

                    data = json.loads(message)
                    event = data.get("event", "")

                    if event == "start":
                        self._stream_sid = data.get("streamSid", "")
                        logger.info(f"🎙️ Twilio stream started: {self._stream_sid}")

                    elif event == "media":
                        # Audio from caller
                        payload = data.get("media", {}).get("payload", "")
                        if payload:
                            ulaw_data = base64.b64decode(payload)
                            pcm_data = self._ulaw_to_pcm(ulaw_data)
                            await self.conversation.send_audio(pcm_data)

                    elif event == "stop":
                        logger.info("📴 Twilio stream stopped")
                        break

                except Exception as recv_error:
                    # Check if it's a disconnect
                    if (
                        "disconnect" in str(recv_error).lower()
                        or "closed" in str(recv_error).lower()
                    ):
                        logger.info("📴 WebSocket closed")
                        break
                    raise

        except Exception as e:
            logger.error(f"Twilio bridge error: {e}")
        finally:
            await self.conversation.stop()

    async def _send_to_twilio(self, ulaw_data: bytes) -> None:
        """Send audio back to Twilio."""
        if not self._twilio_ws or not self._stream_sid:
            return

        payload = base64.b64encode(ulaw_data).decode("utf-8")

        msg = {
            "event": "media",
            "streamSid": self._stream_sid,
            "media": {
                "payload": payload,
            },
        }

        msg_str = json.dumps(msg)

        # Handle both FastAPI WebSocket and websockets library WebSocket
        if hasattr(self._twilio_ws, "send_text"):
            await self._twilio_ws.send_text(msg_str)
        else:
            await self._twilio_ws.send(msg_str)

    @staticmethod
    def _ulaw_to_pcm(ulaw_data: bytes) -> bytes:
        """Convert μ-law 8kHz to PCM 16kHz."""
        # μ-law decoding table
        ULAW_TABLE = [
            -32124,
            -31100,
            -30076,
            -29052,
            -28028,
            -27004,
            -25980,
            -24956,
            -23932,
            -22908,
            -21884,
            -20860,
            -19836,
            -18812,
            -17788,
            -16764,
            -15996,
            -15484,
            -14972,
            -14460,
            -13948,
            -13436,
            -12924,
            -12412,
            -11900,
            -11388,
            -10876,
            -10364,
            -9852,
            -9340,
            -8828,
            -8316,
            -7932,
            -7676,
            -7420,
            -7164,
            -6908,
            -6652,
            -6396,
            -6140,
            -5884,
            -5628,
            -5372,
            -5116,
            -4860,
            -4604,
            -4348,
            -4092,
            -3900,
            -3772,
            -3644,
            -3516,
            -3388,
            -3260,
            -3132,
            -3004,
            -2876,
            -2748,
            -2620,
            -2492,
            -2364,
            -2236,
            -2108,
            -1980,
            -1884,
            -1820,
            -1756,
            -1692,
            -1628,
            -1564,
            -1500,
            -1436,
            -1372,
            -1308,
            -1244,
            -1180,
            -1116,
            -1052,
            -988,
            -924,
            -876,
            -844,
            -812,
            -780,
            -748,
            -716,
            -684,
            -652,
            -620,
            -588,
            -556,
            -524,
            -492,
            -460,
            -428,
            -396,
            -372,
            -356,
            -340,
            -324,
            -308,
            -292,
            -276,
            -260,
            -244,
            -228,
            -212,
            -196,
            -180,
            -164,
            -148,
            -132,
            -120,
            -112,
            -104,
            -96,
            -88,
            -80,
            -72,
            -64,
            -56,
            -48,
            -40,
            -32,
            -24,
            -16,
            -8,
            0,
            32124,
            31100,
            30076,
            29052,
            28028,
            27004,
            25980,
            24956,
            23932,
            22908,
            21884,
            20860,
            19836,
            18812,
            17788,
            16764,
            15996,
            15484,
            14972,
            14460,
            13948,
            13436,
            12924,
            12412,
            11900,
            11388,
            10876,
            10364,
            9852,
            9340,
            8828,
            8316,
            7932,
            7676,
            7420,
            7164,
            6908,
            6652,
            6396,
            6140,
            5884,
            5628,
            5372,
            5116,
            4860,
            4604,
            4348,
            4092,
            3900,
            3772,
            3644,
            3516,
            3388,
            3260,
            3132,
            3004,
            2876,
            2748,
            2620,
            2492,
            2364,
            2236,
            2108,
            1980,
            1884,
            1820,
            1756,
            1692,
            1628,
            1564,
            1500,
            1436,
            1372,
            1308,
            1244,
            1180,
            1116,
            1052,
            988,
            924,
            876,
            844,
            812,
            780,
            748,
            716,
            684,
            652,
            620,
            588,
            556,
            524,
            492,
            460,
            428,
            396,
            372,
            356,
            340,
            324,
            308,
            292,
            276,
            260,
            244,
            228,
            212,
            196,
            180,
            164,
            148,
            132,
            120,
            112,
            104,
            96,
            88,
            80,
            72,
            64,
            56,
            48,
            40,
            32,
            24,
            16,
            8,
            0,
        ]

        # Decode μ-law to PCM 8kHz
        pcm_8k = []
        for byte in ulaw_data:
            pcm_8k.append(ULAW_TABLE[byte])

        # Upsample 8kHz → 16kHz (simple linear interpolation)
        pcm_16k = []
        for i in range(len(pcm_8k)):
            pcm_16k.append(pcm_8k[i])
            if i < len(pcm_8k) - 1:
                # Interpolate
                pcm_16k.append((pcm_8k[i] + pcm_8k[i + 1]) // 2)
            else:
                pcm_16k.append(pcm_8k[i])

        # Pack as bytes
        return struct.pack(f"<{len(pcm_16k)}h", *pcm_16k)

    @staticmethod
    def _pcm_to_ulaw(pcm_data: bytes) -> bytes:
        """Convert PCM 16kHz to μ-law 8kHz."""
        # Unpack PCM
        num_samples = len(pcm_data) // 2
        samples = struct.unpack(f"<{num_samples}h", pcm_data)

        # Downsample 16kHz → 8kHz
        samples_8k = samples[::2]

        # PCM to μ-law encoding
        def encode_ulaw(sample: int) -> int:
            BIAS = 0x84
            MAX = 32635

            sign = (sample >> 8) & 0x80
            if sign:
                sample = -sample
            if sample > MAX:
                sample = MAX
            sample += BIAS

            exponent = 7
            exp_mask = 0x4000
            while (sample & exp_mask) == 0 and exponent > 0:
                exponent -= 1
                exp_mask >>= 1

            mantissa = (sample >> (exponent + 3)) & 0x0F
            return ~(sign | (exponent << 4) | mantissa) & 0xFF

        ulaw_bytes = bytes(encode_ulaw(s) for s in samples_8k)
        return ulaw_bytes


# =============================================================================
# Convenience Functions
# =============================================================================


_conversation: ElevenLabsConversationalAI | None = None


async def get_conversational_ai() -> ElevenLabsConversationalAI:
    """Get or create the conversational AI singleton."""
    global _conversation
    if _conversation is None:
        config = ConversationConfig()
        _conversation = ElevenLabsConversationalAI(config)
        await _conversation.initialize()
    return _conversation


async def start_conversation(
    on_audio: Callable[[bytes], None] | None = None,
    on_transcript: Callable[[str, bool], None] | None = None,
    on_response: Callable[[str], None] | None = None,
) -> ConversationSession | None:
    """Start a new conversation.

    Args:
        on_audio: Callback for audio chunks
        on_transcript: Callback for user transcripts
        on_response: Callback for agent responses

    Returns:
        ConversationSession if successful
    """
    config = ConversationConfig(
        on_audio=on_audio,
        on_transcript=on_transcript,
        on_response=on_response,
    )

    conversation = ElevenLabsConversationalAI(config)
    if not await conversation.initialize():
        return None

    return await conversation.start()


async def start_phone_conversation(
    phone_number: str,
    webhook_url: str | None = None,
) -> str | None:
    """Start a phone conversation with ElevenLabs ConvAI.

    This initiates a Twilio call that connects to ElevenLabs.

    Args:
        phone_number: E.164 format phone number
        webhook_url: URL for Twilio to connect Media Streams

    Returns:
        Call SID if successful
    """
    try:
        from twilio.rest import Client

        from kagami.core.security import get_secret

        account_sid = get_secret("twilio_account_sid")
        auth_token = get_secret("twilio_auth_token")
        from_number = get_secret("twilio_phone_number")

        if not all([account_sid, auth_token, from_number]):
            logger.error("Missing Twilio credentials")
            return None

        client = Client(account_sid, auth_token)

        # TwiML to connect to our WebSocket handler
        # This needs a publicly accessible webhook
        base_url = webhook_url or get_secret("kagami_api_url") or "https://api.kagami.dev"

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{base_url.replace("https://", "").replace("http://", "")}/ws/voice/twilio">
            <Parameter name="agent_id" value="{get_secret("elevenlabs_agent_id")}"/>
        </Stream>
    </Connect>
</Response>"""

        call = client.calls.create(
            to=phone_number,
            from_=from_number,
            twiml=twiml,
        )

        logger.info(f"📞 Phone conversation initiated: {call.sid}")
        return call.sid

    except Exception as e:
        logger.error(f"Failed to start phone conversation: {e}")
        return None


__all__ = [
    "AudioFormat",
    "ConversationConfig",
    "ConversationSession",
    "ConversationState",
    # Classes
    "ElevenLabsConversationalAI",
    "TwilioElevenLabsBridge",
    # Functions
    "get_conversational_ai",
    "start_conversation",
    "start_phone_conversation",
]
