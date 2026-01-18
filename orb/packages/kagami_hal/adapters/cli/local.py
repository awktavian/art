"""Local CLI Adapter — Execute Commands on Host Machine.

Provides command execution on the local machine with:
- Platform detection (macOS, Linux, Windows)
- Shell selection (bash, zsh, powershell, cmd)
- Environment and working directory management
- Timeout and error handling

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .protocol import (
    CommandResult,
    Platform,
    ShellType,
)

logger = logging.getLogger(__name__)


class LocalCLIAdapter:
    """Local command-line adapter for host machine execution.

    Features:
    - Auto-detects platform and default shell
    - Supports multiple shells per platform
    - Environment variable management
    - Working directory tracking
    - Script execution via temp files

    Usage:
        cli = LocalCLIAdapter()
        result = await cli.execute("ls -la")

        # With specific shell
        result = await cli.execute("Get-Process", shell=ShellType.POWERSHELL)

        # With environment
        result = await cli.execute("echo $MY_VAR", env={"MY_VAR": "hello"})
    """

    def __init__(self) -> None:
        """Initialize local CLI adapter."""
        self._platform = self._detect_platform()
        self._default_shell = self._detect_default_shell()
        self._env: dict[str, str] = {}
        self._cwd: str | None = None

        logger.info(
            f"LocalCLIAdapter initialized: platform={self._platform.value}, shell={self._default_shell.value}"
        )

    @property
    def platform(self) -> Platform:
        """Get detected platform."""
        return self._platform

    @property
    def default_shell(self) -> ShellType:
        """Get default shell for this platform."""
        return self._default_shell

    def _detect_platform(self) -> Platform:
        """Detect current platform."""
        system = platform.system().lower()
        if system == "darwin":
            return Platform.MACOS
        elif system == "linux":
            return Platform.LINUX
        elif system == "windows":
            return Platform.WINDOWS
        else:
            logger.warning(f"Unknown platform: {system}, defaulting to Linux")
            return Platform.LINUX

    def _detect_default_shell(self) -> ShellType:
        """Detect default shell based on platform and environment."""
        if self._platform == Platform.WINDOWS:
            # Prefer PowerShell Core if available
            if shutil.which("pwsh"):
                return ShellType.PWSH
            return ShellType.POWERSHELL

        # Unix: check SHELL environment variable
        shell_path = os.environ.get("SHELL", "/bin/bash")
        shell_name = Path(shell_path).name

        shell_map = {
            "bash": ShellType.BASH,
            "zsh": ShellType.ZSH,
            "fish": ShellType.FISH,
            "sh": ShellType.SH,
        }

        return shell_map.get(shell_name, ShellType.BASH)

    def _get_shell_command(self, shell: ShellType) -> tuple[str, list[str]]:
        """Get shell executable and arguments.

        Returns:
            Tuple of (executable, args)
        """
        shell_configs = {
            ShellType.BASH: ("bash", ["-c"]),
            ShellType.ZSH: ("zsh", ["-c"]),
            ShellType.SH: ("sh", ["-c"]),
            ShellType.FISH: ("fish", ["-c"]),
            ShellType.CMD: ("cmd", ["/c"]),
            ShellType.POWERSHELL: ("powershell", ["-Command"]),
            ShellType.PWSH: ("pwsh", ["-Command"]),
        }

        if shell == ShellType.AUTO:
            shell = self._default_shell

        return shell_configs.get(shell, ("sh", ["-c"]))

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
        """Execute a command locally.

        Args:
            command: Command string to execute
            shell: Shell to use (AUTO = platform default)
            cwd: Working directory
            env: Additional environment variables
            timeout: Timeout in seconds
            capture_output: Whether to capture output

        Returns:
            CommandResult with exit code and output
        """
        if shell == ShellType.AUTO:
            shell = self._default_shell

        # Build environment
        full_env = os.environ.copy()
        full_env.update(self._env)
        if env:
            full_env.update(env)

        # Determine working directory
        work_dir = cwd or self._cwd or os.getcwd()

        # Get shell command
        shell_exe, shell_args = self._get_shell_command(shell)

        start_time = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                shell_exe,
                *shell_args,
                command,
                cwd=work_dir,
                env=full_env,
                stdout=asyncio.subprocess.PIPE if capture_output else None,
                stderr=asyncio.subprocess.PIPE if capture_output else None,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )

            duration_ms = (time.time() - start_time) * 1000

            return CommandResult(
                exit_code=proc.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
                stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
                command=command,
                shell=shell,
                platform=self._platform,
                duration_ms=duration_ms,
            )

        except TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                command=command,
                shell=shell,
                platform=self._platform,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Command execution failed: {e}")
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                command=command,
                shell=shell,
                platform=self._platform,
                duration_ms=duration_ms,
            )

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

        Creates a temporary script file and executes it.

        Args:
            script: Multi-line script content
            shell: Shell to use
            cwd: Working directory
            env: Additional environment variables
            timeout: Timeout in seconds

        Returns:
            CommandResult with exit code and output
        """
        if shell == ShellType.AUTO:
            shell = self._default_shell

        # Determine file extension and shebang
        if shell in (ShellType.CMD, ShellType.POWERSHELL, ShellType.PWSH):
            if shell == ShellType.CMD:
                ext = ".bat"
                prefix = "@echo off\n"
            else:
                ext = ".ps1"
                prefix = ""
        else:
            ext = ".sh"
            prefix = f"#!/usr/bin/env {shell.value}\n"

        # Create temp script file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=ext,
            delete=False,
        ) as f:
            f.write(prefix + script)
            script_path = f.name

        try:
            # Make executable on Unix
            if self._platform != Platform.WINDOWS:
                os.chmod(script_path, 0o755)

            # Execute the script
            if shell == ShellType.CMD:
                command = script_path
            elif shell in (ShellType.POWERSHELL, ShellType.PWSH):
                command = f"& '{script_path}'"
            else:
                command = script_path

            return await self.execute(
                command,
                shell=shell,
                cwd=cwd,
                env=env,
                timeout=timeout,
            )
        finally:
            # Clean up temp file
            try:
                os.unlink(script_path)
            except OSError:
                pass

    async def which(self, program: str) -> str | None:
        """Find program location."""
        path = shutil.which(program)
        return path

    async def get_env(self, name: str) -> str | None:
        """Get environment variable."""
        # Check our local overrides first
        if name in self._env:
            return self._env[name]
        return os.environ.get(name)

    async def set_env(self, name: str, value: str) -> None:
        """Set environment variable for subsequent commands."""
        self._env[name] = value

    async def get_cwd(self) -> str:
        """Get current working directory."""
        return self._cwd or os.getcwd()

    async def set_cwd(self, path: str) -> None:
        """Set working directory for subsequent commands."""
        if not os.path.isdir(path):
            raise ValueError(f"Directory does not exist: {path}")
        self._cwd = path

    async def is_available(self) -> bool:
        """Check if local CLI is available (always True)."""
        return True

    # Convenience methods

    async def run(self, command: str, **kwargs: Any) -> str:
        """Execute command and return stdout (convenience method).

        Raises RuntimeError on non-zero exit code.
        """
        result = await self.execute(command, **kwargs)
        result.raise_on_error()
        return result.stdout.strip()

    async def run_python(
        self,
        code: str,
        *,
        timeout: float = 30.0,
    ) -> CommandResult:
        """Execute Python code."""
        # Use the same Python interpreter
        python = sys.executable
        return await self.execute(
            f'{python} -c "{code}"',
            timeout=timeout,
        )

    async def install_package(
        self,
        package: str,
        *,
        pip_args: list[str] | None = None,
    ) -> CommandResult:
        """Install a Python package via pip."""
        python = sys.executable
        args = pip_args or []
        return await self.execute(
            f"{python} -m pip install {' '.join(args)} {package}",
            timeout=120.0,
        )


# Singleton instance
_local_cli: LocalCLIAdapter | None = None


def get_local_cli() -> LocalCLIAdapter:
    """Get or create the local CLI adapter singleton."""
    global _local_cli
    if _local_cli is None:
        _local_cli = LocalCLIAdapter()
    return _local_cli
