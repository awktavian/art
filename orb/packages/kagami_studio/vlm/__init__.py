"""Vision Language Model Integration — Gemini 3 Default.

Unified VLM interface for video understanding, transcription, and analysis.
Uses Gemini 3 Pro as primary model with automatic fallback.

CAPABILITIES:
- Video transcription with word-level timing
- Scene understanding and description
- Object/person detection and tracking
- Emotion and sentiment analysis
- Multi-language support

USAGE:
    from kagami_studio.vlm import transcribe_video, analyze_video

    # Transcription (Gemini 3 default)
    transcript = await transcribe_video("video.mp4")

    # Full analysis
    analysis = await analyze_video("video.mp4", include_scenes=True)

MODELS (priority order):
1. gemini-3-pro-preview (best quality)
2. gemini-2.5-pro (fallback)
3. whisper (audio-only fallback)
"""

from kagami_studio.vlm.gemini import (
    GeminiVLM,
    VLMAnalysis,
    VLMConfig,
    VLMScene,
    VLMSegment,
    VLMTranscript,
    VLMWord,
    analyze_video,
    get_vlm,
    transcribe_video,
)

__all__ = [
    "GeminiVLM",
    "VLMAnalysis",
    "VLMConfig",
    "VLMScene",
    "VLMSegment",
    "VLMTranscript",
    "VLMWord",
    "analyze_video",
    "get_vlm",
    "transcribe_video",
]
