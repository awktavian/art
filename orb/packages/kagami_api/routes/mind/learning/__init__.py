"""Learning API - Training streams and learning progress.

Endpoints at /api/mind/learning:
- WebSocket /stream - Training progress stream
- GET /state - Current training state
- GET /history - Training history
"""

from .training_stream import get_router

__all__ = ["get_router"]
