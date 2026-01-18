"""VM Adapter Protocol.

Protocol definition for VM-based computer control adapters.
Supports three tiers:
- Tier 1 (Host): Peekaboo for direct macOS control
- Tier 2 (Sandboxed): CUA/Lume for isolated macOS VMs
- Tier 3 (Multi-OS): Parallels for Windows/Linux VMs

Created: December 30, 2025
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .types import (
        AccessibilityElement,
        ClickOptions,
        CommandResult,
        TypeOptions,
        VMConfig,
        VMDisplayInfo,
        VMStatus,
    )


@runtime_checkable
class VMAdapterProtocol(Protocol):
    """Protocol for VM-based computer control.

    This protocol defines a unified interface for controlling computers
    across three tiers:

    Tier 1 (Host): Direct control of the host macOS via Peekaboo
    Tier 2 (Sandboxed): Isolated macOS VMs via CUA/Lume (97% native perf)
    Tier 3 (Multi-OS): Windows/Linux VMs via Parallels

    All methods are async for consistency with kagami_hal patterns.
    """

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def initialize(self, config: VMConfig | None = None) -> bool:
        """Initialize the VM adapter.

        Args:
            config: Optional VM configuration

        Returns:
            True if initialization succeeded
        """
        ...

    async def shutdown(self) -> None:
        """Shutdown the adapter and release resources."""
        ...

    async def start(self) -> bool:
        """Start the VM (no-op for Tier 1 host).

        Returns:
            True if VM started successfully
        """
        ...

    async def stop(self) -> bool:
        """Stop the VM (no-op for Tier 1 host).

        Returns:
            True if VM stopped successfully
        """
        ...

    async def restart(self) -> bool:
        """Restart the VM.

        Returns:
            True if restart succeeded
        """
        ...

    async def get_status(self) -> VMStatus:
        """Get current VM status.

        Returns:
            VMStatus with state, display info, etc.
        """
        ...

    # =========================================================================
    # Display / Screenshots
    # =========================================================================

    async def screenshot(self, retina: bool = True) -> bytes:
        """Capture screenshot of the VM display.

        Args:
            retina: If True, capture at Retina resolution (2x)

        Returns:
            PNG image data as bytes
        """
        ...

    async def get_display_info(self) -> VMDisplayInfo:
        """Get VM display information.

        Returns:
            Display dimensions, scale, refresh rate
        """
        ...

    # =========================================================================
    # Mouse Input
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
            options: Click options (button, modifiers, double-click)
        """
        ...

    async def click_element(
        self,
        label: str,
        app: str | None = None,
        options: ClickOptions | None = None,
    ) -> bool:
        """Click a UI element by accessibility label.

        Args:
            label: Accessibility label to click
            app: Optional app name to scope search
            options: Click options

        Returns:
            True if element found and clicked
        """
        ...

    async def double_click(self, x: int, y: int) -> None:
        """Double-click at coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        ...

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
            x1: Start X coordinate
            y1: Start Y coordinate
            x2: End X coordinate
            y2: End Y coordinate
            duration_ms: Duration of drag operation
        """
        ...

    async def move(self, x: int, y: int) -> None:
        """Move mouse cursor to coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        ...

    async def scroll(
        self,
        delta_x: int = 0,
        delta_y: int = 0,
        x: int | None = None,
        y: int | None = None,
    ) -> None:
        """Scroll at current or specified position.

        Args:
            delta_x: Horizontal scroll amount
            delta_y: Vertical scroll amount
            x: Optional X coordinate to scroll at
            y: Optional Y coordinate to scroll at
        """
        ...

    # =========================================================================
    # Keyboard Input
    # =========================================================================

    async def type_text(
        self,
        text: str,
        options: TypeOptions | None = None,
    ) -> None:
        """Type text string.

        Args:
            text: Text to type
            options: Typing options (delay, clear first)
        """
        ...

    async def hotkey(self, *keys: str) -> None:
        """Execute keyboard shortcut.

        Args:
            keys: Key names (e.g., "cmd", "c" for Cmd+C)

        Examples:
            await vm.hotkey("cmd", "c")  # Copy
            await vm.hotkey("cmd", "shift", "3")  # Screenshot
        """
        ...

    async def press(self, key: str, modifiers: list[str] | None = None) -> None:
        """Press a single key.

        Args:
            key: Key name (e.g., "enter", "tab", "escape")
            modifiers: Optional modifier keys
        """
        ...

    # =========================================================================
    # Accessibility / UI Inspection
    # =========================================================================

    async def get_accessibility_tree(
        self,
        app: str | None = None,
        max_depth: int = 10,
    ) -> AccessibilityElement | None:
        """Get accessibility tree for an app.

        Args:
            app: App name (None for frontmost app)
            max_depth: Maximum tree depth to traverse

        Returns:
            Root accessibility element, or None if unavailable
        """
        ...

    async def find_element(
        self,
        label: str | None = None,
        role: str | None = None,
        identifier: str | None = None,
        app: str | None = None,
    ) -> AccessibilityElement | None:
        """Find a UI element by attributes.

        Args:
            label: Accessibility label
            role: Element role (button, textfield, etc.)
            identifier: Accessibility identifier
            app: App name to search in

        Returns:
            Matching element, or None if not found
        """
        ...

    # =========================================================================
    # App Control
    # =========================================================================

    async def launch_app(self, app_name: str) -> bool:
        """Launch an application.

        Args:
            app_name: Application name or bundle ID

        Returns:
            True if app launched successfully
        """
        ...

    async def quit_app(self, app_name: str) -> bool:
        """Quit an application.

        Args:
            app_name: Application name or bundle ID

        Returns:
            True if app quit successfully
        """
        ...

    async def get_frontmost_app(self) -> str | None:
        """Get name of frontmost application.

        Returns:
            App name, or None if unavailable
        """
        ...

    async def list_running_apps(self) -> list[str]:
        """List running applications.

        Returns:
            List of application names
        """
        ...

    # =========================================================================
    # Clipboard
    # =========================================================================

    async def get_clipboard(self) -> str | None:
        """Get clipboard text content.

        Returns:
            Clipboard text, or None if empty/non-text
        """
        ...

    async def set_clipboard(self, text: str) -> None:
        """Set clipboard text content.

        Args:
            text: Text to copy to clipboard
        """
        ...

    # =========================================================================
    # Snapshots (Tier 2/3 only)
    # =========================================================================

    async def create_snapshot(self, name: str) -> bool:
        """Create a VM snapshot.

        Args:
            name: Snapshot name

        Returns:
            True if snapshot created successfully
        """
        ...

    async def restore_snapshot(self, name: str) -> bool:
        """Restore a VM snapshot.

        Args:
            name: Snapshot name

        Returns:
            True if snapshot restored successfully
        """
        ...

    async def list_snapshots(self) -> list[str]:
        """List available snapshots.

        Returns:
            List of snapshot names
        """
        ...

    async def delete_snapshot(self, name: str) -> bool:
        """Delete a snapshot.

        Args:
            name: Snapshot name

        Returns:
            True if snapshot deleted successfully
        """
        ...

    # =========================================================================
    # File Transfer (Tier 2/3 only)
    # =========================================================================

    async def copy_to_vm(self, local_path: str, remote_path: str) -> bool:
        """Copy file from host to VM.

        Args:
            local_path: Path on host
            remote_path: Path in VM

        Returns:
            True if copy succeeded
        """
        ...

    async def copy_from_vm(self, remote_path: str, local_path: str) -> bool:
        """Copy file from VM to host.

        Args:
            remote_path: Path in VM
            local_path: Path on host

        Returns:
            True if copy succeeded
        """
        ...

    # =========================================================================
    # Command Execution (Tier 2/3 only)
    # =========================================================================

    async def execute(
        self,
        command: str,
        timeout_ms: int = 30000,
    ) -> CommandResult:
        """Execute shell command in VM.

        Args:
            command: Shell command to execute
            timeout_ms: Timeout in milliseconds

        Returns:
            CommandResult with exit code, stdout, stderr
        """
        ...


__all__ = ["VMAdapterProtocol"]
