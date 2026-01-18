"""WebSocket Routes Package.

Contains WebSocket endpoints for real-time communication:
- twilio_voice: Twilio Media Streams ↔ ElevenLabs ConvAI bridge
- voice: General voice WebSocket endpoints
"""

from kagami_api.routes.websockets.twilio_voice import router as twilio_voice_router
from kagami_api.routes.websockets.voice import router as voice_router

__all__ = ["twilio_voice_router", "voice_router"]
