"""Virtual HAL Platform for Headless Operation and Testing.

This package provides mock hardware implementations suitable for:
- CI/CD testing without physical devices
- Cloud/headless deployment
- Development on machines without cameras/mics
- Integration testing with reproducible data

Configuration:
    Environment variables control behavior:
    - KAGAMI_VIRTUAL_RECORD_MODE: 1 to enable recording to files
    - KAGAMI_VIRTUAL_OUTPUT_DIR: Directory for recorded data (default: ./virtual_hal_output)
    - KAGAMI_VIRTUAL_DETERMINISTIC: 1 for reproducible data generation
    - KAGAMI_VIRTUAL_SEED: Random seed for deterministic mode (default: 42)

Recording Mode:
    When enabled, all sensor readings and actuator outputs are saved:
    - Camera frames: virtual_hal_output/frames/frame_NNNN.raw
    - Microphone: virtual_hal_output/audio/recording_TIMESTAMP.raw
    - Speaker: virtual_hal_output/audio/playback_TIMESTAMP.raw
    - Sensor data: virtual_hal_output/sensors/SENSOR_TYPE.jsonl

Created: November 10, 2025
Enhanced: December 15, 2025 - Full virtual platform with recording
"""

from .audio import VirtualAudio
from .compute import (
    ComputeCapabilities,
    detect_compute_capabilities,
    get_optimal_worker_count,
    supports_mixed_precision,
)
from .config import VirtualHALConfig, get_virtual_config
from .display import VirtualDisplay
from .input import VirtualInput
from .mock_camera import VirtualCamera
from .mock_microphone import VirtualMicrophone
from .power import VirtualPower
from .sensors import VirtualSensors

__all__ = [
    # Compute capabilities
    "ComputeCapabilities",
    # Core adapters
    "VirtualAudio",
    # Mock devices
    "VirtualCamera",
    "VirtualDisplay",
    # Configuration
    "VirtualHALConfig",
    "VirtualInput",
    "VirtualMicrophone",
    "VirtualPower",
    "VirtualSensors",
    "detect_compute_capabilities",
    "get_optimal_worker_count",
    "get_virtual_config",
    "supports_mixed_precision",
]
