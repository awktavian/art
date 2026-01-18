"""HAL I/O Manager.

Provides centralized management of all HAL I/O operations,
including sensor polling, actuator scheduling, and event routing.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from kagami_hal.interface.actuators import IActuator
from kagami_hal.interface.platform import PlatformCapabilities
from kagami_hal.interface.safe_hal import SafeHAL
from kagami_hal.interface.sensors import ISensor, SensorReading

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class IOEvent:
    """An I/O event from a sensor or actuator."""

    source: str
    event_type: str
    timestamp: datetime
    data: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamStats:
    """Statistics for a sensor stream."""

    total_samples: int = 0
    dropped_samples: int = 0
    avg_latency_ms: float = 0.0
    last_sample_time: datetime | None = None


@dataclass
class StreamHandle:
    """Handle for a running sensor stream."""

    stream_id: str
    sensor: ISensor
    rate_hz: float
    stats: StreamStats = field(default_factory=StreamStats)
    is_paused: bool = False
    is_running: bool = True


SensorCallback = Callable[[SensorReading], Awaitable[None]]
EventCallback = Callable[[IOEvent], Awaitable[None]]


class HALIOManager:
    """Centralized I/O manager for HAL devices.

    Features:
    - Automatic sensor polling with configurable rates
    - Event-driven sensor subscriptions
    - Actuator command queuing and scheduling
    - Integration with SafeHAL for safety enforcement
    - Unified event bus for all I/O operations
    """

    def __init__(
        self,
        safe_hal: SafeHAL | None = None,
        platform: PlatformCapabilities | None = None,
        max_concurrent_streams: int = 10,
    ):
        """Initialize the I/O manager.

        Args:
            safe_hal: Optional SafeHAL for safety-wrapped actuator access
            platform: Platform capabilities
            max_concurrent_streams: Maximum number of concurrent sensor streams
        """
        self.safe_hal = safe_hal or SafeHAL()
        self.platform = platform or PlatformCapabilities()
        self.max_concurrent_streams = max_concurrent_streams

        # Stream management
        self._streams: dict[str, StreamHandle] = {}
        self._stream_tasks: dict[str, asyncio.Task] = {}
        self._stream_callbacks: dict[str, SensorCallback] = {}

        # Sensor polling (legacy)
        self._sensor_poll_tasks: dict[str, asyncio.Task] = {}
        self._sensor_callbacks: dict[str, list[SensorCallback]] = {}
        self._sensor_poll_rates: dict[str, float] = {}

        # Event routing
        self._event_callbacks: list[EventCallback] = []
        self._event_queue: asyncio.Queue[IOEvent] = asyncio.Queue()
        self._event_router_task: asyncio.Task | None = None

        # State
        self._running = False

    async def initialize(self) -> None:
        """Initialize the I/O manager."""
        await self.start()

    async def start(self) -> None:
        """Start the I/O manager."""
        if self._running:
            return

        await self.safe_hal.initialize()

        # Start event router
        self._event_router_task = asyncio.create_task(self._event_router())

        self._running = True
        logger.info("HALIOManager started")

    async def shutdown(self) -> None:
        """Stop the I/O manager."""
        await self.stop()

    async def stop(self) -> None:
        """Stop the I/O manager."""
        if not self._running:
            return

        self._running = False

        # Stop all streams in parallel
        stream_ids = list(self._stream_tasks.keys())
        if stream_ids:
            await asyncio.gather(
                *[self.stop_sensor_stream(sid) for sid in stream_ids], return_exceptions=True
            )

        # Cancel and stop all sensor polling tasks in parallel
        for task in self._sensor_poll_tasks.values():
            task.cancel()
        if self._sensor_poll_tasks:
            await asyncio.gather(*self._sensor_poll_tasks.values(), return_exceptions=True)
        self._sensor_poll_tasks.clear()

        # Stop event router
        if self._event_router_task:
            self._event_router_task.cancel()
            try:
                await self._event_router_task
            except asyncio.CancelledError:
                pass
            self._event_router_task = None

        await self.safe_hal.shutdown()
        logger.info("HALIOManager stopped")

    def register_sensor(self, name: str, sensor: ISensor) -> None:
        """Register a sensor with the I/O manager."""
        self.safe_hal.register_sensor(name, sensor)
        self._sensor_callbacks[name] = []

    def register_actuator(self, name: str, actuator: IActuator) -> None:
        """Register an actuator with the I/O manager."""
        self.safe_hal.register_actuator(name, actuator)

    async def start_sensor_stream(
        self,
        sensor: ISensor,
        callback: SensorCallback,
        rate_hz: float = 10.0,
    ) -> StreamHandle:
        """Start a sensor stream.

        Args:
            sensor: The sensor to stream from
            callback: Async callback for sensor readings
            rate_hz: Polling rate in Hz

        Returns:
            StreamHandle for managing the stream
        """
        if len(self._streams) >= self.max_concurrent_streams:
            raise RuntimeError(
                f"Maximum concurrent streams ({self.max_concurrent_streams}) reached"
            )

        stream_id = str(uuid.uuid4())
        handle = StreamHandle(
            stream_id=stream_id,
            sensor=sensor,
            rate_hz=rate_hz,
        )

        self._streams[stream_id] = handle
        self._stream_callbacks[stream_id] = callback

        # Start the stream task
        self._stream_tasks[stream_id] = asyncio.create_task(self._run_stream(stream_id))

        logger.info(f"Started sensor stream {stream_id} at {rate_hz} Hz")
        return handle

    async def stop_sensor_stream(self, stream_id: str) -> None:
        """Stop a sensor stream.

        Args:
            stream_id: ID of the stream to stop
        """
        if stream_id not in self._streams:
            return

        handle = self._streams[stream_id]
        handle.is_running = False

        # Cancel the task
        if stream_id in self._stream_tasks:
            self._stream_tasks[stream_id].cancel()
            try:
                await self._stream_tasks[stream_id]
            except asyncio.CancelledError:
                pass
            del self._stream_tasks[stream_id]

        # Clean up
        del self._streams[stream_id]
        if stream_id in self._stream_callbacks:
            del self._stream_callbacks[stream_id]

        logger.info(f"Stopped sensor stream {stream_id}")

    async def pause_sensor_stream(self, stream_id: str) -> None:
        """Pause a sensor stream.

        Args:
            stream_id: ID of the stream to pause
        """
        if stream_id in self._streams:
            self._streams[stream_id].is_paused = True
            logger.debug(f"Paused sensor stream {stream_id}")

    async def resume_sensor_stream(self, stream_id: str) -> None:
        """Resume a paused sensor stream.

        Args:
            stream_id: ID of the stream to resume
        """
        if stream_id in self._streams:
            self._streams[stream_id].is_paused = False
            logger.debug(f"Resumed sensor stream {stream_id}")

    async def _run_stream(self, stream_id: str) -> None:
        """Run a sensor stream.

        Args:
            stream_id: ID of the stream to run
        """
        handle = self._streams.get(stream_id)
        if not handle:
            return

        callback = self._stream_callbacks.get(stream_id)
        if not callback:
            return

        interval = 1.0 / handle.rate_hz

        while handle.is_running:
            try:
                if handle.is_paused:
                    await asyncio.sleep(0.01)
                    continue

                # Read sensor
                data = await handle.sensor.read_once()
                caps = await handle.sensor.get_capabilities()

                reading = SensorReading(
                    sensor_type=caps.sensor_type,
                    timestamp=datetime.now(),
                    values=data,
                )

                # Update stats
                handle.stats.total_samples += 1
                handle.stats.last_sample_time = reading.timestamp

                # Call callback
                try:
                    await callback(reading)
                except Exception as e:
                    logger.error(f"Stream callback error: {e}")

                # Emit event
                await self.emit_event(
                    IOEvent(
                        source=stream_id,
                        event_type="sensor_reading",
                        timestamp=reading.timestamp,
                        data=reading,
                    )
                )

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stream error: {e}")
                handle.stats.dropped_samples += 1
                await asyncio.sleep(interval)

    async def subscribe_sensor(
        self,
        name: str,
        callback: SensorCallback,
        poll_rate_hz: float = 10.0,
    ) -> None:
        """Subscribe to sensor updates (legacy API).

        Args:
            name: Sensor name
            callback: Async callback for sensor readings
            poll_rate_hz: Polling rate in Hz
        """
        if name not in self._sensor_callbacks:
            raise KeyError(f"Sensor '{name}' not registered")

        self._sensor_callbacks[name].append(callback)
        self._sensor_poll_rates[name] = poll_rate_hz

        # Start polling if not already running
        if name not in self._sensor_poll_tasks:
            self._sensor_poll_tasks[name] = asyncio.create_task(self._poll_sensor(name))

    async def unsubscribe_sensor(self, name: str, callback: SensorCallback) -> None:
        """Unsubscribe from sensor updates."""
        if name in self._sensor_callbacks:
            if callback in self._sensor_callbacks[name]:
                self._sensor_callbacks[name].remove(callback)

            # Stop polling if no more subscribers
            if not self._sensor_callbacks[name] and name in self._sensor_poll_tasks:
                self._sensor_poll_tasks[name].cancel()
                del self._sensor_poll_tasks[name]

    async def read_sensor(self, name: str) -> SensorReading:
        """Read a sensor value directly."""
        return await self.safe_hal.read_sensor(name)

    async def write_actuator(self, name: str, value: Any) -> None:
        """Write a command to an actuator (with safety checking)."""
        await self.safe_hal.write_actuator(name, value)

    def subscribe_events(self, callback: EventCallback) -> None:
        """Subscribe to all I/O events."""
        self._event_callbacks.append(callback)

    def unsubscribe_events(self, callback: EventCallback) -> None:
        """Unsubscribe from I/O events."""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)

    async def emit_event(self, event: IOEvent) -> None:
        """Emit an I/O event to all subscribers."""
        await self._event_queue.put(event)

    async def _poll_sensor(self, name: str) -> None:
        """Poll a sensor at the configured rate."""
        while self._running:
            try:
                rate_hz = self._sensor_poll_rates.get(name, 10.0)
                interval = 1.0 / rate_hz

                reading = await self.safe_hal.read_sensor(name)

                # Call all callbacks
                for callback in self._sensor_callbacks.get(name, []):
                    try:
                        await callback(reading)
                    except Exception as e:
                        logger.error(f"Sensor callback error for {name}: {e}")

                # Emit event
                await self.emit_event(
                    IOEvent(
                        source=name,
                        event_type="sensor_reading",
                        timestamp=reading.timestamp,
                        data=reading,
                    )
                )

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error polling sensor {name}: {e}")
                await asyncio.sleep(1.0)  # Back off on error

    async def _event_router(self) -> None:
        """Route events to subscribers."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0,
                )

                for callback in self._event_callbacks:
                    try:
                        await callback(event)
                    except Exception as e:
                        logger.error(f"Event callback error: {e}")

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event router error: {e}")
