"""Hardware Abstraction Layer (HAL) for K os.

Provides unified interface to hardware peripherals across platforms.

The HAL is the Hardware VM. The RTE is the Executor. The Protocol is the Bytecode.

Supported platforms:
- Linux (framebuffer, ALSA, evdev, I2C/SPI)
- macOS (CoreGraphics, CoreAudio, IOKit)
- Windows (GDI, WASAPI, Win32, WMI)
- iOS (UIKit, AVFoundation, CoreMotion)
- Android (SurfaceView, AudioTrack, SensorManager)
- Embedded (SPI/I2C display, I2S audio, GPIO input, RTE backends)
- WASM (Canvas, Web Audio, Web Sensors)
- Virtual (testing/headless simulation)

RTE (Real-Time Executor) backends:
- PicoRTE: Raspberry Pi Pico via UART (deterministic timing)
- NativeRTE: Direct hardware access (Linux timing)
- VirtualRTE: Testing/simulation

Created: November 10, 2025
Updated: December 2, 2025 - Full platform implementation
Updated: January 2, 2026 - Added RTE subsystem for deterministic timing
"""

from kagami_hal.adapters.common.gestural_interface import (
    ColonyActivation,
    ColonyIntent,
    GesturalInterface,
    GestureCommand,
    GesturePhysics,
    IntentType,
)

# Gesture subsystem
from kagami_hal.adapters.common.gesture import (
    Gesture,
    GestureConfig,
    GestureEvent,
    GestureRecognizer,
    GestureType,
    get_gesture_recognizer,
    start_gesture_recognizer,
)
from kagami_hal.audio_controller import AudioController
from kagami_hal.colony_activation_bridge import (
    ColonyActivationBridge,
    get_colony_bridge,
    setup_gesture_colony_routing,
)
from kagami_hal.display_controller import DisplayController
from kagami_hal.driver import DeviceDriver
from kagami_hal.input_controller import InputController
from kagami_hal.manager import HALManager, get_hal_manager, shutdown_hal_manager
from kagami_hal.power_controller import PowerController
from kagami_hal.protocols import (
    AudioAdapterProtocol,
    DisplayAdapterProtocol,
    InputAdapterProtocol,
    PowerAdapterProtocol,
    SensorAdapterProtocol,
)

# Real-Time Executor (RTE) subsystem
from kagami_hal.rte import (
    LEDPattern,
    NativeRTE,
    PicoRTE,
    RTEBackend,
    RTECommand,
    RTEError,
    RTEEvent,
    RTEEventType,
    RTEResponse,
    RTEStatus,
    VirtualRTE,
    get_rte_backend,
)
from kagami_hal.sensor_manager import SensorManager
from kagami_hal.wake_word import (
    WAKE_WORD_AVAILABLE,
    HALWakeWord,
    WakeWordConfig,
    get_hal_wake_word,
    initialize_hal_wake_word,
    shutdown_hal_wake_word,
)

__all__ = [
    "WAKE_WORD_AVAILABLE",
    # Protocols
    "AudioAdapterProtocol",
    "AudioController",
    # Gestural interface (sEMG)
    "ColonyActivation",
    # Colony activation bridge
    "ColonyActivationBridge",
    "ColonyIntent",
    # Controllers
    "DeviceDriver",
    "DisplayAdapterProtocol",
    "DisplayController",
    "GesturalInterface",
    # Gesture recognition (IMU)
    "Gesture",
    "GestureCommand",
    "GestureConfig",
    "GestureEvent",
    "GesturePhysics",
    "GestureRecognizer",
    "GestureType",
    # Manager
    "HALManager",
    # Wake Word Detection
    "HALWakeWord",
    "InputAdapterProtocol",
    "InputController",
    "IntentType",
    # RTE (Real-Time Executor) - Hardware VM
    "LEDPattern",
    "NativeRTE",
    "PicoRTE",
    "PowerAdapterProtocol",
    "PowerController",
    "RTEBackend",
    "RTECommand",
    "RTEError",
    "RTEEvent",
    "RTEEventType",
    "RTEResponse",
    "RTEStatus",
    "SensorAdapterProtocol",
    "SensorManager",
    "VirtualRTE",
    "WakeWordConfig",
    "get_colony_bridge",
    "get_gesture_recognizer",
    "get_hal_manager",
    "get_hal_wake_word",
    "get_rte_backend",
    "initialize_hal_wake_word",
    "setup_gesture_colony_routing",
    "shutdown_hal_manager",
    "shutdown_hal_wake_word",
    "start_gesture_recognizer",
]
