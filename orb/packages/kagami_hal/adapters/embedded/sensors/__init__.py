"""Embedded Sensor Modules.

Provides sensor implementations for embedded platforms:
- Camera (libcamera, V4L2, Jetson CSI)
- GPIO (buttons, PIR, reed switches)
- I2C (BME280, MPU6050, BH1750)
- SPI (MCP3008, MAX31855, ADXL345)

Created: December 15, 2025
"""

from kagami_hal.adapters.embedded.sensors.camera import CameraSensor
from kagami_hal.adapters.embedded.sensors.gpio import (
    GPIOEdge,
    GPIOMode,
    GPIOSensor,
    PIRSensor,
    ReedSwitchSensor,
)
from kagami_hal.adapters.embedded.sensors.i2c import (
    BH1750Sensor,
    BME280Sensor,
    I2CAddress,
    I2CSensor,
    MPU6050Sensor,
)
from kagami_hal.adapters.embedded.sensors.spi import (
    ADXL345Sensor,
    MAX31855Sensor,
    MCP3008Sensor,
    SPIMode,
    SPISensor,
)

__all__ = [
    "ADXL345Sensor",
    "BH1750Sensor",
    "BME280Sensor",
    # Camera
    "CameraSensor",
    "GPIOEdge",
    "GPIOMode",
    # GPIO
    "GPIOSensor",
    "I2CAddress",
    # I2C
    "I2CSensor",
    "MAX31855Sensor",
    "MCP3008Sensor",
    "MPU6050Sensor",
    "PIRSensor",
    "ReedSwitchSensor",
    "SPIMode",
    # SPI
    "SPISensor",
]
