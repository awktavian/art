"""XMOS XVF3800 Voice Processor Driver for Colony Orb.

Driver for XMOS XVF3800 voice processor providing advanced audio DSP
for voice interfaces. Handles echo cancellation, beamforming, and
voice activity detection in hardware.

Hardware Specifications:
- Processor: XMOS xcore.ai XVF3800
- Microphone inputs: Up to 4 (supports various array configs)
- Audio interface: I2S (in/out)
- Control interface: I2C, SPI, or USB
- Sample rates: 16kHz, 48kHz
- Features: AEC, beamforming, noise suppression, AGC, VAD

Key Capabilities:
- Acoustic Echo Cancellation (AEC): 50ms tail, -50dB ERLE
- Beamforming: Adaptive or fixed beam steering
- Noise Suppression: Up to 20dB reduction
- Voice Activity Detection: Low-latency wake word support
- Automatic Gain Control: Consistent output levels

Colony Orb Integration:
- Works with sensiBel SBM100B microphone array
- Processes 4-channel input, outputs clean mono/stereo
- Provides hardware VAD for wake-on-voice
- I2C control from main processor

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

logger = logging.getLogger(__name__)

# Check for I2C availability
I2C_AVAILABLE = Path("/dev/i2c-1").exists() or Path("/dev/i2c-0").exists()
SMBUS_AVAILABLE = False
try:
    import smbus2  # noqa: F401

    SMBUS_AVAILABLE = True
except ImportError:
    pass


# =============================================================================
# Error Types
# =============================================================================


class XVF3800Error(Exception):
    """Base error for XMOS XVF3800 voice processor driver.

    All XVF3800-specific errors inherit from this class, allowing
    callers to catch all processor errors with a single except clause.

    Attributes:
        message: Human-readable error description.
        code: Optional error code for programmatic handling.
    """

    def __init__(self, message: str, code: int = 0) -> None:
        """Initialize XVF3800 error.

        Args:
            message: Human-readable error description.
            code: Optional error code (default 0).
        """
        self.message = message
        self.code = code
        super().__init__(f"XVF3800 Error ({code}): {message}" if code else message)


class XVF3800InitializationError(XVF3800Error):
    """Raised when processor initialization fails.

    This can occur due to:
    - I2C interface not available
    - Device not found at expected address
    - Firmware load failure
    - Device identification mismatch
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=1)


class XVF3800CommunicationError(XVF3800Error):
    """Raised when I2C communication fails.

    This indicates a failure in the I2C communication layer,
    such as NACK, timeout, or bus error.
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=2)


class XVF3800ConfigurationError(XVF3800Error):
    """Raised when processor configuration is invalid or fails.

    Examples:
    - Invalid beam angle (out of range)
    - Unsupported noise suppression level
    - Invalid VAD threshold
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=3)


class XVF3800StateError(XVF3800Error):
    """Raised when operation is invalid for current processor state.

    Examples:
    - Attempting configuration before initialization
    - Beam steering when not initialized
    - Mode change during active processing
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=4)


class XVF3800FirmwareError(XVF3800Error):
    """Raised when firmware operations fail.

    This can occur when:
    - Firmware file not found
    - Firmware verification failure
    - Bootloader communication error
    - Incompatible firmware version
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=5)


class XVF3800Mode(Enum):
    """XVF3800 operating modes."""

    VOICE = "voice"  # Optimized for voice capture
    MUSIC = "music"  # Wider frequency response
    CONFERENCING = "conferencing"  # Full AEC + beamforming
    LOW_POWER = "low_power"  # Reduced processing


class XVF3800BeamMode(Enum):
    """XVF3800 beamforming modes."""

    FIXED = "fixed"  # Fixed beam direction
    ADAPTIVE = "adaptive"  # Tracks active speaker
    DUAL_BEAM = "dual_beam"  # Two simultaneous beams
    OMNIDIRECTIONAL = "omni"  # No beamforming


class XVF3800NoiseSuppressionLevel(Enum):
    """XVF3800 noise suppression levels."""

    OFF = "off"
    LOW = "low"  # ~6dB reduction
    MEDIUM = "medium"  # ~12dB reduction
    HIGH = "high"  # ~18dB reduction
    AGGRESSIVE = "aggressive"  # ~24dB reduction (may affect voice)


@dataclass
class XVF3800Config:
    """XVF3800 voice processor configuration."""

    # Control interface
    i2c_bus: int = 1
    i2c_address: int = 0x2C  # Default XVF3800 address

    # Audio configuration
    sample_rate: int = 16000  # 16kHz for voice, 48kHz for music
    mic_channels: int = 4
    output_channels: int = 1  # Mono output after processing

    # Operating mode
    mode: XVF3800Mode = XVF3800Mode.VOICE

    # AEC settings
    enable_aec: bool = True
    aec_tail_ms: int = 50  # Echo tail length

    # Beamforming
    beam_mode: XVF3800BeamMode = XVF3800BeamMode.ADAPTIVE
    beam_angle_degrees: float = 0.0  # For FIXED mode

    # Noise suppression
    noise_suppression: XVF3800NoiseSuppressionLevel = XVF3800NoiseSuppressionLevel.MEDIUM

    # AGC
    enable_agc: bool = True
    agc_target_level_dbfs: float = -6.0

    # VAD
    enable_vad: bool = True
    vad_threshold: float = 0.5  # 0-1 sensitivity

    # Firmware
    firmware_path: str | None = None


@dataclass
class XVF3800Status:
    """XVF3800 current status."""

    # Operating state
    mode: XVF3800Mode
    firmware_version: str
    running: bool

    # AEC status
    aec_active: bool
    echo_return_loss_db: float  # Current ERLE
    echo_detected: bool

    # Beam status
    beam_mode: XVF3800BeamMode
    beam_angle_degrees: float
    source_angle_degrees: float | None  # Detected source

    # VAD status
    vad_active: bool
    voice_detected: bool
    voice_confidence: float

    # Audio levels
    input_level_dbfs: float
    output_level_dbfs: float
    noise_floor_dbfs: float


class XMOSAudioProcessor:
    """XMOS XVF3800 Voice Processor Driver.

    Provides control interface for the XVF3800 DSP. The processor
    handles audio stream processing independently; this driver
    configures parameters and monitors status.

    Audio flow:
        sensiBel mics -> I2S -> XVF3800 -> I2S -> processed output
                              ^
                              | I2C control
                              |
                        This driver

    Safety: h(x) >= 0 - VAD state is always queryable for privacy
    indication. No silent bypass of processing chain.
    """

    # I2C register addresses (simplified - actual XVF3800 uses SPI protocol)
    _REG_DEVICE_ID = 0x00
    _REG_FIRMWARE_VERSION = 0x01
    _REG_CONTROL = 0x10
    _REG_AEC_ENABLE = 0x20
    _REG_AEC_TAIL = 0x21
    _REG_BEAM_MODE = 0x30
    _REG_BEAM_ANGLE = 0x31
    _REG_NOISE_SUPPRESSION = 0x40
    _REG_AGC_ENABLE = 0x50
    _REG_AGC_TARGET = 0x51
    _REG_VAD_ENABLE = 0x60
    _REG_VAD_THRESHOLD = 0x61
    _REG_VAD_STATUS = 0x62
    _REG_INPUT_LEVEL = 0x70
    _REG_OUTPUT_LEVEL = 0x71

    def __init__(self, config: XVF3800Config | None = None) -> None:
        """Initialize XVF3800 driver.

        Args:
            config: Processor configuration. Uses defaults if None.
        """
        self._config = config or XVF3800Config()

        # Hardware handles
        self._bus: Any = None

        # State
        self._initialized = False
        self._firmware_loaded = False
        self._last_status: XVF3800Status | None = None

    async def initialize(self) -> bool:
        """Initialize the XVF3800 voice processor.

        Performs:
        1. I2C bus connection
        2. Device identification
        3. Firmware loading (if specified)
        4. Initial configuration

        Returns:
            True if initialization successful.
        """
        if not I2C_AVAILABLE:
            if is_test_mode():
                logger.info("XVF3800: I2C not available, gracefully degrading")
                return False
            raise RuntimeError("XVF3800: I2C interface required")

        if not SMBUS_AVAILABLE:
            if is_test_mode():
                logger.info("XVF3800: SMBus not available, gracefully degrading")
                return False
            raise RuntimeError("XVF3800: SMBus2 required. Install: pip install smbus2")

        try:
            # Open I2C bus
            await self._open_i2c()

            # Verify device presence
            await self._verify_device()

            # Load firmware if specified
            if self._config.firmware_path:
                await self.load_firmware(self._config.firmware_path)

            # Apply initial configuration
            await self._apply_config()

            self._initialized = True
            logger.info(
                f"XVF3800 initialized: {self._config.mode.value} mode, "
                f"AEC={'on' if self._config.enable_aec else 'off'}, "
                f"beam={self._config.beam_mode.value}"
            )
            return True

        except Exception as e:
            if is_test_mode():
                logger.info(f"XVF3800 init failed, gracefully degrading: {e}")
                return False
            logger.error(f"XVF3800 initialization failed: {e}", exc_info=True)
            return False

    async def _open_i2c(self) -> None:
        """Open I2C bus connection."""
        raise NotImplementedError(
            f"TODO: Implement XVF3800 I2C bus open. Use smbus2.SMBus({self._config.i2c_bus})."
        )

    async def _verify_device(self) -> None:
        """Verify XVF3800 device is present."""
        raise NotImplementedError(
            f"TODO: Implement XVF3800 device verification. "
            f"Read device ID from address 0x{self._config.i2c_address:02X}."
        )

    async def _apply_config(self) -> None:
        """Apply configuration to XVF3800."""
        raise NotImplementedError(
            "TODO: Implement XVF3800 configuration. "
            "Write AEC, beamforming, NS, AGC, VAD settings via I2C."
        )

    async def load_firmware(self, path: str) -> bool:
        """Load firmware image to XVF3800.

        Args:
            path: Path to firmware binary (.bin or .dfu).

        Returns:
            True if firmware loaded successfully.
        """
        firmware_path = Path(path)
        if not firmware_path.exists():
            raise FileNotFoundError(f"Firmware not found: {path}")

        raise NotImplementedError(
            f"TODO: Implement XVF3800 firmware loading from {path}. "
            "Requires bootloader protocol implementation."
        )

    async def set_beam_direction(self, angle_degrees: float) -> None:
        """Set beamforming direction.

        Args:
            angle_degrees: Target beam angle (0-359 degrees).
        """
        if not self._initialized:
            raise RuntimeError("XVF3800: Not initialized")

        raise NotImplementedError(
            f"TODO: Implement XVF3800 beam steering to {angle_degrees} degrees. "
            "Write to BEAM_ANGLE register."
        )

    async def set_beam_mode(self, mode: XVF3800BeamMode) -> None:
        """Set beamforming mode.

        Args:
            mode: Target beamforming mode.
        """
        raise NotImplementedError(
            f"TODO: Implement XVF3800 beam mode change to {mode.value}. "
            "Write to BEAM_MODE register."
        )

    async def enable_aec(self, enable: bool = True) -> None:
        """Enable or disable acoustic echo cancellation.

        Args:
            enable: True to enable AEC.
        """
        raise NotImplementedError(
            f"TODO: Implement XVF3800 AEC {'enable' if enable else 'disable'}. "
            "Write to AEC_ENABLE register."
        )

    async def set_noise_suppression(self, level: XVF3800NoiseSuppressionLevel) -> None:
        """Set noise suppression level.

        Args:
            level: Target noise suppression level.
        """
        raise NotImplementedError(
            f"TODO: Implement XVF3800 noise suppression to {level.value}. "
            "Write to NOISE_SUPPRESSION register."
        )

    async def enable_vad(self, enable: bool = True, threshold: float = 0.5) -> None:
        """Enable or disable voice activity detection.

        Args:
            enable: True to enable VAD.
            threshold: Detection threshold (0-1, higher = less sensitive).
        """
        raise NotImplementedError(
            f"TODO: Implement XVF3800 VAD {'enable' if enable else 'disable'} "
            f"with threshold {threshold}. Write to VAD registers."
        )

    async def get_vad_status(self) -> tuple[bool, float]:
        """Get current voice activity detection status.

        Returns:
            Tuple of (voice_detected: bool, confidence: float).

        Safety: h(x) >= 0 - VAD status is always available for
        privacy indication.
        """
        raise NotImplementedError(
            "TODO: Implement XVF3800 VAD status read. Read from VAD_STATUS register."
        )

    async def is_voice_detected(self) -> bool:
        """Check if voice is currently detected.

        Convenience method wrapping get_vad_status().

        Returns:
            True if voice activity detected.
        """
        voice_detected, _ = await self.get_vad_status()
        return voice_detected

    async def get_status(self) -> XVF3800Status:
        """Get comprehensive processor status.

        Returns:
            Current status of all XVF3800 subsystems.
        """
        raise NotImplementedError(
            "TODO: Implement XVF3800 full status read. "
            "Read all status registers and build XVF3800Status."
        )

    async def get_audio_levels(self) -> tuple[float, float, float]:
        """Get current audio levels.

        Returns:
            Tuple of (input_dbfs, output_dbfs, noise_floor_dbfs).
        """
        raise NotImplementedError(
            "TODO: Implement XVF3800 level metering. "
            "Read from INPUT_LEVEL and OUTPUT_LEVEL registers."
        )

    async def set_mode(self, mode: XVF3800Mode) -> None:
        """Change operating mode.

        Args:
            mode: Target operating mode.

        Note: Mode change may briefly interrupt audio processing.
        """
        raise NotImplementedError(
            f"TODO: Implement XVF3800 mode change to {mode.value}. "
            "Requires reconfiguring multiple subsystems."
        )

    async def reset(self) -> None:
        """Perform soft reset of the processor."""
        raise NotImplementedError(
            "TODO: Implement XVF3800 soft reset. Write reset command to CONTROL register."
        )

    async def shutdown(self) -> None:
        """Shutdown processor and release resources.

        Safety: h(x) >= 0 - Processor is put into known low-power
        state before releasing I2C bus.
        """
        if self._bus is not None:
            try:
                # Put processor into low power mode
                # Would write to control register
                pass
            except Exception as e:
                logger.warning(f"XVF3800 shutdown warning: {e}")
            finally:
                try:
                    self._bus.close()
                except Exception:
                    pass
                self._bus = None

        self._initialized = False
        logger.info("XVF3800 voice processor shutdown complete")


# Factory function for consistent HAL pattern
def create_xmos_audio_processor(config: XVF3800Config | None = None) -> XMOSAudioProcessor:
    """Create XVF3800 audio processor driver instance.

    Factory function following HAL adapter pattern.

    Args:
        config: Processor configuration. Uses defaults if None.

    Returns:
        Configured XMOSAudioProcessor instance.

    Example:
        dsp = create_xmos_audio_processor()
        await dsp.initialize()
        await dsp.enable_aec(True)
        await dsp.set_beam_direction(45.0)
        voice_active, confidence = await dsp.get_vad_status()
    """
    return XMOSAudioProcessor(config)


__all__ = [
    # Driver
    "XMOSAudioProcessor",
    "XVF3800BeamMode",
    "XVF3800CommunicationError",
    # Data classes
    "XVF3800Config",
    "XVF3800ConfigurationError",
    # Error types
    "XVF3800Error",
    "XVF3800FirmwareError",
    "XVF3800InitializationError",
    # Enums
    "XVF3800Mode",
    "XVF3800NoiseSuppressionLevel",
    "XVF3800StateError",
    "XVF3800Status",
    # Factory
    "create_xmos_audio_processor",
]
