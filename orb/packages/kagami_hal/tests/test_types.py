"""Tests for VM Adapter Types.

Tests cover:
- All enums (VMTier, VMState, OSType)
- All dataclasses (VMDisplayInfo, VMStatus, VMConfig, ClickOptions, TypeOptions,
  AccessibilityElement, CommandResult)
- Default values and custom values
- Field validation

Created: December 31, 2025
"""

from __future__ import annotations

from kagami_hal.adapters.vm.types import (
    AccessibilityElement,
    ClickOptions,
    CommandResult,
    OSType,
    TypeOptions,
    VMConfig,
    VMDisplayInfo,
    VMState,
    VMStatus,
    VMTier,
)

# =============================================================================
# VMTier Tests
# =============================================================================


class TestVMTier:
    """Tests for VMTier enum."""

    def test_tier_values(self):
        """Test VMTier enum values."""
        assert VMTier.HOST.value == 1
        assert VMTier.SANDBOXED.value == 2
        assert VMTier.MULTI_OS.value == 3

    def test_tier_ordering(self):
        """Test VMTier values represent increasing isolation."""
        assert VMTier.HOST.value < VMTier.SANDBOXED.value
        assert VMTier.SANDBOXED.value < VMTier.MULTI_OS.value

    def test_all_tiers_defined(self):
        """Test all expected tiers are defined."""
        tiers = list(VMTier)
        assert len(tiers) == 3
        assert VMTier.HOST in tiers
        assert VMTier.SANDBOXED in tiers
        assert VMTier.MULTI_OS in tiers


# =============================================================================
# VMState Tests
# =============================================================================


class TestVMState:
    """Tests for VMState enum."""

    def test_state_values(self):
        """Test VMState enum values."""
        assert VMState.STOPPED.value == "stopped"
        assert VMState.STARTING.value == "starting"
        assert VMState.RUNNING.value == "running"
        assert VMState.PAUSED.value == "paused"
        assert VMState.SUSPENDED.value == "suspended"
        assert VMState.STOPPING.value == "stopping"
        assert VMState.ERROR.value == "error"

    def test_all_states_defined(self):
        """Test all expected states are defined."""
        states = list(VMState)
        assert len(states) == 7

    def test_state_string_representation(self):
        """Test state value is string."""
        for state in VMState:
            assert isinstance(state.value, str)


# =============================================================================
# OSType Tests
# =============================================================================


class TestOSType:
    """Tests for OSType enum."""

    def test_os_type_values(self):
        """Test OSType enum values."""
        assert OSType.MACOS.value == "macos"
        assert OSType.WINDOWS.value == "windows"
        assert OSType.LINUX.value == "linux"
        assert OSType.UNKNOWN.value == "unknown"

    def test_all_os_types_defined(self):
        """Test all expected OS types are defined."""
        os_types = list(OSType)
        assert len(os_types) == 4

    def test_os_type_string_representation(self):
        """Test OS type value is string."""
        for os_type in OSType:
            assert isinstance(os_type.value, str)


# =============================================================================
# VMDisplayInfo Tests
# =============================================================================


class TestVMDisplayInfo:
    """Tests for VMDisplayInfo dataclass."""

    def test_default_values(self):
        """Test VMDisplayInfo default values."""
        info = VMDisplayInfo(width=1920, height=1080)

        assert info.width == 1920
        assert info.height == 1080
        assert info.scale_factor == 1.0
        assert info.color_depth == 32
        assert info.refresh_rate == 60

    def test_custom_values(self):
        """Test VMDisplayInfo with custom values."""
        info = VMDisplayInfo(
            width=2560,
            height=1440,
            scale_factor=2.0,
            color_depth=24,
            refresh_rate=144,
        )

        assert info.width == 2560
        assert info.height == 1440
        assert info.scale_factor == 2.0
        assert info.color_depth == 24
        assert info.refresh_rate == 144

    def test_retina_display(self):
        """Test typical Retina display configuration."""
        info = VMDisplayInfo(
            width=2560,
            height=1600,
            scale_factor=2.0,
        )

        assert info.width == 2560
        assert info.height == 1600
        assert info.scale_factor == 2.0


# =============================================================================
# VMStatus Tests
# =============================================================================


class TestVMStatus:
    """Tests for VMStatus dataclass."""

    def test_minimal_status(self):
        """Test VMStatus with minimal required fields."""
        status = VMStatus(
            name="test-vm",
            state=VMState.RUNNING,
            os_type=OSType.MACOS,
            tier=VMTier.SANDBOXED,
        )

        assert status.name == "test-vm"
        assert status.state == VMState.RUNNING
        assert status.os_type == OSType.MACOS
        assert status.tier == VMTier.SANDBOXED

    def test_default_values(self):
        """Test VMStatus default values."""
        status = VMStatus(
            name="test-vm",
            state=VMState.STOPPED,
            os_type=OSType.WINDOWS,
            tier=VMTier.MULTI_OS,
        )

        assert status.display is None
        assert status.cpu_count == 0
        assert status.memory_mb == 0
        assert status.uptime_seconds == 0.0
        assert status.snapshots == []
        assert status.error_message is None

    def test_full_status(self):
        """Test VMStatus with all fields."""
        display = VMDisplayInfo(width=1920, height=1080)
        status = VMStatus(
            name="full-vm",
            state=VMState.RUNNING,
            os_type=OSType.LINUX,
            tier=VMTier.MULTI_OS,
            display=display,
            cpu_count=8,
            memory_mb=16384,
            uptime_seconds=3600.0,
            snapshots=["snap1", "snap2"],
            error_message=None,
        )

        assert status.display == display
        assert status.cpu_count == 8
        assert status.memory_mb == 16384
        assert status.uptime_seconds == 3600.0
        assert status.snapshots == ["snap1", "snap2"]

    def test_error_status(self):
        """Test VMStatus with error state."""
        status = VMStatus(
            name="error-vm",
            state=VMState.ERROR,
            os_type=OSType.MACOS,
            tier=VMTier.SANDBOXED,
            error_message="Failed to start VM",
        )

        assert status.state == VMState.ERROR
        assert status.error_message == "Failed to start VM"


# =============================================================================
# VMConfig Tests
# =============================================================================


class TestVMConfig:
    """Tests for VMConfig dataclass."""

    def test_minimal_config(self):
        """Test VMConfig with minimal required fields."""
        config = VMConfig(name="test-vm")

        assert config.name == "test-vm"

    def test_default_values(self):
        """Test VMConfig default values."""
        config = VMConfig(name="test-vm")

        assert config.os_type == OSType.MACOS
        assert config.tier == VMTier.SANDBOXED
        assert config.memory_mb == 8192
        assert config.cpu_count == 4
        assert config.display_width == 1920
        assert config.display_height == 1080
        assert config.base_snapshot == "clean-state"
        assert config.auto_restore_on_release is True

    def test_custom_config(self):
        """Test VMConfig with custom values."""
        config = VMConfig(
            name="custom-vm",
            os_type=OSType.WINDOWS,
            tier=VMTier.MULTI_OS,
            memory_mb=32768,
            cpu_count=16,
            display_width=2560,
            display_height=1440,
            base_snapshot="fresh-install",
            auto_restore_on_release=False,
        )

        assert config.name == "custom-vm"
        assert config.os_type == OSType.WINDOWS
        assert config.tier == VMTier.MULTI_OS
        assert config.memory_mb == 32768
        assert config.cpu_count == 16
        assert config.display_width == 2560
        assert config.display_height == 1440
        assert config.base_snapshot == "fresh-install"
        assert config.auto_restore_on_release is False


# =============================================================================
# ClickOptions Tests
# =============================================================================


class TestClickOptions:
    """Tests for ClickOptions dataclass."""

    def test_default_values(self):
        """Test ClickOptions default values."""
        options = ClickOptions()

        assert options.button == "left"
        assert options.modifiers == []
        assert options.double_click is False

    def test_right_click(self):
        """Test right-click options."""
        options = ClickOptions(button="right")

        assert options.button == "right"

    def test_middle_click(self):
        """Test middle-click options."""
        options = ClickOptions(button="middle")

        assert options.button == "middle"

    def test_double_click(self):
        """Test double-click options."""
        options = ClickOptions(double_click=True)

        assert options.double_click is True

    def test_with_modifiers(self):
        """Test click with modifiers."""
        options = ClickOptions(modifiers=["cmd", "shift"])

        assert options.modifiers == ["cmd", "shift"]

    def test_complex_click(self):
        """Test complex click with all options."""
        options = ClickOptions(
            button="right",
            modifiers=["ctrl", "alt"],
            double_click=True,
        )

        assert options.button == "right"
        assert options.modifiers == ["ctrl", "alt"]
        assert options.double_click is True


# =============================================================================
# TypeOptions Tests
# =============================================================================


class TestTypeOptions:
    """Tests for TypeOptions dataclass."""

    def test_default_values(self):
        """Test TypeOptions default values."""
        options = TypeOptions()

        assert options.delay_ms == 0
        assert options.clear_first is False

    def test_with_delay(self):
        """Test typing with delay."""
        options = TypeOptions(delay_ms=50)

        assert options.delay_ms == 50

    def test_clear_first(self):
        """Test clear field before typing."""
        options = TypeOptions(clear_first=True)

        assert options.clear_first is True

    def test_all_options(self):
        """Test all typing options."""
        options = TypeOptions(delay_ms=100, clear_first=True)

        assert options.delay_ms == 100
        assert options.clear_first is True


# =============================================================================
# AccessibilityElement Tests
# =============================================================================


class TestAccessibilityElement:
    """Tests for AccessibilityElement dataclass."""

    def test_minimal_element(self):
        """Test AccessibilityElement with minimal required fields."""
        element = AccessibilityElement(role="button")

        assert element.role == "button"

    def test_default_values(self):
        """Test AccessibilityElement default values."""
        element = AccessibilityElement(role="textfield")

        assert element.label is None
        assert element.value is None
        assert element.identifier is None
        assert element.frame is None
        assert element.children == []
        assert element.actions == []

    def test_full_element(self):
        """Test AccessibilityElement with all fields."""
        child = AccessibilityElement(role="statictext", label="Child Label")

        element = AccessibilityElement(
            role="button",
            label="Submit",
            value="pressed",
            identifier="submit-button",
            frame=(100, 200, 80, 30),
            children=[child],
            actions=["press", "cancel"],
        )

        assert element.role == "button"
        assert element.label == "Submit"
        assert element.value == "pressed"
        assert element.identifier == "submit-button"
        assert element.frame == (100, 200, 80, 30)
        assert len(element.children) == 1
        assert element.children[0].role == "statictext"
        assert element.actions == ["press", "cancel"]

    def test_frame_tuple_format(self):
        """Test frame is (x, y, width, height) tuple."""
        element = AccessibilityElement(
            role="window",
            frame=(0, 0, 800, 600),
        )

        x, y, width, height = element.frame
        assert x == 0
        assert y == 0
        assert width == 800
        assert height == 600

    def test_nested_elements(self):
        """Test deeply nested accessibility elements."""
        leaf = AccessibilityElement(role="statictext", label="Leaf")
        branch = AccessibilityElement(role="group", children=[leaf])
        root = AccessibilityElement(role="window", children=[branch])

        assert root.children[0].children[0].label == "Leaf"


# =============================================================================
# CommandResult Tests
# =============================================================================


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_minimal_result(self):
        """Test CommandResult with minimal required fields."""
        result = CommandResult(
            exit_code=0,
            stdout="output",
            stderr="",
        )

        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.stderr == ""

    def test_default_duration(self):
        """Test CommandResult default duration."""
        result = CommandResult(
            exit_code=0,
            stdout="",
            stderr="",
        )

        assert result.duration_ms == 0.0

    def test_with_duration(self):
        """Test CommandResult with duration."""
        result = CommandResult(
            exit_code=0,
            stdout="output",
            stderr="",
            duration_ms=1234.5,
        )

        assert result.duration_ms == 1234.5

    def test_error_result(self):
        """Test CommandResult for failed command."""
        result = CommandResult(
            exit_code=1,
            stdout="",
            stderr="Command not found",
            duration_ms=50.0,
        )

        assert result.exit_code == 1
        assert result.stderr == "Command not found"

    def test_multiline_output(self):
        """Test CommandResult with multiline output."""
        result = CommandResult(
            exit_code=0,
            stdout="line1\nline2\nline3",
            stderr="warning1\nwarning2",
        )

        assert "line2" in result.stdout
        assert result.stdout.count("\n") == 2


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Tests for module __all__ exports."""

    def test_all_types_exported(self):
        """Test all types are exported."""
        from kagami_hal.adapters.vm import types

        expected_exports = [
            "AccessibilityElement",
            "ClickOptions",
            "CommandResult",
            "OSType",
            "TypeOptions",
            "VMConfig",
            "VMDisplayInfo",
            "VMState",
            "VMStatus",
            "VMTier",
        ]

        for export in expected_exports:
            assert hasattr(types, export), f"Missing export: {export}"

    def test_all_list_matches_exports(self):
        """Test __all__ matches actual exports."""
        from kagami_hal.adapters.vm.types import __all__

        assert "AccessibilityElement" in __all__
        assert "ClickOptions" in __all__
        assert "CommandResult" in __all__
        assert "OSType" in __all__
        assert "TypeOptions" in __all__
        assert "VMConfig" in __all__
        assert "VMDisplayInfo" in __all__
        assert "VMState" in __all__
        assert "VMStatus" in __all__
        assert "VMTier" in __all__
