"""Unified Voice Module — THE canonical voice interface.

**MESH IS CORE**: All voice output routes through mesh coordination.

This module provides:
- UnifiedVoicePipeline: Complete voice I/O pipeline
- STT: Speech-to-text (FasterWhisper)
- Speaker ID: Voice-based user identification
- TTS: Routes through UnifiedVoiceEffector → Mesh
- LiveKit: Real-time bidirectional voice/video (phone, WebRTC, OBS)
- ConsensusVoice: Distributed hub coordination (mesh core)

All voice operations should go through this module.

Usage:
    from kagami.core.voice import process_voice, speak

    # Input (STT)
    result = await process_voice(audio_bytes)
    print(f"{result.speaker.speaker.name}: {result.transcript}")

    # Output (TTS via mesh)
    await speak("Hello Tim")  # Auto-routes via mesh coordinator

    # Real-time bidirectional (LiveKit)
    from kagami.core.voice import get_livekit_service
    service = get_livekit_service()
    await service.make_outbound_call("+1234567890")

Architecture:
    speak() → UnifiedVoicePipeline → ConsensusVoiceCoordinator (mesh)
           → Hub selection → TTS → Spatial Audio → Output

Created: January 1, 2026
Updated: January 11, 2026 — Mesh-core consolidation
"""

from kagami.core.effectors.consensus_voice import (
    ConsensusVoiceCoordinator,
    DistributedVoiceMutex,
    HubSelection,
    HubVoiceCapability,
    VoicePriority,
    VoiceRequest,
    VoiceResult,
    get_consensus_voice,
)
from kagami.core.services.voice.livekit_integration import (
    CallSession,
    ConnectionType,
    LiveKitConfig,
    LiveKitService,
    StreamType,
    get_livekit_service,
)
from kagami.core.voice.unified_voice_pipeline import (
    FasterWhisperSTT,
    SpeakerIdentifier,
    SpeakerMatch,
    SpeakerProfile,
    # Providers
    STTProvider,
    # Main pipeline
    UnifiedVoicePipeline,
    VoiceContext,
    VoiceInputResult,
    # Data types
    VoiceInputState,
    get_voice_pipeline,
    # Convenience functions
    process_voice,
    reset_voice_pipeline,
    speak,
)

__all__ = [
    # LiveKit (Real-time Voice/Video)
    "CallSession",
    "ConnectionType",
    # Mesh Coordination (CORE)
    "ConsensusVoiceCoordinator",
    "DistributedVoiceMutex",
    "FasterWhisperSTT",
    "HubSelection",
    "HubVoiceCapability",
    "LiveKitConfig",
    "LiveKitService",
    # Providers
    "STTProvider",
    "SpeakerIdentifier",
    "SpeakerMatch",
    "SpeakerProfile",
    "StreamType",
    # Main pipeline
    "UnifiedVoicePipeline",
    "VoiceContext",
    "VoiceInputResult",
    # Data types
    "VoiceInputState",
    "VoicePriority",
    "VoiceRequest",
    "VoiceResult",
    "get_consensus_voice",
    "get_livekit_service",
    "get_voice_pipeline",
    # Convenience functions
    "process_voice",
    "reset_voice_pipeline",
    "speak",
]
