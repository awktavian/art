"""VM-Based Orchestral Rendering.

Runs REAPER rendering entirely inside a Lume VM to avoid disrupting
the host machine. Uses SSH for command execution and SCP for file transfer.

Features:
- Zero host disruption (no windows, no audio, no CPU spikes)
- Async monitoring with progress callbacks
- Parallel rendering limited only by VM resources
- Automatic file transfer in/out of VM
- Graceful cleanup on errors

Requirements:
- Lume CLI installed: `brew install trycua/tap/lume`
- macOS CUA image: `lume pull macos-sequoia-cua:latest`
- REAPER installed in the VM

Colony: Forge (e₂)
Created: January 6, 2026
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Default Lume VM configuration
DEFAULT_VM_NAME = "macos-sequoia-cua_latest"
LUME_SSH_USER = "lume"
LUME_SSH_PASSWORD = "lume"  # pragma: allowlist secret
SSH_PORT = 22

# Paths inside VM
VM_REAPER_APP = "/Applications/REAPER.app/Contents/MacOS/REAPER"
VM_RENDER_DIR = "/Users/lume/renders"
VM_PROJECT_DIR = "/Users/lume/projects"

# Timeouts
VM_START_TIMEOUT = 120  # Time to wait for VM to boot
SSH_CONNECT_TIMEOUT = 30
RENDER_TIMEOUT_PER_MINUTE = 90  # Seconds per minute of audio (1x + overhead)


@dataclass
class VMRenderJob:
    """A rendering job to execute in VM."""

    name: str
    project_path: Path  # Local path to .rpp file
    midi_path: Path  # Local path to .mid file
    output_name: str  # Output filename (without extension)
    expected_duration: float = 60.0  # Expected duration in seconds
    priority: int = 0  # Higher = render first


@dataclass
class VMRenderResult:
    """Result of a VM render job."""

    name: str
    success: bool
    output_path: Path | None = None
    render_time: float = 0.0
    error: str | None = None


@dataclass
class VMRenderBatchResult:
    """Result of rendering a batch of jobs."""

    total_jobs: int
    successful: int
    failed: int
    results: list[VMRenderResult] = field(default_factory=list)
    total_time: float = 0.0
    output_dir: Path | None = None


class VMRenderer:
    """Render audio in isolated VM without host disruption.

    This class manages a Lume VM for REAPER rendering, keeping all
    processing off the host machine.

    Example:
        >>> renderer = VMRenderer()
        >>> await renderer.initialize()
        >>>
        >>> jobs = [VMRenderJob(name="violin", project_path=...)]
        >>> result = await renderer.render_batch(jobs, output_dir)
        >>>
        >>> await renderer.shutdown()
    """

    def __init__(
        self,
        vm_name: str = DEFAULT_VM_NAME,
        ssh_user: str = LUME_SSH_USER,
        ssh_password: str = LUME_SSH_PASSWORD,
        max_parallel: int = 2,  # VM has fewer resources
    ) -> None:
        """Initialize VM renderer.

        Args:
            vm_name: Name of Lume VM to use
            ssh_user: SSH username
            ssh_password: SSH password
            max_parallel: Max parallel renders inside VM
        """
        self.vm_name = vm_name
        self.ssh_user = ssh_user
        self.ssh_password = ssh_password
        self.max_parallel = max_parallel

        self._vm_ip: str | None = None
        self._initialized = False
        self._progress_callback: Callable[[str, float], None] | None = None

    async def initialize(
        self,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> None:
        """Initialize VM and verify REAPER is available.

        Args:
            progress_callback: Optional callback for progress updates
                               Called with (message, progress_0_to_1)
        """
        self._progress_callback = progress_callback
        self._report_progress("Checking Lume installation...", 0.0)

        # Verify lume is installed
        lume_path = shutil.which("lume")
        if not lume_path:
            raise RuntimeError("Lume not installed. Install with: brew install trycua/tap/lume")

        self._report_progress("Starting VM (this may take a minute)...", 0.1)

        # Start VM if not running
        await self._start_vm()

        self._report_progress("Waiting for SSH...", 0.4)

        # Wait for SSH
        await self._wait_for_ssh()

        self._report_progress("Verifying REAPER in VM...", 0.7)

        # Verify REAPER exists in VM
        result = await self._ssh_exec(f"test -x {VM_REAPER_APP} && echo OK")
        if "OK" not in result:
            raise RuntimeError(
                f"REAPER not found in VM at {VM_REAPER_APP}. Install REAPER in the VM first."
            )

        # Create render directories in VM
        await self._ssh_exec(f"mkdir -p {VM_RENDER_DIR} {VM_PROJECT_DIR}")

        self._report_progress("VM ready", 1.0)
        self._initialized = True
        logger.info(f"VM renderer initialized: {self.vm_name} @ {self._vm_ip}")

    async def shutdown(self, stop_vm: bool = False) -> None:
        """Shutdown renderer and optionally stop VM.

        Args:
            stop_vm: If True, stop the VM (otherwise leave running)
        """
        if stop_vm and self._vm_ip:
            self._report_progress("Stopping VM...", 0.5)
            await asyncio.to_thread(
                subprocess.run,
                ["lume", "stop", self.vm_name],
                capture_output=True,
            )
            self._report_progress("VM stopped", 1.0)

        self._initialized = False
        self._vm_ip = None

    async def render_batch(
        self,
        jobs: Sequence[VMRenderJob],
        output_dir: Path,
        cleanup_vm: bool = True,
    ) -> VMRenderBatchResult:
        """Render a batch of jobs in the VM.

        Args:
            jobs: List of render jobs
            output_dir: Local directory for output files
            cleanup_vm: Clean up VM temp files after

        Returns:
            VMRenderBatchResult with all results
        """
        if not self._initialized:
            await self.initialize(self._progress_callback)

        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[VMRenderResult] = []
        start_time = asyncio.get_event_loop().time()

        # Sort by priority (highest first)
        sorted_jobs = sorted(jobs, key=lambda j: -j.priority)

        total = len(sorted_jobs)
        self._report_progress(f"Rendering {total} stems in VM...", 0.0)

        # Process in batches
        for i in range(0, total, self.max_parallel):
            batch = sorted_jobs[i : i + self.max_parallel]
            batch_results = await asyncio.gather(
                *[self._render_single(job, output_dir) for job in batch],
                return_exceptions=True,
            )

            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results.append(
                        VMRenderResult(
                            name=batch[j].name,
                            success=False,
                            error=str(result),
                        )
                    )
                else:
                    results.append(result)

            progress = min(1.0, (i + len(batch)) / total)
            completed = len([r for r in results if r.success])
            self._report_progress(f"Rendered {completed}/{total} stems", progress)

        # Cleanup VM temp files
        if cleanup_vm:
            await self._ssh_exec(f"rm -rf {VM_PROJECT_DIR}/* {VM_RENDER_DIR}/*")

        total_time = asyncio.get_event_loop().time() - start_time
        successful = len([r for r in results if r.success])

        return VMRenderBatchResult(
            total_jobs=total,
            successful=successful,
            failed=total - successful,
            results=results,
            total_time=total_time,
            output_dir=output_dir,
        )

    async def _render_single(
        self,
        job: VMRenderJob,
        output_dir: Path,
    ) -> VMRenderResult:
        """Render a single job in the VM.

        Args:
            job: Render job
            output_dir: Local output directory

        Returns:
            VMRenderResult
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Transfer project and MIDI to VM
            vm_project = f"{VM_PROJECT_DIR}/{job.name}.rpp"
            vm_midi = f"{VM_PROJECT_DIR}/{job.name}.mid"
            vm_output = f"{VM_RENDER_DIR}/{job.output_name}.wav"

            await self._scp_to_vm(job.project_path, vm_project)
            await self._scp_to_vm(job.midi_path, vm_midi)

            # Update project to use VM paths
            await self._ssh_exec(
                f"sed -i '' 's|FILE \".*\\.mid\"|FILE \"{vm_midi}\"|g' {vm_project}"
            )
            await self._ssh_exec(
                f"sed -i '' 's|RENDER_FILE \".*\"|RENDER_FILE \"{VM_RENDER_DIR}\"|g' {vm_project}"
            )

            # Calculate timeout based on duration
            timeout = int(job.expected_duration * RENDER_TIMEOUT_PER_MINUTE / 60) + 60

            # Run REAPER render (headless, no display)
            render_cmd = f"DISPLAY= {VM_REAPER_APP} -nosplash -newinst -renderproject {vm_project}"

            logger.info(f"Rendering {job.name} in VM (timeout: {timeout}s)")
            await self._ssh_exec(render_cmd, timeout=timeout)

            # Check output exists
            check_result = await self._ssh_exec(f"test -f {vm_output} && echo EXISTS")
            if "EXISTS" not in check_result:
                # Try alternative output name
                alt_output = f"{VM_RENDER_DIR}/{job.name}.wav"
                check_result = await self._ssh_exec(f"test -f {alt_output} && echo EXISTS")
                if "EXISTS" in check_result:
                    vm_output = alt_output
                else:
                    return VMRenderResult(
                        name=job.name,
                        success=False,
                        error="Render produced no output file",
                    )

            # Transfer output back to host
            local_output = output_dir / f"{job.output_name}.wav"
            await self._scp_from_vm(vm_output, local_output)

            render_time = asyncio.get_event_loop().time() - start_time

            return VMRenderResult(
                name=job.name,
                success=True,
                output_path=local_output,
                render_time=render_time,
            )

        except TimeoutError:
            return VMRenderResult(
                name=job.name,
                success=False,
                error=f"Render timed out after {timeout}s",
            )
        except Exception as e:
            return VMRenderResult(
                name=job.name,
                success=False,
                error=str(e),
            )

    async def _start_vm(self) -> None:
        """Start the VM if not running."""
        # Check current status
        result = await asyncio.to_thread(
            subprocess.run,
            ["lume", "ls"],
            capture_output=True,
            text=True,
        )

        if self.vm_name in result.stdout:
            # Parse status
            for line in result.stdout.split("\n"):
                if self.vm_name in line:
                    if "running" in line.lower():
                        # Extract IP
                        parts = line.split()
                        for part in parts:
                            if part.count(".") == 3:  # IP address
                                self._vm_ip = part
                                logger.info(f"VM already running at {self._vm_ip}")
                                return
                    break

        # Start VM headless (no display window on host)
        logger.info(f"Starting VM: {self.vm_name}")
        await asyncio.to_thread(
            subprocess.run,
            ["lume", "run", self.vm_name, "--no-display"],
            capture_output=True,
            text=True,
            timeout=VM_START_TIMEOUT,
        )

        # Get IP after start
        await asyncio.sleep(5)  # Wait for VM to initialize networking

        result = await asyncio.to_thread(
            subprocess.run,
            ["lume", "ls"],
            capture_output=True,
            text=True,
        )

        for line in result.stdout.split("\n"):
            if self.vm_name in line and "running" in line.lower():
                parts = line.split()
                for part in parts:
                    if part.count(".") == 3:
                        self._vm_ip = part
                        logger.info(f"VM started at {self._vm_ip}")
                        return

        raise RuntimeError(f"Failed to start VM: {self.vm_name}")

    async def _wait_for_ssh(self, timeout: int = SSH_CONNECT_TIMEOUT) -> None:
        """Wait for SSH to become available."""
        if not self._vm_ip:
            raise RuntimeError("VM IP not known")

        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            try:
                result = await self._ssh_exec("echo READY", timeout=5)
                if "READY" in result:
                    return
            except Exception:
                pass
            await asyncio.sleep(2)

        raise RuntimeError(f"SSH not available after {timeout}s")

    async def _ssh_exec(self, command: str, timeout: int = 60) -> str:
        """Execute command via SSH.

        Args:
            command: Command to execute
            timeout: Command timeout

        Returns:
            Command output
        """
        if not self._vm_ip:
            raise RuntimeError("VM IP not known")

        ssh_cmd = [
            "sshpass",
            "-p",
            self.ssh_password,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "ConnectTimeout=10",
            f"{self.ssh_user}@{self._vm_ip}",
            command,
        ]

        result = await asyncio.to_thread(
            subprocess.run,
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0 and result.stderr:
            logger.warning(f"SSH command failed: {result.stderr}")

        return result.stdout

    async def _scp_to_vm(self, local_path: Path, remote_path: str) -> None:
        """Copy file to VM via SCP."""
        if not self._vm_ip:
            raise RuntimeError("VM IP not known")

        scp_cmd = [
            "sshpass",
            "-p",
            self.ssh_password,
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            str(local_path),
            f"{self.ssh_user}@{self._vm_ip}:{remote_path}",
        ]

        await asyncio.to_thread(
            subprocess.run,
            scp_cmd,
            capture_output=True,
            check=True,
            timeout=60,
        )

    async def _scp_from_vm(self, remote_path: str, local_path: Path) -> None:
        """Copy file from VM via SCP."""
        if not self._vm_ip:
            raise RuntimeError("VM IP not known")

        scp_cmd = [
            "sshpass",
            "-p",
            self.ssh_password,
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"{self.ssh_user}@{self._vm_ip}:{remote_path}",
            str(local_path),
        ]

        await asyncio.to_thread(
            subprocess.run,
            scp_cmd,
            capture_output=True,
            check=True,
            timeout=120,  # Longer for large audio files
        )

    def _report_progress(self, message: str, progress: float) -> None:
        """Report progress to callback if set."""
        logger.info(f"[{progress * 100:.0f}%] {message}")
        if self._progress_callback:
            self._progress_callback(message, progress)


# =============================================================================
# Host-Based Async Renderer (Minimal Disruption)
# =============================================================================


class AsyncHostRenderer:
    """Async renderer that runs on host with minimal disruption.

    This is a fallback when VM is not available. It:
    - Runs REAPER with lowest priority (nice -n 19)
    - Hides all windows via AppleScript
    - Uses async monitoring (non-blocking)
    - Batch processes to reduce overhead

    Still causes some CPU usage but doesn't steal focus or show windows.
    """

    def __init__(self, max_parallel: int = 2) -> None:
        """Initialize async host renderer.

        Args:
            max_parallel: Max parallel REAPER instances
        """
        self.max_parallel = max_parallel
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._progress_callback: Callable[[str, float], None] | None = None

    async def render_batch(
        self,
        jobs: Sequence[VMRenderJob],
        output_dir: Path,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> VMRenderBatchResult:
        """Render batch with async monitoring.

        Args:
            jobs: Render jobs
            output_dir: Output directory
            progress_callback: Progress callback

        Returns:
            Batch result
        """
        self._progress_callback = progress_callback
        output_dir.mkdir(parents=True, exist_ok=True)

        results: list[VMRenderResult] = []
        start_time = asyncio.get_event_loop().time()
        total = len(jobs)

        # Hide REAPER continuously in background
        hide_task = asyncio.create_task(self._hide_reaper_loop())

        try:
            # Render in batches
            sorted_jobs = sorted(jobs, key=lambda j: -j.priority)

            for i in range(0, total, self.max_parallel):
                batch = sorted_jobs[i : i + self.max_parallel]
                batch_results = await asyncio.gather(
                    *[self._render_single(job, output_dir) for job in batch],
                    return_exceptions=True,
                )

                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        results.append(
                            VMRenderResult(
                                name=batch[j].name,
                                success=False,
                                error=str(result),
                            )
                        )
                    else:
                        results.append(result)

                progress = min(1.0, (i + len(batch)) / total)
                self._report_progress(
                    f"Rendered {len([r for r in results if r.success])}/{total}",
                    progress,
                )

        finally:
            hide_task.cancel()
            try:
                await hide_task
            except asyncio.CancelledError:
                pass

            # Kill any lingering REAPER processes
            await asyncio.to_thread(
                subprocess.run,
                ["pkill", "-f", "REAPER"],
                capture_output=True,
            )

        total_time = asyncio.get_event_loop().time() - start_time
        successful = len([r for r in results if r.success])

        return VMRenderBatchResult(
            total_jobs=total,
            successful=successful,
            failed=total - successful,
            results=results,
            total_time=total_time,
            output_dir=output_dir,
        )

    async def _render_single(
        self,
        job: VMRenderJob,
        output_dir: Path,
    ) -> VMRenderResult:
        """Render single job asynchronously."""
        start_time = asyncio.get_event_loop().time()

        try:
            reaper_app = Path("/Applications/REAPER.app/Contents/MacOS/REAPER")
            if not reaper_app.exists():
                return VMRenderResult(
                    name=job.name,
                    success=False,
                    error="REAPER not found",
                )

            # Calculate timeout
            timeout = int(job.expected_duration * 1.5) + 60

            # Run REAPER with lowest priority, no splash
            proc = await asyncio.create_subprocess_exec(
                "nice",
                "-n",
                "19",
                str(reaper_app),
                "-nosplash",
                "-newinst",
                "-renderproject",
                str(job.project_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            self._processes[job.name] = proc

            try:
                await asyncio.wait_for(proc.wait(), timeout=timeout)
            except TimeoutError:
                proc.kill()
                return VMRenderResult(
                    name=job.name,
                    success=False,
                    error=f"Timeout after {timeout}s",
                )
            finally:
                self._processes.pop(job.name, None)

            # Check for output
            expected_output = job.project_path.parent / f"{job.output_name}.wav"
            if expected_output.exists():
                # Move to output dir
                final_path = output_dir / f"{job.output_name}.wav"
                shutil.move(str(expected_output), str(final_path))

                return VMRenderResult(
                    name=job.name,
                    success=True,
                    output_path=final_path,
                    render_time=asyncio.get_event_loop().time() - start_time,
                )
            else:
                return VMRenderResult(
                    name=job.name,
                    success=False,
                    error="No output file produced",
                )

        except Exception as e:
            return VMRenderResult(
                name=job.name,
                success=False,
                error=str(e),
            )

    async def _hide_reaper_loop(self) -> None:
        """Continuously hide REAPER windows."""
        hide_script = """
        tell application "System Events"
            try
                set visible of application process "REAPER" to false
            end try
            try
                click button 1 of window 1 of application process "REAPER"
            end try
        end tell
        """

        while True:
            await asyncio.to_thread(
                subprocess.run,
                ["osascript", "-e", hide_script],
                capture_output=True,
            )
            await asyncio.sleep(1)

    def _report_progress(self, message: str, progress: float) -> None:
        """Report progress."""
        logger.info(f"[{progress * 100:.0f}%] {message}")
        if self._progress_callback:
            self._progress_callback(message, progress)


# =============================================================================
# Factory Functions
# =============================================================================


async def get_best_renderer(
    prefer_vm: bool = True,
) -> VMRenderer | AsyncHostRenderer:
    """Get the best available renderer.

    Args:
        prefer_vm: Prefer VM rendering if available

    Returns:
        VMRenderer if available and preferred, else AsyncHostRenderer
    """
    if prefer_vm:
        # Check if Lume and VM are available
        lume_path = shutil.which("lume")
        if lume_path:
            result = subprocess.run(
                ["lume", "ls"],
                capture_output=True,
                text=True,
            )
            if "macos-sequoia-cua" in result.stdout:
                logger.info("Using VM renderer for zero host disruption")
                return VMRenderer()

    logger.info("Using async host renderer (VM not available)")
    return AsyncHostRenderer()
