"""Tests for MultiDeviceCoordinator - covers 304 lines."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kagami.core.ambient.multi_device_coordinator import (
    Device,
    DeviceStatus,
    DeviceType,
    HandoffRequest,
    MultiDeviceCoordinator,
)


class TestMultiDeviceCoordinatorInit:
    """Test MultiDeviceCoordinator initialization."""

    def test_init_creates_empty_devices_dict(self) -> None:
        """Test coordinator initializes with empty devices dict."""
        coordinator = MultiDeviceCoordinator()
        assert coordinator.devices == {}
        assert isinstance(coordinator.devices, dict)

    def test_init_sets_no_active_device(self) -> None:
        """Test coordinator initializes with no active device."""
        coordinator = MultiDeviceCoordinator()
        assert coordinator.active_device is None

    def test_init_creates_empty_shared_state(self) -> None:
        """Test coordinator initializes with empty shared state."""
        coordinator = MultiDeviceCoordinator()
        assert coordinator.shared_state == {}
        assert isinstance(coordinator.shared_state, dict)

    def test_init_creates_handoff_queue(self) -> None:
        """Test coordinator initializes handoff queue."""
        coordinator = MultiDeviceCoordinator()
        assert len(coordinator.handoff_queue) == 0
        assert coordinator.handoff_queue.maxlen == 100

    def test_init_creates_stats(self) -> None:
        """Test coordinator initializes statistics."""
        coordinator = MultiDeviceCoordinator()
        assert coordinator.stats["handoffs"] == 0
        assert coordinator.stats["syncs"] == 0
        assert coordinator.stats["devices_discovered"] == 0

    def test_init_not_running(self) -> None:
        """Test coordinator initializes in stopped state."""
        coordinator = MultiDeviceCoordinator()
        assert coordinator._running is False


class TestMultiDeviceCoordinatorDeviceRegistration:
    """Test device registration."""

    def test_register_device_creates_device(self) -> None:
        """Test registering a device creates Device object."""
        coordinator = MultiDeviceCoordinator()
        device = coordinator.register_device(
            "device-1", "My Phone", DeviceType.PHONE, {"screen": "6.1inch"}
        )

        assert isinstance(device, Device)
        assert device.id == "device-1"
        assert device.name == "My Phone"
        assert device.type == DeviceType.PHONE
        assert device.capabilities["screen"] == "6.1inch"

    def test_register_device_adds_to_devices_dict(self) -> None:
        """Test registering a device adds it to devices dict."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "My Phone", DeviceType.PHONE)

        assert "device-1" in coordinator.devices
        assert coordinator.devices["device-1"].name == "My Phone"

    def test_register_device_sets_nearby_status(self) -> None:
        """Test newly registered device has NEARBY status."""
        coordinator = MultiDeviceCoordinator()
        device = coordinator.register_device("device-1", "My Phone", DeviceType.PHONE)

        assert device.status == DeviceStatus.NEARBY

    def test_register_device_increments_stats(self) -> None:
        """Test registering device increments discovery counter."""
        coordinator = MultiDeviceCoordinator()
        initial_count = coordinator.stats["devices_discovered"]

        coordinator.register_device("device-1", "My Phone", DeviceType.PHONE)

        assert coordinator.stats["devices_discovered"] == initial_count + 1

    def test_register_device_updates_existing(self) -> None:
        """Test registering existing device updates it instead of duplicating."""
        coordinator = MultiDeviceCoordinator()
        device1 = coordinator.register_device("device-1", "Old Name", DeviceType.PHONE)
        device2 = coordinator.register_device("device-1", "New Name", DeviceType.TABLET)

        assert device1 is device2  # Same object updated
        assert device2.name == "New Name"
        assert device2.type == DeviceType.TABLET
        assert len(coordinator.devices) == 1

    def test_normalize_capabilities_dict(self) -> None:
        """Test capability normalization with dict input."""
        coordinator = MultiDeviceCoordinator()
        device = coordinator.register_device(
            "device-1", "Phone", DeviceType.PHONE, {"screen": "6.1inch", "nfc": True}
        )

        assert device.capabilities["screen"] == "6.1inch"
        assert device.capabilities["nfc"] is True

    def test_normalize_capabilities_string(self) -> None:
        """Test capability normalization with string input."""
        coordinator = MultiDeviceCoordinator()
        device = coordinator.register_device("device-1", "Phone", DeviceType.PHONE, "nfc")

        assert device.capabilities["nfc"] is True

    def test_normalize_capabilities_list(self) -> None:
        """Test capability normalization with list input."""
        coordinator = MultiDeviceCoordinator()
        device = coordinator.register_device(
            "device-1", "Phone", DeviceType.PHONE, ["nfc", "bluetooth", ("wifi", "5GHz")]
        )

        assert device.capabilities["nfc"] is True
        assert device.capabilities["bluetooth"] is True
        assert device.capabilities["wifi"] == "5GHz"

    def test_normalize_capabilities_none(self) -> None:
        """Test capability normalization with None input."""
        coordinator = MultiDeviceCoordinator()
        device = coordinator.register_device("device-1", "Phone", DeviceType.PHONE, None)

        assert device.capabilities == {}


class TestMultiDeviceCoordinatorDeviceManagement:
    """Test device management operations."""

    def test_set_active_device_changes_status(self) -> None:
        """Test setting active device changes its status to ACTIVE."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)

        coordinator.set_active_device("device-1")

        assert coordinator.devices["device-1"].status == DeviceStatus.ACTIVE
        assert coordinator.active_device == "device-1"

    def test_set_active_device_deactivates_previous(self) -> None:
        """Test setting new active device deactivates previous one."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)
        coordinator.register_device("device-2", "Tablet", DeviceType.TABLET)

        coordinator.set_active_device("device-1")
        coordinator.set_active_device("device-2")

        assert coordinator.devices["device-1"].status == DeviceStatus.NEARBY
        assert coordinator.devices["device-2"].status == DeviceStatus.ACTIVE
        assert coordinator.active_device == "device-2"

    def test_set_active_device_unknown_raises_error(self) -> None:
        """Test setting unknown device as active raises ValueError."""
        coordinator = MultiDeviceCoordinator()

        with pytest.raises(ValueError, match="Unknown device"):
            coordinator.set_active_device("nonexistent")

    def test_heartbeat_updates_last_seen(self) -> None:
        """Test heartbeat updates device last_seen timestamp."""
        coordinator = MultiDeviceCoordinator()
        device = coordinator.register_device("device-1", "Phone", DeviceType.PHONE)
        original_time = device.last_seen

        time.sleep(0.01)  # Small delay to ensure time difference
        coordinator.heartbeat("device-1")

        assert coordinator.devices["device-1"].last_seen > original_time

    def test_heartbeat_updates_status(self) -> None:
        """Test heartbeat updates device status."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)

        coordinator.heartbeat("device-1", status=DeviceStatus.ACTIVE)

        assert coordinator.devices["device-1"].status == DeviceStatus.ACTIVE

    def test_heartbeat_updates_battery(self) -> None:
        """Test heartbeat updates battery level."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)

        coordinator.heartbeat("device-1", battery_level=0.75)

        assert coordinator.devices["device-1"].battery_level == 0.75

    def test_heartbeat_clamps_battery_level(self) -> None:
        """Test heartbeat clamps battery level to [0, 1]."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)

        coordinator.heartbeat("device-1", battery_level=1.5)
        assert coordinator.devices["device-1"].battery_level == 1.0

        coordinator.heartbeat("device-1", battery_level=-0.5)
        assert coordinator.devices["device-1"].battery_level == 0.0

    def test_heartbeat_updates_location(self) -> None:
        """Test heartbeat updates device location."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)

        coordinator.heartbeat("device-1", location="home")

        assert coordinator.devices["device-1"].location == "home"

    def test_heartbeat_merges_capabilities(self) -> None:
        """Test heartbeat merges new capabilities with existing ones."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE, {"nfc": True})

        coordinator.heartbeat("device-1", capabilities={"bluetooth": "5.0"})

        assert coordinator.devices["device-1"].capabilities["nfc"] is True
        assert coordinator.devices["device-1"].capabilities["bluetooth"] == "5.0"

    def test_heartbeat_unknown_device_returns_none(self) -> None:
        """Test heartbeat on unknown device returns None."""
        coordinator = MultiDeviceCoordinator()
        result = coordinator.heartbeat("nonexistent")

        assert result is None


@pytest.mark.asyncio
class TestMultiDeviceCoordinatorAsync:
    """Test async operations."""

    async def test_start_sets_running_flag(self):
        """Test start() sets the _running flag to True."""
        coordinator = MultiDeviceCoordinator()
        assert coordinator._running is False

        await coordinator.start()

        assert coordinator._running is True

    async def test_stop_clears_running_flag(self):
        """Test stop() sets the _running flag to False."""
        coordinator = MultiDeviceCoordinator()
        await coordinator.start()
        assert coordinator._running is True

        await coordinator.stop()

        assert coordinator._running is False

    async def test_start_idempotent(self):
        """Test calling start() multiple times is safe."""
        coordinator = MultiDeviceCoordinator()

        await coordinator.start()
        await coordinator.start()

        assert coordinator._running is True

    async def test_sync_state_updates_shared_state(self):
        """Test sync_state updates the shared state dict."""
        coordinator = MultiDeviceCoordinator()
        updates = {"key1": "value1", "key2": 42}

        await coordinator.sync_state(updates)

        assert coordinator.shared_state["key1"] == "value1"
        assert coordinator.shared_state["key2"] == 42

    async def test_sync_state_increments_counter(self):
        """Test sync_state increments sync counter."""
        coordinator = MultiDeviceCoordinator()
        initial_syncs = coordinator.stats["syncs"]

        await coordinator.sync_state({"key": "value"})

        assert coordinator.stats["syncs"] == initial_syncs + 1

    async def test_sync_state_merges_updates(self):
        """Test sync_state merges new updates with existing state."""
        coordinator = MultiDeviceCoordinator()
        coordinator.shared_state["existing"] = "old"

        await coordinator.sync_state({"new": "data", "existing": "updated"})

        assert coordinator.shared_state["new"] == "data"
        assert coordinator.shared_state["existing"] == "updated"


@pytest.mark.asyncio
class TestMultiDeviceCoordinatorHandoff:
    """Test device handoff operations."""

    async def test_request_handoff_validates_source_device(self):
        """Test handoff request validates source device exists."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-2", "Target", DeviceType.TABLET)

        result = await coordinator.request_handoff("nonexistent", "device-2", {})

        assert result is False

    async def test_request_handoff_validates_target_device(self):
        """Test handoff request validates target device exists."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Source", DeviceType.PHONE)

        result = await coordinator.request_handoff("device-1", "nonexistent", {})

        assert result is False

    async def test_request_handoff_creates_handoff_request(self):
        """Test handoff request creates HandoffRequest object."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)
        coordinator.register_device("device-2", "Tablet", DeviceType.TABLET)

        # Mock the transfer to avoid Socket.IO dependency
        with patch.object(coordinator, "_transfer_context", new_callable=AsyncMock):
            await coordinator.request_handoff("device-1", "device-2", {"context": "test"})

        assert len(coordinator.handoff_queue) == 1
        request = coordinator.handoff_queue[0]
        assert isinstance(request, HandoffRequest)
        assert request.from_device == "device-1"
        assert request.to_device == "device-2"

    async def test_request_handoff_increments_counter_on_success(self):
        """Test successful handoff increments handoff counter."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)
        coordinator.register_device("device-2", "Tablet", DeviceType.TABLET)
        initial_handoffs = coordinator.stats["handoffs"]

        # Mock successful transfer
        with patch.object(coordinator, "_transfer_context", new_callable=AsyncMock):
            result = await coordinator.request_handoff("device-1", "device-2", {})

        assert result is True
        assert coordinator.stats["handoffs"] == initial_handoffs + 1

    async def test_request_handoff_sets_new_active_device(self):
        """Test successful handoff sets target as active device."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)
        coordinator.register_device("device-2", "Tablet", DeviceType.TABLET)
        coordinator.set_active_device("device-1")

        # Mock successful transfer
        with patch.object(coordinator, "_transfer_context", new_callable=AsyncMock):
            await coordinator.request_handoff("device-1", "device-2", {})

        assert coordinator.active_device == "device-2"
        assert coordinator.devices["device-2"].status == DeviceStatus.ACTIVE
        assert coordinator.devices["device-1"].status == DeviceStatus.NEARBY

    async def test_request_handoff_tracks_timing_metrics(self):
        """Test handoff tracks timing metrics."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)
        coordinator.register_device("device-2", "Tablet", DeviceType.TABLET)

        # Mock successful transfer
        with patch.object(coordinator, "_transfer_context", new_callable=AsyncMock):
            await coordinator.request_handoff("device-1", "device-2", {})

        assert coordinator.stats["handoff_last_ms"] > 0
        assert len(coordinator._handoff_times) == 1

    async def test_serialize_context_handles_dict(self):
        """Test context serialization handles regular dict."""
        coordinator = MultiDeviceCoordinator()
        context = {"key": "value", "number": 42}

        serialized = await coordinator._serialize_context(context)

        assert serialized["key"] == "value"
        assert serialized["number"] == 42

    async def test_serialize_context_handles_bytes(self):
        """Test context serialization encodes bytes as base64."""
        coordinator = MultiDeviceCoordinator()
        context = {"data": b"binary data"}

        serialized = await coordinator._serialize_context(context)

        assert serialized["data"]["_type"] == "bytes"
        assert "_data" in serialized["data"]

    async def test_serialize_context_compresses_large_data(self):
        """Test context serialization compresses large payloads."""
        coordinator = MultiDeviceCoordinator()
        # Create large context (>1KB)
        large_data = "x" * 2000
        context = {"large": large_data}

        serialized = await coordinator._serialize_context(context)

        assert "_compressed" in serialized
        assert serialized["_compressed"] is True

    async def test_transfer_context_calls_direct_handler(self):
        """Test context transfer calls device's direct handler if available."""
        coordinator = MultiDeviceCoordinator()
        handler_mock = AsyncMock()
        coordinator.register_device(
            "device-1", "Phone", DeviceType.PHONE, {"handoff_handler": handler_mock}
        )

        await coordinator._transfer_context("device-1", {"test": "data"})

        handler_mock.assert_called_once()
        call_args = handler_mock.call_args[0][0]
        assert call_args["context"] == {"test": "data"}

    async def test_transfer_context_raises_on_unknown_device(self):
        """Test context transfer raises error for unknown device."""
        coordinator = MultiDeviceCoordinator()

        with pytest.raises(ValueError, match="Device not found"):
            await coordinator._transfer_context("nonexistent", {})


class TestMultiDeviceCoordinatorStats:
    """Test statistics and monitoring."""

    def test_get_stats_returns_device_count(self) -> None:
        """Test get_stats includes device count."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)
        coordinator.register_device("device-2", "Tablet", DeviceType.TABLET)

        stats = coordinator.get_stats()

        assert stats["devices"] == 2

    def test_get_stats_returns_active_device(self) -> None:
        """Test get_stats includes active device ID."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)
        coordinator.set_active_device("device-1")

        stats = coordinator.get_stats()

        assert stats["active_device"] == "device-1"

    def test_get_stats_returns_shared_state_keys(self) -> None:
        """Test get_stats includes shared state key count."""
        coordinator = MultiDeviceCoordinator()
        coordinator.shared_state = {"key1": "val1", "key2": "val2"}

        stats = coordinator.get_stats()

        assert stats["shared_state_keys"] == 2

    def test_get_stats_includes_counters(self) -> None:
        """Test get_stats includes all counter metrics."""
        coordinator = MultiDeviceCoordinator()

        stats = coordinator.get_stats()

        assert "handoffs" in stats
        assert "syncs" in stats
        assert "devices_discovered" in stats
        assert "handoff_last_ms" in stats
        assert "handoff_p95_ms" in stats


class TestMultiDeviceCoordinatorEdgeCases:
    """Test edge cases and error handling."""

    def test_handoff_queue_max_length(self) -> None:
        """Test handoff queue respects max length."""
        coordinator = MultiDeviceCoordinator()

        # Add more than maxlen items
        for i in range(150):
            request = HandoffRequest(
                from_device=f"device-{i}", to_device=f"device-{i + 1}", context={}
            )
            coordinator.handoff_queue.append(request)

        assert len(coordinator.handoff_queue) == 100

    def test_register_device_preserves_active_status(self) -> None:
        """Test re-registering active device preserves ACTIVE status."""
        coordinator = MultiDeviceCoordinator()
        coordinator.register_device("device-1", "Phone", DeviceType.PHONE)
        coordinator.set_active_device("device-1")

        coordinator.register_device("device-1", "Phone Updated", DeviceType.PHONE)

        assert coordinator.devices["device-1"].status == DeviceStatus.ACTIVE

    def test_multiple_devices_different_types(self) -> None:
        """Test coordinator handles multiple devices of different types."""
        coordinator = MultiDeviceCoordinator()

        coordinator.register_device("watch-1", "Apple Watch", DeviceType.WEARABLE)
        coordinator.register_device("phone-1", "iPhone", DeviceType.PHONE)
        coordinator.register_device("tablet-1", "iPad", DeviceType.TABLET)
        coordinator.register_device("laptop-1", "MacBook", DeviceType.LAPTOP)

        assert len(coordinator.devices) == 4
        assert coordinator.devices["watch-1"].type == DeviceType.WEARABLE
        assert coordinator.devices["phone-1"].type == DeviceType.PHONE
        assert coordinator.devices["tablet-1"].type == DeviceType.TABLET
        assert coordinator.devices["laptop-1"].type == DeviceType.LAPTOP
