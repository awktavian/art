"""Scene Management — OBS-like scene composition."""

from kagami_studio.scenes.manager import SceneManager
from kagami_studio.scenes.overlays import LowerThird, Overlay, TextOverlay
from kagami_studio.scenes.scene import Scene, SceneItem
from kagami_studio.scenes.stinger import StingerLibrary, StingerTransition
from kagami_studio.scenes.transitions import Transition, TransitionType

__all__ = [
    "LowerThird",
    "Overlay",
    "Scene",
    "SceneItem",
    "SceneManager",
    "StingerLibrary",
    "StingerTransition",
    "TextOverlay",
    "Transition",
    "TransitionType",
]
