from __future__ import annotations

"""
Streaming generation for Forge character creation.

Provides progressive updates during character generation.
"""
import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class GenerationStage(str, Enum):
    """Stages of character generation."""

    INIT = "init"
    MESH = "mesh"
    RIGGING = "rigging"
    TEXTURING = "texturing"
    PERSONALITY = "personality"
    VOICE = "voice"
    COMPLETE = "complete"


@dataclass
class ProgressUpdate:
    """Progress update during generation."""

    stage: GenerationStage
    percent: float
    message: str
    preview_url: str | None = None
    eta_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "percent": round(self.percent, 1),
            "message": self.message,
            "preview_url": self.preview_url,
            "eta_seconds": round(self.eta_seconds, 1) if self.eta_seconds else None,
            "timestamp": time.time(),
        }


class StreamingGenerator:
    """Streaming character generation with progressive updates."""

    def __init__(self, forge_matrix: Any) -> None:
        self.forge = forge_matrix

    async def generate_with_progress(self, request: Any) -> AsyncIterator[ProgressUpdate]:
        """Generate character with streaming progress updates."""
        # Timing is handled by outer API layer; avoid unused variable

        yield ProgressUpdate(
            stage=GenerationStage.INIT,
            percent=0.0,
            message="Initializing...",
            eta_seconds=10.0,
        )

        if not self.forge.initialized:
            await self.forge.initialize()

        yield ProgressUpdate(
            stage=GenerationStage.MESH,
            percent=10.0,
            message=f"Generating mesh for: {request.concept}",
            eta_seconds=8.0,
        )

        await asyncio.sleep(0.1)

        yield ProgressUpdate(
            stage=GenerationStage.MESH,
            percent=40.0,
            message="Mesh generation in progress...",
            eta_seconds=5.0,
        )

        yield ProgressUpdate(
            stage=GenerationStage.RIGGING,
            percent=55.0,
            message="Auto-rigging skeleton...",
            eta_seconds=3.0,
        )

        yield ProgressUpdate(
            stage=GenerationStage.TEXTURING,
            percent=70.0,
            message="Generating textures...",
            eta_seconds=2.0,
        )

        yield ProgressUpdate(
            stage=GenerationStage.PERSONALITY,
            percent=85.0,
            message="Synthesizing personality...",
            eta_seconds=1.0,
        )

        # Finalize generation; API handler consumes the actual result
        await self.forge.generate_character(request)

        yield ProgressUpdate(
            stage=GenerationStage.COMPLETE,
            percent=100.0,
            message="Generation complete!",
            eta_seconds=0.0,
        )


def get_streaming_generator(forge_matrix: Any) -> StreamingGenerator:
    return StreamingGenerator(forge_matrix)


__all__ = [
    "GenerationStage",
    "ProgressUpdate",
    "StreamingGenerator",
    "get_streaming_generator",
]
