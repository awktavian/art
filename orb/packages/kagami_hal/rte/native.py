"""鏡 Native RTE Backend — Direct Hardware Access.

Real-Time Executor backend using direct Linux hardware access.
Provides software timing (less precise than Pico) for systems
without a coprocessor.

Use Cases:
- Desktop development without Pico hardware
- High-powered embedded systems (Jetson, Pi 5)
- Systems where ~10ms timing jitter is acceptable

Limitations:
- LED animations may have visible jitter
- Button latency ~10-50ms
- No audio I2S support

Usage:
    from kagami_hal.rte import NativeRTE, RTECommand

    rte = NativeRTE()
    await rte.initialize()

    await rte.send_command(RTECommand.LED_PATTERN, 1)

    await rte.shutdown()

Created: January 2, 2026
Colony: Forge (e₂) — Direct implementation
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from kagami_hal.rte.protocol import (
    RTEBackend,
    RTECommand,
    RTEError,
)
from kagami_hal.rte.types import LEDPattern, RTEEvent, RTEStatus

logger = logging.getLogger(__name__)

# Check for hardware libraries
NEOPIXEL_AVAILABLE = False
try:
    import board
    import neopixel

    NEOPIXEL_AVAILABLE = True
except ImportError:
    pass

GPIO_AVAILABLE = False
try:
    import RPi.GPIO as GPIO

    GPIO_AVAILABLE = True
except ImportError:
    pass

GPIOD_AVAILABLE = False
try:
    import gpiod

    GPIOD_AVAILABLE = True
except ImportError:
    pass


class NativeRTE(RTEBackend):
    """Native Real-Time Executor using direct hardware access.

    Provides software-timed LED control and GPIO input.
    Less precise than Pico but works without additional hardware.

    Attributes:
        led_pin: GPIO pin for WS2812 data (default 18)
        led_count: Number of LEDs (default 12)
        button_pin: GPIO pin for button (default 17)
    """

    def __init__(
        self,
        led_pin: int = 18,
        led_count: int = 12,
        button_pin: int = 17,
        brightness: float = 0.5,
    ):
        """Initialize Native RTE.

        Args:
            led_pin: GPIO pin for WS2812 data line
            led_count: Number of LEDs in ring
            button_pin: GPIO pin for button input
            brightness: Initial brightness (0.0-1.0)
        """
        self._led_pin = led_pin
        self._led_count = led_count
        self._button_pin = button_pin
        self._initial_brightness = brightness

        self._pixels: Any = None
        self._gpio_chip: Any = None
        self._button_line: Any = None

        self._connected = False
        self._pattern = LEDPattern.IDLE
        self._brightness = int(brightness * 255)
        self._override_color: tuple[int, int, int] | None = None
        self._frame_count = 0

        self._animation_task: asyncio.Task | None = None
        self._running = False

    async def initialize(self) -> bool:
        """Initialize native hardware access.

        Returns:
            True if any hardware was initialized
        """
        success = False

        # Initialize NeoPixel LEDs
        if NEOPIXEL_AVAILABLE:
            try:
                # board.D18 is GPIO 18
                pin = getattr(board, f"D{self._led_pin}", board.D18)
                self._pixels = neopixel.NeoPixel(
                    pin,
                    self._led_count,
                    brightness=self._initial_brightness,
                    auto_write=False,
                )
                logger.info(f"✓ NeoPixel initialized on GPIO {self._led_pin}")
                success = True
            except Exception as e:
                logger.warning(f"NeoPixel init failed: {e}")

        # Initialize GPIO button
        if GPIOD_AVAILABLE and Path("/dev/gpiochip0").exists():
            try:
                self._gpio_chip = gpiod.Chip("/dev/gpiochip0")
                self._button_line = self._gpio_chip.get_line(self._button_pin)
                self._button_line.request(
                    consumer="kagami_rte",
                    type=gpiod.LINE_REQ_EV_BOTH_EDGES,
                    flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP,
                )
                logger.info(f"✓ GPIO button initialized on pin {self._button_pin}")
                success = True
            except Exception as e:
                logger.warning(f"GPIOD init failed: {e}")

        elif GPIO_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self._button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                logger.info(f"✓ RPi.GPIO button initialized on pin {self._button_pin}")
                success = True
            except Exception as e:
                logger.warning(f"RPi.GPIO init failed: {e}")

        # If no hardware available, run in virtual mode
        if not success:
            logger.info("No hardware available, running in virtual mode")
            success = True

        self._connected = success

        # Start animation loop
        if success:
            self._running = True
            self._animation_task = asyncio.create_task(self._animation_loop())

        return success

    async def shutdown(self) -> None:
        """Shutdown native hardware."""
        self._running = False
        self._connected = False

        # Stop animation task
        if self._animation_task:
            self._animation_task.cancel()
            try:
                await self._animation_task
            except asyncio.CancelledError:
                pass

        # Cleanup NeoPixel
        if self._pixels:
            try:
                self._pixels.fill((0, 0, 0))
                self._pixels.show()
                self._pixels.deinit()
            except Exception:
                pass
            self._pixels = None

        # Cleanup GPIO
        if self._button_line:
            try:
                self._button_line.release()
            except Exception:
                pass
            self._button_line = None

        if self._gpio_chip:
            try:
                self._gpio_chip.close()
            except Exception:
                pass
            self._gpio_chip = None

        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup(self._button_pin)
            except Exception:
                pass

        logger.info("Native RTE shutdown complete")

    async def send_command(self, cmd: RTECommand, *args: Any) -> str:
        """Execute command directly on hardware.

        Args:
            cmd: Command to execute
            *args: Command arguments

        Returns:
            Response string
        """
        try:
            if cmd == RTECommand.LED_PATTERN:
                self._pattern = LEDPattern(int(args[0]))
                return "OK"

            elif cmd == RTECommand.LED_BRIGHTNESS:
                self._brightness = min(255, max(0, int(args[0])))
                if self._pixels:
                    self._pixels.brightness = self._brightness / 255.0
                return "OK"

            elif cmd == RTECommand.LED_COLOR:
                self._override_color = (int(args[0]), int(args[1]), int(args[2]))
                return "OK"

            elif cmd == RTECommand.PING:
                return "PON"

            elif cmd == RTECommand.STATUS:
                return f"STS:{self._pattern},{self._brightness},{self._frame_count}"

            elif cmd == RTECommand.RESET:
                self._pattern = LEDPattern.IDLE
                self._brightness = 128
                self._override_color = None
                return "OK"

            else:
                raise RTEError(RTEError.UNKNOWN_COMMAND)

        except (ValueError, IndexError) as e:
            raise RTEError(RTEError.INVALID_ARGS, str(e)) from e

    async def get_status(self) -> RTEStatus:
        """Get current status.

        Returns:
            RTEStatus with current state
        """
        return RTEStatus(
            pattern=self._pattern,
            brightness=self._brightness,
            frame_count=self._frame_count,
            connected=self._connected,
            latency_us=0,  # Direct access has no latency
            version="1.0",
        )

    def is_connected(self) -> bool:
        """Check if hardware is available.

        Returns:
            True if connected
        """
        return self._connected

    async def poll_events(self) -> list[RTEEvent]:
        """Poll for button events.

        Returns:
            List of pending events
        """
        events = []

        # Check button state
        if self._button_line:
            try:
                if self._button_line.event_wait(nsec=1_000_000):  # 1ms timeout
                    event = self._button_line.event_read()
                    if event.type == gpiod.LineEvent.FALLING_EDGE:
                        events.append(RTEEvent.button_pressed())
            except Exception:
                pass

        elif GPIO_AVAILABLE:
            try:
                if GPIO.input(self._button_pin) == GPIO.LOW:
                    events.append(RTEEvent.button_pressed())
            except Exception:
                pass

        return events

    async def _animation_loop(self) -> None:
        """Background task for LED animations.

        Runs at ~60fps when hardware is available.
        """
        frame_time = 1.0 / 60.0  # 60fps target

        while self._running:
            start = time.perf_counter()

            if self._pixels:
                self._render_frame()
                self._pixels.show()

            self._frame_count += 1

            # Calculate sleep time to maintain frame rate
            elapsed = time.perf_counter() - start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0)  # Yield to other tasks

    def _render_frame(self) -> None:
        """Render current animation frame to LED buffer."""
        if not self._pixels:
            return

        t = self._frame_count / 60.0  # Time in seconds

        # If override color set, use it
        if self._override_color:
            self._pixels.fill(self._override_color)
            return

        # Render based on pattern
        if self._pattern == LEDPattern.IDLE:
            self._render_idle()
        elif self._pattern == LEDPattern.BREATHING:
            self._render_breathing(t)
        elif self._pattern == LEDPattern.SPIN:
            self._render_spin(t)
        elif self._pattern == LEDPattern.PULSE:
            self._render_pulse(t)
        elif self._pattern == LEDPattern.FLASH:
            self._render_flash((0, 255, 0))  # Green
        elif self._pattern == LEDPattern.ERROR_FLASH:
            self._render_flash((255, 0, 0))  # Red
        elif self._pattern == LEDPattern.RAINBOW:
            self._render_rainbow(t)
        elif self._pattern == LEDPattern.SAFETY_SAFE:
            self._pixels.fill((0, 255, 0))
        elif self._pattern == LEDPattern.SAFETY_CAUTION:
            self._pixels.fill((255, 255, 0))
        elif self._pattern == LEDPattern.SAFETY_VIOLATION:
            self._render_flash((255, 0, 0))
        else:
            self._render_idle()

    def _render_idle(self) -> None:
        """Render static colony colors."""
        colors = [
            (232, 33, 39),  # Spark
            (232, 33, 39),  # Spark
            (247, 148, 29),  # Forge
            (247, 148, 29),  # Forge
            (255, 199, 44),  # Flow
            (255, 199, 44),  # Flow
            (0, 166, 81),  # Nexus
            (0, 166, 81),  # Nexus
            (0, 174, 239),  # Beacon
            (0, 174, 239),  # Beacon
            (146, 39, 143),  # Grove
            (237, 30, 121),  # Crystal
        ]
        for i, color in enumerate(colors[: self._led_count]):
            self._pixels[i] = color

    def _render_breathing(self, t: float) -> None:
        """Render breathing animation."""
        import math

        brightness = (math.sin(t * 2) + 1) / 2  # 0-1 sine wave
        self._render_idle()
        for i in range(self._led_count):
            r, g, b = self._pixels[i]
            self._pixels[i] = (
                int(r * brightness),
                int(g * brightness),
                int(b * brightness),
            )

    def _render_spin(self, t: float) -> None:
        """Render spinning chase animation."""
        head = int(t * 10) % self._led_count
        self._pixels.fill((0, 0, 0))
        for i in range(3):
            idx = (head - i) % self._led_count
            brightness = 1.0 - (i * 0.3)
            self._pixels[idx] = (
                int(0 * brightness),
                int(174 * brightness),
                int(239 * brightness),
            )

    def _render_pulse(self, t: float) -> None:
        """Render center-out pulse animation."""
        phase = (t * 3) % 1.0  # Pulse phase
        for i in range(self._led_count):
            # Distance from "center" (LED 0)
            dist = min(i, self._led_count - i) / (self._led_count / 2)
            brightness = max(0, 1.0 - abs(dist - phase) * 3)
            self._pixels[i] = (
                int(0 * brightness),
                int(166 * brightness),
                int(81 * brightness),
            )

    def _render_flash(self, color: tuple[int, int, int]) -> None:
        """Render flash animation."""
        if (self._frame_count // 6) % 2 == 0:
            self._pixels.fill(color)
        else:
            self._pixels.fill((0, 0, 0))

    def _render_rainbow(self, t: float) -> None:
        """Render rainbow HSV rotation."""
        for i in range(self._led_count):
            hue = (i / self._led_count + t * 0.1) % 1.0
            r, g, b = self._hsv_to_rgb(hue, 1.0, 1.0)
            self._pixels[i] = (int(r * 255), int(g * 255), int(b * 255))

    @staticmethod
    def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[float, float, float]:
        """Convert HSV to RGB."""
        import colorsys

        return colorsys.hsv_to_rgb(h, s, v)


__all__ = [
    "NativeRTE",
]
