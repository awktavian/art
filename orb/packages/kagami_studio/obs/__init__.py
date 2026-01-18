"""🎬 OBS Studio Integration — Real-Time Production Control.

Full WebSocket integration with OBS Studio for:
- Scene management and transitions
- Source control (cameras, screens, NDI, browser)
- Filter management (chromakey, blur, color correction)
- Streaming and recording control
- Virtual camera output
- Real-time compositing

Requirements:
    pip install obsws-python

Quick Start:
    from kagami_studio.obs import OBSController, connect_obs

    # Context manager (recommended)
    async with connect_obs() as obs:
        await obs.switch_scene("Main")
        await obs.start_streaming()

    # Or manual
    obs = OBSController()
    await obs.connect()
    await obs.switch_scene("Kagami Live")
    await obs.disconnect()

Integration with Kagami Studio:
    from kagami_studio import Studio
    from kagami_studio.obs import OBSBridge

    async with Studio() as studio:
        # Bridge studio to OBS for real-time output
        bridge = OBSBridge(studio)
        await bridge.connect()

        # Now studio output goes to OBS
        await studio.generate_and_speak("Welcome!")

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                      Kagami Studio                          │
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐│
    │  │ Sources │  │ Scenes  │  │ Outputs │  │ AI Generation   ││
    │  └────┬────┘  └────┬────┘  └────┬────┘  └───────┬─────────┘│
    │       │            │            │                │          │
    │       └────────────┴────────────┴────────────────┘          │
    │                            │                                │
    │                      OBS Bridge                             │
    │                            │                                │
    └────────────────────────────┼────────────────────────────────┘
                                 │
                          ┌──────┴──────┐
                          │ OBS Studio  │
                          │ (WebSocket) │
                          └─────────────┘

Version: 1.0.0
"""

from kagami_studio.obs.bridge import (
    BridgeMode,
    OBSBridge,
)
from kagami_studio.obs.client import (
    OBSConfig,
    OBSConnectionState,
    OBSController,
    connect_obs,
)
from kagami_studio.obs.compositing import (
    CompositeLayer,
    LayerBlendMode,
    OBSCompositor,
    create_corner_cam_layout,
    create_pip_layout,
    create_side_by_side_layout,
)
from kagami_studio.obs.filters import (
    FilterType,
    OBSFilter,
    create_blur_filter,
    create_chromakey_filter,
    create_color_correction_filter,
    create_lut_filter,
)
from kagami_studio.obs.scenes import (
    OBSScene,
    OBSSceneItem,
    OBSTransition,
    TransitionType,
)
from kagami_studio.obs.sources import (
    OBSSource,
    OBSSourceSettings,
    OBSSourceType,
    create_browser_source,
    create_image_source,
    create_media_source,
    create_video_source,
)
from kagami_studio.obs.streaming import (
    RecordingSettings,
    StreamingPlatform,
    StreamSettings,
)

__all__ = [
    "BridgeMode",
    "CompositeLayer",
    "FilterType",
    "LayerBlendMode",
    # Bridge
    "OBSBridge",
    # Compositing
    "OBSCompositor",
    "OBSConfig",
    "OBSConnectionState",
    # Client
    "OBSController",
    # Filters
    "OBSFilter",
    # Scenes
    "OBSScene",
    "OBSSceneItem",
    # Sources
    "OBSSource",
    "OBSSourceSettings",
    "OBSSourceType",
    "OBSTransition",
    "RecordingSettings",
    # Streaming
    "StreamSettings",
    "StreamingPlatform",
    "TransitionType",
    "connect_obs",
    "create_blur_filter",
    "create_browser_source",
    "create_chromakey_filter",
    "create_color_correction_filter",
    "create_corner_cam_layout",
    "create_image_source",
    "create_lut_filter",
    "create_media_source",
    "create_pip_layout",
    "create_side_by_side_layout",
    "create_video_source",
]
