"""Tests for BaseVMAdapter (Abstract Base Class).

Tests cover:
- Properties (tier, is_initialized, state)
- Default implementations
- Abstract method requirements
- Tier-specific behavior (HOST vs VM tiers)

Created: December 31, 2025
"""

from __future__ import annotations

from abc import ABC
from unittest.mock import AsyncMock

import pytest
from kagami_hal.adapters.vm.base import BaseVMAdapter
from kagami_hal.adapters.vm.types import (
    AccessibilityElement,
    ClickOptions,
    CommandResult,
    OSType,
    TypeOptions,
    VMConfig,
    VMState,
    VMTier,
)

# =============================================================================
# Concrete Implementation for Testing
# =============================================================================


class ConcreteVMAdapter(BaseVMAdapter):
    """Concrete implementation of BaseVMAdapter for testing."""

    def __init__(self, tier: VMTier = VMTier.SANDBOXED):
        super().__init__(tier)
        self._screenshot_data = b"test_screenshot"
        self._click_calls = []
        self._type_calls = []
        self._hotkey_calls = []

    async def initialize(self, config: VMConfig | None = None) -> bool:
        self._config = config or VMConfig(name="test-vm", tier=self._tier)
        self._initialized = True
        return True

    async def shutdown(self) -> None:
        self._initialized = False
        self._state = VMState.STOPPED

    async def screenshot(self, retina: bool = True) -> bytes:
        return self._screenshot_data

    async def click(
        self,
        x: int,
        y: int,
        options: ClickOptions | None = None,
    ) -> None:
        self._click_calls.append((x, y, options))

    async def type_text(
        self,
        text: str,
        options: TypeOptions | None = None,
    ) -> None:
        self._type_calls.append((text, options))

    async def hotkey(self, *keys: str) -> None:
        self._hotkey_calls.append(keys)


class HostVMAdapter(ConcreteVMAdapter):
    """Host tier adapter for testing."""

    def __init__(self):
        super().__init__(tier=VMTier.HOST)


class SandboxedVMAdapter(ConcreteVMAdapter):
    """Sandboxed tier adapter for testing."""

    def __init__(self):
        super().__init__(tier=VMTier.SANDBOXED)


class MultiOSVMAdapter(ConcreteVMAdapter):
    """Multi-OS tier adapter for testing."""

    def __init__(self):
        super().__init__(tier=VMTier.MULTI_OS)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def host_adapter():
    """Create a host tier adapter."""
    return HostVMAdapter()


@pytest.fixture
def sandboxed_adapter():
    """Create a sandboxed tier adapter."""
    return SandboxedVMAdapter()


@pytest.fixture
def multi_os_adapter():
    """Create a multi-OS tier adapter."""
    return MultiOSVMAdapter()


@pytest.fixture
def initialized_adapter():
    """Create an initialized adapter."""
    adapter = SandboxedVMAdapter()
    adapter._initialized = True
    adapter._config = VMConfig(name="test-vm", tier=VMTier.SANDBOXED)
    return adapter


# =============================================================================
# Abstract Class Tests
# =============================================================================


class TestAbstractClass:
    """Tests for abstract class requirements."""

    def test_cannot_instantiate_directly(self):
        """Test BaseVMAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseVMAdapter(VMTier.SANDBOXED)

    def test_must_implement_abstract_methods(self):
        """Test all abstract methods must be implemented."""

        # Missing all abstract methods
        class IncompleteAdapter(BaseVMAdapter):
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter(VMTier.SANDBOXED)

    def test_must_implement_initialize(self):
        """Test initialize must be implemented."""

        class MissingInitialize(BaseVMAdapter):
            async def shutdown(self):
                pass

            async def screenshot(self, retina=True):
                return b""

            async def click(self, x, y, options=None):
                pass

            async def type_text(self, text, options=None):
                pass

            async def hotkey(self, *keys):
                pass

        with pytest.raises(TypeError):
            MissingInitialize(VMTier.SANDBOXED)


# =============================================================================
# Property Tests
# =============================================================================


class TestProperties:
    """Tests for adapter properties."""

    def test_tier_property(self, sandboxed_adapter):
        """Test tier property returns correct tier."""
        assert sandboxed_adapter.tier == VMTier.SANDBOXED

    def test_tier_property_host(self, host_adapter):
        """Test tier property for host adapter."""
        assert host_adapter.tier == VMTier.HOST

    def test_tier_property_multi_os(self, multi_os_adapter):
        """Test tier property for multi-OS adapter."""
        assert multi_os_adapter.tier == VMTier.MULTI_OS

    def test_is_initialized_property_false(self, sandboxed_adapter):
        """Test is_initialized returns False initially."""
        assert sandboxed_adapter.is_initialized is False

    def test_is_initialized_property_true(self, initialized_adapter):
        """Test is_initialized returns True after initialization."""
        assert initialized_adapter.is_initialized is True

    def test_state_property_default(self, sandboxed_adapter):
        """Test state defaults to STOPPED."""
        assert sandboxed_adapter.state == VMState.STOPPED

    def test_state_property_changes(self, sandboxed_adapter):
        """Test state can be changed."""
        sandboxed_adapter._state = VMState.RUNNING
        assert sandboxed_adapter.state == VMState.RUNNING


# =============================================================================
# Default Implementation Tests
# =============================================================================


class TestDefaultImplementations:
    """Tests for default method implementations."""

    @pytest.mark.asyncio
    async def test_start_host_tier(self, host_adapter):
        """Test start for host tier sets state to RUNNING."""
        result = await host_adapter.start()

        assert result is True
        assert host_adapter.state == VMState.RUNNING

    @pytest.mark.asyncio
    async def test_start_non_host_tier(self, sandboxed_adapter):
        """Test start for non-host tier returns False."""
        result = await sandboxed_adapter.start()

        assert result is False

    @pytest.mark.asyncio
    async def test_stop_host_tier(self, host_adapter):
        """Test stop for host tier returns True."""
        result = await host_adapter.stop()

        assert result is True

    @pytest.mark.asyncio
    async def test_stop_non_host_tier(self, sandboxed_adapter):
        """Test stop for non-host tier returns False."""
        result = await sandboxed_adapter.stop()

        assert result is False

    @pytest.mark.asyncio
    async def test_restart(self, host_adapter):
        """Test restart calls stop then start."""
        result = await host_adapter.restart()

        assert result is True
        assert host_adapter.state == VMState.RUNNING

    @pytest.mark.asyncio
    async def test_get_status_minimal(self, sandboxed_adapter):
        """Test get_status returns minimal status."""
        sandboxed_adapter._state = VMState.RUNNING

        status = await sandboxed_adapter.get_status()

        assert status.name == "unknown"  # No config set
        assert status.state == VMState.RUNNING
        assert status.tier == VMTier.SANDBOXED

    @pytest.mark.asyncio
    async def test_get_status_with_config(self, initialized_adapter):
        """Test get_status uses config values."""
        initialized_adapter._state = VMState.RUNNING

        status = await initialized_adapter.get_status()

        assert status.name == "test-vm"
        assert status.os_type == OSType.MACOS

    @pytest.mark.asyncio
    async def test_get_display_info_with_config(self, initialized_adapter):
        """Test get_display_info uses config values."""
        info = await initialized_adapter.get_display_info()

        assert info.width == 1920  # Default from VMConfig
        assert info.height == 1080

    @pytest.mark.asyncio
    async def test_get_display_info_no_config(self, sandboxed_adapter):
        """Test get_display_info defaults without config."""
        info = await sandboxed_adapter.get_display_info()

        assert info.width == 1920
        assert info.height == 1080

    @pytest.mark.asyncio
    async def test_double_click(self, initialized_adapter):
        """Test double_click uses click with double_click option."""
        await initialized_adapter.double_click(100, 200)

        assert len(initialized_adapter._click_calls) == 1
        x, y, options = initialized_adapter._click_calls[0]
        assert x == 100
        assert y == 200
        assert options.double_click is True

    @pytest.mark.asyncio
    async def test_move_default(self, initialized_adapter):
        """Test move is a no-op by default."""
        # Should not raise
        await initialized_adapter.move(100, 200)

    @pytest.mark.asyncio
    async def test_scroll_default(self, initialized_adapter):
        """Test scroll logs warning by default."""
        # Should not raise
        await initialized_adapter.scroll(delta_y=10)

    @pytest.mark.asyncio
    async def test_press_with_modifiers(self, initialized_adapter):
        """Test press calls hotkey with modifiers."""
        await initialized_adapter.press("c", modifiers=["cmd"])

        assert len(initialized_adapter._hotkey_calls) == 1
        assert initialized_adapter._hotkey_calls[0] == ("cmd", "c")

    @pytest.mark.asyncio
    async def test_press_without_modifiers(self, initialized_adapter):
        """Test press calls hotkey without modifiers."""
        await initialized_adapter.press("enter")

        assert len(initialized_adapter._hotkey_calls) == 1
        assert initialized_adapter._hotkey_calls[0] == ("enter",)


# =============================================================================
# Accessibility Default Tests
# =============================================================================


class TestAccessibilityDefaults:
    """Tests for accessibility default implementations."""

    @pytest.mark.asyncio
    async def test_get_accessibility_tree_default(self, initialized_adapter):
        """Test get_accessibility_tree returns None by default."""
        tree = await initialized_adapter.get_accessibility_tree()

        assert tree is None

    @pytest.mark.asyncio
    async def test_find_element_default(self, initialized_adapter):
        """Test find_element returns None by default."""
        element = await initialized_adapter.find_element(label="Test")

        assert element is None

    @pytest.mark.asyncio
    async def test_click_element_default(self, initialized_adapter):
        """Test click_element returns False when element not found."""
        result = await initialized_adapter.click_element("Test")

        assert result is False

    @pytest.mark.asyncio
    async def test_click_element_with_found_element(self, initialized_adapter):
        """Test click_element clicks when element found."""
        # Mock find_element to return an element
        element = AccessibilityElement(
            role="button",
            label="Submit",
            frame=(100, 200, 80, 30),
        )
        initialized_adapter.find_element = AsyncMock(return_value=element)

        result = await initialized_adapter.click_element("Submit")

        assert result is True
        assert len(initialized_adapter._click_calls) == 1
        # Should click center of element
        x, y, _ = initialized_adapter._click_calls[0]
        assert x == 100 + 40  # center x
        assert y == 200 + 15  # center y


# =============================================================================
# App Control Default Tests
# =============================================================================


class TestAppControlDefaults:
    """Tests for app control default implementations."""

    @pytest.mark.asyncio
    async def test_launch_app_default(self, initialized_adapter):
        """Test launch_app returns False by default."""
        result = await initialized_adapter.launch_app("Safari")

        assert result is False

    @pytest.mark.asyncio
    async def test_quit_app_default(self, initialized_adapter):
        """Test quit_app returns False by default."""
        result = await initialized_adapter.quit_app("Safari")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_frontmost_app_default(self, initialized_adapter):
        """Test get_frontmost_app returns None by default."""
        app = await initialized_adapter.get_frontmost_app()

        assert app is None

    @pytest.mark.asyncio
    async def test_list_running_apps_default(self, initialized_adapter):
        """Test list_running_apps returns empty list by default."""
        apps = await initialized_adapter.list_running_apps()

        assert apps == []


# =============================================================================
# Clipboard Default Tests
# =============================================================================


class TestClipboardDefaults:
    """Tests for clipboard default implementations."""

    @pytest.mark.asyncio
    async def test_get_clipboard_default(self, initialized_adapter):
        """Test get_clipboard returns None by default."""
        text = await initialized_adapter.get_clipboard()

        assert text is None

    @pytest.mark.asyncio
    async def test_set_clipboard_default(self, initialized_adapter):
        """Test set_clipboard is a no-op by default."""
        # Should not raise
        await initialized_adapter.set_clipboard("test")


# =============================================================================
# Snapshot Default Tests (Tier-Specific)
# =============================================================================


class TestSnapshotDefaults:
    """Tests for snapshot default implementations."""

    @pytest.mark.asyncio
    async def test_create_snapshot_host(self, host_adapter):
        """Test create_snapshot returns False for host tier."""
        result = await host_adapter.create_snapshot("test")

        assert result is False

    @pytest.mark.asyncio
    async def test_create_snapshot_non_host(self, sandboxed_adapter):
        """Test create_snapshot returns False by default for non-host."""
        result = await sandboxed_adapter.create_snapshot("test")

        assert result is False

    @pytest.mark.asyncio
    async def test_restore_snapshot_host(self, host_adapter):
        """Test restore_snapshot returns False for host tier."""
        result = await host_adapter.restore_snapshot("test")

        assert result is False

    @pytest.mark.asyncio
    async def test_restore_snapshot_non_host(self, sandboxed_adapter):
        """Test restore_snapshot returns False by default for non-host."""
        result = await sandboxed_adapter.restore_snapshot("test")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_snapshots_default(self, initialized_adapter):
        """Test list_snapshots returns empty list by default."""
        snapshots = await initialized_adapter.list_snapshots()

        assert snapshots == []

    @pytest.mark.asyncio
    async def test_delete_snapshot_default(self, initialized_adapter):
        """Test delete_snapshot returns False by default."""
        result = await initialized_adapter.delete_snapshot("test")

        assert result is False


# =============================================================================
# File Transfer Default Tests (Tier-Specific)
# =============================================================================


class TestFileTransferDefaults:
    """Tests for file transfer default implementations."""

    @pytest.mark.asyncio
    async def test_copy_to_vm_host(self, host_adapter):
        """Test copy_to_vm returns False for host tier."""
        result = await host_adapter.copy_to_vm("/local", "/remote")

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_to_vm_non_host(self, sandboxed_adapter):
        """Test copy_to_vm returns False by default for non-host."""
        result = await sandboxed_adapter.copy_to_vm("/local", "/remote")

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_from_vm_host(self, host_adapter):
        """Test copy_from_vm returns False for host tier."""
        result = await host_adapter.copy_from_vm("/remote", "/local")

        assert result is False

    @pytest.mark.asyncio
    async def test_copy_from_vm_non_host(self, sandboxed_adapter):
        """Test copy_from_vm returns False by default for non-host."""
        result = await sandboxed_adapter.copy_from_vm("/remote", "/local")

        assert result is False


# =============================================================================
# Command Execution Default Tests (Tier-Specific)
# =============================================================================


class TestCommandExecutionDefaults:
    """Tests for command execution default implementations."""

    @pytest.mark.asyncio
    async def test_execute_host(self, host_adapter):
        """Test execute returns error for host tier."""
        result = await host_adapter.execute("ls")

        assert result.exit_code == -1
        assert "Not supported on host" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_non_host(self, sandboxed_adapter):
        """Test execute returns error by default for non-host."""
        result = await sandboxed_adapter.execute("ls")

        assert result.exit_code == -1
        assert "Not implemented" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_result_format(self, sandboxed_adapter):
        """Test execute returns CommandResult format."""
        result = await sandboxed_adapter.execute("ls")

        assert isinstance(result, CommandResult)
        assert hasattr(result, "exit_code")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Tests for module __all__ exports."""

    def test_base_adapter_exported(self):
        """Test BaseVMAdapter is exported."""
        from kagami_hal.adapters.vm.base import __all__

        assert "BaseVMAdapter" in __all__

    def test_can_import_base_adapter(self):
        """Test BaseVMAdapter can be imported."""
        from kagami_hal.adapters.vm.base import BaseVMAdapter

        assert BaseVMAdapter is not None
        assert issubclass(BaseVMAdapter, ABC)
