"""Unified Composition System — Shot, Scene, Audio abstractions.

This is THE definition of Shot, Scene, and Audio for all of Kagami.
Replaces:
- effectors/video/hybrid_composer.py Shot
- kagami_media/production/shot.py Shot
- core/media/production/scene.py Scene/Beat

Usage:
    from kagami_studio.composition import Shot, Scene, Project, ShotType

    # Create a shot with audio layers
    shot = Shot(
        type=ShotType.DIALOGUE,
        text="Hello, I'm Kagami!",
        character="kagami",
        music="ambient_piano",  # Background music (ducked)
        sfx=["door_open"],      # Sound effects
    )

    # Create a scene with audio bed
    scene = Scene(
        name="Introduction",
        shots=[
            Shot(type=ShotType.ESTABLISHING, action_prompt="Modern smart home"),
            Shot(type=ShotType.DIALOGUE, text="Welcome home!", character="kagami"),
        ],
        audio_bed="cinematic_score",  # Scene-level music
    )

    # Render (audio is automatically mixed)
    result = await render_scene(scene)
"""

from kagami_studio.composition.audio import (
    AudioRenderer,
    AudioRenderResult,
    AudioTrack,
    get_audio_renderer,
)
from kagami_studio.composition.project import (
    Project,
    ProjectResult,
    render_project,
)
from kagami_studio.composition.scene import (
    Scene,
    SceneResult,
    render_scene,
)
from kagami_studio.composition.shot import (
    CameraAngle,
    Shot,
    ShotResult,
    ShotType,
    render_shot,
)

__all__ = [
    "AudioRenderResult",
    "AudioRenderer",
    "AudioTrack",
    "CameraAngle",
    "Project",
    "ProjectResult",
    "Scene",
    "SceneResult",
    "Shot",
    "ShotResult",
    "ShotType",
    "get_audio_renderer",
    "render_project",
    "render_scene",
    "render_shot",
]
