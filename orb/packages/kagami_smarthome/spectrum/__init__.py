"""Spectrum Module — Unified Music-Light Frequency Mapping.

LIGHT IS MUSIC IS SPECTRUM.

This module provides the complete audio-visual synchronization system:

1. **SpectrumEngine** — Maps musical features to light parameters
2. **AdaptiveLightController** — Real-time music-reactive lights
3. **SpatialSyncController** — Synchronized spatial audio + lights
4. **OrchestralPlaybackController** — BBC SO rendering + lights

Usage:
    # Basic spectrum mapping
    from kagami_smarthome.spectrum import SpectrumEngine, MusicalContext

    engine = SpectrumEngine()
    context = MusicalContext(tempo_bpm=90, key="Am", dynamics=0.7)
    output = engine.compute(context)

    # Orchestral playback with lights
    from kagami_smarthome.spectrum import play_orchestral

    await play_orchestral(
        "/path/to/beethoven.mid",
        smart_home=controller,
    )

    # Real-time music-reactive lights
    from kagami_smarthome.spectrum import get_adaptive_lights

    adaptive = await get_adaptive_lights(controller)
    await adaptive.start()

Created: January 3, 2026
h(x) >= 0 always.
"""

from kagami_smarthome.spectrum.adaptive_lights import (
    AdaptiveLightConfig,
    AdaptiveLightController,
    SpotifyAudioFeatures,
    get_adaptive_lights,
)
from kagami_smarthome.spectrum.engine import (
    FrequencyBalance,
    MusicalContext,
    MusicMood,
    PatternType,
    SpectrumEngine,
    SpectrumOutput,
    frequency_to_hue,
    get_spectrum_engine,
    hue_to_wavelength,
)
from kagami_smarthome.spectrum.orchestral import (
    OrchestralPlaybackConfig,
    OrchestralPlaybackController,
    analyze_midi_context,
    play_orchestral,
    stop_orchestral,
)
from kagami_smarthome.spectrum.spatial_sync import (
    AudioFrame,
    RealtimeAnalyzer,
    SpatialLightMapper,
    SpatialSyncConfig,
    SpatialSyncController,
    demo_spectrum_sync,
    play_orchestral_with_lights,
)

__all__ = [
    # Core engine
    "FrequencyBalance",
    "MusicMood",
    "MusicalContext",
    "PatternType",
    "SpectrumEngine",
    "SpectrumOutput",
    "frequency_to_hue",
    "get_spectrum_engine",
    "hue_to_wavelength",
    # Adaptive lights
    "AdaptiveLightConfig",
    "AdaptiveLightController",
    "SpotifyAudioFeatures",
    "get_adaptive_lights",
    # Spatial sync
    "AudioFrame",
    "RealtimeAnalyzer",
    "SpatialLightMapper",
    "SpatialSyncConfig",
    "SpatialSyncController",
    "demo_spectrum_sync",
    "play_orchestral_with_lights",
    # Orchestral
    "OrchestralPlaybackConfig",
    "OrchestralPlaybackController",
    "analyze_midi_context",
    "play_orchestral",
    "stop_orchestral",
]
