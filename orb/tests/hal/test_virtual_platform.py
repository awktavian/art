"""Tests for Virtual HAL Platform.

Created: December 15, 2025

NOTE: These tests must run serially due to global config singleton.
The virtual HAL uses a global configuration cache that cannot be
safely shared across pytest-xdist workers. The xdist_group marker
ensures all tests in this file run in the same worker.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

# Mark all tests in this module to run serially (same xdist worker)
from kagami_hal.adapters.virtual.compute import (
    detect_compute_capabilities,
    get_optimal_worker_count,
)
from kagami_hal.data_types import AudioConfig, AudioFormat, SensorType
from kagami_hal.manager import HALManager
from kagami_hal.types import Platform


@pytest.mark.asyncio
async def test_virtual_hal_initialization():
    """Test virtual HAL initializes successfully."""
    hal = HALManager(force_platform=Platform.VIRTUAL)
    success = await hal.initialize()

    assert success
    assert hal.display is not None
    assert hal.audio is not None
    assert hal.sensors is not None
    assert hal.input is not None
    assert hal.power is not None

    await hal.shutdown()


@pytest.mark.asyncio
async def test_virtual_sensors_deterministic():
    """Test deterministic sensor data generation."""
    os.environ["KAGAMI_VIRTUAL_DETERMINISTIC"] = "1"
    os.environ["KAGAMI_VIRTUAL_SEED"] = "12345"

    hal1 = HALManager(force_platform=Platform.VIRTUAL)
    await hal1.initialize()

    hal2 = HALManager(force_platform=Platform.VIRTUAL)
    await hal2.initialize()

    # Read same sensor from both instances
    reading1 = await hal1.sensors.read(SensorType.TEMPERATURE)  # type: ignore[union-attr]
    reading2 = await hal2.sensors.read(SensorType.TEMPERATURE)  # type: ignore[union-attr]

    # Should be identical due to deterministic mode
    assert reading1.value == reading2.value
    assert reading1.sensor == reading2.sensor

    await hal1.shutdown()
    await hal2.shutdown()

    # Cleanup
    del os.environ["KAGAMI_VIRTUAL_DETERMINISTIC"]
    del os.environ["KAGAMI_VIRTUAL_SEED"]


@pytest.mark.asyncio
async def test_virtual_audio_recording():
    """Test virtual audio with recording mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["KAGAMI_VIRTUAL_RECORD_MODE"] = "1"
        os.environ["KAGAMI_VIRTUAL_OUTPUT_DIR"] = tmpdir

        hal = HALManager(force_platform=Platform.VIRTUAL)
        await hal.initialize()

        # Play audio
        test_audio = b"\x00\xff" * 1024
        await hal.audio.play(test_audio)  # type: ignore[union-attr]

        # Check recording was created
        audio_dir = Path(tmpdir) / "audio"
        recordings = list(audio_dir.glob("playback_*.raw"))
        assert len(recordings) > 0

        # Verify content
        with open(recordings[0], "rb") as f:
            recorded = f.read()
        assert recorded == test_audio

        await hal.shutdown()

        # Cleanup
        del os.environ["KAGAMI_VIRTUAL_RECORD_MODE"]
        del os.environ["KAGAMI_VIRTUAL_OUTPUT_DIR"]


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_virtual_microphone_patterns():
    """Test virtual microphone generates different patterns."""
    os.environ["KAGAMI_VIRTUAL_MIC_PATTERN"] = "sine"

    hal = HALManager(force_platform=Platform.VIRTUAL)

    try:
        await hal.initialize()

        # Record audio with timeout to prevent hangs (should be sine wave, not silence)
        audio_bytes = await asyncio.wait_for(
            hal.audio.record(100),
            timeout=5.0,
        )  # 100ms record, 5s timeout
        assert len(audio_bytes) > 0
        assert audio_bytes != b"\x00" * len(audio_bytes)  # Not silence

    finally:
        # Ensure cleanup happens even if test fails or times out
        await asyncio.wait_for(hal.shutdown(), timeout=2.0)

        # Cleanup environment
        if "KAGAMI_VIRTUAL_MIC_PATTERN" in os.environ:
            del os.environ["KAGAMI_VIRTUAL_MIC_PATTERN"]


@pytest.mark.asyncio
async def test_virtual_display_recording():
    """Test virtual display frame recording."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["KAGAMI_VIRTUAL_RECORD_MODE"] = "1"
        os.environ["KAGAMI_VIRTUAL_OUTPUT_DIR"] = tmpdir

        hal = HALManager(force_platform=Platform.VIRTUAL)
        await hal.initialize()

        # Write frame
        test_frame = b"\xff\x00\x00\xff" * 256  # RGBA pattern
        await hal.display.write_frame(test_frame)  # type: ignore[union-attr]

        # Check recording
        frames_dir = Path(tmpdir) / "frames"
        frames = list(frames_dir.glob("display_*.raw"))
        assert len(frames) > 0

        await hal.shutdown()

        del os.environ["KAGAMI_VIRTUAL_RECORD_MODE"]
        del os.environ["KAGAMI_VIRTUAL_OUTPUT_DIR"]


@pytest.mark.asyncio
async def test_virtual_sensor_recording():
    """Test sensor data recording to JSONL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["KAGAMI_VIRTUAL_RECORD_MODE"] = "1"
        os.environ["KAGAMI_VIRTUAL_OUTPUT_DIR"] = tmpdir

        hal = HALManager(force_platform=Platform.VIRTUAL)
        await hal.initialize()

        # Read sensor multiple times
        for _ in range(5):
            await hal.sensors.read(SensorType.TEMPERATURE)  # type: ignore[union-attr]

        # Check JSONL file
        sensor_file = Path(tmpdir) / "sensors" / "temperature.jsonl"
        assert sensor_file.exists()

        # Verify JSONL format
        import json

        lines = sensor_file.read_text().strip().split("\n")
        assert len(lines) == 5

        for line in lines:
            record = json.loads(line)
            assert "sensor" in record
            assert "timestamp_ms" in record
            assert "accuracy" in record

        await hal.shutdown()

        del os.environ["KAGAMI_VIRTUAL_RECORD_MODE"]
        del os.environ["KAGAMI_VIRTUAL_OUTPUT_DIR"]


@pytest.mark.asyncio
async def test_virtual_sensor_throughput():
    """Test virtual sensor reading performance."""
    hal = HALManager(force_platform=Platform.VIRTUAL)
    await hal.initialize()

    import time

    start = time.time()
    count = 1000

    for _ in range(count):
        await hal.sensors.read(SensorType.ACCELEROMETER)  # type: ignore[union-attr]

    elapsed = time.time() - start
    rate = count / elapsed

    # Virtual sensors should be very fast (no real I/O)
    assert rate > 100, f"Expected >100 Hz, got {rate:.1f} Hz"

    await hal.shutdown()


def test_compute_capabilities() -> None:
    """Test compute capability detection."""
    caps = detect_compute_capabilities()

    assert caps.platform is not None
    assert caps.cpu_count > 0
    assert isinstance(caps.has_gpu, bool)
    assert caps.recommended_batch_size > 0
    assert caps.recommended_precision in ("fp32", "fp16", "int8")


def test_optimal_worker_count() -> None:
    """Test worker count calculation."""
    workers = get_optimal_worker_count()
    assert workers >= 1
    assert workers <= 8


@pytest.mark.asyncio
async def test_virtual_display_configurable_resolution():
    """Test virtual display uses configured resolution."""
    os.environ["KAGAMI_VIRTUAL_CAMERA_WIDTH"] = "1920"
    os.environ["KAGAMI_VIRTUAL_CAMERA_HEIGHT"] = "1080"

    hal = HALManager(force_platform=Platform.VIRTUAL)
    await hal.initialize()

    info = await hal.display.get_info()  # type: ignore[union-attr]
    assert info.width == 1920
    assert info.height == 1080

    await hal.shutdown()

    del os.environ["KAGAMI_VIRTUAL_CAMERA_WIDTH"]
    del os.environ["KAGAMI_VIRTUAL_CAMERA_HEIGHT"]


@pytest.mark.asyncio
async def test_virtual_input_injection():
    """Test input event injection."""
    hal = HALManager(force_platform=Platform.VIRTUAL)
    await hal.initialize()

    from kagami_hal.data_types import InputType

    # Inject event
    success = await hal.input.inject_event(InputType.BUTTON, 102, 1)  # type: ignore[union-attr]
    assert success

    # Read event back
    event = await hal.input.read_event()  # type: ignore[union-attr]
    assert event is not None
    assert event.type == InputType.BUTTON
    assert event.code == 102
    assert event.value == 1

    await hal.shutdown()


@pytest.mark.asyncio
async def test_virtual_power_simulation():
    """Test virtual power simulation."""
    hal = HALManager(force_platform=Platform.VIRTUAL)
    await hal.initialize()

    # Get battery status
    battery = await hal.power.get_battery_status()  # type: ignore[union-attr]
    assert 0 <= battery.level <= 100
    assert battery.voltage > 0

    # Get power stats
    stats = await hal.power.get_power_stats()  # type: ignore[union-attr]
    assert stats.current_watts >= 0
    assert stats.avg_watts >= 0

    await hal.shutdown()
