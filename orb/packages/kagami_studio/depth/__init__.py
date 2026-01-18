"""🎥 Kagami Studio Depth — 3D Camera Motion from 2D Media.

Extract 3D information and create camera motion from photos and video.

## What I Know From A Photo

From a single image, I can extract:
- **Depth map**: Relative depth at every pixel (Depth Anything V2)
- **Metric depth**: Actual distances in meters (indoor/outdoor models)
- **Subject segmentation**: People, objects, background layers
- **Scene geometry**: Planes, surfaces, layout estimation
- **Lighting**: Direction, intensity, color temperature
- **3D mesh**: Point cloud or mesh from depth + RGB

## What I Know From Video

From video, I gain additional knowledge:
- **Temporally consistent depth**: Smooth depth across frames (DepthCrafter)
- **Camera trajectory**: Original camera path estimation
- **Structure from Motion**: Multi-view 3D reconstruction
- **Dense point cloud**: More accurate than single-frame
- **Scene flow**: How 3D points move over time
- **Dynamic vs static**: What's moving vs environment

## 3D Camera Motion

With depth, I can simulate camera motion:
- **Dolly**: Move camera forward/backward through scene
- **Truck**: Move camera left/right
- **Pedestal**: Move camera up/down
- **Pan**: Rotate camera horizontally
- **Tilt**: Rotate camera vertically
- **Roll**: Rotate camera around lens axis
- **Zoom**: Focal length change (with parallax!)
- **Ken Burns 3D**: Classic photo animation with real depth

Quick Start - Photo to 3D Motion:
    from kagami_studio.depth import (
        estimate_depth,
        create_camera_motion,
        CameraPath,
    )

    # Get depth from photo
    depth = await estimate_depth("photo.jpg")

    # Create 3D dolly zoom
    result = await create_camera_motion(
        image="photo.jpg",
        depth=depth,
        camera_path=CameraPath.DOLLY_IN,
        duration=3.0,
        output="animated.mp4",
    )

Quick Start - Video Depth:
    from kagami_studio.depth import estimate_video_depth

    # Temporally consistent depth for entire video
    depth_video = await estimate_video_depth(
        "interview.mp4",
        model="depthcrafter",  # or "depth_anything_v2"
    )

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │                   Input Media                           │
    │            (Photo or Video)                             │
    └─────────────────────┬───────────────────────────────────┘
                          │
    ┌─────────────────────▼───────────────────────────────────┐
    │              Depth Estimation                           │
    │  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  │
    │  │ Depth        │  │ DepthCrafter│  │ MiDaS 3.1    │  │
    │  │ Anything V2  │  │ (video)     │  │ (fallback)   │  │
    │  └──────────────┘  └─────────────┘  └──────────────┘  │
    └─────────────────────┬───────────────────────────────────┘
                          │
    ┌─────────────────────▼───────────────────────────────────┐
    │              Scene Understanding                        │
    │  • Layer segmentation (fg/mg/bg)                       │
    │  • Edge detection & inpainting                         │
    │  • Plane detection                                     │
    │  • Occlusion handling                                  │
    └─────────────────────┬───────────────────────────────────┘
                          │
    ┌─────────────────────▼───────────────────────────────────┐
    │              3D Rendering                               │
    │  • Depth-based mesh generation                         │
    │  • Camera motion simulation                            │
    │  • Parallax compositing                                │
    │  • Disocclusion inpainting                            │
    └─────────────────────┬───────────────────────────────────┘
                          │
    ┌─────────────────────▼───────────────────────────────────┐
    │              Output                                     │
    │  • 3D motion video                                     │
    │  • Depth map visualization                             │
    │  • Point cloud export                                  │
    └─────────────────────────────────────────────────────────┘

Version: 1.0.0
"""

from kagami_studio.depth.camera import (
    CameraConfig,
    CameraMotion,
    CameraPath,
    create_camera_motion,
    create_dolly_zoom,
    create_ken_burns_3d,
    create_parallax_pan,
)
from kagami_studio.depth.estimator import (
    DepthEstimator,
    DepthModel,
    DepthResult,
    estimate_depth,
    estimate_video_depth,
)
from kagami_studio.depth.renderer import (
    DepthRenderer,
    RenderConfig,
    render_3d_motion,
)
from kagami_studio.depth.scene import (
    DepthLayer,
    LayerType,
    SceneGeometry,
    analyze_scene,
    segment_by_depth,
)

__all__ = [
    "CameraConfig",
    # Camera
    "CameraMotion",
    "CameraPath",
    # Estimation
    "DepthEstimator",
    "DepthLayer",
    "DepthModel",
    # Rendering
    "DepthRenderer",
    "DepthResult",
    "LayerType",
    "RenderConfig",
    # Scene
    "SceneGeometry",
    "analyze_scene",
    "create_camera_motion",
    "create_dolly_zoom",
    "create_ken_burns_3d",
    "create_parallax_pan",
    "estimate_depth",
    "estimate_video_depth",
    "render_3d_motion",
    "segment_by_depth",
]
