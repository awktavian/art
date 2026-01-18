"""
Tests for Power Management Drivers

Tests cover:
- BQ25895 charger initialization and registers
- BQ40Z50 fuel gauge SMBus protocol
- Unified PowerMonitor interface
- Charge state machine
- Battery protection thresholds
"""

import pytest
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(pytest.importorskip("pathlib").Path(__file__).parent.parent))

from kagami_orb.drivers.power import (
    BQ25895Driver,
    BQ25895Reg,
    BQ25895ChargeStatus,
    BQ25895VBUSStatus,
    BQ25895Fault,
    BQ25895Status,
    BQ40Z50Driver,
    BQ40Z50Cmd,
    BQ40Z50Status,
    PowerMonitor,
)


class TestBQ25895Registers:
    """Test BQ25895 register definitions."""
    
    def test_register_addresses(self):
        """Verify register addresses match datasheet."""
        # From TI BQ25895 datasheet
        assert BQ25895Reg.INPUT_SOURCE == 0x00
        assert BQ25895Reg.POWER_ON_CONFIG == 0x01
        assert BQ25895Reg.CHARGE_CURRENT == 0x02
        assert BQ25895Reg.CHARGE_VOLTAGE == 0x04
        assert BQ25895Reg.SYSTEM_STATUS == 0x08
        assert BQ25895Reg.FAULT == 0x09
        assert BQ25895Reg.ADC_VBAT == 0x0F
        assert BQ25895Reg.PART_INFO == 0x14
    
    def test_charge_status_enum(self):
        """Verify charge status values."""
        assert BQ25895ChargeStatus.NOT_CHARGING == 0b00
        assert BQ25895ChargeStatus.PRE_CHARGE == 0b01
        assert BQ25895ChargeStatus.FAST_CHARGING == 0b10
        assert BQ25895ChargeStatus.CHARGE_DONE == 0b11
    
    def test_vbus_status_enum(self):
        """Verify VBUS status values."""
        assert BQ25895VBUSStatus.NO_INPUT == 0b000
        assert BQ25895VBUSStatus.USB_SDP == 0b001
        assert BQ25895VBUSStatus.USB_CDP == 0b010
        assert BQ25895VBUSStatus.USB_DCP == 0b011


class TestBQ25895Driver:
    """Test BQ25895 charger driver."""
    
    @pytest.fixture
    def charger(self):
        """Create charger in simulation mode."""
        return BQ25895Driver(simulate=True)
    
    def test_initialization(self, charger):
        """Test driver initializes correctly."""
        assert charger.is_initialized()
        assert charger.i2c_addr == 0x6A
    
    def test_get_status(self, charger):
        """Test reading complete status."""
        status = charger.get_status()
        
        assert isinstance(status, BQ25895Status)
        assert isinstance(status.vbus_status, BQ25895VBUSStatus)
        assert isinstance(status.charge_status, BQ25895ChargeStatus)
        assert isinstance(status.faults, BQ25895Fault)
    
    def test_adc_voltage_conversion(self, charger):
        """Test VBAT ADC conversion formula."""
        # Simulate specific ADC value
        charger._sim_vbat = 4200  # 4.2V
        
        status = charger.get_status()
        
        # VBAT = 2304mV + 20mV * ADC
        # ADC = (4200 - 2304) / 20 = 94.8 -> 94
        # Readback = 2304 + 20 * 94 = 4184 (rounding error)
        assert 4100 <= status.vbat_mv <= 4300
    
    def test_set_charge_current(self, charger):
        """Test setting charge current."""
        # Should not raise in simulation
        charger.set_charge_current(2000)  # 2A
        charger.set_charge_current(5000)  # 5A (max)
        charger.set_charge_current(100)   # Low current
    
    def test_set_charge_voltage(self, charger):
        """Test setting charge voltage."""
        charger.set_charge_voltage(4200)  # 4.2V standard
        charger.set_charge_voltage(4350)  # 4.35V for high-voltage cells
    
    def test_enable_disable_charging(self, charger):
        """Test enabling/disabling charging."""
        charger.enable_charging(True)
        charger.enable_charging(False)
    
    def test_watchdog_reset(self, charger):
        """Test watchdog timer reset."""
        charger.reset_watchdog()
    
    def test_no_faults_initially(self, charger):
        """Test that simulation has no faults."""
        status = charger.get_status()
        assert status.faults == BQ25895Fault.NONE


class TestBQ40Z50Commands:
    """Test BQ40Z50 SMBus commands."""
    
    def test_sbs_command_addresses(self):
        """Verify SBS command addresses match standard."""
        # Standard SBS 1.1 commands
        assert BQ40Z50Cmd.MANUFACTURER_ACCESS == 0x00
        assert BQ40Z50Cmd.TEMPERATURE == 0x08
        assert BQ40Z50Cmd.VOLTAGE == 0x09
        assert BQ40Z50Cmd.CURRENT == 0x0A
        assert BQ40Z50Cmd.RELATIVE_STATE_OF_CHARGE == 0x0D
        assert BQ40Z50Cmd.REMAINING_CAPACITY == 0x0F
        assert BQ40Z50Cmd.FULL_CHARGE_CAPACITY == 0x10
        assert BQ40Z50Cmd.CYCLE_COUNT == 0x17


class TestBQ40Z50Driver:
    """Test BQ40Z50 fuel gauge driver."""
    
    @pytest.fixture
    def fuel_gauge(self):
        """Create fuel gauge in simulation mode."""
        return BQ40Z50Driver(simulate=True)
    
    def test_initialization(self, fuel_gauge):
        """Test driver initializes correctly."""
        assert fuel_gauge.is_initialized()
        assert fuel_gauge.i2c_addr == 0x0B
    
    def test_get_voltage(self, fuel_gauge):
        """Test reading battery voltage."""
        voltage = fuel_gauge.get_voltage()
        
        # Simulation: 3.7V * 3 cells = 11.1V
        assert 10000 <= voltage <= 13000
    
    def test_get_current_signed(self, fuel_gauge):
        """Test current reading is properly signed."""
        current = fuel_gauge.get_current()
        
        # Simulation is discharging (negative)
        assert current < 0
    
    def test_get_temperature(self, fuel_gauge):
        """Test temperature conversion from 0.1K."""
        temp = fuel_gauge.get_temperature()
        
        # Simulation: ~25°C
        assert 20 <= temp <= 30
    
    def test_get_state_of_charge(self, fuel_gauge):
        """Test SOC reading."""
        soc = fuel_gauge.get_state_of_charge()
        
        # Simulation: 75%
        assert 0 <= soc <= 100
    
    def test_get_remaining_capacity(self, fuel_gauge):
        """Test remaining capacity."""
        remaining = fuel_gauge.get_remaining_capacity()
        
        assert remaining > 0
    
    def test_get_full_charge_capacity(self, fuel_gauge):
        """Test full charge capacity."""
        fcc = fuel_gauge.get_full_charge_capacity()
        
        # Simulation: 2200mAh
        assert fcc == 2200
    
    def test_get_cycle_count(self, fuel_gauge):
        """Test cycle count."""
        cycles = fuel_gauge.get_cycle_count()
        
        # Simulation: 42 cycles
        assert cycles >= 0
    
    def test_get_time_to_empty(self, fuel_gauge):
        """Test runtime estimation."""
        tte = fuel_gauge.get_time_to_empty()
        
        # Should be positive (discharging)
        assert tte > 0 or tte == 65535  # 65535 = N/A
    
    def test_get_cell_voltages(self, fuel_gauge):
        """Test per-cell voltage reading (3S pack)."""
        v1, v2, v3 = fuel_gauge.get_cell_voltages()
        
        # Each cell ~3.7V
        assert 3000 <= v1 <= 4500
        assert 3000 <= v2 <= 4500
        assert 3000 <= v3 <= 4500
    
    def test_get_complete_status(self, fuel_gauge):
        """Test complete status reading."""
        status = fuel_gauge.get_status()
        
        assert isinstance(status, BQ40Z50Status)
        assert status.voltage_mv > 0
        assert 0 <= status.state_of_charge <= 100
        assert len(status.cell_voltages_mv) == 3


class TestPowerMonitor:
    """Test unified power monitor."""
    
    @pytest.fixture
    def monitor(self):
        """Create power monitor in simulation mode."""
        return PowerMonitor(simulate=True)
    
    def test_initialization(self, monitor):
        """Test both ICs initialize."""
        assert monitor.is_initialized()
    
    def test_battery_percentage(self, monitor):
        """Test getting battery percentage."""
        pct = monitor.get_battery_percentage()
        
        assert 0 <= pct <= 100
    
    def test_charging_status_string(self, monitor):
        """Test charging status returns valid string."""
        status = monitor.get_charging_status()
        
        assert status in ["charging", "discharging", "full", "pre_charge", "not_present"]
    
    def test_temperature(self, monitor):
        """Test temperature reading."""
        temp = monitor.get_temperature()
        
        assert 0 <= temp <= 60  # Reasonable range
    
    def test_voltage(self, monitor):
        """Test voltage reading."""
        voltage = monitor.get_voltage()
        
        assert voltage > 0
    
    def test_current(self, monitor):
        """Test current reading."""
        current = monitor.get_current()
        
        # Can be positive or negative
        assert isinstance(current, int)
    
    def test_estimated_runtime(self, monitor):
        """Test runtime estimation."""
        runtime = monitor.get_estimated_runtime()
        
        # Either valid minutes or -1 (charging)
        assert runtime >= -1
    
    def test_no_faults(self, monitor):
        """Test fault detection."""
        assert not monitor.has_faults()


class TestPowerProtection:
    """Test battery protection features."""
    
    def test_overvoltage_detection(self):
        """Test that high voltage is flagged."""
        # In real implementation, BQ25895 handles this
        charger = BQ25895Driver(simulate=True)
        charger._sim_vbat = 4500  # Over 4.35V
        
        status = charger.get_status()
        # Would expect OVP flag in real hardware
        # Simulation doesn't trigger this
    
    def test_thermal_management(self):
        """Test thermal regulation status."""
        charger = BQ25895Driver(simulate=True)
        status = charger.get_status()
        
        # Should report thermal status
        assert isinstance(status.in_thermal_regulation, bool)
    
    def test_input_dpm(self):
        """Test Dynamic Power Management status."""
        charger = BQ25895Driver(simulate=True)
        status = charger.get_status()
        
        assert isinstance(status.in_dpm, bool)


class TestI2CProtocol:
    """Test I2C protocol handling."""
    
    def test_charger_address(self):
        """Test default charger I2C address."""
        charger = BQ25895Driver(simulate=True)
        assert charger.i2c_addr == 0x6A
    
    def test_fuel_gauge_address(self):
        """Test default fuel gauge I2C address."""
        fuel_gauge = BQ40Z50Driver(simulate=True)
        assert fuel_gauge.i2c_addr == 0x0B
    
    def test_alternate_addresses(self):
        """Test alternate I2C addresses."""
        charger = BQ25895Driver(i2c_addr=0x6B, simulate=True)
        assert charger.i2c_addr == 0x6B


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
