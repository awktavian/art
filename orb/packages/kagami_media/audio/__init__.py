"""Audio Extraction and Speaker Diarization Module.

Extracts audio from videos, performs speaker diarization,
and extracts clean voice samples for voice cloning.

Key Features:
- Audio track extraction from video
- Speaker diarization ("who spoke when")
- Transcription with word-level timestamps
- Voice sample extraction per speaker
- Speaker embedding generation (192-dim)

Usage:
    from kagami_media.audio import SpeakerDiarizer, VoiceExtractor

    diarizer = SpeakerDiarizer()
    segments = diarizer.diarize("video.mp4")

    extractor = VoiceExtractor()
    samples = extractor.extract_voice_samples(segments, "video.mp4")
"""

from kagami_media.audio.speaker_diarization import (
    DiarizationResult,
    SpeakerDiarizer,
    SpeakerSegment,
    diarize_audio,
)
from kagami_media.audio.voice_extractor import (
    VoiceExtractor,
    VoiceSample,
    extract_voice_samples,
)

__all__ = [
    "DiarizationResult",
    "SpeakerDiarizer",
    "SpeakerSegment",
    "VoiceExtractor",
    "VoiceSample",
    "diarize_audio",
    "extract_voice_samples",
]
