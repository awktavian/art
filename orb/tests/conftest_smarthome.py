"""💎 CRYSTAL COLONY — Smart Home Test Configuration

Shared test configuration, fixtures, and utilities for smart home testing.
Provides standardized test setup, mock integrations, and safety validation
helpers for the entire test suite.

Features:
- Standardized controller fixtures
- Mock integration factories
- Safety validation utilities
- Test environment configuration
- Performance measurement tools

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from kagami.core.safety import get_safety_filter
from kagami_smarthome import SmartHomeController, SmartHomeConfig
from kagami_smarthome.types import SecurityState, PresenceState, ActivityContext


# Configure test logging
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def cbf_filter():
    """Provide Control Barrier Function filter for safety validation."""
    return get_safety_filter()


@pytest.fixture
def base_config():
    """Provide base smart home configuration for testing."""
    return SmartHomeConfig(
        control4_host="192.168.1.100",
        control4_bearer_token="test_token_12345",
        control4_director_id="1234",
        unifi_host="192.168.1.1",
        unifi_username="test@example.com",
        unifi_password="test_password",
        denon_host="192.168.1.101",
        lg_tv_host="192.168.1.102",
        lg_tv_client_key="test_lg_key",
        samsung_tv_host="192.168.1.103",
        samsung_tv_mac="ab:cd:ef:12:34:56",
        tesla_email="test@example.com",
        tesla_password="test_password",
        august_email="test@example.com",
        august_password="test_password",
        eight_sleep_email="test@example.com",
        eight_sleep_password="test_password",
        oelo_host="192.168.1.104",
        mitsubishi_username="test@example.com",
        mitsubishi_password="test_password",
        dsc_host="192.168.1.105",
        dsc_port=4025,
        dsc_password="user",
        dsc_code="1234",
    )


@pytest.fixture
async def mock_controller(base_config):
    """Provide fully mocked smart home controller."""
    controller = SmartHomeController(base_config)

    # Mock all integrations
    await setup_mock_integrations(controller)

    return controller


@pytest.fixture
async def realistic_controller(base_config):
    """Provide controller with realistic mock responses."""
    controller = SmartHomeController(base_config)

    # Setup realistic mocks
    await setup_realistic_mock_integrations(controller)

    return controller


@pytest.fixture
async def failing_controller(base_config):
    """Provide controller with failing integrations for testing error handling."""
    controller = SmartHomeController(base_config)

    # Setup failing mocks
    await setup_failing_mock_integrations(controller)

    return controller


async def setup_mock_integrations(controller: SmartHomeController) -> None:
    """Setup basic mock integrations."""

    # Control4 integration
    controller._control4 = Mock()
    controller._control4.is_connected = True
    controller._control4.get_rooms = Mock(
        return_value={
            "1": {"name": "Living Room", "id": 1},
            "2": {"name": "Kitchen", "id": 2},
            "3": {"name": "Primary Bedroom", "id": 3},
            "4": {"name": "Office", "id": 4},
        }
    )
    controller._control4.get_lights = Mock(
        return_value={
            "101": {"name": "Living Room Table", "room": "Living Room", "level": 75},
            "102": {"name": "Kitchen Island", "room": "Kitchen", "level": 100},
            "103": {"name": "Bedroom Main", "room": "Primary Bedroom", "level": 25},
        }
    )
    controller._control4.get_shades = Mock(
        return_value={
            "201": {"name": "Living Room Window", "room": "Living Room", "level": 50},
            "202": {"name": "Kitchen Window", "room": "Kitchen", "level": 0},
        }
    )
    controller._control4.get_audio_zones = Mock(
        return_value={
            "301": {"name": "Living Room Audio", "room": "Living Room", "volume": 30},
            "302": {"name": "Kitchen Audio", "room": "Kitchen", "volume": 20},
        }
    )
    controller._control4.set_light_level = AsyncMock(return_value=True)
    controller._control4.set_shade_level = AsyncMock(return_value=True)
    controller._control4.set_room_volume = AsyncMock(return_value=True)
    controller._control4.fireplace_on = AsyncMock(return_value=True)
    controller._control4.fireplace_off = AsyncMock(return_value=True)
    controller._control4.mantelmount_recall = AsyncMock(return_value=True)
    controller._control4.mantelmount_home = AsyncMock(return_value=True)

    # UniFi integration
    controller._unifi = Mock()
    controller._unifi.is_connected = True
    controller._unifi.get_cameras = Mock(
        return_value={
            "cam1": {"name": "Front Door", "status": "connected"},
            "cam2": {"name": "Back Yard", "status": "connected"},
            "cam3": {"name": "Driveway", "status": "connected"},
            "cam4": {"name": "Side Gate", "status": "connected"},
        }
    )
    controller._unifi.get_wifi_devices = Mock(
        return_value={
            "device1": {"name": "iPhone", "mac": "aa:bb:cc:dd:ee:01"},
            "device2": {"name": "iPad", "mac": "aa:bb:cc:dd:ee:02"},
        }
    )

    # Denon integration
    controller._denon = Mock()
    controller._denon.is_connected = True
    controller._denon.get_zones = Mock(return_value=["Main", "Zone2"])
    controller._denon.get_sources = Mock(return_value=["HDMI1", "HDMI2", "Bluetooth"])
    controller._denon.power_on = AsyncMock(return_value=True)
    controller._denon.set_volume = AsyncMock(return_value=True)
    controller._denon.set_source = AsyncMock(return_value=True)
    controller._denon.set_sound_mode = AsyncMock(return_value=True)

    # August integration
    controller._august = Mock()
    controller._august.is_connected = True
    controller._august.get_locks = Mock(
        return_value={
            "lock1": Mock(name="Front Door", lock_state="locked", battery_level=0.85),
            "lock2": Mock(name="Back Door", lock_state="locked", battery_level=0.75),
        }
    )
    controller._august.lock_all = AsyncMock(return_value=True)
    controller._august.unlock_by_name = AsyncMock(return_value=True)
    controller._august.is_door_open = Mock(return_value=False)
    controller.get_lock_battery_levels = Mock(return_value={"front_door": 0.85, "back_door": 0.75})

    # Eight Sleep integration
    controller._eight_sleep = Mock()
    controller._eight_sleep.is_connected = True
    controller.is_anyone_in_bed = Mock(return_value=False)
    controller.is_anyone_asleep = Mock(return_value=False)
    controller._eight_sleep.set_temperature = AsyncMock(return_value=True)

    # LG TV integration
    controller._lg_tv = Mock()
    controller._lg_tv.is_connected = True
    controller._lg_tv.power_on = AsyncMock(return_value=True)
    controller._lg_tv.power_off = AsyncMock(return_value=True)
    controller._lg_tv.set_volume = AsyncMock(return_value=True)
    controller._lg_tv.launch_netflix = AsyncMock(return_value=True)
    controller._lg_tv.show_notification = AsyncMock(return_value=True)

    # Samsung TV integration
    controller._samsung_tv = Mock()
    controller._samsung_tv.is_connected = True
    controller._samsung_tv.power_on = AsyncMock(return_value=True)
    controller._samsung_tv.power_off = AsyncMock(return_value=True)
    controller._samsung_tv.enable_art_mode = AsyncMock(return_value=True)

    # Tesla integration
    controller._tesla = Mock()
    controller._tesla.is_connected = True
    controller.is_car_home = Mock(return_value=True)
    controller.get_car_battery = Mock(return_value=75)
    controller._tesla.start_climate = AsyncMock(return_value=True)
    controller._tesla.start_charging = AsyncMock(return_value=True)

    # Oelo integration
    controller._oelo = Mock()
    controller._oelo.is_connected = True
    controller._oelo.turn_on = AsyncMock(return_value=True)
    controller._oelo.turn_off = AsyncMock(return_value=True)
    controller._oelo.set_color = AsyncMock(return_value=True)
    controller._oelo.welcome_mode = AsyncMock(return_value=True)

    # Mitsubishi integration
    controller._mitsubishi = Mock()
    controller._mitsubishi.is_connected = True
    controller._mitsubishi.get_zones = Mock(
        return_value=[
            Mock(
                name="Office", zone_id="zone1", status={"current_temp": 72.5, "target_temp": 72.0}
            ),
            Mock(
                name="Bedroom", zone_id="zone2", status={"current_temp": 71.8, "target_temp": 71.0}
            ),
        ]
    )
    controller._mitsubishi.set_zone_temp = AsyncMock(return_value=True)
    controller._mitsubishi.set_away_mode = AsyncMock(return_value=True)
    controller.get_hvac_temps = Mock(return_value={"office": (72.5, 72.0), "bedroom": (71.8, 71.0)})
    controller.get_average_temp = Mock(return_value=72.2)

    # Envisalink integration
    controller._envisalink = Mock()
    controller._envisalink.is_connected = True
    controller._envisalink.get_partition = Mock(return_value=Mock(state=Mock(value="DISARMED")))
    controller._envisalink.arm_away = AsyncMock(return_value=True)
    controller._envisalink.arm_stay = AsyncMock(return_value=True)
    controller._envisalink.disarm = AsyncMock(return_value=True)
    controller.get_security_state = AsyncMock(return_value=SecurityState.DISARMED)
    controller.get_open_zones = Mock(return_value=[])
    controller.get_dsc_trouble_status = Mock(
        return_value={"ac_failure": False, "battery_low": False, "system_tamper": False}
    )

    # Room registry and orchestrator
    from kagami_smarthome.room import Room, RoomRegistry, RoomType, RoomState
    from kagami_smarthome.orchestrator import RoomOrchestrator

    # Create mock rooms
    rooms = [
        Room(id=1, name="Living Room", room_type=RoomType.LIVING_ROOM),
        Room(id=2, name="Kitchen", room_type=RoomType.KITCHEN),
        Room(id=3, name="Primary Bedroom", room_type=RoomType.BEDROOM),
        Room(id=4, name="Office", room_type=RoomType.OFFICE),
    ]

    controller._rooms = Mock(spec=RoomRegistry)
    controller._rooms.get_all = Mock(return_value=rooms)
    controller._rooms.get_by_name = Mock(
        side_effect=lambda name: next((r for r in rooms if r.name == name), None)
    )
    controller._rooms.get_occupied = Mock(return_value=[])

    controller._orchestrator = Mock(spec=RoomOrchestrator)
    controller._orchestrator.set_room_scene = AsyncMock(return_value=True)
    controller._orchestrator.enter_movie_mode = AsyncMock(return_value=True)
    controller._orchestrator.exit_movie_mode = AsyncMock(return_value=True)
    controller._orchestrator.goodnight = AsyncMock(return_value=True)
    controller._orchestrator.welcome_home = AsyncMock(return_value=True)
    controller._orchestrator.set_away_mode = AsyncMock(return_value=True)
    controller._orchestrator.is_movie_mode = False

    # Audio bridge
    controller._audio_bridge = Mock()
    controller._audio_bridge.is_initialized = True
    controller._audio_bridge.announce = AsyncMock(return_value=(True, "announcement_id"))
    controller._audio_bridge.announce_all = AsyncMock(return_value=(True, "announcement_id"))
    controller._audio_bridge.speak_to_room = AsyncMock(return_value=(True, "announcement_id"))
    controller._audio_bridge.get_available_rooms = Mock(
        return_value=["Living Room", "Kitchen", "Office", "Primary Bedroom"]
    )


async def setup_realistic_mock_integrations(controller: SmartHomeController) -> None:
    """Setup realistic mock integrations with proper delays and responses."""
    await setup_mock_integrations(controller)

    # Add realistic delays and responses
    async def realistic_delay(original_func, delay_ms: float = 100):
        await asyncio.sleep(delay_ms / 1000)
        if asyncio.iscoroutinefunction(original_func):
            return await original_func()
        return original_func()

    # Control4 with realistic delays
    controller._control4.set_light_level = AsyncMock(
        side_effect=lambda *args: realistic_delay(lambda: True, 150)
    )
    controller._control4.set_shade_level = AsyncMock(
        side_effect=lambda *args: realistic_delay(lambda: True, 2000)
    )

    # Denon with connection establishment time
    controller._denon.power_on = AsyncMock(
        side_effect=lambda *args: realistic_delay(lambda: True, 800)
    )

    # Tesla with cloud API delay
    controller._tesla.start_climate = AsyncMock(
        side_effect=lambda *args: realistic_delay(lambda: True, 3000)
    )


async def setup_failing_mock_integrations(controller: SmartHomeController) -> None:
    """Setup failing mock integrations for error handling tests."""

    # Control4 - connection refused
    controller._control4 = Mock()
    controller._control4.is_connected = False
    controller._control4.set_light_level = AsyncMock(
        side_effect=ConnectionRefusedError("Control4 offline")
    )

    # UniFi - authentication failure
    controller._unifi = Mock()
    controller._unifi.is_connected = False
    controller._unifi.get_cameras = Mock(side_effect=Exception("Authentication failed"))

    # Denon - timeout
    controller._denon = Mock()
    controller._denon.is_connected = False
    controller._denon.power_on = AsyncMock(side_effect=TimeoutError("Denon timeout"))

    # August - rate limited
    controller._august = Mock()
    controller._august.is_connected = False
    controller._august.lock_all = AsyncMock(side_effect=Exception("Rate limited"))

    # Other integrations offline
    for integration in [
        "eight_sleep",
        "lg_tv",
        "samsung_tv",
        "tesla",
        "oelo",
        "mitsubishi",
        "envisalink",
    ]:
        mock_integration = Mock()
        mock_integration.is_connected = False
        setattr(controller, f"_{integration}", mock_integration)


@pytest.fixture
def performance_timer():
    """Provide performance timing utilities."""

    class PerformanceTimer:
        def __init__(self):
            self.start_time = None
            self.measurements = {}

        def start(self, name: str = "default"):
            self.start_time = time.time()
            return self

        def stop(self, name: str = "default"):
            if self.start_time is None:
                raise ValueError("Timer not started")

            duration = time.time() - self.start_time
            self.measurements[name] = duration
            self.start_time = None
            return duration

        def __enter__(self):
            self.start()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.stop()

    return PerformanceTimer()


@pytest.fixture
def safety_validator(cbf_filter):
    """Provide safety validation utilities."""

    class SafetyValidator:
        def __init__(self, cbf_filter):
            self.cbf_filter = cbf_filter
            self.violations = []

        def validate_action(self, action_name: str, **context) -> float:
            """Validate action safety and return h(x) value."""
            h_value = self.cbf_filter.evaluate_safety({"action": action_name, **context})

            if h_value < 0:
                self.violations.append(
                    {
                        "action": action_name,
                        "h_value": h_value,
                        "context": context,
                        "timestamp": time.time(),
                    }
                )

            return h_value

        def assert_safe(self, action_name: str, **context):
            """Assert that action is safe (h(x) ≥ 0)."""
            h_value = self.validate_action(action_name, **context)
            assert h_value >= 0, f"Safety violation: {action_name} h={h_value:.3f}"

        def assert_safe_threshold(self, action_name: str, threshold: float = 0.5, **context):
            """Assert that action meets safety threshold."""
            h_value = self.validate_action(action_name, **context)
            assert h_value >= threshold, (
                f"Safety below threshold: {action_name} h={h_value:.3f} < {threshold}"
            )

        def get_violations(self) -> list[dict]:
            """Get all recorded safety violations."""
            return self.violations.copy()

        def clear_violations(self):
            """Clear violation history."""
            self.violations.clear()

    return SafetyValidator(cbf_filter)


@pytest.fixture
def mock_network_conditions():
    """Provide network condition simulation utilities."""

    class NetworkSimulator:
        def __init__(self):
            self.conditions = {}

        def set_condition(self, integration: str, condition: str):
            """Set network condition for integration."""
            self.conditions[integration] = condition

        def apply_conditions(self, controller: SmartHomeController):
            """Apply network conditions to controller integrations."""
            for integration, condition in self.conditions.items():
                mock_integration = getattr(controller, f"_{integration}", None)
                if not mock_integration:
                    continue

                if condition == "timeout":
                    mock_integration.connect = AsyncMock(side_effect=TimeoutError("Timeout"))
                elif condition == "connection_refused":
                    mock_integration.connect = AsyncMock(
                        side_effect=ConnectionRefusedError("Refused")
                    )
                elif condition == "slow":

                    async def slow_connect():
                        await asyncio.sleep(2.0)
                        return True

                    mock_integration.connect = slow_connect
                elif condition == "intermittent":

                    def intermittent_response():
                        import random

                        if random.random() < 0.3:
                            raise ConnectionError("Intermittent failure")
                        return True

                    mock_integration.connect = AsyncMock(side_effect=intermittent_response)

        def reset(self):
            """Reset all conditions."""
            self.conditions.clear()

    return NetworkSimulator()


@pytest.fixture
async def integration_health_monitor():
    """Provide integration health monitoring utilities."""
    from tests.monitoring.test_smarthome_health import SmartHomeHealthMonitor

    class HealthTestMonitor:
        def __init__(self):
            self.monitor = None

        async def start_monitoring(self, controller: SmartHomeController):
            """Start health monitoring for controller."""
            self.monitor = SmartHomeHealthMonitor(controller)
            await self.monitor.start_monitoring()
            return self.monitor

        async def stop_monitoring(self):
            """Stop health monitoring."""
            if self.monitor:
                await self.monitor.stop_monitoring()

        def get_health_status(self):
            """Get current health status."""
            if self.monitor:
                return self.monitor.get_system_health()
            return {}

        def get_integration_health(self):
            """Get integration health status."""
            if self.monitor:
                return self.monitor.get_integration_health()
            return {}

    return HealthTestMonitor()


# Async test utilities
@pytest.fixture
def event_loop():
    """Provide event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Test markers for categorization
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "safety: mark test as safety verification test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "network: mark test as network resilience test")
    config.addinivalue_line("markers", "security: mark test as security test")


# Environment configuration
@pytest.fixture(autouse=True)
def test_environment():
    """Configure test environment variables."""
    os.environ["KAGAMI_TEST_MODE"] = "true"
    os.environ["KAGAMI_LOG_LEVEL"] = "DEBUG"
    yield
    os.environ.pop("KAGAMI_TEST_MODE", None)
    os.environ.pop("KAGAMI_LOG_LEVEL", None)


# Test data providers
@pytest.fixture
def sample_device_data():
    """Provide sample device data for testing."""
    return {
        "lights": {
            "101": {"name": "Living Room Main", "level": 75, "on": True},
            "102": {"name": "Kitchen Island", "level": 100, "on": True},
            "103": {"name": "Bedroom Bedside", "level": 25, "on": True},
        },
        "shades": {
            "201": {"name": "Living Room Window", "level": 50},
            "202": {"name": "Kitchen Window", "level": 0},
        },
        "hvac_zones": [
            {"zone_id": "zone1", "name": "Office", "current_temp": 72.5, "target_temp": 72.0},
            {"zone_id": "zone2", "name": "Bedroom", "current_temp": 71.8, "target_temp": 71.0},
        ],
        "cameras": {
            "cam1": {"name": "Front Door", "status": "online"},
            "cam2": {"name": "Back Yard", "status": "online"},
        },
    }


@pytest.fixture
def sample_alert_data():
    """Provide sample alert data for testing."""
    return [
        {
            "id": "alert_001",
            "level": "warning",
            "message": "Low battery on Front Door lock",
            "component": "august",
            "timestamp": "2025-12-29T10:00:00Z",
        },
        {
            "id": "alert_002",
            "level": "critical",
            "message": "Control4 connection timeout",
            "component": "control4",
            "timestamp": "2025-12-29T10:05:00Z",
        },
    ]


# Helper functions for common test operations
def create_test_scenario_actions(controller: SmartHomeController) -> list[tuple[str, Any]]:
    """Create standard test scenario actions."""
    return [
        ("set_lights", lambda: controller.set_lights(75, ["Living Room"])),
        ("set_shades", lambda: controller.set_shades(50, ["Living Room"])),
        ("set_audio", lambda: controller.set_audio(30, "Living Room")),
        ("check_security", lambda: controller.get_security_state()),
        ("announce", lambda: controller.announce("Test message", ["Living Room"])),
    ]


def assert_integration_health(controller: SmartHomeController, min_connected: int = 5):
    """Assert minimum integration health."""
    status = controller.get_integration_status()
    connected_count = sum(1 for connected in status.values() if connected)
    assert connected_count >= min_connected, (
        f"Only {connected_count} integrations connected, need {min_connected}"
    )


async def wait_for_async_operations(timeout: float = 5.0):
    """Wait for pending async operations to complete."""
    try:
        await asyncio.wait_for(asyncio.gather(*asyncio.all_tasks()), timeout=timeout)
    except (TimeoutError, RuntimeError):
        pass  # Some tasks may not complete
