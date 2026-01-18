"""鏡 Virtual RTE Backend — Testing/Simulation.

Real-Time Executor backend for testing and headless operation.
Records all commands for verification without requiring hardware.

Use Cases:
- Unit testing
- CI/CD pipelines
- Development without hardware
- Simulation and playback

Features:
- Command logging with timestamps
- State tracking
- Configurable latency simulation
- Event injection for testing

Usage:
    from kagami_hal.rte import VirtualRTE, RTECommand

    rte = VirtualRTE()
    await rte.initialize()

    await rte.send_command(RTECommand.LED_PATTERN, 1)

    # Check recorded commands
    assert len(rte.command_log) == 1
    assert rte.command_log[0].command == RTECommand.LED_PATTERN

    # Inject events for testing
    rte.inject_event(RTEEvent.button_pressed())

    events = await rte.poll_events()
    assert len(events) == 1

Created: January 2, 2026
Colony: Crystal (e₇) — Testing and verification
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from kagami_hal.rte.protocol import (
    RTEBackend,
    RTECommand,
    RTEError,
)
from kagami_hal.rte.types import LEDPattern, RTEEvent, RTEStatus

logger = logging.getLogger(__name__)


@dataclass
class CommandRecord:
    """Record of a command sent to Virtual RTE.

    Attributes:
        command: The command that was sent
        args: Command arguments
        timestamp: When the command was received
        response: The response that was returned
    """

    command: RTECommand
    args: tuple[Any, ...]
    timestamp: datetime = field(default_factory=datetime.now)
    response: str = "OK"


class VirtualRTE(RTEBackend):
    """Virtual Real-Time Executor for testing.

    Simulates an RTE backend without hardware, recording all commands
    for verification and allowing event injection for testing.

    Attributes:
        command_log: List of all commands received
        simulate_latency_ms: Simulated command latency
        fail_next: If True, next command will fail with error
    """

    def __init__(
        self,
        simulate_latency_ms: int = 0,
        max_log_size: int = 1000,
    ):
        """Initialize Virtual RTE.

        Args:
            simulate_latency_ms: Simulated command latency
            max_log_size: Maximum number of commands to log
        """
        self._simulate_latency_ms = simulate_latency_ms
        self._max_log_size = max_log_size

        # State
        self._connected = False
        self._pattern = LEDPattern.IDLE
        self._brightness = 128
        self._override_color: tuple[int, int, int] | None = None
        self._frame_count = 0

        # Logging
        self._command_log: deque[CommandRecord] = deque(maxlen=max_log_size)

        # Event queue for testing
        self._event_queue: deque[RTEEvent] = deque()

        # Testing controls
        self._fail_next = False
        self._fail_code = RTEError.HARDWARE_FAILURE

    @property
    def command_log(self) -> list[CommandRecord]:
        """Get list of recorded commands."""
        return list(self._command_log)

    @property
    def state(self) -> dict[str, Any]:
        """Get current simulated state."""
        return {
            "pattern": self._pattern,
            "brightness": self._brightness,
            "override_color": self._override_color,
            "frame_count": self._frame_count,
            "connected": self._connected,
        }

    async def initialize(self) -> bool:
        """Initialize virtual RTE.

        Returns:
            Always True (virtual RTE is always available)
        """
        self._connected = True
        logger.info("✓ Virtual RTE initialized (testing mode)")
        return True

    async def shutdown(self) -> None:
        """Shutdown virtual RTE."""
        self._connected = False
        logger.info("Virtual RTE shutdown complete")

    async def send_command(self, cmd: RTECommand, *args: Any) -> str:
        """Process command and record it.

        Args:
            cmd: Command to process
            *args: Command arguments

        Returns:
            Response string

        Raises:
            RTEError: If fail_next is set
        """
        # Simulate latency
        if self._simulate_latency_ms > 0:
            await asyncio.sleep(self._simulate_latency_ms / 1000.0)

        # Check for forced failure
        if self._fail_next:
            self._fail_next = False
            raise RTEError(self._fail_code)

        # Process command
        response = self._process_command(cmd, args)

        # Log command
        record = CommandRecord(
            command=cmd,
            args=args,
            response=response,
        )
        self._command_log.append(record)

        logger.debug(f"Virtual RTE: {cmd.value}:{args} -> {response}")

        return response

    def _process_command(self, cmd: RTECommand, args: tuple[Any, ...]) -> str:
        """Process a command and update state.

        Args:
            cmd: Command to process
            args: Command arguments

        Returns:
            Response string
        """
        if cmd == RTECommand.LED_PATTERN:
            self._pattern = LEDPattern(int(args[0]))
            return "OK"

        elif cmd == RTECommand.LED_BRIGHTNESS:
            self._brightness = min(255, max(0, int(args[0])))
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

        elif cmd == RTECommand.VERSION:
            return "ACK:1.0"

        else:
            return "OK"

    async def get_status(self) -> RTEStatus:
        """Get current simulated status.

        Returns:
            RTEStatus with simulated state
        """
        return RTEStatus(
            pattern=self._pattern,
            brightness=self._brightness,
            frame_count=self._frame_count,
            connected=self._connected,
            latency_us=self._simulate_latency_ms * 1000,
            version="1.0",
        )

    def is_connected(self) -> bool:
        """Check if virtual RTE is "connected".

        Returns:
            True if initialized
        """
        return self._connected

    async def poll_events(self) -> list[RTEEvent]:
        """Get injected events.

        Returns:
            List of injected events
        """
        events = []
        while self._event_queue:
            events.append(self._event_queue.popleft())
        return events

    # =========================================================================
    # Testing Utilities
    # =========================================================================

    def inject_event(self, event: RTEEvent) -> None:
        """Inject an event for testing.

        Args:
            event: Event to inject

        Example:
            >>> rte.inject_event(RTEEvent.button_pressed())
            >>> events = await rte.poll_events()
            >>> assert len(events) == 1
        """
        self._event_queue.append(event)

    def set_fail_next(self, code: int = RTEError.HARDWARE_FAILURE) -> None:
        """Make the next command fail with an error.

        Args:
            code: Error code to return

        Example:
            >>> rte.set_fail_next()
            >>> with pytest.raises(RTEError):
            ...     await rte.send_command(RTECommand.PING)
        """
        self._fail_next = True
        self._fail_code = code

    def clear_log(self) -> None:
        """Clear the command log."""
        self._command_log.clear()

    def reset_state(self) -> None:
        """Reset all state to defaults."""
        self._pattern = LEDPattern.IDLE
        self._brightness = 128
        self._override_color = None
        self._frame_count = 0
        self._fail_next = False
        self._event_queue.clear()
        self._command_log.clear()

    def simulate_frames(self, count: int) -> None:
        """Simulate frame rendering.

        Args:
            count: Number of frames to simulate
        """
        self._frame_count += count

    def get_last_command(self) -> CommandRecord | None:
        """Get the last command received.

        Returns:
            Last CommandRecord or None if log is empty
        """
        if self._command_log:
            return self._command_log[-1]
        return None

    def get_commands_by_type(self, cmd: RTECommand) -> list[CommandRecord]:
        """Get all commands of a specific type.

        Args:
            cmd: Command type to filter by

        Returns:
            List of matching CommandRecords
        """
        return [r for r in self._command_log if r.command == cmd]

    def assert_command_sent(
        self,
        cmd: RTECommand,
        args: tuple[Any, ...] | None = None,
    ) -> None:
        """Assert a command was sent.

        Args:
            cmd: Command to look for
            args: Optional exact args to match

        Raises:
            AssertionError: If command not found
        """
        for record in self._command_log:
            if record.command == cmd:
                if args is None or record.args == args:
                    return

        raise AssertionError(f"Command {cmd.value} with args {args} not found in log")


__all__ = [
    "CommandRecord",
    "VirtualRTE",
]
