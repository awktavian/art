"""Integration tests for HAL Syscalls.

Verifies that:
1. Syscalls are registered correctly.
2. Syscalls route to the correct HAL method.
3. Results are returned correctly.
4. Errors are handled gracefully.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

pytestmark = pytest.mark.tier_integration
import os
from kagami.core.kernel.syscalls import (
    syscall_handler,
    KagamiOSSyscall,
    _register_core_syscalls,
)
from kagami_hal.manager import get_hal_manager, shutdown_hal_manager
class TestSyscallIntegration:
    @pytest_asyncio.fixture(autouse=True)
    async def setup_hal(self):
        # Force mock mode for integration tests
        os.environ["KAGAMI_HAL_MOCK_MODE"] = "1"
        # Reset HAL manager
        await shutdown_hal_manager()
        hal = await get_hal_manager()
        # Register syscalls
        _register_core_syscalls()
        yield
        # Cleanup
        await shutdown_hal_manager()
        if "KAGAMI_HAL_MOCK_MODE" in os.environ:
            del os.environ["KAGAMI_HAL_MOCK_MODE"]
    @pytest.mark.asyncio
    async def test_display_syscalls(self):
        """Test display syscalls."""
        # SYS_DISPLAY_GET_INFO
        result = await syscall_handler(KagamiOSSyscall.SYS_DISPLAY_GET_INFO)
        assert result.success
        assert result.data is not None
        # Check for dict or object access
        width = result.data.get("width") if isinstance(result.data, dict) else result.data.width
        assert width > 0  # type: ignore[operator]
        # SYS_DISPLAY_WRITE
        buffer = b"\x00" * 100
        result = await syscall_handler(KagamiOSSyscall.SYS_DISPLAY_WRITE, buffer=buffer)
        assert result.success
        # SYS_DISPLAY_SET_BRIGHTNESS
        result = await syscall_handler(KagamiOSSyscall.SYS_DISPLAY_SET_BRIGHTNESS, level=0.5)
        assert result.success
    @pytest.mark.asyncio
    async def test_audio_syscalls(self):
        """Test audio syscalls."""
        # SYS_AUDIO_SET_VOLUME
        result = await syscall_handler(KagamiOSSyscall.SYS_AUDIO_SET_VOLUME, level=0.8)
        assert result.success
        # SYS_AUDIO_PLAY
        result = await syscall_handler(KagamiOSSyscall.SYS_AUDIO_PLAY, buffer=b"\x00" * 100)
        assert result.success
    @pytest.mark.asyncio
    async def test_power_syscalls(self):
        """Test power syscalls."""
        # SYS_POWER_GET_BATTERY
        result = await syscall_handler(KagamiOSSyscall.SYS_POWER_GET_BATTERY)
        assert result.success
        assert result.data is not None
        # SYS_POWER_SET_MODE
        from kagami_hal.power_controller import PowerMode
        result = await syscall_handler(KagamiOSSyscall.SYS_POWER_SET_MODE, mode=PowerMode.SAVER)
        assert result.success
    @pytest.mark.asyncio
    async def test_sensor_syscalls(self):
        """Test sensor syscalls."""
        # SYS_SENSOR_LIST
        result = await syscall_handler(KagamiOSSyscall.SYS_SENSOR_LIST)
        assert result.success
        assert isinstance(result.data, list)
        # SYS_SENSOR_READ (might fail if sensor not available, but mock has them)
        # We assume mock adapter has sensors
        result = await syscall_handler(KagamiOSSyscall.SYS_SENSOR_READ, sensor_type="temperature")
        if not result.success:
            # Should succeed in mock mode
            pytest.fail(f"Sensor read failed in mock mode: {result.error}")
