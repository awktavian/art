"""Platform-specific HAL adapters for K os.

Provides concrete implementations of HAL interfaces for:
- Linux (framebuffer, ALSA, evdev, I2C/SPI)
- macOS (CoreGraphics, CoreAudio, IOKit)
- iOS (CoreMotion, CoreLocation)
- watchOS (WatchKit, HealthKit, CoreMotion)
- visionOS (RealityKit, ARKit, Spatial Audio)
- Android (SensorManager, JNI)
- Wear OS (Health Services, SensorManager)
- Windows (WMI, Sensor API)
- WASM (Web APIs)
- Embedded (I2C/SPI)
- Virtual (testing)
- VM (Peekaboo, Lume, Parallels)
- CLI (cross-platform command execution)
- Meta Glasses (Ray-Ban Meta smart glasses via DAT)
- Neural (Meta Neural Band sEMG wristband)
- Haptics (Cross-device haptic feedback)

Created: November 10, 2025
Updated: December 8, 2025 - Added SensorAdapterBase
Updated: December 13, 2025 - Added WatchOS and WearOS adapters
Updated: December 30, 2025 - Added VM, CLI, visionOS, and Meta Glasses adapters
Updated: January 2026 - Added Neural and Haptics adapters
"""

# CLI adapters
from kagami_hal.adapters.cli import (
    CLIAdapterProtocol,
    CommandResult,
    LocalCLIAdapter,
    Platform,
    RemoteCLIAdapter,
    ShellType,
    UnifiedCLI,
    get_local_cli,
    get_remote_cli,
    get_unified_cli,
)

# Haptics adapters
from kagami_hal.adapters.haptics import (
    HapticDevice,
    HapticFeedback,
    HapticIntensity,
    HapticPattern,
    UnifiedHapticsController,
    get_haptics_controller,
)

# Meta Glasses adapters
from kagami_hal.adapters.meta_glasses import (
    AudioBuffer,
    CameraFrame,
    CameraStreamConfig,
    GlassesCommand,
    GlassesConnectionState,
    GlassesEvent,
    MetaGlassesAudio,
    MetaGlassesCamera,
    MetaGlassesProtocol,
    OpenEarAudioConfig,
    PhotoCaptureResult,
)

# Neural adapters
from kagami_hal.adapters.neural import (
    EMGCalibrationState,
    EMGConnectionState,
    EMGGesture,
    MetaEMGAdapter,
    MetaEMGConfig,
    MetaEMGEvent,
    get_meta_emg_adapter,
)
from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase

# visionOS adapters
from kagami_hal.adapters.visionos import (
    VisionOSAudio,
    VisionOSGaze,
    VisionOSSpatial,
)

# VM adapters
from kagami_hal.adapters.vm import (
    CUALumeAdapter,
    OSType,
    ParallelsAdapter,
    PeekabooAdapter,
    VMAdapterProtocol,
    VMPool,
    VMState,
    VMStatus,
    VMTier,
    get_vm_pool,
)

__all__ = [
    "AudioBuffer",
    # CLI adapters
    "CLIAdapterProtocol",
    "CUALumeAdapter",
    "CameraFrame",
    "CameraStreamConfig",
    "CommandResult",
    # Neural adapters
    "EMGCalibrationState",
    "EMGConnectionState",
    "EMGGesture",
    "GlassesCommand",
    "GlassesConnectionState",
    "GlassesEvent",
    # Haptics adapters
    "HapticDevice",
    "HapticFeedback",
    "HapticIntensity",
    "HapticPattern",
    "LocalCLIAdapter",
    "MetaEMGAdapter",
    "MetaEMGConfig",
    "MetaEMGEvent",
    "MetaGlassesAudio",
    "MetaGlassesCamera",
    # Meta Glasses adapters
    "MetaGlassesProtocol",
    "OSType",
    "OpenEarAudioConfig",
    "ParallelsAdapter",
    "PeekabooAdapter",
    "PhotoCaptureResult",
    "Platform",
    "RemoteCLIAdapter",
    # Sensor base
    "SensorAdapterBase",
    "ShellType",
    "UnifiedCLI",
    "UnifiedHapticsController",
    # VM adapters
    "VMAdapterProtocol",
    "VMPool",
    "VMState",
    "VMStatus",
    "VMTier",
    "VisionOSAudio",
    "VisionOSGaze",
    # visionOS adapters
    "VisionOSSpatial",
    "get_haptics_controller",
    "get_local_cli",
    "get_meta_emg_adapter",
    "get_remote_cli",
    "get_unified_cli",
    "get_vm_pool",
]
