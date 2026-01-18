"""Visual Perception Pipeline — Camera → VisionSystem → World Model.

This module provides the complete visual perception pipeline:

    Camera Snapshot → VisionSystem → SceneGraph → Perception Vector → World Model

Components:
1. CameraSnapshotPoller: Periodic camera snapshot acquisition
2. VisualPerceptionEncoder: VisionSystem → perception vector encoding
3. SceneGraphPersistence: Store scene graphs for memory

Architecture:
    UniFi Camera (5x AI Pro)
            │
            │ get_camera_snapshot(name)
            ▼
    JPEG/PNG bytes
            │
            │ VisionSystem.perceive(image)
            ▼
    VisionPerception
    ├── features: DINOv2 [1536D]
    ├── objects: DetectedObject[]
    ├── scene_description: str
    └── relationships: SpatialRelation[]
            │
            │ encode_vision_perception()
            ▼
    Perception Vector [512D]
            │
            │ SensoryToWorldModel
            ▼
    E8 code [8] + S7 phase [7]
            │
            │ OrganismRSSM.step_all()
            ▼
    World Model State

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

    from kagami.core.embodiment.vision_system import VisionSystem

logger = logging.getLogger(__name__)


@dataclass
class CameraState:
    """State of a single camera."""

    camera_id: str
    name: str
    last_snapshot_time: float = 0.0
    last_perception: Any = None  # VisionPerception
    motion_detected: bool = False
    person_detected: bool = False
    features: np.ndarray | None = None  # DINOv2 features


@dataclass
class VisualPerceptionState:
    """Aggregate visual perception state."""

    cameras: dict[str, CameraState] = field(default_factory=dict)
    last_poll_time: float = 0.0
    perception_vector: np.ndarray | None = None  # Combined [512D]
    active_objects: list[dict] = field(default_factory=list)  # Detected objects
    scene_descriptions: dict[str, str] = field(default_factory=dict)  # Camera → description


class VisualPerceptionPipeline:
    """Complete visual perception pipeline from cameras to world model.

    This pipeline:
    1. Polls camera snapshots periodically
    2. Runs VisionSystem on each snapshot
    3. Encodes results to perception vector
    4. Emits to UnifiedSensory for world model integration

    Args:
        smart_home: SmartHomeController for camera access
        vision_system: VisionSystem instance (optional, created if None)
        poll_interval_s: Seconds between snapshot polls (default: 30)
        max_cameras_per_poll: Max cameras to process per poll cycle
    """

    def __init__(
        self,
        smart_home: SmartHomeController | None = None,
        vision_system: VisionSystem | None = None,
        poll_interval_s: float = 30.0,
        max_cameras_per_poll: int = 2,
    ):
        self._smart_home = smart_home
        self._vision_system = vision_system
        self._poll_interval_s = poll_interval_s
        self._max_cameras_per_poll = max_cameras_per_poll

        # State
        self._state = VisualPerceptionState()
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._camera_index = 0  # Round-robin camera selection

        # Camera list (discovered at init)
        self._camera_names: list[str] = []

        logger.info(
            f"VisualPerceptionPipeline: interval={poll_interval_s}s, "
            f"max_per_poll={max_cameras_per_poll}"
        )

    async def initialize(self) -> None:
        """Initialize the pipeline."""
        # Lazy load SmartHome
        if self._smart_home is None:
            try:
                from kagami_smarthome import get_smart_home

                self._smart_home = await get_smart_home()
            except Exception as e:
                logger.warning(f"SmartHome not available: {e}")

        # Lazy load VisionSystem
        if self._vision_system is None:
            try:
                from kagami.core.embodiment.vision_system import VisionSystem

                self._vision_system = VisionSystem()
            except Exception as e:
                logger.warning(f"VisionSystem not available: {e}")

        # Discover cameras
        await self._discover_cameras()

        logger.info(f"✅ VisualPerceptionPipeline initialized: {len(self._camera_names)} cameras")

    async def _discover_cameras(self) -> None:
        """Discover available cameras from UniFi."""
        if self._smart_home is None:
            return

        try:
            unifi = getattr(self._smart_home, "_unifi", None)
            if unifi and hasattr(unifi, "get_cameras"):
                cameras = unifi.get_cameras()
                self._camera_names = [
                    cam.get("name", cam_id)
                    for cam_id, cam in cameras.items()
                    if cam.get("is_connected", False)
                ]

                # Initialize camera states
                for name in self._camera_names:
                    self._state.cameras[name] = CameraState(
                        camera_id=name,
                        name=name,
                    )

                logger.info(f"Discovered {len(self._camera_names)} cameras: {self._camera_names}")
        except Exception as e:
            logger.warning(f"Camera discovery failed: {e}")

    async def start(self) -> None:
        """Start the visual perception polling loop."""
        if self._running:
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("🎥 VisualPerceptionPipeline started")

    async def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("VisualPerceptionPipeline stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._poll_cameras()
                await asyncio.sleep(self._poll_interval_s)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Visual poll error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on error

    async def _poll_cameras(self) -> None:
        """Poll subset of cameras and process with vision."""
        if not self._camera_names:
            return

        # Select cameras to poll (round-robin)
        cameras_to_poll = []
        for _ in range(min(self._max_cameras_per_poll, len(self._camera_names))):
            cameras_to_poll.append(self._camera_names[self._camera_index])
            self._camera_index = (self._camera_index + 1) % len(self._camera_names)

        # Process each camera
        for camera_name in cameras_to_poll:
            try:
                await self._process_camera(camera_name)
            except Exception as e:
                logger.debug(f"Camera {camera_name} processing failed: {e}")

        # Update aggregate perception
        await self._update_aggregate_perception()

        self._state.last_poll_time = time.time()

    async def _process_camera(self, camera_name: str) -> None:
        """Process a single camera snapshot."""
        if self._smart_home is None or self._vision_system is None:
            return

        # Get snapshot
        try:
            snapshot = await self._get_camera_snapshot(camera_name)
            if snapshot is None:
                return
        except Exception as e:
            logger.debug(f"Snapshot failed for {camera_name}: {e}")
            return

        # Run vision perception
        try:
            perception = await self._vision_system.perceive(snapshot)

            # Update camera state
            cam_state = self._state.cameras.get(camera_name)
            if cam_state:
                cam_state.last_snapshot_time = time.time()
                cam_state.last_perception = perception
                cam_state.person_detected = any(
                    obj.label.lower() in ("person", "human", "man", "woman")
                    for obj in perception.objects
                )
                cam_state.motion_detected = len(perception.objects) > 0

                # Store features if available
                if perception.features is not None:
                    if hasattr(perception.features, "numpy"):
                        cam_state.features = perception.features.numpy()
                    else:
                        cam_state.features = np.array(perception.features)

            # Store scene description
            self._state.scene_descriptions[camera_name] = perception.scene_description

            logger.debug(
                f"📸 {camera_name}: {len(perception.objects)} objects, "
                f"person={cam_state.person_detected if cam_state else False}"
            )

        except Exception as e:
            logger.warning(f"Vision processing failed for {camera_name}: {e}")

    async def _get_camera_snapshot(self, camera_name: str) -> bytes | None:
        """Get camera snapshot bytes."""
        if self._smart_home is None:
            return None

        try:
            # Use SmartHome's camera snapshot method
            unifi = getattr(self._smart_home, "_unifi", None)
            if unifi and hasattr(unifi, "get_camera_snapshot"):
                return await unifi.get_camera_snapshot(camera_name)
        except Exception as e:
            logger.debug(f"Snapshot acquisition failed: {e}")

        return None

    async def _update_aggregate_perception(self) -> None:
        """Update aggregate perception vector from all cameras."""
        # Collect all features
        all_features = []
        all_objects = []

        for cam_state in self._state.cameras.values():
            if cam_state.features is not None:
                all_features.append(cam_state.features)

            if cam_state.last_perception:
                for obj in cam_state.last_perception.objects:
                    all_objects.append(
                        {
                            "camera": cam_state.name,
                            "label": obj.label,
                            "confidence": obj.confidence,
                            "bbox": obj.bounding_box,
                        }
                    )

        self._state.active_objects = all_objects

        # Combine features (mean pool)
        if all_features:
            combined = np.mean(all_features, axis=0)
            # Project to 512D perception space
            self._state.perception_vector = self._project_to_perception(combined)

        # Emit to UnifiedSensory if we have perception
        if self._state.perception_vector is not None:
            await self._emit_visual_perception()

    def _project_to_perception(self, features: np.ndarray) -> np.ndarray:
        """Project vision features to 512D perception space.

        DINOv2 features are 1536D, we project to 512D.
        """
        if len(features) == 512:
            return features

        # Simple projection: take first 512 dims or pad
        if len(features) >= 512:
            return features[:512]
        else:
            padded = np.zeros(512)
            padded[: len(features)] = features
            return padded

    async def _emit_visual_perception(self) -> None:
        """Emit visual perception to UnifiedSensory."""
        try:
            from kagami.core.integrations import SenseType, get_unified_sensory

            sensory = get_unified_sensory()

            # Build data dict
            data = {
                "perception_vector": self._state.perception_vector.tolist()
                if self._state.perception_vector is not None
                else None,
                "active_objects": self._state.active_objects,
                "camera_count": len(self._camera_names),
                "cameras_with_people": sum(
                    1 for c in self._state.cameras.values() if c.person_detected
                ),
                "scene_descriptions": self._state.scene_descriptions,
                "timestamp": time.time(),
            }

            # Emit as CAMERAS sense type
            await sensory._emit_change(SenseType.CAMERAS, data, data)

        except Exception as e:
            logger.debug(f"Visual perception emit failed: {e}")

    def get_state(self) -> VisualPerceptionState:
        """Get current visual perception state."""
        return self._state

    def get_perception_vector(self) -> np.ndarray | None:
        """Get current 512D perception vector."""
        return self._state.perception_vector

    def get_active_objects(self) -> list[dict]:
        """Get currently detected objects across all cameras."""
        return self._state.active_objects


# =============================================================================
# Global Instance
# =============================================================================

_pipeline: VisualPerceptionPipeline | None = None


def get_visual_perception_pipeline() -> VisualPerceptionPipeline:
    """Get global VisualPerceptionPipeline instance."""
    global _pipeline

    if _pipeline is None:
        _pipeline = VisualPerceptionPipeline()

    return _pipeline


async def initialize_visual_perception(
    smart_home: SmartHomeController | None = None,
    poll_interval_s: float = 30.0,
    auto_start: bool = True,
) -> VisualPerceptionPipeline:
    """Initialize and optionally start the visual perception pipeline.

    Args:
        smart_home: SmartHomeController instance
        poll_interval_s: Polling interval
        auto_start: Whether to start polling automatically

    Returns:
        Initialized VisualPerceptionPipeline
    """
    global _pipeline

    _pipeline = VisualPerceptionPipeline(
        smart_home=smart_home,
        poll_interval_s=poll_interval_s,
    )
    await _pipeline.initialize()

    if auto_start:
        await _pipeline.start()

    logger.info("✅ VisualPerceptionPipeline initialized and started")
    return _pipeline


def reset_visual_perception() -> None:
    """Reset global instance (for testing)."""
    global _pipeline
    _pipeline = None


__all__ = [
    "CameraState",
    "VisualPerceptionPipeline",
    "VisualPerceptionState",
    "get_visual_perception_pipeline",
    "initialize_visual_perception",
    "reset_visual_perception",
]
