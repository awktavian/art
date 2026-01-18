"""Source Management — All input sources for Kagami Studio.

Source Types:
    - CameraSource: Webcam, capture card
    - ScreenSource: Display capture
    - ImageSource: Static images
    - VideoSource: Video files (with loop)
    - AvatarSource: AI avatar (real-time)
    - AudioSource: Audio inputs
    - BrowserSource: Web page capture
    - NDISource: NDI input
    - GeneratedSource: AI-generated content

Usage:
    manager = SourceManager(config)
    await manager.initialize()

    # Add sources
    cam_id = await manager.add_camera(0)
    img_id = await manager.add_image(Path("background.png"))
    avatar_id = await manager.add_avatar("kagami")

    # Get frames
    frame = await manager.get_frame(cam_id)
"""

from kagami_studio.sources.audio import AudioSource
from kagami_studio.sources.avatar import AvatarSource
from kagami_studio.sources.base import Source, SourceState, SourceType
from kagami_studio.sources.browser import BrowserSource
from kagami_studio.sources.camera import CameraSource
from kagami_studio.sources.image import ImageSource
from kagami_studio.sources.manager import SourceManager
from kagami_studio.sources.ndi import NDISource
from kagami_studio.sources.screen import ScreenSource
from kagami_studio.sources.video import VideoSource

__all__ = [
    "AudioSource",
    "AvatarSource",
    "BrowserSource",
    # Sources
    "CameraSource",
    "ImageSource",
    "NDISource",
    "ScreenSource",
    # Base
    "Source",
    # Manager
    "SourceManager",
    "SourceState",
    "SourceType",
    "VideoSource",
]
