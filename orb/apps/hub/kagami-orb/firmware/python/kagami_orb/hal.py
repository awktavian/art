"""
Hardware Abstraction Layer (HAL) Protocol Definitions

Defines the contracts that all hardware drivers must implement.
Ensures clean separation between hardware specifics and application logic.

Architecture:
    ┌─────────────────────────────────────────────────────┐
    │             Application Layer                        │
    │  (OrbSystem, Animations, AI Inference, etc.)        │
    └─────────────────────┬───────────────────────────────┘
                          │
    ┌─────────────────────┴───────────────────────────────┐
    │                  HAL Interface                       │
    │  (This module - protocols & abstract interfaces)    │
    └─────────────────────┬───────────────────────────────┘
                          │
    ┌─────────────────────┴───────────────────────────────┐
    │             Hardware Drivers                         │
    │  (LED, Power, Sensors, NPU, Cellular, GNSS)         │
    └─────────────────────────────────────────────────────┘

Design Principles:
    1. All drivers MUST support simulate=True mode
    2. All drivers MUST implement is_initialized() -> bool
    3. All drivers MUST implement close() for cleanup
    4. Hardware-specific details stay in drivers
    5. Application uses only HAL interfaces
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol, runtime_checkable, Any
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# HAL PROTOCOLS (Interface Contracts)
# =============================================================================


@runtime_checkable
class HardwareDriver(Protocol):
    """Base protocol all hardware drivers must implement."""

    simulate: bool

    def is_initialized(self) -> bool:
        """Check if driver is ready for use."""
        ...

    def close(self) -> None:
        """Release hardware resources."""
        ...


@runtime_checkable
class LEDDriver(Protocol):
    """Protocol for LED drivers."""

    num_leds: int
    max_brightness: int

    def set_led(self, index: int, r: int, g: int, b: int, w: int = 0) -> None:
        """Set single LED color (8-bit values)."""
        ...

    def set_all(self, r: int, g: int, b: int, w: int = 0) -> None:
        """Set all LEDs to same color."""
        ...

    def clear(self) -> None:
        """Turn off all LEDs."""
        ...

    def show(self) -> None:
        """Push buffer to hardware."""
        ...


@runtime_checkable
class PowerDriver(Protocol):
    """Protocol for power management drivers."""

    def get_battery_percentage(self) -> int:
        """Get battery state of charge (0-100%)."""
        ...

    def get_voltage_mv(self) -> int:
        """Get battery voltage in millivolts."""
        ...

    def is_charging(self) -> bool:
        """Check if battery is charging."""
        ...


@runtime_checkable
class IMUDriver(Protocol):
    """Protocol for inertial measurement unit drivers."""

    def read_acceleration(self) -> tuple[float, float, float]:
        """Read accelerometer (x, y, z) in g."""
        ...

    def read_gyroscope(self) -> tuple[float, float, float]:
        """Read gyroscope (x, y, z) in degrees/second."""
        ...

    def read_temperature(self) -> float:
        """Read die temperature in Celsius."""
        ...


@runtime_checkable
class ToFDriver(Protocol):
    """Protocol for Time-of-Flight distance sensors."""

    resolution: int  # Number of zones (16 or 64)

    def get_distance_mm(self) -> int:
        """Get closest detected distance in mm."""
        ...

    def get_distance_map(self) -> list[int]:
        """Get distance for each zone."""
        ...


@runtime_checkable
class EnvironmentDriver(Protocol):
    """Protocol for environmental sensors."""

    def read_temperature(self) -> float:
        """Read ambient temperature in Celsius."""
        ...

    def read_humidity(self) -> float:
        """Read relative humidity (0-100%)."""
        ...


@runtime_checkable
class NPUDriver(Protocol):
    """Protocol for neural processing unit drivers."""

    def load_model(self, model_path: str) -> bool:
        """Load a model file."""
        ...

    def infer(self, input_data: Any) -> Any:
        """Run inference on input data."""
        ...

    def get_utilization(self) -> float:
        """Get NPU utilization (0.0-1.0)."""
        ...


@runtime_checkable
class CellularDriver(Protocol):
    """Protocol for cellular modem drivers."""

    def connect(self) -> bool:
        """Establish data connection."""
        ...

    def disconnect(self) -> None:
        """Disconnect from network."""
        ...

    def is_connected(self) -> bool:
        """Check connection status."""
        ...

    def get_signal_strength(self) -> int:
        """Get signal strength (0-5 bars)."""
        ...


@runtime_checkable
class GNSSDriver(Protocol):
    """Protocol for GNSS/GPS receivers."""

    def get_position(self) -> tuple[float, float, float] | None:
        """Get (latitude, longitude, altitude) or None if no fix."""
        ...

    def get_satellites(self) -> int:
        """Get number of satellites in view."""
        ...

    def has_fix(self) -> bool:
        """Check if position fix is available."""
        ...


# =============================================================================
# HAL CAPABILITY FLAGS
# =============================================================================


class HardwareCapability(Enum):
    """Flags indicating available hardware capabilities."""

    LED_RING = auto()
    BATTERY = auto()
    CHARGING = auto()
    IMU = auto()
    TOF = auto()
    TEMPERATURE = auto()
    HUMIDITY = auto()
    NPU = auto()
    CELLULAR = auto()
    GNSS = auto()
    WIFI = auto()
    BLUETOOTH = auto()
    AUDIO_INPUT = auto()
    AUDIO_OUTPUT = auto()
    CAMERA = auto()


@dataclass
class HardwareCapabilities:
    """Hardware capability manifest for the platform."""

    platform: str
    capabilities: set[HardwareCapability]

    @classmethod
    def qcs6490(cls) -> "HardwareCapabilities":
        """Create capability manifest for QCS6490 SoM."""
        return cls(
            platform="QCS6490",
            capabilities={
                HardwareCapability.LED_RING,
                HardwareCapability.BATTERY,
                HardwareCapability.CHARGING,
                HardwareCapability.IMU,
                HardwareCapability.TOF,
                HardwareCapability.TEMPERATURE,
                HardwareCapability.HUMIDITY,
                HardwareCapability.NPU,
                HardwareCapability.CELLULAR,
                HardwareCapability.GNSS,
                HardwareCapability.WIFI,
                HardwareCapability.BLUETOOTH,
                HardwareCapability.AUDIO_INPUT,
                HardwareCapability.AUDIO_OUTPUT,
                HardwareCapability.CAMERA,
            },
        )

    @classmethod
    def simulation(cls) -> "HardwareCapabilities":
        """Create capability manifest for simulation mode."""
        return cls(
            platform="Simulation",
            capabilities=set(HardwareCapability),  # All capabilities
        )

    def has(self, cap: HardwareCapability) -> bool:
        """Check if capability is available."""
        return cap in self.capabilities


# =============================================================================
# HAL ERRORS
# =============================================================================


class HALError(Exception):
    """Base exception for HAL errors."""

    pass


class HardwareNotInitializedError(HALError):
    """Raised when accessing uninitialized hardware."""

    pass


class HardwareNotAvailableError(HALError):
    """Raised when hardware is not present."""

    pass


class HardwareCommunicationError(HALError):
    """Raised on I2C/SPI/Serial communication failure."""

    pass


class HardwareTimeoutError(HALError):
    """Raised when hardware operation times out."""

    pass


# =============================================================================
# HAL VALIDATION
# =============================================================================


def validate_driver(driver: Any, protocol: type) -> bool:
    """
    Validate that a driver implements the required protocol.

    Args:
        driver: Driver instance to validate
        protocol: Protocol class to check against

    Returns:
        True if driver implements protocol
    """
    return isinstance(driver, protocol)


def validate_hal_interface(orb_system: Any) -> list[str]:
    """
    Validate that an OrbSystem has all required HAL components.

    Args:
        orb_system: OrbSystem instance to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required subsystems exist
    required = ["led", "power", "sensors", "npu", "cellular", "gnss", "location"]
    for subsystem in required:
        if not hasattr(orb_system, subsystem):
            errors.append(f"Missing required subsystem: {subsystem}")

    # Check all implement HardwareDriver base
    for subsystem in ["led", "npu", "cellular", "gnss"]:
        if hasattr(orb_system, subsystem):
            driver = getattr(orb_system, subsystem)
            if not hasattr(driver, "is_initialized"):
                errors.append(f"{subsystem} missing is_initialized()")
            if not hasattr(driver, "simulate"):
                errors.append(f"{subsystem} missing simulate attribute")

    return errors


# =============================================================================
# HAL CONSTANTS
# =============================================================================


# I2C Addresses (7-bit)
class I2CAddress:
    """Standard I2C addresses for orb components."""

    BQ25895_CHARGER = 0x6A
    BQ40Z50_FUEL_GAUGE = 0x0B
    ICM45686_IMU = 0x68  # AD0=LOW
    ICM45686_IMU_ALT = 0x69  # AD0=HIGH
    VL53L8CX_TOF = 0x29
    SHT45_TEMP_HUMIDITY = 0x44
    MCP4725_DAC = 0x60


# SPI Configuration
class SPIConfig:
    """Standard SPI configuration."""

    LED_MAX_SPEED_HZ = 20_000_000  # 20 MHz for HD108
    MODE = 0  # CPOL=0, CPHA=0


# GPIO Pins (QCS6490 GPIO numbering)
class GPIOPin:
    """GPIO pin assignments for orb."""

    LED_SPI_CLK = 0
    LED_SPI_MOSI = 1
    IMU_INT1 = 10
    IMU_INT2 = 11
    TOF_INT = 12
    CHARGER_INT = 13
    FUEL_GAUGE_ALRT = 14
    GNSS_PPS = 15


__all__ = [
    "CellularDriver",
    "EnvironmentDriver",
    "GNSSDriver",
    "GPIOPin",
    # Errors
    "HALError",
    "HardwareCapabilities",
    # Capabilities
    "HardwareCapability",
    "HardwareCommunicationError",
    # Protocols
    "HardwareDriver",
    "HardwareNotAvailableError",
    "HardwareNotInitializedError",
    "HardwareTimeoutError",
    # Constants
    "I2CAddress",
    "IMUDriver",
    "LEDDriver",
    "NPUDriver",
    "PowerDriver",
    "SPIConfig",
    "ToFDriver",
    # Validation
    "validate_driver",
    "validate_hal_interface",
]
