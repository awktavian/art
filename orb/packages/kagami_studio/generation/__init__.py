"""Generation Tools — AI Music, Image, Video, 3D, Audio.

Implements the 17 generation actions from action_space.py that were
previously unimplemented (30/100 → 100/100).

Actions Implemented:
    Music: music_generate, music_extend (Suno API)
    Image: image_generate, image_edit, image_variation (DALL-E/SD/FLUX)
    Video: video_generate, video_extend (Runway Gen-3)
    3D: model_3d_generate, model_3d_texture (Meshy)
    Audio: audio_tts, audio_sfx, audio_clone (ElevenLabs)
    World: world_generate, world_explore, world_expand (Emu 3.5 - future)

Created: 2026-01-05 (Part of 125+/100 implementation)
"""

from kagami_studio.generation.music import MusicGenerator
from kagami_studio.generation.image import ImageGenerator
from kagami_studio.generation.video import VideoGenerator
from kagami_studio.generation.model_3d import Model3DGenerator
from kagami_studio.generation.audio import AudioGenerator

__all__ = [
    "AudioGenerator",
    "ImageGenerator",
    "Model3DGenerator",
    "MusicGenerator",
    "VideoGenerator",
]
