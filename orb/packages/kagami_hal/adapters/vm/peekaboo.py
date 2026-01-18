"""Peekaboo VM Adapter (Tier 1: Host macOS Control).

Direct control of the host macOS via Peekaboo CLI.
This is the fastest tier with zero isolation - for trusted operations only.

Requires:
- Peekaboo installed: brew install steipete/tap/peekaboo
- Screen Recording permission granted
- Accessibility permission granted

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .base import BaseVMAdapter
from .types import (
    AccessibilityElement,
    ClickOptions,
    OSType,
    TypeOptions,
    VMConfig,
    VMDisplayInfo,
    VMState,
    VMStatus,
    VMTier,
)

logger = logging.getLogger(__name__)


class PeekabooAdapter(BaseVMAdapter):
    """Tier 1 VM adapter using Peekaboo for host macOS control.

    This adapter provides direct control over the host macOS system
    using the Peekaboo CLI. It offers:

    - Screenshot capture (screen, window, app)
    - Mouse control (click, drag, scroll)
    - Keyboard control (type, hotkey)
    - Accessibility tree inspection
    - App control (launch, quit)
    - Clipboard access

    Security: This tier has NO isolation. Use only for trusted operations.

    Usage:
        adapter = PeekabooAdapter()
        await adapter.initialize()

        # Take screenshot
        screenshot = await adapter.screenshot()

        # Click at coordinates
        await adapter.click(100, 200)

        # Type text
        await adapter.type_text("Hello, World!")

        # Execute keyboard shortcut
        await adapter.hotkey("cmd", "c")

        # Get accessibility tree
        tree = await adapter.get_accessibility_tree("Safari")
    """

    def __init__(self):
        """Initialize Peekaboo adapter."""
        super().__init__(tier=VMTier.HOST)
        self._peekaboo_path: str | None = None
        self._session_id: str | None = None

    async def initialize(self, config: VMConfig | None = None) -> bool:
        """Initialize Peekaboo adapter.

        Verifies Peekaboo is installed and permissions are granted.

        Args:
            config: Optional config (mostly ignored for Tier 1)

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        # Find peekaboo binary
        self._peekaboo_path = shutil.which("peekaboo")
        if not self._peekaboo_path:
            # Try npx fallback
            try:
                result = await self._run_command(["npx", "-y", "@steipete/peekaboo", "--version"])
                if result.returncode == 0:
                    self._peekaboo_path = "npx -y @steipete/peekaboo"
                    logger.info("Using Peekaboo via npx")
            except Exception:
                pass

        if not self._peekaboo_path:
            logger.error("Peekaboo not found. Install via: brew install steipete/tap/peekaboo")
            return False

        # Check permissions
        try:
            result = await self._run_peekaboo(["permissions"])
            if "Granted" not in result.stdout_text:
                logger.warning(
                    "Peekaboo permissions not fully granted. "
                    "Grant Screen Recording and Accessibility in System Preferences."
                )
        except Exception as e:
            logger.warning(f"Could not check Peekaboo permissions: {e}")

        # Store config
        self._config = config or VMConfig(
            name="host-macos",
            os_type=OSType.MACOS,
            tier=VMTier.HOST,
        )

        self._state = VMState.RUNNING
        self._initialized = True
        logger.info("✅ Peekaboo adapter initialized (Tier 1: Host macOS)")
        return True

    async def shutdown(self) -> None:
        """Shutdown adapter."""
        self._initialized = False
        self._state = VMState.STOPPED
        logger.info("Peekaboo adapter shutdown")

    async def _run_command(
        self,
        args: list[str],
        timeout: float = 30.0,
    ) -> asyncio.subprocess.Process:
        """Run a shell command.

        Args:
            args: Command arguments
            timeout: Timeout in seconds

        Returns:
            Completed process
        """
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        proc.stdout_text = stdout.decode() if stdout else ""
        proc.stderr_text = stderr.decode() if stderr else ""
        return proc

    async def _run_peekaboo(
        self,
        args: list[str],
        timeout: float = 30.0,
    ) -> Any:
        """Run a Peekaboo command.

        Args:
            args: Peekaboo subcommand and arguments
            timeout: Timeout in seconds

        Returns:
            Process result with stdout/stderr
        """
        if self._peekaboo_path and " " in self._peekaboo_path:
            # npx command
            full_args = self._peekaboo_path.split() + args
        else:
            full_args = [self._peekaboo_path or "peekaboo", *args]

        return await self._run_command(full_args, timeout)

    # =========================================================================
    # Screenshots
    # =========================================================================

    async def screenshot(self, retina: bool = True) -> bytes:
        """Capture screenshot of the screen.

        Args:
            retina: If True, capture at Retina resolution

        Returns:
            PNG image data
        """
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name

        try:
            args = ["image", "--mode", "screen", "--path", temp_path]
            if retina:
                args.append("--retina")

            result = await self._run_peekaboo(args)
            if result.returncode != 0:
                raise RuntimeError(f"Screenshot failed: {result.stderr_text}")

            return Path(temp_path).read_bytes()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def screenshot_app(self, app_name: str, retina: bool = True) -> bytes:
        """Capture screenshot of a specific app.

        Args:
            app_name: Application name
            retina: Retina resolution

        Returns:
            PNG image data
        """
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name

        try:
            args = ["image", "--mode", "app", "--app", app_name, "--path", temp_path]
            if retina:
                args.append("--retina")

            result = await self._run_peekaboo(args)
            if result.returncode != 0:
                raise RuntimeError(f"Screenshot failed: {result.stderr_text}")

            return Path(temp_path).read_bytes()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def get_display_info(self) -> VMDisplayInfo:
        """Get display information."""
        # Peekaboo doesn't have a direct display info command
        # Return common macOS defaults
        return VMDisplayInfo(
            width=2560,  # Common MacBook Pro resolution
            height=1600,
            scale_factor=2.0,  # Retina
            color_depth=32,
            refresh_rate=60,
        )

    # =========================================================================
    # Mouse Control
    # =========================================================================

    async def click(
        self,
        x: int,
        y: int,
        options: ClickOptions | None = None,
    ) -> None:
        """Click at coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            options: Click options
        """
        opts = options or ClickOptions()
        args = ["click", "--x", str(x), "--y", str(y)]

        if opts.button == "right":
            args.extend(["--button", "right"])
        elif opts.button == "middle":
            args.extend(["--button", "middle"])

        if opts.double_click:
            args.append("--double")

        if opts.modifiers:
            args.extend(["--modifiers", ",".join(opts.modifiers)])

        result = await self._run_peekaboo(args)
        if result.returncode != 0:
            logger.warning(f"Click failed: {result.stderr_text}")

    async def drag(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 500,
    ) -> None:
        """Drag from one point to another.

        Args:
            x1, y1: Start coordinates
            x2, y2: End coordinates
            duration_ms: Duration in milliseconds
        """
        args = [
            "drag",
            "--from",
            f"{x1},{y1}",
            "--to",
            f"{x2},{y2}",
            "--duration",
            str(duration_ms / 1000),
        ]
        result = await self._run_peekaboo(args)
        if result.returncode != 0:
            logger.warning(f"Drag failed: {result.stderr_text}")

    async def move(self, x: int, y: int) -> None:
        """Move mouse cursor.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        args = ["move", "--x", str(x), "--y", str(y)]
        result = await self._run_peekaboo(args)
        if result.returncode != 0:
            logger.warning(f"Move failed: {result.stderr_text}")

    async def scroll(
        self,
        delta_x: int = 0,
        delta_y: int = 0,
        x: int | None = None,
        y: int | None = None,
    ) -> None:
        """Scroll at position.

        Args:
            delta_x: Horizontal scroll amount
            delta_y: Vertical scroll amount
            x, y: Optional position to scroll at
        """
        args = ["scroll"]
        if delta_y > 0:
            args.extend(["--direction", "down", "--amount", str(abs(delta_y))])
        elif delta_y < 0:
            args.extend(["--direction", "up", "--amount", str(abs(delta_y))])
        elif delta_x > 0:
            args.extend(["--direction", "right", "--amount", str(abs(delta_x))])
        elif delta_x < 0:
            args.extend(["--direction", "left", "--amount", str(abs(delta_x))])
        else:
            return  # No scroll

        if x is not None and y is not None:
            args.extend(["--x", str(x), "--y", str(y)])

        result = await self._run_peekaboo(args)
        if result.returncode != 0:
            logger.warning(f"Scroll failed: {result.stderr_text}")

    # =========================================================================
    # Keyboard Control
    # =========================================================================

    async def type_text(
        self,
        text: str,
        options: TypeOptions | None = None,
    ) -> None:
        """Type text string.

        Args:
            text: Text to type
            options: Typing options
        """
        opts = options or TypeOptions()
        args = ["type", text]

        if opts.delay_ms > 0:
            args.extend(["--delay", str(opts.delay_ms)])

        result = await self._run_peekaboo(args)
        if result.returncode != 0:
            logger.warning(f"Type failed: {result.stderr_text}")

    async def hotkey(self, *keys: str) -> None:
        """Execute keyboard shortcut.

        Args:
            keys: Key names (e.g., "cmd", "c" for Cmd+C)
        """
        if not keys:
            return

        # Separate modifiers from regular keys
        modifiers = []
        regular_keys = []
        for key in keys:
            if key.lower() in ("cmd", "command", "shift", "alt", "option", "ctrl", "control"):
                modifiers.append(key)
            else:
                regular_keys.append(key)

        args = ["hotkey"]
        if modifiers:
            args.extend(["--modifiers", ",".join(modifiers)])
        if regular_keys:
            args.extend(["--key", regular_keys[0]])  # Usually just one key

        result = await self._run_peekaboo(args)
        if result.returncode != 0:
            logger.warning(f"Hotkey failed: {result.stderr_text}")

    async def press(self, key: str, modifiers: list[str] | None = None) -> None:
        """Press a single key.

        Args:
            key: Key name
            modifiers: Optional modifiers
        """
        args = ["press", "--key", key]
        if modifiers:
            args.extend(["--modifiers", ",".join(modifiers)])

        result = await self._run_peekaboo(args)
        if result.returncode != 0:
            logger.warning(f"Press failed: {result.stderr_text}")

    # =========================================================================
    # Accessibility
    # =========================================================================

    async def get_accessibility_tree(
        self,
        app: str | None = None,
        max_depth: int = 10,
    ) -> AccessibilityElement | None:
        """Get accessibility tree for an app.

        Args:
            app: App name (None for frontmost)
            max_depth: Maximum depth

        Returns:
            Root accessibility element
        """
        args = ["see", "--json-output"]
        if app:
            args.extend(["--app", app])
        args.extend(["--max-depth", str(max_depth)])

        result = await self._run_peekaboo(args, timeout=60.0)
        if result.returncode != 0:
            logger.warning(f"Accessibility tree failed: {result.stderr_text}")
            return None

        try:
            data = json.loads(result.stdout_text)
            return self._parse_accessibility_element(data)
        except json.JSONDecodeError:
            logger.warning("Failed to parse accessibility tree JSON")
            return None

    def _parse_accessibility_element(self, data: dict) -> AccessibilityElement:
        """Parse accessibility element from Peekaboo JSON.

        Args:
            data: JSON data from Peekaboo

        Returns:
            AccessibilityElement
        """
        children = []
        for child in data.get("children", []):
            children.append(self._parse_accessibility_element(child))

        frame = None
        if "frame" in data:
            f = data["frame"]
            frame = (f.get("x", 0), f.get("y", 0), f.get("width", 0), f.get("height", 0))

        return AccessibilityElement(
            role=data.get("role", "unknown"),
            label=data.get("label"),
            value=data.get("value"),
            identifier=data.get("identifier"),
            frame=frame,
            children=children,
            actions=data.get("actions", []),
        )

    async def find_element(
        self,
        label: str | None = None,
        role: str | None = None,
        identifier: str | None = None,
        app: str | None = None,
    ) -> AccessibilityElement | None:
        """Find a UI element.

        Args:
            label: Accessibility label
            role: Element role
            identifier: Accessibility identifier
            app: App name

        Returns:
            Matching element or None
        """
        tree = await self.get_accessibility_tree(app)
        if not tree:
            return None

        return self._find_in_tree(tree, label, role, identifier)

    def _find_in_tree(
        self,
        element: AccessibilityElement,
        label: str | None,
        role: str | None,
        identifier: str | None,
    ) -> AccessibilityElement | None:
        """Recursively find element in tree.

        Args:
            element: Current element
            label, role, identifier: Search criteria

        Returns:
            Matching element or None
        """
        # Check current element
        matches = True
        if label and element.label != label:
            matches = False
        if role and element.role != role:
            matches = False
        if identifier and element.identifier != identifier:
            matches = False

        if matches and (label or role or identifier):
            return element

        # Search children
        for child in element.children:
            found = self._find_in_tree(child, label, role, identifier)
            if found:
                return found

        return None

    async def click_element(
        self,
        label: str,
        app: str | None = None,
        options: ClickOptions | None = None,
    ) -> bool:
        """Click element by label using Peekaboo's native click-on feature.

        Args:
            label: Element label to click
            app: App to search in
            options: Click options

        Returns:
            True if element found and clicked
        """
        args = ["click", "--on", label]
        if app:
            args.extend(["--app", app])

        opts = options or ClickOptions()
        if opts.double_click:
            args.append("--double")

        result = await self._run_peekaboo(args)
        return result.returncode == 0

    # =========================================================================
    # App Control
    # =========================================================================

    async def launch_app(self, app_name: str) -> bool:
        """Launch an application.

        Args:
            app_name: Application name

        Returns:
            True if launched
        """
        args = ["app", "launch", app_name]
        result = await self._run_peekaboo(args)
        return result.returncode == 0

    async def quit_app(self, app_name: str) -> bool:
        """Quit an application.

        Args:
            app_name: Application name

        Returns:
            True if quit
        """
        args = ["app", "quit", app_name]
        result = await self._run_peekaboo(args)
        return result.returncode == 0

    async def get_frontmost_app(self) -> str | None:
        """Get frontmost application name.

        Returns:
            App name or None
        """
        args = ["app", "list", "--frontmost", "--json-output"]
        result = await self._run_peekaboo(args)
        if result.returncode != 0:
            return None

        try:
            data = json.loads(result.stdout_text)
            return data.get("name")
        except (json.JSONDecodeError, KeyError):
            return None

    async def list_running_apps(self) -> list[str]:
        """List running applications.

        Returns:
            List of app names
        """
        args = ["app", "list", "--json-output"]
        result = await self._run_peekaboo(args)
        if result.returncode != 0:
            return []

        try:
            data = json.loads(result.stdout_text)
            return [app.get("name", "") for app in data.get("apps", [])]
        except (json.JSONDecodeError, KeyError):
            return []

    # =========================================================================
    # Clipboard
    # =========================================================================

    async def get_clipboard(self) -> str | None:
        """Get clipboard text.

        Returns:
            Clipboard text or None
        """
        args = ["clipboard", "get"]
        result = await self._run_peekaboo(args)
        if result.returncode != 0:
            return None
        return result.stdout_text.strip() or None

    async def set_clipboard(self, text: str) -> None:
        """Set clipboard text.

        Args:
            text: Text to copy
        """
        args = ["clipboard", "set", text]
        await self._run_peekaboo(args)

    # =========================================================================
    # Status
    # =========================================================================

    async def get_status(self) -> VMStatus:
        """Get adapter status.

        Returns:
            VMStatus for host macOS
        """
        display = await self.get_display_info()
        return VMStatus(
            name="host-macos",
            state=self._state,
            os_type=OSType.MACOS,
            tier=VMTier.HOST,
            display=display,
            cpu_count=0,  # Not applicable for host
            memory_mb=0,  # Not applicable for host
            uptime_seconds=0,
        )


__all__ = ["PeekabooAdapter"]
