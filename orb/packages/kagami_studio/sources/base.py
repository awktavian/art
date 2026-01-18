"""Base Source — Abstract base for all source types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class SourceType(str, Enum):
    """Source type enumeration."""

    CAMERA = "camera"
    SCREEN = "screen"
    IMAGE = "image"
    VIDEO = "video"
    AVATAR = "avatar"
    AUDIO = "audio"
    BROWSER = "browser"
    NDI = "ndi"
    GENERATED = "generated"


class SourceState(str, Enum):
    """Source state."""

    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class SourceInfo:
    """Source metadata."""

    id: str
    name: str
    type: SourceType
    state: SourceState = SourceState.INACTIVE
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    properties: dict[str, Any] = field(default_factory=dict)


class Source(ABC):
    """Abstract base class for all sources.

    All sources must implement:
    - start(): Begin capturing/generating
    - stop(): Stop capturing
    - get_frame(): Get current video frame
    - get_audio(): Get current audio samples (if applicable)
    """

    def __init__(self, source_id: str, name: str, source_type: SourceType):
        self.id = source_id
        self.name = name
        self.type = source_type
        self.state = SourceState.INACTIVE
        self._width = 0
        self._height = 0
        self._fps = 0.0

    @abstractmethod
    async def start(self) -> None:
        """Start the source."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the source."""
        pass

    @abstractmethod
    async def get_frame(self) -> np.ndarray | None:
        """Get the current video frame.

        Returns:
            BGR numpy array or None if no frame available
        """
        pass

    async def get_audio(self) -> np.ndarray | None:
        """Get current audio samples.

        Returns:
            Audio samples or None if not applicable
        """
        return None

    def get_info(self) -> SourceInfo:
        """Get source information."""
        return SourceInfo(
            id=self.id,
            name=self.name,
            type=self.type,
            state=self.state,
            width=self._width,
            height=self._height,
            fps=self._fps,
            has_audio=False,
        )

    def set_property(self, key: str, value: Any) -> None:
        """Set a source property."""
        pass

    def get_property(self, key: str) -> Any:
        """Get a source property."""
        return None
