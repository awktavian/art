"""Multi-Device Coordinator for K os Ambient OS.

Enables seamless operation across multiple devices:
- Wearable (smartwatch)
- Phone (iOS/Android)
- Tablet
- Desktop/Laptop

Features:
- Device registration
- Seamless handoff protocol
- State synchronization

Created: November 10, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """Device types in ambient ecosystem."""

    WEARABLE = "wearable"  # Smartwatch
    PHONE = "phone"
    TABLET = "tablet"
    DESKTOP = "desktop"
    LAPTOP = "laptop"


class DeviceStatus(Enum):
    """Device connection status."""

    ACTIVE = "active"  # Currently active
    NEARBY = "nearby"  # Connected, not active
    AWAY = "away"  # Not connected


@dataclass
class DeviceSensoryData:
    """Sensory data from a device (health, motion, audio)."""

    # Health metrics (from HealthKit/Health Connect)
    heart_rate: float | None = None
    resting_heart_rate: float | None = None
    hrv: float | None = None
    steps: int | None = None
    active_calories: int | None = None
    exercise_minutes: int | None = None
    blood_oxygen: float | None = None
    sleep_hours: float | None = None

    # Motion data
    motion_intensity: float | None = None  # 0-1 scale
    is_moving: bool | None = None
    activity_type: str | None = None  # walking, running, stationary

    # Audio data
    ambient_noise_level: float | None = None  # dB
    is_speaking: bool | None = None

    # Location (if device provides it)
    latitude: float | None = None
    longitude: float | None = None

    # Metadata
    timestamp: float = field(default_factory=time.time)


@dataclass
class Device:
    """Device in ambient ecosystem."""

    id: str
    name: str
    type: DeviceType
    status: DeviceStatus
    capabilities: dict[str, Any] = field(default_factory=dict[str, Any])
    battery_level: float = 1.0
    last_seen: float = field(default_factory=time.time)
    location: str | None = None

    # Sensory data from device (Dec 30, 2025)
    sensory_data: DeviceSensoryData = field(default_factory=DeviceSensoryData)

    @property
    def has_health_data(self) -> bool:
        """Check if device provides health data."""
        return "healthkit" in self.capabilities or "health_connect" in self.capabilities


@dataclass
class HandoffRequest:
    """Handoff request between devices."""

    from_device: str
    to_device: str
    context: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class MultiDeviceCoordinator:
    """Coordinates state across multiple devices."""

    def __init__(self) -> None:
        # Registered devices
        self.devices: dict[str, Device] = {}

        # Current active device
        self.active_device: str | None = None

        # Shared state
        self.shared_state: dict[str, Any] = {}

        # Handoff queue
        self.handoff_queue: deque[HandoffRequest] = deque(maxlen=100)

        # Statistics
        self.stats = {
            "handoffs": 0,
            "syncs": 0,
            "devices_discovered": 0,
            "handoff_last_ms": 0.0,
            "handoff_p95_ms": 0.0,
        }
        self._handoff_times: deque[float] = deque(maxlen=100)
        # Lifecycle flag (kept for compatibility with boot shutdown hooks).
        self._running = False

    @staticmethod
    def _normalize_capabilities(capabilities: Any | None) -> dict[str, Any]:
        """Convert heterogeneous capability payloads into a dict[str, Any]."""
        if capabilities is None:
            return {}
        if isinstance(capabilities, dict):
            return dict(capabilities)
        if isinstance(capabilities, str):
            return {capabilities: True}
        if isinstance(capabilities, (list, tuple, set, frozenset)):
            normalized: dict[str, Any] = {}
            for entry in capabilities:
                if isinstance(entry, dict):
                    normalized.update(entry)
                elif isinstance(entry, (tuple, list)) and len(entry) == 2:
                    key, value = entry
                    normalized[str(key)] = value
                else:
                    normalized[str(entry)] = True
            return normalized
        # Fallback: treat unknown payloads as a single capability flag
        return {"value": capabilities}

    def register_device(
        self,
        device_id: str,
        name: str,
        device_type: DeviceType,
        capabilities: Any | None = None,
    ) -> Device:
        """Register device in ecosystem.

        Args:
            device_id: Unique device ID
            name: Human-readable name
            device_type: Device type
            capabilities: Device capabilities

        Returns:
            Device object
        """
        normalized_capabilities = self._normalize_capabilities(capabilities)

        # If device already exists, update in place (preserve cached state, endpoint info, etc.)
        existing = self.devices.get(device_id)
        if existing is not None:
            existing.name = name
            existing.type = device_type
            # Treat registration as presence signal
            existing.status = (
                DeviceStatus.NEARBY if existing.status != DeviceStatus.ACTIVE else existing.status
            )
            existing.last_seen = time.time()
            # Merge capabilities (do NOT drop existing keys like cached "state")
            existing.capabilities.update(normalized_capabilities)
            logger.info(f"📱 Device updated: {name} ({device_type.value}, {device_id[:8]})")
            return existing

        device = Device(
            id=device_id,
            name=name,
            type=device_type,
            status=DeviceStatus.NEARBY,
            capabilities=normalized_capabilities,
        )

        self.devices[device_id] = device
        self.stats["devices_discovered"] += 1

        logger.info(f"📱 Device registered: {name} ({device_type.value}, {device_id[:8]})")

        return device

    def heartbeat(
        self,
        device_id: str,
        *,
        status: DeviceStatus | None = None,
        battery_level: float | None = None,
        location: str | None = None,
        capabilities: Any | None = None,
    ) -> Device | None:
        """Update device liveness and mutable fields.

        Intended for frequent calls from device clients:
        - updates last_seen
        - updates status/battery/location/capabilities (merged)
        """
        device = self.devices.get(device_id)
        if device is None:
            return None

        device.last_seen = time.time()
        if status is not None:
            device.status = status
        if battery_level is not None:
            try:
                device.battery_level = max(0.0, min(1.0, float(battery_level)))
            except Exception:
                pass
        if location is not None:
            device.location = location
        if capabilities is not None:
            device.capabilities.update(self._normalize_capabilities(capabilities))

        return device

    async def update_sensory_data(
        self,
        device_id: str,
        data: dict[str, Any],
    ) -> bool:
        """Update sensory data from a device (health, motion, audio).

        This method:
        1. Updates the device's sensory_data
        2. Aggregates health data from all devices
        3. Forwards to UnifiedSensory HEALTH sense

        Args:
            device_id: Device identifier
            data: Sensory data dict with keys like heart_rate, hrv, steps, etc.

        Returns:
            True if successful
        """
        device = self.devices.get(device_id)
        if device is None:
            logger.warning(f"Unknown device for sensory update: {device_id}")
            return False

        # Update device's sensory data
        sd = device.sensory_data
        if "heart_rate" in data:
            sd.heart_rate = data["heart_rate"]
        if "resting_heart_rate" in data:
            sd.resting_heart_rate = data["resting_heart_rate"]
        if "hrv" in data:
            sd.hrv = data["hrv"]
        if "steps" in data:
            sd.steps = data["steps"]
        if "active_calories" in data:
            sd.active_calories = data["active_calories"]
        if "exercise_minutes" in data:
            sd.exercise_minutes = data["exercise_minutes"]
        if "blood_oxygen" in data:
            sd.blood_oxygen = data["blood_oxygen"]
        if "sleep_hours" in data:
            sd.sleep_hours = data["sleep_hours"]
        if "motion_intensity" in data:
            sd.motion_intensity = data["motion_intensity"]
        if "is_moving" in data:
            sd.is_moving = data["is_moving"]
        if "activity_type" in data:
            sd.activity_type = data["activity_type"]
        if "ambient_noise_level" in data:
            sd.ambient_noise_level = data["ambient_noise_level"]
        if "is_speaking" in data:
            sd.is_speaking = data["is_speaking"]
        if "latitude" in data and "longitude" in data:
            sd.latitude = data["latitude"]
            sd.longitude = data["longitude"]

        sd.timestamp = time.time()
        device.last_seen = sd.timestamp  # Sensory data implies heartbeat

        # Forward aggregated health to UnifiedSensory
        await self._forward_health_to_unified_sensory()

        logger.debug(f"📊 Sensory data updated from {device.name}")
        return True

    async def _forward_health_to_unified_sensory(self) -> None:
        """Forward aggregated health data to UnifiedSensory HEALTH sense.

        Priority: WEARABLE > PHONE > TABLET > DESKTOP
        """
        # Find best health data source
        priority_order = [
            DeviceType.WEARABLE,
            DeviceType.PHONE,
            DeviceType.TABLET,
            DeviceType.DESKTOP,
        ]

        best_device: Device | None = None
        for dtype in priority_order:
            for device in self.devices.values():
                if device.type == dtype and device.has_health_data:
                    sd = device.sensory_data
                    # Check if has recent data (within 5 minutes)
                    if sd.timestamp > time.time() - 300:
                        best_device = device
                        break
            if best_device:
                break

        if not best_device:
            return

        # Forward to UnifiedSensory
        try:
            from kagami.core.integrations import get_unified_sensory

            sensory = get_unified_sensory()
            if sensory and hasattr(sensory, "update_client_health"):
                sd = best_device.sensory_data
                await sensory.update_client_health(
                    source=best_device.name,
                    data={
                        "heart_rate": sd.heart_rate,
                        "resting_heart_rate": sd.resting_heart_rate,
                        "hrv": sd.hrv,
                        "steps": sd.steps,
                        "active_calories": sd.active_calories,
                        "exercise_minutes": sd.exercise_minutes,
                        "blood_oxygen": sd.blood_oxygen,
                        "sleep_hours": sd.sleep_hours,
                    },
                )
        except Exception as e:
            logger.debug(f"Failed to forward health to UnifiedSensory: {e}")

    def get_aggregated_health(self) -> DeviceSensoryData | None:
        """Get aggregated health data from the best source.

        Returns:
            DeviceSensoryData from highest-priority device with health data
        """
        priority_order = [
            DeviceType.WEARABLE,
            DeviceType.PHONE,
            DeviceType.TABLET,
            DeviceType.DESKTOP,
        ]

        for dtype in priority_order:
            for device in self.devices.values():
                if device.type == dtype and device.has_health_data:
                    sd = device.sensory_data
                    if sd.timestamp > time.time() - 300:  # Within 5 minutes
                        return sd
        return None

    def set_active_device(self, device_id: str) -> None:
        """Set currently active device.

        Args:
            device_id: Device to set[Any] as active
        """
        if device_id not in self.devices:
            raise ValueError(f"Unknown device: {device_id}")

        # Deactivate previous
        if self.active_device and self.active_device in self.devices:
            self.devices[self.active_device].status = DeviceStatus.NEARBY

        # Activate new
        self.devices[device_id].status = DeviceStatus.ACTIVE
        self.active_device = device_id

        logger.info(f"📱 Active device: {self.devices[device_id].name}")

    async def request_handoff(
        self,
        from_device: str,
        to_device: str,
        context: dict[str, Any],
    ) -> bool:
        """Request device handoff.

        Args:
            from_device: Source device ID
            to_device: Target device ID
            context: Context to transfer

        Returns:
            True if handoff succeeded
        """
        if from_device not in self.devices:
            logger.error(f"Unknown source device: {from_device}")
            return False

        if to_device not in self.devices:
            logger.error(f"Unknown target device: {to_device}")
            return False

        # Create handoff request
        request = HandoffRequest(
            from_device=from_device,
            to_device=to_device,
            context=context,
        )

        self.handoff_queue.append(request)

        # Process handoff
        success = await self._process_handoff(request)

        if success:
            self.stats["handoffs"] += 1
            self.set_active_device(to_device)

            logger.info(
                f"✨ Handoff: {self.devices[from_device].name} → {self.devices[to_device].name}"
            )

        return success

    async def _process_handoff(self, request: HandoffRequest) -> bool:
        """Process handoff request.

        Args:
            request: Handoff request

        Returns:
            True if successful
        """
        start_time = time.perf_counter()
        try:
            # Serialize context from source
            serialized = await self._serialize_context(request.context)

            # Transfer to target
            await self._transfer_context(
                request.to_device, serialized, from_device=request.from_device
            )

            # Update shared state + broadcast delta (event-driven Constellation)
            await self.sync_state(request.context, from_device=request.from_device)

            # Update metrics
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.stats["handoff_last_ms"] = duration_ms
            self._handoff_times.append(duration_ms)

            if len(self._handoff_times) > 0:
                sorted_times = sorted(self._handoff_times)
                idx = int(len(sorted_times) * 0.95)
                self.stats["handoff_p95_ms"] = sorted_times[min(idx, len(sorted_times) - 1)]

            return True

        except Exception as e:
            logger.error(f"Handoff failed: {e}", exc_info=True)
            return False

    async def _serialize_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Serialize context for transfer.

        Args:
            context: Context data

        Returns:
            Serialized context
        """
        import base64
        import gzip
        import json

        try:
            # Convert to JSON-serializable format
            serializable = {}

            for key, value in context.items():
                if isinstance(value, bytes):
                    # Encode binary data as base64
                    serializable[key] = {
                        "_type": "bytes",
                        "_data": base64.b64encode(value).decode("utf-8"),
                    }
                elif hasattr(value, "tolist"):  # numpy/torch arrays
                    serializable[key] = {
                        "_type": "array",
                        "_data": value.tolist(),
                    }
                else:
                    serializable[key] = value

            # Convert to JSON
            json_str = json.dumps(serializable)

            # Compress if large (>1KB)
            if len(json_str) > 1024:
                compressed = gzip.compress(json_str.encode("utf-8"))

                return {
                    "_compressed": True,
                    "_data": base64.b64encode(compressed).decode("utf-8"),
                }

            return serializable

        except Exception as e:
            logger.error(f"Serialization failed: {e}")
            return context

    async def _transfer_context(
        self, device_id: str, context: dict[str, Any], *, from_device: str | None = None
    ) -> None:
        """Transfer context to device.

        Args:
            device_id: Target device
            context: Serialized context
            from_device: Optional origin device id for attribution
        """
        device = self.devices.get(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")

        origin = from_device or self.active_device

        # 1) Direct handoff handler (in-memory/testing)
        handler = device.capabilities.get("handoff_handler")
        if handler and asyncio.iscoroutinefunction(handler):
            await handler({"context": context, "from_device": origin, "timestamp": time.time()})
            logger.info(f"Transferred context to {device_id} via direct handler")
            return

        # 2) Constellation runtime: Socket.IO device room (preferred)
        try:
            from kagami.core.di.container import try_resolve
            from kagami.core.interfaces import RealtimeBroadcaster

            sio = try_resolve(RealtimeBroadcaster)
            if sio:
                # Add timeout to prevent hanging (Dec 28, 2025)
                await asyncio.wait_for(
                    sio.emit(
                        "context_transfer",
                        {"context": context, "from_device": origin, "timestamp": time.time()},
                        room=f"device_{device_id}",
                    ),
                    timeout=2.0,  # 2 second timeout for context transfer
                )
                logger.info(f"Transferred context to {device_id} via Socket.IO")
                return
        except Exception as e:
            raise RuntimeError(f"Socket.IO transfer failed: {e}") from e

        # No supported transport available
        raise RuntimeError(f"No Constellation transport available for device {device_id}")

    async def sync_state(self, updates: dict[str, Any], *, from_device: str | None = None) -> None:
        """Synchronize state across devices.

        Args:
            updates: State updates
            from_device: Optional device id that originated the update
        """
        self.shared_state.update(updates)
        self.stats["syncs"] += 1

        # Best-effort realtime push (do not wait for the 30s polling sync loop).
        await self._push_state_delta(updates, from_device=from_device)

        logger.debug(f"State synced: {len(updates)} updates")

    async def _push_state_delta(
        self, delta: dict[str, Any], *, from_device: str | None = None
    ) -> None:
        """Push a state delta to connected device rooms (Socket.IO best-effort)."""
        if not delta:
            return

        try:
            from kagami.core.di.container import try_resolve
            from kagami.core.interfaces import RealtimeBroadcaster

            sio = try_resolve(RealtimeBroadcaster)
            if not sio:
                return

            version = int(time.time() * 1000)
            origin = from_device or self.active_device

            for device_id, device in list(self.devices.items()):
                # Only try to push to present devices (AWAY devices will resync when back)
                if device.status == DeviceStatus.AWAY:
                    continue

                try:
                    # Add timeout to prevent hanging during boot (Dec 28, 2025)
                    await asyncio.wait_for(
                        sio.emit(
                            "state_sync",
                            {"delta": delta, "version": version, "from_device": origin},
                            room=f"device_{device_id}",
                        ),
                        timeout=1.0,  # 1 second timeout for best-effort sync
                    )

                    # Update device cached state (used for delta computation elsewhere)
                    device_state = device.capabilities.get("state", {})
                    if isinstance(device_state, dict):
                        device.capabilities["state"] = {**device_state, **delta}
                    else:
                        device.capabilities["state"] = dict(delta)
                except Exception:
                    # Best-effort: device may not be connected or timed out.
                    pass
        except Exception:
            # Never let realtime push break state sync.
            return

    async def start(self) -> None:
        """Start multi-device coordinator."""
        if self._running:
            return
        # Constellation is now event-driven (Socket.IO + explicit device heartbeats/state sync).
        self._running = True
        logger.info("🔄 Multi-device coordinator started (event-driven)")

    async def stop(self) -> None:
        """Stop multi-device coordinator."""
        self._running = False
        logger.info("🔄 Multi-device coordinator stopped")

    def get_stats(self) -> dict[str, Any]:
        """Get coordinator statistics.

        Returns:
            Statistics dict[str, Any]
        """
        return {
            **self.stats,
            "devices": len(self.devices),
            "active_device": self.active_device,
            "shared_state_keys": len(self.shared_state),
        }


# Global coordinator instance
_COORDINATOR: MultiDeviceCoordinator | None = None


async def get_multi_device_coordinator() -> MultiDeviceCoordinator:
    """Get global multi-device coordinator."""
    global _COORDINATOR
    if _COORDINATOR is None:
        _COORDINATOR = MultiDeviceCoordinator()
        await _COORDINATOR.start()
    return _COORDINATOR
