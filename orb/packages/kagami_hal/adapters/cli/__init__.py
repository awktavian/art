"""Cross-Platform Command Line Interface Adapter.

Provides unified shell/command execution across all platforms:
- Local: macOS, Linux, Windows
- Remote: VM execution via Parallels, Lume, SSH

This is the canonical entry point for all command-line operations in Kagami.

Created: December 30, 2025
"""

from kagami_hal.adapters.cli.local import LocalCLIAdapter
from kagami_hal.adapters.cli.protocol import (
    CLIAdapterProtocol,
    CommandResult,
    Platform,
    ShellType,
)
from kagami_hal.adapters.cli.remote import RemoteCLIAdapter
from kagami_hal.adapters.cli.unified import (
    UnifiedCLI,
    get_local_cli,
    get_remote_cli,
    get_unified_cli,
)

__all__ = [
    # Protocol
    "CLIAdapterProtocol",
    "CommandResult",
    # Adapters
    "LocalCLIAdapter",
    "Platform",
    "RemoteCLIAdapter",
    "ShellType",
    # Unified interface
    "UnifiedCLI",
    "get_local_cli",
    "get_remote_cli",
    "get_unified_cli",
]
