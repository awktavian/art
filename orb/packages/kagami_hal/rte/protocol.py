"""鏡 RTE Protocol Definition.

Defines the protocol contract for Real-Time Executor backends.

Wire Format:
    COMMAND:arg1,arg2,...\\n
    RESPONSE:data\\n

Commands (Host → RTE):
    PAT:n       Set LED pattern (0-15)
    BRT:n       Set brightness (0-255)
    COL:r,g,b   Set override color
    FRM:hex     Raw LED frame data
    AUD:cmd,... Audio subsystem command
    SEN:id      Read sensor value
    PWR:mode    Set power mode
    PNG         Ping (heartbeat)
    STS         Request status
    RST         Reset to defaults
    VER:m.n     Request protocol version

Responses (RTE → Host):
    ACK:v       Version acknowledgement
    PON         Pong (heartbeat response)
    STS:p,b,f   Status (pattern, brightness, frames)
    SEN:id,v    Sensor reading
    BTN         Button pressed
    ERR:code    Error occurred
    OK          Command succeeded

Created: January 2, 2026
Colony: Nexus (e₄)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_hal.rte.types import RTEEvent, RTEStatus


class RTECommand(Enum):
    """Commands that can be sent to an RTE backend.

    Each command has a wire format prefix for serialization.
    """

    # LED Commands
    LED_PATTERN = "PAT"  # Set animation pattern
    LED_BRIGHTNESS = "BRT"  # Set brightness (0-255)
    LED_COLOR = "COL"  # Set RGB color override
    LED_FRAME = "FRM"  # Raw frame data (hex)

    # Audio Commands
    AUDIO_PLAY = "APL"  # Play audio
    AUDIO_STOP = "AST"  # Stop audio
    AUDIO_VOLUME = "AVL"  # Set volume

    # Sensor Commands
    SENSOR_READ = "SRD"  # Read sensor value
    SENSOR_SUBSCRIBE = "SSB"  # Subscribe to sensor updates

    # Power Commands
    POWER_MODE = "PWR"  # Set power mode
    POWER_SLEEP = "SLP"  # Enter sleep mode

    # System Commands
    PING = "PNG"  # Heartbeat
    STATUS = "STS"  # Request status
    RESET = "RST"  # Reset to defaults
    VERSION = "VER"  # Protocol version


class RTEResponse(Enum):
    """Responses from an RTE backend."""

    VERSION_ACK = "ACK"  # Version acknowledgement
    PONG = "PON"  # Heartbeat response
    STATUS = "STS"  # Status response
    SENSOR = "SEN"  # Sensor reading
    BUTTON = "BTN"  # Button event
    ERROR = "ERR"  # Error response
    OK = "OK"  # Success response


class RTEError(Exception):
    """Error from RTE backend.

    Attributes:
        code: Error code
        message: Human-readable message
    """

    # Standard error codes
    UNKNOWN_COMMAND = 1
    INVALID_ARGS = 2
    HARDWARE_FAILURE = 3
    TIMEOUT = 4
    BUFFER_OVERFLOW = 5
    VERSION_MISMATCH = 6
    DISCONNECTED = 7

    def __init__(self, code: int, message: str = ""):
        self.code = code
        self.message = message or self._default_message(code)
        super().__init__(f"RTE Error {code}: {self.message}")

    @staticmethod
    def _default_message(code: int) -> str:
        """Get default message for error code."""
        messages = {
            1: "Unknown command",
            2: "Invalid arguments",
            3: "Hardware failure",
            4: "Timeout",
            5: "Buffer overflow",
            6: "Version mismatch",
            7: "Disconnected",
        }
        return messages.get(code, "Unknown error")


def encode_command(cmd: RTECommand, *args: Any) -> bytes:
    """Encode a command for wire transmission.

    Args:
        cmd: The command to encode
        *args: Command arguments

    Returns:
        Encoded command bytes (newline-terminated)

    Example:
        >>> encode_command(RTECommand.LED_PATTERN, 1)
        b'PAT:1\\n'
        >>> encode_command(RTECommand.LED_COLOR, 255, 128, 0)
        b'COL:255,128,0\\n'
    """
    if not args:
        return f"{cmd.value}\n".encode()

    args_str = ",".join(str(a) for a in args)
    return f"{cmd.value}:{args_str}\n".encode()


def parse_response(data: bytes) -> tuple[RTEResponse, list[str]]:
    """Parse a response from wire format.

    Args:
        data: Raw response bytes

    Returns:
        Tuple of (response_type, arguments)

    Raises:
        RTEError: If response indicates an error
        ValueError: If response is malformed

    Example:
        >>> parse_response(b'STS:1,128,1000\\n')
        (RTEResponse.STATUS, ['1', '128', '1000'])
    """
    line = data.decode().strip()

    if ":" in line:
        prefix, args_str = line.split(":", 1)
        args = args_str.split(",")
    else:
        prefix = line
        args = []

    # Check for error
    if prefix == "ERR":
        code = int(args[0]) if args else 0
        raise RTEError(code)

    # Map prefix to response type
    for resp in RTEResponse:
        if resp.value == prefix:
            return resp, args

    raise ValueError(f"Unknown response: {prefix}")


class RTEBackend(ABC):
    """Abstract protocol for Real-Time Executor backends.

    All RTE implementations must implement this protocol.

    The RTE Backend provides:
    - Deterministic timing for LED animations (60fps)
    - Sample-accurate audio I2S
    - Sub-millisecond button latency
    - Hardware abstraction for embedded I/O

    Safety Note:
        RTE does NOT validate commands for safety.
        SafeHAL enforces h(x) >= 0 BEFORE commands reach RTE.

    Example:
        >>> rte = PicoRTE("/dev/ttyACM0")
        >>> await rte.initialize()
        >>> await rte.send_command(RTECommand.LED_PATTERN, 1)
        >>> status = await rte.get_status()
        >>> await rte.shutdown()
    """

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the RTE backend.

        Returns:
            True if initialization succeeded
        """
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the RTE backend and release resources."""
        ...

    @abstractmethod
    async def send_command(self, cmd: RTECommand, *args: Any) -> str:
        """Send a command to the RTE.

        Args:
            cmd: Command to send
            *args: Command arguments

        Returns:
            Response string from RTE

        Raises:
            RTEError: If command fails
        """
        ...

    @abstractmethod
    async def get_status(self) -> RTEStatus:
        """Get current RTE status.

        Returns:
            RTEStatus with current state
        """
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if backend is connected.

        Returns:
            True if connected and ready
        """
        ...

    async def ping(self) -> bool:
        """Send heartbeat ping.

        Returns:
            True if pong received
        """
        try:
            response = await self.send_command(RTECommand.PING)
            return response.startswith("PON")
        except RTEError:
            return False

    async def poll_events(self) -> list[RTEEvent]:
        """Poll for events from the RTE.

        Override in backends that support async events.

        Returns:
            List of pending events (may be empty)
        """
        return []

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    async def set_pattern(self, pattern: int) -> None:
        """Set LED animation pattern.

        Args:
            pattern: Pattern ID (0-15)
        """
        await self.send_command(RTECommand.LED_PATTERN, pattern)

    async def set_brightness(self, level: int) -> None:
        """Set LED brightness.

        Args:
            level: Brightness (0-255)
        """
        await self.send_command(RTECommand.LED_BRIGHTNESS, min(255, max(0, level)))

    async def set_color(self, r: int, g: int, b: int) -> None:
        """Set LED color override.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        await self.send_command(RTECommand.LED_COLOR, r, g, b)

    async def show_idle(self) -> None:
        """Show idle pattern (static colony colors)."""
        await self.set_pattern(0)

    async def show_listening(self) -> None:
        """Show listening pattern (pulsing)."""
        await self.set_pattern(3)

    async def show_processing(self) -> None:
        """Show processing pattern (spinning)."""
        await self.set_pattern(2)

    async def show_success(self) -> None:
        """Show success pattern (green flash)."""
        await self.set_pattern(5)

    async def show_error(self) -> None:
        """Show error pattern (red flash)."""
        await self.set_pattern(6)

    async def show_safety(self, h_x: float) -> None:
        """Show safety status based on CBF value.

        Args:
            h_x: Current CBF barrier value
        """
        if h_x >= 0.5:
            await self.set_pattern(13)  # Safe (green)
        elif h_x >= 0.0:
            await self.set_pattern(14)  # Caution (yellow)
        else:
            await self.set_pattern(15)  # Violation (red)


__all__ = [
    "RTEBackend",
    "RTECommand",
    "RTEError",
    "RTEResponse",
    "encode_command",
    "parse_response",
]
