"""Base Output — Abstract base for output types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

import numpy as np


class OutputType(str, Enum):
    """Output type enumeration."""

    RECORDING = "recording"
    STREAMING = "streaming"
    VIRTUAL_CAM = "virtual_cam"
    NDI = "ndi"


class OutputState(str, Enum):
    """Output state."""

    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    ERROR = "error"


class Output(ABC):
    """Abstract base for outputs."""

    def __init__(self, output_type: OutputType):
        self.type = output_type
        self.state = OutputState.INACTIVE

    @abstractmethod
    async def start(self) -> None:
        """Start the output."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the output."""
        pass

    @abstractmethod
    async def send_frame(self, frame: np.ndarray) -> None:
        """Send a video frame to the output."""
        pass

    async def send_audio(self, samples: np.ndarray) -> None:
        """Send audio samples to the output."""
        pass
