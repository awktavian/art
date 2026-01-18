"""Remote CLI Adapter — Execute Commands on Remote Machines/VMs.

Provides command execution on remote systems via:
- Parallels (prlctl exec)
- SSH
- Lume/CUA VMs

Created: December 30, 2025
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .local import get_local_cli
from .protocol import (
    CommandResult,
    Platform,
    ShellType,
)

logger = logging.getLogger(__name__)


class RemoteType(Enum):
    """Type of remote connection."""

    PARALLELS = "parallels"  # Via prlctl exec
    SSH = "ssh"  # Via SSH
    LUME = "lume"  # Via Lume VM (SSH-based)


@dataclass
class RemoteConfig:
    """Configuration for remote connection."""

    remote_type: RemoteType

    # For Parallels
    vm_name: str | None = None

    # For SSH
    host: str | None = None
    port: int = 22
    user: str | None = None
    key_file: str | None = None
    password: str | None = None

    # Platform hint (for shell selection)
    platform: Platform = Platform.AUTO


class RemoteCLIAdapter:
    """Remote CLI adapter for VM/SSH execution.

    Supports:
    - Parallels VMs (Windows, Linux, macOS)
    - SSH connections
    - Lume macOS VMs (via SSH)

    Usage:
        # Parallels
        cli = RemoteCLIAdapter.for_parallels("Gaming")
        result = await cli.execute("dir C:\\")

        # SSH
        cli = RemoteCLIAdapter.for_ssh("192.168.64.2", user="admin")
        result = await cli.execute("ls -la")

        # Lume
        cli = RemoteCLIAdapter.for_lume("macos-sequoia-cua_latest")
        result = await cli.execute("ls -la")
    """

    def __init__(self, config: RemoteConfig) -> None:
        """Initialize remote CLI adapter.

        Args:
            config: Remote connection configuration
        """
        self._config = config
        self._platform = config.platform
        self._env: dict[str, str] = {}
        self._cwd: str | None = None
        self._local = get_local_cli()

        # Auto-detect platform if needed
        if self._platform == Platform.AUTO:
            self._platform = self._detect_platform()

    @classmethod
    def for_parallels(
        cls,
        vm_name: str,
        platform: Platform = Platform.WINDOWS,
    ) -> RemoteCLIAdapter:
        """Create adapter for Parallels VM.

        Args:
            vm_name: Name of the Parallels VM (e.g., "Gaming")
            platform: Platform type (WINDOWS, LINUX, MACOS)
        """
        return cls(
            RemoteConfig(
                remote_type=RemoteType.PARALLELS,
                vm_name=vm_name,
                platform=platform,
            )
        )

    @classmethod
    def for_ssh(
        cls,
        host: str,
        *,
        user: str = "root",
        port: int = 22,
        key_file: str | None = None,
        password: str | None = None,
        platform: Platform = Platform.LINUX,
    ) -> RemoteCLIAdapter:
        """Create adapter for SSH connection.

        Args:
            host: Remote hostname or IP
            user: SSH username
            port: SSH port
            key_file: Path to SSH private key
            password: SSH password (not recommended)
            platform: Platform type
        """
        return cls(
            RemoteConfig(
                remote_type=RemoteType.SSH,
                host=host,
                port=port,
                user=user,
                key_file=key_file,
                password=password,
                platform=platform,
            )
        )

    @classmethod
    def for_lume(
        cls,
        vm_name: str = "macos-sequoia-cua_latest",
        password: str = "lume",
    ) -> RemoteCLIAdapter:
        """Create adapter for Lume macOS VM.

        Args:
            vm_name: Name of the Lume VM
            password: SSH password (default: lume)
        """
        return cls(
            RemoteConfig(
                remote_type=RemoteType.LUME,
                vm_name=vm_name,
                password=password,
                platform=Platform.MACOS,
            )
        )

    @property
    def platform(self) -> Platform:
        """Get target platform."""
        return self._platform

    @property
    def default_shell(self) -> ShellType:
        """Get default shell for target platform."""
        if self._platform == Platform.WINDOWS:
            return ShellType.CMD
        elif self._platform == Platform.MACOS:
            return ShellType.ZSH
        else:
            return ShellType.BASH

    def _detect_platform(self) -> Platform:
        """Detect platform based on remote type and config."""
        if self._config.remote_type == RemoteType.PARALLELS:
            # Parallels VMs are typically Windows
            return Platform.WINDOWS
        elif self._config.remote_type == RemoteType.LUME:
            # Lume VMs are always macOS
            return Platform.MACOS
        else:
            # SSH - default to Linux
            return Platform.LINUX

    async def _get_lume_ip(self) -> str | None:
        """Get IP address of Lume VM."""
        result = await self._local.execute(
            f"lume ls | grep {self._config.vm_name} | awk '{{print $NF}}'",
            shell=ShellType.BASH,
        )
        if result.success and result.stdout.strip():
            # Parse IP from the output (might be in IP column or need extraction)
            output = result.stdout.strip()
            # Check if it's an IP address
            import re

            ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", output)
            if ip_match:
                return ip_match.group(1)
        return None

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
        """Execute command on remote machine.

        Args:
            command: Command to execute
            shell: Shell to use
            cwd: Working directory
            env: Environment variables
            timeout: Timeout in seconds
            capture_output: Whether to capture output

        Returns:
            CommandResult with exit code and output
        """
        if shell == ShellType.AUTO:
            shell = self.default_shell

        # Build the command with environment and cwd
        full_command = command
        work_dir = cwd or self._cwd

        # Merge environments
        full_env = dict(self._env)
        if env:
            full_env.update(env)

        # Add environment prefix if needed
        if full_env:
            if self._platform == Platform.WINDOWS:
                env_prefix = " && ".join(f"set {k}={v}" for k, v in full_env.items())
                full_command = f"{env_prefix} && {command}"
            else:
                env_prefix = " ".join(f"{k}={v}" for k, v in full_env.items())
                full_command = f"{env_prefix} {command}"

        # Add cd prefix if needed
        if work_dir:
            if self._platform == Platform.WINDOWS:
                full_command = f"cd /d {work_dir} && {full_command}"
            else:
                full_command = f"cd {work_dir} && {full_command}"

        start_time = time.time()

        try:
            if self._config.remote_type == RemoteType.PARALLELS:
                result = await self._execute_parallels(full_command, shell, timeout)
            elif self._config.remote_type == RemoteType.SSH:
                result = await self._execute_ssh(full_command, shell, timeout)
            elif self._config.remote_type == RemoteType.LUME:
                result = await self._execute_lume(full_command, shell, timeout)
            else:
                raise ValueError(f"Unknown remote type: {self._config.remote_type}")

            result.command = command
            result.shell = shell
            result.platform = self._platform
            result.duration_ms = (time.time() - start_time) * 1000
            result.vm_name = self._config.vm_name
            result.remote_host = self._config.host

            return result

        except Exception as e:
            logger.error(f"Remote execution failed: {e}")
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                command=command,
                shell=shell,
                platform=self._platform,
                duration_ms=(time.time() - start_time) * 1000,
                vm_name=self._config.vm_name,
                remote_host=self._config.host,
            )

    async def _execute_parallels(
        self,
        command: str,
        shell: ShellType,
        timeout: float,
    ) -> CommandResult:
        """Execute command via prlctl exec."""
        vm_name = self._config.vm_name

        # Build prlctl command based on shell type
        if shell in (ShellType.CMD, ShellType.POWERSHELL, ShellType.PWSH):
            if shell == ShellType.CMD:
                prlctl_cmd = f'prlctl exec "{vm_name}" cmd /c "{command}"'
            else:
                # PowerShell
                shell_exe = "powershell" if shell == ShellType.POWERSHELL else "pwsh"
                escaped_cmd = command.replace('"', '\\"')
                prlctl_cmd = f'prlctl exec "{vm_name}" {shell_exe} -Command "{escaped_cmd}"'
        else:
            # Unix shell
            escaped_cmd = command.replace("'", "'\"'\"'")
            prlctl_cmd = f"prlctl exec \"{vm_name}\" {shell.value} -c '{escaped_cmd}'"

        return await self._local.execute(prlctl_cmd, timeout=timeout)

    async def _execute_ssh(
        self,
        command: str,
        shell: ShellType,
        timeout: float,
    ) -> CommandResult:
        """Execute command via SSH."""
        host = self._config.host
        user = self._config.user or "root"
        port = self._config.port

        # Build SSH command
        ssh_opts = ["-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes"]
        if self._config.key_file:
            ssh_opts.extend(["-i", self._config.key_file])
        if port != 22:
            ssh_opts.extend(["-p", str(port)])

        ssh_opts_str = " ".join(ssh_opts)

        # Escape command for SSH
        escaped_cmd = command.replace("'", "'\"'\"'")
        ssh_cmd = f"ssh {ssh_opts_str} {user}@{host} '{escaped_cmd}'"

        return await self._local.execute(ssh_cmd, timeout=timeout)

    async def _execute_lume(
        self,
        command: str,
        shell: ShellType,
        timeout: float,
    ) -> CommandResult:
        """Execute command on Lume VM via SSH."""
        # Get VM IP address
        ip = await self._get_lume_ip()
        if not ip:
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=f"Could not get IP for Lume VM: {self._config.vm_name}",
            )

        # Use sshpass for password authentication
        password = self._config.password or "lume"
        escaped_cmd = command.replace("'", "'\"'\"'")

        # Check if sshpass is available
        if await self._local.which("sshpass"):
            ssh_cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no admin@{ip} '{escaped_cmd}'"
        else:
            # Fall back to expect-style or just warn
            logger.warning("sshpass not installed - Lume SSH may require manual authentication")
            ssh_cmd = f"ssh -o StrictHostKeyChecking=no admin@{ip} '{escaped_cmd}'"

        return await self._local.execute(ssh_cmd, timeout=timeout)

    async def execute_script(
        self,
        script: str,
        *,
        shell: ShellType = ShellType.AUTO,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> CommandResult:
        """Execute a multi-line script on remote machine.

        For Parallels, this copies the script to the VM and executes it.
        For SSH/Lume, this uses heredoc-style execution.
        """
        if shell == ShellType.AUTO:
            shell = self.default_shell

        # For simple cases, join lines with semicolons or &&
        lines = [line.strip() for line in script.strip().split("\n") if line.strip()]

        if self._platform == Platform.WINDOWS:
            joined = " && ".join(lines)
        else:
            joined = " && ".join(lines)

        return await self.execute(
            joined,
            shell=shell,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )

    async def which(self, program: str) -> str | None:
        """Find program location on remote machine."""
        if self._platform == Platform.WINDOWS:
            result = await self.execute(f"where {program}", shell=ShellType.CMD)
        else:
            result = await self.execute(f"which {program}")

        if result.success:
            return result.stdout.strip().split("\n")[0]
        return None

    async def get_env(self, name: str) -> str | None:
        """Get environment variable on remote machine."""
        if name in self._env:
            return self._env[name]

        if self._platform == Platform.WINDOWS:
            result = await self.execute(f"echo %{name}%", shell=ShellType.CMD)
        else:
            result = await self.execute(f"echo ${name}")

        if result.success:
            value = result.stdout.strip()
            # Check if it's empty or the literal variable name
            if value and value != f"%{name}%" and value != f"${name}":
                return value
        return None

    async def set_env(self, name: str, value: str) -> None:
        """Set environment variable for subsequent commands."""
        self._env[name] = value

    async def get_cwd(self) -> str:
        """Get current working directory on remote machine."""
        if self._cwd:
            return self._cwd

        if self._platform == Platform.WINDOWS:
            result = await self.execute("cd", shell=ShellType.CMD)
        else:
            result = await self.execute("pwd")

        return result.stdout.strip()

    async def set_cwd(self, path: str) -> None:
        """Set working directory for subsequent commands."""
        self._cwd = path

    async def is_available(self) -> bool:
        """Check if remote machine is reachable."""
        try:
            if self._config.remote_type == RemoteType.PARALLELS:
                result = await self._local.execute(
                    f'prlctl status "{self._config.vm_name}"',
                    timeout=5.0,
                )
                return "running" in result.stdout.lower()

            elif self._config.remote_type == RemoteType.LUME:
                result = await self._local.execute(
                    f"lume ls | grep {self._config.vm_name}",
                    timeout=5.0,
                )
                return "running" in result.stdout.lower()

            elif self._config.remote_type == RemoteType.SSH:
                result = await self._local.execute(
                    f"nc -z -w 2 {self._config.host} {self._config.port}",
                    timeout=5.0,
                )
                return result.success

            return False
        except Exception:
            return False

    # Convenience methods

    async def run(self, command: str, **kwargs: Any) -> str:
        """Execute command and return stdout (convenience method)."""
        result = await self.execute(command, **kwargs)
        result.raise_on_error()
        return result.stdout.strip()


# Factory functions


def get_remote_cli(
    remote_type: str,
    **kwargs: Any,
) -> RemoteCLIAdapter:
    """Factory function to create remote CLI adapter.

    Args:
        remote_type: One of "parallels", "ssh", "lume"
        **kwargs: Arguments for the specific adapter type

    Returns:
        RemoteCLIAdapter instance
    """
    if remote_type == "parallels":
        return RemoteCLIAdapter.for_parallels(**kwargs)
    elif remote_type == "ssh":
        return RemoteCLIAdapter.for_ssh(**kwargs)
    elif remote_type == "lume":
        return RemoteCLIAdapter.for_lume(**kwargs)
    else:
        raise ValueError(f"Unknown remote type: {remote_type}")
