"""Effectors — Kagami's action outputs.

Voice:
    from kagami.core.effectors.voice import speak, VoiceTarget
    await speak("Hello Tim")  # Auto-routes to correct output
    await speak("Goodnight", target=VoiceTarget.HOME_ALL)

Orchestra (BBC Symphony Orchestra):
    from kagami.core.effectors.bbc_renderer import get_bbc_renderer, render
    from kagami.core.effectors.bbc_stem_renderer import render_stem_gui
    from kagami.core.effectors.stem_manager import StemManager, get_stem_manager
    from kagami.core.effectors.spatial_mixer import mix_orchestral_stems, create_spatial_mix

Audio Verification:
    from kagami.core.effectors.audio_verification import check_audio_exists, analyze_wav

Spatial Audio:
    from kagami.core.effectors.spatial_audio import get_spatial_engine
    engine = await get_spatial_engine()
    await engine.play_spatial(audio_path)
"""

# Voice effector (THE canonical voice output)
# Audio verification
from kagami.core.effectors.audio_verification import (
    AudioMetrics,
    analyze_wav,
    check_audio_exists,
    get_silent_stems,
    get_stems_with_audio,
    verify_stems,
)

# BBC SO rendering
from kagami.core.effectors.bbc_stem_renderer import (
    BBCRenderConfig,
    create_bbc_render_func,
    render_stem_gui,
    render_stem_with_retry,
)

# Spatial mixing
from kagami.core.effectors.spatial_mixer import (
    MixConfig,
    StemMixConfig,
    create_spatial_mix,
    mix_orchestral_stems,
    mix_stems,
)

# Stem management
from kagami.core.effectors.stem_manager import (
    RenderProgress,
    StemCache,
    StemInfo,
    StemManager,
    get_stem_manager,
)
from kagami.core.effectors.voice import (
    UnifiedVoiceEffector,
    VoiceEffectorResult,
    VoiceTarget,
    announce,
    get_voice_effector,
    play_audio,
    speak,
    whisper,
)

__all__ = [
    # Audio verification
    "AudioMetrics",
    # BBC SO rendering
    "BBCRenderConfig",
    # Spatial mixing
    "MixConfig",
    # Stem management
    "RenderProgress",
    "StemCache",
    "StemInfo",
    "StemManager",
    "StemMixConfig",
    # Voice
    "UnifiedVoiceEffector",
    "VoiceEffectorResult",
    "VoiceTarget",
    "analyze_wav",
    "announce",
    "check_audio_exists",
    "create_bbc_render_func",
    "create_spatial_mix",
    "get_silent_stems",
    "get_stem_manager",
    "get_stems_with_audio",
    "get_voice_effector",
    "mix_orchestral_stems",
    "mix_stems",
    "play_audio",
    "render_stem_gui",
    "render_stem_with_retry",
    "speak",
    "verify_stems",
    "whisper",
]
