"""HAL Manager - Central Hardware Abstraction Layer Lifecycle Manager.

HARDENED (Dec 22, 2025): Real hardware is MANDATORY. No mock fallbacks.

Responsibilities:
- Platform auto-detection
- Adapter initialization and lifecycle
- Adapter registry and discovery
- Health monitoring

Design Note:
    This manager uses local (inline) imports for platform adapters to avoid
    import-time circular dependencies and reduce startup time on platforms
    where specific adapters are not needed.

Created: November 10, 2025
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
from typing import Any

from kagami_hal.adapters.common.gestural_interface import (
    ColonyActivation,
    GesturalInterface,
    GesturePhysics,
)
from kagami_hal.adapters.common.gesture import (
    GestureConfig,
    GestureRecognizer,
    get_gesture_recognizer,
)
from kagami_hal.data_types import AudioConfig, AudioFormat
from kagami_hal.metrics_adapter import emit_hal_status
from kagami_hal.protocols import (
    AudioAdapterProtocol,
    DisplayAdapterProtocol,
    InputAdapterProtocol,
    PowerAdapterProtocol,
    SensorAdapterProtocol,
)

# Import shared types from canonical location (hal/types.py)
from kagami_hal.types import HALStatus, Platform

logger = logging.getLogger(__name__)


class HALManager:
    """Central HAL lifecycle manager.

    Usage:
        hal = HALManager()
        await hal.initialize()

        # Access adapters
        display = hal.display
        audio = hal.audio

        # Cleanup
        await hal.shutdown()
    """

    def __init__(
        self,
        force_platform: Platform | None = None,
    ):
        """Initialize HAL manager.

        HARDENED (Dec 22, 2025): Real hardware is MANDATORY.

        Args:
            force_platform: Override platform detection
        """
        self._force_platform = force_platform

        # Detect platform
        self.platform = self._detect_platform()

        # Adapters (None until initialized)
        # NOTE: These use Protocol types but concrete implementations may not fully satisfy
        # the protocol due to platform-specific variations. The type: ignore comments below
        # are intentional - removing them requires substantial refactoring to make all
        # platform adapters strictly conform to protocols (tracked in tech debt).
        self.display: DisplayAdapterProtocol | None = None
        self.audio: AudioAdapterProtocol | None = None
        self.input: InputAdapterProtocol | None = None
        self.sensors: SensorAdapterProtocol | None = None
        self.power: PowerAdapterProtocol | None = None

        # Gesture subsystem (cross-platform, always available)
        self.gesture: GestureRecognizer | None = None
        self.gestural: GesturalInterface | None = None
        self._colony_callbacks: list = []

        # Wake word detection (optional, requires PICOVOICE_ACCESS_KEY)
        self.wake_word: Any = None

        # Status tracking
        self._initialized = False
        self._adapters_initialized = 0
        self._adapters_failed = 0
        self._mock_mode = False

    def _detect_platform(self) -> Platform:
        """Detect current platform.

        Returns:
            Platform enum
        """
        if self._force_platform:
            return self._force_platform

        # Check for virtual mode environment variable (testing/CI)
        if os.getenv("KAGAMI_HAL_VIRTUAL_MODE", "0") == "1":
            logger.info("Virtual mode enabled via KAGAMI_HAL_VIRTUAL_MODE")
            return Platform.VIRTUAL

        # Check environment overrides (only if explicitly set)
        env_platform = os.getenv("KAGAMI_HAL_PLATFORM")
        logger.debug(f"KAGAMI_HAL_PLATFORM env var: {env_platform!r}")
        if env_platform:
            # Normalize common aliases
            platform_map = {
                "macos": "darwin",
                "osx": "darwin",
                "mac": "darwin",
                "win": "windows",
                "win32": "windows",
            }
            normalized = platform_map.get(env_platform.lower(), env_platform.lower())
            logger.debug(f"Normalized platform: {normalized!r}")
            try:
                detected = Platform(normalized)
                logger.info(f"Platform from env: {detected.value}")
                return detected
            except ValueError:
                logger.warning(f"Invalid KAGAMI_HAL_PLATFORM: {env_platform}")

        # Auto-detect
        system = platform.system().lower()

        if system == "linux":
            # Check for Android / Wear OS
            if os.path.exists("/system/build.prop"):
                # Check for Wear OS (has wear feature)
                if os.path.exists("/system/framework/com.google.android.wearable.jar"):
                    return Platform.WEAROS
                return Platform.ANDROID
            return Platform.LINUX

        elif system == "darwin":
            # Check for iOS / watchOS
            machine = platform.machine()
            if machine.startswith("iP"):
                return Platform.IOS
            elif machine.startswith("Watch") or os.environ.get("KAGAMI_PLATFORM") == "watchos":
                return Platform.WATCHOS
            return Platform.MACOS

        elif system == "windows":
            return Platform.WINDOWS

        else:
            logger.warning(f"Unknown platform: {system}")
            return Platform.UNKNOWN

    async def initialize(self) -> bool:
        """Initialize all HAL adapters.

        Returns:
            True if at least one adapter initialized successfully
        """
        if self._initialized:
            logger.warning("HAL manager already initialized")
            return True

        logger.info(f"🔧 Initializing HAL for platform: {self.platform.value}")

        # HARDENED (Dec 22, 2025): No mock mode - real hardware required
        self._mock_mode = False
        success = await self._initialize_platform_adapters()

        if not success:
            raise RuntimeError(
                f"HAL initialization failed for platform {self.platform.value} - real hardware required"
            )

        # UNIFIED DISPLAY STRATEGY:
        # Wrap whatever physical display we found (or None) with the Unified Adapter
        # This ensures AGUI streaming always works, regardless of physical hardware
        from kagami_hal.adapters.unified_display import UnifiedDisplayAdapter

        # If we initialized a physical display, pass it to Unified
        # Cast to DisplayController for UnifiedDisplayAdapter compatibility
        from kagami_hal.display_controller import DisplayController

        # Type ignore: DisplayAdapterProtocol -> DisplayController cast is safe at runtime
        # but mypy cannot verify protocol structural typing here
        physical_display: DisplayController | None = self.display  # type: ignore[assignment]
        unified = UnifiedDisplayAdapter(physical_display)

        # Always initialize the Unified display wrapper so AGUI init events fire.
        # The adapter is responsible for avoiding duplicate physical initialization.
        await unified.initialize()
        # Type ignore: UnifiedDisplayAdapter implements DisplayAdapterProtocol but mypy
        # cannot verify due to complexity of protocol structural typing
        self.display = unified  # type: ignore[assignment]

        self._initialized = success

        # Initialize gesture subsystem (always available, cross-platform)
        await self._initialize_gesture_subsystem()

        # Initialize wake word detection (optional, requires PICOVOICE_ACCESS_KEY)
        await self._initialize_wake_word()

        # Log status
        status = self.get_status()
        logger.info(
            f"✅ HAL initialized: {status.adapters_initialized} adapters, "
            f"{status.adapters_failed} failed, virtual={status.mock_mode}, "
            f"gesture={self.gesture is not None}, wake_word={self.wake_word is not None}"
        )
        emit_hal_status(status)

        return success

    async def _initialize_gesture_subsystem(self) -> bool:
        """Initialize gesture recognition and gestural interface.

        This subsystem is cross-platform and always available.
        When sensors provide IMU data, gestures are recognized.
        When EMG data is available, continuous intent is extracted.
        """
        try:
            # Initialize IMU gesture recognizer
            gesture_config = GestureConfig(
                sample_rate_hz=100,
                colony_gesture_enabled=True,
                colony_confidence_threshold=0.7,
            )
            self.gesture = get_gesture_recognizer(gesture_config)
            await self.gesture.start()

            # Initialize Alyx-style gestural interface for sEMG
            gesture_physics = GesturePhysics(
                spring_k=50.0,
                damping_b=10.0,
                activation_threshold=0.15,
            )
            self.gestural = GesturalInterface(
                physics=gesture_physics,
                enable_haptics=self.audio is not None,  # Haptics via audio if available
            )
            await self.gestural.start()

            # Wire colony activations to callbacks
            self.gestural.register_colony_callback(self._on_colony_activation)

            # Wire sensor data to gesture subsystem
            await self._wire_gesture_sensors()

            logger.info("✅ Gesture subsystem initialized (IMU + sEMG)")
            return True

        except Exception as e:
            logger.warning(f"Gesture subsystem unavailable: {e}")
            return False

    async def _initialize_wake_word(self) -> bool:
        """Initialize wake word detection.

        This is optional and requires:
        - pyaudio and pvporcupine installed
        - PICOVOICE_ACCESS_KEY environment variable set

        Returns:
            True if wake word detector initialized successfully
        """
        try:
            from kagami_hal.wake_word import (
                WAKE_WORD_AVAILABLE,
                HALWakeWord,
                WakeWordConfig,
            )

            if not WAKE_WORD_AVAILABLE:
                logger.debug("Wake word dependencies not available")
                return False

            if not os.environ.get("PICOVOICE_ACCESS_KEY"):
                logger.debug("PICOVOICE_ACCESS_KEY not set, wake word disabled")
                return False

            # Configure with built-in keywords
            config = WakeWordConfig(
                keywords=["computer", "jarvis"],  # Built-in Porcupine keywords
                threshold=0.5,
            )

            self.wake_word = HALWakeWord()
            if await self.wake_word.initialize(config):
                logger.info("✅ Wake word detection initialized")
                return True
            else:
                self.wake_word = None
                return False

        except Exception as e:
            logger.debug(f"Wake word initialization skipped: {e}")
            self.wake_word = None
            return False

    async def _wire_gesture_sensors(self) -> None:
        """Wire sensor callbacks to gesture recognition.

        Subscribes to IMU sensors (accelerometer, gyroscope) and feeds
        data to the gesture recognizer. Also wires sEMG to the gestural
        interface for continuous intent recognition.
        """
        from kagami_hal.data_types import SensorReading, SensorType

        if self.sensors is None:
            logger.debug("No sensors available for gesture wiring")
            return

        # Track latest gyro reading for combining with accel
        self._latest_gyro: tuple[float, float, float] | None = None

        async def on_accel(reading: SensorReading) -> None:
            """Feed accelerometer data to gesture recognizer."""
            if self.gesture is None:
                return
            try:
                val = reading.value
                # Handle both dict and tuple formats
                if isinstance(val, dict):
                    accel = (val.get("x", 0.0), val.get("y", 0.0), val.get("z", 0.0))
                elif hasattr(val, "x"):
                    accel = (val.x, val.y, val.z)
                else:
                    accel = tuple(val) if hasattr(val, "__iter__") else (0.0, 0.0, 0.0)

                await self.gesture.feed_imu(
                    accel=accel,
                    gyro=self._latest_gyro,
                    timestamp=reading.timestamp_ms / 1000.0,
                )
            except Exception as e:
                logger.debug(f"Gesture feed_imu error: {e}")

        async def on_gyro(reading: SensorReading) -> None:
            """Cache gyroscope data for combining with accelerometer."""
            try:
                val = reading.value
                if isinstance(val, dict):
                    self._latest_gyro = (val.get("x", 0.0), val.get("y", 0.0), val.get("z", 0.0))
                elif hasattr(val, "x"):
                    self._latest_gyro = (val.x, val.y, val.z)
                else:
                    self._latest_gyro = tuple(val) if hasattr(val, "__iter__") else None
            except Exception:
                pass

        async def on_emg(reading: SensorReading) -> None:
            """Feed sEMG data to gestural interface."""
            if self.gestural is None:
                return
            try:
                val = reading.value
                # EMG is typically 8 channels
                if isinstance(val, list | tuple):
                    await self.gestural.feed_emg(val)  # type: ignore[arg-type]
                elif hasattr(val, "channels"):
                    await self.gestural.feed_emg(val.channels)
            except Exception as e:
                logger.debug(f"Gestural feed_emg error: {e}")

        # Subscribe to available sensors
        try:
            available = await self.sensors.list_sensors()

            if SensorType.ACCELEROMETER in available:
                await self.sensors.subscribe(SensorType.ACCELEROMETER, on_accel, rate_hz=100)
                logger.debug("Gesture: subscribed to accelerometer")

            if SensorType.GYROSCOPE in available:
                await self.sensors.subscribe(SensorType.GYROSCOPE, on_gyro, rate_hz=100)
                logger.debug("Gesture: subscribed to gyroscope")

            if SensorType.SEMG in available:
                await self.sensors.subscribe(SensorType.SEMG, on_emg, rate_hz=200)
                logger.debug("Gesture: subscribed to sEMG")

        except Exception as e:
            logger.debug(f"Gesture sensor wiring incomplete: {e}")

    async def _on_colony_activation(self, activation: ColonyActivation) -> None:
        """Handle colony activation from gesture interface.

        This is the bridge between HAL gestures and colony routing.
        """
        logger.debug(
            f"Colony activation: {activation.colony.value} "
            f"(activation={activation.activation:.2f}, confidence={activation.confidence:.2f})"
        )

        # Notify all registered callbacks
        for callback in self._colony_callbacks:
            try:
                await callback(activation)
            except Exception as e:
                logger.warning(f"Colony callback error: {e}")

    def register_colony_callback(self, callback: Any) -> None:
        """Register a callback for colony activation events.

        Callbacks receive ColonyActivation objects when gestures
        trigger colony transitions.
        """
        self._colony_callbacks.append(callback)

    async def _initialize_platform_adapters(self) -> bool:
        """Initialize platform-specific adapters.

        Returns:
            True if at least one adapter succeeded
        """
        # Inline imports to prevent circular dependencies and reduce import time
        if self.platform == Platform.LINUX:
            return await self._initialize_linux()
        elif self.platform == Platform.MACOS:
            return await self._initialize_macos()
        elif self.platform == Platform.WINDOWS:
            return await self._initialize_windows()
        elif self.platform == Platform.ANDROID:
            return await self._initialize_android()
        elif self.platform == Platform.IOS:
            return await self._initialize_ios()
        elif self.platform == Platform.WATCHOS:
            return await self._initialize_watchos()
        elif self.platform == Platform.WEAROS:
            return await self._initialize_wearos()
        elif self.platform == Platform.EMBEDDED:
            return await self._initialize_embedded()
        elif self.platform == Platform.WASM:
            return await self._initialize_wasm()
        elif self.platform == Platform.AGUI:
            # HARDENED (Dec 22, 2025): AGUI requires real AGUI hardware/service
            logger.info("Initializing AGUI platform")
            return await self._initialize_agui()  # type: ignore[attr-defined]
        elif self.platform == Platform.VIRTUAL:
            # Virtual adapters for testing/CI (Dec 23, 2025)
            logger.info("Initializing virtual platform (testing mode)")
            self._mock_mode = True
            return await self._initialize_virtual_adapters()
        else:
            # HARDENED (Dec 22, 2025): No fallback - fail on unsupported platform
            raise RuntimeError(f"Platform not supported: {self.platform}. Real hardware required.")

    # =========================================================================
    # Adapter Initialization Helper (Reduces Boilerplate)
    # =========================================================================

    async def _init_adapter(
        self,
        adapter_type: str,
        module_path: str,
        class_name: str,
        platform_name: str,
        config: AudioConfig | None = None,
    ) -> bool:
        """Initialize a single adapter with error handling.

        Args:
            adapter_type: Type of adapter (display, audio, input, sensors, power)
            module_path: Full module path to import from
            class_name: Name of adapter class
            platform_name: Platform name for logging
            config: Optional config for audio adapters

        Returns:
            True if initialization succeeded
        """
        try:
            import importlib

            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)
            adapter = adapter_class()

            # Initialize (audio needs config)
            if config is not None:
                init_result = await adapter.initialize(config)
            else:
                init_result = await adapter.initialize()

            if init_result:
                setattr(self, adapter_type, adapter)
                self._adapters_initialized += 1
                return True
            else:
                self._adapters_failed += 1
                return False

        except Exception as e:
            logger.warning(f"{platform_name} {adapter_type} unavailable: {e}")
            self._adapters_failed += 1
            return False

    # =========================================================================
    # Platform-Specific Initialization
    # =========================================================================

    async def _initialize_linux(self) -> bool:
        """Initialize Linux adapters."""
        audio_config = AudioConfig(
            sample_rate=44100, channels=2, format=AudioFormat.PCM_16, buffer_size=1024
        )

        results = await asyncio.gather(
            self._init_adapter(
                "display",
                "kagami_hal.adapters.linux.display",
                "LinuxFramebufferDisplay",
                "Linux",
            ),
            self._init_adapter(
                "audio",
                "kagami_hal.adapters.linux.audio",
                "LinuxALSAAudio",
                "Linux",
                audio_config,
            ),
            self._init_adapter(
                "input", "kagami_hal.adapters.linux.input", "LinuxEvdevInput", "Linux"
            ),
            self._init_adapter(
                "sensors", "kagami_hal.adapters.linux.sensors", "LinuxSensorAdapter", "Linux"
            ),
            self._init_adapter("power", "kagami_hal.adapters.linux.power", "LinuxPower", "Linux"),
            return_exceptions=True,
        )

        return any(r is True for r in results)

    async def _initialize_macos(self) -> bool:
        """Initialize macOS adapters."""
        audio_config = AudioConfig(
            sample_rate=48000, channels=2, format=AudioFormat.PCM_16, buffer_size=2048
        )

        results = await asyncio.gather(
            self._init_adapter(
                "display",
                "kagami_hal.adapters.macos.display",
                "MacOSCoreGraphicsDisplay",
                "macOS",
            ),
            self._init_adapter(
                "audio",
                "kagami_hal.adapters.macos.audio",
                "MacOSCoreAudio",
                "macOS",
                audio_config,
            ),
            self._init_adapter(
                "input", "kagami_hal.adapters.macos.input", "MacOSIOKitInput", "macOS"
            ),
            self._init_adapter(
                "sensors", "kagami_hal.adapters.macos.sensors", "MacOSSensors", "macOS"
            ),
            self._init_adapter("power", "kagami_hal.adapters.macos.power", "MacOSPower", "macOS"),
            return_exceptions=True,
        )

        return any(r is True for r in results)

    async def _initialize_windows(self) -> bool:
        """Initialize Windows adapters."""
        success = False

        # Display (Win32 GDI)
        try:
            from kagami_hal.adapters.windows.display import WindowsGDIDisplay

            display = WindowsGDIDisplay()
            if await display.initialize():
                self.display = display  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True
            else:
                self._adapters_failed += 1
        except Exception as e:
            logger.warning(f"Windows display unavailable: {e}")
            self._adapters_failed += 1

        # Audio (WASAPI)
        try:
            from kagami_hal.adapters.windows.audio import WindowsWASAPIAudio
            from kagami_hal.data_types import AudioConfig, AudioFormat

            audio = WindowsWASAPIAudio()
            config = AudioConfig(48000, 2, AudioFormat.PCM_16, 2048)
            if await audio.initialize(config):
                self.audio = audio  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True
            else:
                self._adapters_failed += 1
        except Exception as e:
            logger.warning(f"Windows audio unavailable: {e}")
            self._adapters_failed += 1

        # Input, Sensors, Power
        try:
            from kagami_hal.adapters.windows.input import WindowsInput
            from kagami_hal.adapters.windows.power import WindowsPower
            from kagami_hal.adapters.windows.sensors import (
                WindowsSensors,  # type: ignore[attr-defined]
            )

            input_adapter = WindowsInput()
            if await input_adapter.initialize():
                self.input = input_adapter  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            sensors = WindowsSensors()
            if await sensors.initialize():
                self.sensors = sensors

                self._adapters_initialized += 1
                success = True

            power = WindowsPower()
            if await power.initialize():
                self.power = power  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True
        except Exception as e:
            logger.warning(f"Windows adapters unavailable: {e}")

        return success

    async def _initialize_android(self) -> bool:
        """Initialize Android adapters."""
        success = False

        try:
            from kagami_hal.adapters.android.audio import AndroidAudio
            from kagami_hal.adapters.android.display import AndroidDisplay
            from kagami_hal.adapters.android.input import AndroidInput
            from kagami_hal.adapters.android.power import AndroidPower
            from kagami_hal.adapters.android.sensors import AndroidSensors
            from kagami_hal.data_types import AudioConfig, AudioFormat

            display = AndroidDisplay()
            if await display.initialize():
                self.display = display  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            audio = AndroidAudio()
            config = AudioConfig(48000, 2, AudioFormat.PCM_16, 1024)
            if await audio.initialize(config):
                self.audio = audio  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            input_adapter = AndroidInput()
            if await input_adapter.initialize():
                self.input = input_adapter  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            sensors = AndroidSensors()
            if await sensors.initialize():
                self.sensors = sensors  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            power = AndroidPower()
            if await power.initialize():
                self.power = power  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True
        except Exception as e:
            logger.warning(f"Android adapters unavailable: {e}")

        return success

    async def _initialize_ios(self) -> bool:
        """Initialize iOS adapters."""
        success = False

        try:
            from kagami_hal.adapters.ios.audio import iOSAudio
            from kagami_hal.adapters.ios.display import iOSDisplay
            from kagami_hal.adapters.ios.input import iOSInput
            from kagami_hal.adapters.ios.power import iOSPower
            from kagami_hal.adapters.ios.sensors import iOSSensors
            from kagami_hal.data_types import AudioConfig, AudioFormat

            display = iOSDisplay()
            if await display.initialize():
                self.display = display  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            audio = iOSAudio()
            config = AudioConfig(48000, 2, AudioFormat.PCM_16, 1024)
            if await audio.initialize(config):
                self.audio = audio  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            input_adapter = iOSInput()
            if await input_adapter.initialize():
                self.input = input_adapter  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            sensors = iOSSensors()
            if await sensors.initialize():
                self.sensors = sensors  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            power = iOSPower()
            if await power.initialize():
                self.power = power  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True
        except Exception as e:
            logger.warning(f"iOS adapters unavailable: {e}")

        return success

    async def _initialize_watchos(self) -> bool:
        """Initialize Apple Watch adapters."""
        success = False

        try:
            from kagami_hal.adapters.watchos.audio import WatchOSAudio
            from kagami_hal.adapters.watchos.display import WatchOSDisplay
            from kagami_hal.adapters.watchos.input import WatchOSInput
            from kagami_hal.adapters.watchos.power import WatchOSPower
            from kagami_hal.adapters.watchos.sensors import WatchOSSensors
            from kagami_hal.data_types import AudioConfig, AudioFormat

            display = WatchOSDisplay()
            if await display.initialize():
                self.display = display
                self._adapters_initialized += 1
                success = True

            # Lower sample rate for watch audio
            audio = WatchOSAudio()
            config = AudioConfig(16000, 1, AudioFormat.PCM_16, 512)
            if await audio.initialize(config):
                self.audio = audio
                self._adapters_initialized += 1
                success = True

            input_adapter = WatchOSInput()
            if await input_adapter.initialize():
                self.input = input_adapter
                self._adapters_initialized += 1
                success = True

            sensors = WatchOSSensors()
            if await sensors.initialize():
                self.sensors = sensors  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            power = WatchOSPower()
            if await power.initialize():
                self.power = power
                self._adapters_initialized += 1
                success = True

        except Exception as e:
            logger.warning(f"WatchOS adapters unavailable: {e}")

        return success

    async def _initialize_wearos(self) -> bool:
        """Initialize Wear OS adapters."""
        success = False

        try:
            from kagami_hal.adapters.wearos.audio import WearOSAudio
            from kagami_hal.adapters.wearos.display import WearOSDisplay
            from kagami_hal.adapters.wearos.input import WearOSInput
            from kagami_hal.adapters.wearos.power import WearOSPower
            from kagami_hal.adapters.wearos.sensors import WearOSSensors
            from kagami_hal.data_types import AudioConfig, AudioFormat

            display = WearOSDisplay()
            if await display.initialize():
                self.display = display
                self._adapters_initialized += 1
                success = True

            # Lower sample rate for watch audio
            audio = WearOSAudio()
            config = AudioConfig(16000, 1, AudioFormat.PCM_16, 1024)
            if await audio.initialize(config):
                self.audio = audio
                self._adapters_initialized += 1
                success = True

            input_adapter = WearOSInput()
            if await input_adapter.initialize():
                self.input = input_adapter
                self._adapters_initialized += 1
                success = True

            sensors = WearOSSensors()
            if await sensors.initialize():
                self.sensors = sensors  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            power = WearOSPower()
            if await power.initialize():
                self.power = power
                self._adapters_initialized += 1
                success = True

        except Exception as e:
            logger.warning(f"WearOS adapters unavailable: {e}")

        return success

    async def _initialize_embedded(self) -> bool:
        """Initialize embedded platform adapters."""
        success = False

        try:
            from kagami_hal.adapters.embedded.audio import EmbeddedAudio
            from kagami_hal.adapters.embedded.display import EmbeddedDisplay
            from kagami_hal.adapters.embedded.input import EmbeddedInput
            from kagami_hal.adapters.embedded.power import EmbeddedPower
            from kagami_hal.adapters.embedded.sensors import (
                EmbeddedSensors,  # type: ignore[attr-defined]
            )
            from kagami_hal.data_types import AudioConfig, AudioFormat

            display = EmbeddedDisplay()
            if await display.initialize():
                self.display = display  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            audio = EmbeddedAudio()
            config = AudioConfig(16000, 1, AudioFormat.PCM_16, 512)
            if await audio.initialize(config):
                self.audio = audio  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            input_adapter = EmbeddedInput()
            if await input_adapter.initialize():
                self.input = input_adapter  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            sensors = EmbeddedSensors()
            if await sensors.initialize():
                self.sensors = sensors

                self._adapters_initialized += 1
                success = True

            power = EmbeddedPower()
            if await power.initialize():
                self.power = power  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True
        except Exception as e:
            logger.warning(f"Embedded adapters unavailable: {e}")

        return success

    async def _initialize_wasm(self) -> bool:
        """Initialize WebAssembly adapters."""
        success = False

        try:
            from kagami_hal.adapters.wasm.audio import WASMAudio
            from kagami_hal.adapters.wasm.display import WASMDisplay
            from kagami_hal.adapters.wasm.input import WASMInput
            from kagami_hal.adapters.wasm.power import WASMPower
            from kagami_hal.adapters.wasm.sensors import WASMSensors
            from kagami_hal.data_types import AudioConfig, AudioFormat

            display = WASMDisplay()
            if await display.initialize():
                self.display = display  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            audio = WASMAudio()
            config = AudioConfig(48000, 2, AudioFormat.PCM_16, 2048)
            if await audio.initialize(config):
                self.audio = audio  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            input_adapter = WASMInput()
            if await input_adapter.initialize():
                self.input = input_adapter  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            sensors = WASMSensors()
            if await sensors.initialize():
                self.sensors = sensors  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True

            power = WASMPower()
            if await power.initialize():
                self.power = power  # type: ignore[assignment]
                self._adapters_initialized += 1
                success = True
        except Exception as e:
            logger.warning(f"WASM adapters unavailable: {e}")

        return success

    async def _initialize_virtual_adapters(self) -> bool:
        """Initialize virtual adapters for headless/testing environments."""
        logger.info("🖥️ Initializing virtual HAL adapters")

        try:
            from kagami_hal.adapters.virtual.audio import VirtualAudio
            from kagami_hal.adapters.virtual.display import VirtualDisplay
            from kagami_hal.adapters.virtual.input import VirtualInput
            from kagami_hal.adapters.virtual.power import VirtualPower
            from kagami_hal.adapters.virtual.sensors import VirtualSensors
            from kagami_hal.data_types import AudioConfig, AudioFormat

            display = VirtualDisplay()
            await display.initialize()
            self.display = display  # type: ignore[assignment]

            audio = VirtualAudio()
            config = AudioConfig(44100, 2, AudioFormat.PCM_16, 1024)
            await audio.initialize(config)
            self.audio = audio  # type: ignore[assignment]

            input_adapter = VirtualInput()
            await input_adapter.initialize()
            self.input = input_adapter  # type: ignore[assignment]

            sensors = VirtualSensors()
            await sensors.initialize()
            self.sensors = sensors  # type: ignore[assignment]

            power = VirtualPower()
            await power.initialize()
            self.power = power  # type: ignore[assignment]

            self._adapters_initialized = 5
            self._adapters_failed = 0
            logger.info("✅ Virtual adapters initialized (5/5)")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize virtual adapters: {e}")
            return False

    async def shutdown(self) -> None:
        """Shutdown all adapters."""
        if not self._initialized:
            return

        logger.info("🔧 Shutting down HAL adapters")

        # Shutdown wake word first
        if self.wake_word:
            try:
                await self.wake_word.shutdown()
            except Exception as e:
                logger.error(f"Wake word shutdown failed: {e}")

        # Shutdown gesture subsystem
        if self.gestural:
            try:
                await self.gestural.stop()
            except Exception as e:
                logger.error(f"Gestural interface shutdown failed: {e}")

        if self.gesture:
            try:
                await self.gesture.stop()
            except Exception as e:
                logger.error(f"Gesture recognizer shutdown failed: {e}")

        # Shutdown in reverse order
        if self.power:
            try:
                await self.power.shutdown()
            except Exception as e:
                logger.error(f"Power shutdown failed: {e}")

        if self.sensors:
            try:
                await self.sensors.shutdown()
            except Exception as e:
                logger.error(f"Sensors shutdown failed: {e}")

        if self.input:
            try:
                await self.input.shutdown()
            except Exception as e:
                logger.error(f"Input shutdown failed: {e}")

        if self.audio:
            try:
                await self.audio.shutdown()
            except Exception as e:
                logger.error(f"Audio shutdown failed: {e}")

        if self.display:
            try:
                await self.display.shutdown()
            except Exception as e:
                logger.error(f"Display shutdown failed: {e}")

        self._initialized = False
        logger.info("✅ HAL shutdown complete")
        emit_hal_status(self.get_status())

    def get_status(self) -> HALStatus:
        """Get current HAL status.

        Returns:
            HALStatus with adapter availability
        """
        return HALStatus(
            platform=self.platform,
            display_available=self.display is not None,
            audio_available=self.audio is not None,
            input_available=self.input is not None,
            sensors_available=self.sensors is not None,
            power_available=self.power is not None,
            gesture_available=self.gesture is not None,
            gestural_available=self.gestural is not None,
            wake_word_available=self.wake_word is not None,
            mock_mode=self._mock_mode,
            adapters_initialized=self._adapters_initialized,
            adapters_failed=self._adapters_failed,
        )

    def __repr__(self) -> str:
        """String representation."""
        status = self.get_status()
        return (
            f"HALManager(platform={self.platform.value}, "
            f"initialized={self._initialized}, "
            f"adapters={status.adapters_initialized}, "
            f"virtual={status.mock_mode})"
        )


# Global singleton
_HAL_MANAGER: HALManager | None = None


async def get_hal_manager() -> HALManager:
    """Get global HAL manager singleton.

    Returns:
        Initialized HAL manager
    """
    global _HAL_MANAGER

    if _HAL_MANAGER is None:
        _HAL_MANAGER = HALManager()
        await _HAL_MANAGER.initialize()

    return _HAL_MANAGER


async def shutdown_hal_manager() -> None:
    """Shutdown global HAL manager."""
    global _HAL_MANAGER

    if _HAL_MANAGER is not None:
        await _HAL_MANAGER.shutdown()
        _HAL_MANAGER = None
