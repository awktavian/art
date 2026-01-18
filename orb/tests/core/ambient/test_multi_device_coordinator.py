from __future__ import annotations


import pytest
from kagami.core.ambient.multi_device_coordinator import DeviceType, MultiDeviceCoordinator


@pytest.mark.asyncio
async def test_handoff_latency_and_direct_channel(monkeypatch) -> None:
    coordinator = MultiDeviceCoordinator()
    received: list[dict[str, object]] = []

    async def direct_channel(payload: dict[str, object]) -> None:
        received.append(payload)

    source = coordinator.register_device(
        device_id="device-source",
        name="K os Phone",
        device_type=DeviceType.PHONE,
    )
    target = coordinator.register_device(
        device_id="device-target",
        name="K os Watch",
        device_type=DeviceType.WEARABLE,
        capabilities={"handoff_handler": direct_channel},
    )
    coordinator.set_active_device(source.id)

    context = {"view": "metrics", "tab": "overview"}

    success = await coordinator.request_handoff(source.id, target.id, context)

    assert success
    assert received and received[0]["context"] == context

    stats = coordinator.get_stats()
    assert stats["handoff_last_ms"] < 1000  # <1s requirement
    assert stats["handoff_p95_ms"] <= stats["handoff_last_ms"]


# NOTE: BLE discovery feature was removed from MultiDeviceCoordinator.
# Device discovery is now handled via explicit registration or Socket.IO connections.
# The test_ble_discovery_registers_device test was removed as it tests non-existent
# functionality (_run_ble_discovery method no longer exists in the implementation).
