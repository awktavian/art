"""Parallels VM Adapter (Tier 3: Multi-OS VMs).

Control Windows/Linux/macOS VMs via Parallels Desktop CLI (prlctl).
This tier provides full VM isolation with multi-OS support.

Requires:
- Parallels Desktop installed
- prlctl available in PATH

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
import shutil
import tempfile
from pathlib import Path

from .base import BaseVMAdapter
from .types import (
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

logger = logging.getLogger(__name__)

# Regex patterns for input validation
_VM_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\s\.]+$")
_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_\-/\\:\.\s]+$")
_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_vm_name(name: str) -> str:
    """Validate and return VM name.

    Args:
        name: VM name to validate

    Returns:
        Validated VM name

    Raises:
        ValueError: If name contains invalid characters
    """
    if not name or not _VM_NAME_PATTERN.match(name):
        raise ValueError(f"Invalid VM name: {name!r}")
    return name


def _validate_path(path: str) -> str:
    """Validate and return file path.

    Args:
        path: Path to validate

    Returns:
        Validated path

    Raises:
        ValueError: If path contains invalid characters
    """
    if not path or not _PATH_PATTERN.match(path):
        raise ValueError(f"Invalid path: {path!r}")
    return path


def _validate_key(key: str) -> str:
    """Validate and return key name.

    Args:
        key: Key name to validate

    Returns:
        Validated key name

    Raises:
        ValueError: If key contains invalid characters
    """
    if not key or not _KEY_PATTERN.match(key):
        raise ValueError(f"Invalid key: {key!r}")
    return key


def _validate_coordinates(x: int, y: int) -> tuple[int, int]:
    """Validate screen coordinates.

    Args:
        x: X coordinate
        y: Y coordinate

    Returns:
        Validated (x, y) tuple

    Raises:
        ValueError: If coordinates are out of reasonable range
    """
    if not (0 <= x <= 10000 and 0 <= y <= 10000):
        raise ValueError(f"Coordinates out of range: ({x}, {y})")
    return (x, y)


class ParallelsAdapter(BaseVMAdapter):
    """Tier 3 VM adapter using Parallels Desktop.

    This adapter provides control over Parallels VMs:

    - Full VM lifecycle (start, stop, suspend, snapshot)
    - Screenshot capture via guest tools
    - Mouse/keyboard control via cliclick/xdotool
    - Command execution via prlctl exec
    - File transfer between host and guest

    Security: Full VM isolation. Safe for untrusted operations.

    Usage:
        adapter = ParallelsAdapter("Windows-Agent")
        await adapter.initialize()

        # Start VM
        await adapter.start()

        # Take screenshot
        screenshot = await adapter.screenshot()

        # Execute command in VM
        result = await adapter.execute("dir C:\\")

        # Create snapshot
        await adapter.create_snapshot("clean-state")
    """

    def __init__(self, vm_name: str | None = None):
        """Initialize Parallels adapter.

        Args:
            vm_name: Name of VM to control (can be set in config)
        """
        super().__init__(tier=VMTier.MULTI_OS)
        self._vm_name = vm_name
        self._prlctl_path: str | None = None
        self._os_type: OSType = OSType.UNKNOWN

    async def initialize(self, config: VMConfig | None = None) -> bool:
        """Initialize Parallels adapter.

        Args:
            config: VM configuration

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        # Find prlctl
        self._prlctl_path = shutil.which("prlctl")
        if not self._prlctl_path:
            logger.error("prlctl not found. Is Parallels Desktop installed?")
            return False

        # Store config
        self._config = config or VMConfig(
            name=self._vm_name or "kagami-vm",
            os_type=OSType.MACOS,
            tier=VMTier.MULTI_OS,
        )
        self._vm_name = self._config.name

        # Verify VM exists
        if not await self._vm_exists():
            logger.error(f"VM '{self._vm_name}' not found in Parallels")
            return False

        # Detect OS type
        self._os_type = await self._detect_os_type()

        self._initialized = True
        logger.info(f"✅ Parallels adapter initialized for VM: {self._vm_name}")
        return True

    async def shutdown(self) -> None:
        """Shutdown adapter."""
        self._initialized = False
        logger.info(f"Parallels adapter shutdown: {self._vm_name}")

    async def _run_prlctl(
        self,
        args: list[str],
        timeout: float = 60.0,
    ) -> tuple[int, str, str]:
        """Run prlctl command.

        Args:
            args: prlctl arguments
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        proc = await asyncio.create_subprocess_exec(
            self._prlctl_path or "prlctl",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        return (
            proc.returncode or 0,
            stdout.decode() if stdout else "",
            stderr.decode() if stderr else "",
        )

    async def _vm_exists(self) -> bool:
        """Check if VM exists.

        Returns:
            True if VM exists
        """
        exit_code, stdout, _ = await self._run_prlctl(["list", "-a", "--json"])
        if exit_code != 0:
            return False

        try:
            vms = json.loads(stdout)
            return any(vm.get("name") == self._vm_name for vm in vms)
        except json.JSONDecodeError:
            return False

    async def _detect_os_type(self) -> OSType:
        """Detect VM operating system type.

        Returns:
            OSType enum
        """
        exit_code, stdout, _ = await self._run_prlctl(["list", "-i", self._vm_name, "--json"])
        if exit_code != 0:
            return OSType.UNKNOWN

        try:
            info = json.loads(stdout)
            if isinstance(info, list):
                info = info[0] if info else {}

            os_str = info.get("OS", "").lower()
            if "windows" in os_str:
                return OSType.WINDOWS
            elif "macos" in os_str or "mac" in os_str:
                return OSType.MACOS
            elif "linux" in os_str or "ubuntu" in os_str or "debian" in os_str:
                return OSType.LINUX
            else:
                return OSType.UNKNOWN
        except json.JSONDecodeError:
            return OSType.UNKNOWN

    async def _get_vm_state(self) -> VMState:
        """Get current VM state.

        Returns:
            VMState enum
        """
        exit_code, stdout, _ = await self._run_prlctl(["list", "-o", "status", self._vm_name])
        if exit_code != 0:
            return VMState.ERROR

        status = stdout.strip().lower()
        if "running" in status:
            return VMState.RUNNING
        elif "stopped" in status:
            return VMState.STOPPED
        elif "paused" in status:
            return VMState.PAUSED
        elif "suspended" in status:
            return VMState.SUSPENDED
        else:
            return VMState.STOPPED

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> bool:
        """Start the VM.

        Returns:
            True if started successfully
        """
        self._state = VMState.STARTING
        exit_code, _, stderr = await self._run_prlctl(["start", self._vm_name])
        if exit_code == 0:
            self._state = VMState.RUNNING
            logger.info(f"VM started: {self._vm_name}")
            return True
        else:
            logger.error(f"Failed to start VM: {stderr}")
            self._state = VMState.ERROR
            return False

    async def stop(self) -> bool:
        """Stop the VM.

        Returns:
            True if stopped successfully
        """
        self._state = VMState.STOPPING
        exit_code, _, stderr = await self._run_prlctl(["stop", self._vm_name])
        if exit_code == 0:
            self._state = VMState.STOPPED
            logger.info(f"VM stopped: {self._vm_name}")
            return True
        else:
            logger.error(f"Failed to stop VM: {stderr}")
            return False

    async def restart(self) -> bool:
        """Restart the VM.

        Returns:
            True if restarted
        """
        exit_code, _, _ = await self._run_prlctl(["restart", self._vm_name])
        if exit_code == 0:
            self._state = VMState.RUNNING
            return True
        return False

    async def get_status(self) -> VMStatus:
        """Get VM status.

        Returns:
            VMStatus with current state
        """
        state = await self._get_vm_state()
        self._state = state

        # Get VM info
        exit_code, stdout, _ = await self._run_prlctl(["list", "-i", self._vm_name, "--json"])

        cpu_count = 0
        memory_mb = 0
        if exit_code == 0:
            try:
                info = json.loads(stdout)
                if isinstance(info, list):
                    info = info[0] if info else {}
                cpu_count = int(info.get("cpu", {}).get("count", 0))
                memory_mb = int(info.get("memory", {}).get("size", 0))
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        snapshots = await self.list_snapshots()

        return VMStatus(
            name=self._vm_name or "unknown",
            state=state,
            os_type=self._os_type,
            tier=VMTier.MULTI_OS,
            cpu_count=cpu_count,
            memory_mb=memory_mb,
            snapshots=snapshots,
        )

    # =========================================================================
    # Screenshots
    # =========================================================================

    async def screenshot(self, retina: bool = True) -> bytes:
        """Capture VM screenshot.

        Uses guest tools to capture screen inside VM.

        Args:
            retina: Ignored for VMs

        Returns:
            PNG image data
        """
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            guest_path = (
                "/tmp/screenshot.png"
                if self._os_type != OSType.WINDOWS
                else "C:\\Temp\\screenshot.png"
            )

        try:
            # Capture screenshot inside VM
            # Note: guest_path is hardcoded above and safe, but we validate anyway
            _validate_path(guest_path)

            if self._os_type == OSType.WINDOWS:
                # Use PowerShell to capture - guest_path is hardcoded, safe
                # Using single quotes in PowerShell string to avoid injection
                cmd = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "[System.Windows.Forms.Screen]::PrimaryScreen | ForEach-Object { "
                    "$bitmap = New-Object System.Drawing.Bitmap($_.Bounds.Width, $_.Bounds.Height); "
                    "$graphics = [System.Drawing.Graphics]::FromImage($bitmap); "
                    "$graphics.CopyFromScreen($_.Bounds.Location, [System.Drawing.Point]::Empty, $_.Bounds.Size); "
                    f"$bitmap.Save('{guest_path}')"
                    " }"
                )
                await self._execute_in_vm(["powershell", "-Command", cmd])
            elif self._os_type == OSType.MACOS:
                await self._execute_in_vm(["screencapture", "-x", guest_path])
            else:  # Linux
                await self._execute_in_vm(["import", "-window", "root", guest_path])

            # Copy from VM to host
            await self.copy_from_vm(guest_path, temp_path)
            return Path(temp_path).read_bytes()

        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def get_display_info(self) -> VMDisplayInfo:
        """Get VM display info.

        Returns:
            VMDisplayInfo
        """
        # Get from VM config
        exit_code, stdout, _ = await self._run_prlctl(["list", "-i", self._vm_name, "--json"])

        width = 1920
        height = 1080
        if exit_code == 0:
            try:
                info = json.loads(stdout)
                if isinstance(info, list):
                    info = info[0] if info else {}
                video = info.get("video", {})
                width = int(video.get("width", 1920))
                height = int(video.get("height", 1080))
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        return VMDisplayInfo(
            width=width,
            height=height,
            scale_factor=1.0,  # VMs typically don't use Retina
        )

    # =========================================================================
    # Input Control
    # =========================================================================

    async def click(
        self,
        x: int,
        y: int,
        options: ClickOptions | None = None,
    ) -> None:
        """Click at coordinates in VM.

        Requires cliclick (macOS), xdotool (Linux), or nircmd (Windows) in VM.

        Args:
            x: X coordinate
            y: Y coordinate
            options: Click options
        """
        # Validate coordinates to prevent injection
        _validate_coordinates(x, y)
        opts = options or ClickOptions()

        if self._os_type == OSType.MACOS:
            # Use cliclick - coordinates are validated integers
            click_type = "dc" if opts.double_click else "c"
            if opts.button == "right":
                click_type = "rc"
            await self._execute_in_vm(["cliclick", f"{click_type}:{x},{y}"])

        elif self._os_type == OSType.LINUX:
            # Use xdotool - coordinates are validated integers
            if opts.double_click:
                await self._execute_in_vm(
                    ["xdotool", "mousemove", str(x), str(y), "click", "--repeat", "2", "1"]
                )
            else:
                button = {"left": "1", "right": "3", "middle": "2"}.get(opts.button, "1")
                await self._execute_in_vm(["xdotool", "mousemove", str(x), str(y), "click", button])

        elif self._os_type == OSType.WINDOWS:
            # Use PowerShell - coordinates are validated integers
            cmd = (
                "[System.Windows.Forms.Cursor]::Position = "
                f"New-Object System.Drawing.Point({x},{y}); "
                "[System.Windows.Forms.SendKeys]::SendWait(' ')"
            )
            await self._execute_in_vm(["powershell", "-Command", cmd])

    async def type_text(
        self,
        text: str,
        options: TypeOptions | None = None,
    ) -> None:
        """Type text in VM.

        Args:
            text: Text to type
            options: Typing options
        """
        if self._os_type == OSType.MACOS:
            # cliclick t: argument - use shlex for safe quoting
            # The t: prefix is cliclick's "type" command
            await self._execute_in_vm(["cliclick", f"t:{text}"])

        elif self._os_type == OSType.LINUX:
            # xdotool type handles its own argument safely via list
            await self._execute_in_vm(["xdotool", "type", "--", text])

        elif self._os_type == OSType.WINDOWS:
            # PowerShell SendKeys - escape single quotes for PS string
            # Replace ' with '' for PowerShell single-quoted strings
            escaped = text.replace("'", "''")
            cmd = f"[System.Windows.Forms.SendKeys]::SendWait('{escaped}')"
            await self._execute_in_vm(["powershell", "-Command", cmd])

    async def hotkey(self, *keys: str) -> None:
        """Execute keyboard shortcut in VM.

        Args:
            keys: Key names
        """
        if not keys:
            return

        # Validate all keys to prevent injection
        for key in keys:
            _validate_key(key)

        if self._os_type == OSType.MACOS:
            # Convert to cliclick format
            modifiers = []
            key = keys[-1]
            for k in keys[:-1]:
                if k.lower() in ("cmd", "command"):
                    modifiers.append("cmd")
                elif k.lower() in ("shift",):
                    modifiers.append("shift")
                elif k.lower() in ("alt", "option"):
                    modifiers.append("alt")
                elif k.lower() in ("ctrl", "control"):
                    modifiers.append("ctrl")

            mod_str = "+".join(modifiers) + "+" if modifiers else ""
            await self._execute_in_vm(["cliclick", f"kp:{mod_str}{key}"])

        elif self._os_type == OSType.LINUX:
            # xdotool format: xdotool key ctrl+c
            # Keys are validated, safe to join
            key_combo = "+".join(keys)
            await self._execute_in_vm(["xdotool", "key", key_combo])

        elif self._os_type == OSType.WINDOWS:
            # Convert to SendKeys format
            key_map = {
                "cmd": "^",  # Ctrl on Windows
                "ctrl": "^",
                "alt": "%",
                "shift": "+",
            }
            send_keys = ""
            for k in keys[:-1]:
                send_keys += key_map.get(k.lower(), "")
            send_keys += keys[-1]
            # Keys are validated, safe to use in command
            cmd = f"[System.Windows.Forms.SendKeys]::SendWait('{send_keys}')"
            await self._execute_in_vm(["powershell", "-Command", cmd])

    # =========================================================================
    # Snapshots
    # =========================================================================

    async def create_snapshot(self, name: str) -> bool:
        """Create VM snapshot.

        Args:
            name: Snapshot name

        Returns:
            True if created
        """
        exit_code, _, stderr = await self._run_prlctl(["snapshot", self._vm_name, "-n", name])
        if exit_code == 0:
            logger.info(f"Snapshot created: {name}")
            return True
        else:
            logger.error(f"Snapshot failed: {stderr}")
            return False

    async def restore_snapshot(self, name: str) -> bool:
        """Restore VM snapshot.

        Args:
            name: Snapshot name

        Returns:
            True if restored
        """
        exit_code, _, stderr = await self._run_prlctl(
            ["snapshot-switch", self._vm_name, "-n", name]
        )
        if exit_code == 0:
            logger.info(f"Snapshot restored: {name}")
            return True
        else:
            logger.error(f"Snapshot restore failed: {stderr}")
            return False

    async def list_snapshots(self) -> list[str]:
        """List VM snapshots.

        Returns:
            List of snapshot names
        """
        exit_code, stdout, _ = await self._run_prlctl(["snapshot-list", self._vm_name, "--json"])
        if exit_code != 0:
            return []

        try:
            data = json.loads(stdout)
            return [s.get("name", "") for s in data.get("snapshots", [])]
        except json.JSONDecodeError:
            return []

    async def delete_snapshot(self, name: str) -> bool:
        """Delete VM snapshot.

        Args:
            name: Snapshot name

        Returns:
            True if deleted
        """
        exit_code, _, _ = await self._run_prlctl(["snapshot-delete", self._vm_name, "-n", name])
        return exit_code == 0

    # =========================================================================
    # File Transfer
    # =========================================================================

    async def copy_to_vm(self, local_path: str, remote_path: str) -> bool:
        """Copy file to VM.

        Args:
            local_path: Host path
            remote_path: VM path

        Returns:
            True if copied
        """
        # Use prlctl copy
        exit_code, _, stderr = await self._run_prlctl(
            ["copy", self._vm_name, local_path, remote_path],
            timeout=120.0,
        )
        if exit_code != 0:
            logger.error(f"Copy to VM failed: {stderr}")
            return False
        return True

    async def copy_from_vm(self, remote_path: str, local_path: str) -> bool:
        """Copy file from VM.

        Args:
            remote_path: VM path
            local_path: Host path

        Returns:
            True if copied
        """
        # Use prlctl exec to cat the file
        if self._os_type == OSType.WINDOWS:
            result = await self.execute(f'type "{remote_path}"')
        else:
            result = await self.execute(f'cat "{remote_path}"')

        if result.exit_code == 0:
            Path(local_path).write_text(result.stdout)
            return True
        return False

    # =========================================================================
    # Command Execution
    # =========================================================================

    async def _execute_in_vm(
        self,
        args: list[str],
        timeout_ms: int = 30000,
    ) -> CommandResult:
        """Execute command in VM with list arguments (safe from injection).

        This is the preferred method for internal use as it passes arguments
        as a list, avoiding shell injection vulnerabilities.

        Args:
            args: Command and arguments as list
            timeout_ms: Timeout in milliseconds

        Returns:
            CommandResult with exit code and output
        """
        import time

        start = time.time()
        # Build safe command by joining with proper quoting for the target OS
        if self._os_type == OSType.WINDOWS:
            # Windows: use subprocess list directly via prlctl exec
            # prlctl exec passes args to the guest shell
            command = " ".join(args)  # Windows handles this via prlctl
        else:
            # Unix: use shlex.join for proper quoting
            command = shlex.join(args)

        exit_code, stdout, stderr = await self._run_prlctl(
            ["exec", self._vm_name, command],
            timeout=timeout_ms / 1000,
        )
        duration = (time.time() - start) * 1000

        return CommandResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration,
        )

    async def execute(
        self,
        command: str,
        timeout_ms: int = 30000,
    ) -> CommandResult:
        """Execute command in VM.

        WARNING: This method passes the command string directly to the VM shell.
        Use _execute_in_vm with a list of arguments for internal calls to avoid
        command injection. This method is kept for backward compatibility with
        user-provided commands.

        Args:
            command: Shell command
            timeout_ms: Timeout in milliseconds

        Returns:
            CommandResult with exit code and output
        """
        import time

        start = time.time()
        exit_code, stdout, stderr = await self._run_prlctl(
            ["exec", self._vm_name, command],
            timeout=timeout_ms / 1000,
        )
        duration = (time.time() - start) * 1000

        return CommandResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration,
        )


__all__ = ["ParallelsAdapter"]
