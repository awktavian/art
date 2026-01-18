"""Twilio Voice WebSocket — Bridge to ElevenLabs Conversational AI.

Handles Twilio Media Streams WebSocket connections and bridges them to
ElevenLabs real-time conversational AI.

Endpoint: /ws/voice/twilio

Flow:
    Twilio Call → Media Streams → This WebSocket → ElevenLabs ConvAI
                                        ↓
                             Tim's cloned voice responds
                                        ↓
                                  → Media Streams → Caller hears

Created: January 7, 2026
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws/voice", tags=["voice-websocket"])


@router.websocket("/twilio")
async def twilio_media_stream(websocket: WebSocket) -> None:
    """Handle Twilio Media Stream WebSocket.

    This endpoint receives audio from a Twilio call and bridges it to
    ElevenLabs Conversational AI for real-time bidirectional conversation.
    """
    await websocket.accept()
    logger.info("📞 Twilio Media Stream connected")

    try:
        from kagami.core.services.voice.conversational_ai import (
            ConversationConfig,
            ElevenLabsConversationalAI,
            TwilioElevenLabsBridge,
        )

        # Create conversation with callbacks for logging
        def on_transcript(text: str, is_final: bool) -> None:
            logger.info(f"👤 Caller: {text} {'✓' if is_final else '...'}")

        def on_response(text: str) -> None:
            logger.info(f"🪞 Kagami: {text}")

        config = ConversationConfig(
            on_transcript=on_transcript,
            on_response=on_response,
        )

        conversation = ElevenLabsConversationalAI(config)

        if not await conversation.initialize():
            logger.error("Failed to initialize ConversationalAI")
            await websocket.close()
            return

        # Start the ElevenLabs conversation
        session = await conversation.start()
        if not session:
            logger.error("Failed to start conversation")
            await websocket.close()
            return

        # Create bridge to handle audio conversion
        bridge = TwilioElevenLabsBridge(conversation)

        # Handle the WebSocket (this runs until disconnect)
        await bridge.handle_twilio_websocket(websocket)

    except WebSocketDisconnect:
        logger.info("📴 Twilio Media Stream disconnected")
    except Exception as e:
        logger.error(f"Twilio WebSocket error: {e}")
    finally:
        logger.info("Call ended")


@router.websocket("/elevenlabs")
async def elevenlabs_direct(websocket: WebSocket) -> None:
    """Direct ElevenLabs ConvAI WebSocket for web clients.

    This endpoint allows web browsers to connect directly to a conversation
    using WebRTC/WebSocket audio streaming.
    """
    await websocket.accept()
    logger.info("🌐 Direct ElevenLabs connection")

    try:
        import base64

        from kagami.core.services.voice.conversational_ai import (
            ConversationConfig,
            ElevenLabsConversationalAI,
        )

        # Callbacks for client
        audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

        def on_audio(data: bytes) -> None:
            audio_queue.put_nowait(data)

        def on_transcript(text: str, is_final: bool) -> None:
            asyncio.create_task(
                websocket.send_json(
                    {
                        "type": "transcript",
                        "text": text,
                        "is_final": is_final,
                    }
                )
            )

        def on_response(text: str) -> None:
            asyncio.create_task(
                websocket.send_json(
                    {
                        "type": "response",
                        "text": text,
                    }
                )
            )

        config = ConversationConfig(
            on_audio=on_audio,
            on_transcript=on_transcript,
            on_response=on_response,
        )

        conversation = ElevenLabsConversationalAI(config)

        if not await conversation.initialize():
            await websocket.send_json({"type": "error", "message": "Init failed"})
            await websocket.close()
            return

        session = await conversation.start()
        if not session:
            await websocket.send_json({"type": "error", "message": "Start failed"})
            await websocket.close()
            return

        await websocket.send_json(
            {
                "type": "connected",
                "session_id": session.session_id,
            }
        )

        # Audio send task
        async def send_audio() -> None:
            while True:
                try:
                    audio = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                    await websocket.send_json(
                        {
                            "type": "audio",
                            "data": base64.b64encode(audio).decode("utf-8"),
                        }
                    )
                except TimeoutError:
                    continue
                except Exception:
                    break

        send_task = asyncio.create_task(send_audio())

        try:
            # Receive audio from client
            async for message in websocket.iter_json():
                msg_type = message.get("type", "")

                if msg_type == "audio":
                    # Client sent audio chunk
                    audio_b64 = message.get("data", "")
                    if audio_b64:
                        audio_data = base64.b64decode(audio_b64)
                        await conversation.send_audio(audio_data)

                elif msg_type == "text":
                    # Client sent text (bypass STT)
                    text = message.get("text", "")
                    if text:
                        await conversation.send_text(text)

                elif msg_type == "end":
                    break

        finally:
            send_task.cancel()
            await conversation.stop()

    except WebSocketDisconnect:
        logger.info("🌐 Direct connection disconnected")
    except Exception as e:
        logger.error(f"Direct WebSocket error: {e}")
