"""3D Motion Renderer — Generate video from depth + camera motion.

Renders depth-based parallax video using:
1. Depth-based displacement for parallax
2. Mesh-based rendering for large motions
3. Inpainting for disoccluded regions

Usage:
    from kagami_studio.depth import render_3d_motion

    video_path = await render_3d_motion(
        image=rgb_image,
        depth=depth_result,
        motion=camera_motion,
        duration=3.0,
        output="output.mp4",
    )
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from kagami_studio.depth.camera import CameraKeyframe, CameraMotion
    from kagami_studio.depth.estimator import DepthResult

logger = logging.getLogger(__name__)


@dataclass
class RenderConfig:
    """Rendering configuration."""

    # Output
    fps: int = 30
    codec: str = "libx264"
    crf: int = 18

    # Quality
    antialiasing: bool = True
    motion_blur: bool = False
    motion_blur_samples: int = 8

    # Depth handling
    depth_scale: float = 50.0  # Pixel displacement per depth unit
    edge_smoothing: int = 3  # Smooth depth edges

    # Inpainting
    inpaint_method: str = "telea"  # telea, ns, or none
    inpaint_radius: int = 5


class DepthRenderer:
    """Render 3D camera motion from depth maps."""

    def __init__(self, config: RenderConfig | None = None):
        """Initialize renderer.

        Args:
            config: Rendering configuration
        """
        self.config = config or RenderConfig()

    async def render(
        self,
        image: np.ndarray,
        depth: DepthResult,
        motion: CameraMotion,
        duration: float,
        output: Path,
    ) -> Path:
        """Render 3D motion video.

        Args:
            image: Source RGB image
            depth: Depth estimation result
            motion: Camera motion sequence
            duration: Video duration in seconds
            output: Output path

        Returns:
            Path to rendered video
        """
        h, w = image.shape[:2]
        depth_map = depth.normalize()

        # Smooth depth edges
        if self.config.edge_smoothing > 0:
            k = self.config.edge_smoothing * 2 + 1
            depth_map = cv2.GaussianBlur(depth_map, (k, k), 0)

        # Calculate frame count
        frame_count = int(duration * self.config.fps)

        # Render frames to temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            for i in range(frame_count):
                t = i / (frame_count - 1) if frame_count > 1 else 0

                # Get camera position at this time
                keyframe = motion.interpolate(t)

                # Render frame
                frame = self._render_frame(image, depth_map, keyframe, w, h)

                # Save frame
                frame_path = tmpdir / f"frame_{i:06d}.png"
                cv2.imwrite(str(frame_path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

            # Encode video with FFmpeg
            output.parent.mkdir(parents=True, exist_ok=True)

            cmd = [
                "ffmpeg",
                "-y",
                "-framerate",
                str(self.config.fps),
                "-i",
                str(tmpdir / "frame_%06d.png"),
                "-c:v",
                self.config.codec,
                "-crf",
                str(self.config.crf),
                "-pix_fmt",
                "yuv420p",
                str(output),
            ]

            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")

        return output

    def _render_frame(
        self,
        image: np.ndarray,
        depth_map: np.ndarray,
        keyframe: CameraKeyframe,
        w: int,
        h: int,
    ) -> np.ndarray:
        """Render single frame with camera transform.

        Uses depth-based forward warping with splatting.
        """
        # Calculate displacement map
        dx, dy = self._calculate_displacement(depth_map, keyframe, w, h)

        # Create output with forward warping
        output = self._forward_warp(image, dx, dy)

        # Apply zoom
        if keyframe.zoom != 1.0:
            output = self._apply_zoom(output, keyframe.zoom)

        # Inpaint holes
        if self.config.inpaint_method != "none":
            output = self._inpaint_holes(output)

        return output

    def _calculate_displacement(
        self,
        depth_map: np.ndarray,
        keyframe: CameraKeyframe,
        w: int,
        h: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Calculate per-pixel displacement from camera motion.

        Returns:
            (dx, dy) displacement maps
        """
        scale = self.config.depth_scale

        # Base displacement from camera position
        # Objects move opposite to camera, scaled by depth
        # Near objects (depth=1) move more, far objects (depth=0) move less

        # Truck/pedestal: lateral movement
        base_dx = -keyframe.x * w * 0.5
        base_dy = -keyframe.y * h * 0.5

        # Dolly: forward motion causes radial expansion/contraction
        # Near objects expand more than far objects
        if keyframe.z != 0:
            cy, cx = h / 2, w / 2
            y_coords = np.arange(h)[:, None] - cy
            x_coords = np.arange(w)[None, :] - cx

            # Radial distance from center
            radial = np.sqrt(x_coords**2 + y_coords**2)
            max_radial = np.sqrt(cx**2 + cy**2)

            # Displacement scales with depth and distance from center
            dolly_factor = keyframe.z * depth_map * (radial / max_radial)
            dolly_dx = x_coords * dolly_factor * 0.3
            dolly_dy = y_coords * dolly_factor * 0.3
        else:
            dolly_dx = np.zeros_like(depth_map)
            dolly_dy = np.zeros_like(depth_map)

        # Parallax: depth-weighted displacement
        parallax_factor = depth_map * scale

        dx = (base_dx * parallax_factor + dolly_dx).astype(np.float32)
        dy = (base_dy * parallax_factor + dolly_dy).astype(np.float32)

        # Pan/tilt: rotation-based displacement
        if keyframe.pan != 0:
            pan_rad = np.radians(keyframe.pan)
            dx += np.tan(pan_rad) * w * 0.5 * (1 - depth_map * 0.5)

        if keyframe.tilt != 0:
            tilt_rad = np.radians(keyframe.tilt)
            dy += np.tan(tilt_rad) * h * 0.5 * (1 - depth_map * 0.5)

        return dx, dy

    def _forward_warp(
        self,
        image: np.ndarray,
        dx: np.ndarray,
        dy: np.ndarray,
    ) -> np.ndarray:
        """Forward warp image using displacement.

        Simple approach: use inverse mapping with bilinear interpolation.
        """
        h, w = image.shape[:2]

        # Create coordinate grids
        x_coords = np.arange(w)[None, :].repeat(h, axis=0).astype(np.float32)
        y_coords = np.arange(h)[:, None].repeat(w, axis=1).astype(np.float32)

        # Calculate source coordinates (inverse of displacement)
        src_x = x_coords - dx
        src_y = y_coords - dy

        # Clamp to valid range
        src_x = np.clip(src_x, 0, w - 1)
        src_y = np.clip(src_y, 0, h - 1)

        # Remap using bilinear interpolation
        output = cv2.remap(
            image,
            src_x,
            src_y,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )

        return output

    def _apply_zoom(
        self,
        image: np.ndarray,
        zoom: float,
    ) -> np.ndarray:
        """Apply zoom transform."""
        h, w = image.shape[:2]

        # Calculate crop region
        new_w = int(w / zoom)
        new_h = int(h / zoom)

        x1 = (w - new_w) // 2
        y1 = (h - new_h) // 2

        # Crop and resize
        if zoom > 1:
            # Zoom in: crop then upscale
            cropped = image[y1 : y1 + new_h, x1 : x1 + new_w]
            return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            # Zoom out: downscale then pad
            scaled = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            output = np.zeros_like(image)
            output[y1 : y1 + new_h, x1 : x1 + new_w] = scaled
            return output

    def _inpaint_holes(self, image: np.ndarray) -> np.ndarray:
        """Inpaint black/missing regions."""
        # Detect holes (very dark pixels)
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        mask = (gray < 5).astype(np.uint8)

        # Dilate mask slightly
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)

        if np.sum(mask) == 0:
            return image

        # Inpaint
        if self.config.inpaint_method == "telea":
            return cv2.inpaint(image, mask, self.config.inpaint_radius, cv2.INPAINT_TELEA)
        elif self.config.inpaint_method == "ns":
            return cv2.inpaint(image, mask, self.config.inpaint_radius, cv2.INPAINT_NS)
        else:
            return image


async def render_3d_motion(
    image: np.ndarray,
    depth: DepthResult,
    motion: CameraMotion,
    duration: float,
    output: Path | str,
    config: RenderConfig | None = None,
) -> Path:
    """Convenience function to render 3D motion.

    Args:
        image: Source RGB image
        depth: Depth estimation result
        motion: Camera motion
        duration: Video duration
        output: Output path
        config: Render configuration

    Returns:
        Path to output video
    """
    renderer = DepthRenderer(config=config)
    return await renderer.render(
        image=image,
        depth=depth,
        motion=motion,
        duration=duration,
        output=Path(output),
    )
