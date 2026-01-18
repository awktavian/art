"""Tests for PeekabooAdapter (Tier 1: Host macOS Control).

Tests cover:
- Initialization and permissions check
- Screenshot capture (screen, app)
- Mouse control (click, drag, scroll, move)
- Keyboard control (type, hotkey, press)
- Accessibility tree inspection
- App control (launch, quit, list)
- Clipboard operations
- Error handling

Created: December 31, 2025
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter
from kagami_hal.adapters.vm.types import (
    ClickOptions,
    OSType,
    TypeOptions,
    VMConfig,
    VMState,
    VMTier,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_peekaboo_path():
    """Mock shutil.which to return a peekaboo path."""
    with patch("shutil.which", return_value="/opt/homebrew/bin/peekaboo"):
        yield


@pytest.fixture
def mock_peekaboo_not_found():
    """Mock shutil.which to return None (peekaboo not installed)."""
    with patch("shutil.which", return_value=None):
        yield


@pytest.fixture
def adapter(mock_peekaboo_path):
    """Create a PeekabooAdapter instance."""
    return PeekabooAdapter()


@pytest.fixture
def mock_process():
    """Create a mock subprocess result."""
    process = MagicMock()
    process.returncode = 0
    process.stdout_text = ""
    process.stderr_text = ""
    return process


@pytest.fixture
def initialized_adapter(mock_peekaboo_path, mock_process):
    """Create an initialized PeekabooAdapter instance."""
    adapter = PeekabooAdapter()
    mock_process.stdout_text = "Granted"
    adapter._run_peekaboo = AsyncMock(return_value=mock_process)
    return adapter


# =============================================================================
# Initialization Tests
# =============================================================================


class TestPeekabooAdapterInit:
    """Tests for PeekabooAdapter initialization."""

    def test_init(self):
        """Test basic initialization."""
        adapter = PeekabooAdapter()
        assert adapter._tier == VMTier.HOST
        assert adapter._initialized is False
        assert adapter._peekaboo_path is None

    @pytest.mark.asyncio
    async def test_initialize_success(self, initialized_adapter):
        """Test successful initialization."""
        result = await initialized_adapter.initialize()
        assert result is True
        assert initialized_adapter._initialized is True
        assert initialized_adapter._state == VMState.RUNNING

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, initialized_adapter):
        """Test initialization is idempotent."""
        await initialized_adapter.initialize()
        result = await initialized_adapter.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_initialize_peekaboo_not_found_fallback_to_npx(self, mock_peekaboo_not_found):
        """Test fallback to npx when peekaboo not found."""
        adapter = PeekabooAdapter()

        # Mock npx check to succeed
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout_text = "1.0.0"
        mock_process.stderr_text = ""

        with patch.object(adapter, "_run_command", AsyncMock(return_value=mock_process)):
            await adapter.initialize()
            # Should have attempted npx fallback
            assert adapter._peekaboo_path == "npx -y @steipete/peekaboo"

    @pytest.mark.asyncio
    async def test_initialize_peekaboo_not_found_no_fallback(self, mock_peekaboo_not_found):
        """Test initialization fails when peekaboo not found and npx fails."""
        adapter = PeekabooAdapter()

        # Mock npx check to fail
        with patch.object(
            adapter, "_run_command", AsyncMock(side_effect=Exception("npx not found"))
        ):
            result = await adapter.initialize()
            assert result is False

    @pytest.mark.asyncio
    async def test_initialize_with_config(self, mock_peekaboo_path, mock_process):
        """Test initialization with custom config."""
        adapter = PeekabooAdapter()
        mock_process.stdout_text = "Granted"
        adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        config = VMConfig(
            name="custom-host",
            os_type=OSType.MACOS,
            tier=VMTier.HOST,
        )
        result = await adapter.initialize(config)
        assert result is True
        assert adapter._config.name == "custom-host"

    @pytest.mark.asyncio
    async def test_initialize_permissions_warning(self, mock_peekaboo_path, mock_process):
        """Test initialization with permissions not granted."""
        adapter = PeekabooAdapter()
        mock_process.stdout_text = "Not Granted"
        adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        # Should still succeed but log warning
        result = await adapter.initialize()
        assert result is True


# =============================================================================
# Shutdown Tests
# =============================================================================


class TestPeekabooAdapterShutdown:
    """Tests for PeekabooAdapter shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown(self, initialized_adapter):
        """Test adapter shutdown."""
        await initialized_adapter.initialize()
        await initialized_adapter.shutdown()
        assert initialized_adapter._initialized is False
        assert initialized_adapter._state == VMState.STOPPED


# =============================================================================
# Screenshot Tests
# =============================================================================


class TestScreenshot:
    """Tests for screenshot capture."""

    @pytest.mark.asyncio
    async def test_screenshot_success(self, initialized_adapter, mock_process):
        """Test successful screenshot capture."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        with patch("pathlib.Path.read_bytes", return_value=b"fake_png_data"):
            screenshot = await initialized_adapter.screenshot()

        assert screenshot == b"fake_png_data"
        # Verify correct args
        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "image" in call_args
        assert "--mode" in call_args
        assert "screen" in call_args
        assert "--retina" in call_args

    @pytest.mark.asyncio
    async def test_screenshot_no_retina(self, initialized_adapter, mock_process):
        """Test screenshot without retina."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        with patch("pathlib.Path.read_bytes", return_value=b"fake_png_data"):
            await initialized_adapter.screenshot(retina=False)

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--retina" not in call_args

    @pytest.mark.asyncio
    async def test_screenshot_failure(self, initialized_adapter, mock_process):
        """Test screenshot capture failure."""
        await initialized_adapter.initialize()
        mock_process.returncode = 1
        mock_process.stderr_text = "Screen capture failed"
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        with pytest.raises(RuntimeError, match="Screenshot failed"):
            await initialized_adapter.screenshot()

    @pytest.mark.asyncio
    async def test_screenshot_app(self, initialized_adapter, mock_process):
        """Test app screenshot capture."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        with patch("pathlib.Path.read_bytes", return_value=b"fake_png_data"):
            await initialized_adapter.screenshot_app("Safari")

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--mode" in call_args
        assert "app" in call_args
        assert "--app" in call_args
        assert "Safari" in call_args


# =============================================================================
# Mouse Control Tests
# =============================================================================


class TestMouseControl:
    """Tests for mouse control operations."""

    @pytest.mark.asyncio
    async def test_click_basic(self, initialized_adapter, mock_process):
        """Test basic click."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.click(100, 200)

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "click" in call_args
        assert "--x" in call_args
        assert "100" in call_args
        assert "--y" in call_args
        assert "200" in call_args

    @pytest.mark.asyncio
    async def test_click_right_button(self, initialized_adapter, mock_process):
        """Test right-click."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.click(100, 200, ClickOptions(button="right"))

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--button" in call_args
        assert "right" in call_args

    @pytest.mark.asyncio
    async def test_click_middle_button(self, initialized_adapter, mock_process):
        """Test middle-click."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.click(100, 200, ClickOptions(button="middle"))

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--button" in call_args
        assert "middle" in call_args

    @pytest.mark.asyncio
    async def test_click_double(self, initialized_adapter, mock_process):
        """Test double-click."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.click(100, 200, ClickOptions(double_click=True))

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--double" in call_args

    @pytest.mark.asyncio
    async def test_click_with_modifiers(self, initialized_adapter, mock_process):
        """Test click with modifiers."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.click(100, 200, ClickOptions(modifiers=["cmd", "shift"]))

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--modifiers" in call_args
        assert "cmd,shift" in call_args

    @pytest.mark.asyncio
    async def test_click_failure_warning(self, initialized_adapter, mock_process):
        """Test click failure logs warning."""
        await initialized_adapter.initialize()
        mock_process.returncode = 1
        mock_process.stderr_text = "Click failed"
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        # Should not raise, just log warning
        await initialized_adapter.click(100, 200)

    @pytest.mark.asyncio
    async def test_drag(self, initialized_adapter, mock_process):
        """Test drag operation."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.drag(100, 200, 300, 400, duration_ms=1000)

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "drag" in call_args
        assert "--from" in call_args
        assert "100,200" in call_args
        assert "--to" in call_args
        assert "300,400" in call_args
        assert "--duration" in call_args
        assert "1.0" in call_args  # 1000ms = 1.0s

    @pytest.mark.asyncio
    async def test_move(self, initialized_adapter, mock_process):
        """Test mouse move."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.move(100, 200)

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "move" in call_args
        assert "--x" in call_args
        assert "--y" in call_args

    @pytest.mark.asyncio
    async def test_scroll_down(self, initialized_adapter, mock_process):
        """Test scroll down."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.scroll(delta_y=10)

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "scroll" in call_args
        assert "--direction" in call_args
        assert "down" in call_args
        assert "--amount" in call_args
        assert "10" in call_args

    @pytest.mark.asyncio
    async def test_scroll_up(self, initialized_adapter, mock_process):
        """Test scroll up."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.scroll(delta_y=-10)

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "up" in call_args

    @pytest.mark.asyncio
    async def test_scroll_right(self, initialized_adapter, mock_process):
        """Test scroll right."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.scroll(delta_x=10)

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "right" in call_args

    @pytest.mark.asyncio
    async def test_scroll_left(self, initialized_adapter, mock_process):
        """Test scroll left."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.scroll(delta_x=-10)

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "left" in call_args

    @pytest.mark.asyncio
    async def test_scroll_no_delta(self, initialized_adapter, mock_process):
        """Test scroll with no delta does nothing."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.scroll()

        initialized_adapter._run_peekaboo.assert_not_called()

    @pytest.mark.asyncio
    async def test_scroll_at_position(self, initialized_adapter, mock_process):
        """Test scroll at specific position."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.scroll(delta_y=10, x=100, y=200)

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--x" in call_args
        assert "--y" in call_args


# =============================================================================
# Keyboard Control Tests
# =============================================================================


class TestKeyboardControl:
    """Tests for keyboard control operations."""

    @pytest.mark.asyncio
    async def test_type_text(self, initialized_adapter, mock_process):
        """Test typing text."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.type_text("Hello World")

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "type" in call_args
        assert "Hello World" in call_args

    @pytest.mark.asyncio
    async def test_type_text_with_delay(self, initialized_adapter, mock_process):
        """Test typing text with delay."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.type_text("Hello", TypeOptions(delay_ms=100))

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--delay" in call_args
        assert "100" in call_args

    @pytest.mark.asyncio
    async def test_hotkey_basic(self, initialized_adapter, mock_process):
        """Test basic hotkey."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.hotkey("cmd", "c")

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "hotkey" in call_args
        assert "--modifiers" in call_args
        assert "cmd" in call_args
        assert "--key" in call_args
        assert "c" in call_args

    @pytest.mark.asyncio
    async def test_hotkey_multiple_modifiers(self, initialized_adapter, mock_process):
        """Test hotkey with multiple modifiers."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.hotkey("cmd", "shift", "s")

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--modifiers" in call_args
        modifiers_index = call_args.index("--modifiers")
        assert "cmd,shift" in call_args[modifiers_index + 1]

    @pytest.mark.asyncio
    async def test_hotkey_no_modifiers(self, initialized_adapter, mock_process):
        """Test hotkey with just a key."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.hotkey("escape")

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--key" in call_args
        assert "escape" in call_args

    @pytest.mark.asyncio
    async def test_hotkey_empty(self, initialized_adapter, mock_process):
        """Test hotkey with no keys does nothing."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.hotkey()

        initialized_adapter._run_peekaboo.assert_not_called()

    @pytest.mark.asyncio
    async def test_press_key(self, initialized_adapter, mock_process):
        """Test pressing a single key."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.press("enter")

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "press" in call_args
        assert "--key" in call_args
        assert "enter" in call_args

    @pytest.mark.asyncio
    async def test_press_key_with_modifiers(self, initialized_adapter, mock_process):
        """Test pressing key with modifiers."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.press("a", modifiers=["cmd"])

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--modifiers" in call_args
        assert "cmd" in call_args


# =============================================================================
# Accessibility Tests
# =============================================================================


class TestAccessibility:
    """Tests for accessibility tree inspection."""

    @pytest.mark.asyncio
    async def test_get_accessibility_tree(self, initialized_adapter, mock_process):
        """Test getting accessibility tree."""
        await initialized_adapter.initialize()

        tree_data = {
            "role": "window",
            "label": "Main Window",
            "children": [
                {
                    "role": "button",
                    "label": "OK",
                    "frame": {"x": 10, "y": 20, "width": 100, "height": 30},
                },
                {"role": "textfield", "value": "Hello", "identifier": "input1"},
            ],
        }
        mock_process.stdout_text = json.dumps(tree_data)
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        tree = await initialized_adapter.get_accessibility_tree("Safari")

        assert tree is not None
        assert tree.role == "window"
        assert tree.label == "Main Window"
        assert len(tree.children) == 2
        assert tree.children[0].role == "button"
        assert tree.children[0].frame == (10, 20, 100, 30)

    @pytest.mark.asyncio
    async def test_get_accessibility_tree_failure(self, initialized_adapter, mock_process):
        """Test accessibility tree failure returns None."""
        await initialized_adapter.initialize()
        mock_process.returncode = 1
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        tree = await initialized_adapter.get_accessibility_tree()

        assert tree is None

    @pytest.mark.asyncio
    async def test_get_accessibility_tree_invalid_json(self, initialized_adapter, mock_process):
        """Test accessibility tree with invalid JSON returns None."""
        await initialized_adapter.initialize()
        mock_process.stdout_text = "invalid json"
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        tree = await initialized_adapter.get_accessibility_tree()

        assert tree is None

    @pytest.mark.asyncio
    async def test_find_element_by_label(self, initialized_adapter, mock_process):
        """Test finding element by label."""
        await initialized_adapter.initialize()

        tree_data = {
            "role": "window",
            "children": [
                {"role": "button", "label": "Cancel"},
                {"role": "button", "label": "OK"},
            ],
        }
        mock_process.stdout_text = json.dumps(tree_data)
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        element = await initialized_adapter.find_element(label="OK")

        assert element is not None
        assert element.label == "OK"

    @pytest.mark.asyncio
    async def test_find_element_by_role(self, initialized_adapter, mock_process):
        """Test finding element by role."""
        await initialized_adapter.initialize()

        tree_data = {
            "role": "window",
            "children": [
                {"role": "textfield", "value": "Hello"},
                {"role": "button", "label": "OK"},
            ],
        }
        mock_process.stdout_text = json.dumps(tree_data)
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        element = await initialized_adapter.find_element(role="textfield")

        assert element is not None
        assert element.role == "textfield"

    @pytest.mark.asyncio
    async def test_find_element_by_identifier(self, initialized_adapter, mock_process):
        """Test finding element by identifier."""
        await initialized_adapter.initialize()

        tree_data = {
            "role": "window",
            "children": [
                {"role": "textfield", "identifier": "username"},
                {"role": "textfield", "identifier": "password"},
            ],
        }
        mock_process.stdout_text = json.dumps(tree_data)
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        element = await initialized_adapter.find_element(identifier="password")

        assert element is not None
        assert element.identifier == "password"

    @pytest.mark.asyncio
    async def test_find_element_not_found(self, initialized_adapter, mock_process):
        """Test finding element that doesn't exist."""
        await initialized_adapter.initialize()

        tree_data = {"role": "window", "children": []}
        mock_process.stdout_text = json.dumps(tree_data)
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        element = await initialized_adapter.find_element(label="NonExistent")

        assert element is None

    @pytest.mark.asyncio
    async def test_click_element_success(self, initialized_adapter, mock_process):
        """Test clicking element by label."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        result = await initialized_adapter.click_element("OK", app="Safari")

        assert result is True
        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "click" in call_args
        assert "--on" in call_args
        assert "OK" in call_args
        assert "--app" in call_args
        assert "Safari" in call_args

    @pytest.mark.asyncio
    async def test_click_element_with_double_click(self, initialized_adapter, mock_process):
        """Test double-clicking element."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.click_element("File", options=ClickOptions(double_click=True))

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "--double" in call_args


# =============================================================================
# App Control Tests
# =============================================================================


class TestAppControl:
    """Tests for app control operations."""

    @pytest.mark.asyncio
    async def test_launch_app_success(self, initialized_adapter, mock_process):
        """Test launching app successfully."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        result = await initialized_adapter.launch_app("Safari")

        assert result is True
        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "app" in call_args
        assert "launch" in call_args
        assert "Safari" in call_args

    @pytest.mark.asyncio
    async def test_launch_app_failure(self, initialized_adapter, mock_process):
        """Test launching app failure."""
        await initialized_adapter.initialize()
        mock_process.returncode = 1
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        result = await initialized_adapter.launch_app("NonExistentApp")

        assert result is False

    @pytest.mark.asyncio
    async def test_quit_app_success(self, initialized_adapter, mock_process):
        """Test quitting app successfully."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        result = await initialized_adapter.quit_app("Safari")

        assert result is True
        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "app" in call_args
        assert "quit" in call_args

    @pytest.mark.asyncio
    async def test_get_frontmost_app(self, initialized_adapter, mock_process):
        """Test getting frontmost app."""
        await initialized_adapter.initialize()
        mock_process.stdout_text = json.dumps({"name": "Finder"})
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        app = await initialized_adapter.get_frontmost_app()

        assert app == "Finder"

    @pytest.mark.asyncio
    async def test_get_frontmost_app_failure(self, initialized_adapter, mock_process):
        """Test getting frontmost app failure."""
        await initialized_adapter.initialize()
        mock_process.returncode = 1
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        app = await initialized_adapter.get_frontmost_app()

        assert app is None

    @pytest.mark.asyncio
    async def test_list_running_apps(self, initialized_adapter, mock_process):
        """Test listing running apps."""
        await initialized_adapter.initialize()
        mock_process.stdout_text = json.dumps(
            {
                "apps": [
                    {"name": "Finder"},
                    {"name": "Safari"},
                    {"name": "Terminal"},
                ]
            }
        )
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        apps = await initialized_adapter.list_running_apps()

        assert apps == ["Finder", "Safari", "Terminal"]

    @pytest.mark.asyncio
    async def test_list_running_apps_failure(self, initialized_adapter, mock_process):
        """Test listing running apps failure."""
        await initialized_adapter.initialize()
        mock_process.returncode = 1
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        apps = await initialized_adapter.list_running_apps()

        assert apps == []


# =============================================================================
# Clipboard Tests
# =============================================================================


class TestClipboard:
    """Tests for clipboard operations."""

    @pytest.mark.asyncio
    async def test_get_clipboard(self, initialized_adapter, mock_process):
        """Test getting clipboard contents."""
        await initialized_adapter.initialize()
        mock_process.stdout_text = "clipboard contents"
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        text = await initialized_adapter.get_clipboard()

        assert text == "clipboard contents"
        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "clipboard" in call_args
        assert "get" in call_args

    @pytest.mark.asyncio
    async def test_get_clipboard_empty(self, initialized_adapter, mock_process):
        """Test getting empty clipboard."""
        await initialized_adapter.initialize()
        mock_process.stdout_text = ""
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        text = await initialized_adapter.get_clipboard()

        assert text is None

    @pytest.mark.asyncio
    async def test_get_clipboard_failure(self, initialized_adapter, mock_process):
        """Test clipboard get failure."""
        await initialized_adapter.initialize()
        mock_process.returncode = 1
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        text = await initialized_adapter.get_clipboard()

        assert text is None

    @pytest.mark.asyncio
    async def test_set_clipboard(self, initialized_adapter, mock_process):
        """Test setting clipboard contents."""
        await initialized_adapter.initialize()
        initialized_adapter._run_peekaboo = AsyncMock(return_value=mock_process)

        await initialized_adapter.set_clipboard("new content")

        call_args = initialized_adapter._run_peekaboo.call_args[0][0]
        assert "clipboard" in call_args
        assert "set" in call_args
        assert "new content" in call_args


# =============================================================================
# Status Tests
# =============================================================================


class TestStatus:
    """Tests for status retrieval."""

    @pytest.mark.asyncio
    async def test_get_status(self, initialized_adapter):
        """Test getting adapter status."""
        await initialized_adapter.initialize()

        status = await initialized_adapter.get_status()

        assert status.name == "host-macos"
        assert status.state == VMState.RUNNING
        assert status.os_type == OSType.MACOS
        assert status.tier == VMTier.HOST

    @pytest.mark.asyncio
    async def test_get_display_info(self, initialized_adapter):
        """Test getting display info."""
        await initialized_adapter.initialize()

        info = await initialized_adapter.get_display_info()

        # Should return reasonable macOS defaults
        assert info.width == 2560
        assert info.height == 1600
        assert info.scale_factor == 2.0  # Retina


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_parse_accessibility_element_with_actions(self, initialized_adapter):
        """Test parsing accessibility element with actions."""
        await initialized_adapter.initialize()

        data = {
            "role": "button",
            "label": "Submit",
            "actions": ["press", "cancel"],
        }

        element = initialized_adapter._parse_accessibility_element(data)

        assert element.actions == ["press", "cancel"]

    @pytest.mark.asyncio
    async def test_parse_accessibility_element_nested(self, initialized_adapter):
        """Test parsing deeply nested accessibility tree."""
        await initialized_adapter.initialize()

        data = {
            "role": "window",
            "children": [
                {
                    "role": "group",
                    "children": [
                        {"role": "button", "label": "Deep Button"},
                    ],
                },
            ],
        }

        element = initialized_adapter._parse_accessibility_element(data)

        assert element.children[0].children[0].label == "Deep Button"

    @pytest.mark.asyncio
    async def test_run_peekaboo_npx_path(self, mock_peekaboo_not_found, mock_process):
        """Test running peekaboo with npx path."""
        adapter = PeekabooAdapter()
        adapter._peekaboo_path = "npx -y @steipete/peekaboo"
        adapter._initialized = True

        with patch.object(adapter, "_run_command", AsyncMock(return_value=mock_process)):
            await adapter._run_peekaboo(["screenshot"])

            call_args = adapter._run_command.call_args[0][0]
            assert "npx" in call_args
