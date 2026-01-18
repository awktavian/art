"""Cross-platform E2E Test Fixtures.

This module provides comprehensive fixtures for end-to-end testing of:
- Mock device constellation (multiple hubs, clients, devices)
- Simulated network conditions (latency, partitions, failures)
- User personas (Tim, Guest users)
- Smart home automation scenarios

Colony: Nexus (e4) - Connection and integration
Colony: Crystal (e7) - Verification and trust

h(x) >= 0. Always.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio


# ==============================================================================
# ENUMS AND CONSTANTS
# ==============================================================================


class DeviceType(str, Enum):
    """Types of devices in the constellation."""

    HUB = "hub"
    PHONE = "phone"
    WATCH = "watch"
    TV = "tv"
    SPEAKER = "speaker"
    LIGHT = "light"
    LOCK = "lock"
    THERMOSTAT = "thermostat"
    CAMERA = "camera"
    SENSOR = "sensor"


class ConnectionState(str, Enum):
    """Device connection states."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class NetworkCondition(str, Enum):
    """Network condition simulations."""

    NORMAL = "normal"
    HIGH_LATENCY = "high_latency"
    PACKET_LOSS = "packet_loss"
    PARTITION = "partition"
    OFFLINE = "offline"
    FLAKY = "flaky"


class UserRole(str, Enum):
    """User roles in the household."""

    OWNER = "owner"
    GUEST = "guest"
    ADMIN = "admin"


# ==============================================================================
# USER PERSONAS
# ==============================================================================


@dataclass
class UserPersona:
    """User persona for testing household scenarios."""

    user_id: str
    name: str
    role: UserRole
    email: str
    preferences: dict[str, Any] = field(default_factory=dict)
    devices: list[str] = field(default_factory=list)
    presence_home: bool = True
    current_room: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "role": self.role.value,
            "email": self.email,
            "preferences": self.preferences,
            "devices": self.devices,
            "presence_home": self.presence_home,
            "current_room": self.current_room,
        }


@pytest.fixture
def tim_persona() -> UserPersona:
    """Tim - the primary owner of the household."""
    return UserPersona(
        user_id="tim-001",
        name="Tim",
        role=UserRole.OWNER,
        email="tim@kagami.dev",
        preferences={
            "wake_time": "06:30",
            "sleep_time": "22:30",
            "preferred_temp": 72.0,
            "lighting_preference": "warm",
            "music_preference": "ambient",
            "coffee_time": "06:45",
            "work_start": "08:00",
            "movie_volume": 45,
        },
        devices=["phone-tim", "watch-tim", "laptop-tim"],
        presence_home=True,
        current_room="Primary Bedroom",
    )


@pytest.fixture
def guest_persona() -> UserPersona:
    """Guest user with limited access."""
    return UserPersona(
        user_id="guest-001",
        name="Guest",
        role=UserRole.GUEST,
        email="guest@example.com",
        preferences={
            "preferred_temp": 70.0,
        },
        devices=["phone-guest"],
        presence_home=False,
        current_room=None,
    )


@pytest.fixture
def kristi_persona() -> UserPersona:
    """Kristi - Tim's sister who visits with Bella."""
    return UserPersona(
        user_id="kristi-001",
        name="Kristi",
        role=UserRole.GUEST,
        email="kristi@example.com",
        preferences={
            "preferred_temp": 71.0,
            "lighting_preference": "bright",
        },
        devices=["phone-kristi"],
        presence_home=False,
        current_room=None,
    )


# ==============================================================================
# MOCK DEVICE CLASSES
# ==============================================================================


@dataclass
class MockDevice:
    """Base mock device for testing."""

    device_id: str
    name: str
    device_type: DeviceType
    room: str | None = None
    connection_state: ConnectionState = ConnectionState.CONNECTED
    last_seen: float = field(default_factory=time.time)
    properties: dict[str, Any] = field(default_factory=dict)
    hub_id: str | None = None

    def is_online(self) -> bool:
        return self.connection_state == ConnectionState.CONNECTED

    def update_property(self, key: str, value: Any) -> None:
        self.properties[key] = value
        self.last_seen = time.time()


@dataclass
class MockHub:
    """Mock hub node for mesh network testing."""

    hub_id: str
    name: str
    address: str = "127.0.0.1"
    port: int = 8080
    is_primary: bool = False
    is_leader: bool = False
    connection_state: ConnectionState = ConnectionState.CONNECTED
    devices: list[MockDevice] = field(default_factory=list)
    peers: list[str] = field(default_factory=list)
    last_heartbeat: float = field(default_factory=time.time)

    # Circuit breaker state
    circuit_state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    circuit_open_time: float | None = None

    # Mesh state
    vector_clock: dict[str, int] = field(default_factory=dict)
    pending_sync: list[dict] = field(default_factory=list)
    offline_queue: list[dict] = field(default_factory=list)

    def is_online(self) -> bool:
        return self.connection_state == ConnectionState.CONNECTED

    def record_failure(self, threshold: int = 5) -> None:
        self.failure_count += 1
        if self.failure_count >= threshold:
            self.circuit_state = CircuitState.OPEN
            self.circuit_open_time = time.time()

    def record_success(self) -> None:
        self.failure_count = 0
        self.circuit_state = CircuitState.CLOSED
        self.circuit_open_time = None

    def increment_clock(self) -> None:
        self.vector_clock[self.hub_id] = self.vector_clock.get(self.hub_id, 0) + 1

    def merge_clock(self, other_clock: dict[str, int]) -> None:
        for hub_id, ts in other_clock.items():
            self.vector_clock[hub_id] = max(self.vector_clock.get(hub_id, 0), ts)


# ==============================================================================
# MOCK DEVICE CONSTELLATION
# ==============================================================================


@dataclass
class MockDeviceConstellation:
    """Complete mock device constellation for testing."""

    hubs: dict[str, MockHub] = field(default_factory=dict)
    devices: dict[str, MockDevice] = field(default_factory=dict)
    network_condition: NetworkCondition = NetworkCondition.NORMAL
    latency_ms: int = 10

    # Event tracking
    events: list[dict] = field(default_factory=list)
    command_history: list[dict] = field(default_factory=list)

    def add_hub(self, hub: MockHub) -> None:
        self.hubs[hub.hub_id] = hub

        # Connect to all existing hubs
        for existing_hub_id in self.hubs:
            if existing_hub_id != hub.hub_id:
                hub.peers.append(existing_hub_id)
                self.hubs[existing_hub_id].peers.append(hub.hub_id)

    def add_device(self, device: MockDevice) -> None:
        self.devices[device.device_id] = device

        # Assign to primary hub if not specified
        if device.hub_id is None and self.hubs:
            primary_hub = next((h for h in self.hubs.values() if h.is_primary), None)
            if primary_hub is None:
                primary_hub = list(self.hubs.values())[0]
            device.hub_id = primary_hub.hub_id
            primary_hub.devices.append(device)

    def get_primary_hub(self) -> MockHub | None:
        return next((h for h in self.hubs.values() if h.is_primary), None)

    def get_leader_hub(self) -> MockHub | None:
        return next((h for h in self.hubs.values() if h.is_leader), None)

    def set_network_condition(self, condition: NetworkCondition) -> None:
        self.network_condition = condition

        if condition == NetworkCondition.OFFLINE:
            for hub in self.hubs.values():
                hub.connection_state = ConnectionState.DISCONNECTED
            for device in self.devices.values():
                device.connection_state = ConnectionState.DISCONNECTED
        elif condition == NetworkCondition.HIGH_LATENCY:
            self.latency_ms = 500
        elif condition == NetworkCondition.NORMAL:
            self.latency_ms = 10
            for hub in self.hubs.values():
                hub.connection_state = ConnectionState.CONNECTED
            for device in self.devices.values():
                device.connection_state = ConnectionState.CONNECTED

    def simulate_hub_failure(self, hub_id: str) -> None:
        """Simulate a hub going offline."""
        if hub_id in self.hubs:
            hub = self.hubs[hub_id]
            hub.connection_state = ConnectionState.DISCONNECTED

            # Disconnect all devices on this hub
            for device in hub.devices:
                device.connection_state = ConnectionState.DISCONNECTED

            # Remove from peer lists
            for other_hub in self.hubs.values():
                if hub_id in other_hub.peers:
                    other_hub.peers.remove(hub_id)

            self._record_event("hub_failure", {"hub_id": hub_id})

    def simulate_hub_recovery(self, hub_id: str) -> None:
        """Simulate a hub coming back online."""
        if hub_id in self.hubs:
            hub = self.hubs[hub_id]
            hub.connection_state = ConnectionState.CONNECTED

            # Reconnect devices
            for device in hub.devices:
                device.connection_state = ConnectionState.CONNECTED

            # Rejoin peer list
            for other_hub in self.hubs.values():
                if other_hub.hub_id != hub_id and hub_id not in other_hub.peers:
                    other_hub.peers.append(hub_id)

            self._record_event("hub_recovery", {"hub_id": hub_id})

    def simulate_network_partition(self, partition_a: list[str], partition_b: list[str]) -> None:
        """Simulate network partition between two groups of hubs."""
        for hub_id_a in partition_a:
            for hub_id_b in partition_b:
                if hub_id_a in self.hubs and hub_id_b in self.hubs:
                    # Remove peer connections across partition
                    if hub_id_b in self.hubs[hub_id_a].peers:
                        self.hubs[hub_id_a].peers.remove(hub_id_b)
                    if hub_id_a in self.hubs[hub_id_b].peers:
                        self.hubs[hub_id_b].peers.remove(hub_id_a)

        self._record_event(
            "network_partition",
            {
                "partition_a": partition_a,
                "partition_b": partition_b,
            },
        )

    def heal_network_partition(self) -> None:
        """Heal a network partition by restoring all peer connections."""
        for hub in self.hubs.values():
            for other_hub in self.hubs.values():
                if other_hub.hub_id != hub.hub_id and other_hub.hub_id not in hub.peers:
                    hub.peers.append(other_hub.hub_id)

        self._record_event("partition_healed", {})

    async def execute_command(
        self,
        command: str,
        target: str,
        params: dict[str, Any],
        user: UserPersona | None = None,
    ) -> dict[str, Any]:
        """Execute a command on a device."""
        # Simulate network latency
        if self.network_condition != NetworkCondition.OFFLINE:
            await asyncio.sleep(self.latency_ms / 1000)

        result = {
            "command": command,
            "target": target,
            "params": params,
            "success": False,
            "timestamp": time.time(),
            "user_id": user.user_id if user else None,
        }

        # Check network condition
        if self.network_condition == NetworkCondition.OFFLINE:
            result["error"] = "Network offline"
            self._queue_offline_command(command, target, params)
        elif self.network_condition == NetworkCondition.PARTITION:
            result["error"] = "Network partition"
        else:
            result["success"] = True
            result["result"] = f"Executed {command} on {target}"

        self.command_history.append(result)
        return result

    def _queue_offline_command(self, command: str, target: str, params: dict) -> None:
        """Queue a command for later replay when online."""
        for hub in self.hubs.values():
            hub.offline_queue.append(
                {
                    "id": str(uuid.uuid4()),
                    "command": command,
                    "target": target,
                    "params": params,
                    "timestamp": time.time(),
                }
            )

    def _record_event(self, event_type: str, data: dict) -> None:
        self.events.append(
            {
                "type": event_type,
                "data": data,
                "timestamp": time.time(),
            }
        )


@pytest.fixture
def mock_constellation() -> MockDeviceConstellation:
    """Create a mock device constellation with standard setup."""
    constellation = MockDeviceConstellation()

    # Add hubs
    constellation.add_hub(
        MockHub(
            hub_id="hub-living-room",
            name="Living Room Hub",
            port=8080,
            is_primary=True,
            is_leader=True,
        )
    )
    constellation.add_hub(
        MockHub(
            hub_id="hub-bedroom",
            name="Bedroom Hub",
            port=8081,
        )
    )
    constellation.add_hub(
        MockHub(
            hub_id="hub-kitchen",
            name="Kitchen Hub",
            port=8082,
        )
    )
    constellation.add_hub(
        MockHub(
            hub_id="hub-office",
            name="Office Hub",
            port=8083,
        )
    )

    # Add devices
    devices = [
        MockDevice("light-living-1", "Living Room Main Light", DeviceType.LIGHT, "Living Room"),
        MockDevice("light-living-2", "Living Room Accent Light", DeviceType.LIGHT, "Living Room"),
        MockDevice("light-bedroom-1", "Bedroom Main Light", DeviceType.LIGHT, "Primary Bedroom"),
        MockDevice("light-kitchen-1", "Kitchen Light", DeviceType.LIGHT, "Kitchen"),
        MockDevice("light-office-1", "Office Light", DeviceType.LIGHT, "Office"),
        MockDevice("tv-living", "Living Room TV", DeviceType.TV, "Living Room"),
        MockDevice("speaker-living", "Living Room Speaker", DeviceType.SPEAKER, "Living Room"),
        MockDevice("thermostat-main", "Main Thermostat", DeviceType.THERMOSTAT, "Hallway"),
        MockDevice("lock-front", "Front Door Lock", DeviceType.LOCK, "Entry"),
        MockDevice("lock-back", "Back Door Lock", DeviceType.LOCK, "Kitchen"),
        MockDevice("camera-front", "Front Door Camera", DeviceType.CAMERA, "Entry"),
        MockDevice("sensor-motion-living", "Living Room Motion", DeviceType.SENSOR, "Living Room"),
        MockDevice("phone-tim", "Tim's iPhone", DeviceType.PHONE, None),
        MockDevice("watch-tim", "Tim's Watch", DeviceType.WATCH, None),
    ]

    for device in devices:
        constellation.add_device(device)

    return constellation


# ==============================================================================
# NETWORK SIMULATION FIXTURES
# ==============================================================================


@dataclass
class NetworkSimulator:
    """Simulates various network conditions for testing."""

    base_latency_ms: int = 10
    jitter_ms: int = 5
    packet_loss_rate: float = 0.0
    is_partitioned: bool = False
    is_offline: bool = False

    async def simulate_request(self, success_callback: Callable) -> Any:
        """Simulate a network request with configured conditions."""
        import random

        if self.is_offline:
            raise ConnectionError("Network is offline")

        if self.is_partitioned:
            raise ConnectionError("Network partition")

        # Simulate latency
        latency = self.base_latency_ms + random.randint(-self.jitter_ms, self.jitter_ms)
        await asyncio.sleep(latency / 1000)

        # Simulate packet loss
        if random.random() < self.packet_loss_rate:
            raise TimeoutError("Packet lost")

        return await success_callback()

    def set_normal(self) -> None:
        self.base_latency_ms = 10
        self.jitter_ms = 5
        self.packet_loss_rate = 0.0
        self.is_partitioned = False
        self.is_offline = False

    def set_high_latency(self) -> None:
        self.base_latency_ms = 500
        self.jitter_ms = 100
        self.packet_loss_rate = 0.01

    def set_flaky(self) -> None:
        self.base_latency_ms = 50
        self.jitter_ms = 200
        self.packet_loss_rate = 0.1

    def set_offline(self) -> None:
        self.is_offline = True

    def set_partitioned(self) -> None:
        self.is_partitioned = True


@pytest.fixture
def network_simulator() -> NetworkSimulator:
    """Create a network simulator for testing."""
    return NetworkSimulator()


# ==============================================================================
# SMART HOME CONTROLLER MOCK
# ==============================================================================


@pytest.fixture
def mock_smart_home_controller(mock_constellation: MockDeviceConstellation):
    """Create a mock smart home controller."""
    controller = MagicMock()

    # Basic properties
    controller.is_connected = True
    controller._constellation = mock_constellation

    # Light control
    controller.set_lights = AsyncMock(return_value=True)
    controller.set_room_scene = AsyncMock(return_value=True)
    controller.open_shades = AsyncMock(return_value=True)
    controller.close_shades = AsyncMock(return_value=True)
    controller.set_shades = AsyncMock(return_value=True)

    # Climate control
    controller.set_room_temp = AsyncMock(return_value=True)
    controller.set_bed_temperature = AsyncMock(return_value=True)
    controller.set_away_hvac = AsyncMock(return_value=True)

    # Security
    controller.lock_all = AsyncMock(return_value=True)
    controller.unlock_door = AsyncMock(return_value=True)
    controller.arm_security = AsyncMock(return_value=True)
    controller.disarm_security = AsyncMock(return_value=True)
    controller.get_security_state = AsyncMock(return_value="disarmed")
    controller.get_lock_states = AsyncMock(
        return_value={
            "front_door": "locked",
            "back_door": "locked",
        }
    )

    # Media
    controller.tv_on = AsyncMock(return_value=True)
    controller.tv_off = AsyncMock(return_value=True)
    controller.lower_tv = AsyncMock(return_value=True)
    controller.raise_tv = AsyncMock(return_value=True)
    controller.enter_movie_mode = AsyncMock(return_value=True)
    controller.exit_movie_mode = AsyncMock(return_value=True)

    # Audio
    controller.announce = AsyncMock(return_value=True)
    controller.announce_all = AsyncMock(return_value=True)
    controller.mute_room = AsyncMock(return_value=True)
    controller.spotify_play_playlist = AsyncMock(return_value=True)
    controller.spotify_pause = AsyncMock(return_value=True)

    # Presence
    controller.is_anyone_in_bed = Mock(return_value=False)
    controller.is_home = Mock(return_value=True)
    controller.get_presence_state = Mock(return_value={"tim": True})

    # Scenes
    controller.goodnight = AsyncMock(return_value=True)
    controller.welcome_home = AsyncMock(return_value=True)
    controller.set_away_mode = AsyncMock(return_value=True)

    # Fireplace
    controller.fireplace_on = AsyncMock(return_value=True)
    controller.fireplace_off = AsyncMock(return_value=True)

    # Outdoor
    controller.outdoor_lights_on = AsyncMock(return_value=True)
    controller.outdoor_lights_off = AsyncMock(return_value=True)
    controller.outdoor_welcome = AsyncMock(return_value=True)

    # Coffee machine
    controller.start_coffee = AsyncMock(return_value=True)

    return controller


# ==============================================================================
# ASYNC HELPERS
# ==============================================================================


@pytest.fixture
def event_loop_policy():
    """Get asyncio event loop policy."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture
async def async_timeout():
    """Fixture for async timeout helper."""

    async def _timeout(coro, seconds: float):
        return await asyncio.wait_for(coro, timeout=seconds)

    return _timeout


# ==============================================================================
# SAFETY FILTER MOCK
# ==============================================================================


@pytest.fixture
def mock_safety_filter():
    """Create a mock safety filter for CBF validation."""
    safety_filter = MagicMock()

    def evaluate_safety(context: dict) -> float:
        """Evaluate safety h(x) - must be >= 0."""
        # Default safe value
        h_value = 1.0

        # Check for known unsafe patterns
        action = context.get("action", "")

        if "emergency" in action.lower():
            h_value = 0.3  # Lower but still safe
        elif "fire" in action.lower():
            h_value = 0.2  # Emergency mode
        elif "bypass" in action.lower() or "override" in action.lower():
            h_value = 0.1  # Very cautious

        # Ensure h(x) >= 0 always
        return max(0.0, h_value)

    safety_filter.evaluate_safety = Mock(side_effect=evaluate_safety)
    safety_filter.is_safe = Mock(return_value=True)
    safety_filter.get_safety_report = Mock(
        return_value={
            "h_value": 1.0,
            "violations": [],
            "warnings": [],
        }
    )

    return safety_filter


# ==============================================================================
# TIMING HELPERS
# ==============================================================================


@pytest.fixture
def fibonacci_timings() -> dict[str, int]:
    """Fibonacci timing constants for animations/delays."""
    return {
        "micro": 89,  # Micro-interactions
        "button": 144,  # Button presses
        "modal": 233,  # Modal appearances
        "page": 377,  # Page transitions
        "complex": 610,  # Complex reveals
        "ambient": 987,  # Ambient motion
        "background": 1597,  # Background animations
        "breathing": 2584,  # Breathing effects
    }


# ==============================================================================
# TEST MARKERS
# ==============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "e2e: End-to-end integration tests")
    config.addinivalue_line("markers", "cross_device: Cross-device handoff tests")
    config.addinivalue_line("markers", "mesh: Mesh network constellation tests")
    config.addinivalue_line("markers", "user_journey: User journey scenario tests")
    config.addinivalue_line("markers", "slow: Slow tests that may take > 1 minute")
    config.addinivalue_line(
        "markers", "network_simulation: Tests with network condition simulation"
    )
