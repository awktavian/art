"""Kagami Genesis — Physics-based world simulation and rendering.

A high-performance world simulation and rendering engine for Kagami,
featuring physics-based simulation, real-time rendering, and spatial audio.

Key Capabilities:
- Physics simulation via Genesis engine
- Foveated rendering with gaze tracking
- Spatial audio synthesis
- Post-processing effects
- Hardware-accelerated rendering

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                     Genesis Engine                          │
    │                                                             │
    │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐ │
    │  │ Physics  │──►│ Renderer │──►│  Post-   │──►│  Output │ │
    │  │  Sim     │   │          │   │ Process  │   │         │ │
    │  └──────────┘   └──────────┘   └──────────┘   └─────────┘ │
    │        │              │              │              │       │
    │        └──────────────┴──────────────┴──────────────┘       │
    │                         Audio System                        │
    └─────────────────────────────────────────────────────────────┘

Modules:
- renderer/: Core rendering pipeline
  - foveated_rendering.py: Gaze-aware adaptive quality
  - audio_system.py: Physics-based spatial audio
  - hardware_detection.py: GPU/device detection
  - memory_profiler.py: VRAM tracking
- post_processing.py: Visual effects and filters
- materials.py: PBR material system
- cameras.py: Camera models and transforms
- optics.py: Optical simulation

Usage:
    from kagami_genesis import create_renderer, RenderConfig

    config = RenderConfig(width=1920, height=1080)
    renderer = create_renderer(config)

    # Render a scene
    frame = renderer.render(scene)

Created: December 2025
"""

__version__ = "0.1.0"

# Renderer components
# from kagami_genesis.renderer import (
#     FoveationConfig,
#     FrameStats,
#     RealtimeConfig,
# )

# Alias for backwards compatibility with docstring examples
# RenderConfig = RealtimeConfig

__all__ = [
    # "FoveationConfig",  # TODO: Re-export after renderer refactoring complete
    "FrameStats",
    "RealtimeConfig",
    "RenderConfig",
]
