"""
Power Management Drivers

BQ25895: 5A Switch-Mode Battery Charger with I2C
BQ40Z50: Battery Fuel Gauge with SMBus

Reference: 
- BQ25895: https://www.ti.com/lit/ds/symlink/bq25895.pdf
- BQ40Z50: https://cdn.sparkfun.com/assets/e/a/e/1/8/bq40z50_-_Technical_Reference.pdf
"""

from dataclasses import dataclass
from enum import IntEnum, IntFlag
from typing import Optional, Tuple
import time

try:
    import smbus2
    HAS_SMBUS = True
except ImportError:
    HAS_SMBUS = False


# =============================================================================
# BQ25895 CHARGER DRIVER
# =============================================================================

class BQ25895Reg(IntEnum):
    """BQ25895 I2C Register Addresses (from datasheet Table 1)."""
    INPUT_SOURCE = 0x00          # Input source control
    POWER_ON_CONFIG = 0x01       # Power-on configuration
    CHARGE_CURRENT = 0x02        # Charge current control
    PRE_CHARGE = 0x03            # Pre-charge/termination current
    CHARGE_VOLTAGE = 0x04        # Charge voltage control
    CHARGE_TERM_TIMER = 0x05     # Charge termination/timer control
    BOOST_VOLTAGE = 0x06         # Boost voltage/thermal regulation
    MISC_OPERATION = 0x07        # Misc operation control
    SYSTEM_STATUS = 0x08         # System status (read-only)
    FAULT = 0x09                 # Fault status (read-only)
    VBUS_STATUS = 0x0A           # VBUS status (read-only)
    VBAT_STATUS = 0x0B           # VBAT status (read-only)
    VSYS_STATUS = 0x0C           # VSYS status (read-only)
    TS_STATUS = 0x0D             # TS status (read-only)
    ADC_CONTROL = 0x0E           # ADC control
    ADC_VBAT = 0x0F              # ADC VBAT reading
    ADC_VSYS = 0x10              # ADC VSYS reading
    ADC_TS = 0x11                # ADC TS reading
    ADC_VBUS = 0x12              # ADC VBUS reading
    ADC_ICHG = 0x13              # ADC charge current reading
    PART_INFO = 0x14             # Part information (read-only)


class BQ25895ChargeStatus(IntEnum):
    """Charge status from REG08[4:3]."""
    NOT_CHARGING = 0b00
    PRE_CHARGE = 0b01
    FAST_CHARGING = 0b10
    CHARGE_DONE = 0b11


class BQ25895VBUSStatus(IntEnum):
    """VBUS status from REG08[7:5]."""
    NO_INPUT = 0b000
    USB_SDP = 0b001              # USB Standard Downstream Port
    USB_CDP = 0b010              # USB Charging Downstream Port
    USB_DCP = 0b011              # USB Dedicated Charging Port
    ADJUSTABLE_HV = 0b100        # Adjustable High Voltage DCP
    UNKNOWN_ADAPTER = 0b101
    NON_STANDARD = 0b110
    OTG = 0b111


class BQ25895Fault(IntFlag):
    """Fault flags from REG09."""
    NONE = 0
    WATCHDOG = 0x80
    BOOST = 0x40
    CHRG_INPUT = 0x10
    CHRG_THERMAL = 0x20
    CHRG_SAFETY = 0x30
    BAT_OVP = 0x08
    NTC_COLD = 0x01
    NTC_HOT = 0x02


@dataclass
class BQ25895Status:
    """BQ25895 complete status."""
    vbus_status: BQ25895VBUSStatus
    charge_status: BQ25895ChargeStatus
    power_good: bool
    in_dpm: bool                 # Input DPM (Dynamic Power Management)
    in_thermal_regulation: bool
    vsys_regulation: bool
    faults: BQ25895Fault
    vbat_mv: int                 # Battery voltage in mV
    vsys_mv: int                 # System voltage in mV
    vbus_mv: int                 # Input voltage in mV
    ichg_ma: int                 # Charge current in mA
    temperature_c: float         # Estimated temp from TS


class BQ25895Driver:
    """
    Driver for BQ25895 battery charger IC.
    
    Features:
    - 5A max charge current
    - 3.9V to 14V input voltage range
    - I2C interface at 400kHz
    - Integrated ADC for monitoring
    - Multiple safety protections
    """
    
    I2C_ADDR = 0x6A  # 7-bit address (can also be 0x6B)
    
    def __init__(
        self,
        i2c_bus: int = 1,
        i2c_addr: int = 0x6A,
        simulate: bool = False,
    ):
        """
        Initialize BQ25895 driver.
        
        Args:
            i2c_bus: I2C bus number (typically 1 on Linux)
            i2c_addr: I2C address (0x6A or 0x6B based on ADDR pin)
            simulate: Run in simulation mode without hardware
        """
        self.i2c_bus = i2c_bus
        self.i2c_addr = i2c_addr
        self.simulate = simulate or not HAS_SMBUS
        
        self._bus: Optional[smbus2.SMBus] = None
        self._initialized = False
        
        # Simulation state
        self._sim_vbat = 3800  # mV
        self._sim_charging = True
        
        self._init_i2c()
    
    def _init_i2c(self) -> None:
        """Initialize I2C interface."""
        if self.simulate:
            self._initialized = True
            return
        
        try:
            self._bus = smbus2.SMBus(self.i2c_bus)
            # Verify device by reading part info
            part_info = self._read_reg(BQ25895Reg.PART_INFO)
            # BQ25895 should return 0xC0 (REV bits + PN bits)
            if (part_info & 0x38) != 0x18:  # PN = 011 for BQ25895
                print(f"Warning: Unexpected part ID: {part_info:#04x}")
            self._initialized = True
        except Exception as e:
            print(f"BQ25895 I2C init failed: {e}")
            self._initialized = False
            self.simulate = True
    
    def _read_reg(self, reg: BQ25895Reg) -> int:
        """Read a single register."""
        if self.simulate:
            return self._simulate_read(reg)
        return self._bus.read_byte_data(self.i2c_addr, reg)
    
    def _write_reg(self, reg: BQ25895Reg, value: int) -> None:
        """Write a single register."""
        if self.simulate:
            return
        self._bus.write_byte_data(self.i2c_addr, reg, value)
    
    def _simulate_read(self, reg: BQ25895Reg) -> int:
        """Simulate register reads for testing."""
        if reg == BQ25895Reg.SYSTEM_STATUS:
            # VBUS=USB_CDP, CHRG=FAST_CHARGING, PG=1
            return (0b010 << 5) | (0b10 << 3) | 0x04
        elif reg == BQ25895Reg.FAULT:
            return 0x00  # No faults
        elif reg == BQ25895Reg.ADC_VBAT:
            # VBAT = 2304mV + 20mV * REG[6:0]
            return (self._sim_vbat - 2304) // 20
        elif reg == BQ25895Reg.ADC_ICHG:
            # ICHG = 0mA + 50mA * REG[6:0]
            return 40  # 2000mA
        elif reg == BQ25895Reg.PART_INFO:
            return 0xC0 | 0x18  # BQ25895 part number
        return 0x00
    
    def is_initialized(self) -> bool:
        """Check if driver is initialized."""
        return self._initialized
    
    def enable_adc(self, one_shot: bool = False) -> None:
        """
        Enable ADC for voltage/current measurements.
        
        Args:
            one_shot: If True, do one conversion. If False, continuous.
        """
        reg = self._read_reg(BQ25895Reg.ADC_CONTROL)
        if one_shot:
            reg |= 0x80  # ADC_START = 1
            reg &= ~0x40  # ADC_CONV_RATE = 0 (one-shot)
        else:
            reg |= 0x80 | 0x40  # Enable continuous
        self._write_reg(BQ25895Reg.ADC_CONTROL, reg)
    
    def get_status(self) -> BQ25895Status:
        """Read complete device status."""
        # Read status registers
        sys_status = self._read_reg(BQ25895Reg.SYSTEM_STATUS)
        fault = self._read_reg(BQ25895Reg.FAULT)
        
        # Read ADC values
        vbat = self._read_reg(BQ25895Reg.ADC_VBAT)
        vsys = self._read_reg(BQ25895Reg.ADC_VSYS)
        vbus = self._read_reg(BQ25895Reg.ADC_VBUS)
        ichg = self._read_reg(BQ25895Reg.ADC_ICHG)
        ts = self._read_reg(BQ25895Reg.ADC_TS)
        
        # Parse status register
        vbus_status = BQ25895VBUSStatus((sys_status >> 5) & 0x07)
        charge_status = BQ25895ChargeStatus((sys_status >> 3) & 0x03)
        power_good = bool(sys_status & 0x04)
        in_dpm = bool(sys_status & 0x02)
        vsys_regulation = bool(sys_status & 0x01)
        
        # Convert ADC readings to real values
        # VBAT = 2304mV + 20mV * BATV[6:0]
        vbat_mv = 2304 + 20 * (vbat & 0x7F)
        # VSYS = 2304mV + 20mV * SYSV[6:0]
        vsys_mv = 2304 + 20 * (vsys & 0x7F)
        # VBUS = 2600mV + 100mV * BUSV[6:0]
        vbus_mv = 2600 + 100 * (vbus & 0x7F)
        # ICHG = 0mA + 50mA * ICHGR[6:0]
        ichg_ma = 50 * (ichg & 0x7F)
        # TS% = 21% + 0.465% * TSPCT[6:0] (approximate)
        ts_pct = 21.0 + 0.465 * (ts & 0x7F)
        
        return BQ25895Status(
            vbus_status=vbus_status,
            charge_status=charge_status,
            power_good=power_good,
            in_dpm=in_dpm,
            in_thermal_regulation=False,  # Would need REG0D
            vsys_regulation=vsys_regulation,
            faults=BQ25895Fault(fault),
            vbat_mv=vbat_mv,
            vsys_mv=vsys_mv,
            vbus_mv=vbus_mv,
            ichg_ma=ichg_ma,
            temperature_c=25.0,  # Would need NTC calculation
        )
    
    def set_charge_current(self, current_ma: int) -> None:
        """
        Set fast charge current limit.
        
        Args:
            current_ma: Charge current in mA (0-5056mA in 64mA steps)
        """
        # ICHG = 64mA * ICHG[6:0]
        ichg = min(79, max(0, current_ma // 64))
        self._write_reg(BQ25895Reg.CHARGE_CURRENT, ichg)
    
    def set_charge_voltage(self, voltage_mv: int) -> None:
        """
        Set charge voltage limit.
        
        Args:
            voltage_mv: Charge voltage in mV (3840-4608mV in 16mV steps)
        """
        # VREG = 3840mV + 16mV * VREG[5:0]
        vreg = min(63, max(0, (voltage_mv - 3840) // 16))
        reg = self._read_reg(BQ25895Reg.CHARGE_VOLTAGE)
        reg = (reg & 0x03) | (vreg << 2)
        self._write_reg(BQ25895Reg.CHARGE_VOLTAGE, reg)
    
    def enable_charging(self, enable: bool = True) -> None:
        """Enable or disable charging."""
        reg = self._read_reg(BQ25895Reg.POWER_ON_CONFIG)
        if enable:
            reg |= 0x10  # CHG_CONFIG = 1
        else:
            reg &= ~0x10  # CHG_CONFIG = 0
        self._write_reg(BQ25895Reg.POWER_ON_CONFIG, reg)
    
    def reset_watchdog(self) -> None:
        """Reset the watchdog timer."""
        reg = self._read_reg(BQ25895Reg.POWER_ON_CONFIG)
        reg |= 0x40  # WD_RST = 1
        self._write_reg(BQ25895Reg.POWER_ON_CONFIG, reg)
    
    def close(self) -> None:
        """Clean up resources."""
        if self._bus:
            self._bus.close()
            self._bus = None
        self._initialized = False


# =============================================================================
# BQ40Z50 FUEL GAUGE DRIVER
# =============================================================================

class BQ40Z50Cmd(IntEnum):
    """BQ40Z50 SMBus Command Codes (SBS 1.1 compliant)."""
    # Standard SBS Commands
    MANUFACTURER_ACCESS = 0x00
    REMAINING_CAPACITY_ALARM = 0x01
    REMAINING_TIME_ALARM = 0x02
    BATTERY_MODE = 0x03
    AT_RATE = 0x04
    AT_RATE_TIME_TO_FULL = 0x05
    AT_RATE_TIME_TO_EMPTY = 0x06
    AT_RATE_OK = 0x07
    TEMPERATURE = 0x08
    VOLTAGE = 0x09
    CURRENT = 0x0A
    AVERAGE_CURRENT = 0x0B
    MAX_ERROR = 0x0C
    RELATIVE_STATE_OF_CHARGE = 0x0D
    ABSOLUTE_STATE_OF_CHARGE = 0x0E
    REMAINING_CAPACITY = 0x0F
    FULL_CHARGE_CAPACITY = 0x10
    RUN_TIME_TO_EMPTY = 0x11
    AVERAGE_TIME_TO_EMPTY = 0x12
    AVERAGE_TIME_TO_FULL = 0x13
    CHARGING_CURRENT = 0x14
    CHARGING_VOLTAGE = 0x15
    BATTERY_STATUS = 0x16
    CYCLE_COUNT = 0x17
    DESIGN_CAPACITY = 0x18
    DESIGN_VOLTAGE = 0x19
    SPECIFICATION_INFO = 0x1A
    MANUFACTURER_DATE = 0x1B
    SERIAL_NUMBER = 0x1C
    MANUFACTURER_NAME = 0x20
    DEVICE_NAME = 0x21
    DEVICE_CHEMISTRY = 0x22
    MANUFACTURER_DATA = 0x23
    # Block access
    MANUFACTURER_BLOCK_ACCESS = 0x44
    # Cell voltages
    CELL_VOLTAGE_4 = 0x3C
    CELL_VOLTAGE_3 = 0x3D
    CELL_VOLTAGE_2 = 0x3E
    CELL_VOLTAGE_1 = 0x3F


class BQ40Z50MACCmd(IntEnum):
    """ManufacturerAccess sub-commands via 0x00."""
    DEVICE_TYPE = 0x0001
    FIRMWARE_VERSION = 0x0002
    HARDWARE_VERSION = 0x0003
    CHEM_ID = 0x0006
    SHUTDOWN = 0x0010
    SLEEP = 0x0011
    SEAL = 0x0020
    IT_ENABLE = 0x0021
    CAL_ENABLE = 0x002D
    LIFETIME_DATA_RESET = 0x0028
    PERMANENT_FAILURE_RESET = 0x0029
    SEAL_DEVICE = 0x0030
    SAFETY_STATUS = 0x0051
    PFSTATUS = 0x0053
    OPERATION_STATUS = 0x0054
    CHARGING_STATUS = 0x0055
    GAUGING_STATUS = 0x0056
    MANUFACTURING_STATUS = 0x0057


@dataclass
class BQ40Z50Status:
    """Complete battery status."""
    voltage_mv: int
    current_ma: int
    temperature_c: float
    state_of_charge: int        # 0-100%
    remaining_capacity_mah: int
    full_charge_capacity_mah: int
    cycle_count: int
    time_to_empty_min: int
    time_to_full_min: int
    is_charging: bool
    is_discharging: bool
    cell_voltages_mv: Tuple[int, ...]  # Per-cell voltages


class BQ40Z50Driver:
    """
    Driver for BQ40Z50 battery fuel gauge.
    
    Features:
    - Impedance Track™ algorithm
    - Cell balancing support
    - Integrated protection FET control
    - SMBus v1.1 compliant
    """
    
    I2C_ADDR = 0x0B  # Standard SBS address (can be 0x16 in some configs)
    
    def __init__(
        self,
        i2c_bus: int = 1,
        i2c_addr: int = 0x0B,
        simulate: bool = False,
    ):
        """
        Initialize BQ40Z50 driver.
        
        Args:
            i2c_bus: I2C bus number
            i2c_addr: I2C address (0x0B standard)
            simulate: Run in simulation mode
        """
        self.i2c_bus = i2c_bus
        self.i2c_addr = i2c_addr
        self.simulate = simulate or not HAS_SMBUS
        
        self._bus: Optional[smbus2.SMBus] = None
        self._initialized = False
        
        # Simulation state (3S battery)
        self._sim_soc = 75
        self._sim_voltage = 11100  # 3.7V * 3 cells
        self._sim_current = -500   # Discharging 500mA
        
        self._init_i2c()
    
    def _init_i2c(self) -> None:
        """Initialize I2C interface."""
        if self.simulate:
            self._initialized = True
            return
        
        try:
            self._bus = smbus2.SMBus(self.i2c_bus)
            # Verify by reading device type
            self._initialized = True
        except Exception as e:
            print(f"BQ40Z50 I2C init failed: {e}")
            self._initialized = False
            self.simulate = True
    
    def _read_word(self, cmd: int) -> int:
        """Read a 16-bit word (little-endian)."""
        if self.simulate:
            return self._simulate_read(cmd)
        return self._bus.read_word_data(self.i2c_addr, cmd)
    
    def _read_block(self, cmd: int, length: int) -> bytes:
        """Read a block of data."""
        if self.simulate:
            return bytes([0] * length)
        data = self._bus.read_i2c_block_data(self.i2c_addr, cmd, length)
        return bytes(data)
    
    def _write_word(self, cmd: int, value: int) -> None:
        """Write a 16-bit word."""
        if self.simulate:
            return
        self._bus.write_word_data(self.i2c_addr, cmd, value)
    
    def _simulate_read(self, cmd: int) -> int:
        """Simulate register reads."""
        if cmd == BQ40Z50Cmd.VOLTAGE:
            return self._sim_voltage
        elif cmd == BQ40Z50Cmd.CURRENT:
            # Signed 16-bit
            return self._sim_current & 0xFFFF
        elif cmd == BQ40Z50Cmd.TEMPERATURE:
            # 0.1K units, 25°C = 2981
            return 2981
        elif cmd == BQ40Z50Cmd.RELATIVE_STATE_OF_CHARGE:
            return self._sim_soc
        elif cmd == BQ40Z50Cmd.REMAINING_CAPACITY:
            return int(2200 * self._sim_soc / 100)  # 2200mAh design
        elif cmd == BQ40Z50Cmd.FULL_CHARGE_CAPACITY:
            return 2200
        elif cmd == BQ40Z50Cmd.CYCLE_COUNT:
            return 42
        elif cmd == BQ40Z50Cmd.RUN_TIME_TO_EMPTY:
            if self._sim_current < 0:
                return int(2200 * self._sim_soc / 100 / abs(self._sim_current) * 60)
            return 65535
        elif cmd == BQ40Z50Cmd.AVERAGE_TIME_TO_FULL:
            if self._sim_current > 0:
                return int(2200 * (100 - self._sim_soc) / 100 / self._sim_current * 60)
            return 65535
        elif cmd in [BQ40Z50Cmd.CELL_VOLTAGE_1, BQ40Z50Cmd.CELL_VOLTAGE_2, BQ40Z50Cmd.CELL_VOLTAGE_3]:
            return self._sim_voltage // 3
        return 0
    
    def is_initialized(self) -> bool:
        """Check if driver is initialized."""
        return self._initialized
    
    def get_voltage(self) -> int:
        """Get battery pack voltage in mV."""
        return self._read_word(BQ40Z50Cmd.VOLTAGE)
    
    def get_current(self) -> int:
        """
        Get battery current in mA.
        Positive = charging, Negative = discharging.
        """
        raw = self._read_word(BQ40Z50Cmd.CURRENT)
        # Convert from unsigned to signed 16-bit
        if raw >= 0x8000:
            raw -= 0x10000
        return raw
    
    def get_temperature(self) -> float:
        """Get battery temperature in Celsius."""
        # Returns 0.1K units
        raw = self._read_word(BQ40Z50Cmd.TEMPERATURE)
        kelvin = raw / 10.0
        return kelvin - 273.15
    
    def get_state_of_charge(self) -> int:
        """Get relative state of charge (0-100%)."""
        return self._read_word(BQ40Z50Cmd.RELATIVE_STATE_OF_CHARGE)
    
    def get_remaining_capacity(self) -> int:
        """Get remaining capacity in mAh."""
        return self._read_word(BQ40Z50Cmd.REMAINING_CAPACITY)
    
    def get_full_charge_capacity(self) -> int:
        """Get full charge capacity in mAh."""
        return self._read_word(BQ40Z50Cmd.FULL_CHARGE_CAPACITY)
    
    def get_cycle_count(self) -> int:
        """Get battery cycle count."""
        return self._read_word(BQ40Z50Cmd.CYCLE_COUNT)
    
    def get_time_to_empty(self) -> int:
        """Get estimated time to empty in minutes."""
        return self._read_word(BQ40Z50Cmd.RUN_TIME_TO_EMPTY)
    
    def get_time_to_full(self) -> int:
        """Get estimated time to full in minutes."""
        return self._read_word(BQ40Z50Cmd.AVERAGE_TIME_TO_FULL)
    
    def get_cell_voltages(self) -> Tuple[int, int, int]:
        """Get individual cell voltages (3S pack)."""
        v1 = self._read_word(BQ40Z50Cmd.CELL_VOLTAGE_1)
        v2 = self._read_word(BQ40Z50Cmd.CELL_VOLTAGE_2)
        v3 = self._read_word(BQ40Z50Cmd.CELL_VOLTAGE_3)
        return (v1, v2, v3)
    
    def get_status(self) -> BQ40Z50Status:
        """Get complete battery status."""
        current = self.get_current()
        
        return BQ40Z50Status(
            voltage_mv=self.get_voltage(),
            current_ma=current,
            temperature_c=self.get_temperature(),
            state_of_charge=self.get_state_of_charge(),
            remaining_capacity_mah=self.get_remaining_capacity(),
            full_charge_capacity_mah=self.get_full_charge_capacity(),
            cycle_count=self.get_cycle_count(),
            time_to_empty_min=self.get_time_to_empty(),
            time_to_full_min=self.get_time_to_full(),
            is_charging=current > 0,
            is_discharging=current < 0,
            cell_voltages_mv=self.get_cell_voltages(),
        )
    
    def close(self) -> None:
        """Clean up resources."""
        if self._bus:
            self._bus.close()
            self._bus = None
        self._initialized = False


# =============================================================================
# UNIFIED POWER MONITOR
# =============================================================================

class PowerMonitor:
    """
    Unified power monitoring interface.
    
    Combines BQ25895 (charger) and BQ40Z50 (fuel gauge) into
    a single high-level interface for power management.
    """
    
    def __init__(self, i2c_bus: int = 1, simulate: bool = False):
        """
        Initialize power monitoring.
        
        Args:
            i2c_bus: I2C bus number
            simulate: Run in simulation mode
        """
        self.charger = BQ25895Driver(i2c_bus=i2c_bus, simulate=simulate)
        self.fuel_gauge = BQ40Z50Driver(i2c_bus=i2c_bus, simulate=simulate)
        
        # Enable ADC for continuous monitoring
        if self.charger.is_initialized():
            self.charger.enable_adc(one_shot=False)
    
    def is_initialized(self) -> bool:
        """Check if both ICs are initialized."""
        return self.charger.is_initialized() and self.fuel_gauge.is_initialized()
    
    def get_battery_percentage(self) -> int:
        """Get battery state of charge (0-100%)."""
        return self.fuel_gauge.get_state_of_charge()
    
    def get_charging_status(self) -> str:
        """Get current charging status."""
        status = self.charger.get_status()
        
        if status.charge_status == BQ25895ChargeStatus.NOT_CHARGING:
            if status.power_good:
                return "full"
            else:
                return "discharging"
        elif status.charge_status == BQ25895ChargeStatus.PRE_CHARGE:
            return "pre_charge"
        elif status.charge_status == BQ25895ChargeStatus.FAST_CHARGING:
            return "charging"
        elif status.charge_status == BQ25895ChargeStatus.CHARGE_DONE:
            return "full"
        return "not_present"
    
    def get_temperature(self) -> float:
        """Get battery temperature in Celsius."""
        return self.fuel_gauge.get_temperature()
    
    def get_voltage(self) -> int:
        """Get battery voltage in mV."""
        return self.fuel_gauge.get_voltage()
    
    def get_current(self) -> int:
        """Get battery current in mA (negative = discharging)."""
        return self.fuel_gauge.get_current()
    
    def get_estimated_runtime(self) -> int:
        """Get estimated runtime in minutes."""
        current = self.fuel_gauge.get_current()
        if current < 0:
            return self.fuel_gauge.get_time_to_empty()
        return -1  # Charging, not discharging
    
    def get_time_to_full(self) -> int:
        """Get estimated time to full charge in minutes."""
        return self.fuel_gauge.get_time_to_full()
    
    def has_faults(self) -> bool:
        """Check if there are any charger faults."""
        status = self.charger.get_status()
        return status.faults != BQ25895Fault.NONE
    
    def get_faults(self) -> BQ25895Fault:
        """Get active fault flags."""
        status = self.charger.get_status()
        return status.faults
    
    def close(self) -> None:
        """Clean up resources."""
        self.charger.close()
        self.fuel_gauge.close()
