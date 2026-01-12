"""
Tests for Sensor Drivers

Tests cover:
- ICM-45686 IMU initialization, registers, and data conversion
- VL53L8CX ToF 64-zone ranging
- SHT45 temperature/humidity with CRC validation
- Unified sensor interface
"""

import pytest
import math
import time

import sys
sys.path.insert(0, str(pytest.importorskip("pathlib").Path(__file__).parent.parent))

from kagami_orb.drivers.sensors import (
    ICM45686Driver,
    ICM45686Reg,
    ICM45686AccelFS,
    ICM45686GyroFS,
    ICM45686ODR,
    IMUData,
    VL53L8CXDriver,
    ToFZone,
    ToFFrame,
    SHT45Driver,
    SHT45Cmd,
    TempHumidity,
    OrbSensors,
)


class TestICM45686Registers:
    """Test ICM-45686 register definitions."""
    
    def test_who_am_i_address(self):
        """Verify WHO_AM_I register address."""
        assert ICM45686Reg.WHO_AM_I == 0x75
    
    def test_data_registers(self):
        """Verify data register addresses are consecutive."""
        assert ICM45686Reg.TEMP_DATA1 == 0x1D
        assert ICM45686Reg.TEMP_DATA0 == 0x1E
        assert ICM45686Reg.ACCEL_DATA_X1 == 0x1F
        assert ICM45686Reg.ACCEL_DATA_X0 == 0x20
        assert ICM45686Reg.GYRO_DATA_X1 == 0x25
    
    def test_config_registers(self):
        """Verify configuration register addresses."""
        assert ICM45686Reg.PWR_MGMT0 == 0x4E
        assert ICM45686Reg.GYRO_CONFIG0 == 0x4F
        assert ICM45686Reg.ACCEL_CONFIG0 == 0x50


class TestICM45686Driver:
    """Test ICM-45686 IMU driver."""
    
    @pytest.fixture
    def imu(self):
        """Create IMU in simulation mode."""
        return ICM45686Driver(simulate=True)
    
    def test_initialization(self, imu):
        """Test driver initializes correctly."""
        assert imu.is_initialized()
        assert imu.i2c_addr == 0x68
    
    def test_who_am_i_value(self):
        """Test WHO_AM_I constant."""
        assert ICM45686Driver.WHO_AM_I_VALUE == 0xE5
    
    def test_read_imu_data(self, imu):
        """Test reading IMU data."""
        data = imu.read()
        
        assert isinstance(data, IMUData)
        assert isinstance(data.accel_x, float)
        assert isinstance(data.gyro_x, float)
        assert isinstance(data.temperature_c, float)
    
    def test_acceleration_units(self, imu):
        """Test acceleration is in m/s²."""
        data = imu.read()
        
        # At rest, magnitude should be ~9.8 (gravity)
        # In simulation, it's oscillating
        assert data.accel_magnitude >= 0
    
    def test_gyro_units(self, imu):
        """Test gyroscope is in rad/s."""
        data = imu.read()
        
        # Angular velocity
        assert data.gyro_magnitude >= 0
    
    def test_timestamp(self, imu):
        """Test timestamp is present."""
        data = imu.read()
        assert data.timestamp_ms > 0
    
    def test_sensitivity_tables(self):
        """Test sensitivity lookup tables."""
        # Accelerometer: ±4g -> 8192 LSB/g
        assert ICM45686Driver.ACCEL_SENSITIVITY[ICM45686AccelFS.FS_4G] == 8192.0
        
        # Gyroscope: ±500°/s -> 65.5 LSB/(°/s)
        assert ICM45686Driver.GYRO_SENSITIVITY[ICM45686GyroFS.FS_500DPS] == 65.5
    
    def test_signed_conversion(self, imu):
        """Test signed 16-bit conversion."""
        # Test positive
        assert imu._to_signed16(0x00, 0x01) == 1
        assert imu._to_signed16(0x7F, 0xFF) == 32767
        
        # Test negative
        assert imu._to_signed16(0xFF, 0xFF) == -1
        assert imu._to_signed16(0x80, 0x00) == -32768


class TestIMUData:
    """Test IMUData dataclass."""
    
    def test_accel_magnitude(self):
        """Test acceleration magnitude calculation."""
        data = IMUData(
            accel_x=3.0,
            accel_y=4.0,
            accel_z=0.0,
            gyro_x=0,
            gyro_y=0,
            gyro_z=0,
            temperature_c=25,
        )
        
        assert data.accel_magnitude == 5.0  # 3-4-5 triangle
    
    def test_gyro_magnitude(self):
        """Test gyroscope magnitude calculation."""
        data = IMUData(
            accel_x=0,
            accel_y=0,
            accel_z=0,
            gyro_x=1.0,
            gyro_y=1.0,
            gyro_z=1.0,
            temperature_c=25,
        )
        
        expected = math.sqrt(3)
        assert abs(data.gyro_magnitude - expected) < 0.001


class TestVL53L8CXDriver:
    """Test VL53L8CX ToF driver."""
    
    @pytest.fixture
    def tof(self):
        """Create ToF sensor in simulation mode."""
        return VL53L8CXDriver(simulate=True)
    
    def test_initialization(self, tof):
        """Test driver initializes correctly."""
        assert tof.is_initialized()
        assert tof.i2c_addr == 0x29
    
    def test_resolution_options(self, tof):
        """Test resolution configuration."""
        assert tof.resolution in [16, 64]
    
    def test_read_frame(self, tof):
        """Test reading a ranging frame."""
        frame = tof.read_frame()
        
        assert isinstance(frame, ToFFrame)
        assert len(frame.zones) == tof.resolution
    
    def test_zone_data(self, tof):
        """Test zone data structure."""
        frame = tof.read_frame()
        zone = frame.zones[0]
        
        assert isinstance(zone, ToFZone)
        assert zone.distance_mm >= 0
        assert zone.sigma_mm >= 0
    
    def test_zone_validity(self, tof):
        """Test zone validity checking."""
        zone = ToFZone(
            distance_mm=1500,
            status=0,
            sigma_mm=10,
            signal_kcps=10000,
            ambient_kcps=200,
        )
        assert zone.is_valid
        
        invalid_zone = ToFZone(
            distance_mm=0,
            status=255,
            sigma_mm=0,
            signal_kcps=0,
            ambient_kcps=0,
        )
        assert not invalid_zone.is_valid
    
    def test_frame_timestamp(self, tof):
        """Test frame has timestamp."""
        frame = tof.read_frame()
        assert frame.timestamp_ms > 0
    
    def test_frame_id_increment(self, tof):
        """Test frame ID increments."""
        frame1 = tof.read_frame()
        frame2 = tof.read_frame()
        
        assert frame2.frame_id > frame1.frame_id


class TestToFFrame:
    """Test ToFFrame helper methods."""
    
    @pytest.fixture
    def frame(self):
        """Create a test frame."""
        zones = []
        for i in range(64):
            row = i // 8
            col = i % 8
            # Distance varies by position
            distance = 1000 + row * 100 + col * 10
            zones.append(ToFZone(
                distance_mm=distance,
                status=0,
                sigma_mm=10,
                signal_kcps=10000,
                ambient_kcps=200,
            ))
        return ToFFrame(zones=zones, resolution=64)
    
    def test_get_zone_by_position(self, frame):
        """Test getting zone by row/column."""
        zone = frame.get_zone(0, 0)
        assert zone.distance_mm == 1000
        
        zone = frame.get_zone(7, 7)
        assert zone.distance_mm == 1770
    
    def test_get_distance_matrix(self, frame):
        """Test getting 2D distance matrix."""
        matrix = frame.get_distance_matrix()
        
        assert len(matrix) == 8
        assert len(matrix[0]) == 8
        assert matrix[0][0] == 1000
    
    def test_get_closest(self, frame):
        """Test finding closest distance."""
        dist, row, col = frame.get_closest()
        
        assert dist == 1000
        assert row == 0
        assert col == 0


class TestSHT45Commands:
    """Test SHT45 command definitions."""
    
    def test_measurement_commands(self):
        """Verify measurement command codes."""
        assert SHT45Cmd.MEASURE_HIGH_PRECISION == 0xFD
        assert SHT45Cmd.MEASURE_MEDIUM_PRECISION == 0xF6
        assert SHT45Cmd.MEASURE_LOW_PRECISION == 0xE0
    
    def test_utility_commands(self):
        """Verify utility command codes."""
        assert SHT45Cmd.READ_SERIAL == 0x89
        assert SHT45Cmd.SOFT_RESET == 0x94


class TestSHT45Driver:
    """Test SHT45 temperature/humidity driver."""
    
    @pytest.fixture
    def sensor(self):
        """Create sensor in simulation mode."""
        return SHT45Driver(simulate=True)
    
    def test_initialization(self, sensor):
        """Test driver initializes correctly."""
        assert sensor.is_initialized()
        assert sensor.i2c_addr == 0x44
    
    def test_serial_number(self, sensor):
        """Test serial number reading."""
        serial = sensor.get_serial()
        assert serial is not None
    
    def test_read_high_precision(self, sensor):
        """Test high precision measurement."""
        reading = sensor.read(precision="high")
        
        assert isinstance(reading, TempHumidity)
        assert isinstance(reading.temperature_c, float)
        assert isinstance(reading.humidity_pct, float)
    
    def test_read_medium_precision(self, sensor):
        """Test medium precision measurement."""
        reading = sensor.read(precision="medium")
        assert reading.temperature_c is not None
    
    def test_read_low_precision(self, sensor):
        """Test low precision measurement."""
        reading = sensor.read(precision="low")
        assert reading.temperature_c is not None
    
    def test_temperature_range(self, sensor):
        """Test temperature is in reasonable range."""
        reading = sensor.read()
        
        # Room temperature: 15-35°C
        assert 10 <= reading.temperature_c <= 40
    
    def test_humidity_range(self, sensor):
        """Test humidity is in valid range."""
        reading = sensor.read()
        
        # 0-100%
        assert 0 <= reading.humidity_pct <= 100
    
    def test_crc8_calculation(self, sensor):
        """Test CRC-8 calculation."""
        # Test vector from Sensirion
        # Data: 0xBE, 0xEF -> CRC: 0x92
        data = bytes([0xBE, 0xEF])
        crc = sensor._crc8(data)
        assert crc == 0x92


class TestTempHumidity:
    """Test TempHumidity dataclass."""
    
    def test_temperature_fahrenheit(self):
        """Test Fahrenheit conversion."""
        reading = TempHumidity(temperature_c=25.0, humidity_pct=50.0)
        
        assert reading.temperature_f == 77.0
    
    def test_dew_point(self):
        """Test dew point calculation."""
        reading = TempHumidity(temperature_c=25.0, humidity_pct=50.0)
        
        # At 25°C and 50% RH, dew point is ~13.9°C
        assert 12 <= reading.dew_point_c <= 15
    
    def test_heat_index(self):
        """Test heat index calculation."""
        # At comfortable conditions, heat index ≈ temperature
        reading = TempHumidity(temperature_c=25.0, humidity_pct=50.0)
        assert reading.heat_index_c == 25.0  # Below threshold
        
        # At hot/humid conditions, heat index > temperature
        reading = TempHumidity(temperature_c=35.0, humidity_pct=80.0)
        assert reading.heat_index_c > 35.0


class TestOrbSensors:
    """Test unified sensor interface."""
    
    @pytest.fixture
    def sensors(self):
        """Create unified sensor interface."""
        return OrbSensors(simulate=True)
    
    def test_initialization(self, sensors):
        """Test all sensors initialize."""
        assert sensors.is_initialized()
    
    def test_read_all(self, sensors):
        """Test reading all sensors at once."""
        state = sensors.read_all()
        
        assert state.imu is not None
        assert state.tof is not None
        assert state.environment is not None
        assert state.timestamp_ms > 0
    
    def test_individual_sensor_access(self, sensors):
        """Test accessing individual sensors."""
        imu_data = sensors.imu.read()
        assert imu_data is not None
        
        tof_frame = sensors.tof.read_frame()
        assert tof_frame is not None
        
        env = sensors.env.read()
        assert env is not None


class TestSensorPerformance:
    """Test sensor performance."""
    
    def test_imu_read_speed(self):
        """Test IMU reads at required rate."""
        imu = ICM45686Driver(simulate=True)
        
        start = time.monotonic()
        for _ in range(100):
            imu.read()
        elapsed = time.monotonic() - start
        
        # Should handle 100Hz easily
        assert elapsed < 1.0
    
    def test_tof_frame_rate(self):
        """Test ToF frame rate."""
        tof = VL53L8CXDriver(simulate=True, ranging_frequency_hz=15)
        
        start = time.monotonic()
        for _ in range(15):
            tof.read_frame()
        elapsed = time.monotonic() - start
        
        # 15 frames should complete in ~1 second
        assert elapsed < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
