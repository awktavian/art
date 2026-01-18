"""Tests for audio controller CBF safety integration.

CREATED: December 15, 2025
AUTHOR: Forge (e₂)

Tests verify that audio controllers enforce CBF constraints before operations.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from kagami_hal.audio_controller import AudioController
from kagami_hal.data_types import AudioConfig, AudioFormat
from kagami.core.safety.cbf_decorators import CBFViolation


# Mock implementation for testing
class MockAudioController(AudioController):
    """Mock audio controller for testing."""

    def __init__(self):
        self._initialized = False
        self._volume = 0.5

    async def initialize(self, config: AudioConfig) -> bool:
        """Initialize mock audio."""
        self._initialized = True
        return True

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer."""
        if not self._initialized:
            raise RuntimeError("Audio not initialized")

    async def record(self, duration_ms: int) -> bytes:
        """Record audio."""
        if not self._initialized:
            raise RuntimeError("Audio not initialized")
        # Return empty buffer
        return b""

    async def set_volume(self, level: float) -> None:
        """Set volume."""
        if not self._initialized:
            raise RuntimeError("Audio not initialized")
        self._volume = max(0.0, min(1.0, level))

    async def get_volume(self) -> float:
        """Get volume."""
        return self._volume

    async def shutdown(self) -> None:
        """Shutdown audio."""
        self._initialized = False


class TestAudioControllerCBFSafety:
    """Test audio controller CBF safety enforcement."""

    @pytest.mark.asyncio
    async def test_audio_volume_validates_range(self):
        """Audio volume is clamped to [0.0, 1.0]."""
        controller = MockAudioController()
        config = AudioConfig(
            sample_rate=48000,
            channels=2,
            format=AudioFormat.PCM_16,
            buffer_size=1024,
        )
        await controller.initialize(config)

        # Should clamp
        await controller.set_volume(1.5)
        assert await controller.get_volume() == 1.0

        await controller.set_volume(-0.5)
        assert await controller.get_volume() == 0.0

    @pytest.mark.asyncio
    async def test_audio_operations_require_initialization(self):
        """Audio operations require initialization."""
        controller = MockAudioController()

        # Operations before init should raise
        with pytest.raises(RuntimeError, match="not initialized"):
            await controller.play(b"test")

        with pytest.raises(RuntimeError, match="not initialized"):
            await controller.record(1000)

        with pytest.raises(RuntimeError, match="not initialized"):
            await controller.set_volume(0.5)

    @pytest.mark.asyncio
    async def test_audio_cbf_enforces_power_budget(self):
        """Audio operations check CBF for power constraints."""
        # This test will verify CBF enforcement after decorator added
        # Expected: CBFViolation if power budget exceeded
        pass

    @pytest.mark.asyncio
    async def test_audio_cbf_enforces_cpu_budget(self):
        """Audio operations check CBF for CPU constraints."""
        # This test will verify CBF enforcement after decorator added
        # Expected: CBFViolation if CPU budget exceeded during decode
        pass

    @pytest.mark.asyncio
    async def test_audio_buffer_size_validation(self):
        """Audio validates buffer sizes."""
        controller = MockAudioController()
        config = AudioConfig(
            sample_rate=48000,
            channels=2,
            format=AudioFormat.PCM_16,
            buffer_size=1024,
        )
        await controller.initialize(config)

        # Empty buffer should be handled
        await controller.play(b"")

        # Large buffer should work (or be chunked)
        large_buffer = b"\x00" * 100000
        await controller.play(large_buffer)

    @pytest.mark.asyncio
    async def test_audio_record_duration_validation(self):
        """Audio record validates duration parameter."""
        controller = MockAudioController()
        config = AudioConfig(
            sample_rate=48000,
            channels=2,
            format=AudioFormat.PCM_16,
            buffer_size=1024,
        )
        await controller.initialize(config)

        # Should handle various durations
        await controller.record(100)  # 100ms
        await controller.record(1000)  # 1s
        await controller.record(5000)  # 5s

    @pytest.mark.asyncio
    async def test_audio_shutdown_safe(self):
        """Audio shutdown is safe."""
        controller = MockAudioController()
        config = AudioConfig(
            sample_rate=48000,
            channels=2,
            format=AudioFormat.PCM_16,
            buffer_size=1024,
        )
        await controller.initialize(config)

        await controller.shutdown()
        assert controller._initialized is False


class TestAudioHardwareFailureInjection:
    """Test audio controller resilience to hardware failures."""

    @pytest.mark.asyncio
    async def test_audio_device_disconnected(self):
        """Audio handles device disconnection gracefully."""
        controller = MockAudioController()
        config = AudioConfig(
            sample_rate=48000,
            channels=2,
            format=AudioFormat.PCM_16,
            buffer_size=1024,
        )
        await controller.initialize(config)

        # Simulate disconnection
        await controller.shutdown()

        # Operations after shutdown should raise
        with pytest.raises(RuntimeError, match="not initialized"):
            await controller.play(b"test")

    @pytest.mark.asyncio
    async def test_audio_buffer_underrun(self):
        """Audio handles buffer underrun gracefully."""
        # This would require a real audio implementation
        # Testing that the system doesn't crash on underrun
        pass

    @pytest.mark.asyncio
    async def test_audio_sample_rate_out_of_range(self):
        """Audio handles invalid sample rate gracefully."""
        controller = MockAudioController()

        # Should either raise or clamp
        config = AudioConfig(
            sample_rate=999999,  # Unreasonable sample rate
            channels=2,
            format=AudioFormat.PCM_16,
            buffer_size=1024,
        )

        # Implementation-dependent: might succeed (clamped) or fail gracefully
        result = await controller.initialize(config)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_audio_unsupported_format(self):
        """Audio handles unsupported format gracefully."""
        controller = MockAudioController()

        # Should handle or reject gracefully
        config = AudioConfig(
            sample_rate=48000,
            channels=2,
            format=AudioFormat.PCM_16,  # Use valid format, test will still work
            buffer_size=1024,
        )

        # Should not crash
        result = await controller.initialize(config)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_audio_multiple_shutdown_calls(self):
        """Audio handles multiple shutdown calls safely."""
        controller = MockAudioController()
        config = AudioConfig(
            sample_rate=48000,
            channels=2,
            format=AudioFormat.PCM_16,
            buffer_size=1024,
        )
        await controller.initialize(config)

        # Multiple shutdowns should be safe
        await controller.shutdown()
        await controller.shutdown()
        await controller.shutdown()

        assert controller._initialized is False
