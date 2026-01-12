"""
Tests for HAL (Hardware Abstraction Layer) protocols and validation.

Tests the HAL interface contracts, capability detection, and validation utilities.
"""

import pytest

from kagami_orb import (
    OrbSystem,
    # HAL Protocols
    HardwareCapability,
    HardwareCapabilities,
    # HAL Errors
    HALError,
    HardwareNotInitializedError,
    HardwareNotAvailableError,
    HardwareCommunicationError,
    HardwareTimeoutError,
    # HAL Utilities
    validate_hal_interface,
    I2CAddress,
    SPIConfig,
    GPIOPin,
)


class TestHALCapabilities:
    """Test hardware capability detection."""

    def test_qcs6490_capabilities(self):
        """Test QCS6490 platform has expected capabilities."""
        caps = HardwareCapabilities.qcs6490()

        assert caps.platform == "QCS6490"
        assert caps.has(HardwareCapability.LED_RING)
        assert caps.has(HardwareCapability.BATTERY)
        assert caps.has(HardwareCapability.NPU)
        assert caps.has(HardwareCapability.CELLULAR)
        assert caps.has(HardwareCapability.GNSS)

    def test_simulation_capabilities(self):
        """Test simulation mode has all capabilities."""
        caps = HardwareCapabilities.simulation()

        assert caps.platform == "Simulation"
        # Should have ALL capabilities
        for cap in HardwareCapability:
            assert caps.has(cap), f"Missing capability: {cap}"


class TestHALValidation:
    """Test HAL validation utilities."""

    @pytest.fixture
    def orb_system(self):
        """Create OrbSystem for testing."""
        return OrbSystem(simulate=True)

    def test_validate_hal_interface_passes(self, orb_system):
        """Test HAL validation passes for valid system."""
        errors = validate_hal_interface(orb_system)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_validate_driver_led(self, orb_system):
        """Test LED driver implements protocol."""
        # LED driver should have required attributes
        assert hasattr(orb_system.led, "num_leds")
        assert hasattr(orb_system.led, "max_brightness")
        assert hasattr(orb_system.led, "set_led")
        assert hasattr(orb_system.led, "set_all")
        assert hasattr(orb_system.led, "clear")
        assert hasattr(orb_system.led, "show")

    def test_validate_driver_simulation_flag(self, orb_system):
        """Test all drivers have simulate attribute."""
        assert hasattr(orb_system.led, "simulate")
        assert hasattr(orb_system.npu, "simulate")
        assert hasattr(orb_system.cellular, "simulate")
        assert hasattr(orb_system.gnss, "simulate")

        # Should all be True in simulation mode
        assert orb_system.led.simulate is True
        assert orb_system.npu.simulate is True
        assert orb_system.cellular.simulate is True
        assert orb_system.gnss.simulate is True


class TestHALErrors:
    """Test HAL error hierarchy."""

    def test_hal_error_base(self):
        """Test HALError is base class."""
        assert issubclass(HardwareNotInitializedError, HALError)
        assert issubclass(HardwareNotAvailableError, HALError)
        assert issubclass(HardwareCommunicationError, HALError)
        assert issubclass(HardwareTimeoutError, HALError)

    def test_hal_error_catchable(self):
        """Test HAL errors can be caught."""
        try:
            raise HardwareNotInitializedError("Test error")
        except HALError as e:
            assert "Test error" in str(e)

    def test_hal_error_specific(self):
        """Test specific HAL errors."""
        with pytest.raises(HardwareNotInitializedError):
            raise HardwareNotInitializedError("LED not ready")

        with pytest.raises(HardwareCommunicationError):
            raise HardwareCommunicationError("I2C NACK")

        with pytest.raises(HardwareTimeoutError):
            raise HardwareTimeoutError("SPI timeout")


class TestHALConstants:
    """Test HAL constants are correct."""

    def test_i2c_addresses(self):
        """Test I2C addresses match datasheets."""
        assert I2CAddress.BQ25895_CHARGER == 0x6A
        assert I2CAddress.BQ40Z50_FUEL_GAUGE == 0x0B
        assert I2CAddress.ICM45686_IMU == 0x68
        assert I2CAddress.VL53L8CX_TOF == 0x29
        assert I2CAddress.SHT45_TEMP_HUMIDITY == 0x44

    def test_spi_config(self):
        """Test SPI configuration values."""
        assert SPIConfig.LED_MAX_SPEED_HZ == 20_000_000
        assert SPIConfig.MODE == 0

    def test_gpio_pins_defined(self):
        """Test GPIO pins are defined."""
        assert hasattr(GPIOPin, "LED_SPI_CLK")
        assert hasattr(GPIOPin, "LED_SPI_MOSI")
        assert hasattr(GPIOPin, "IMU_INT1")


class TestOrbSystemHALCompliance:
    """Test OrbSystem follows HAL patterns."""

    @pytest.fixture
    def orb(self):
        """Create OrbSystem."""
        return OrbSystem(simulate=True)

    def test_subsystem_initialization(self, orb):
        """Test all subsystems initialize correctly."""
        assert orb.led.is_initialized()
        assert orb.sensors.is_initialized()
        assert orb.npu.is_initialized()
        # Cellular and GNSS might need explicit init

    def test_simulation_mode_propagates(self, orb):
        """Test simulation mode is consistent across subsystems."""
        assert orb.simulate is True
        assert orb.led.simulate is True
        assert orb.sensors.imu.simulate is True
        assert orb.sensors.tof.simulate is True
        assert orb.sensors.env.simulate is True

    def test_get_state_works(self, orb):
        """Test get_state returns valid snapshot."""
        state = orb.get_state()

        assert state.timestamp is not None
        assert 0 <= state.battery_percent <= 100
        assert isinstance(state.is_charging, bool)
        assert isinstance(state.temperature_c, float)
        assert isinstance(state.humidity_pct, float)


class TestHALProtocolConformance:
    """Test drivers conform to HAL protocols."""

    def test_hardware_driver_protocol(self):
        """Test HardwareDriver protocol requirements."""
        orb = OrbSystem(simulate=True)

        # Check LED driver
        assert hasattr(orb.led, "simulate")
        assert hasattr(orb.led, "is_initialized")
        assert callable(orb.led.is_initialized)

        # Check NPU driver
        assert hasattr(orb.npu, "simulate")
        assert hasattr(orb.npu, "is_initialized")
        assert callable(orb.npu.close)

    def test_led_driver_protocol(self):
        """Test LEDDriver protocol methods exist."""
        orb = OrbSystem(simulate=True)

        assert hasattr(orb.led, "num_leds")
        assert hasattr(orb.led, "max_brightness")
        assert callable(orb.led.set_led)
        assert callable(orb.led.set_all)
        assert callable(orb.led.clear)
        assert callable(orb.led.show)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
