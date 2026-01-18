"""Tesla Streaming and Event Bus Tests.

Tests for:
- TeslaStreamingClient class (SSE streaming)
- TeslaEventBus class (event processing)
- Telemetry processing
- Derived state computation
- Event subscriptions
- Smart home integration
- Geofencing calculations

Created: December 31, 2025
"""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from kagami_smarthome.integrations.tesla import (
    HOME_LAT,
    HOME_LON,
    DrivingState,
    EventPayload,
    TelemetrySnapshot,
    TelemetryValue,
    TeslaEventBus,
    TeslaEventType,
    TeslaIntegration,
    TeslaPresenceState,
    TeslaStreamingClient,
    connect_tesla_event_bus,
    get_tesla_event_bus,
)
from kagami_smarthome.integrations.tesla.tesla import (
    TELEMETRY_FIELDS,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_tesla_integration():
    """Create mock Tesla integration for streaming tests."""
    mock = MagicMock(spec=TeslaIntegration)
    mock._vehicle_id = "12345678901234567"
    mock._vehicle_vin = "5YJ3E1EA1NF123456"
    mock._access_token = "test_access_token"
    return mock


@pytest.fixture
def streaming_client(mock_tesla_integration):
    """Create TeslaStreamingClient with mock integration."""
    return TeslaStreamingClient(mock_tesla_integration)


@pytest.fixture
def event_bus():
    """Create fresh TeslaEventBus."""
    return TeslaEventBus()


@pytest.fixture
def mock_smart_home():
    """Create mock smart home controller."""
    mock = MagicMock()
    mock.set_hvac_mode = AsyncMock()
    mock.set_lights = AsyncMock()
    mock.welcome_home = AsyncMock()
    mock.leaving_home = AsyncMock()
    mock.announce = AsyncMock()
    mock.announce_all = AsyncMock()
    mock.open_garage = AsyncMock()
    return mock


# =============================================================================
# STREAMING CLIENT TESTS
# =============================================================================


class TestTeslaStreamingClient:
    """Test TeslaStreamingClient."""

    def test_init(self, streaming_client, mock_tesla_integration):
        """Test streaming client initialization."""
        assert streaming_client._integration == mock_tesla_integration
        assert not streaming_client._running
        assert streaming_client._listener_task is None
        assert len(streaming_client._callbacks) == 0

    def test_is_connected_false_initially(self, streaming_client):
        """Test is_connected returns False initially."""
        assert streaming_client.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_without_vehicle_id(self, mock_tesla_integration):
        """Test connect fails without vehicle_id."""
        mock_tesla_integration._vehicle_id = None
        client = TeslaStreamingClient(mock_tesla_integration)

        result = await client.connect()

        assert result is False

    @pytest.mark.asyncio
    async def test_connect_without_access_token(self, mock_tesla_integration):
        """Test connect fails without access token."""
        mock_tesla_integration._access_token = None
        client = TeslaStreamingClient(mock_tesla_integration)

        result = await client.connect()

        assert result is False

    def test_on_event_callback(self, streaming_client):
        """Test registering event callback."""

        async def callback(field, value, timestamp):
            pass

        streaming_client.on_event(callback)

        assert callback in streaming_client._callbacks

    def test_off_event_callback(self, streaming_client):
        """Test unregistering event callback."""

        async def callback(field, value, timestamp):
            pass

        streaming_client.on_event(callback)
        streaming_client.off_event(callback)

        assert callback not in streaming_client._callbacks

    def test_on_alert_callback(self, streaming_client):
        """Test registering alert callback."""

        async def callback(signal, data):
            pass

        streaming_client.on_alert(callback)

        assert callback in streaming_client._alert_callbacks

    def test_off_alert_callback(self, streaming_client):
        """Test unregistering alert callback."""

        async def callback(signal, data):
            pass

        streaming_client.on_alert(callback)
        streaming_client.off_alert(callback)

        assert callback not in streaming_client._alert_callbacks

    @pytest.mark.asyncio
    async def test_disconnect(self, streaming_client):
        """Test disconnect cleans up properly."""
        streaming_client._running = True
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        streaming_client._session = mock_session

        await streaming_client.disconnect()

        assert streaming_client._running is False
        # Session gets set to None after close, so check the mock directly
        mock_session.close.assert_called_once()

    def test_get_stats(self, streaming_client, mock_tesla_integration):
        """Test get_stats returns correct structure."""
        stats = streaming_client.get_stats()

        assert "events_received" in stats
        assert "alerts_received" in stats
        assert "reconnects" in stats
        assert "connected" in stats
        assert "vehicle_id" in stats
        assert "callbacks" in stats
        assert "latency_summary" in stats
        assert stats["vehicle_id"] == mock_tesla_integration._vehicle_id

    @pytest.mark.asyncio
    async def test_handle_event_valid_json(self, streaming_client):
        """Test handle_event processes valid JSON."""
        received_events = []

        async def callback(field, value, timestamp):
            received_events.append((field, value))

        streaming_client.on_event(callback)

        # Simulate event data
        data = json.dumps(
            {
                "BatteryLevel": 75,
                "timestamp": time.time() * 1000,
            }
        )

        await streaming_client._handle_event(data)

        assert streaming_client._stats["events_received"] == 1

    @pytest.mark.asyncio
    async def test_handle_event_invalid_json(self, streaming_client):
        """Test handle_event handles invalid JSON gracefully."""
        await streaming_client._handle_event("not valid json")

        # Should not crash, stats should remain at 0
        assert streaming_client._stats["events_received"] == 0

    @pytest.mark.asyncio
    async def test_handle_event_with_alerts(self, streaming_client):
        """Test handle_event processes alerts."""
        received_alerts = []

        async def alert_callback(signal, data):
            received_alerts.append(signal)

        streaming_client.on_alert(alert_callback)

        data = json.dumps(
            {
                "Alerts": ["ESP_w001_stability", "BMS_w002_lowBattery"],
                "timestamp": time.time() * 1000,
            }
        )

        await streaming_client._handle_event(data)

        assert streaming_client._stats["alerts_received"] == 2
        assert "ESP_w001_stability" in received_alerts
        assert "BMS_w002_lowBattery" in received_alerts


# =============================================================================
# TELEMETRY FIELDS TESTS
# =============================================================================


class TestTelemetryFields:
    """Test telemetry field constants."""

    def test_telemetry_fields_not_empty(self):
        """Test TELEMETRY_FIELDS has content."""
        assert len(TELEMETRY_FIELDS) > 50

    def test_critical_fields_present(self):
        """Test critical telemetry fields are defined."""
        critical_fields = [
            "BatteryLevel",
            "Location",
            "Speed",
            "ChargeState",
            "InsideTemp",
            "OutsideTemp",
            "Locked",
            "SentryMode",
            "Alerts",
        ]

        for field in critical_fields:
            assert field in TELEMETRY_FIELDS


# =============================================================================
# EVENT BUS INITIALIZATION TESTS
# =============================================================================


class TestEventBusInitialization:
    """Test TeslaEventBus initialization."""

    def test_init(self, event_bus):
        """Test event bus initializes correctly."""
        assert event_bus._presence_state == TeslaPresenceState.UNKNOWN
        assert event_bus._driving_state == DrivingState.UNKNOWN
        assert len(event_bus._telemetry) == 0
        assert len(event_bus._history) == 0

    def test_init_subscribers(self, event_bus):
        """Test all event types have subscriber lists."""
        for event_type in TeslaEventType:
            assert event_type in event_bus._subscribers
            assert isinstance(event_bus._subscribers[event_type], list)

    def test_init_stats(self, event_bus):
        """Test stats are initialized to zero."""
        assert event_bus._stats["telemetry_received"] == 0
        assert event_bus._stats["events_emitted"] == 0
        assert event_bus._stats["presence_changes"] == 0


# =============================================================================
# EVENT SUBSCRIPTION TESTS
# =============================================================================


class TestEventSubscription:
    """Test event subscription system."""

    def test_subscribe(self, event_bus):
        """Test subscribing to events."""

        async def callback(payload):
            pass

        event_bus.subscribe(TeslaEventType.ARRIVAL_DETECTED, callback)

        assert callback in event_bus._subscribers[TeslaEventType.ARRIVAL_DETECTED]

    def test_unsubscribe(self, event_bus):
        """Test unsubscribing from events."""

        async def callback(payload):
            pass

        event_bus.subscribe(TeslaEventType.ARRIVAL_DETECTED, callback)
        event_bus.unsubscribe(TeslaEventType.ARRIVAL_DETECTED, callback)

        assert callback not in event_bus._subscribers[TeslaEventType.ARRIVAL_DETECTED]

    def test_unsubscribe_nonexistent(self, event_bus):
        """Test unsubscribing callback that isn't subscribed."""

        async def callback(payload):
            pass

        # Should not raise
        event_bus.unsubscribe(TeslaEventType.ARRIVAL_DETECTED, callback)

    @pytest.mark.asyncio
    async def test_emit(self, event_bus):
        """Test event emission."""
        received = []

        async def callback(payload):
            received.append(payload)

        event_bus.subscribe(TeslaEventType.ARRIVAL_DETECTED, callback)

        await event_bus._emit(TeslaEventType.ARRIVAL_DETECTED, {"location": (47.6815, -122.3406)})

        assert len(received) == 1
        assert received[0].event_type == TeslaEventType.ARRIVAL_DETECTED
        assert received[0].data["location"] == (47.6815, -122.3406)

    @pytest.mark.asyncio
    async def test_emit_increments_stats(self, event_bus):
        """Test emit increments stats."""
        await event_bus._emit(TeslaEventType.ARRIVAL_DETECTED, {})

        assert event_bus._stats["events_emitted"] == 1


# =============================================================================
# TELEMETRY PROCESSING TESTS
# =============================================================================


class TestTelemetryProcessing:
    """Test telemetry processing."""

    @pytest.mark.asyncio
    async def test_on_telemetry_stores_value(self, event_bus):
        """Test telemetry values are stored."""
        await event_bus.on_telemetry("BatteryLevel", 75, time.time())

        assert "BatteryLevel" in event_bus._telemetry
        assert event_bus._telemetry["BatteryLevel"].value == 75

    @pytest.mark.asyncio
    async def test_on_telemetry_increments_stats(self, event_bus):
        """Test telemetry increments stats."""
        await event_bus.on_telemetry("BatteryLevel", 75, time.time())

        assert event_bus._stats["telemetry_received"] == 1

    @pytest.mark.asyncio
    async def test_get_value(self, event_bus):
        """Test _get_value helper."""
        event_bus._telemetry["BatteryLevel"] = TelemetryValue(75, time.time())

        assert event_bus._get_value("BatteryLevel") == 75
        assert event_bus._get_value("Nonexistent") is None
        assert event_bus._get_value("Nonexistent", 100) == 100


# =============================================================================
# LOCATION PROCESSING TESTS
# =============================================================================


class TestLocationProcessing:
    """Test location and geofencing."""

    @pytest.mark.asyncio
    async def test_process_location_dict(self, event_bus):
        """Test processing location as dict."""
        await event_bus._process_location({"latitude": 47.6815, "longitude": -122.3406}, None)

        assert event_bus._last_location == (47.6815, -122.3406)

    @pytest.mark.asyncio
    async def test_process_location_tuple(self, event_bus):
        """Test processing location as tuple."""
        await event_bus._process_location((47.6815, -122.3406), None)

        assert event_bus._last_location == (47.6815, -122.3406)

    @pytest.mark.asyncio
    async def test_process_location_emits_arrival(self, event_bus):
        """Test arrival event is emitted when entering home."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.ARRIVAL_DETECTED, callback)
        event_bus._last_at_home = False

        # Move to home location
        await event_bus._process_location({"latitude": HOME_LAT, "longitude": HOME_LON}, None)

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.ARRIVAL_DETECTED

    @pytest.mark.asyncio
    async def test_process_location_emits_departure(self, event_bus):
        """Test departure event is emitted when leaving home."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.DEPARTURE_DETECTED, callback)
        event_bus._last_at_home = True

        # Move away from home
        await event_bus._process_location(
            {"latitude": 47.5, "longitude": -122.5},  # Different location
            None,
        )

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.DEPARTURE_DETECTED

    def test_is_at_home_true(self, event_bus):
        """Test is_at_home returns True at home."""
        assert event_bus._is_at_home(HOME_LAT, HOME_LON) is True

    def test_is_at_home_false(self, event_bus):
        """Test is_at_home returns False away from home."""
        # Pike Place Market - about 3 miles away
        assert event_bus._is_at_home(47.6097, -122.3422) is False

    def test_distance_to_home(self, event_bus):
        """Test distance calculation."""
        event_bus._last_location = (47.6097, -122.3422)  # Pike Place

        distance = event_bus._distance_to_home()

        # Should be approximately 5 miles (more accurate calculation)
        assert 4.0 < distance < 6.0

    def test_distance_to_home_no_location(self, event_bus):
        """Test distance returns infinity without location."""
        event_bus._last_location = None

        assert event_bus._distance_to_home() == float("inf")


# =============================================================================
# SPEED PROCESSING TESTS
# =============================================================================


class TestSpeedProcessing:
    """Test speed-related telemetry processing."""

    @pytest.mark.asyncio
    async def test_process_speed_driving_started(self, event_bus):
        """Test driving_started event is emitted."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.DRIVING_STARTED, callback)

        # Simulate speed change from 0 to moving
        old_value = TelemetryValue(0, time.time())
        await event_bus._process_speed(45, old_value)

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.DRIVING_STARTED
        assert events[0].data["speed"] == 45

    @pytest.mark.asyncio
    async def test_process_speed_driving_stopped(self, event_bus):
        """Test driving_stopped event is emitted."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.DRIVING_STOPPED, callback)

        # Simulate speed change from moving to 0
        old_value = TelemetryValue(45, time.time())
        await event_bus._process_speed(0, old_value)

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.DRIVING_STOPPED


# =============================================================================
# SHIFT STATE PROCESSING TESTS
# =============================================================================


class TestShiftStateProcessing:
    """Test shift state processing."""

    @pytest.mark.asyncio
    async def test_process_shift_state_parked_home(self, event_bus):
        """Test parked_home event when parking at home."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.PARKED_HOME, callback)
        event_bus._last_at_home = True

        # Shift from D to P
        old_value = TelemetryValue("D", time.time())
        await event_bus._process_shift_state("P", old_value)

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.PARKED_HOME

    @pytest.mark.asyncio
    async def test_process_shift_state_parked_away(self, event_bus):
        """Test parked_away event when parking away."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.PARKED_AWAY, callback)
        event_bus._last_at_home = False
        event_bus._last_location = (47.5, -122.5)

        # Shift from D to P
        old_value = TelemetryValue("D", time.time())
        await event_bus._process_shift_state("P", old_value)

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.PARKED_AWAY


# =============================================================================
# CHARGE STATE PROCESSING TESTS
# =============================================================================


class TestChargeStateProcessing:
    """Test charge state processing."""

    @pytest.mark.asyncio
    async def test_process_charge_started(self, event_bus):
        """Test charge_started event."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.CHARGE_STARTED, callback)

        old_value = TelemetryValue("Disconnected", time.time())
        await event_bus._process_charge_state("Charging", old_value)

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.CHARGE_STARTED

    @pytest.mark.asyncio
    async def test_process_charge_complete(self, event_bus):
        """Test charge_complete event."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.CHARGE_COMPLETE, callback)

        old_value = TelemetryValue("Charging", time.time())
        await event_bus._process_charge_state("Complete", old_value)

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.CHARGE_COMPLETE


# =============================================================================
# CLIMATE PROCESSING TESTS
# =============================================================================


class TestClimateProcessing:
    """Test climate-related processing."""

    @pytest.mark.asyncio
    async def test_process_inside_temp_pet_warning(self, event_bus):
        """Test pet temperature warning in dog mode."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.PET_TEMP_WARNING, callback)
        event_bus._telemetry["ClimateKeeperMode"] = TelemetryValue("dog", time.time())

        await event_bus._process_inside_temp(84)  # Above warning threshold

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.PET_TEMP_WARNING
        assert events[0].data["temp_f"] == 84

    @pytest.mark.asyncio
    async def test_process_inside_temp_pet_critical(self, event_bus):
        """Test pet temperature critical in dog mode."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.PET_TEMP_CRITICAL, callback)
        event_bus._telemetry["ClimateKeeperMode"] = TelemetryValue("dog", time.time())

        await event_bus._process_inside_temp(90)  # Above critical threshold

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.PET_TEMP_CRITICAL

    @pytest.mark.asyncio
    async def test_process_inside_temp_no_alert_without_climate_keeper(self, event_bus):
        """Test no pet alert without dog/camp mode."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.PET_TEMP_WARNING, callback)
        event_bus.subscribe(TeslaEventType.PET_TEMP_CRITICAL, callback)
        # No climate keeper mode set

        await event_bus._process_inside_temp(100)

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_process_climate_keeper_active(self, event_bus):
        """Test climate keeper active event."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.CLIMATE_KEEPER_ACTIVE, callback)

        await event_bus._process_climate_keeper("dog", None)

        assert len(events) == 1
        assert events[0].data["mode"] == "dog"


# =============================================================================
# ALERT PROCESSING TESTS
# =============================================================================


class TestAlertProcessing:
    """Test alert processing."""

    @pytest.mark.asyncio
    async def test_process_critical_alert(self, event_bus):
        """Test critical alert processing."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.SAFETY_ALERT, callback)

        await event_bus._process_alerts(["PULL OVER SAFELY - Vehicle shutting down"])

        assert len(events) == 1
        assert events[0].event_type == TeslaEventType.SAFETY_ALERT
        assert events[0].data["priority"] == "critical"

    def test_is_critical_alert(self, event_bus):
        """Test critical alert detection."""
        assert event_bus._is_critical_alert("PULL OVER SAFELY") is True
        assert event_bus._is_critical_alert("Vehicle shutting down") is True
        assert event_bus._is_critical_alert("ABS disabled") is True
        assert event_bus._is_critical_alert("Brake system fault") is True
        assert event_bus._is_critical_alert("Airbag sensor issue") is True
        assert event_bus._is_critical_alert("Low washer fluid") is False


# =============================================================================
# SENTRY MODE PROCESSING TESTS
# =============================================================================


class TestSentryProcessing:
    """Test sentry mode processing."""

    @pytest.mark.asyncio
    async def test_process_sentry_changed(self, event_bus):
        """Test security_changed event on sentry toggle."""
        events = []

        async def callback(payload):
            events.append(payload)

        event_bus.subscribe(TeslaEventType.SECURITY_CHANGED, callback)

        old_value = TelemetryValue(False, time.time())
        await event_bus._process_sentry(True, old_value)

        assert len(events) == 1
        assert events[0].data["sentry_mode"] is True


# =============================================================================
# STATE COMPUTATION TESTS
# =============================================================================


class TestStateComputation:
    """Test derived state computation."""

    def test_recompute_presence_parked_home(self, event_bus):
        """Test presence state when parked at home."""
        event_bus._last_at_home = True
        event_bus._telemetry["ShiftState"] = TelemetryValue("P", time.time())
        event_bus._telemetry["Speed"] = TelemetryValue(0, time.time())

        event_bus._recompute_presence()

        assert event_bus._presence_state == TeslaPresenceState.PARKED_HOME

    def test_recompute_presence_parked_away(self, event_bus):
        """Test presence state when parked away."""
        event_bus._last_at_home = False
        event_bus._telemetry["ShiftState"] = TelemetryValue("P", time.time())
        event_bus._telemetry["Speed"] = TelemetryValue(0, time.time())

        event_bus._recompute_presence()

        assert event_bus._presence_state == TeslaPresenceState.PARKED_AWAY

    def test_recompute_driving_states(self, event_bus):
        """Test driving state computation."""
        event_bus._telemetry["ShiftState"] = TelemetryValue("P", time.time())
        event_bus._recompute_driving()
        assert event_bus._driving_state == DrivingState.PARKED

        event_bus._telemetry["ShiftState"] = TelemetryValue("D", time.time())
        event_bus._telemetry["Speed"] = TelemetryValue(0, time.time())
        event_bus._recompute_driving()
        assert event_bus._driving_state == DrivingState.STOPPED

        event_bus._telemetry["Speed"] = TelemetryValue(10, time.time())
        event_bus._recompute_driving()
        assert event_bus._driving_state == DrivingState.MOVING_SLOW

        event_bus._telemetry["Speed"] = TelemetryValue(50, time.time())
        event_bus._recompute_driving()
        assert event_bus._driving_state == DrivingState.MOVING_FAST


# =============================================================================
# HELPER METHOD TESTS
# =============================================================================


class TestHelperMethods:
    """Test helper calculation methods."""

    def test_haversine(self, event_bus):
        """Test haversine distance calculation."""
        # Green Lake to Pike Place: ~5 miles (more accurate measurement)
        distance = event_bus._haversine(
            47.6815,
            -122.3406,  # Green Lake
            47.6097,
            -122.3422,  # Pike Place
        )
        assert 4.0 < distance < 6.0

        # Same point
        distance = event_bus._haversine(47.6815, -122.3406, 47.6815, -122.3406)
        assert distance < 0.001

    def test_bearing(self, event_bus):
        """Test bearing calculation."""
        # Green Lake to downtown Seattle (roughly south)
        bearing = event_bus._bearing(
            47.6815,
            -122.3406,  # Green Lake
            47.6097,
            -122.3422,  # Pike Place
        )
        # Should be roughly south (180 +/- 45)
        assert 135 < bearing < 225

    def test_is_heading_home(self, event_bus):
        """Test heading toward home detection."""
        # Position south of home, heading north (toward home)
        event_bus._last_location = (47.6, -122.3406)
        event_bus._telemetry["Heading"] = TelemetryValue(0, time.time())  # North

        assert event_bus._is_heading_home() is True

        # Same position, heading south (away from home)
        event_bus._telemetry["Heading"] = TelemetryValue(180, time.time())
        assert event_bus._is_heading_home() is False

    def test_estimate_eta(self, event_bus):
        """Test ETA estimation."""
        # 3 miles away at 30 mph = ~6 min + 2 min buffer = ~8 min
        event_bus._last_location = (47.6097, -122.3422)  # Pike Place
        event_bus._telemetry["Speed"] = TelemetryValue(30, time.time())

        eta = event_bus._estimate_eta()

        assert 5 < eta < 15

    def test_is_late_night(self, event_bus):
        """Test late night detection."""
        # This is time-dependent, just ensure it doesn't crash
        result = event_bus._is_late_night()
        assert isinstance(result, bool)


# =============================================================================
# PROPERTIES TESTS
# =============================================================================


class TestProperties:
    """Test event bus properties."""

    def test_presence_state(self, event_bus):
        """Test presence_state property."""
        event_bus._presence_state = TeslaPresenceState.ARRIVING
        assert event_bus.presence_state == TeslaPresenceState.ARRIVING

    def test_driving_state(self, event_bus):
        """Test driving_state property."""
        event_bus._driving_state = DrivingState.MOVING_FAST
        assert event_bus.driving_state == DrivingState.MOVING_FAST

    def test_is_home(self, event_bus):
        """Test is_home property."""
        event_bus._presence_state = TeslaPresenceState.PARKED_HOME
        assert event_bus.is_home is True

        event_bus._presence_state = TeslaPresenceState.PARKED_AWAY
        assert event_bus.is_home is False

    def test_is_moving(self, event_bus):
        """Test is_moving property."""
        event_bus._driving_state = DrivingState.MOVING_FAST
        assert event_bus.is_moving is True

        event_bus._driving_state = DrivingState.PARKED
        assert event_bus.is_moving is False

    def test_stats_property(self, event_bus):
        """Test stats property."""
        event_bus._last_at_home = True
        event_bus._last_location = (47.6815, -122.3406)

        stats = event_bus.stats

        assert "telemetry_received" in stats
        assert "events_emitted" in stats
        assert "presence_state" in stats
        assert "driving_state" in stats
        assert "at_home" in stats


# =============================================================================
# SMART HOME INTEGRATION TESTS
# =============================================================================


class TestSmartHomeIntegration:
    """Test smart home integration."""

    @pytest.mark.asyncio
    async def test_connect_smart_home(self, event_bus, mock_smart_home):
        """Test connecting smart home controller."""
        await event_bus.connect_smart_home(mock_smart_home)

        assert event_bus._smart_home == mock_smart_home

        # Should have subscribed to events
        assert len(event_bus._subscribers[TeslaEventType.ARRIVAL_IMMINENT]) > 0
        assert len(event_bus._subscribers[TeslaEventType.ARRIVAL_DETECTED]) > 0
        assert len(event_bus._subscribers[TeslaEventType.DEPARTURE_DETECTED]) > 0

    @pytest.mark.asyncio
    async def test_arrival_triggers_welcome_home(self, event_bus, mock_smart_home):
        """Test arrival triggers welcome_home."""
        await event_bus.connect_smart_home(mock_smart_home)

        await event_bus._emit(TeslaEventType.ARRIVAL_DETECTED, {"location": (47.6815, -122.3406)})

        mock_smart_home.welcome_home.assert_called_once()

    @pytest.mark.asyncio
    async def test_departure_triggers_leaving_home(self, event_bus, mock_smart_home):
        """Test departure triggers leaving_home."""
        await event_bus.connect_smart_home(mock_smart_home)

        await event_bus._emit(TeslaEventType.DEPARTURE_DETECTED, {"location": (47.6815, -122.3406)})

        mock_smart_home.leaving_home.assert_called_once()

    @pytest.mark.asyncio
    async def test_pet_warning_triggers_announce(self, event_bus, mock_smart_home):
        """Test pet warning triggers announcement."""
        await event_bus.connect_smart_home(mock_smart_home)

        await event_bus._emit(TeslaEventType.PET_TEMP_WARNING, {"temp_f": 85, "mode": "dog"})

        mock_smart_home.announce.assert_called_once()

    @pytest.mark.asyncio
    async def test_pet_critical_triggers_announce_all(self, event_bus, mock_smart_home):
        """Test pet critical triggers announce_all."""
        await event_bus.connect_smart_home(mock_smart_home)

        await event_bus._emit(TeslaEventType.PET_TEMP_CRITICAL, {"temp_f": 95, "mode": "dog"})

        mock_smart_home.announce_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_safety_alert_triggers_announce_all(self, event_bus, mock_smart_home):
        """Test safety alert triggers announce_all."""
        await event_bus.connect_smart_home(mock_smart_home)

        await event_bus._emit(TeslaEventType.SAFETY_ALERT, {"signal": "PULL OVER"})

        mock_smart_home.announce_all.assert_called_once()


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


class TestFactoryFunctions:
    """Test factory functions."""

    def test_get_tesla_event_bus_singleton(self):
        """Test get_tesla_event_bus returns singleton."""
        # Reset singleton
        import kagami_smarthome.integrations.tesla_event_bus as module

        module._event_bus = None

        bus1 = get_tesla_event_bus()
        bus2 = get_tesla_event_bus()

        assert bus1 is bus2

        # Cleanup
        module._event_bus = None

    @pytest.mark.asyncio
    async def test_connect_tesla_event_bus(self, mock_tesla_integration, mock_smart_home):
        """Test connect_tesla_event_bus factory."""
        # Reset singleton
        import kagami_smarthome.integrations.tesla_event_bus as module

        module._event_bus = None

        streaming = TeslaStreamingClient(mock_tesla_integration)

        bus = await connect_tesla_event_bus(streaming, mock_smart_home)

        assert bus._smart_home == mock_smart_home
        assert bus.on_telemetry in streaming._callbacks

        # Cleanup
        module._event_bus = None


# =============================================================================
# DATA STRUCTURE TESTS
# =============================================================================


class TestDataStructures:
    """Test data structure classes."""

    def test_telemetry_value(self):
        """Test TelemetryValue dataclass."""
        now = time.time()
        tv = TelemetryValue(value=75, timestamp=now)

        assert tv.value == 75
        assert tv.timestamp == now
        assert tv.age_seconds < 1

    def test_event_payload(self):
        """Test EventPayload dataclass."""
        payload = EventPayload(
            event_type=TeslaEventType.ARRIVAL_DETECTED,
            timestamp=time.time(),
            data={"location": (47.6815, -122.3406)},
        )

        assert payload.event_type == TeslaEventType.ARRIVAL_DETECTED
        assert payload.data["location"] == (47.6815, -122.3406)

    def test_telemetry_snapshot(self):
        """Test TelemetrySnapshot dataclass."""
        snapshot = TelemetrySnapshot(
            timestamp=time.time(),
            location=(47.6815, -122.3406),
            speed=0,
            shift_state="P",
            heading=180,
            battery_level=75,
            charge_state="Disconnected",
            inside_temp=22.0,
            climate_keeper_mode=None,
            locked=True,
            sentry_mode=False,
        )

        assert snapshot.location == (47.6815, -122.3406)
        assert snapshot.battery_level == 75


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestEnums:
    """Test event bus enums."""

    def test_tesla_event_type_values(self):
        """Test TeslaEventType enum values."""
        assert TeslaEventType.ARRIVAL_IMMINENT.value == "arrival_imminent"
        assert TeslaEventType.ARRIVAL_DETECTED.value == "arrival_detected"
        assert TeslaEventType.DEPARTURE_DETECTED.value == "departure_detected"
        assert TeslaEventType.PARKED_HOME.value == "parked_home"
        assert TeslaEventType.CHARGE_STARTED.value == "charge_started"
        assert TeslaEventType.PET_TEMP_CRITICAL.value == "pet_temp_critical"
        assert TeslaEventType.SAFETY_ALERT.value == "safety_alert"

    def test_tesla_presence_state_values(self):
        """Test TeslaPresenceState enum values."""
        assert TeslaPresenceState.PARKED_HOME.value == "parked_home"
        assert TeslaPresenceState.PARKED_AWAY.value == "parked_away"
        assert TeslaPresenceState.DRIVING_HOME.value == "driving_home"
        assert TeslaPresenceState.DRIVING_AWAY.value == "driving_away"
        assert TeslaPresenceState.ARRIVING.value == "arriving"

    def test_driving_state_values(self):
        """Test DrivingState enum values."""
        assert DrivingState.PARKED.value == "parked"
        assert DrivingState.STOPPED.value == "stopped"
        assert DrivingState.MOVING_SLOW.value == "moving_slow"
        assert DrivingState.MOVING_FAST.value == "moving_fast"
