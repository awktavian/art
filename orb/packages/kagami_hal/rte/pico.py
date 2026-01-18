"""鏡 Pico RTE Backend — UART Communication.

Real-Time Executor backend using a Raspberry Pi Pico coprocessor
connected via UART. The Pico provides deterministic timing for:
- LED ring animations (60fps, <100µs latency)
- Button input (<1ms latency)
- Audio I2S (future)

Wire Connection:
    Pi GPIO 14 (TXD) → Pico GPIO 1 (RX)
    Pi GPIO 15 (RXD) → Pico GPIO 0 (TX)
    Pi GND           → Pico GND
    Pi 5V            → Pico VBUS

Usage:
    from kagami_hal.rte import PicoRTE, RTECommand

    rte = PicoRTE("/dev/ttyACM0")
    await rte.initialize()

    await rte.send_command(RTECommand.LED_PATTERN, 1)
    status = await rte.get_status()

    await rte.shutdown()

Created: January 2, 2026
Colony: Nexus (e₄) — Bridge between Pi and Pico
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from kagami_hal.rte.protocol import (
    RTEBackend,
    RTECommand,
    RTEError,
    encode_command,
)
from kagami_hal.rte.types import RTEEvent, RTEStatus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Check for serial libraries
SERIAL_AVAILABLE = False
try:
    import serial
    import serial.tools.list_ports

    SERIAL_AVAILABLE = True
except ImportError:
    pass

TOKIO_SERIAL_AVAILABLE = False
try:
    import aioserial

    TOKIO_SERIAL_AVAILABLE = True
except ImportError:
    pass


def find_pico_ports() -> list[str]:
    """Find connected Pico devices.

    Returns:
        List of port paths that appear to be Pico devices
    """
    if not SERIAL_AVAILABLE:
        return []

    pico_ports = []
    for port in serial.tools.list_ports.comports():
        # Check for Pico USB identifiers
        is_pico = (
            "ACM" in port.device
            or "usbmodem" in port.device
            or (port.vid == 0x2E8A)  # Raspberry Pi Foundation VID
        )
        if is_pico:
            logger.debug(f"Found potential Pico at: {port.device}")
            pico_ports.append(port.device)

    return pico_ports


class PicoRTE(RTEBackend):
    """Pico Real-Time Executor via UART.

    Communicates with Kagami Pico firmware (Embassy RTOS) over serial.
    Provides deterministic timing for LED ring and button input.

    Attributes:
        port_path: Serial port path (e.g., "/dev/ttyACM0")
        baudrate: Serial baudrate (default 115200)
        timeout_ms: Command timeout in milliseconds
    """

    def __init__(
        self,
        port_path: str | None = None,
        baudrate: int = 115200,
        timeout_ms: int = 500,
    ):
        """Initialize Pico RTE.

        Args:
            port_path: Serial port path, or None to auto-discover
            baudrate: Serial baudrate
            timeout_ms: Command timeout in milliseconds
        """
        self._port_path = port_path
        self._baudrate = baudrate
        self._timeout_ms = timeout_ms

        self._port: Any = None
        self._lock = asyncio.Lock()
        self._connected = False
        self._version = "1.0"
        self._last_latency_us = 0

    @classmethod
    def auto_discover(cls) -> PicoRTE | None:
        """Create PicoRTE with auto-discovered port.

        Returns:
            PicoRTE instance if Pico found, None otherwise
        """
        ports = find_pico_ports()
        if ports:
            logger.info(f"Auto-discovered Pico at {ports[0]}")
            return cls(ports[0])
        return None

    async def initialize(self) -> bool:
        """Initialize UART connection to Pico.

        Returns:
            True if connection established
        """
        if not SERIAL_AVAILABLE:
            logger.warning("Serial library not available")
            return False

        # Auto-discover if no port specified
        if self._port_path is None:
            ports = find_pico_ports()
            if not ports:
                logger.warning("No Pico device found")
                return False
            self._port_path = ports[0]

        try:
            logger.info(f"Connecting to Pico at {self._port_path}")

            # Use aioserial if available for async I/O
            if TOKIO_SERIAL_AVAILABLE:
                self._port = aioserial.AioSerial(
                    port=self._port_path,
                    baudrate=self._baudrate,
                    timeout=self._timeout_ms / 1000.0,
                )
            else:
                # Fall back to synchronous serial
                self._port = serial.Serial(
                    port=self._port_path,
                    baudrate=self._baudrate,
                    timeout=self._timeout_ms / 1000.0,
                )

            # Verify connection with ping
            self._connected = True
            if await self.ping():
                logger.info(f"✓ Connected to Pico coprocessor at {self._port_path}")
                return True
            else:
                logger.warning("Pico did not respond to ping")
                self._connected = False
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Pico: {e}")
            self._connected = False
            return False

    async def shutdown(self) -> None:
        """Close UART connection."""
        self._connected = False
        if self._port:
            try:
                self._port.close()
            except Exception as e:
                logger.warning(f"Error closing serial port: {e}")
            self._port = None
        logger.info("Pico RTE shutdown complete")

    async def send_command(self, cmd: RTECommand, *args: Any) -> str:
        """Send command to Pico and wait for response.

        Args:
            cmd: Command to send
            *args: Command arguments

        Returns:
            Response string from Pico

        Raises:
            RTEError: If command fails or times out
        """
        if not self._connected or not self._port:
            raise RTEError(RTEError.DISCONNECTED)

        async with self._lock:
            start_time = time.perf_counter()

            try:
                # Encode and send command
                data = encode_command(cmd, *args)

                if TOKIO_SERIAL_AVAILABLE:
                    await self._port.write_async(data)
                else:
                    self._port.write(data)
                    self._port.flush()

                logger.debug(f"Sent to Pico: {data.decode().strip()}")

                # Read response
                response = await self._read_line()

                # Calculate latency
                elapsed_us = int((time.perf_counter() - start_time) * 1_000_000)
                self._last_latency_us = elapsed_us

                logger.debug(f"Received from Pico: {response} ({elapsed_us}µs)")

                # Check for error
                if response.startswith("ERR:"):
                    code = int(response[4:]) if len(response) > 4 else 0
                    raise RTEError(code)

                return response

            except TimeoutError as e:
                raise RTEError(RTEError.TIMEOUT) from e
            except serial.SerialException as e:
                logger.error(f"Serial error: {e}")
                self._connected = False
                raise RTEError(RTEError.HARDWARE_FAILURE, str(e)) from e

    async def _read_line(self) -> str:
        """Read a line from serial port with timeout.

        Returns:
            Response line (stripped)
        """
        try:
            if TOKIO_SERIAL_AVAILABLE:
                line = await asyncio.wait_for(
                    self._port.readline_async(),
                    timeout=self._timeout_ms / 1000.0,
                )
            else:
                # Synchronous fallback with timeout
                line = await asyncio.get_event_loop().run_in_executor(None, self._port.readline)

            return line.decode().strip()

        except TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Read error: {e}")
            raise RTEError(RTEError.HARDWARE_FAILURE, str(e)) from e

    async def get_status(self) -> RTEStatus:
        """Get current Pico status.

        Returns:
            RTEStatus with current state
        """
        response = await self.send_command(RTECommand.STATUS)

        # Parse response: STS:pattern,brightness,frames
        if response.startswith("STS:"):
            parts = response[4:].split(",")
            if len(parts) >= 3:
                return RTEStatus(
                    pattern=int(parts[0]),
                    brightness=int(parts[1]),
                    frame_count=int(parts[2]),
                    connected=True,
                    latency_us=self._last_latency_us,
                    version=self._version,
                )

        # Return default status if parse failed
        return RTEStatus(connected=self._connected)

    def is_connected(self) -> bool:
        """Check if Pico is connected.

        Returns:
            True if connected
        """
        return self._connected and self._port is not None

    async def poll_events(self) -> list[RTEEvent]:
        """Poll for events from Pico.

        Returns:
            List of pending events
        """
        events = []

        if not self._connected or not self._port:
            return events

        try:
            # Check for available data (non-blocking)
            if TOKIO_SERIAL_AVAILABLE:
                if self._port.in_waiting > 0:
                    line = await self._port.readline_async()
                    event = self._parse_event(line.decode().strip())
                    if event:
                        events.append(event)
            else:
                if self._port.in_waiting > 0:
                    line = self._port.readline().decode().strip()
                    event = self._parse_event(line)
                    if event:
                        events.append(event)

        except Exception as e:
            logger.warning(f"Error polling events: {e}")

        return events

    def _parse_event(self, line: str) -> RTEEvent | None:
        """Parse an event line from Pico.

        Args:
            line: Raw event line

        Returns:
            RTEEvent or None if not an event
        """
        if line.startswith("BTN"):
            return RTEEvent.button_pressed()
        elif line.startswith("ERR:"):
            code = int(line[4:]) if len(line) > 4 else 0
            return RTEEvent.error(code)
        return None


__all__ = [
    "PicoRTE",
    "find_pico_ports",
]
