"""Comprehensive tests for virtual HAL adapters.

CREATED: December 15, 2025
AUTHOR: Forge (e₂)

Virtual adapters are always available and provide deterministic testing.
This test suite achieves high coverage by exercising all adapter functionality.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from kagami_hal.adapters.virtual.audio import VirtualAudio
from kagami_hal.adapters.virtual.display import VirtualDisplay
from kagami_hal.adapters.virtual.input import VirtualInput
from kagami_hal.adapters.virtual.mock_camera import VirtualCamera
from kagami_hal.adapters.virtual.mock_microphone import VirtualMicrophone
from kagami_hal.adapters.virtual.power import VirtualPower
from kagami_hal.adapters.virtual.sensors import VirtualSensors
from kagami_hal.data_types import AudioConfig, AudioFormat, DisplayMode


class TestVirtualDisplay:
    """Test virtual display adapter coverage."""

    @pytest.mark.asyncio
    async def test_display_initialization(self) -> None:
        """Test display initialization."""
        adapter = VirtualDisplay()
        success = await adapter.initialize()
        assert success is True

        # Get info
        info = await adapter.get_info()
        assert info.width == 1920
        assert info.height == 1080

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_display_write_frame(self) -> None:
        """Test display frame writing."""
        adapter = VirtualDisplay()
        await adapter.initialize()

        # Write frame
        buffer = bytes(1920 * 1080 * 4)  # RGBA
        await adapter.write_frame(buffer)

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_display_brightness(self) -> None:
        """Test display brightness control."""
        adapter = VirtualDisplay()
        await adapter.initialize()

        await adapter.set_brightness(0.5)
        brightness = await adapter.get_brightness()
        assert 0.4 <= brightness <= 0.6

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_display_modes(self) -> None:
        """Test display mode transitions."""
        adapter = VirtualDisplay()
        await adapter.initialize()

        # Test all modes
        await adapter.set_mode(DisplayMode.FULL)
        await adapter.set_mode(DisplayMode.LOW_POWER)
        await adapter.set_mode(DisplayMode.OFF)
        await adapter.set_mode(DisplayMode.ALWAYS_ON)

        await adapter.shutdown()


class TestVirtualAudio:
    """Test virtual audio adapter coverage."""

    @pytest.mark.asyncio
    async def test_audio_initialization(self) -> None:
        """Test audio initialization."""
        adapter = VirtualAudio()
        config = AudioConfig(
            sample_rate=48000,
            channels=2,
            format=AudioFormat.PCM_16,
            buffer_size=1024,
        )
        success = await adapter.initialize(config)
        assert success is True

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_audio_playback(self) -> None:
        """Test audio playback."""
        adapter = VirtualAudio()
        config = AudioConfig(48000, 2, AudioFormat.PCM_16, 1024)
        await adapter.initialize(config)

        # Play audio
        buffer = bytes(4096)
        await adapter.play(buffer)

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_audio_recording(self) -> None:
        """Test audio recording."""
        adapter = VirtualAudio()
        config = AudioConfig(48000, 2, AudioFormat.PCM_16, 1024)
        await adapter.initialize(config)

        # Record audio
        buffer = await adapter.record(1000)  # 1 second
        assert len(buffer) > 0

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_audio_volume(self) -> None:
        """Test audio volume control."""
        adapter = VirtualAudio()
        config = AudioConfig(48000, 2, AudioFormat.PCM_16, 1024)
        await adapter.initialize(config)

        await adapter.set_volume(0.7)
        volume = await adapter.get_volume()
        assert 0.6 <= volume <= 0.8

        await adapter.shutdown()


class TestVirtualInput:
    """Test virtual input adapter coverage."""

    @pytest.mark.asyncio
    async def test_input_initialization(self) -> None:
        """Test input initialization."""
        adapter = VirtualInput()
        success = await adapter.initialize()
        assert success is True

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_input_event_reading(self) -> None:
        """Test input event reading."""
        adapter = VirtualInput()
        await adapter.initialize()

        # Read events (should return empty list in virtual mode)
        events = await adapter.read_events()
        assert isinstance(events, list)

        await adapter.shutdown()


class TestVirtualSensors:
    """Test virtual sensor adapter coverage."""

    @pytest.mark.asyncio
    async def test_sensor_initialization(self) -> None:
        """Test sensor initialization."""
        adapter = VirtualSensors()
        success = await adapter.initialize()
        assert success is True

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_sensor_data_reading(self) -> None:
        """Test sensor data reading."""
        adapter = VirtualSensors()
        await adapter.initialize()

        # Read all sensor types
        accel = await adapter.read_accelerometer()
        assert len(accel) == 3  # type: ignore[arg-type]

        gyro = await adapter.read_gyroscope()
        assert len(gyro) == 3  # type: ignore[arg-type]

        mag = await adapter.read_magnetometer()
        assert len(mag) == 3

        temp = await adapter.read_temperature()
        assert isinstance(temp, float)

        pressure = await adapter.read_pressure()
        assert isinstance(pressure, float)

        await adapter.shutdown()


class TestVirtualPower:
    """Test virtual power adapter coverage."""

    @pytest.mark.asyncio
    async def test_power_initialization(self) -> None:
        """Test power initialization."""
        adapter = VirtualPower()
        success = await adapter.initialize()
        assert success is True

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_power_battery_status(self) -> None:
        """Test battery status reading."""
        adapter = VirtualPower()
        await adapter.initialize()

        level = await adapter.get_battery_level()
        assert 0.0 <= level <= 1.0

        charging = await adapter.is_charging()
        assert isinstance(charging, bool)

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_power_sleep(self) -> None:
        """Test sleep functionality."""
        adapter = VirtualPower()
        await adapter.initialize()

        # Sleep should complete without error
        await adapter.sleep()

        await adapter.shutdown()


# Note: VirtualCompute not present in adapters/virtual/compute.py
# Only ComputeCapabilities dataclass exists, so skipping those tests


class TestVirtualCamera:
    """Test virtual camera coverage."""

    @pytest.mark.asyncio
    async def test_camera_initialization(self) -> None:
        """Test camera initialization."""
        camera = VirtualCamera(width=640, height=480)
        success = await camera.initialize()
        assert success is True

        await camera.shutdown()

    @pytest.mark.asyncio
    async def test_camera_capture(self) -> None:
        """Test camera frame capture."""
        camera = VirtualCamera(width=640, height=480)
        await camera.initialize()

        frame = await camera.read_frame()
        assert frame.shape == (480, 640, 3)

        await camera.shutdown()


class TestVirtualMicrophone:
    """Test virtual microphone coverage."""

    @pytest.mark.asyncio
    async def test_microphone_initialization(self) -> None:
        """Test microphone initialization."""
        mic = VirtualMicrophone(sample_rate=48000, channels=2)
        success = await mic.initialize()
        assert success is True

        await mic.shutdown()

    @pytest.mark.asyncio
    async def test_microphone_recording(self) -> None:
        """Test microphone recording."""
        mic = VirtualMicrophone(sample_rate=48000, channels=2)
        await mic.initialize()

        buffer = await mic.record(1000)  # 1 second
        assert len(buffer) > 0

        await mic.shutdown()
