"""Tests for ParallelsAdapter (Tier 3: Multi-OS VMs).

Tests cover:
- Initialization and configuration
- VM lifecycle (start, stop, restart)
- Screenshot capture
- Input control (click, type, hotkey)
- Snapshot management
- Command execution
- Error handling

Created: December 31, 2025
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from kagami_hal.adapters.vm.parallels import ParallelsAdapter
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
def mock_prlctl_path():
    """Mock shutil.which to return a prlctl path."""
    with patch("shutil.which", return_value="/usr/local/bin/prlctl"):
        yield


@pytest.fixture
def mock_prlctl_not_found():
    """Mock shutil.which to return None (prlctl not installed)."""
    with patch("shutil.which", return_value=None):
        yield


@pytest.fixture
def adapter(mock_prlctl_path):
    """Create a ParallelsAdapter instance."""
    return ParallelsAdapter("test-vm")


@pytest.fixture
def initialized_adapter(mock_prlctl_path):
    """Create an initialized ParallelsAdapter instance with mocked subprocess."""

    async def mock_run_prlctl(args, timeout=60.0):
        if args == ["list", "-a", "--json"]:
            return (0, json.dumps([{"name": "test-vm"}]), "")
        elif args == ["list", "-i", "test-vm", "--json"]:
            return (
                0,
                json.dumps([{"OS": "Windows 11", "cpu": {"count": 4}, "memory": {"size": 8192}}]),
                "",
            )
        return (0, "", "")

    adapter = ParallelsAdapter("test-vm")
    adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)
    return adapter


# =============================================================================
# Initialization Tests
# =============================================================================


class TestParallelsAdapterInit:
    """Tests for ParallelsAdapter initialization."""

    def test_init_with_vm_name(self):
        """Test initialization with VM name."""
        adapter = ParallelsAdapter("my-windows-vm")
        assert adapter._vm_name == "my-windows-vm"
        assert adapter._tier == VMTier.MULTI_OS
        assert adapter._initialized is False

    def test_init_without_vm_name(self):
        """Test initialization without VM name."""
        adapter = ParallelsAdapter()
        assert adapter._vm_name is None

    @pytest.mark.asyncio
    async def test_initialize_prlctl_not_found(self, mock_prlctl_not_found):
        """Test initialization fails when prlctl not found."""
        adapter = ParallelsAdapter("test-vm")
        result = await adapter.initialize()
        assert result is False
        assert adapter._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_vm_not_found(self, mock_prlctl_path):
        """Test initialization fails when VM doesn't exist."""
        adapter = ParallelsAdapter("nonexistent-vm")

        async def mock_run_prlctl(args, timeout=60.0):
            if args == ["list", "-a", "--json"]:
                return (0, json.dumps([{"name": "other-vm"}]), "")
            return (0, "", "")

        adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)
        adapter._prlctl_path = "/usr/local/bin/prlctl"

        result = await adapter.initialize()
        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_success(self, initialized_adapter):
        """Test successful initialization."""
        result = await initialized_adapter.initialize()
        assert result is True
        assert initialized_adapter._initialized is True
        assert initialized_adapter._os_type == OSType.WINDOWS

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, initialized_adapter):
        """Test initialization is idempotent."""
        await initialized_adapter.initialize()
        result = await initialized_adapter.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_initialize_with_config(self, mock_prlctl_path):
        """Test initialization with custom config."""
        adapter = ParallelsAdapter()
        config = VMConfig(
            name="custom-vm",
            os_type=OSType.WINDOWS,
            tier=VMTier.MULTI_OS,
        )

        async def mock_run_prlctl(args, timeout=60.0):
            if args == ["list", "-a", "--json"]:
                return (0, json.dumps([{"name": "custom-vm"}]), "")
            elif "list" in args and "-i" in args:
                return (0, json.dumps([{"OS": "Windows"}]), "")
            return (0, "", "")

        adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)
        adapter._prlctl_path = "/usr/local/bin/prlctl"

        result = await adapter.initialize(config)
        assert result is True
        assert adapter._vm_name == "custom-vm"


# =============================================================================
# Shutdown Tests
# =============================================================================


class TestParallelsAdapterShutdown:
    """Tests for ParallelsAdapter shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown(self, initialized_adapter):
        """Test adapter shutdown."""
        await initialized_adapter.initialize()
        await initialized_adapter.shutdown()
        assert initialized_adapter._initialized is False


# =============================================================================
# OS Detection Tests
# =============================================================================


class TestOSDetection:
    """Tests for OS type detection."""

    @pytest.mark.asyncio
    async def test_detect_windows(self, mock_prlctl_path):
        """Test Windows detection."""
        adapter = ParallelsAdapter("win-vm")

        async def mock_run_prlctl(args, timeout=60.0):
            if args == ["list", "-a", "--json"]:
                return (0, json.dumps([{"name": "win-vm"}]), "")
            elif "list" in args and "-i" in args:
                return (0, json.dumps([{"OS": "Windows 11 Pro"}]), "")
            return (0, "", "")

        adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)
        adapter._prlctl_path = "/usr/local/bin/prlctl"

        await adapter.initialize()
        assert adapter._os_type == OSType.WINDOWS

    @pytest.mark.asyncio
    async def test_detect_macos(self, mock_prlctl_path):
        """Test macOS detection."""
        adapter = ParallelsAdapter("mac-vm")

        async def mock_run_prlctl(args, timeout=60.0):
            if args == ["list", "-a", "--json"]:
                return (0, json.dumps([{"name": "mac-vm"}]), "")
            elif "list" in args and "-i" in args:
                return (0, json.dumps([{"OS": "macOS 14 Sonoma"}]), "")
            return (0, "", "")

        adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)
        adapter._prlctl_path = "/usr/local/bin/prlctl"

        await adapter.initialize()
        assert adapter._os_type == OSType.MACOS

    @pytest.mark.asyncio
    async def test_detect_linux(self, mock_prlctl_path):
        """Test Linux detection."""
        adapter = ParallelsAdapter("linux-vm")

        async def mock_run_prlctl(args, timeout=60.0):
            if args == ["list", "-a", "--json"]:
                return (0, json.dumps([{"name": "linux-vm"}]), "")
            elif "list" in args and "-i" in args:
                return (0, json.dumps([{"OS": "Ubuntu 22.04"}]), "")
            return (0, "", "")

        adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)
        adapter._prlctl_path = "/usr/local/bin/prlctl"

        await adapter.initialize()
        assert adapter._os_type == OSType.LINUX


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestVMLifecycle:
    """Tests for VM lifecycle operations."""

    @pytest.mark.asyncio
    async def test_start_success(self, initialized_adapter):
        """Test successful VM start."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.start()
        assert result is True
        assert initialized_adapter._state == VMState.RUNNING
        initialized_adapter._run_prlctl.assert_called_with(["start", "test-vm"])

    @pytest.mark.asyncio
    async def test_start_failure(self, initialized_adapter):
        """Test VM start failure."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(1, "", "Failed to start"))

        result = await initialized_adapter.start()
        assert result is False
        assert initialized_adapter._state == VMState.ERROR

    @pytest.mark.asyncio
    async def test_stop_success(self, initialized_adapter):
        """Test successful VM stop."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.stop()
        assert result is True
        assert initialized_adapter._state == VMState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_failure(self, initialized_adapter):
        """Test VM stop failure."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(1, "", "Failed to stop"))

        result = await initialized_adapter.stop()
        assert result is False

    @pytest.mark.asyncio
    async def test_restart(self, initialized_adapter):
        """Test VM restart."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.restart()
        assert result is True
        assert initialized_adapter._state == VMState.RUNNING


# =============================================================================
# Status Tests
# =============================================================================


class TestVMStatus:
    """Tests for VM status retrieval."""

    @pytest.mark.asyncio
    async def test_get_status(self, initialized_adapter):
        """Test getting VM status."""
        await initialized_adapter.initialize()

        async def mock_run_prlctl(args, timeout=60.0):
            if args == ["list", "-o", "status", "test-vm"]:
                return (0, "running", "")
            elif "list" in args and "-i" in args:
                return (
                    0,
                    json.dumps([{"cpu": {"count": 8}, "memory": {"size": 16384}}]),
                    "",
                )
            elif args == ["snapshot-list", "test-vm", "--json"]:
                return (0, json.dumps({"snapshots": [{"name": "clean"}]}), "")
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        status = await initialized_adapter.get_status()
        assert status.name == "test-vm"
        assert status.state == VMState.RUNNING
        assert status.tier == VMTier.MULTI_OS
        assert status.cpu_count == 8
        assert status.memory_mb == 16384

    @pytest.mark.asyncio
    async def test_get_vm_state_stopped(self, initialized_adapter):
        """Test getting stopped state."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "stopped", ""))

        state = await initialized_adapter._get_vm_state()
        assert state == VMState.STOPPED

    @pytest.mark.asyncio
    async def test_get_vm_state_paused(self, initialized_adapter):
        """Test getting paused state."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "paused", ""))

        state = await initialized_adapter._get_vm_state()
        assert state == VMState.PAUSED

    @pytest.mark.asyncio
    async def test_get_vm_state_suspended(self, initialized_adapter):
        """Test getting suspended state."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "suspended", ""))

        state = await initialized_adapter._get_vm_state()
        assert state == VMState.SUSPENDED


# =============================================================================
# Screenshot Tests
# =============================================================================


class TestScreenshot:
    """Tests for screenshot capture."""

    @pytest.mark.asyncio
    async def test_screenshot_windows(self, initialized_adapter):
        """Test screenshot on Windows VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.WINDOWS

        # Track execute calls through _run_prlctl
        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])  # command is 3rd arg
                return (0, "", "")
            elif args[0] == "copy":
                return (0, "", "")
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        with patch("pathlib.Path.read_bytes", return_value=b"fake_png_data"):
            with patch("pathlib.Path.write_text"):
                await initialized_adapter.screenshot()

        assert len(execute_calls) >= 1
        # Should use PowerShell for Windows
        assert any("powershell" in call.lower() for call in execute_calls)

    @pytest.mark.asyncio
    async def test_screenshot_macos(self, initialized_adapter):
        """Test screenshot on macOS VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.MACOS

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
                return (0, "", "")
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        with patch("pathlib.Path.read_bytes", return_value=b"fake_png_data"):
            with patch("pathlib.Path.write_text"):
                await initialized_adapter.screenshot()

        assert len(execute_calls) >= 1
        assert any("screencapture" in call for call in execute_calls)

    @pytest.mark.asyncio
    async def test_screenshot_linux(self, initialized_adapter):
        """Test screenshot on Linux VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.LINUX

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
                return (0, "", "")
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        with patch("pathlib.Path.read_bytes", return_value=b"fake_png_data"):
            with patch("pathlib.Path.write_text"):
                await initialized_adapter.screenshot()

        assert len(execute_calls) >= 1
        assert any("import" in call for call in execute_calls)


# =============================================================================
# Input Control Tests
# =============================================================================


class TestInputControl:
    """Tests for mouse and keyboard control."""

    @pytest.mark.asyncio
    async def test_click_macos(self, initialized_adapter):
        """Test click on macOS VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.MACOS

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.click(100, 200)

        assert len(execute_calls) == 1
        assert "cliclick" in execute_calls[0]
        assert "c:100,200" in execute_calls[0]

    @pytest.mark.asyncio
    async def test_click_double_click_macos(self, initialized_adapter):
        """Test double-click on macOS VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.MACOS

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.click(100, 200, ClickOptions(double_click=True))

        assert len(execute_calls) == 1
        assert "dc:100,200" in execute_calls[0]

    @pytest.mark.asyncio
    async def test_click_right_click_macos(self, initialized_adapter):
        """Test right-click on macOS VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.MACOS

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.click(100, 200, ClickOptions(button="right"))

        assert len(execute_calls) == 1
        assert "rc:100,200" in execute_calls[0]

    @pytest.mark.asyncio
    async def test_click_linux(self, initialized_adapter):
        """Test click on Linux VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.LINUX

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.click(100, 200)

        assert len(execute_calls) == 1
        assert "xdotool" in execute_calls[0]
        assert "mousemove" in execute_calls[0]

    @pytest.mark.asyncio
    async def test_click_windows(self, initialized_adapter):
        """Test click on Windows VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.WINDOWS

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.click(100, 200)

        assert len(execute_calls) == 1
        assert "powershell" in execute_calls[0].lower()

    @pytest.mark.asyncio
    async def test_type_text_macos(self, initialized_adapter):
        """Test typing on macOS VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.MACOS

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.type_text("Hello World")

        assert len(execute_calls) == 1
        assert "cliclick" in execute_calls[0]
        assert "t:" in execute_calls[0]

    @pytest.mark.asyncio
    async def test_type_text_linux(self, initialized_adapter):
        """Test typing on Linux VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.LINUX

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.type_text("Hello World")

        assert len(execute_calls) == 1
        assert "xdotool" in execute_calls[0]
        assert "type" in execute_calls[0]

    @pytest.mark.asyncio
    async def test_type_text_windows(self, initialized_adapter):
        """Test typing on Windows VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.WINDOWS

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.type_text("Hello World")

        assert len(execute_calls) == 1
        assert "SendKeys" in execute_calls[0]

    @pytest.mark.asyncio
    async def test_hotkey_macos(self, initialized_adapter):
        """Test hotkey on macOS VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.MACOS

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.hotkey("cmd", "c")

        assert len(execute_calls) == 1
        assert "cliclick" in execute_calls[0]
        assert "kp:" in execute_calls[0]

    @pytest.mark.asyncio
    async def test_hotkey_linux(self, initialized_adapter):
        """Test hotkey on Linux VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.LINUX

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.hotkey("ctrl", "c")

        assert len(execute_calls) == 1
        assert "xdotool" in execute_calls[0]
        assert "key" in execute_calls[0]

    @pytest.mark.asyncio
    async def test_hotkey_empty(self, initialized_adapter):
        """Test hotkey with no keys does nothing."""
        await initialized_adapter.initialize()

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.hotkey()

        assert len(execute_calls) == 0


# =============================================================================
# Snapshot Tests
# =============================================================================


class TestSnapshots:
    """Tests for snapshot management."""

    @pytest.mark.asyncio
    async def test_create_snapshot_success(self, initialized_adapter):
        """Test successful snapshot creation."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.create_snapshot("test-snapshot")
        assert result is True
        initialized_adapter._run_prlctl.assert_called_with(
            ["snapshot", "test-vm", "-n", "test-snapshot"]
        )

    @pytest.mark.asyncio
    async def test_create_snapshot_failure(self, initialized_adapter):
        """Test snapshot creation failure."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(1, "", "Error"))

        result = await initialized_adapter.create_snapshot("test-snapshot")
        assert result is False

    @pytest.mark.asyncio
    async def test_restore_snapshot_success(self, initialized_adapter):
        """Test successful snapshot restoration."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.restore_snapshot("test-snapshot")
        assert result is True

    @pytest.mark.asyncio
    async def test_restore_snapshot_failure(self, initialized_adapter):
        """Test snapshot restoration failure."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(1, "", "Error"))

        result = await initialized_adapter.restore_snapshot("test-snapshot")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_snapshots(self, initialized_adapter):
        """Test listing snapshots."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(
            return_value=(
                0,
                json.dumps({"snapshots": [{"name": "snap1"}, {"name": "snap2"}]}),
                "",
            )
        )

        snapshots = await initialized_adapter.list_snapshots()
        assert snapshots == ["snap1", "snap2"]

    @pytest.mark.asyncio
    async def test_list_snapshots_empty(self, initialized_adapter):
        """Test listing snapshots when none exist."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(
            return_value=(0, json.dumps({"snapshots": []}), "")
        )

        snapshots = await initialized_adapter.list_snapshots()
        assert snapshots == []

    @pytest.mark.asyncio
    async def test_list_snapshots_error(self, initialized_adapter):
        """Test listing snapshots on error."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(1, "", "Error"))

        snapshots = await initialized_adapter.list_snapshots()
        assert snapshots == []

    @pytest.mark.asyncio
    async def test_delete_snapshot_success(self, initialized_adapter):
        """Test successful snapshot deletion."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.delete_snapshot("test-snapshot")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_snapshot_failure(self, initialized_adapter):
        """Test snapshot deletion failure."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(1, "", "Error"))

        result = await initialized_adapter.delete_snapshot("test-snapshot")
        assert result is False


# =============================================================================
# File Transfer Tests
# =============================================================================


class TestFileTransfer:
    """Tests for file transfer operations."""

    @pytest.mark.asyncio
    async def test_copy_to_vm_success(self, initialized_adapter):
        """Test successful file copy to VM."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "", ""))

        result = await initialized_adapter.copy_to_vm("/local/file.txt", "/remote/file.txt")
        assert result is True

    @pytest.mark.asyncio
    async def test_copy_to_vm_failure(self, initialized_adapter):
        """Test file copy to VM failure."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(1, "", "Error"))

        result = await initialized_adapter.copy_to_vm("/local/file.txt", "/remote/file.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_copy_from_vm_unix(self, initialized_adapter):
        """Test file copy from Unix VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.MACOS
        initialized_adapter.execute = AsyncMock(
            return_value=CommandResult(0, "file contents", "", 0)
        )

        with patch("pathlib.Path.write_text"):
            result = await initialized_adapter.copy_from_vm("/tmp/file.txt", "/local/file.txt")
        assert result is True
        call_args = initialized_adapter.execute.call_args[0][0]
        assert "cat" in call_args

    @pytest.mark.asyncio
    async def test_copy_from_vm_windows(self, initialized_adapter):
        """Test file copy from Windows VM."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.WINDOWS
        initialized_adapter.execute = AsyncMock(
            return_value=CommandResult(0, "file contents", "", 0)
        )

        with patch("pathlib.Path.write_text"):
            result = await initialized_adapter.copy_from_vm("C:\\file.txt", "/local/file.txt")
        assert result is True
        call_args = initialized_adapter.execute.call_args[0][0]
        assert "type" in call_args


# =============================================================================
# Command Execution Tests
# =============================================================================


class TestCommandExecution:
    """Tests for command execution."""

    @pytest.mark.asyncio
    async def test_execute_success(self, initialized_adapter):
        """Test successful command execution."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "output", ""))

        result = await initialized_adapter.execute("dir")
        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_failure(self, initialized_adapter):
        """Test command execution failure."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(1, "", "error"))

        result = await initialized_adapter.execute("invalid_command")
        assert result.exit_code == 1
        assert result.stderr == "error"

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, initialized_adapter):
        """Test command execution with custom timeout."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "output", ""))

        result = await initialized_adapter.execute("long_command", timeout_ms=60000)
        assert result.exit_code == 0
        # Verify timeout was passed (60000ms = 60s)
        call_args = initialized_adapter._run_prlctl.call_args
        assert call_args[1]["timeout"] == 60.0


# =============================================================================
# Display Info Tests
# =============================================================================


class TestDisplayInfo:
    """Tests for display information."""

    @pytest.mark.asyncio
    async def test_get_display_info_default(self, initialized_adapter):
        """Test getting display info with defaults."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, json.dumps([{}]), ""))

        info = await initialized_adapter.get_display_info()
        assert info.width == 1920
        assert info.height == 1080
        assert info.scale_factor == 1.0

    @pytest.mark.asyncio
    async def test_get_display_info_custom(self, initialized_adapter):
        """Test getting display info from VM config."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(
            return_value=(
                0,
                json.dumps([{"video": {"width": 2560, "height": 1440}}]),
                "",
            )
        )

        info = await initialized_adapter.get_display_info()
        assert info.width == 2560
        assert info.height == 1440


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_json_decode_error_vm_exists(self, mock_prlctl_path):
        """Test handling of invalid JSON in VM exists check."""
        adapter = ParallelsAdapter("test-vm")
        adapter._prlctl_path = "/usr/local/bin/prlctl"
        adapter._run_prlctl = AsyncMock(return_value=(0, "invalid json", ""))

        result = await adapter._vm_exists()
        assert result is False

    @pytest.mark.asyncio
    async def test_json_decode_error_os_detection(self, initialized_adapter):
        """Test handling of invalid JSON in OS detection."""
        await initialized_adapter.initialize()
        initialized_adapter._run_prlctl = AsyncMock(return_value=(0, "invalid json", ""))

        os_type = await initialized_adapter._detect_os_type()
        assert os_type == OSType.UNKNOWN

    @pytest.mark.asyncio
    async def test_type_text_with_quotes(self, initialized_adapter):
        """Test typing text with special characters."""
        await initialized_adapter.initialize()
        initialized_adapter._os_type = OSType.MACOS

        execute_calls = []

        async def mock_run_prlctl(args, timeout=60.0):
            if args[0] == "exec":
                execute_calls.append(args[2])
            return (0, "", "")

        initialized_adapter._run_prlctl = AsyncMock(side_effect=mock_run_prlctl)

        await initialized_adapter.type_text("Hello 'World'")

        assert len(execute_calls) == 1
        # Quotes should be escaped - the actual escaping is complex shell escaping
        # which replaces ' with '\'' pattern
        assert "cliclick" in execute_calls[0]
        assert "Hello" in execute_calls[0]
        assert "World" in execute_calls[0]
