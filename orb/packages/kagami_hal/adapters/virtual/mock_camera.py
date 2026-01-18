"""Virtual Camera Sensor.

Generates synthetic camera frames for testing without hardware.

Supports:
- Test patterns (solid colors, gradients, checkerboard)
- Noise generation (white, perlin)
- Deterministic frame generation
- Recording mode (save frames to disk)

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import random

import numpy as np

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.data_types import SensorReading, SensorType

from .config import get_virtual_config

logger = logging.getLogger(__name__)


class VirtualCamera(SensorAdapterBase):
    """Virtual camera sensor for testing.

    Generates synthetic frames with configurable patterns.
    """

    def __init__(self, width: int | None = None, height: int | None = None) -> None:
        """Initialize virtual camera.

        Args:
            width: Frame width (default from config)
            height: Frame height (default from config)
        """
        super().__init__()
        self._config = get_virtual_config()

        # Override dimensions if provided
        if width is not None:
            self._config.frame_width = width
        if height is not None:
            self._config.frame_height = height

        self._frame_count = 0
        self._start_time = self._config.get_time()

        # Seed RNG if deterministic mode
        if self._config.deterministic:
            random.seed(self._config.seed)
            np.random.seed(self._config.seed)

        # Camera is always available in virtual mode
        self._available_sensors.add(SensorType.ACCELEROMETER)  # Will use custom camera type

    async def initialize(self) -> bool:
        """Initialize camera."""
        self._running = True
        self._start_time = self._config.get_time()
        self._frame_count = 0
        logger.info(
            f"✅ Virtual camera initialized: "
            f"{self._config.frame_width}x{self._config.frame_height}@{self._config.frame_fps}fps"
        )
        return True

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read camera frame."""
        timestamp = int(self._config.get_time() * 1000)
        elapsed = self._config.get_time() - self._start_time

        # Generate frame based on mode
        frame = self._generate_frame(elapsed)

        # Record if enabled
        if self._config.record_mode:
            self._record_frame(frame)

        self._frame_count += 1

        return SensorReading(
            sensor=sensor,
            value=frame,
            timestamp_ms=timestamp,
            accuracy=1.0,
        )

    async def read_frame(self) -> np.ndarray:
        """Read camera frame directly.

        Returns:
            RGB frame as numpy array (H, W, 3)
        """
        elapsed = self._config.get_time() - self._start_time
        frame = self._generate_frame(elapsed)

        # Record if enabled
        if self._config.record_mode:
            self._record_frame(frame)

        self._frame_count += 1
        return frame

    async def shutdown(self) -> None:
        """Shutdown camera."""
        self._running = False
        logger.info(f"Virtual camera shutdown ({self._frame_count} frames)")

    def _generate_frame(self, elapsed: float) -> np.ndarray:
        """Generate synthetic frame.

        Args:
            elapsed: Time since initialization

        Returns:
            RGB frame as numpy array (H, W, 3)
        """
        h = self._config.frame_height
        w = self._config.frame_width

        # Choose pattern based on frame count
        pattern = self._frame_count % 5

        if pattern == 0:
            # Solid color cycling through RGB
            phase = (elapsed * 0.5) % 3
            if phase < 1:
                color = [int(255 * phase), 0, 0]
            elif phase < 2:
                color = [0, int(255 * (phase - 1)), 0]
            else:
                color = [0, 0, int(255 * (phase - 2))]
            frame = np.full((h, w, 3), color, dtype=np.uint8)

        elif pattern == 1:
            # Horizontal gradient
            gradient = np.linspace(0, 255, w, dtype=np.uint8)
            frame = np.tile(gradient, (h, 1))  # type: ignore[assignment]
            frame = np.stack([frame, frame, frame], axis=-1)  # type: ignore[assignment]

        elif pattern == 2:
            # Vertical gradient
            gradient = np.linspace(0, 255, h, dtype=np.uint8)
            frame = np.tile(gradient[:, np.newaxis], (1, w))  # type: ignore[assignment]
            frame = np.stack([frame, frame, frame], axis=-1)  # type: ignore[assignment]

        elif pattern == 3:
            # Checkerboard
            block_size = 32
            x = np.arange(w) // block_size
            y = np.arange(h) // block_size
            xx, yy = np.meshgrid(x, y)
            checkerboard = ((xx + yy) % 2) * 255
            frame = np.stack([checkerboard, checkerboard, checkerboard], axis=-1).astype(np.uint8)  # type: ignore[assignment]

        else:
            # Animated noise (white noise with time variation)
            if self._config.deterministic:
                # Use frame count as seed for deterministic noise
                rng = np.random.RandomState(self._config.seed + self._frame_count)
                noise = rng.randint(0, 256, (h, w, 3), dtype=np.uint8)
            else:
                noise = np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)
            frame = noise  # type: ignore[assignment]

        return frame

    def _record_frame(self, frame: np.ndarray) -> None:
        """Record frame to disk.

        Args:
            frame: Frame to save
        """
        try:
            output_path = self._config.output_dir / "frames" / f"frame_{self._frame_count:06d}.raw"
            frame.tofile(output_path)
        except Exception as e:
            logger.warning(f"Failed to record frame: {e}")

    def get_frame_count(self) -> int:
        """Get number of frames generated."""
        return self._frame_count

    def get_fps(self) -> float:
        """Get actual frame rate."""
        elapsed = self._config.get_time() - self._start_time
        if elapsed > 0:
            return self._frame_count / elapsed
        return 0.0
