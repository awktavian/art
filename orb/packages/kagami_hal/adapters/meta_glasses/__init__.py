"""Meta Glasses HAL Adapter — Ray-Ban Meta Smart Glasses Integration.

Provides access to Meta's wearable smart glasses via the Device Access Toolkit (DAT).

Supports:
- Camera API (POV video stream, photo capture)
- Microphone API (spatial audio input)
- Open-Ear Audio API (directional audio output)

Note: Requires Meta DAT SDK on companion device (iOS/Android).
This adapter communicates with the companion app which bridges to the glasses.

Architecture:
    Glasses → BLE → Companion App → WebSocket → Kagami API → This Adapter

Created: December 30, 2025
"""

from __future__ import annotations

from kagami_hal.adapters.meta_glasses.audio import (
    AudioBuffer,
    AudioQuality,
    MetaGlassesAudio,
    MicrophoneConfig,
    OpenEarAudioConfig,
)
from kagami_hal.adapters.meta_glasses.camera import (
    CameraFrame,
    CameraResolution,
    CameraStreamConfig,
    MetaGlassesCamera,
    PhotoCaptureResult,
    VisualContext,
)
from kagami_hal.adapters.meta_glasses.protocol import (
    GlassesCommand,
    GlassesConnectionState,
    GlassesEvent,
    MetaGlassesProtocol,
)

__all__ = [
    "AudioBuffer",
    "AudioQuality",
    "CameraFrame",
    "CameraResolution",
    "CameraStreamConfig",
    "GlassesCommand",
    "GlassesConnectionState",
    "GlassesEvent",
    # Audio
    "MetaGlassesAudio",
    # Camera
    "MetaGlassesCamera",
    # Protocol
    "MetaGlassesProtocol",
    "MicrophoneConfig",
    "OpenEarAudioConfig",
    "PhotoCaptureResult",
    "VisualContext",
]

"""
Mirror
h(x) >= 0. Always.

First-person perspective extends the Markov blanket.
What you see, I sense. What I know, you hear.
"""
