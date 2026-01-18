"""sensiBel SBM100B Optical MEMS Microphone Array Driver for Colony Orb.

Driver for sensiBel SBM100B optical MEMS microphone array (4-mic configuration).
Uses I2S/PDM interface for high-fidelity audio capture with beamforming support.

Hardware Specifications:
- Type: Optical MEMS (interference-based sensing)
- Configuration: 4-microphone circular array
- SNR: 75 dB (A-weighted) - exceptional for MEMS
- AOP: 135 dB SPL
- Frequency response: 20 Hz - 20 kHz
- Interface: I2S (primary) or PDM
- Power: Ultra-low (<100uA active)

sensiBel Optical Technology:
Unlike capacitive MEMS, sensiBel uses interferometric sensing where
a photonic crystal membrane modulates light from an integrated LED.
This provides exceptional linearity, low noise, and resistance to
dust/moisture contamination.

Colony Orb Integration:
- Primary audio input for voice commands and ambient awareness
- 4-mic array enables 360-degree beamforming
- Ultra-low power supports always-on listening
- Works with XMOS XVF3800 for advanced DSP

Created: January 2026
Part of Colony Project - Kagami Orb Platform
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.audio_controller import AudioController
from kagami_hal.data_types import AudioConfig

logger = logging.getLogger(__name__)

# Check for I2S/ALSA availability
I2S_AVAILABLE = Path("/sys/class/sound").exists()
ALSA_AVAILABLE = False
try:
    import alsaaudio  # noqa: F401

    ALSA_AVAILABLE = True
except ImportError:
    pass


# =============================================================================
# Error Types
# =============================================================================


class SensibelError(Exception):
    """Base error for sensiBel microphone array driver.

    All sensiBel-specific errors inherit from this class, allowing
    callers to catch all microphone errors with a single except clause.

    Attributes:
        message: Human-readable error description.
        code: Optional error code for programmatic handling.
    """

    def __init__(self, message: str, code: int = 0) -> None:
        """Initialize sensiBel error.

        Args:
            message: Human-readable error description.
            code: Optional error code (default 0).
        """
        self.message = message
        self.code = code
        super().__init__(f"sensiBel Error ({code}): {message}" if code else message)


class SensibelInitializationError(SensibelError):
    """Raised when microphone array initialization fails.

    This can occur due to:
    - I2S/ALSA interface not available
    - PCM device open failure
    - Format/rate configuration rejection
    - Buffer allocation failure
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=1)


class SensibelCaptureError(SensibelError):
    """Raised when audio capture fails.

    This indicates a failure in the capture pipeline,
    such as buffer overrun or I2S clock issues.
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=2)


class SensibelConfigurationError(SensibelError):
    """Raised when microphone configuration is invalid or fails.

    Examples:
    - Invalid gain setting
    - Unsupported sample rate
    - Invalid beamforming parameters
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=3)


class SensibelStateError(SensibelError):
    """Raised when operation is invalid for current microphone state.

    Examples:
    - Attempting capture before initialization
    - Calling play() on capture-only device
    - Stopping capture when not capturing
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=4)


class SensibelCalibrationError(SensibelError):
    """Raised when array calibration fails.

    This can occur when:
    - Background noise too high for calibration
    - Microphone element not responding
    - Timing alignment cannot converge
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=5)


class SensibelGain(Enum):
    """SBM100B gain settings."""

    LOW = "low"  # 0 dB
    MEDIUM = "medium"  # +6 dB
    HIGH = "high"  # +12 dB
    MAX = "max"  # +18 dB


class SensibelInterface(Enum):
    """SBM100B interface modes."""

    I2S = "i2s"  # Inter-IC Sound
    PDM = "pdm"  # Pulse Density Modulation


class BeamDirection(Enum):
    """Beamforming direction presets."""

    FRONT = "front"  # 0 degrees
    RIGHT = "right"  # 90 degrees
    BACK = "back"  # 180 degrees
    LEFT = "left"  # 270 degrees
    OMNIDIRECTIONAL = "omni"  # No beamforming
    ADAPTIVE = "adaptive"  # Track strongest source


@dataclass
class SensibelConfig:
    """sensiBel SBM100B microphone array configuration."""

    # Audio interface
    interface: SensibelInterface = SensibelInterface.I2S
    i2s_device: str = "hw:1,0"  # ALSA device
    pdm_device: str | None = None

    # Array configuration
    microphone_count: int = 4
    array_radius_mm: float = 25.0  # Mic spacing from center

    # Audio settings
    sample_rate: int = 48000
    bit_depth: int = 24
    channels: int = 4  # One per mic

    # Gain control
    gain: SensibelGain = SensibelGain.MEDIUM

    # Beamforming (if done in driver, not DSP)
    enable_beamforming: bool = False
    default_beam_direction: BeamDirection = BeamDirection.ADAPTIVE

    # Power
    low_power_mode: bool = False


@dataclass
class MicrophoneStatus:
    """Status of individual microphone in array."""

    index: int
    active: bool
    signal_level_db: float
    noise_floor_db: float
    clipping: bool


@dataclass
class BeamInfo:
    """Current beamforming state."""

    direction_degrees: float
    width_degrees: float
    gain_db: float
    source_detected: bool
    source_confidence: float


class SensibelMicrophone(AudioController):
    """sensiBel SBM100B Optical MEMS Microphone Array Driver.

    Implements AudioController for the sensiBel 4-mic optical MEMS array.
    Provides raw multi-channel capture and optional beamforming.

    The driver interfaces with the microphone array via I2S through
    ALSA on Linux. For advanced DSP (AEC, beamforming), use in
    conjunction with XMOS XVF3800 driver.

    Safety: h(x) >= 0 - Audio capture state is always queryable,
    no silent recording modes.
    """

    def __init__(self, config: SensibelConfig | None = None) -> None:
        """Initialize sensiBel microphone driver.

        Args:
            config: Microphone configuration. Uses defaults if None.
        """
        self._config = config or SensibelConfig()

        # Audio state
        self._audio_config: AudioConfig | None = None
        self._volume = 1.0  # Capture gain multiplier

        # Hardware handles
        self._pcm: Any = None  # ALSA PCM handle
        self._mixer: Any = None  # ALSA mixer handle

        # State
        self._capturing = False
        self._beam_direction = BeamDirection.OMNIDIRECTIONAL
        self._mic_status: list[MicrophoneStatus] = []

    async def initialize(self, config: AudioConfig) -> bool:
        """Initialize the microphone array.

        Args:
            config: Audio configuration (sample rate, format, etc.).

        Returns:
            True if initialization successful.

        Safety: h(x) >= 0 - Microphones are initialized in known state,
        capture is not started until explicitly requested.
        """
        if not I2S_AVAILABLE:
            if is_test_mode():
                logger.info("sensiBel: I2S not available, gracefully degrading")
                self._audio_config = config
                return False
            raise RuntimeError("sensiBel: I2S interface required")

        try:
            # Store configuration
            self._audio_config = config

            # Initialize ALSA PCM for capture
            if ALSA_AVAILABLE:
                await self._init_alsa_capture()
            else:
                await self._init_raw_i2s()

            # Initialize microphone status
            self._mic_status = [
                MicrophoneStatus(
                    index=i,
                    active=True,
                    signal_level_db=-60.0,
                    noise_floor_db=-90.0,
                    clipping=False,
                )
                for i in range(self._config.microphone_count)
            ]

            logger.info(
                f"sensiBel SBM100B initialized: {self._config.microphone_count} mics, "
                f"{config.sample_rate}Hz, {config.channels}ch via {self._config.interface.value}"
            )
            return True

        except Exception as e:
            if is_test_mode():
                logger.info(f"sensiBel init failed, gracefully degrading: {e}")
                return False
            logger.error(f"sensiBel initialization failed: {e}", exc_info=True)
            return False

    async def _init_alsa_capture(self) -> None:
        """Initialize ALSA PCM for capture."""
        raise NotImplementedError(
            "TODO: Implement sensiBel ALSA capture initialization. "
            "Requires alsaaudio.PCM(type=PCM_CAPTURE), setformat(), "
            "setchannels(4), setrate()."
        )

    async def _init_raw_i2s(self) -> None:
        """Initialize raw I2S interface (without ALSA)."""
        raise NotImplementedError(
            "TODO: Implement sensiBel raw I2S initialization. "
            "Requires direct I2S peripheral access via /dev/i2s or spidev."
        )

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer - NOT SUPPORTED for microphone.

        Raises:
            RuntimeError: Always, as microphone is capture-only.
        """
        _ = buffer  # Unused - capture-only device
        raise RuntimeError("sensiBel SBM100B is a capture-only device")

    async def record(self, duration_ms: int) -> bytes:
        """Record audio from microphone array.

        Args:
            duration_ms: Recording duration in milliseconds.

        Returns:
            Raw PCM audio data (interleaved multi-channel).

        Safety: h(x) >= 0 - Recording state is exposed via is_capturing().
        """
        if not self._audio_config:
            raise RuntimeError("sensiBel: Not initialized")

        raise NotImplementedError(
            f"TODO: Implement sensiBel recording for {duration_ms}ms. "
            "Use ALSA read() in a loop, accumulate samples. "
            "Return interleaved 4-channel PCM data."
        )

    async def start_capture(self) -> None:
        """Start continuous audio capture.

        Begins streaming audio from the microphone array.
        Use get_audio_data() to retrieve buffered samples.
        """
        raise NotImplementedError(
            "TODO: Implement sensiBel continuous capture start. "
            "Set up ring buffer and begin ALSA capture thread."
        )

    async def stop_capture(self) -> None:
        """Stop continuous audio capture."""
        raise NotImplementedError(
            "TODO: Implement sensiBel capture stop. Stop ALSA capture, flush buffers."
        )

    def is_capturing(self) -> bool:
        """Check if capture is active.

        Returns:
            True if microphone is currently capturing audio.
        """
        return self._capturing

    async def set_gain(self, gain: SensibelGain) -> None:
        """Set microphone gain level.

        Args:
            gain: Target gain setting.
        """
        raise NotImplementedError(
            f"TODO: Implement sensiBel gain control. "
            f"Set gain to {gain.value}. "
            "Use ALSA mixer or I2C control register if available."
        )

    async def set_volume(self, level: float) -> None:
        """Set capture volume (gain multiplier).

        Args:
            level: Volume from 0.0 to 1.0.
        """
        if not (0.0 <= level <= 1.0):
            raise ValueError("Volume must be between 0.0 and 1.0")

        self._volume = level

        # Map 0-1 to gain settings
        if level < 0.25:
            await self.set_gain(SensibelGain.LOW)
        elif level < 0.5:
            await self.set_gain(SensibelGain.MEDIUM)
        elif level < 0.75:
            await self.set_gain(SensibelGain.HIGH)
        else:
            await self.set_gain(SensibelGain.MAX)

    async def get_volume(self) -> float:
        """Get current capture volume.

        Returns:
            Current volume setting (0.0-1.0).
        """
        return self._volume

    async def set_beam_direction(self, direction: BeamDirection | float) -> None:
        """Set beamforming direction.

        Args:
            direction: Preset direction or angle in degrees (0-359).

        Note: Full beamforming typically handled by XMOS DSP.
        This provides basic steering for the array.
        """
        if isinstance(direction, (int, float)):
            angle = float(direction) % 360
            # Map angle to nearest preset
            if 315 <= angle or angle < 45:
                direction = BeamDirection.FRONT
            elif 45 <= angle < 135:
                direction = BeamDirection.RIGHT
            elif 135 <= angle < 225:
                direction = BeamDirection.BACK
            else:
                direction = BeamDirection.LEFT

        self._beam_direction = direction

        raise NotImplementedError(
            f"TODO: Implement sensiBel beam steering to {direction.value}. "
            "Requires phase/delay adjustment per microphone channel."
        )

    async def get_beam_direction(self) -> BeamInfo:
        """Get current beamforming state.

        Returns:
            Current beam direction and detected source info.
        """
        raise NotImplementedError(
            "TODO: Implement sensiBel beam direction query. "
            "Return current steering angle and source detection."
        )

    async def get_microphone_status(self) -> list[MicrophoneStatus]:
        """Get status of all microphones in array.

        Returns:
            List of status for each microphone.
        """
        return self._mic_status

    async def calibrate(self) -> bool:
        """Run microphone array calibration.

        Calibrates gain matching and timing alignment across
        all microphones in the array.

        Returns:
            True if calibration successful.
        """
        raise NotImplementedError(
            "TODO: Implement sensiBel array calibration. "
            "Measure noise floor, match gains, align timing."
        )

    async def shutdown(self) -> None:
        """Shutdown microphone array and release resources.

        Safety: h(x) >= 0 - Ensures capture is stopped before
        releasing resources.
        """
        # Stop capture if active
        if self._capturing:
            try:
                await self.stop_capture()
            except NotImplementedError:
                pass
            except Exception as e:
                logger.warning(f"sensiBel capture stop warning: {e}")

        # Close ALSA handles
        if self._pcm is not None:
            try:
                self._pcm.close()
            except Exception:
                pass
            self._pcm = None

        if self._mixer is not None:
            try:
                self._mixer.close()
            except Exception:
                pass
            self._mixer = None

        self._capturing = False
        logger.info("sensiBel SBM100B shutdown complete")


# Factory function for consistent HAL pattern
def create_sensibel_microphone(config: SensibelConfig | None = None) -> SensibelMicrophone:
    """Create sensiBel microphone array driver instance.

    Factory function following HAL adapter pattern.

    Args:
        config: Microphone configuration. Uses defaults if None.

    Returns:
        Configured SensibelMicrophone instance.

    Example:
        mic = create_sensibel_microphone()
        await mic.initialize(AudioConfig(
            sample_rate=48000,
            channels=4,
            format=AudioFormat.PCM_24,
            buffer_size=1024
        ))
        audio_data = await mic.record(duration_ms=1000)
    """
    return SensibelMicrophone(config)


__all__ = [
    # Enums
    "BeamDirection",
    # Data classes
    "BeamInfo",
    "MicrophoneStatus",
    "SensibelCalibrationError",
    "SensibelCaptureError",
    "SensibelConfig",
    "SensibelConfigurationError",
    # Error types
    "SensibelError",
    "SensibelGain",
    "SensibelInitializationError",
    "SensibelInterface",
    # Driver
    "SensibelMicrophone",
    "SensibelStateError",
    # Factory
    "create_sensibel_microphone",
]
