"""Virtual HAL Configuration.

Centralized configuration for virtual adapters with environment variable support.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VirtualHALConfig:
    """Configuration for virtual HAL adapters.

    Attributes:
        record_mode: Save all sensor/actuator data to files
        output_dir: Directory for recorded data
        deterministic: Use deterministic data generation (reproducible)
        seed: Random seed for deterministic mode
        frame_width: Virtual camera width
        frame_height: Virtual camera height
        frame_fps: Virtual camera frame rate
        audio_sample_rate: Virtual audio sample rate
        audio_channels: Virtual audio channels
    """

    record_mode: bool
    output_dir: Path
    deterministic: bool
    seed: int
    frame_width: int
    frame_height: int
    frame_fps: int
    audio_sample_rate: int
    audio_channels: int

    # Internal state for deterministic time (not user-configurable)
    _virtual_time: float = field(default=0.0, init=False, repr=False)
    _time_increment: float = field(default=0.001, init=False, repr=False)  # 1ms per call

    def get_time(self) -> float:
        """Get time (mocked in deterministic mode).

        Returns:
            Current time in seconds (virtual or real)
        """
        if self.deterministic:
            t = self._virtual_time
            self._virtual_time += self._time_increment
            return t
        return time.time()

    @classmethod
    def from_env(cls) -> VirtualHALConfig:
        """Load configuration from environment variables."""
        record_mode = os.getenv("KAGAMI_VIRTUAL_RECORD_MODE", "0") == "1"
        output_dir = Path(os.getenv("KAGAMI_VIRTUAL_OUTPUT_DIR", "./virtual_hal_output"))
        deterministic = os.getenv("KAGAMI_VIRTUAL_DETERMINISTIC", "0") == "1"
        seed = int(os.getenv("KAGAMI_VIRTUAL_SEED", "42"))

        # Camera config
        frame_width = int(os.getenv("KAGAMI_VIRTUAL_CAMERA_WIDTH", "640"))
        frame_height = int(os.getenv("KAGAMI_VIRTUAL_CAMERA_HEIGHT", "480"))
        frame_fps = int(os.getenv("KAGAMI_VIRTUAL_CAMERA_FPS", "30"))

        # Audio config
        audio_sample_rate = int(os.getenv("KAGAMI_VIRTUAL_AUDIO_RATE", "44100"))
        audio_channels = int(os.getenv("KAGAMI_VIRTUAL_AUDIO_CHANNELS", "2"))

        config = cls(
            record_mode=record_mode,
            output_dir=output_dir,
            deterministic=deterministic,
            seed=seed,
            frame_width=frame_width,
            frame_height=frame_height,
            frame_fps=frame_fps,
            audio_sample_rate=audio_sample_rate,
            audio_channels=audio_channels,
        )

        if record_mode:
            logger.info(f"Virtual HAL recording mode enabled: {output_dir}")
            # Create output directories
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "frames").mkdir(exist_ok=True)
            (output_dir / "audio").mkdir(exist_ok=True)
            (output_dir / "sensors").mkdir(exist_ok=True)

        if deterministic:
            logger.info(f"Virtual HAL deterministic mode enabled (seed={seed})")

        return config


# Global config singleton
_config: VirtualHALConfig | None = None


def get_virtual_config() -> VirtualHALConfig:
    """Get or create virtual HAL configuration."""
    global _config
    if _config is None:
        _config = VirtualHALConfig.from_env()
    return _config


def reset_virtual_config() -> None:
    """Reset virtual HAL configuration (for testing)."""
    global _config
    _config = None
