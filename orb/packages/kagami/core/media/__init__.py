"""Kagami Media — Unified Voice, Video, and Spatial Audio Pipeline.

THE single entry point for all media operations:

    from kagami.core.media import speak, video_call, phone_call, transcribe

    # Voice output with spatial routing
    await speak("Hello Tim")
    await speak("Dinner ready", target=MediaTarget.HOME_ROOM, rooms=["Kitchen"])

    # Video calls via LiveKit
    session = await video_call("+16613105469")

    # Phone calls via Twilio
    await phone_call("+16613105469", message="Hi from Kagami!")

    # Speech recognition
    result = await transcribe(audio_bytes)

Architecture:
    Input → STT → LLM → TTS → Spatial → Output
           ↓
    LiveKit (video) / Twilio (phone) for calls

Colony: Nexus (e₄) — Integration
Created: January 7, 2026
鏡
"""

from kagami.core.media.unified_pipeline import (
    InputSource,
    MediaConfig,
    # Enums
    MediaTarget,
    PipelineState,
    # Results
    SpeakResult,
    TranscriptionResult,
    # Main class
    UnifiedMediaPipeline,
    VideoCallSession,
    # Factory
    get_media_pipeline,
    phone_call,
    reset_media_pipeline,
    # Convenience
    speak,
    transcribe,
    video_call,
)

__all__ = [
    "InputSource",
    "MediaConfig",
    # Enums
    "MediaTarget",
    "PipelineState",
    # Results
    "SpeakResult",
    "TranscriptionResult",
    # Main class
    "UnifiedMediaPipeline",
    "VideoCallSession",
    # Factory
    "get_media_pipeline",
    "phone_call",
    "reset_media_pipeline",
    # Convenience
    "speak",
    "transcribe",
    "video_call",
]
