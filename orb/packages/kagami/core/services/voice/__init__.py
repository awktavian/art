"""Voice Services — Unified Real-time Voice System.

============================================================================
THE SINGLE ENTRY POINT FOR ALL VOICE+VIDEO:
============================================================================

    from kagami.core.services.voice import (
        get_realtime_service,
        conversation,
        call,
        video_call,
    )

    service = await get_realtime_service()

    # Bidirectional ConvAI with VAD, turn-taking, interruption
    session = await service.conversation()

    # Phone call (one-way or bidirectional)
    session = await service.call("+16613105469")

    # Video call via LiveKit
    session = await service.video_call("room-name")

============================================================================
ARCHITECTURE:
============================================================================

    ┌─────────────────────────────────────────────────────────────┐
    │            UnifiedRealtimeService                           │
    │                                                             │
    │   conversation()     call()        video_call()             │
    │        │                │               │                   │
    │        └────────────────┼───────────────┘                   │
    │                         │                                   │
    │              ┌──────────▼──────────┐                        │
    │              │  ElevenLabs ConvAI  │                        │
    │              │  • VAD              │                        │
    │              │  • Turn-taking      │                        │
    │              │  • Tim's voice      │                        │
    │              │  • Tool calls       │                        │
    │              └──────────┬──────────┘                        │
    │                         │                                   │
    │         ┌───────────────┼───────────────┐                   │
    │         ▼               ▼               ▼                   │
    │    ┌─────────┐    ┌─────────┐    ┌─────────┐               │
    │    │ Twilio  │    │ LiveKit │    │  OBS    │               │
    │    │ PSTN    │    │ WebRTC  │    │ RTMP    │               │
    │    └─────────┘    └─────────┘    └─────────┘               │
    │                                                             │
    └─────────────────────────────────────────────────────────────┘

============================================================================
COMPONENTS:
============================================================================

Core (all go through UnifiedRealtimeService):
- realtime.py — THE unified service (call, conversation, video_call)
- conversational_ai.py — ElevenLabs ConvAI with VAD, tool calls
- livekit_integration.py — WebRTC video, SIP, RTMP egress
- twilio_config.py — Twilio phone number configuration

Supporting:
- kagami_voice.py — TTS with colony conditioning
- realtime_pipeline.py — Ultra-low latency multilingual TTS
- video_sync.py — Frame-accurate audio-video sync
- dialogue.py — Multi-speaker dialogue generation
- ai_answering_machine.py — Call handling with Theory of Mind
- home_theater_voice.py — KEF Reference 5.2.4 audio routing

============================================================================
QUICK START:
============================================================================

# Bidirectional conversation with VAD
from kagami.core.services.voice import conversation
session = await conversation()

# Phone call
from kagami.core.services.voice import call
session = await call("+16613105469", message="Hey Tim!")

# Video call
from kagami.core.services.voice import video_call
session = await video_call("my-room")
"""

from kagami.core.services.voice.agent_manager import (
    AgentManager,
    get_agent_manager,
    prank_call,
    restore_normal_mode,
    sync_agent,
)
from kagami.core.services.voice.ai_answering_machine import (
    AIAnsweringMachine,
    AnsweringMachineConfig,
    CallerRelationship,
    CallMode,
    TimTheoryOfMind,
    get_answering_machine,
    reset_answering_machine,
)
from kagami.core.services.voice.ai_answering_machine import (
    CallSession as AnsweringCallSession,
)
from kagami.core.services.voice.conversational_ai import (
    AudioFormat,
    ConversationConfig,
    ConversationSession,
    ConversationState,
    ElevenLabsConversationalAI,
    TwilioElevenLabsBridge,
    get_conversational_ai,
    start_conversation,
    start_phone_conversation,
)
from kagami.core.services.voice.dialogue import (
    DialogueGenerator,
    DialogueLine,
    DialogueResult,
    Speaker,
    VoiceSettings,
    create_voice_variant,
    get_dialogue_generator,
    remix_speaker_voice,
)
from kagami.core.services.voice.expressive_tags import (
    Emotion,
    Tag,
    build_expressive_text,
    laugh,
    pause,
    sing,
    whisper,
)
from kagami.core.services.voice.home_theater_voice import (
    HomeTheaterVoiceConfig,
    HomeTheaterVoiceService,
    VoiceInputState,
    VoiceSession,
    get_home_theater_voice,
    reset_home_theater_voice,
)
from kagami.core.services.voice.kagami_voice import (
    ELEVENLABS_MODEL,
    Colony,
    KagamiVoice,
    SpeakResult,
    get_kagami_voice,
)
from kagami.core.services.voice.kagami_voice import (
    synthesize as kagami_synthesize,
)
from kagami.core.services.voice.livekit_integration import (
    CallSession,
    ConnectionType,
    LiveKitConfig,
    LiveKitService,
    StreamType,
    get_livekit_service,
)
from kagami.core.services.voice.prompts import (
    VoiceMode,
    VoicePrompt,
    get_first_message,
    get_prompt,
    get_system_prompt,
    get_voice_mode,
    set_voice_mode,
)
from kagami.core.services.voice.realtime import (
    CallState,
    RealtimeSession,
    UnifiedRealtimeService,
    call,
    conversation,
    get_realtime_service,
    reset_realtime_service,
    video_call,
)
from kagami.core.services.voice.realtime import (
    CallType as RealtimeCallType,
)
from kagami.core.services.voice.realtime_pipeline import (
    ExpressiveSegment,
    LanguageCode,
    RealtimeVoicePipeline,
    SyncedAudioChunk,
    SynthesisResult,
    VoiceConfig,
    build_tagged_text,
    detect_language_boundaries,
    detect_language_fast,
    get_realtime_pipeline,
    parse_stage_direction,
    reset_pipeline,
)
from kagami.core.services.voice.realtime_pipeline import (
    WordTiming as PipelineWordTiming,
)
from kagami.core.services.voice.remixing import (
    REMIX_PRESETS,
    PromptStrength,
    RemixableVoice,
    RemixPreview,
    RemixResult,
    VoiceRemixer,
    get_voice_remixer,
    quick_remix,
)
from kagami.core.services.voice.twilio_config import (
    TwilioConfigResult,
    configure_twilio,
    get_twilio_status,
    set_caller_id,
)
from kagami.core.services.voice.video_sync import (
    FrameSync,
    SyncState,
    VideoSyncEngine,
    Viseme,
    VisemeFrame,
    export_subtitles,
    generate_visemes_from_words,
    get_video_sync_engine,
    interpolate_word_position,
    reset_sync_engine,
    sync_to_frames,
)
from kagami.core.services.voice.video_sync import (
    WordTiming as SyncWordTiming,
)

__all__ = [
    "REMIX_PRESETS",
    # AI Answering Machine (Theory of Mind)
    "AIAnsweringMachine",
    # Agent Manager (ElevenLabs sync)
    "AgentManager",
    "AnsweringCallSession",
    "AnsweringMachineConfig",
    # Conversational AI (Real-time Bidirectional)
    "AudioFormat",
    "CallMode",
    # LiveKit (Real-time Voice/Video)
    "CallSession",
    # ==========================================================================
    # UNIFIED REALTIME SERVICE — THE SINGLE ENTRY POINT
    # ==========================================================================
    # All voice+video goes through here:
    #   - conversation() — Bidirectional ConvAI with VAD
    #   - call() — Phone calls (one-way or bidirectional)
    #   - video_call() — LiveKit WebRTC
    # ==========================================================================
    "CallState",
    "CallerRelationship",
    "Colony",
    "ConnectionType",
    "ConversationConfig",
    "ConversationSession",
    "ConversationState",
    # Dialogue
    "DialogueGenerator",
    "DialogueLine",
    "DialogueResult",
    "ElevenLabsConversationalAI",
    "Emotion",
    # Realtime Pipeline (< 100ms TTFA)
    "ExpressiveSegment",
    # Video Sync
    "FrameSync",
    # Home Theater Voice (Control4 → Mac Studio)
    "HomeTheaterVoiceConfig",
    "HomeTheaterVoiceService",
    # Kagami voice
    "KagamiVoice",
    "LanguageCode",
    "LiveKitConfig",
    "LiveKitService",
    "ELEVENLABS_MODEL",
    "PipelineWordTiming",
    "PromptStrength",
    "RealtimeSession",
    "RealtimeVoicePipeline",
    "RemixPreview",
    "RemixResult",
    "RemixableVoice",
    "SpeakResult",
    "Speaker",
    "StreamType",
    "SyncState",
    "SyncWordTiming",
    "SyncedAudioChunk",
    "SynthesisResult",
    "Tag",
    "TimTheoryOfMind",
    # Twilio Configuration
    "TwilioConfigResult",
    "TwilioElevenLabsBridge",
    "UnifiedRealtimeService",
    "VideoSyncEngine",
    "Viseme",
    "VisemeFrame",
    "VoiceConfig",
    "VoiceInputState",
    # Voice Mode / Prompts
    "VoiceMode",
    "VoicePrompt",
    # Remixing
    "VoiceRemixer",
    "VoiceSession",
    "VoiceSettings",
    # Tags
    "build_expressive_text",
    "build_tagged_text",
    "call",
    "configure_twilio",
    "conversation",  # Bidirectional ConvAI with VAD
    "create_voice_variant",
    "detect_language_boundaries",
    "detect_language_fast",
    "export_subtitles",
    "generate_visemes_from_words",
    "get_agent_manager",
    "get_answering_machine",
    "get_conversational_ai",
    "get_dialogue_generator",
    "get_first_message",
    "get_home_theater_voice",
    "get_kagami_voice",
    "get_livekit_service",
    "get_prompt",
    "get_realtime_pipeline",
    "get_realtime_service",
    "get_system_prompt",
    "get_twilio_status",
    "get_video_sync_engine",
    "get_voice_mode",
    "get_voice_remixer",
    "interpolate_word_position",
    "kagami_synthesize",
    "laugh",
    "parse_stage_direction",
    "pause",
    "prank_call",
    "quick_remix",
    "remix_speaker_voice",
    "reset_answering_machine",
    "reset_home_theater_voice",
    "reset_pipeline",
    "reset_realtime_service",
    "reset_sync_engine",
    "restore_normal_mode",
    "set_caller_id",
    "set_voice_mode",
    "sing",
    "start_conversation",
    "start_phone_conversation",
    "sync_agent",
    "sync_to_frames",
    "video_call",
    "whisper",
]
