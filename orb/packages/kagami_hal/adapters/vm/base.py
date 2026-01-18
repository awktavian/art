"""Base VM Adapter.

Abstract base class with shared logic for VM adapters.

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .types import (
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

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BaseVMAdapter(ABC):
    """Abstract base class for VM adapters.

    Provides shared logic and default implementations for common operations.
    Concrete implementations must override abstract methods.
    """

    def __init__(self, tier: VMTier):
        """Initialize base adapter.

        Args:
            tier: VM isolation tier
        """
        self._tier = tier
        self._config: VMConfig | None = None
        self._initialized = False
        self._state = VMState.STOPPED

    @property
    def tier(self) -> VMTier:
        """Get adapter tier."""
        return self._tier

    @property
    def is_initialized(self) -> bool:
        """Check if adapter is initialized."""
        return self._initialized

    @property
    def state(self) -> VMState:
        """Get current VM state."""
        return self._state

    # =========================================================================
    # Abstract Methods (must override)
    # =========================================================================

    @abstractmethod
    async def initialize(self, config: VMConfig | None = None) -> bool:
        """Initialize the adapter."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the adapter."""
        ...

    @abstractmethod
    async def screenshot(self, retina: bool = True) -> bytes:
        """Capture screenshot."""
        ...

    @abstractmethod
    async def click(
        self,
        x: int,
        y: int,
        options: ClickOptions | None = None,
    ) -> None:
        """Click at coordinates."""
        ...

    @abstractmethod
    async def type_text(
        self,
        text: str,
        options: TypeOptions | None = None,
    ) -> None:
        """Type text."""
        ...

    @abstractmethod
    async def hotkey(self, *keys: str) -> None:
        """Execute keyboard shortcut."""
        ...

    # =========================================================================
    # Default Implementations
    # =========================================================================

    async def start(self) -> bool:
        """Start VM (no-op for Tier 1)."""
        if self._tier == VMTier.HOST:
            self._state = VMState.RUNNING
            return True
        return False

    async def stop(self) -> bool:
        """Stop VM (no-op for Tier 1)."""
        if self._tier == VMTier.HOST:
            return True
        return False

    async def restart(self) -> bool:
        """Restart VM."""
        await self.stop()
        return await self.start()

    async def get_status(self) -> VMStatus:
        """Get VM status."""
        return VMStatus(
            name=self._config.name if self._config else "unknown",
            state=self._state,
            os_type=self._config.os_type if self._config else OSType.MACOS,
            tier=self._tier,
        )

    async def get_display_info(self) -> VMDisplayInfo:
        """Get display info."""
        if self._config:
            return VMDisplayInfo(
                width=self._config.display_width,
                height=self._config.display_height,
            )
        return VMDisplayInfo(width=1920, height=1080)

    async def double_click(self, x: int, y: int) -> None:
        """Double-click at coordinates."""
        await self.click(x, y, ClickOptions(double_click=True))

    async def move(self, x: int, y: int) -> None:
        """Move mouse cursor."""
        # Default: no-op (some adapters don't support move without click)
        pass

    async def scroll(
        self,
        delta_x: int = 0,
        delta_y: int = 0,
        x: int | None = None,
        y: int | None = None,
    ) -> None:
        """Scroll at position."""
        # Default: no-op
        logger.warning(f"{self.__class__.__name__} does not support scroll")

    async def press(self, key: str, modifiers: list[str] | None = None) -> None:
        """Press a single key."""
        if modifiers:
            await self.hotkey(*modifiers, key)
        else:
            await self.hotkey(key)

    async def click_element(
        self,
        label: str,
        app: str | None = None,
        options: ClickOptions | None = None,
    ) -> bool:
        """Click element by label."""
        element = await self.find_element(label=label, app=app)
        if element and element.frame:
            x = element.frame[0] + element.frame[2] // 2
            y = element.frame[1] + element.frame[3] // 2
            await self.click(x, y, options)
            return True
        return False

    async def get_accessibility_tree(
        self,
        app: str | None = None,
        max_depth: int = 10,
    ) -> AccessibilityElement | None:
        """Get accessibility tree."""
        # Default: not supported
        return None

    async def find_element(
        self,
        label: str | None = None,
        role: str | None = None,
        identifier: str | None = None,
        app: str | None = None,
    ) -> AccessibilityElement | None:
        """Find UI element."""
        # Default: not supported
        return None

    async def launch_app(self, app_name: str) -> bool:
        """Launch app."""
        return False

    async def quit_app(self, app_name: str) -> bool:
        """Quit app."""
        return False

    async def get_frontmost_app(self) -> str | None:
        """Get frontmost app."""
        return None

    async def list_running_apps(self) -> list[str]:
        """List running apps."""
        return []

    async def get_clipboard(self) -> str | None:
        """Get clipboard."""
        return None

    async def set_clipboard(self, text: str) -> None:
        """Set clipboard."""
        pass

    # =========================================================================
    # Snapshot Methods (Tier 2/3 only)
    # =========================================================================

    async def create_snapshot(self, name: str) -> bool:
        """Create snapshot."""
        if self._tier == VMTier.HOST:
            logger.warning("Snapshots not supported on Tier 1 (host)")
            return False
        return False

    async def restore_snapshot(self, name: str) -> bool:
        """Restore snapshot."""
        if self._tier == VMTier.HOST:
            logger.warning("Snapshots not supported on Tier 1 (host)")
            return False
        return False

    async def list_snapshots(self) -> list[str]:
        """List snapshots."""
        return []

    async def delete_snapshot(self, name: str) -> bool:
        """Delete snapshot."""
        return False

    # =========================================================================
    # File Transfer Methods (Tier 2/3 only)
    # =========================================================================

    async def copy_to_vm(self, local_path: str, remote_path: str) -> bool:
        """Copy to VM."""
        if self._tier == VMTier.HOST:
            logger.warning("File transfer not needed on Tier 1 (host)")
            return False
        return False

    async def copy_from_vm(self, remote_path: str, local_path: str) -> bool:
        """Copy from VM."""
        if self._tier == VMTier.HOST:
            logger.warning("File transfer not needed on Tier 1 (host)")
            return False
        return False

    # =========================================================================
    # Command Execution (Tier 2/3 only)
    # =========================================================================

    async def execute(
        self,
        command: str,
        timeout_ms: int = 30000,
    ) -> CommandResult:
        """Execute command."""
        if self._tier == VMTier.HOST:
            logger.warning("Use subprocess for host commands, not VM execute")
            return CommandResult(exit_code=-1, stdout="", stderr="Not supported on host")
        return CommandResult(exit_code=-1, stdout="", stderr="Not implemented")


__all__ = ["BaseVMAdapter"]
