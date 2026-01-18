"""Tests for Tesla Companion Protocol.

Tests cover:
- Connection management
- Speak commands with retry
- Circuit breaker behavior
- Health checks
- Device failover
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from kagami_smarthome.integrations.tesla import (
    CompanionState,
    CompanionStatus,
    SpeakResult,
    TeslaCompanionProtocol,
    get_companion_protocol,
)
from kagami_smarthome.integrations.tesla.tesla import MessageType

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def protocol():
    """Create a fresh protocol instance for each test."""
    return TeslaCompanionProtocol()


@pytest.fixture
def mock_send():
    """Create a mock send function."""
    return AsyncMock()


# =============================================================================
# CONNECTION TESTS
# =============================================================================


class TestConnectionManagement:
    """Test connection registration and unregistration."""

    @pytest.mark.asyncio
    async def test_register_connection(self, protocol, mock_send):
        """Test registering a new connection."""
        await protocol.register_connection(mock_send, "device_1")

        assert "device_1" in protocol.connected_devices
        status = protocol.get_status("device_1")
        assert status.connected is True
        assert status.last_seen > 0

    @pytest.mark.asyncio
    async def test_unregister_connection(self, protocol, mock_send):
        """Test unregistering a connection."""
        await protocol.register_connection(mock_send, "device_1")
        await protocol.unregister_connection("device_1")

        assert "device_1" not in protocol.connected_devices
        status = protocol.get_status("device_1")
        assert status.connected is False

    @pytest.mark.asyncio
    async def test_multiple_connections(self, protocol):
        """Test multiple devices can connect."""
        await protocol.register_connection(AsyncMock(), "device_1")
        await protocol.register_connection(AsyncMock(), "device_2")

        assert len(protocol.connected_devices) == 2
        assert "device_1" in protocol.connected_devices
        assert "device_2" in protocol.connected_devices


# =============================================================================
# MESSAGE HANDLING TESTS
# =============================================================================


class TestMessageHandling:
    """Test protocol message handling."""

    @pytest.mark.asyncio
    async def test_handle_status_message(self, protocol, mock_send):
        """Test handling status update."""
        await protocol.register_connection(mock_send, "device_1")

        await protocol.handle_message(
            {
                "type": "status",
                "connected": True,
                "bluetooth": True,
                "bluetooth_device": "Tesla Model S",
                "volume": 0.8,
            },
            "device_1",
        )

        status = protocol.get_status("device_1")
        assert status.bluetooth_connected is True
        assert status.bluetooth_device == "Tesla Model S"
        assert status.volume == 0.8

    @pytest.mark.asyncio
    async def test_handle_pong_calculates_latency(self, protocol, mock_send):
        """Test pong response latency calculation."""
        await protocol.register_connection(mock_send, "device_1")

        sent_time = time.time() - 0.05  # 50ms ago
        await protocol.handle_message(
            {
                "type": "pong",
                "sent_time": sent_time,
            },
            "device_1",
        )

        status = protocol.get_status("device_1")
        assert status.latency_ms > 0
        assert status.latency_ms < 200  # Should be around 50ms


# =============================================================================
# SPEAK TESTS
# =============================================================================


class TestSpeak:
    """Test speak command handling."""

    @pytest.mark.asyncio
    async def test_speak_no_device_returns_error(self, protocol):
        """Test speak fails when no devices connected."""
        result = await protocol.speak("Hello", "https://example.com/audio.mp3")

        assert result.success is False
        assert "No companion device" in result.error

    @pytest.mark.asyncio
    async def test_speak_sends_to_ready_device(self, protocol, mock_send):
        """Test speak sends to a ready device."""
        await protocol.register_connection(mock_send, "device_1")

        # Mark as ready with Bluetooth
        await protocol.handle_message(
            {
                "type": "status",
                "connected": True,
                "bluetooth": True,
            },
            "device_1",
        )

        # Start speak (don't wait for completion)
        speak_task = asyncio.create_task(
            protocol.speak("Hello", "https://example.com/audio.mp3", timeout=0.5)
        )

        # Give it time to send
        await asyncio.sleep(0.1)

        # Check message was sent
        assert mock_send.called
        call_data = mock_send.call_args[0][0]
        import json

        data = json.loads(call_data)
        assert data["type"] == "speak"
        assert data["text"] == "Hello"
        assert data["audio_url"] == "https://example.com/audio.mp3"

        # Cleanup
        speak_task.cancel()
        try:
            await speak_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_speak_completes_on_success_response(self, protocol, mock_send):
        """Test speak completes when device responds with success."""
        await protocol.register_connection(mock_send, "device_1")

        # Mark as ready
        await protocol.handle_message(
            {
                "type": "status",
                "connected": True,
                "bluetooth": True,
            },
            "device_1",
        )

        # Start speak
        speak_task = asyncio.create_task(
            protocol.speak("Hello", "https://example.com/audio.mp3", timeout=5)
        )

        # Give it time to send
        await asyncio.sleep(0.1)

        # Get the request_id from the sent message
        import json

        sent_data = json.loads(mock_send.call_args[0][0])
        request_id = sent_data["request_id"]

        # Simulate success response
        await protocol.handle_message(
            {
                "type": "speak_complete",
                "request_id": request_id,
                "success": True,
                "duration_ms": 1500,
            },
            "device_1",
        )

        # Should complete now
        result = await speak_task
        assert result.success is True
        assert result.duration_ms == 1500


# =============================================================================
# CIRCUIT BREAKER TESTS
# =============================================================================


class TestCircuitBreaker:
    """Test circuit breaker behavior."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self, protocol):
        """Test circuit breaker opens after threshold failures."""
        protocol._record_failure("device_1")
        protocol._record_failure("device_1")
        protocol._record_failure("device_1")
        protocol._record_failure("device_1")
        protocol._record_failure("device_1")  # 5 failures = threshold

        assert protocol._is_circuit_open("device_1") is True
        assert protocol._stats["circuit_breaks"] == 1

    @pytest.mark.asyncio
    async def test_success_resets_failures(self, protocol):
        """Test success resets failure count."""
        protocol._record_failure("device_1")
        protocol._record_failure("device_1")
        protocol._record_success("device_1")

        assert protocol._circuit_failures.get("device_1", 0) == 0
        assert protocol._is_circuit_open("device_1") is False

    @pytest.mark.asyncio
    async def test_circuit_resets_after_timeout(self, protocol):
        """Test circuit breaker resets after timeout."""
        # Open the circuit
        for _ in range(5):
            protocol._record_failure("device_1")

        assert protocol._is_circuit_open("device_1") is True

        # Manually expire the circuit
        protocol._circuit_open_until["device_1"] = time.time() - 1

        # Should be closed now
        assert protocol._is_circuit_open("device_1") is False


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_no_devices(self, protocol):
        """Test health check with no devices."""
        health = await protocol.health_check()

        assert health["healthy"] is False
        assert health["ready_count"] == 0
        assert len(health["devices"]) == 0

    @pytest.mark.asyncio
    async def test_health_check_with_ready_device(self, protocol, mock_send):
        """Test health check with ready device."""
        await protocol.register_connection(mock_send, "device_1")
        await protocol.handle_message(
            {
                "type": "status",
                "connected": True,
                "bluetooth": True,
            },
            "device_1",
        )

        health = await protocol.health_check()

        assert health["healthy"] is True
        assert health["ready_count"] == 1
        assert "device_1" in health["devices"]
        assert health["devices"]["device_1"]["bluetooth"] is True

    @pytest.mark.asyncio
    async def test_health_check_reports_issues(self, protocol, mock_send):
        """Test health check reports issues."""
        await protocol.register_connection(mock_send, "device_1")
        # Device connected but no Bluetooth

        health = await protocol.health_check()

        assert health["healthy"] is False
        assert "no Bluetooth" in str(health["issues"])


# =============================================================================
# STATS TESTS
# =============================================================================


class TestStats:
    """Test statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_initial(self, protocol):
        """Test initial stats."""
        stats = protocol.get_stats()

        assert stats["speaks_requested"] == 0
        assert stats["speaks_completed"] == 0
        assert stats["speaks_failed"] == 0
        assert stats["connected_devices"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_connection(self, protocol, mock_send):
        """Test stats after connection."""
        await protocol.register_connection(mock_send, "device_1")

        stats = protocol.get_stats()
        assert stats["connected_devices"] == 1


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


class TestFactoryFunction:
    """Test factory function."""

    def test_get_companion_protocol_returns_singleton(self):
        """Test factory returns singleton."""
        protocol1 = get_companion_protocol()
        protocol2 = get_companion_protocol()

        assert protocol1 is protocol2


# =============================================================================
# DATA CLASSES TESTS
# =============================================================================


class TestDataClasses:
    """Test data class behavior."""

    def test_companion_status_is_ready(self):
        """Test CompanionStatus.is_ready property."""
        status = CompanionStatus(connected=True, bluetooth_connected=True)
        assert status.is_ready is True

        status = CompanionStatus(connected=True, bluetooth_connected=False)
        assert status.is_ready is False

        status = CompanionStatus(connected=False, bluetooth_connected=True)
        assert status.is_ready is False

    def test_companion_status_is_car(self):
        """Test CompanionStatus.is_car property."""
        # By type
        status = CompanionStatus(bluetooth_type="car")
        assert status.is_car is True
        assert status.is_glasses is False

        # By device name
        status = CompanionStatus(bluetooth_device="Tesla Model S")
        assert status.is_car is True

        status = CompanionStatus(bluetooth_device="Random Speaker")
        assert status.is_car is False

    def test_companion_status_is_glasses(self):
        """Test CompanionStatus.is_glasses property."""
        # By type
        status = CompanionStatus(bluetooth_type="glasses")
        assert status.is_glasses is True
        assert status.is_car is False

        # By device name
        status = CompanionStatus(bluetooth_device="Ray-Ban Meta")
        assert status.is_glasses is True

        status = CompanionStatus(bluetooth_device="Random Speaker")
        assert status.is_glasses is False

    def test_speak_result_defaults(self):
        """Test SpeakResult defaults."""
        result = SpeakResult(success=True, request_id="test_123")

        assert result.success is True
        assert result.request_id == "test_123"
        assert result.error is None
        assert result.latency_ms == 0.0


# =============================================================================
# ENUMS TESTS
# =============================================================================


class TestEnums:
    """Test enum values."""

    def test_companion_state_values(self):
        """Test CompanionState enum values."""
        assert CompanionState.DISCONNECTED.value == "disconnected"
        assert CompanionState.CONNECTED.value == "connected"
        assert CompanionState.BLUETOOTH_READY.value == "bluetooth_ready"

    def test_message_type_values(self):
        """Test MessageType enum values."""
        assert MessageType.SPEAK.value == "speak"
        assert MessageType.STOP.value == "stop"
        assert MessageType.STATUS.value == "status"
        assert MessageType.SPEAK_COMPLETE.value == "speak_complete"
