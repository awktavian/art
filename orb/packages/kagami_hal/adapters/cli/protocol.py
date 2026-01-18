"""CLI Adapter Protocol — Cross-Platform Command Execution Interface.

Defines the contract for all CLI adapters (local and remote).

Created: December 30, 2025
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class Platform(Enum):
    """Target platform for command execution."""

    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"
    AUTO = "auto"  # Detect from environment


class ShellType(Enum):
    """Shell type for command execution."""

    # Unix shells
    BASH = "bash"
    ZSH = "zsh"
    SH = "sh"
    FISH = "fish"

    # Windows shells
    CMD = "cmd"
    POWERSHELL = "powershell"
    PWSH = "pwsh"  # PowerShell Core (cross-platform)

    # Auto-detect
    AUTO = "auto"


@dataclass
class CommandResult:
    """Result of command execution."""

    # Exit status
    exit_code: int
    success: bool = field(init=False)

    # Output
    stdout: str = ""
    stderr: str = ""

    # Metadata
    command: str = ""
    shell: ShellType = ShellType.AUTO
    platform: Platform = Platform.AUTO
    duration_ms: float = 0.0

    # Remote execution info
    remote_host: str | None = None
    vm_name: str | None = None

    def __post_init__(self) -> None:
        self.success = self.exit_code == 0

    @property
    def output(self) -> str:
        """Combined stdout + stderr."""
        return self.stdout + self.stderr

    def raise_on_error(self, message: str = "") -> None:
        """Raise exception if command failed."""
        if not self.success:
            error_msg = message or f"Command failed: {self.command}"
            raise RuntimeError(f"{error_msg}\nExit code: {self.exit_code}\nStderr: {self.stderr}")


@runtime_checkable
class CLIAdapterProtocol(Protocol):
    """Protocol for CLI adapters.

    All CLI adapters must implement this interface for:
    - Command execution
    - Shell selection
    - Environment management
    - Working directory control
    """

    @property
    def platform(self) -> Platform:
        """Get the target platform."""
        ...

    @property
    def default_shell(self) -> ShellType:
        """Get the default shell for this adapter."""
        ...

    async def execute(
        self,
        command: str,
        *,
        shell: ShellType = ShellType.AUTO,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
        capture_output: bool = True,
    ) -> CommandResult:
        """Execute a command.

        Args:
            command: Command string to execute
            shell: Shell to use (AUTO = adapter default)
            cwd: Working directory (None = current)
            env: Additional environment variables
            timeout: Timeout in seconds
            capture_output: Whether to capture stdout/stderr

        Returns:
            CommandResult with exit code and output
        """
        ...

    async def execute_script(
        self,
        script: str,
        *,
        shell: ShellType = ShellType.AUTO,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> CommandResult:
        """Execute a multi-line script.

        Args:
            script: Multi-line script content
            shell: Shell to use
            cwd: Working directory
            env: Additional environment variables
            timeout: Timeout in seconds

        Returns:
            CommandResult with exit code and output
        """
        ...

    async def which(self, program: str) -> str | None:
        """Find program location (like `which` command).

        Args:
            program: Program name to find

        Returns:
            Full path to program, or None if not found
        """
        ...

    async def get_env(self, name: str) -> str | None:
        """Get environment variable value.

        Args:
            name: Variable name

        Returns:
            Variable value, or None if not set
        """
        ...

    async def set_env(self, name: str, value: str) -> None:
        """Set environment variable for subsequent commands.

        Args:
            name: Variable name
            value: Variable value
        """
        ...

    async def get_cwd(self) -> str:
        """Get current working directory."""
        ...

    async def set_cwd(self, path: str) -> None:
        """Set current working directory for subsequent commands.

        Args:
            path: Directory path
        """
        ...

    async def is_available(self) -> bool:
        """Check if this CLI adapter is available/functional."""
        ...
