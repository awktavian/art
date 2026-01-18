"""Audio Processing — Mixing, ducking, and effects."""

from kagami_studio.audio.ducking import AudioDucker, DuckingConfig
from kagami_studio.audio.mixer import AudioChannel, AudioMixer, MixerConfig

__all__ = [
    "AudioChannel",
    "AudioDucker",
    "AudioMixer",
    "DuckingConfig",
    "MixerConfig",
]
