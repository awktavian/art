"""Output Management — Recording, streaming, virtual camera."""

from kagami_studio.outputs.base import Output, OutputState, OutputType
from kagami_studio.outputs.manager import OutputManager
from kagami_studio.outputs.recording import RecordingOutput
from kagami_studio.outputs.streaming import StreamingOutput
from kagami_studio.outputs.virtual_cam import VirtualCamOutput

__all__ = [
    "Output",
    "OutputManager",
    "OutputState",
    "OutputType",
    "RecordingOutput",
    "StreamingOutput",
    "VirtualCamOutput",
]
