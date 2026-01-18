"""
Sensor Drivers for Kagami Orb

ICM-45686: 6-axis IMU (accelerometer + gyroscope) via I2C/SPI
VL53L8CX: 64-zone Time-of-Flight sensor via I2C  
SHT45: Temperature and humidity sensor via I2C

Reference:
- ICM-45686: https://invensense.tdk.com/products/motion-tracking/6-axis/icm-45686/
- VL53L8CX: https://www.st.com/en/imaging-and-photonics-solutions/vl53l8cx.html
- SHT45: https://sensirion.com/media/documents/33FD6951/67EB9032/HT_DS_Datasheet_SHT4x_5.pdf
"""

import struct
import time
import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Tuple, List
import logging

try:
    import smbus2
    HAS_SMBUS = True
except ImportError:
    HAS_SMBUS = False

logger = logging.getLogger(__name__)


# =============================================================================
# ICM-45686 IMU DRIVER
# =============================================================================

class ICM45686Reg(IntEnum):
    """ICM-45686 Register Map (Bank 0 - most common)."""
    # Device identification
    WHO_AM_I = 0x75              # Should return 0xE5
    
    # Configuration
    DEVICE_CONFIG = 0x11
    DRIVE_CONFIG = 0x13
    INT_CONFIG = 0x14
    FIFO_CONFIG = 0x16
    
    # Temperature
    TEMP_DATA1 = 0x1D            # High byte
    TEMP_DATA0 = 0x1E            # Low byte
    
    # Accelerometer
    ACCEL_DATA_X1 = 0x1F         # X high byte
    ACCEL_DATA_X0 = 0x20         # X low byte
    ACCEL_DATA_Y1 = 0x21
    ACCEL_DATA_Y0 = 0x22
    ACCEL_DATA_Z1 = 0x23
    ACCEL_DATA_Z0 = 0x24
    
    # Gyroscope
    GYRO_DATA_X1 = 0x25          # X high byte
    GYRO_DATA_X0 = 0x26          # X low byte
    GYRO_DATA_Y1 = 0x27
    GYRO_DATA_Y0 = 0x28
    GYRO_DATA_Z1 = 0x29
    GYRO_DATA_Z0 = 0x2A
    
    # Timestamp
    TMST_FSYNCH = 0x2B
    TMST_FSYNCL = 0x2C
    
    # Interrupt status
    INT_STATUS = 0x2D
    FIFO_COUNTH = 0x2E
    FIFO_COUNTL = 0x2F
    FIFO_DATA = 0x30
    
    # Apex status
    APEX_DATA0 = 0x31
    APEX_DATA1 = 0x32
    APEX_DATA2 = 0x33
    APEX_DATA3 = 0x34
    
    # Signal path reset
    SIGNAL_PATH_RESET = 0x4B
    
    # Power management
    INTF_CONFIG0 = 0x4C
    INTF_CONFIG1 = 0x4D
    PWR_MGMT0 = 0x4E
    
    # Gyro config
    GYRO_CONFIG0 = 0x4F
    
    # Accel config
    ACCEL_CONFIG0 = 0x50
    GYRO_CONFIG1 = 0x51
    GYRO_ACCEL_CONFIG0 = 0x52
    ACCEL_CONFIG1 = 0x53
    
    # FIFO config
    TMST_CONFIG = 0x54
    APEX_CONFIG0 = 0x56
    
    # Interrupt config
    SMD_CONFIG = 0x57
    FIFO_CONFIG1 = 0x5F
    FIFO_CONFIG2 = 0x60
    FIFO_CONFIG3 = 0x61
    
    # INT source
    FSYNC_CONFIG = 0x62
    INT_CONFIG0 = 0x63
    INT_CONFIG1 = 0x64
    INT_SOURCE0 = 0x65
    INT_SOURCE1 = 0x66
    
    # Self test
    SELF_TEST_CONFIG = 0x70
    
    # Bank select
    REG_BANK_SEL = 0x76


class ICM45686AccelFS(IntEnum):
    """Accelerometer full-scale range."""
    FS_16G = 0b000   # ±16g
    FS_8G = 0b001    # ±8g
    FS_4G = 0b010    # ±4g
    FS_2G = 0b011    # ±2g


class ICM45686GyroFS(IntEnum):
    """Gyroscope full-scale range."""
    FS_2000DPS = 0b000  # ±2000 °/s
    FS_1000DPS = 0b001  # ±1000 °/s
    FS_500DPS = 0b010   # ±500 °/s
    FS_250DPS = 0b011   # ±250 °/s
    FS_125DPS = 0b100   # ±125 °/s
    FS_62_5DPS = 0b101  # ±62.5 °/s
    FS_31_25DPS = 0b110 # ±31.25 °/s


class ICM45686ODR(IntEnum):
    """Output data rate."""
    ODR_32KHZ = 0b0001
    ODR_16KHZ = 0b0010
    ODR_8KHZ = 0b0011
    ODR_4KHZ = 0b0100
    ODR_2KHZ = 0b0101
    ODR_1KHZ = 0b0110
    ODR_200HZ = 0b0111
    ODR_100HZ = 0b1000
    ODR_50HZ = 0b1001
    ODR_25HZ = 0b1010
    ODR_12_5HZ = 0b1011


@dataclass
class IMUData:
    """IMU reading with all sensor data."""
    accel_x: float  # m/s²
    accel_y: float
    accel_z: float
    gyro_x: float   # rad/s
    gyro_y: float
    gyro_z: float
    temperature_c: float
    timestamp_ms: float = 0.0
    
    @property
    def accel_magnitude(self) -> float:
        """Total acceleration magnitude."""
        return math.sqrt(self.accel_x**2 + self.accel_y**2 + self.accel_z**2)
    
    @property
    def gyro_magnitude(self) -> float:
        """Total angular velocity magnitude."""
        return math.sqrt(self.gyro_x**2 + self.gyro_y**2 + self.gyro_z**2)


class ICM45686Driver:
    """
    Driver for TDK ICM-45686 6-axis IMU.
    
    Features:
    - BalancedGyro Technology for superior vibration rejection
    - 0.42mA in Low Noise mode (industry lowest)
    - Up to 32kHz ODR
    - I2C/SPI/I3C interfaces
    - APEX features (pedometer, tilt, tap detection)
    """
    
    I2C_ADDR = 0x68  # Default address (AD0=0), or 0x69 (AD0=1)
    WHO_AM_I_VALUE = 0xE5
    
    # Sensitivity factors
    ACCEL_SENSITIVITY = {
        ICM45686AccelFS.FS_2G: 16384.0,   # LSB/g
        ICM45686AccelFS.FS_4G: 8192.0,
        ICM45686AccelFS.FS_8G: 4096.0,
        ICM45686AccelFS.FS_16G: 2048.0,
    }
    
    GYRO_SENSITIVITY = {
        ICM45686GyroFS.FS_250DPS: 131.0,    # LSB/(°/s)
        ICM45686GyroFS.FS_500DPS: 65.5,
        ICM45686GyroFS.FS_1000DPS: 32.8,
        ICM45686GyroFS.FS_2000DPS: 16.4,
    }
    
    def __init__(
        self,
        i2c_bus: int = 1,
        i2c_addr: int = 0x68,
        accel_fs: ICM45686AccelFS = ICM45686AccelFS.FS_4G,
        gyro_fs: ICM45686GyroFS = ICM45686GyroFS.FS_500DPS,
        odr: ICM45686ODR = ICM45686ODR.ODR_100HZ,
        simulate: bool = False,
    ):
        """
        Initialize ICM-45686 IMU.
        
        Args:
            i2c_bus: I2C bus number
            i2c_addr: I2C address (0x68 or 0x69)
            accel_fs: Accelerometer full-scale range
            gyro_fs: Gyroscope full-scale range
            odr: Output data rate
            simulate: Run in simulation mode
        """
        self.i2c_bus = i2c_bus
        self.i2c_addr = i2c_addr
        self.accel_fs = accel_fs
        self.gyro_fs = gyro_fs
        self.odr = odr
        self.simulate = simulate or not HAS_SMBUS
        
        self._bus: Optional[smbus2.SMBus] = None
        self._initialized = False
        
        # Simulation state
        self._sim_angle = 0.0
        
        self._init_device()
    
    def _init_device(self) -> None:
        """Initialize the IMU."""
        if self.simulate:
            self._initialized = True
            return
        
        try:
            self._bus = smbus2.SMBus(self.i2c_bus)
            
            # Check WHO_AM_I
            who_am_i = self._read_reg(ICM45686Reg.WHO_AM_I)
            if who_am_i != self.WHO_AM_I_VALUE:
                logger.warning(f"Unexpected WHO_AM_I: {who_am_i:#04x} (expected {self.WHO_AM_I_VALUE:#04x})")
            
            # Soft reset
            self._write_reg(ICM45686Reg.DEVICE_CONFIG, 0x01)
            time.sleep(0.001)  # 1ms reset time
            
            # Select Bank 0
            self._write_reg(ICM45686Reg.REG_BANK_SEL, 0x00)
            
            # Configure accelerometer
            accel_config = (self.accel_fs << 5) | self.odr
            self._write_reg(ICM45686Reg.ACCEL_CONFIG0, accel_config)
            
            # Configure gyroscope
            gyro_config = (self.gyro_fs << 5) | self.odr
            self._write_reg(ICM45686Reg.GYRO_CONFIG0, gyro_config)
            
            # Enable accel and gyro in Low Noise mode
            # PWR_MGMT0: ACCEL_MODE[1:0]=0b11 (LN), GYRO_MODE[1:0]=0b11 (LN)
            self._write_reg(ICM45686Reg.PWR_MGMT0, 0x0F)
            
            # Wait for sensors to stabilize
            time.sleep(0.030)  # 30ms
            
            self._initialized = True
            logger.info("ICM-45686 initialized successfully")
            
        except Exception as e:
            logger.error(f"ICM-45686 init failed: {e}")
            self._initialized = False
            self.simulate = True
    
    def _read_reg(self, reg: int) -> int:
        """Read a single register."""
        if self.simulate:
            return self._simulate_read(reg)
        return self._bus.read_byte_data(self.i2c_addr, reg)
    
    def _read_regs(self, reg: int, length: int) -> bytes:
        """Read multiple consecutive registers."""
        if self.simulate:
            return bytes([self._simulate_read(reg + i) for i in range(length)])
        return bytes(self._bus.read_i2c_block_data(self.i2c_addr, reg, length))
    
    def _write_reg(self, reg: int, value: int) -> None:
        """Write a single register."""
        if self.simulate:
            return
        self._bus.write_byte_data(self.i2c_addr, reg, value)
    
    def _simulate_read(self, reg: int) -> int:
        """Simulate register reads."""
        if reg == ICM45686Reg.WHO_AM_I:
            return self.WHO_AM_I_VALUE
        elif reg == ICM45686Reg.INT_STATUS:
            return 0x01  # Data ready
        # Simulate gentle oscillation
        self._sim_angle += 0.02
        value = int(4096 * math.sin(self._sim_angle))
        if reg in [ICM45686Reg.ACCEL_DATA_X1, ICM45686Reg.ACCEL_DATA_Y1, ICM45686Reg.ACCEL_DATA_Z1]:
            # High byte
            return (value >> 8) & 0xFF
        elif reg in [ICM45686Reg.ACCEL_DATA_X0, ICM45686Reg.ACCEL_DATA_Y0, ICM45686Reg.ACCEL_DATA_Z0]:
            # Low byte
            return value & 0xFF
        elif reg in [ICM45686Reg.GYRO_DATA_X1, ICM45686Reg.GYRO_DATA_Y1, ICM45686Reg.GYRO_DATA_Z1]:
            return ((value // 2) >> 8) & 0xFF
        elif reg in [ICM45686Reg.GYRO_DATA_X0, ICM45686Reg.GYRO_DATA_Y0, ICM45686Reg.GYRO_DATA_Z0]:
            return (value // 2) & 0xFF
        elif reg == ICM45686Reg.TEMP_DATA1:
            return 0x00
        elif reg == ICM45686Reg.TEMP_DATA0:
            return 0x00  # ~25°C
        return 0x00
    
    def is_initialized(self) -> bool:
        """Check if driver is initialized."""
        return self._initialized
    
    def _to_signed16(self, high: int, low: int) -> int:
        """Convert two bytes to signed 16-bit integer."""
        value = (high << 8) | low
        if value >= 0x8000:
            value -= 0x10000
        return value
    
    def read(self) -> IMUData:
        """
        Read all sensor data in a single burst.
        
        Returns:
            IMUData with acceleration (m/s²) and angular velocity (rad/s)
        """
        # Burst read from TEMP_DATA1 to GYRO_DATA_Z0 (14 bytes)
        data = self._read_regs(ICM45686Reg.TEMP_DATA1, 14)
        
        # Parse temperature (offset binary, 132.48 LSB/°C, offset 25°C)
        temp_raw = self._to_signed16(data[0], data[1])
        temp_c = (temp_raw / 132.48) + 25.0
        
        # Parse accelerometer
        accel_x_raw = self._to_signed16(data[2], data[3])
        accel_y_raw = self._to_signed16(data[4], data[5])
        accel_z_raw = self._to_signed16(data[6], data[7])
        
        # Parse gyroscope
        gyro_x_raw = self._to_signed16(data[8], data[9])
        gyro_y_raw = self._to_signed16(data[10], data[11])
        gyro_z_raw = self._to_signed16(data[12], data[13])
        
        # Convert to physical units
        accel_sens = self.ACCEL_SENSITIVITY[self.accel_fs]
        gyro_sens = self.GYRO_SENSITIVITY[self.gyro_fs]
        
        # Accelerometer: LSB -> g -> m/s² (multiply by 9.80665)
        g_to_ms2 = 9.80665
        accel_x = (accel_x_raw / accel_sens) * g_to_ms2
        accel_y = (accel_y_raw / accel_sens) * g_to_ms2
        accel_z = (accel_z_raw / accel_sens) * g_to_ms2
        
        # Gyroscope: LSB -> °/s -> rad/s (multiply by π/180)
        dps_to_rads = math.pi / 180.0
        gyro_x = (gyro_x_raw / gyro_sens) * dps_to_rads
        gyro_y = (gyro_y_raw / gyro_sens) * dps_to_rads
        gyro_z = (gyro_z_raw / gyro_sens) * dps_to_rads
        
        return IMUData(
            accel_x=accel_x,
            accel_y=accel_y,
            accel_z=accel_z,
            gyro_x=gyro_x,
            gyro_y=gyro_y,
            gyro_z=gyro_z,
            temperature_c=temp_c,
            timestamp_ms=time.monotonic() * 1000,
        )
    
    def close(self) -> None:
        """Clean up resources."""
        if self._bus:
            self._bus.close()
            self._bus = None
        self._initialized = False


# =============================================================================
# VL53L8CX TIME-OF-FLIGHT DRIVER
# =============================================================================

@dataclass
class ToFZone:
    """Single zone ranging result."""
    distance_mm: int
    status: int               # 0=valid, other=error codes
    sigma_mm: int             # Range sigma/uncertainty
    signal_kcps: int          # Signal rate (kilo-counts per second)
    ambient_kcps: int         # Ambient light level
    
    @property
    def is_valid(self) -> bool:
        """Check if measurement is valid."""
        return self.status == 0 or self.status == 5  # 5 = valid but ranging rate lower


@dataclass
class ToFFrame:
    """Complete 8x8 (64-zone) ranging frame."""
    zones: List[ToFZone]
    resolution: int = 64      # 4x4 (16) or 8x8 (64)
    frame_id: int = 0
    timestamp_ms: float = 0.0
    
    def get_zone(self, row: int, col: int) -> ToFZone:
        """Get zone by row/column (0-7)."""
        if self.resolution == 64:
            idx = row * 8 + col
        else:
            idx = row * 4 + col
        return self.zones[idx]
    
    def get_distance_matrix(self) -> List[List[int]]:
        """Get distances as 2D matrix."""
        size = 8 if self.resolution == 64 else 4
        matrix = []
        for row in range(size):
            row_data = []
            for col in range(size):
                idx = row * size + col
                row_data.append(self.zones[idx].distance_mm)
            matrix.append(row_data)
        return matrix
    
    def get_closest(self) -> Tuple[int, int, int]:
        """Get closest valid distance and its position."""
        min_dist = 99999
        min_row, min_col = 0, 0
        size = 8 if self.resolution == 64 else 4
        
        for i, zone in enumerate(self.zones):
            if zone.is_valid and zone.distance_mm < min_dist and zone.distance_mm > 0:
                min_dist = zone.distance_mm
                min_row = i // size
                min_col = i % size
        
        return min_dist, min_row, min_col


class VL53L8CXDriver:
    """
    Driver for ST VL53L8CX 64-zone ToF sensor.
    
    Features:
    - 8x8 multizone ranging (64 zones)
    - Up to 4 meters range
    - 65° diagonal FOV
    - Up to 60Hz frame rate
    
    Note: Uses ST's Ultra Lite Driver (ULD) API abstraction.
    Direct register access is not officially supported by ST.
    """
    
    I2C_ADDR = 0x29  # Default address
    
    def __init__(
        self,
        i2c_bus: int = 1,
        i2c_addr: int = 0x29,
        resolution: int = 64,  # 16 or 64 zones
        ranging_frequency_hz: int = 15,
        simulate: bool = False,
    ):
        """
        Initialize VL53L8CX ToF sensor.
        
        Args:
            i2c_bus: I2C bus number
            i2c_addr: I2C address
            resolution: 16 (4x4) or 64 (8x8) zones
            ranging_frequency_hz: Target frequency (1-60Hz)
            simulate: Run in simulation mode
        """
        self.i2c_bus = i2c_bus
        self.i2c_addr = i2c_addr
        self.resolution = 64 if resolution >= 64 else 16
        self.ranging_frequency_hz = min(60, max(1, ranging_frequency_hz))
        self.simulate = simulate or not HAS_SMBUS
        
        self._bus: Optional[smbus2.SMBus] = None
        self._initialized = False
        self._frame_id = 0
        
        # VL53L8CX requires firmware upload and complex init via ULD
        # In simulation mode, we bypass this
        self._init_device()
    
    def _init_device(self) -> None:
        """Initialize the ToF sensor."""
        if self.simulate:
            self._initialized = True
            return
        
        try:
            self._bus = smbus2.SMBus(self.i2c_bus)
            
            # NOTE: Real VL53L8CX requires:
            # 1. Firmware upload (~80KB)
            # 2. Complex initialization sequence
            # 3. Using ST's VL53L8CX ULD library
            #
            # This is a simplified interface that assumes
            # the ULD library handles low-level communication.
            # For production, wrap the official C library via ctypes/cffi.
            
            logger.warning("VL53L8CX requires ST ULD library for real hardware")
            logger.info("Running in simulation mode")
            self.simulate = True
            self._initialized = True
            
        except Exception as e:
            logger.error(f"VL53L8CX init failed: {e}")
            self._initialized = False
            self.simulate = True
    
    def is_initialized(self) -> bool:
        """Check if driver is initialized."""
        return self._initialized
    
    def read_frame(self) -> ToFFrame:
        """
        Read a complete ranging frame.
        
        Returns:
            ToFFrame with all zone measurements
        """
        if self.simulate:
            return self._simulate_frame()
        
        # In real implementation, this would:
        # 1. Check data_ready status
        # 2. Read ranging results buffer
        # 3. Parse per-zone data
        raise NotImplementedError("Real VL53L8CX requires ST ULD library")
    
    def _simulate_frame(self) -> ToFFrame:
        """Generate a simulated ranging frame."""
        import random
        
        zones = []
        size = 8 if self.resolution == 64 else 4
        
        # Simulate a person at ~1.5m in the center
        center_row, center_col = size // 2, size // 2
        
        for row in range(size):
            for col in range(size):
                # Distance varies based on position
                dist_from_center = math.sqrt((row - center_row)**2 + (col - center_col)**2)
                
                if dist_from_center < 2:
                    # Close object (person)
                    base_dist = 1500 + int(dist_from_center * 100)
                else:
                    # Far wall
                    base_dist = 3500
                
                # Add noise
                distance = base_dist + random.randint(-20, 20)
                
                zones.append(ToFZone(
                    distance_mm=distance,
                    status=0,  # Valid
                    sigma_mm=random.randint(5, 15),
                    signal_kcps=random.randint(5000, 20000),
                    ambient_kcps=random.randint(100, 500),
                ))
        
        self._frame_id += 1
        
        return ToFFrame(
            zones=zones,
            resolution=self.resolution,
            frame_id=self._frame_id,
            timestamp_ms=time.monotonic() * 1000,
        )
    
    def close(self) -> None:
        """Clean up resources."""
        if self._bus:
            self._bus.close()
            self._bus = None
        self._initialized = False


# =============================================================================
# SHT45 TEMPERATURE/HUMIDITY DRIVER
# =============================================================================

class SHT45Cmd(IntEnum):
    """SHT45 I2C Commands (from datasheet)."""
    MEASURE_HIGH_PRECISION = 0xFD       # High repeatability, ~8.2ms
    MEASURE_MEDIUM_PRECISION = 0xF6     # Medium repeatability, ~4.5ms
    MEASURE_LOW_PRECISION = 0xE0        # Low repeatability, ~1.7ms
    READ_SERIAL = 0x89                  # Read unique serial number
    SOFT_RESET = 0x94                   # Soft reset
    
    # Heater commands (for sensor diagnostics)
    HEATER_HIGH_1S = 0x39               # 200mW for 1s
    HEATER_HIGH_100MS = 0x32            # 200mW for 0.1s
    HEATER_MED_1S = 0x2F                # 110mW for 1s
    HEATER_MED_100MS = 0x24             # 110mW for 0.1s
    HEATER_LOW_1S = 0x1E                # 20mW for 1s
    HEATER_LOW_100MS = 0x15             # 20mW for 0.1s


@dataclass
class TempHumidity:
    """Temperature and humidity reading."""
    temperature_c: float
    humidity_pct: float
    timestamp_ms: float = 0.0
    
    @property
    def temperature_f(self) -> float:
        """Temperature in Fahrenheit."""
        return self.temperature_c * 9 / 5 + 32
    
    @property
    def dew_point_c(self) -> float:
        """Calculate dew point using Magnus formula."""
        a = 17.27
        b = 237.7
        alpha = (a * self.temperature_c) / (b + self.temperature_c) + math.log(self.humidity_pct / 100.0)
        return (b * alpha) / (a - alpha)
    
    @property
    def heat_index_c(self) -> float:
        """Calculate heat index (feels-like temperature)."""
        # Simplified Rothfusz regression
        T = self.temperature_c
        R = self.humidity_pct
        
        if T < 27 or R < 40:
            return T
        
        HI = -8.78469475556 + \
             1.61139411 * T + \
             2.33854883889 * R + \
             -0.14611605 * T * R + \
             -0.012308094 * T**2 + \
             -0.0164248277778 * R**2 + \
             0.002211732 * T**2 * R + \
             0.00072546 * T * R**2 + \
             -0.000003582 * T**2 * R**2
        
        return HI


class SHT45Driver:
    """
    Driver for Sensirion SHT45 temperature/humidity sensor.
    
    Features:
    - ±0.1°C temperature accuracy (typical)
    - ±1% RH humidity accuracy (typical)
    - Fully calibrated, linearized
    - Built-in heater for diagnostics
    """
    
    I2C_ADDR = 0x44  # Default address (can be 0x45)
    
    def __init__(
        self,
        i2c_bus: int = 1,
        i2c_addr: int = 0x44,
        simulate: bool = False,
    ):
        """
        Initialize SHT45 sensor.
        
        Args:
            i2c_bus: I2C bus number
            i2c_addr: I2C address (0x44 or 0x45)
            simulate: Run in simulation mode
        """
        self.i2c_bus = i2c_bus
        self.i2c_addr = i2c_addr
        self.simulate = simulate or not HAS_SMBUS
        
        self._bus: Optional[smbus2.SMBus] = None
        self._initialized = False
        self._serial: Optional[int] = None
        
        self._init_device()
    
    def _init_device(self) -> None:
        """Initialize the sensor."""
        if self.simulate:
            self._serial = 0xDEADBEEF
            self._initialized = True
            return
        
        try:
            self._bus = smbus2.SMBus(self.i2c_bus)
            
            # Soft reset
            self._bus.write_byte(self.i2c_addr, SHT45Cmd.SOFT_RESET)
            time.sleep(0.001)  # 1ms reset time
            
            # Read serial number
            self._bus.write_byte(self.i2c_addr, SHT45Cmd.READ_SERIAL)
            time.sleep(0.001)
            data = self._bus.read_i2c_block_data(self.i2c_addr, 0, 6)
            
            # Serial is two 16-bit words with CRC
            self._serial = (data[0] << 24) | (data[1] << 16) | (data[3] << 8) | data[4]
            
            self._initialized = True
            logger.info(f"SHT45 initialized, serial: {self._serial:#010x}")
            
        except Exception as e:
            logger.error(f"SHT45 init failed: {e}")
            self._initialized = False
            self.simulate = True
    
    def is_initialized(self) -> bool:
        """Check if driver is initialized."""
        return self._initialized
    
    def _crc8(self, data: bytes) -> int:
        """Calculate CRC-8 for SHT45 (polynomial 0x31)."""
        crc = 0xFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x31
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc
    
    def read(self, precision: str = "high") -> TempHumidity:
        """
        Read temperature and humidity.
        
        Args:
            precision: "high", "medium", or "low"
        
        Returns:
            TempHumidity with readings
        """
        if self.simulate:
            return self._simulate_read()
        
        # Select command and wait time
        if precision == "high":
            cmd = SHT45Cmd.MEASURE_HIGH_PRECISION
            wait_ms = 10  # 8.2ms typ
        elif precision == "medium":
            cmd = SHT45Cmd.MEASURE_MEDIUM_PRECISION
            wait_ms = 5   # 4.5ms typ
        else:
            cmd = SHT45Cmd.MEASURE_LOW_PRECISION
            wait_ms = 2   # 1.7ms typ
        
        # Send measurement command
        self._bus.write_byte(self.i2c_addr, cmd)
        time.sleep(wait_ms / 1000.0)
        
        # Read 6 bytes: temp_h, temp_l, temp_crc, hum_h, hum_l, hum_crc
        data = self._bus.read_i2c_block_data(self.i2c_addr, 0, 6)
        
        # Verify CRCs
        if self._crc8(bytes([data[0], data[1]])) != data[2]:
            raise IOError("Temperature CRC mismatch")
        if self._crc8(bytes([data[3], data[4]])) != data[5]:
            raise IOError("Humidity CRC mismatch")
        
        # Convert raw values
        temp_raw = (data[0] << 8) | data[1]
        hum_raw = (data[3] << 8) | data[4]
        
        # Datasheet formulas
        temperature_c = -45.0 + 175.0 * (temp_raw / 65535.0)
        humidity_pct = -6.0 + 125.0 * (hum_raw / 65535.0)
        
        # Clamp humidity to valid range
        humidity_pct = max(0.0, min(100.0, humidity_pct))
        
        return TempHumidity(
            temperature_c=temperature_c,
            humidity_pct=humidity_pct,
            timestamp_ms=time.monotonic() * 1000,
        )
    
    def _simulate_read(self) -> TempHumidity:
        """Simulate a reading."""
        import random
        
        # Room temperature with slight variation
        temp = 23.5 + random.uniform(-0.5, 0.5)
        humidity = 45.0 + random.uniform(-2.0, 2.0)
        
        return TempHumidity(
            temperature_c=temp,
            humidity_pct=humidity,
            timestamp_ms=time.monotonic() * 1000,
        )
    
    def get_serial(self) -> Optional[int]:
        """Get sensor serial number."""
        return self._serial
    
    def close(self) -> None:
        """Clean up resources."""
        if self._bus:
            self._bus.close()
            self._bus = None
        self._initialized = False


# =============================================================================
# UNIFIED SENSOR INTERFACE
# =============================================================================

@dataclass
class OrbSensorState:
    """Complete sensor state for the orb."""
    imu: IMUData
    tof: ToFFrame
    environment: TempHumidity
    timestamp_ms: float = 0.0


class OrbSensors:
    """
    Unified sensor interface for Kagami Orb.
    
    Manages all sensors and provides coordinated readings.
    """
    
    def __init__(
        self,
        i2c_bus: int = 1,
        simulate: bool = False,
    ):
        """
        Initialize all sensors.
        
        Args:
            i2c_bus: I2C bus number
            simulate: Run all sensors in simulation mode
        """
        self.imu = ICM45686Driver(i2c_bus=i2c_bus, simulate=simulate)
        self.tof = VL53L8CXDriver(i2c_bus=i2c_bus, simulate=simulate)
        self.env = SHT45Driver(i2c_bus=i2c_bus, simulate=simulate)
    
    def is_initialized(self) -> bool:
        """Check if all sensors are initialized."""
        return (
            self.imu.is_initialized() and
            self.tof.is_initialized() and
            self.env.is_initialized()
        )
    
    def read_all(self) -> OrbSensorState:
        """Read all sensors and return unified state."""
        return OrbSensorState(
            imu=self.imu.read(),
            tof=self.tof.read_frame(),
            environment=self.env.read(),
            timestamp_ms=time.monotonic() * 1000,
        )
    
    def close(self) -> None:
        """Clean up all resources."""
        self.imu.close()
        self.tof.close()
        self.env.close()
