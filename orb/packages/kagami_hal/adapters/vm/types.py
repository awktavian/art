"""VM Adapter Types.

Type definitions for VM-based computer control adapters.

Created: December 30, 2025
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VMTier(Enum):
    """VM isolation tier."""

    HOST = 1  # Direct host control (Peekaboo)
    SANDBOXED = 2  # Isolated VM (CUA/Lume)
    MULTI_OS = 3  # Multi-OS VM (Parallels)


class VMState(Enum):
    """Virtual machine state."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    STOPPING = "stopping"
    ERROR = "error"


class OSType(Enum):
    """Operating system type."""

    MACOS = "macos"
    WINDOWS = "windows"
    LINUX = "linux"
    UNKNOWN = "unknown"


@dataclass
class VMDisplayInfo:
    """VM display information."""

    width: int
    height: int
    scale_factor: float = 1.0
    color_depth: int = 32
    refresh_rate: int = 60


@dataclass
class VMStatus:
    """VM status information."""

    name: str
    state: VMState
    os_type: OSType
    tier: VMTier
    display: VMDisplayInfo | None = None
    cpu_count: int = 0
    memory_mb: int = 0
    uptime_seconds: float = 0.0
    snapshots: list[str] = field(default_factory=list)
    error_message: str | None = None


@dataclass
class VMConfig:
    """VM configuration."""

    name: str
    os_type: OSType = OSType.MACOS
    tier: VMTier = VMTier.SANDBOXED
    memory_mb: int = 8192
    cpu_count: int = 4
    display_width: int = 1920
    display_height: int = 1080
    base_snapshot: str = "clean-state"
    auto_restore_on_release: bool = True


@dataclass
class ClickOptions:
    """Options for click operations."""

    button: str = "left"  # left, right, middle
    modifiers: list[str] = field(default_factory=list)  # cmd, shift, alt, ctrl
    double_click: bool = False


@dataclass
class TypeOptions:
    """Options for typing operations."""

    delay_ms: int = 0  # Delay between keystrokes
    clear_first: bool = False  # Clear field before typing


@dataclass
class AccessibilityElement:
    """UI accessibility element."""

    role: str  # button, textfield, statictext, etc.
    label: str | None = None
    value: str | None = None
    identifier: str | None = None
    frame: tuple[int, int, int, int] | None = None  # x, y, width, height
    children: list[AccessibilityElement] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


@dataclass
class CommandResult:
    """Result of command execution."""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float = 0.0


__all__ = [
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
