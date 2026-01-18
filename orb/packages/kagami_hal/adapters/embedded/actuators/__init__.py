"""Embedded Actuator Modules.

Provides actuator implementations for embedded platforms:
- Display (SSD1306 OLED, ST7735 TFT)
- GPIO (LEDs, relays, motors)
- PWM (servos, ESCs, hardware PWM)
- LED Ring (WS2812 via RTE backend)

Created: December 15, 2025
Updated: January 2, 2026 - Added LED Ring with RTE backend
"""

from kagami_hal.adapters.embedded.actuators.display import (
    SSD1306Display,
    ST7735Display,
)
from kagami_hal.adapters.embedded.actuators.gpio import (
    GPIOActuator,
    GPIOOutputMode,
    LEDActuator,
    MotorActuator,
    RelayActuator,
)
from kagami_hal.adapters.embedded.actuators.led_ring import (
    LEDRingActuator,
)
from kagami_hal.adapters.embedded.actuators.pwm import (
    ESCActuator,
    PWMActuator,
    ServoActuator,
)

__all__ = [
    "ESCActuator",
    # GPIO
    "GPIOActuator",
    "GPIOOutputMode",
    "LEDActuator",
    # LED Ring (RTE backend)
    "LEDRingActuator",
    "MotorActuator",
    # PWM
    "PWMActuator",
    "RelayActuator",
    # Display
    "SSD1306Display",
    "ST7735Display",
    "ServoActuator",
]
