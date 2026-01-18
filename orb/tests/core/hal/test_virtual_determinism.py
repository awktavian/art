"""Test Virtual HAL Determinism.

Verify that deterministic mode produces identical outputs with same seed.

Created: December 15, 2025
"""

from __future__ import annotations

import os
from collections.abc import Generator

import numpy as np
import pytest

pytestmark = pytest.mark.tier_integration

from kagami_hal.adapters.virtual.config import reset_virtual_config
from kagami_hal.adapters.virtual.sensors import VirtualSensors
from kagami_hal.adapters.virtual.mock_camera import VirtualCamera
from kagami_hal.adapters.virtual.mock_microphone import VirtualMicrophone
from kagami_hal.adapters.virtual.power import VirtualPower
from kagami_hal.adapters.virtual.audio import VirtualAudio
from kagami_hal.adapters.virtual.input import VirtualInput
from kagami_hal.data_types import SensorType, AudioConfig, AudioFormat, InputType


@pytest.fixture(autouse=True)
def setup_deterministic_env() -> Generator[None, None, None]:
    """Set up deterministic environment variables."""
    os.environ["KAGAMI_VIRTUAL_DETERMINISTIC"] = "1"
    os.environ["KAGAMI_VIRTUAL_SEED"] = "42"
    os.environ["KAGAMI_VIRTUAL_RECORD_MODE"] = "0"
    reset_virtual_config()
    yield
    reset_virtual_config()


@pytest.mark.asyncio
async def test_sensor_determinism():
    """Test that sensors produce identical readings with same seed."""
    # Run 1
    reset_virtual_config()
    sensors1 = VirtualSensors()
    await sensors1.initialize()

    readings1 = []
    for _ in range(10):
        reading = await sensors1.read(SensorType.ACCELEROMETER)
        readings1.append((reading.value.x, reading.value.y, reading.value.z, reading.timestamp_ms))

    # Run 2 (reset config to same seed)
    reset_virtual_config()
    sensors2 = VirtualSensors()
    await sensors2.initialize()

    readings2 = []
    for _ in range(10):
        reading = await sensors2.read(SensorType.ACCELEROMETER)
        readings2.append((reading.value.x, reading.value.y, reading.value.z, reading.timestamp_ms))

    # Verify identical
    assert readings1 == readings2, "Sensor readings should be identical with same seed"


@pytest.mark.asyncio
async def test_camera_determinism():
    """Test that camera produces identical frames with same seed."""
    # Run 1
    reset_virtual_config()
    camera1 = VirtualCamera()
    await camera1.initialize()

    frames1 = []
    for _ in range(5):
        reading = await camera1.read(SensorType.ACCELEROMETER)
        frames1.append(reading.value)

    # Run 2
    reset_virtual_config()
    camera2 = VirtualCamera()
    await camera2.initialize()

    frames2 = []
    for _ in range(5):
        reading = await camera2.read(SensorType.ACCELEROMETER)
        frames2.append(reading.value)

    # Verify identical
    for f1, f2 in zip(frames1, frames2, strict=False):
        assert np.array_equal(f1, f2), "Camera frames should be identical with same seed"


def test_microphone_determinism():
    """Test that microphone produces identical audio with same seed."""
    # Run 1
    reset_virtual_config()
    mic1 = VirtualMicrophone()
    audio1 = mic1.record(100, pattern="noise")

    # Run 2
    reset_virtual_config()
    mic2 = VirtualMicrophone()
    audio2 = mic2.record(100, pattern="noise")

    # Verify identical
    assert audio1 == audio2, "Microphone audio should be identical with same seed"


@pytest.mark.asyncio
async def test_power_determinism():
    """Test that power adapter produces identical stats with same seed."""
    # Run 1
    reset_virtual_config()
    power1 = VirtualPower()
    await power1.initialize()

    stats1 = []
    for _ in range(5):
        battery = await power1.get_battery_status()
        power_stats = await power1.get_power_stats()
        stats1.append((battery.level, battery.voltage, power_stats.current_watts))

    # Run 2
    reset_virtual_config()
    power2 = VirtualPower()
    await power2.initialize()

    stats2 = []
    for _ in range(5):
        battery = await power2.get_battery_status()
        power_stats = await power2.get_power_stats()
        stats2.append((battery.level, battery.voltage, power_stats.current_watts))

    # Verify identical
    assert stats1 == stats2, "Power stats should be identical with same seed"


@pytest.mark.asyncio
async def test_audio_determinism():
    """Test that audio adapter produces identical recordings with same seed."""
    # Run 1
    reset_virtual_config()
    os.environ["KAGAMI_VIRTUAL_MIC_PATTERN"] = "noise"
    audio1 = VirtualAudio()
    await audio1.initialize(
        AudioConfig(sample_rate=44100, channels=2, format=AudioFormat.PCM_16, buffer_size=1024)
    )

    recording1 = await audio1.record(100)

    # Run 2
    reset_virtual_config()
    os.environ["KAGAMI_VIRTUAL_MIC_PATTERN"] = "noise"
    audio2 = VirtualAudio()
    await audio2.initialize(
        AudioConfig(sample_rate=44100, channels=2, format=AudioFormat.PCM_16, buffer_size=1024)
    )

    recording2 = await audio2.record(100)

    # Verify identical
    assert recording1 == recording2, "Audio recordings should be identical with same seed"


@pytest.mark.asyncio
async def test_input_determinism():
    """Test that input adapter produces identical events with same seed."""
    # Run 1
    reset_virtual_config()
    input1 = VirtualInput()
    await input1.initialize()
    await input1.inject_event(InputType.BUTTON, 1, 1)
    event1 = await input1.read_event()

    # Run 2
    reset_virtual_config()
    input2 = VirtualInput()
    await input2.initialize()
    await input2.inject_event(InputType.BUTTON, 1, 1)
    event2 = await input2.read_event()

    # Verify identical
    assert event1 is not None and event2 is not None
    assert (
        event1.timestamp_ms == event2.timestamp_ms
    ), "Input events should have identical timestamps with same seed"


@pytest.mark.asyncio
async def test_time_monotonic():
    """Test that virtual time is monotonically increasing."""
    reset_virtual_config()
    sensors = VirtualSensors()
    await sensors.initialize()

    timestamps = []
    for _ in range(20):
        reading = await sensors.read(SensorType.TEMPERATURE)
        timestamps.append(reading.timestamp_ms)

    # Verify monotonic
    for i in range(1, len(timestamps)):
        assert timestamps[i] > timestamps[i - 1], "Timestamps should be monotonically increasing"


def test_different_seeds_produce_different_output():
    """Test that different seeds produce different outputs."""
    # Run with seed 42
    os.environ["KAGAMI_VIRTUAL_SEED"] = "42"
    reset_virtual_config()
    mic1 = VirtualMicrophone()
    audio1 = mic1.record(100, pattern="noise")

    # Run with seed 123
    os.environ["KAGAMI_VIRTUAL_SEED"] = "123"
    reset_virtual_config()
    mic2 = VirtualMicrophone()
    audio2 = mic2.record(100, pattern="noise")

    # Verify different
    assert audio1 != audio2, "Different seeds should produce different outputs"
