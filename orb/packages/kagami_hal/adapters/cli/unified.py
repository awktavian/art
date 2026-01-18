"""Unified CLI — Single Entry Point for All Command Execution.

Provides a unified interface for executing commands across:
- Local host (macOS, Linux, Windows)
- Parallels VMs
- Lume VMs
- SSH connections

This is the canonical entry point for all shell operations in Kagami.

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .local import LocalCLIAdapter
from .protocol import (
    CLIAdapterProtocol,
    CommandResult,
    Platform,
    ShellType,
)
from .remote import RemoteCLIAdapter

logger = logging.getLogger(__name__)


class ExecutionTarget(Enum):
    """Where to execute the command."""

    LOCAL = "local"  # Host machine
    PARALLELS = "parallels"  # Parallels VM
    LUME = "lume"  # Lume macOS VM
    SSH = "ssh"  # Remote SSH


@dataclass
class TargetConfig:
    """Configuration for execution target."""

    target: ExecutionTarget = ExecutionTarget.LOCAL

    # For Parallels
    vm_name: str | None = None

    # For SSH
    host: str | None = None
    port: int = 22
    user: str | None = None
    key_file: str | None = None

    # Platform hint
    platform: Platform = Platform.AUTO


class UnifiedCLI:
    """Unified command-line interface for all targets.

    Features:
    - Auto-routing based on target specification
    - Cross-platform command translation
    - Environment and working directory management
    - Connection pooling and caching

    Usage:
        cli = UnifiedCLI()

        # Local execution (default)
        result = await cli.execute("ls -la")

        # Parallels VM
        result = await cli.execute("dir C:\\", target="parallels", vm_name="Gaming")

        # Lume VM
        result = await cli.execute("ls -la", target="lume")

        # SSH
        result = await cli.execute("ls", target="ssh", host="192.168.1.100", user="admin")
    """

    def __init__(self) -> None:
        """Initialize unified CLI."""
        self._local = get_local_cli()
        self._remote_cache: dict[str, RemoteCLIAdapter] = {}

        # Default targets for convenience
        self._default_parallels_vm = "Gaming"
        self._default_lume_vm = "macos-sequoia-cua_latest"

    def _get_cache_key(self, config: TargetConfig) -> str:
        """Generate cache key for remote adapter."""
        if config.target == ExecutionTarget.PARALLELS:
            return f"parallels:{config.vm_name}"
        elif config.target == ExecutionTarget.LUME:
            return f"lume:{config.vm_name}"
        elif config.target == ExecutionTarget.SSH:
            return f"ssh:{config.user}@{config.host}:{config.port}"
        return "local"

    def _get_adapter(self, config: TargetConfig) -> CLIAdapterProtocol:
        """Get or create adapter for target."""
        if config.target == ExecutionTarget.LOCAL:
            return self._local

        cache_key = self._get_cache_key(config)

        if cache_key not in self._remote_cache:
            if config.target == ExecutionTarget.PARALLELS:
                self._remote_cache[cache_key] = RemoteCLIAdapter.for_parallels(
                    vm_name=config.vm_name or self._default_parallels_vm,
                    platform=config.platform,
                )
            elif config.target == ExecutionTarget.LUME:
                self._remote_cache[cache_key] = RemoteCLIAdapter.for_lume(
                    vm_name=config.vm_name or self._default_lume_vm,
                )
            elif config.target == ExecutionTarget.SSH:
                if not config.host:
                    raise ValueError("SSH target requires host")
                self._remote_cache[cache_key] = RemoteCLIAdapter.for_ssh(
                    host=config.host,
                    port=config.port,
                    user=config.user or "root",
                    key_file=config.key_file,
                    platform=config.platform,
                )

        return self._remote_cache[cache_key]

    def _parse_target(
        self,
        target: str | ExecutionTarget | None,
        **kwargs: Any,
    ) -> TargetConfig:
        """Parse target specification into config."""
        if target is None:
            target = ExecutionTarget.LOCAL
        elif isinstance(target, str):
            target = ExecutionTarget(target.lower())

        return TargetConfig(
            target=target,
            vm_name=kwargs.get("vm_name"),
            host=kwargs.get("host"),
            port=kwargs.get("port", 22),
            user=kwargs.get("user"),
            key_file=kwargs.get("key_file"),
            platform=kwargs.get("platform", Platform.AUTO),
        )

    async def execute(
        self,
        command: str,
        *,
        target: str | ExecutionTarget | None = None,
        shell: ShellType = ShellType.AUTO,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
        capture_output: bool = True,
        # Target-specific options
        vm_name: str | None = None,
        host: str | None = None,
        port: int = 22,
        user: str | None = None,
        key_file: str | None = None,
        platform: Platform = Platform.AUTO,
    ) -> CommandResult:
        """Execute command on specified target.

        Args:
            command: Command to execute
            target: Where to execute (local, parallels, lume, ssh)
            shell: Shell to use
            cwd: Working directory
            env: Environment variables
            timeout: Timeout in seconds
            capture_output: Whether to capture output
            vm_name: VM name (for parallels/lume)
            host: SSH host
            port: SSH port
            user: SSH user
            key_file: SSH key file
            platform: Target platform hint

        Returns:
            CommandResult with exit code and output
        """
        config = self._parse_target(
            target,
            vm_name=vm_name,
            host=host,
            port=port,
            user=user,
            key_file=key_file,
            platform=platform,
        )

        adapter = self._get_adapter(config)

        return await adapter.execute(
            command,
            shell=shell,
            cwd=cwd,
            env=env,
            timeout=timeout,
            capture_output=capture_output,
        )

    async def execute_script(
        self,
        script: str,
        *,
        target: str | ExecutionTarget | None = None,
        shell: ShellType = ShellType.AUTO,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute multi-line script on target."""
        config = self._parse_target(target, **kwargs)
        adapter = self._get_adapter(config)

        return await adapter.execute_script(
            script,
            shell=shell,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )

    async def run(
        self,
        command: str,
        *,
        target: str | ExecutionTarget | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute command and return stdout.

        Raises RuntimeError on non-zero exit code.
        """
        result = await self.execute(command, target=target, **kwargs)
        result.raise_on_error()
        return result.stdout.strip()

    async def which(
        self,
        program: str,
        target: str | ExecutionTarget | None = None,
        **kwargs: Any,
    ) -> str | None:
        """Find program location on target."""
        config = self._parse_target(target, **kwargs)
        adapter = self._get_adapter(config)
        return await adapter.which(program)

    async def is_available(
        self,
        target: str | ExecutionTarget | None = None,
        **kwargs: Any,
    ) -> bool:
        """Check if target is available."""
        config = self._parse_target(target, **kwargs)
        adapter = self._get_adapter(config)
        return await adapter.is_available()

    # Convenience methods for common targets

    @property
    def local(self) -> LocalCLIAdapter:
        """Get local CLI adapter."""
        return self._local

    async def local_run(self, command: str, **kwargs: Any) -> str:
        """Run command locally."""
        return await self.run(command, target=ExecutionTarget.LOCAL, **kwargs)

    async def parallels_run(
        self,
        command: str,
        vm_name: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Run command on Parallels VM."""
        return await self.run(
            command,
            target=ExecutionTarget.PARALLELS,
            vm_name=vm_name or self._default_parallels_vm,
            **kwargs,
        )

    async def lume_run(
        self,
        command: str,
        vm_name: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Run command on Lume VM."""
        return await self.run(
            command,
            target=ExecutionTarget.LUME,
            vm_name=vm_name or self._default_lume_vm,
            **kwargs,
        )

    async def ssh_run(
        self,
        command: str,
        host: str,
        user: str = "root",
        **kwargs: Any,
    ) -> str:
        """Run command via SSH."""
        return await self.run(
            command,
            target=ExecutionTarget.SSH,
            host=host,
            user=user,
            **kwargs,
        )

    # Cross-platform utilities

    async def get_os_info(
        self,
        target: str | ExecutionTarget | None = None,
        **kwargs: Any,
    ) -> dict[str, str]:
        """Get OS information from target.

        Returns:
            Dict with keys: os, version, arch, hostname
        """
        config = self._parse_target(target, **kwargs)
        adapter = self._get_adapter(config)
        platform = adapter.platform

        if platform == Platform.WINDOWS:
            result = await self.execute(
                'systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"',
                target=target,
                shell=ShellType.CMD,
                **kwargs,
            )
            hostname = await self.run("hostname", target=target, shell=ShellType.CMD, **kwargs)
            return {
                "os": "windows",
                "version": result.stdout.strip(),
                "arch": "x86_64" if "x64" in result.stdout else "x86",
                "hostname": hostname,
            }
        else:
            uname = await self.run("uname -a", target=target, **kwargs)
            hostname = await self.run("hostname", target=target, **kwargs)
            os_release = await self.execute(
                "cat /etc/os-release 2>/dev/null || sw_vers", target=target, **kwargs
            )

            return {
                "os": "macos" if "Darwin" in uname else "linux",
                "version": uname,
                "arch": "arm64" if "arm64" in uname or "aarch64" in uname else "x86_64",
                "hostname": hostname,
                "release": os_release.stdout.strip() if os_release.success else "",
            }

    async def list_files(
        self,
        path: str = ".",
        target: str | ExecutionTarget | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """List files in directory on target."""
        config = self._parse_target(target, **kwargs)
        adapter = self._get_adapter(config)

        if adapter.platform == Platform.WINDOWS:
            result = await self.execute(
                f'dir /b "{path}"',
                target=target,
                shell=ShellType.CMD,
                **kwargs,
            )
        else:
            result = await self.execute(f'ls -1 "{path}"', target=target, **kwargs)

        if result.success:
            return [f for f in result.stdout.strip().split("\n") if f]
        return []

    async def read_file(
        self,
        path: str,
        target: str | ExecutionTarget | None = None,
        **kwargs: Any,
    ) -> str:
        """Read file contents from target."""
        config = self._parse_target(target, **kwargs)
        adapter = self._get_adapter(config)

        if adapter.platform == Platform.WINDOWS:
            return await self.run(f'type "{path}"', target=target, shell=ShellType.CMD, **kwargs)
        else:
            return await self.run(f'cat "{path}"', target=target, **kwargs)

    async def write_file(
        self,
        path: str,
        content: str,
        target: str | ExecutionTarget | None = None,
        **kwargs: Any,
    ) -> bool:
        """Write content to file on target."""
        config = self._parse_target(target, **kwargs)
        adapter = self._get_adapter(config)

        # Escape content for shell
        escaped = content.replace("\\", "\\\\").replace("'", "'\"'\"'")

        if adapter.platform == Platform.WINDOWS:
            # Use PowerShell for reliable file writing
            ps_content = content.replace("'", "''")
            result = await self.execute(
                f"Set-Content -Path '{path}' -Value '{ps_content}'",
                target=target,
                shell=ShellType.POWERSHELL,
                **kwargs,
            )
        else:
            result = await self.execute(
                f"printf '%s' '{escaped}' > '{path}'",
                target=target,
                **kwargs,
            )

        return result.success

    async def file_exists(
        self,
        path: str,
        target: str | ExecutionTarget | None = None,
        **kwargs: Any,
    ) -> bool:
        """Check if file exists on target."""
        config = self._parse_target(target, **kwargs)
        adapter = self._get_adapter(config)

        if adapter.platform == Platform.WINDOWS:
            result = await self.execute(
                f'if exist "{path}" (echo exists)',
                target=target,
                shell=ShellType.CMD,
                **kwargs,
            )
            return "exists" in result.stdout
        else:
            result = await self.execute(f'test -e "{path}" && echo exists', target=target, **kwargs)
            return "exists" in result.stdout


# Singleton
_unified_cli: UnifiedCLI | None = None


def get_unified_cli() -> UnifiedCLI:
    """Get or create unified CLI singleton."""
    global _unified_cli
    if _unified_cli is None:
        _unified_cli = UnifiedCLI()
    return _unified_cli


# Re-export convenience functions
_local_cli_singleton: LocalCLIAdapter | None = None


def get_local_cli() -> LocalCLIAdapter:
    """Get local CLI adapter singleton."""
    global _local_cli_singleton
    if _local_cli_singleton is None:
        from .local import LocalCLIAdapter

        _local_cli_singleton = LocalCLIAdapter()
    return _local_cli_singleton


def get_remote_cli(
    remote_type: str,
    **kwargs: Any,
) -> RemoteCLIAdapter:
    """Get remote CLI adapter."""
    from .remote import get_remote_cli as _get_remote_cli

    return _get_remote_cli(remote_type, **kwargs)
