"""Embedded HAL adapters.

Platform-specific implementations for embedded systems:
- Raspberry Pi (3, 4, 5)
- NVIDIA Jetson (Nano, Xavier, Orin)
- Generic ARM64 devices
- Colony Orb (custom hardware)

Created: November 10, 2025
Updated: December 15, 2025 - Added platform detection, sensors, actuators
Updated: January 2026 - Added Colony Orb hardware drivers (RM69330, IMX989, sensiBel, XMOS)
"""

# Import EmbeddedSensors from the base sensors.py module (not sensors/ package)
# This maintains backward compatibility with existing HAL code
import importlib.util
from pathlib import Path

from kagami_hal.adapters.embedded.audio import EmbeddedAudio
from kagami_hal.adapters.embedded.display import EmbeddedDisplay
from kagami_hal.adapters.embedded.input import EmbeddedInput
from kagami_hal.adapters.embedded.power import EmbeddedPower

_sensors_file = Path(__file__).parent / "sensors.py"
_spec = importlib.util.spec_from_file_location("_embedded_sensors_legacy", _sensors_file)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Failed to load EmbeddedSensors from {_sensors_file}")
_sensors_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sensors_module)
EmbeddedSensors = _sensors_module.EmbeddedSensors

# Import new platform detection modules
from kagami_hal.adapters.embedded.compute import EdgeComputeDetector

# Colony Orb hardware drivers
from kagami_hal.adapters.embedded.imx989_camera import (
    IMX989Camera,
    IMX989CaptureError,
    IMX989CaptureMode,
    IMX989Config,
    IMX989ConfigurationError,
    IMX989Error,
    IMX989Focus,
    IMX989HDRMode,
    IMX989InitializationError,
    IMX989Metadata,
    IMX989StateError,
    create_imx989_camera,
)
from kagami_hal.adapters.embedded.platforms import (
    ComputeCapabilities,
    EmbeddedHAL,
    EmbeddedPlatform,
    PlatformFeatures,
)
from kagami_hal.adapters.embedded.rm69330_display import (
    RM69330CommunicationError,
    RM69330Config,
    RM69330Display,
    RM69330Error,
    RM69330InitializationError,
    RM69330Interface,
    RM69330PowerMode,
    RM69330StateError,
    create_rm69330_display,
)
from kagami_hal.adapters.embedded.sensibel_microphone import (
    BeamDirection,
    BeamInfo,
    MicrophoneStatus,
    SensibelCalibrationError,
    SensibelCaptureError,
    SensibelConfig,
    SensibelConfigurationError,
    SensibelError,
    SensibelGain,
    SensibelInitializationError,
    SensibelInterface,
    SensibelMicrophone,
    SensibelStateError,
    create_sensibel_microphone,
)
from kagami_hal.adapters.embedded.xmos_audio_processor import (
    XMOSAudioProcessor,
    XVF3800BeamMode,
    XVF3800CommunicationError,
    XVF3800Config,
    XVF3800ConfigurationError,
    XVF3800Error,
    XVF3800FirmwareError,
    XVF3800InitializationError,
    XVF3800Mode,
    XVF3800NoiseSuppressionLevel,
    XVF3800StateError,
    XVF3800Status,
    create_xmos_audio_processor,
)

__all__ = [
    # Colony Orb: sensiBel Microphone Array - Types
    "BeamDirection",
    "BeamInfo",
    # Platform detection
    "ComputeCapabilities",
    "EdgeComputeDetector",
    # Legacy adapters
    "EmbeddedAudio",
    "EmbeddedDisplay",
    "EmbeddedHAL",
    "EmbeddedInput",
    "EmbeddedPlatform",
    "EmbeddedPower",
    "EmbeddedSensors",
    # Colony Orb: IMX989 Camera - Types
    "IMX989Camera",
    "IMX989CaptureError",
    "IMX989CaptureMode",
    "IMX989Config",
    "IMX989ConfigurationError",
    # Colony Orb: IMX989 Camera - Errors
    "IMX989Error",
    "IMX989Focus",
    "IMX989HDRMode",
    "IMX989InitializationError",
    "IMX989Metadata",
    "IMX989StateError",
    "MicrophoneStatus",
    "PlatformFeatures",
    "RM69330CommunicationError",
    # Colony Orb: RM69330 Display - Types
    "RM69330Config",
    "RM69330Display",
    # Colony Orb: RM69330 Display - Errors
    "RM69330Error",
    "RM69330InitializationError",
    "RM69330Interface",
    "RM69330PowerMode",
    "RM69330StateError",
    "SensibelCalibrationError",
    "SensibelCaptureError",
    "SensibelConfig",
    "SensibelConfigurationError",
    # Colony Orb: sensiBel Microphone Array - Errors
    "SensibelError",
    "SensibelGain",
    "SensibelInitializationError",
    "SensibelInterface",
    "SensibelMicrophone",
    "SensibelStateError",
    # Colony Orb: XMOS Voice Processor - Types
    "XMOSAudioProcessor",
    "XVF3800BeamMode",
    "XVF3800CommunicationError",
    "XVF3800Config",
    "XVF3800ConfigurationError",
    # Colony Orb: XMOS Voice Processor - Errors
    "XVF3800Error",
    "XVF3800FirmwareError",
    "XVF3800InitializationError",
    "XVF3800Mode",
    "XVF3800NoiseSuppressionLevel",
    "XVF3800StateError",
    "XVF3800Status",
    "create_imx989_camera",
    "create_rm69330_display",
    "create_sensibel_microphone",
    "create_xmos_audio_processor",
]
