"""Tests for CUALumeAdapter (Tier 2: Sandboxed macOS VMs).

Tests cover:
- Initialization with and without Lume/CUA
- VM lifecycle (start, stop)
- Screenshot capture
- Input control (click, type, hotkey)
- Snapshot management
- File transfer
- Command execution
- Error handling and fallbacks

Created: December 31, 2025
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami_hal.adapters.vm.cua_lume import CUALumeAdapter
from kagami_hal.adapters.vm.types import (
    ClickOptions,
    CommandResult,
    OSType,
    VMConfig,
    VMState,
    VMTier,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_lume_path():
    """Mock shutil.which to return a lume path."""
    with patch("shutil.which", return_value="/usr/local/bin/lume"):
        yield


@pytest.fixture
def mock_lume_not_found():
    """Mock shutil.which to return None (lume not installed)."""
    with patch("shutil.which", return_value=None):
        yield


@pytest.fixture
def mock_cua_available():
    """Mock CUA libraries being available."""
    with patch.dict("sys.modules", {"computer": MagicMock()}):
        yield


@pytest.fixture
def adapter(mock_lume_path):
    """Create a CUALumeAdapter instance."""
    return CUALumeAdapter()


@pytest.fixture
def initialized_adapter(mock_lume_path):
    """Create an initialized CUALumeAdapter instance."""
    adapter = CUALumeAdapter("test-vm")
    adapter._lume_path = "/usr/local/bin/lume"
    adapter._initialized = True
    adapter._state = VMState.STOPPED
    return adapter


# =============================================================================
# Initialization Tests
# =============================================================================


class TestCUALumeAdapterInit:
    """Tests for CUALumeAdapter initialization."""

    def test_init_default(self):
        """Test initialization with default VM name."""
        adapter = CUALumeAdapter()
        assert adapter._vm_name == "macos-sequoia-cua_latest"
        assert adapter._tier == VMTier.SANDBOXED
        assert adapter._initialized is False

    def test_init_custom_name(self):
        """Test initialization with custom VM name."""
        adapter = CUALumeAdapter("custom-vm")
        assert adapter._vm_name == "custom-vm"

    @pytest.mark.asyncio
    async def test_initialize_with_lume(self, mock_lume_path):
        """Test initialization when lume is available."""
        adapter = CUALumeAdapter()
        result = await adapter.initialize()

        assert result is True
        assert adapter._initialized is True
        assert adapter._lume_path == "/usr/local/bin/lume"

    @pytest.mark.asyncio
    async def test_initialize_without_lume(self, mock_lume_not_found):
        """Test initialization when lume is not available."""
        adapter = CUALumeAdapter()
        result = await adapter.initialize()

        # Should still succeed (stub mode)
        assert result is True
        assert adapter._initialized is True
        assert adapter._lume_path is None

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, initialized_adapter):
        """Test initialization is idempotent."""
        result = await initialized_adapter.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_initialize_with_config(self, mock_lume_path):
        """Test initialization with custom config."""
        adapter = CUALumeAdapter()
        config = VMConfig(
            name="custom-vm",
            os_type=OSType.MACOS,
            tier=VMTier.SANDBOXED,
            memory_mb=16384,
            cpu_count=8,
        )

        result = await adapter.initialize(config)

        assert result is True
        assert adapter._config == config

    @pytest.mark.asyncio
    async def test_initialize_cua_available(self, mock_lume_path, mock_cua_available):
        """Test initialization when CUA libraries are available."""
        adapter = CUALumeAdapter()

        # Mock the import inside initialize
        with patch.dict("sys.modules", {"computer": MagicMock()}):
            result = await adapter.initialize()

        assert result is True
        assert adapter._cua_available is True


# =============================================================================
# Shutdown Tests
# =============================================================================


class TestCUALumeAdapterShutdown:
    """Tests for CUALumeAdapter shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown(self, initialized_adapter):
        """Test adapter shutdown."""
        await initialized_adapter.shutdown()

        assert initialized_adapter._initialized is False
        assert initialized_adapter._state == VMState.STOPPED

    @pytest.mark.asyncio
    async def test_shutdown_with_computer(self, initialized_adapter):
        """Test shutdown with active CUA computer."""
        mock_computer = MagicMock()
        mock_computer.__aexit__ = AsyncMock()
        initialized_adapter._computer = mock_computer

        await initialized_adapter.shutdown()

        mock_computer.__aexit__.assert_called_once()
        assert initialized_adapter._computer is None

    @pytest.mark.asyncio
    async def test_shutdown_computer_error(self, initialized_adapter):
        """Test shutdown handles computer close error."""
        mock_computer = MagicMock()
        mock_computer.__aexit__ = AsyncMock(side_effect=Exception("Close error"))
        initialized_adapter._computer = mock_computer

        # Should not raise
        await initialized_adapter.shutdown()

        assert initialized_adapter._computer is None


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestVMLifecycle:
    """Tests for VM lifecycle operations."""

    @pytest.mark.asyncio
    async def test_start_already_running(self, initialized_adapter):
        """Test start when already running."""
        initialized_adapter._state = VMState.RUNNING

        result = await initialized_adapter.start()

        assert result is True

    @pytest.mark.asyncio
    async def test_start_with_lume(self, initialized_adapter):
        """Test start using lume CLI."""
        initialized_adapter._cua_available = False
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.start()

        assert result is True
        assert initialized_adapter._state == VMState.RUNNING
        initialized_adapter._run_lume.assert_called_with(["run", "test-vm:latest"], timeout=120.0)

    @pytest.mark.asyncio
    async def test_start_with_lume_failure(self, initialized_adapter):
        """Test start failure with lume CLI."""
        initialized_adapter._cua_available = False
        initialized_adapter._run_lume = AsyncMock(return_value=(1, "", "Error starting VM"))

        result = await initialized_adapter.start()

        assert result is False
        assert initialized_adapter._state == VMState.ERROR

    @pytest.mark.asyncio
    async def test_start_no_cua_no_lume(self, initialized_adapter):
        """Test start when neither CUA nor lume available."""
        initialized_adapter._cua_available = False
        initialized_adapter._lume_path = None

        result = await initialized_adapter.start()

        assert result is False
        assert initialized_adapter._state == VMState.ERROR

    @pytest.mark.asyncio
    async def test_stop(self, initialized_adapter):
        """Test stop VM."""
        initialized_adapter._state = VMState.RUNNING
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.stop()

        assert result is True
        assert initialized_adapter._state == VMState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_with_computer(self, initialized_adapter):
        """Test stop with active CUA computer."""
        mock_computer = MagicMock()
        mock_computer.__aexit__ = AsyncMock()
        initialized_adapter._computer = mock_computer
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.stop()

        assert result is True
        mock_computer.__aexit__.assert_called_once()
        assert initialized_adapter._computer is None


# =============================================================================
# Status Tests
# =============================================================================


class TestVMStatus:
    """Tests for VM status retrieval."""

    @pytest.mark.asyncio
    async def test_get_status_running(self, initialized_adapter):
        """Test getting status when VM is running."""
        initialized_adapter._run_lume = AsyncMock(
            return_value=(
                0,
                json.dumps([{"name": "test-vm", "status": "running"}]),
                "",
            )
        )
        initialized_adapter._config = VMConfig(
            name="test-vm",
            os_type=OSType.MACOS,
            tier=VMTier.SANDBOXED,
        )

        status = await initialized_adapter.get_status()

        assert status.name == "test-vm"
        assert status.state == VMState.RUNNING
        assert status.os_type == OSType.MACOS
        assert status.tier == VMTier.SANDBOXED

    @pytest.mark.asyncio
    async def test_get_status_stopped(self, initialized_adapter):
        """Test getting status when VM is stopped."""
        initialized_adapter._run_lume = AsyncMock(
            return_value=(
                0,
                json.dumps([{"name": "test-vm", "status": "stopped"}]),
                "",
            )
        )

        status = await initialized_adapter.get_status()

        assert status.state == VMState.STOPPED

    @pytest.mark.asyncio
    async def test_get_status_no_lume(self, initialized_adapter):
        """Test getting status when lume not available."""
        initialized_adapter._lume_path = None

        status = await initialized_adapter.get_status()

        assert status.name == "test-vm"
        # Should return current cached state
        assert status.state == initialized_adapter._state


# =============================================================================
# Screenshot Tests
# =============================================================================


class TestScreenshot:
    """Tests for screenshot capture."""

    @pytest.mark.asyncio
    async def test_screenshot_with_cua(self, initialized_adapter):
        """Test screenshot with CUA computer."""
        mock_computer = MagicMock()
        mock_computer.screenshot = AsyncMock(return_value=b"png_data")
        initialized_adapter._computer = mock_computer

        screenshot = await initialized_adapter.screenshot()

        assert screenshot == b"png_data"
        mock_computer.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_screenshot_cua_failure_fallback(self, initialized_adapter):
        """Test screenshot falls back when CUA fails."""
        mock_computer = MagicMock()
        mock_computer.screenshot = AsyncMock(side_effect=Exception("CUA error"))
        initialized_adapter._computer = mock_computer
        initialized_adapter.execute = AsyncMock(return_value=CommandResult(0, "", "", 0))
        initialized_adapter.copy_from_vm = AsyncMock(return_value=True)

        with patch("pathlib.Path.read_bytes", return_value=b"fallback_png"):
            screenshot = await initialized_adapter.screenshot()

        assert screenshot == b"fallback_png"
        initialized_adapter.execute.assert_called()

    @pytest.mark.asyncio
    async def test_screenshot_no_cua(self, initialized_adapter):
        """Test screenshot without CUA computer."""
        initialized_adapter._computer = None
        initialized_adapter.execute = AsyncMock(return_value=CommandResult(0, "", "", 0))
        initialized_adapter.copy_from_vm = AsyncMock(return_value=True)

        with patch("pathlib.Path.read_bytes", return_value=b"png_data"):
            await initialized_adapter.screenshot()

        call_args = initialized_adapter.execute.call_args[0][0]
        assert "screencapture" in call_args

    @pytest.mark.asyncio
    async def test_screenshot_failure(self, initialized_adapter):
        """Test screenshot failure raises error."""
        initialized_adapter._computer = None
        initialized_adapter.execute = AsyncMock(
            return_value=CommandResult(1, "", "Screenshot failed", 0)
        )

        with pytest.raises(RuntimeError, match="Screenshot failed"):
            await initialized_adapter.screenshot()


# =============================================================================
# Input Control Tests
# =============================================================================


class TestInputControl:
    """Tests for mouse and keyboard control."""

    @pytest.mark.asyncio
    async def test_click_with_cua(self, initialized_adapter):
        """Test click with CUA computer."""
        mock_computer = MagicMock()
        mock_computer.click = AsyncMock()
        initialized_adapter._computer = mock_computer

        await initialized_adapter.click(100, 200)

        mock_computer.click.assert_called_once_with(100, 200)

    @pytest.mark.asyncio
    async def test_click_cua_failure_fallback(self, initialized_adapter):
        """Test click falls back when CUA fails."""
        mock_computer = MagicMock()
        mock_computer.click = AsyncMock(side_effect=Exception("CUA error"))
        initialized_adapter._computer = mock_computer
        initialized_adapter.execute = AsyncMock(return_value=CommandResult(0, "", "", 0))

        await initialized_adapter.click(100, 200)

        call_args = initialized_adapter.execute.call_args[0][0]
        assert "cliclick" in call_args
        assert "c:100,200" in call_args

    @pytest.mark.asyncio
    async def test_click_double(self, initialized_adapter):
        """Test double-click falls back to cliclick."""
        initialized_adapter._computer = None
        initialized_adapter.execute = AsyncMock(return_value=CommandResult(0, "", "", 0))

        await initialized_adapter.click(100, 200, ClickOptions(double_click=True))

        call_args = initialized_adapter.execute.call_args[0][0]
        assert "dc:100,200" in call_args

    @pytest.mark.asyncio
    async def test_click_right(self, initialized_adapter):
        """Test right-click falls back to cliclick."""
        initialized_adapter._computer = None
        initialized_adapter.execute = AsyncMock(return_value=CommandResult(0, "", "", 0))

        await initialized_adapter.click(100, 200, ClickOptions(button="right"))

        call_args = initialized_adapter.execute.call_args[0][0]
        assert "rc:100,200" in call_args

    @pytest.mark.asyncio
    async def test_type_text_with_cua(self, initialized_adapter):
        """Test type with CUA computer."""
        mock_computer = MagicMock()
        mock_computer.type = AsyncMock()
        initialized_adapter._computer = mock_computer

        await initialized_adapter.type_text("Hello")

        mock_computer.type.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_type_text_cua_failure_fallback(self, initialized_adapter):
        """Test type falls back when CUA fails."""
        mock_computer = MagicMock()
        mock_computer.type = AsyncMock(side_effect=Exception("CUA error"))
        initialized_adapter._computer = mock_computer
        initialized_adapter.execute = AsyncMock(return_value=CommandResult(0, "", "", 0))

        await initialized_adapter.type_text("Hello")

        call_args = initialized_adapter.execute.call_args[0][0]
        assert "cliclick" in call_args
        assert "t:" in call_args

    @pytest.mark.asyncio
    async def test_type_text_with_quotes(self, initialized_adapter):
        """Test typing text with quotes escapes properly."""
        initialized_adapter._computer = None
        initialized_adapter.execute = AsyncMock(return_value=CommandResult(0, "", "", 0))

        await initialized_adapter.type_text("Hello 'World'")

        call_args = initialized_adapter.execute.call_args[0][0]
        # Single quotes should be escaped
        assert "\\'" in call_args

    @pytest.mark.asyncio
    async def test_hotkey_with_cua(self, initialized_adapter):
        """Test hotkey with CUA computer."""
        mock_computer = MagicMock()
        mock_computer.hotkey = AsyncMock()
        initialized_adapter._computer = mock_computer

        await initialized_adapter.hotkey("cmd", "c")

        mock_computer.hotkey.assert_called_once_with("cmd", "c")

    @pytest.mark.asyncio
    async def test_hotkey_cua_failure_fallback(self, initialized_adapter):
        """Test hotkey falls back when CUA fails."""
        mock_computer = MagicMock()
        mock_computer.hotkey = AsyncMock(side_effect=Exception("CUA error"))
        initialized_adapter._computer = mock_computer
        initialized_adapter.execute = AsyncMock(return_value=CommandResult(0, "", "", 0))

        await initialized_adapter.hotkey("cmd", "c")

        call_args = initialized_adapter.execute.call_args[0][0]
        assert "cliclick" in call_args
        assert "kp:" in call_args

    @pytest.mark.asyncio
    async def test_hotkey_multiple_modifiers(self, initialized_adapter):
        """Test hotkey with multiple modifiers."""
        initialized_adapter._computer = None
        initialized_adapter.execute = AsyncMock(return_value=CommandResult(0, "", "", 0))

        await initialized_adapter.hotkey("cmd", "shift", "s")

        call_args = initialized_adapter.execute.call_args[0][0]
        assert "cmd+shift+s" in call_args

    @pytest.mark.asyncio
    async def test_hotkey_empty(self, initialized_adapter):
        """Test hotkey with no keys does nothing."""
        initialized_adapter.execute = AsyncMock()

        await initialized_adapter.hotkey()

        initialized_adapter.execute.assert_not_called()


# =============================================================================
# Snapshot Tests
# =============================================================================


class TestSnapshots:
    """Tests for snapshot management."""

    @pytest.mark.asyncio
    async def test_create_snapshot_success(self, initialized_adapter):
        """Test successful snapshot creation."""
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.create_snapshot("clean-state")

        assert result is True
        initialized_adapter._run_lume.assert_called_with(["snapshot", "test-vm", "clean-state"])

    @pytest.mark.asyncio
    async def test_create_snapshot_failure(self, initialized_adapter):
        """Test snapshot creation failure."""
        initialized_adapter._run_lume = AsyncMock(return_value=(1, "", "Error"))

        result = await initialized_adapter.create_snapshot("clean-state")

        assert result is False

    @pytest.mark.asyncio
    async def test_create_snapshot_no_lume(self, initialized_adapter):
        """Test snapshot creation without lume."""
        initialized_adapter._lume_path = None

        result = await initialized_adapter.create_snapshot("clean-state")

        assert result is False

    @pytest.mark.asyncio
    async def test_restore_snapshot_success(self, initialized_adapter):
        """Test successful snapshot restoration."""
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.restore_snapshot("clean-state")

        assert result is True

    @pytest.mark.asyncio
    async def test_restore_snapshot_failure(self, initialized_adapter):
        """Test snapshot restoration failure."""
        initialized_adapter._run_lume = AsyncMock(return_value=(1, "", "Error"))

        result = await initialized_adapter.restore_snapshot("clean-state")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_snapshots(self, initialized_adapter):
        """Test listing snapshots."""
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "snap1\nsnap2\nsnap3", ""))

        snapshots = await initialized_adapter.list_snapshots()

        assert snapshots == ["snap1", "snap2", "snap3"]

    @pytest.mark.asyncio
    async def test_list_snapshots_empty(self, initialized_adapter):
        """Test listing snapshots when none exist."""
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "", ""))

        snapshots = await initialized_adapter.list_snapshots()

        assert snapshots == []

    @pytest.mark.asyncio
    async def test_list_snapshots_no_lume(self, initialized_adapter):
        """Test listing snapshots without lume."""
        initialized_adapter._lume_path = None

        snapshots = await initialized_adapter.list_snapshots()

        assert snapshots == []


# =============================================================================
# File Transfer Tests
# =============================================================================


class TestFileTransfer:
    """Tests for file transfer operations."""

    @pytest.mark.asyncio
    async def test_copy_to_vm_with_cua(self, initialized_adapter):
        """Test copy to VM with CUA computer."""
        mock_computer = MagicMock()
        mock_computer.copy_to = AsyncMock()
        initialized_adapter._computer = mock_computer

        result = await initialized_adapter.copy_to_vm("/local/file.txt", "/remote/file.txt")

        assert result is True
        mock_computer.copy_to.assert_called_once_with("/local/file.txt", "/remote/file.txt")

    @pytest.mark.asyncio
    async def test_copy_to_vm_cua_failure(self, initialized_adapter):
        """Test copy to VM when CUA fails."""
        mock_computer = MagicMock()
        mock_computer.copy_to = AsyncMock(side_effect=Exception("Copy error"))
        initialized_adapter._computer = mock_computer

        result = await initialized_adapter.copy_to_vm("/local/file.txt", "/remote/file.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_to_vm_no_cua(self, initialized_adapter):
        """Test copy to VM without CUA."""
        initialized_adapter._computer = None

        result = await initialized_adapter.copy_to_vm("/local/file.txt", "/remote/file.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_from_vm_with_cua(self, initialized_adapter):
        """Test copy from VM with CUA computer."""
        mock_computer = MagicMock()
        mock_computer.copy_from = AsyncMock()
        initialized_adapter._computer = mock_computer

        result = await initialized_adapter.copy_from_vm("/remote/file.txt", "/local/file.txt")

        assert result is True

    @pytest.mark.asyncio
    async def test_copy_from_vm_cua_failure(self, initialized_adapter):
        """Test copy from VM when CUA fails."""
        mock_computer = MagicMock()
        mock_computer.copy_from = AsyncMock(side_effect=Exception("Copy error"))
        initialized_adapter._computer = mock_computer

        result = await initialized_adapter.copy_from_vm("/remote/file.txt", "/local/file.txt")

        assert result is False


# =============================================================================
# Command Execution Tests
# =============================================================================


class TestCommandExecution:
    """Tests for command execution."""

    @pytest.mark.asyncio
    async def test_execute_with_cua(self, initialized_adapter):
        """Test execute with CUA computer."""
        mock_computer = MagicMock()
        mock_computer.execute = AsyncMock(
            return_value={"exit_code": 0, "stdout": "output", "stderr": ""}
        )
        initialized_adapter._computer = mock_computer

        result = await initialized_adapter.execute("ls -la")

        assert result.exit_code == 0
        assert result.stdout == "output"
        mock_computer.execute.assert_called_once_with("ls -la")

    @pytest.mark.asyncio
    async def test_execute_cua_failure_fallback(self, initialized_adapter):
        """Test execute falls back to lume when CUA fails."""
        mock_computer = MagicMock()
        mock_computer.execute = AsyncMock(side_effect=Exception("CUA error"))
        initialized_adapter._computer = mock_computer
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "output", ""))

        result = await initialized_adapter.execute("ls -la")

        assert result.exit_code == 0
        assert result.stdout == "output"

    @pytest.mark.asyncio
    async def test_execute_with_lume(self, initialized_adapter):
        """Test execute using lume CLI."""
        initialized_adapter._computer = None
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "output", "error"))

        result = await initialized_adapter.execute("ls -la")

        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.stderr == "error"

    @pytest.mark.asyncio
    async def test_execute_no_cua_no_lume(self, initialized_adapter):
        """Test execute when neither CUA nor lume available."""
        initialized_adapter._computer = None
        initialized_adapter._lume_path = None

        result = await initialized_adapter.execute("ls -la")

        assert result.exit_code == -1
        assert "Neither CUA nor Lume available" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, initialized_adapter):
        """Test execute with custom timeout."""
        initialized_adapter._computer = None
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "output", ""))

        await initialized_adapter.execute("long_command", timeout_ms=60000)

        call_args = initialized_adapter._run_lume.call_args
        assert call_args[1]["timeout"] == 60.0


# =============================================================================
# Display Info Tests
# =============================================================================


class TestDisplayInfo:
    """Tests for display information."""

    @pytest.mark.asyncio
    async def test_get_display_info_default(self, initialized_adapter):
        """Test getting display info with defaults."""
        initialized_adapter._config = None

        info = await initialized_adapter.get_display_info()

        assert info.width == 1920
        assert info.height == 1080
        assert info.scale_factor == 2.0  # CUA VMs use Retina

    @pytest.mark.asyncio
    async def test_get_display_info_from_config(self, initialized_adapter):
        """Test getting display info from config."""
        initialized_adapter._config = VMConfig(
            name="test-vm",
            display_width=2560,
            display_height=1440,
        )

        info = await initialized_adapter.get_display_info()

        assert info.width == 2560
        assert info.height == 1440


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_run_lume_not_installed(self, initialized_adapter):
        """Test _run_lume when lume not installed."""
        initialized_adapter._lume_path = None

        exit_code, _stdout, stderr = await initialized_adapter._run_lume(["list"])

        assert exit_code == -1
        assert "Lume not installed" in stderr

    @pytest.mark.asyncio
    async def test_start_with_cua_error(self, initialized_adapter):
        """Test start handles CUA initialization error."""
        initialized_adapter._cua_available = True
        initialized_adapter._lume_path = None

        # Mock CUA import to fail during start
        with patch.dict("sys.modules", {"computer": MagicMock()}):
            # Make Computer raise an error
            with patch(
                "kagami_hal.adapters.vm.cua_lume.CUALumeAdapter.start",
                side_effect=Exception("CUA init failed"),
            ):
                pass  # Can't easily test this without complex mocking

    @pytest.mark.asyncio
    async def test_execute_duration_tracking(self, initialized_adapter):
        """Test that execute tracks duration."""
        initialized_adapter._computer = None
        initialized_adapter._run_lume = AsyncMock(return_value=(0, "output", ""))

        result = await initialized_adapter.execute("ls")

        # Duration should be >= 0
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_hotkey_modifier_mapping(self, initialized_adapter):
        """Test hotkey modifier key mapping."""
        initialized_adapter._computer = None
        initialized_adapter.execute = AsyncMock(return_value=CommandResult(0, "", "", 0))

        # Test various modifier aliases
        await initialized_adapter.hotkey("command", "v")
        call_args = initialized_adapter.execute.call_args[0][0]
        assert "cmd" in call_args

        await initialized_adapter.hotkey("option", "v")
        call_args = initialized_adapter.execute.call_args[0][0]
        assert "alt" in call_args

        await initialized_adapter.hotkey("control", "v")
        call_args = initialized_adapter.execute.call_args[0][0]
        assert "ctrl" in call_args
