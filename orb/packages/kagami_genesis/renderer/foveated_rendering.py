"""Foveated Rendering Module - Gaze-aware adaptive quality rendering.

Responsibilities:
- Cursor/gaze tracking for foveation center
- FPS overlay and performance monitoring
- Foveated rendering with variable SPP
- Multi-camera foveated rendering
- Motion-aware temporal reprojection
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from .render_config import FoveationConfig, FrameStats

logger = logging.getLogger(__name__)


class CursorTracker:
    """Simple cursor tracking for foveation fallback."""

    def __init__(self) -> None:
        self.last_x = 0.0
        self.last_y = 0.0

    def update(self) -> tuple[float, float]:
        """Update cursor position and return normalized coordinates."""
        try:
            # This would integrate with actual cursor tracking
            # For now, return last known position
            return self.last_x, self.last_y
        except Exception as e:
            logger.warning(f"Cursor tracking failed: {e}")
            return 0.5, 0.5  # Center fallback


class FPSOverlay:
    """FPS and performance overlay renderer."""

    def __init__(self) -> None:
        self._font = self._load_font()
        self.frame_times: list[float] = []
        self.max_history = 60  # Keep 60 frames of history

    def _load_font(self) -> Any:
        """Load font for text rendering."""
        try:
            # This would load an actual font
            # For now, return a placeholder
            return None
        except Exception as e:
            logger.warning(f"Could not load font: {e}")
            return None

    def render_overlay(self, frame: np.ndarray, stats: FrameStats) -> np.ndarray:
        """Render performance overlay on frame."""
        try:
            # Add frame time to history
            self.frame_times.append(stats.render_time_ms)
            if len(self.frame_times) > self.max_history:
                self.frame_times.pop(0)

            # Calculate statistics
            avg_frame_time = np.mean(self.frame_times)
            min_frame_time = np.min(self.frame_times)
            max_frame_time = np.max(self.frame_times)
            fps = 1000.0 / avg_frame_time if avg_frame_time > 0 else 0

            # Create overlay text
            overlay_lines = [
                f"FPS: {fps:.1f} ({avg_frame_time:.1f}ms avg)",
                f"Range: {min_frame_time:.1f}-{max_frame_time:.1f}ms",
                f"Frame: {stats.frame_number}",
                f"Rays: {stats.total_rays:,}",
                f"SPP: {stats.samples_per_pixel}",
                f"Depth: {stats.max_depth}",
                f"Memory: {stats.memory_usage_mb:.1f}MB",
            ]

            # Render text overlay (simplified)
            # In practice, this would use proper text rendering
            result_frame = frame.copy()

            # Add simple text rendering placeholder
            # This would be replaced with actual text rendering code
            overlay_height = len(overlay_lines) * 20  # 20 pixels per line
            overlay_width = 300
            overlay_y = 10
            overlay_x = frame.shape[1] - overlay_width - 10

            # Create semi-transparent background
            if (
                overlay_y + overlay_height < frame.shape[0]
                and overlay_x + overlay_width < frame.shape[1]
            ):
                # Dark background
                result_frame[
                    overlay_y : overlay_y + overlay_height,
                    overlay_x : overlay_x + overlay_width,
                ] *= 0.3

                # Add text representation (simplified - would use actual text rendering)
                # For now, just brighten areas where text would be
                for i, _line in enumerate(overlay_lines):
                    line_y = overlay_y + i * 20 + 5
                    line_x = overlay_x + 5
                    if line_y + 15 < frame.shape[0] and line_x + 200 < frame.shape[1]:
                        result_frame[line_y : line_y + 15, line_x : line_x + 200] += 0.1

            return result_frame

        except Exception as e:
            logger.error(f"Overlay rendering failed: {e}")
            return frame


class FoveatedRenderer:
    """Single-camera foveated renderer with gaze tracking."""

    def __init__(self, width: int, height: int, config: FoveationConfig) -> None:
        self.width = width
        self.height = height
        self.config = config
        self.cursor_tracker = CursorTracker()

        # Gaze tracking state
        self.gaze_x = 0.5  # Normalized coordinates
        self.gaze_y = 0.5

    def update_gaze(self, gaze_x: float, gaze_y: float) -> None:
        """Update gaze position (normalized coordinates 0-1)."""
        self.gaze_x = np.clip(gaze_x, 0.0, 1.0)
        self.gaze_y = np.clip(gaze_y, 0.0, 1.0)

    def update_from_cursor(self) -> tuple[float, float]:
        """Update gaze from cursor position."""
        if self.config.fallback_to_cursor:
            self.gaze_x, self.gaze_y = self.cursor_tracker.update()
        return self.gaze_x, self.gaze_y

    def render_foveated(self, scene: Any, camera: Any) -> np.ndarray:
        """Render frame with foveated quality."""
        # This would integrate with the actual ray tracer
        # For now, return a placeholder that demonstrates the concept

        try:
            # Calculate foveation regions
            center_x = int(self.gaze_x * self.width)
            center_y = int(self.gaze_y * self.height)

            center_radius_pixels = int(self.config.center_radius * self.width)
            mid_radius_pixels = int(self.config.mid_radius * self.width)

            # Create quality map
            quality_map = np.zeros((self.height, self.width), dtype=np.float32)

            # Generate coordinate grids
            y_coords, x_coords = np.ogrid[: self.height, : self.width]
            distances = np.sqrt((x_coords - center_x) ** 2 + (y_coords - center_y) ** 2)

            # Apply foveation multipliers
            center_mask = distances <= center_radius_pixels
            mid_mask = (distances > center_radius_pixels) & (distances <= mid_radius_pixels)
            peripheral_mask = distances > mid_radius_pixels

            quality_map[center_mask] = self.config.center_spp_multiplier
            quality_map[mid_mask] = self.config.mid_spp_multiplier
            quality_map[peripheral_mask] = self.config.peripheral_spp_multiplier

            # Apply transition smoothing
            if self.config.transition_width > 0:
                # Smooth transitions between regions
                transition_pixels = int(self.config.transition_width * self.width)

                # Smooth center-to-mid transition
                center_transition_mask = (distances > center_radius_pixels - transition_pixels) & (
                    distances <= center_radius_pixels + transition_pixels
                )
                if np.any(center_transition_mask):
                    transition_factor = (
                        distances[center_transition_mask] - center_radius_pixels + transition_pixels
                    ) / (2 * transition_pixels)
                    quality_map[center_transition_mask] = (
                        self.config.center_spp_multiplier * (1 - transition_factor)
                        + self.config.mid_spp_multiplier * transition_factor
                    )

                # Smooth mid-to-peripheral transition
                mid_transition_mask = (distances > mid_radius_pixels - transition_pixels) & (
                    distances <= mid_radius_pixels + transition_pixels
                )
                if np.any(mid_transition_mask):
                    transition_factor = (
                        distances[mid_transition_mask] - mid_radius_pixels + transition_pixels
                    ) / (2 * transition_pixels)
                    quality_map[mid_transition_mask] = (
                        self.config.mid_spp_multiplier * (1 - transition_factor)
                        + self.config.peripheral_spp_multiplier * transition_factor
                    )

            # This would be passed to the actual ray tracer
            # For now, create a simple visualization of the foveation
            result = np.zeros((self.height, self.width, 3), dtype=np.float32)

            # Visualize foveation regions (for debugging)
            result[center_mask] = [1.0, 0.8, 0.8]  # Red tint for center
            result[mid_mask] = [0.8, 1.0, 0.8]  # Green tint for mid
            result[peripheral_mask] = [0.8, 0.8, 1.0]  # Blue tint for peripheral

            # Apply quality-based brightness
            for channel in range(3):
                result[:, :, channel] *= quality_map

            return result

        except Exception as e:
            logger.error(f"Foveated rendering failed: {e}")
            # Return fallback image
            return np.zeros((self.height, self.width, 3), dtype=np.float32)


class FoveatedMultiCameraRenderer:
    """Multi-camera foveated renderer for stereo/VR."""

    def __init__(
        self,
        width: int,
        height: int,
        config: FoveationConfig,
        num_cameras: int = 2,
    ) -> None:
        self.width = width
        self.height = height
        self.config = config
        self.num_cameras = num_cameras

        # Create individual foveated renderers for each camera
        self.renderers = [FoveatedRenderer(width, height, config) for _ in range(num_cameras)]

        # Blend masks for multi-camera compositing
        self._blend_masks = self._compute_blend_masks()

    def initialize(self, scene: Any) -> None:
        """Initialize the renderer with scene data."""
        self.scene = scene

    def update_camera_pose(
        self,
        camera_id: int,
        position: tuple[float, float, float],
        rotation: tuple[float, float, float, float],
    ) -> None:
        """Update camera pose for multi-camera rendering."""
        # This would update the camera parameters
        # For now, just log the update
        logger.debug(f"Camera {camera_id} pose updated")

    def update_gaze(self, gaze_x: float, gaze_y: float) -> None:
        """Update gaze position for all cameras."""
        for renderer in self.renderers:
            renderer.update_gaze(gaze_x, gaze_y)

    def update_from_cursor(self) -> tuple[float, float]:
        """Update gaze from cursor for all cameras."""
        gaze_pos = None
        for renderer in self.renderers:
            gaze_pos = renderer.update_from_cursor()
        return gaze_pos or (0.5, 0.5)

    def _compute_blend_mask(
        self,
        camera_id: int,
        total_cameras: int,
    ) -> np.ndarray:
        """Compute blending mask for camera overlap regions."""
        mask = np.ones((self.height, self.width), dtype=np.float32)

        if total_cameras == 2:
            # For stereo rendering, simple left/right split
            if camera_id == 0:  # Left eye
                mask[:, self.width // 2 :] *= 0.5  # Reduce right side
            else:  # Right eye
                mask[:, : self.width // 2] *= 0.5  # Reduce left side

        elif total_cameras > 2:
            # For multi-camera setups, create circular blending
            center_x = self.width // 2
            center_y = self.height // 2
            y_coords, x_coords = np.ogrid[: self.height, : self.width]
            np.sqrt((x_coords - center_x) ** 2 + (y_coords - center_y) ** 2)

            # Create radial falloff for each camera
            angle_per_camera = 2 * np.pi / total_cameras
            camera_angle = camera_id * angle_per_camera

            # Compute angular difference from camera direction
            pixel_angles = np.arctan2(y_coords - center_y, x_coords - center_x)
            angle_diff = np.abs(pixel_angles - camera_angle)
            angle_diff = np.minimum(angle_diff, 2 * np.pi - angle_diff)

            # Create smooth falloff based on angle
            falloff = np.cos(angle_diff * total_cameras / 2)
            mask *= np.maximum(0, falloff)

        return mask

    def _compute_blend_masks(self) -> list[np.ndarray]:
        """Pre-compute all blend masks."""
        return [self._compute_blend_mask(i, self.num_cameras) for i in range(self.num_cameras)]

    def render_foveated(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Render foveated frames for all cameras."""
        try:
            results = []

            for _i, renderer in enumerate(self.renderers):
                # Render individual camera
                camera_result = renderer.render_foveated(self.scene, None)
                results.append(camera_result)

            # For stereo, return left and right
            if self.num_cameras == 2:
                return results[0], results[1]
            # For multi-camera, return composite
            return self.composite_foveated(results), None

        except Exception as e:
            logger.error(f"Multi-camera foveated rendering failed: {e}")
            return None, None

    def composite_foveated(
        self,
        camera_frames: list[np.ndarray],
    ) -> np.ndarray:
        """Composite multiple camera frames with blending."""
        if not camera_frames:
            return np.zeros((self.height, self.width, 3), dtype=np.float32)

        try:
            # Initialize composite with first frame
            composite = np.zeros_like(camera_frames[0])

            # Blend all camera frames
            total_weight = np.zeros((self.height, self.width), dtype=np.float32)

            for i, frame in enumerate(camera_frames):
                if i < len(self._blend_masks):
                    mask = self._blend_masks[i]
                    # Apply mask to each color channel
                    for channel in range(3):
                        composite[:, :, channel] += frame[:, :, channel] * mask
                    total_weight += mask

            # Normalize by total weight to avoid over-brightening
            total_weight = np.maximum(total_weight, 1e-6)  # Avoid division by zero
            for channel in range(3):
                composite[:, :, channel] /= total_weight

            return composite

        except Exception as e:
            logger.error(f"Frame compositing failed: {e}")
            return camera_frames[0] if camera_frames else np.zeros((self.height, self.width, 3))

    def render_and_composite(self) -> np.ndarray | None:
        """Render all cameras and return composited result."""
        left, right = self.render_foveated()

        if left is None:
            return None

        if right is None:
            return left

        # Simple stereo compositing (for debugging)
        # In VR, you'd send left/right to separate eye displays
        composite = np.zeros_like(left)
        composite[:, : self.width // 2] = left[:, : self.width // 2]
        composite[:, self.width // 2 :] = right[:, self.width // 2 :]

        return composite


class MotionAwareReprojector:
    """Motion-aware temporal reprojection for improved performance."""

    def __init__(
        self,
        width: int,
        height: int,
        max_history: int = 8,
    ) -> None:
        self.width = width
        self.height = height
        self.max_history = max_history

        # History buffers
        self.frame_history: list[np.ndarray] = []
        self.depth_history: list[np.ndarray] = []
        self.motion_history: list[np.ndarray] = []

        # Camera state
        self.camera_matrices: list[np.ndarray] = []
        self.object_motions: dict[str, Any] = {}

        # Reprojection parameters
        self.max_reprojection_distance = 10.0  # pixels
        self.confidence_threshold = 0.8

    def _build_projection_matrix(self) -> np.ndarray:
        """Build camera projection matrix."""
        # Placeholder projection matrix
        fov = np.pi / 3  # 60 degrees
        aspect = self.width / self.height
        near = 0.1
        far = 1000.0

        f = 1.0 / np.tan(fov / 2)
        return np.array(
            [
                [f / aspect, 0, 0, 0],
                [0, f, 0, 0],
                [0, 0, -(far + near) / (far - near), -2 * far * near / (far - near)],
                [0, 0, -1, 0],
            ],
        )

    def _build_view_matrix(
        self,
        position: tuple[float, float, float],
        rotation: tuple[float, float, float, float],
    ) -> np.ndarray:
        """Build camera view matrix from position and rotation."""
        # Simplified view matrix construction
        # In practice, this would use proper quaternion-to-matrix conversion
        translation = np.array(
            [
                [1, 0, 0, -position[0]],
                [0, 1, 0, -position[1]],
                [0, 0, 1, -position[2]],
                [0, 0, 0, 1],
            ],
        )

        # Placeholder rotation matrix (would convert quaternion to matrix)
        rotation_matrix = np.eye(4)

        return rotation_matrix @ translation

    def _linearize_depth(self, depth_buffer: np.ndarray) -> np.ndarray:
        """Convert depth buffer to linear depth."""
        # Convert from normalized device coordinates to linear depth
        near = 0.1
        far = 1000.0
        return (2.0 * near) / (far + near - depth_buffer * (far - near))

    def _unproject_to_view_space(
        self,
        screen_coords: np.ndarray,
        depth: np.ndarray,
        inv_projection: np.ndarray,
    ) -> np.ndarray:
        """Unproject screen coordinates to view space."""
        # Convert screen coordinates to NDC
        ndc_x = (screen_coords[..., 0] / self.width) * 2.0 - 1.0
        ndc_y = (screen_coords[..., 1] / self.height) * 2.0 - 1.0
        ndc_z = depth * 2.0 - 1.0

        # Create homogeneous coordinates
        ndc_coords = np.stack([ndc_x, ndc_y, ndc_z, np.ones_like(ndc_x)], axis=-1)

        # Transform to view space
        view_coords = ndc_coords @ inv_projection.T

        # Perspective divide
        view_coords[..., :3] /= view_coords[..., 3:4]

        return view_coords[..., :3]

    def _transform_points(
        self,
        points: np.ndarray,
        from_view: np.ndarray,
        to_view: np.ndarray,
    ) -> np.ndarray:
        """Transform points from one view space to another."""
        # Convert to world space
        inv_from_view = np.linalg.inv(from_view)
        world_coords = points @ inv_from_view[:3, :3].T + inv_from_view[:3, 3]

        # Convert to target view space
        return world_coords @ to_view[:3, :3].T + to_view[:3, 3]

    def _project_to_screen(
        self,
        view_coords: np.ndarray,
        projection: np.ndarray,
    ) -> np.ndarray:
        """Project view space coordinates to screen space."""
        # Convert to homogeneous coordinates
        homo_coords = np.concatenate(
            [
                view_coords,
                np.ones((*view_coords.shape[:-1], 1)),
            ],
            axis=-1,
        )

        # Project to NDC
        ndc_coords = homo_coords @ projection.T

        # Perspective divide
        ndc_coords[..., :3] /= ndc_coords[..., 3:4]

        # Convert to screen coordinates
        screen_x = (ndc_coords[..., 0] + 1.0) * self.width / 2.0
        screen_y = (ndc_coords[..., 1] + 1.0) * self.height / 2.0

        return np.stack([screen_x, screen_y], axis=-1)

    def update_object_motion(
        self,
        object_id: str,
        position: tuple[float, float, float],
        rotation: tuple[float, float, float, float],
        velocity: tuple[float, float, float],
        angular_velocity: tuple[float, float, float],
    ) -> None:
        """Update object motion data for reprojection."""
        self.object_motions[object_id] = {
            "position": position,
            "rotation": rotation,
            "velocity": velocity,
            "angular_velocity": angular_velocity,
            "timestamp": time.time(),
        }

    def reproject_frame(
        self,
        current_frame: np.ndarray,
        current_depth: np.ndarray,
        camera_position: tuple[float, float, float],
        camera_rotation: tuple[float, float, float, float],
    ) -> tuple[np.ndarray, np.ndarray]:
        """Perform motion-aware temporal reprojection."""
        if not self.frame_history:
            # No history available, return current frame
            return current_frame, np.ones((self.height, self.width), dtype=np.float32)

        try:
            # Build current camera matrices
            current_view = self._build_view_matrix(camera_position, camera_rotation)
            current_projection = self._build_projection_matrix()
            current_inv_projection = np.linalg.inv(current_projection)

            # Get previous frame and matrices
            prev_frame = self.frame_history[-1]
            self.depth_history[-1]
            prev_view = self.camera_matrices[-1]

            # Create coordinate grids
            y_coords, x_coords = np.ogrid[: self.height, : self.width]
            screen_coords = np.stack(
                [
                    x_coords.astype(np.float32),
                    y_coords.astype(np.float32),
                ],
                axis=-1,
            )

            # Linearize depth
            linear_depth = self._linearize_depth(current_depth)

            # Unproject current pixels to view space
            view_coords = self._unproject_to_view_space(
                screen_coords,
                linear_depth,
                current_inv_projection,
            )

            # Transform to previous view space
            prev_view_coords = self._transform_points(view_coords, current_view, prev_view)

            # Project back to previous screen space
            prev_screen_coords = self._project_to_screen(prev_view_coords, current_projection)

            # Calculate reprojection validity
            # Check if reprojected coordinates are within screen bounds
            valid_x = (prev_screen_coords[..., 0] >= 0) & (prev_screen_coords[..., 0] < self.width)
            valid_y = (prev_screen_coords[..., 1] >= 0) & (prev_screen_coords[..., 1] < self.height)
            valid_mask = valid_x & valid_y

            # Check reprojection distance
            displacement = np.sqrt(np.sum((prev_screen_coords - screen_coords) ** 2, axis=-1))
            distance_valid = displacement < self.max_reprojection_distance
            valid_mask &= distance_valid

            # Create reprojected frame
            reprojected = np.zeros_like(current_frame)
            confidence = np.zeros((self.height, self.width), dtype=np.float32)

            # Sample from previous frame using reprojection
            _y_indices, _x_indices = np.ogrid[: self.height, : self.width]
            valid_pixels = valid_mask

            if np.any(valid_pixels):
                # Bilinear sampling from previous frame
                prev_x = prev_screen_coords[valid_pixels, 0]
                prev_y = prev_screen_coords[valid_pixels, 1]

                # Integer coordinates for sampling
                x0 = np.floor(prev_x).astype(int)
                y0 = np.floor(prev_y).astype(int)
                x1 = x0 + 1
                y1 = y0 + 1

                # Weights for bilinear interpolation
                wx = prev_x - x0
                wy = prev_y - y0

                # Bounds check
                valid_sample = (x0 >= 0) & (x1 < self.width) & (y0 >= 0) & (y1 < self.height)

                if np.any(valid_sample):
                    # Perform bilinear sampling
                    sample_indices = np.where(valid_pixels)[0][valid_sample]

                    for i, idx in enumerate(sample_indices):
                        y_idx, x_idx = np.unravel_index(idx, (self.height, self.width))

                        px0, py0 = x0[valid_sample][i], y0[valid_sample][i]
                        px1, py1 = x1[valid_sample][i], y1[valid_sample][i]
                        wx_val, wy_val = wx[valid_sample][i], wy[valid_sample][i]

                        # Bilinear interpolation
                        c00 = prev_frame[py0, px0]
                        c01 = prev_frame[py1, px0]
                        c10 = prev_frame[py0, px1]
                        c11 = prev_frame[py1, px1]

                        reprojected[y_idx, x_idx] = (
                            c00 * (1 - wx_val) * (1 - wy_val)
                            + c10 * wx_val * (1 - wy_val)
                            + c01 * (1 - wx_val) * wy_val
                            + c11 * wx_val * wy_val
                        )

                        # Set confidence based on displacement
                        disp = displacement[y_idx, x_idx]
                        confidence[y_idx, x_idx] = max(
                            0,
                            1.0 - disp / self.max_reprojection_distance,
                        )

            # Blend with current frame based on confidence
            final_confidence = confidence * (confidence > self.confidence_threshold)
            blended = reprojected * final_confidence[..., np.newaxis] + current_frame * (
                1 - final_confidence[..., np.newaxis]
            )

            return blended, final_confidence

        except Exception as e:
            logger.error(f"Temporal reprojection failed: {e}")
            return current_frame, np.ones((self.height, self.width), dtype=np.float32)

    def add_frame(
        self,
        frame: np.ndarray,
        depth: np.ndarray,
        camera_position: tuple[float, float, float],
        camera_rotation: tuple[float, float, float, float],
    ) -> None:
        """Add frame to history buffer."""
        # Add to history
        self.frame_history.append(frame.copy())
        self.depth_history.append(depth.copy())

        # Build and store camera matrix
        view_matrix = self._build_view_matrix(camera_position, camera_rotation)
        self.camera_matrices.append(view_matrix)

        # Maintain max history size
        if len(self.frame_history) > self.max_history:
            self.frame_history.pop(0)
            self.depth_history.pop(0)
            self.camera_matrices.pop(0)

    def get_motion_vectors(self) -> np.ndarray | None:
        """Get motion vectors for the current frame."""
        if len(self.motion_history) < 2:
            return None

        # Return difference between last two motion fields
        return self.motion_history[-1] - self.motion_history[-2]
