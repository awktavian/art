"""HAL Protocol Definitions.

These protocols define the contracts for HAL adapters.
They import data types from .data_types to avoid circular dependencies with implementations.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from kagami_hal.data_types import (
    AudioConfig,
    BatteryStatus,
    DisplayInfo,
    DisplayMode,
    InputEvent,
    InputType,
    PowerMode,
    PowerStats,
    # sEMG types
    SEMGFrame,
    SEMGGesture,
    SEMGGestureResult,
    SEMGHandwritingResult,
    SEMGIntentState,
    SensorReading,
    SensorType,
    SleepMode,
    WristPose,
)


@runtime_checkable
class HALAdapter(Protocol):
    """Base protocol for all HAL adapters.

    Note: initialize() accepts optional config for adapters that need it.
    Subprotocols may narrow the config type (e.g., AudioAdapterProtocol uses AudioConfig).
    """

    async def initialize(self, config: Any | None = None) -> bool: ...

    async def shutdown(self) -> None: ...


@runtime_checkable
class DisplayAdapterProtocol(HALAdapter, Protocol):
    """Protocol for display adapters."""

    async def get_info(self) -> DisplayInfo:
        """Get display capabilities."""
        ...

    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to display."""
        ...

    async def capture_screen(self) -> bytes | None:
        """Capture current screen content."""
        ...

    async def clear(self, color: int = 0x000000) -> None:
        """Clear display to color."""
        ...

    async def set_brightness(self, level: float) -> None:
        """Set display brightness."""
        ...

    async def set_mode(self, mode: DisplayMode) -> None:
        """Set display power mode."""
        ...


@runtime_checkable
class AudioAdapterProtocol(HALAdapter, Protocol):
    """Protocol for audio adapters."""

    async def initialize(self, config: AudioConfig | None = None) -> bool:
        """Initialize audio adapter.

        Note: config is optional for compatibility with base HALAdapter.
        Concrete implementations should provide a default AudioConfig.
        """
        ...

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer."""
        ...

    async def record(self, duration_ms: int) -> bytes:
        """Record audio."""
        ...

    async def set_volume(self, level: float) -> None:
        """Set volume."""
        ...

    async def get_volume(self) -> float:
        """Get current volume."""
        ...


@runtime_checkable
class InputAdapterProtocol(HALAdapter, Protocol):
    """Protocol for input adapters."""

    async def subscribe(
        self, input_type: InputType, callback: Callable[[InputEvent], Awaitable[None]]
    ) -> None:
        """Subscribe to input events."""
        ...

    async def unsubscribe(self, input_type: InputType) -> None:
        """Unsubscribe from input events."""
        ...

    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking)."""
        ...

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic input event."""
        ...


@runtime_checkable
class SensorAdapterProtocol(HALAdapter, Protocol):
    """Protocol for sensor adapters."""

    async def list_sensors(self) -> list[SensorType]:
        """List available sensors."""
        ...

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value."""
        ...

    async def subscribe(
        self,
        sensor: SensorType,
        callback: Callable[[SensorReading], Awaitable[None]],
        rate_hz: int = 10,
    ) -> None:
        """Subscribe to sensor updates."""
        ...

    async def unsubscribe(self, sensor: SensorType) -> None:
        """Unsubscribe from sensor."""
        ...


@runtime_checkable
class PowerAdapterProtocol(HALAdapter, Protocol):
    """Protocol for power adapters."""

    async def get_battery_status(self) -> BatteryStatus:
        """Get battery status."""
        ...

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set system power mode."""
        ...

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode."""
        ...

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency (DVFS)."""
        ...

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode."""
        ...

    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics."""
        ...


@runtime_checkable
class SEMGAdapterProtocol(HALAdapter, Protocol):
    """Protocol for sEMG neural interface adapters.

    Based on Meta Neural Band interface (Nature, July 2025).
    Supports:
    - Raw sEMG frame streaming (2kHz, 16-48 channels)
    - Discrete gesture classification (9 gestures)
    - Continuous intent inference (Alyx-style)
    - Handwriting recognition (air writing)
    - Wrist pose tracking
    """

    # --- Device Info ---

    async def get_device_info(self) -> dict:
        """Get neural band device information.

        Returns:
            Dict with: device_id, electrode_count, sample_rate_hz,
            firmware_version, battery_level, connection_status
        """
        ...

    async def get_electrode_status(self) -> list[float]:
        """Get per-electrode contact quality.

        Returns:
            List of contact quality values (0-1) for each electrode.
            Values < 0.5 indicate poor contact.
        """
        ...

    # --- Raw Stream ---

    async def subscribe_frames(
        self,
        callback: Callable[[SEMGFrame], Awaitable[None]],
        sample_rate_hz: int = 2000,
    ) -> None:
        """Subscribe to raw sEMG frame stream.

        Args:
            callback: Async callback receiving SEMGFrame
            sample_rate_hz: Target sample rate (device may not support all rates)
        """
        ...

    async def unsubscribe_frames(self) -> None:
        """Stop raw frame streaming."""
        ...

    # --- Discrete Gestures ---

    async def subscribe_gestures(
        self,
        callback: Callable[[SEMGGestureResult], Awaitable[None]],
        gestures: list[SEMGGesture] | None = None,
    ) -> None:
        """Subscribe to discrete gesture events.

        Args:
            callback: Async callback receiving SEMGGestureResult
            gestures: Optional filter for specific gestures (None = all)
        """
        ...

    async def unsubscribe_gestures(self) -> None:
        """Stop gesture event streaming."""
        ...

    # --- Continuous Intent (Alyx-style) ---

    async def subscribe_intent(
        self,
        callback: Callable[[SEMGIntentState], Awaitable[None]],
        update_rate_hz: int = 60,
    ) -> None:
        """Subscribe to continuous intent state.

        This is the Alyx-style interface: continuous tracking of
        what the user is trying to do, not just discrete events.

        Args:
            callback: Async callback receiving SEMGIntentState
            update_rate_hz: How often to update intent state
        """
        ...

    async def unsubscribe_intent(self) -> None:
        """Stop intent streaming."""
        ...

    # --- Handwriting ---

    async def start_handwriting(self) -> None:
        """Start handwriting recognition mode.

        User can write in the air; characters recognized continuously.
        """
        ...

    async def stop_handwriting(self) -> SEMGHandwritingResult | None:
        """Stop handwriting and get final result.

        Returns:
            Recognized text and character details, or None if nothing written.
        """
        ...

    async def subscribe_handwriting(
        self,
        callback: Callable[[SEMGHandwritingResult], Awaitable[None]],
    ) -> None:
        """Subscribe to incremental handwriting results.

        Callback fires as each character is recognized.
        """
        ...

    # --- Wrist Pose ---

    async def subscribe_wrist_pose(
        self,
        callback: Callable[[WristPose], Awaitable[None]],
        update_rate_hz: int = 60,
    ) -> None:
        """Subscribe to continuous wrist pose tracking.

        Args:
            callback: Async callback receiving WristPose
            update_rate_hz: Pose update rate
        """
        ...

    async def unsubscribe_wrist_pose(self) -> None:
        """Stop wrist pose streaming."""
        ...
