"""CUA/Lume VM Adapter (Tier 2: Sandboxed macOS VMs).

Control isolated macOS VMs via CUA (Computer Use Agent) and Lume CLI.
This tier provides full VM isolation with 97% native performance on Apple Silicon.

Features:
- 97% native performance on Apple Silicon
- Full VM isolation for untrusted operations
- SSH-based command execution (no CUA dependencies required)
- Screenshot capture via screencapture
- File transfer via SCP
- Snapshot management

Requires:
- Lume CLI installed (`brew install trycua/tap/lume`)
- macOS CUA image pulled (`lume pull macos-sequoia-cua:latest`)
- Optional: Python cua-computer and cua-agent libraries for native control

Created: December 30, 2025
Updated: January 4, 2026 - Added SSH-based execution
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Default SSH credentials for Lume VMs
LUME_SSH_USER = "lume"
LUME_SSH_PASSWORD = "lume"

# SSH ControlMaster socket path for connection reuse
SSH_CONTROL_DIR = Path.home() / ".kagami" / "ssh_control"


class CUALumeAdapter(BaseVMAdapter):
    """Tier 2 VM adapter using CUA/Lume for sandboxed macOS VMs.

    This adapter provides control over macOS VMs running via Lume:

    - 97% native performance on Apple Silicon
    - Full VM isolation for untrusted operations
    - Screenshot capture
    - Mouse/keyboard control
    - Native CUA agent integration

    Security: Full VM isolation. Safe for untrusted operations.

    Note: This adapter requires Lume CLI and cua libraries to be installed.
    If not available, it provides a stub implementation.

    Usage:
        adapter = CUALumeAdapter()
        await adapter.initialize()

        # Start VM
        await adapter.start()

        # Take screenshot
        screenshot = await adapter.screenshot()

        # Click at coordinates
        await adapter.click(100, 200)

        # Create snapshot
        await adapter.create_snapshot("clean-state")
    """

    def __init__(
        self,
        vm_name: str = "macos-sequoia-cua_latest",
        ssh_user: str = LUME_SSH_USER,
        ssh_password: str = LUME_SSH_PASSWORD,
    ):
        """Initialize CUA/Lume adapter.

        Args:
            vm_name: Name of Lume VM image
            ssh_user: SSH username (default: lume)
            ssh_password: SSH password (default: lume)
        """
        super().__init__(tier=VMTier.SANDBOXED)
        self._vm_name = vm_name
        self._lume_path: str | None = None
        self._sshpass_path: str | None = None
        self._computer: Any = None  # CUA Computer instance
        self._cua_available = False
        self._ssh_user = ssh_user
        self._ssh_password = ssh_password
        self._vm_ip: str | None = None
        self._vnc_url: str | None = None
        self._ssh_control_path: Path | None = None
        self._ssh_master_proc: asyncio.subprocess.Process | None = None

    async def initialize(self, config: VMConfig | None = None) -> bool:
        """Initialize CUA/Lume adapter.

        Args:
            config: VM configuration

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        # Find lume CLI
        self._lume_path = shutil.which("lume")
        if not self._lume_path:
            logger.warning("Lume CLI not found. Install via: brew install trycua/tap/lume")
            # Continue with stub mode

        # Find sshpass for SSH automation
        self._sshpass_path = shutil.which("sshpass")
        if not self._sshpass_path:
            logger.warning(
                "sshpass not found. Install via: brew install hudochenkov/sshpass/sshpass"
            )

        # Check for CUA Python libraries
        try:
            from computer import Computer  # type: ignore

            self._cua_available = True
            logger.info("CUA libraries available")
        except ImportError:
            logger.info("CUA libraries not installed - using SSH fallback (fully functional)")
            self._cua_available = False

        # Store config
        self._config = config or VMConfig(
            name=self._vm_name,
            os_type=OSType.MACOS,
            tier=VMTier.SANDBOXED,
        )

        # Get VM info if already running
        await self._refresh_vm_info()

        self._initialized = True
        logger.info(
            f"✅ CUA/Lume adapter initialized (lume={self._lume_path is not None}, "
            f"sshpass={self._sshpass_path is not None}, cua={self._cua_available})"
        )
        return True

    async def _refresh_vm_info(self) -> None:
        """Refresh VM IP and VNC info from lume ls."""
        if not self._lume_path:
            return

        exit_code, stdout, _ = await self._run_lume(["ls"])
        if exit_code != 0:
            return

        # Parse lume ls output for our VM
        for line in stdout.split("\n"):
            if self._vm_name in line:
                # Extract IP address (format: 192.168.64.X)
                ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                if ip_match:
                    self._vm_ip = ip_match.group(1)
                    logger.info(f"VM IP: {self._vm_ip}")

                # Extract VNC URL
                vnc_match = re.search(r"(vnc://[^\s]+)", line)
                if vnc_match:
                    self._vnc_url = vnc_match.group(1)
                    logger.debug(f"VNC URL: {self._vnc_url}")

                # Check status
                if "running" in line.lower():
                    self._state = VMState.RUNNING
                elif "stopped" in line.lower():
                    self._state = VMState.STOPPED
                break

    async def shutdown(self) -> None:
        """Shutdown adapter and stop VM."""
        # Teardown SSH multiplexing first
        await self._teardown_ssh_multiplexing()

        if self._computer:
            try:
                await self._computer.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing CUA computer: {e}")
            self._computer = None

        self._initialized = False
        self._state = VMState.STOPPED
        logger.info("CUA/Lume adapter shutdown")

    async def _run_lume(
        self,
        args: list[str],
        timeout: float = 60.0,
    ) -> tuple[int, str, str]:
        """Run lume CLI command.

        Args:
            args: Lume arguments
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self._lume_path:
            return (-1, "", "Lume not installed")

        proc = await asyncio.create_subprocess_exec(
            self._lume_path,
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

    async def _setup_ssh_multiplexing(self) -> bool:
        """Setup SSH ControlMaster for connection reuse.

        Creates a persistent SSH connection that subsequent commands can reuse,
        eliminating connection setup overhead (~200ms per command → ~10ms).

        Returns:
            True if multiplexing is ready
        """
        if not self._vm_ip or not self._sshpass_path:
            return False

        # Create control socket directory
        SSH_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
        self._ssh_control_path = SSH_CONTROL_DIR / f"vm_{self._vm_name}_{self._vm_ip}"

        # Check if master already running
        if self._ssh_control_path.exists():
            # Test if it's still alive
            test_cmd = [
                "ssh",
                "-O",
                "check",
                "-o",
                f"ControlPath={self._ssh_control_path}",
                f"{self._ssh_user}@{self._vm_ip}",
            ]
            proc = await asyncio.create_subprocess_exec(
                *test_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            if proc.returncode == 0:
                logger.debug(f"SSH multiplexing already active: {self._ssh_control_path}")
                return True

        # Start ControlMaster (persistent background connection)
        master_cmd = [
            self._sshpass_path,
            "-p",
            self._ssh_password,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            "-o",
            "ControlMaster=yes",
            "-o",
            f"ControlPath={self._ssh_control_path}",
            "-o",
            "ControlPersist=600",  # Keep alive for 10 minutes
            "-N",  # No command, just establish connection
            f"{self._ssh_user}@{self._vm_ip}",
        ]

        self._ssh_master_proc = await asyncio.create_subprocess_exec(
            *master_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait briefly for connection to establish
        await asyncio.sleep(0.5)

        if self._ssh_master_proc.returncode is not None:
            logger.warning("SSH ControlMaster failed to start")
            return False

        logger.info(f"✅ SSH multiplexing active: {self._ssh_control_path}")
        return True

    async def _teardown_ssh_multiplexing(self) -> None:
        """Teardown SSH ControlMaster connection."""
        if self._ssh_control_path and self._ssh_control_path.exists():
            try:
                # Send exit command to ControlMaster
                exit_cmd = [
                    "ssh",
                    "-O",
                    "exit",
                    "-o",
                    f"ControlPath={self._ssh_control_path}",
                    f"{self._ssh_user}@{self._vm_ip}",
                ]
                proc = await asyncio.create_subprocess_exec(
                    *exit_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except Exception as e:
                logger.debug(f"SSH ControlMaster exit: {e}")

        if self._ssh_master_proc:
            try:
                self._ssh_master_proc.terminate()
                await asyncio.wait_for(self._ssh_master_proc.wait(), timeout=2.0)
            except Exception:
                self._ssh_master_proc.kill()
            self._ssh_master_proc = None

    async def _run_ssh(
        self,
        command: str,
        timeout: float = 30.0,
    ) -> tuple[int, str, str]:
        """Run command in VM via SSH.

        Uses ControlMaster multiplexing when available for ~20x faster
        connection setup (200ms → 10ms per command).

        Args:
            command: Shell command to execute
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self._vm_ip:
            await self._refresh_vm_info()
            if not self._vm_ip:
                return (-1, "", "VM IP not available - is VM running?")

        if not self._sshpass_path:
            return (-1, "", "sshpass not installed")

        # Build SSH command - use ControlPath if available for connection reuse
        ssh_args = [
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            "-o",
            f"ConnectTimeout={int(timeout)}",
        ]

        # Use multiplexed connection if available (much faster)
        if self._ssh_control_path and self._ssh_control_path.exists():
            ssh_args.extend(
                [
                    "-o",
                    f"ControlPath={self._ssh_control_path}",
                ]
            )
            # No sshpass needed - reusing authenticated connection
            ssh_cmd = [
                "ssh",
                *ssh_args,
                f"{self._ssh_user}@{self._vm_ip}",
                command,
            ]
        else:
            # Fall back to sshpass (slower, new connection each time)
            ssh_cmd = [
                self._sshpass_path,
                "-p",
                self._ssh_password,
                "ssh",
                *ssh_args,
                f"{self._ssh_user}@{self._vm_ip}",
                command,
            ]

        proc = await asyncio.create_subprocess_exec(
            *ssh_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            return (
                proc.returncode or 0,
                stdout.decode() if stdout else "",
                stderr.decode() if stderr else "",
            )
        except TimeoutError:
            proc.kill()
            return (-1, "", f"SSH command timed out after {timeout}s")

    async def _run_scp_to(
        self,
        local_path: str,
        remote_path: str,
        timeout: float = 60.0,
    ) -> bool:
        """Copy file to VM via SCP.

        Args:
            local_path: Local file path
            remote_path: Path in VM
            timeout: Timeout in seconds

        Returns:
            True if copy succeeded
        """
        if not self._vm_ip or not self._sshpass_path:
            return False

        scp_cmd = [
            self._sshpass_path,
            "-p",
            self._ssh_password,
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            local_path,
            f"{self._ssh_user}@{self._vm_ip}:{remote_path}",
        ]

        proc = await asyncio.create_subprocess_exec(
            *scp_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode == 0
        except TimeoutError:
            proc.kill()
            return False

    async def _run_scp_from(
        self,
        remote_path: str,
        local_path: str,
        timeout: float = 60.0,
    ) -> bool:
        """Copy file from VM via SCP.

        Args:
            remote_path: Path in VM
            local_path: Local file path
            timeout: Timeout in seconds

        Returns:
            True if copy succeeded
        """
        if not self._vm_ip or not self._sshpass_path:
            return False

        scp_cmd = [
            self._sshpass_path,
            "-p",
            self._ssh_password,
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            f"{self._ssh_user}@{self._vm_ip}:{remote_path}",
            local_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *scp_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode == 0
        except TimeoutError:
            proc.kill()
            return False

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(
        self,
        headless: bool = False,
        wait_for_ssh: bool = True,
        ssh_timeout: float = 60.0,
    ) -> bool:
        """Start the CUA VM.

        Args:
            headless: Run without display (--no-display)
            wait_for_ssh: Wait for SSH to become available
            ssh_timeout: Timeout waiting for SSH

        Returns:
            True if started successfully
        """
        # Check if already running
        await self._refresh_vm_info()
        if self._state == VMState.RUNNING:
            logger.info(f"VM already running: {self._vm_name}")
            if wait_for_ssh:
                return await self._wait_for_ssh(timeout=ssh_timeout)
            return True

        self._state = VMState.STARTING

        if self._cua_available:
            try:
                from computer import Computer  # type: ignore

                self._computer = Computer(
                    os_type="macos",
                    display=f"{self._config.display_width}x{self._config.display_height}"
                    if self._config
                    else "1920x1080",
                )
                await self._computer.__aenter__()
                self._state = VMState.RUNNING
                logger.info(f"CUA VM started: {self._vm_name}")
                return True
            except Exception as e:
                logger.warning(f"CUA start failed, trying lume CLI: {e}")
                # Fall through to lume CLI

        if self._lume_path:
            # Build lume run command
            lume_args = ["run", self._vm_name]
            if headless:
                lume_args.append("--no-display")

            # Start VM in background (lume run blocks)
            proc = await asyncio.create_subprocess_exec(
                self._lume_path,
                *lume_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait briefly for VM to start initializing
            await asyncio.sleep(2)

            # Check if process is still running (good) or exited with error
            if proc.returncode is not None and proc.returncode != 0:
                _, stderr = await proc.communicate()
                logger.error(f"Failed to start Lume VM: {stderr.decode()}")
                self._state = VMState.ERROR
                return False

            # Refresh to get IP
            for _ in range(10):
                await asyncio.sleep(2)
                await self._refresh_vm_info()
                if self._vm_ip:
                    break

            if not self._vm_ip:
                logger.error("VM started but no IP assigned")
                self._state = VMState.ERROR
                return False

            self._state = VMState.RUNNING
            logger.info(f"Lume VM started: {self._vm_name} (IP: {self._vm_ip})")

            if wait_for_ssh:
                return await self._wait_for_ssh(timeout=ssh_timeout)
            return True
        else:
            logger.error("Neither CUA nor Lume available")
            self._state = VMState.ERROR
            return False

    async def _wait_for_ssh(self, timeout: float = 60.0) -> bool:
        """Wait for SSH to become available and setup connection multiplexing.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if SSH is available
        """
        if not self._vm_ip:
            return False

        logger.info(f"Waiting for SSH on {self._vm_ip}...")
        start = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start) < timeout:
            exit_code, stdout, _ = await self._run_ssh("echo OK", timeout=5.0)
            if exit_code == 0 and "OK" in stdout:
                logger.info(f"✅ SSH ready on {self._vm_ip}")
                # Setup connection multiplexing for faster subsequent commands
                await self._setup_ssh_multiplexing()
                return True
            await asyncio.sleep(2)

        logger.warning(f"SSH not available after {timeout}s")
        return False

    async def stop(self) -> bool:
        """Stop the CUA VM.

        Returns:
            True if stopped successfully
        """
        self._state = VMState.STOPPING

        if self._computer:
            try:
                await self._computer.__aexit__(None, None, None)
                self._computer = None
            except Exception as e:
                logger.warning(f"Error stopping CUA computer: {e}")

        if self._lume_path:
            await self._run_lume(["stop", self._vm_name])

        self._state = VMState.STOPPED
        logger.info(f"VM stopped: {self._vm_name}")
        return True

    async def get_status(self) -> VMStatus:
        """Get VM status.

        Returns:
            VMStatus
        """
        # Check if running via lume
        if self._lume_path:
            exit_code, stdout, _ = await self._run_lume(["list", "--json"])
            if exit_code == 0:
                try:
                    import json

                    vms = json.loads(stdout)
                    for vm in vms:
                        if self._vm_name in vm.get("name", ""):
                            status = vm.get("status", "").lower()
                            if "running" in status:
                                self._state = VMState.RUNNING
                            elif "stopped" in status:
                                self._state = VMState.STOPPED
                except Exception:
                    pass

        return VMStatus(
            name=self._vm_name,
            state=self._state,
            os_type=OSType.MACOS,
            tier=VMTier.SANDBOXED,
            display=VMDisplayInfo(
                width=self._config.display_width if self._config else 1920,
                height=self._config.display_height if self._config else 1080,
            ),
            memory_mb=self._config.memory_mb if self._config else 8192,
            cpu_count=self._config.cpu_count if self._config else 4,
        )

    # =========================================================================
    # Screenshots
    # =========================================================================

    async def screenshot(self, retina: bool = True) -> bytes:
        """Capture VM screenshot.

        Args:
            retina: Capture at retina resolution

        Returns:
            PNG image data
        """
        if self._computer and hasattr(self._computer, "screenshot"):
            try:
                return await self._computer.screenshot()
            except Exception as e:
                logger.warning(f"CUA screenshot failed, using SSH: {e}")

        # SSH method: execute screencapture in VM and copy back
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name

        try:
            # Capture screenshot in VM
            result = await self.execute("screencapture -x /tmp/kagami_screenshot.png")
            if result.exit_code != 0:
                raise RuntimeError(f"Screenshot capture failed: {result.stderr}")

            # Copy from VM
            success = await self.copy_from_vm("/tmp/kagami_screenshot.png", temp_path)
            if not success:
                raise RuntimeError("Failed to copy screenshot from VM")

            # Clean up in VM
            await self.execute("rm -f /tmp/kagami_screenshot.png")

            return Path(temp_path).read_bytes()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def get_display_info(self) -> VMDisplayInfo:
        """Get VM display info.

        Returns:
            VMDisplayInfo
        """
        return VMDisplayInfo(
            width=self._config.display_width if self._config else 1920,
            height=self._config.display_height if self._config else 1080,
            scale_factor=2.0 if True else 1.0,  # CUA VMs typically use Retina
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

        Args:
            x: X coordinate
            y: Y coordinate
            options: Click options
        """
        opts = options or ClickOptions()

        if self._computer and hasattr(self._computer, "click"):
            try:
                await self._computer.click(x, y)
                return
            except Exception as e:
                logger.warning(f"CUA click failed: {e}")

        # Fallback: use cliclick inside VM
        click_type = "dc" if opts.double_click else "c"
        if opts.button == "right":
            click_type = "rc"
        await self.execute(f"cliclick {click_type}:{x},{y}")

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
        if self._computer and hasattr(self._computer, "type"):
            try:
                await self._computer.type(text)
                return
            except Exception as e:
                logger.warning(f"CUA type failed: {e}")

        # Fallback: use cliclick
        escaped = text.replace("'", "'\\''")
        await self.execute(f"cliclick t:'{escaped}'")

    async def hotkey(self, *keys: str) -> None:
        """Execute keyboard shortcut in VM.

        Args:
            keys: Key names
        """
        if not keys:
            return

        if self._computer and hasattr(self._computer, "hotkey"):
            try:
                await self._computer.hotkey(*keys)
                return
            except Exception as e:
                logger.warning(f"CUA hotkey failed: {e}")

        # Fallback: use cliclick
        modifiers = []
        key = keys[-1]
        for k in keys[:-1]:
            if k.lower() in ("cmd", "command"):
                modifiers.append("cmd")
            elif k.lower() == "shift":
                modifiers.append("shift")
            elif k.lower() in ("alt", "option"):
                modifiers.append("alt")
            elif k.lower() in ("ctrl", "control"):
                modifiers.append("ctrl")

        mod_str = "+".join(modifiers) + "+" if modifiers else ""
        await self.execute(f"cliclick kp:{mod_str}{key}")

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
        if self._lume_path:
            exit_code, _, stderr = await self._run_lume(["snapshot", self._vm_name, name])
            if exit_code == 0:
                logger.info(f"Snapshot created: {name}")
                return True
            logger.error(f"Snapshot failed: {stderr}")
        return False

    async def restore_snapshot(self, name: str) -> bool:
        """Restore VM snapshot.

        Args:
            name: Snapshot name

        Returns:
            True if restored
        """
        if self._lume_path:
            exit_code, _, stderr = await self._run_lume(["restore", self._vm_name, name])
            if exit_code == 0:
                logger.info(f"Snapshot restored: {name}")
                return True
            logger.error(f"Restore failed: {stderr}")
        return False

    async def list_snapshots(self) -> list[str]:
        """List VM snapshots.

        Returns:
            List of snapshot names
        """
        if self._lume_path:
            exit_code, stdout, _ = await self._run_lume(["snapshot", "list", self._vm_name])
            if exit_code == 0:
                return [s.strip() for s in stdout.split("\n") if s.strip()]
        return []

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
        if self._computer and hasattr(self._computer, "copy_to"):
            try:
                await self._computer.copy_to(local_path, remote_path)
                return True
            except Exception as e:
                logger.warning(f"CUA copy_to failed, trying SCP: {e}")

        # SCP fallback (primary method)
        if self._vm_ip and self._sshpass_path:
            return await self._run_scp_to(local_path, remote_path)

        logger.warning("File transfer not available (need SSH)")
        return False

    async def copy_from_vm(self, remote_path: str, local_path: str) -> bool:
        """Copy file from VM.

        Args:
            remote_path: VM path
            local_path: Host path

        Returns:
            True if copied
        """
        if self._computer and hasattr(self._computer, "copy_from"):
            try:
                await self._computer.copy_from(remote_path, local_path)
                return True
            except Exception as e:
                logger.warning(f"CUA copy_from failed, trying SCP: {e}")

        # SCP fallback (primary method)
        if self._vm_ip and self._sshpass_path:
            return await self._run_scp_from(remote_path, local_path)

        logger.warning("File transfer not available (need SSH)")
        return False

    # =========================================================================
    # Command Execution
    # =========================================================================

    async def execute(
        self,
        command: str,
        timeout_ms: int = 30000,
    ) -> CommandResult:
        """Execute command in VM.

        Args:
            command: Shell command
            timeout_ms: Timeout in milliseconds

        Returns:
            CommandResult
        """
        import time

        start = time.time()
        timeout_s = timeout_ms / 1000

        # Try CUA first if available
        if self._computer and hasattr(self._computer, "execute"):
            try:
                result = await self._computer.execute(command)
                duration = (time.time() - start) * 1000
                return CommandResult(
                    exit_code=result.get("exit_code", 0),
                    stdout=result.get("stdout", ""),
                    stderr=result.get("stderr", ""),
                    duration_ms=duration,
                )
            except Exception as e:
                logger.warning(f"CUA execute failed, trying SSH: {e}")

        # SSH is the primary method (fast, reliable)
        if self._vm_ip and self._sshpass_path:
            exit_code, stdout, stderr = await self._run_ssh(command, timeout=timeout_s)
            duration = (time.time() - start) * 1000
            return CommandResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration,
            )

        # Last resort: lume exec (slower)
        if self._lume_path:
            exit_code, stdout, stderr = await self._run_lume(
                ["exec", self._vm_name, command],
                timeout=timeout_s,
            )
            duration = (time.time() - start) * 1000
            return CommandResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration,
            )

        return CommandResult(
            exit_code=-1,
            stdout="",
            stderr="No execution method available (need SSH or Lume)",
            duration_ms=0,
        )

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    async def open_url(self, url: str, browser: str = "Safari") -> bool:
        """Open URL in VM browser.

        Args:
            url: URL to open
            browser: Browser name (Safari, Chrome, Firefox)

        Returns:
            True if opened
        """
        result = await self.execute(f'open -a "{browser}" "{url}"')
        return result.exit_code == 0

    async def open_file(self, path: str) -> bool:
        """Open file in VM with default application.

        Args:
            path: File path in VM

        Returns:
            True if opened
        """
        result = await self.execute(f'open "{path}"')
        return result.exit_code == 0

    async def run_applescript(self, script: str) -> CommandResult:
        """Run AppleScript in VM.

        Args:
            script: AppleScript code

        Returns:
            CommandResult
        """
        # Escape for shell
        escaped = script.replace("'", "'\\''")
        return await self.execute(f"osascript -e '{escaped}'")

    async def get_frontmost_app(self) -> str:
        """Get name of frontmost application.

        Returns:
            App name or empty string
        """
        result = await self.run_applescript(
            'tell application "System Events" to get name of first application process '
            "whose frontmost is true"
        )
        return result.stdout.strip() if result.exit_code == 0 else ""

    @property
    def vm_ip(self) -> str | None:
        """Get VM IP address."""
        return self._vm_ip

    @property
    def vnc_url(self) -> str | None:
        """Get VNC URL for VM."""
        return self._vnc_url

    # =========================================================================
    # Chrome Profile Management
    # =========================================================================

    async def setup_chrome_profile(
        self,
        profile_path: str = "~/.kagami/vm_chrome_profile",
    ) -> bool:
        """Setup Chrome with persistent profile from host.

        Copies Chrome profile to VM for persistent logins/cookies.

        Args:
            profile_path: Local path to Chrome profile backup

        Returns:
            True if setup succeeded
        """
        import os

        profile_path = os.path.expanduser(profile_path)

        # Create local profile dir if needed
        os.makedirs(profile_path, exist_ok=True)

        # Check if profile exists locally
        profile_archive = os.path.join(profile_path, "chrome_profile.tar.gz")

        if os.path.exists(profile_archive):
            logger.info("Restoring Chrome profile to VM...")

            # Copy archive to VM
            success = await self.copy_to_vm(profile_archive, "/tmp/chrome_profile.tar.gz")
            if not success:
                logger.warning("Failed to copy Chrome profile to VM")
                return False

            # Extract in VM
            result = await self.execute(
                "mkdir -p ~/Library/Application\\ Support/Google/Chrome && "
                "cd ~/Library/Application\\ Support/Google/Chrome && "
                "tar -xzf /tmp/chrome_profile.tar.gz && "
                "rm /tmp/chrome_profile.tar.gz"
            )
            if result.exit_code == 0:
                logger.info("✅ Chrome profile restored")
                return True
            else:
                logger.warning(f"Failed to extract profile: {result.stderr}")
                return False
        else:
            logger.info("No Chrome profile backup found, starting fresh")
            return True

    async def save_chrome_profile(
        self,
        profile_path: str = "~/.kagami/vm_chrome_profile",
    ) -> bool:
        """Save Chrome profile from VM to host for persistence.

        Call this before stopping VM to preserve logins/cookies.

        Args:
            profile_path: Local path to save Chrome profile

        Returns:
            True if save succeeded
        """
        import os

        profile_path = os.path.expanduser(profile_path)
        os.makedirs(profile_path, exist_ok=True)

        profile_archive = os.path.join(profile_path, "chrome_profile.tar.gz")
        temp_archive = "/tmp/chrome_profile_backup.tar.gz"

        logger.info("Saving Chrome profile from VM...")

        # Quit Chrome first to ensure profile is saved
        await self.run_applescript('tell application "Google Chrome" to quit')
        await asyncio.sleep(1)

        # Archive profile in VM
        result = await self.execute(
            "cd ~/Library/Application\\ Support/Google/Chrome && "
            f"tar -czf {temp_archive} Default 'Local State' 2>/dev/null || "
            f"tar -czf {temp_archive} . 2>/dev/null"
        )

        if result.exit_code != 0:
            logger.warning(f"Failed to archive profile: {result.stderr}")
            return False

        # Copy to host
        success = await self.copy_from_vm(temp_archive, profile_archive)

        # Cleanup in VM
        await self.execute(f"rm -f {temp_archive}")

        if success:
            logger.info(f"✅ Chrome profile saved to {profile_archive}")
            return True
        else:
            logger.warning("Failed to copy profile from VM")
            return False

    async def open_chrome(
        self,
        url: str | None = None,
        restore_profile: bool = True,
        profile_path: str = "~/.kagami/vm_chrome_profile",
    ) -> bool:
        """Open Chrome in VM with optional profile restoration.

        Args:
            url: URL to open (None = just launch Chrome)
            restore_profile: Restore saved profile first
            profile_path: Path to profile backup

        Returns:
            True if Chrome opened
        """
        # Restore profile if requested
        if restore_profile:
            await self.setup_chrome_profile(profile_path)

        # Check if Chrome is installed
        result = await self.execute(
            "ls /Applications/Google\\ Chrome.app 2>/dev/null || "
            "ls ~/Applications/Google\\ Chrome.app 2>/dev/null"
        )

        if result.exit_code != 0:
            logger.warning("Chrome not installed in VM, using Safari")
            if url:
                return await self.open_url(url, "Safari")
            return False

        # Open Chrome
        if url:
            result = await self.execute(f'open -a "Google Chrome" "{url}"')
        else:
            result = await self.execute('open -a "Google Chrome"')

        return result.exit_code == 0

    async def stop_and_save(
        self,
        save_chrome: bool = True,
        profile_path: str = "~/.kagami/vm_chrome_profile",
    ) -> bool:
        """Stop VM with automatic Chrome profile save.

        Args:
            save_chrome: Save Chrome profile before stopping
            profile_path: Path to save profile

        Returns:
            True if stopped successfully
        """
        if save_chrome:
            await self.save_chrome_profile(profile_path)

        return await self.stop()


__all__ = ["CUALumeAdapter"]
