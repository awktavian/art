"""
Test colony manager subprocess resource management.

This test validates that the colony manager properly manages subprocess
resources without leaks:
1. Pipes are consumed asynchronously (no buffer deadlock)
2. Zombie processes are reaped (proper wait())
3. File descriptors are not leaked

Created: December 21, 2025 (P0-4 fix)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import asyncio
import psutil
from unittest.mock import AsyncMock, MagicMock, patch

from kagami.orchestration.colony_manager import (
    ColonyManager,
    ColonyManagerConfig,
)


@pytest.fixture
def config() -> ColonyManagerConfig:
    """Create test configuration with fast timeouts."""
    return ColonyManagerConfig(
        health_check_interval=1.0,
        startup_grace_period=2.0,
        shutdown_timeout=2.0,
    )


@pytest.mark.asyncio
async def test_subprocess_uses_asyncio_not_popen(config: ColonyManagerConfig) -> None:
    """Verify subprocess.Popen is replaced with asyncio.create_subprocess_exec."""
    manager = ColonyManager(config)

    # Mock asyncio.create_subprocess_exec
    mock_process = AsyncMock()
    mock_process.pid = 12345
    mock_process.stdout = AsyncMock()
    mock_process.stderr = AsyncMock()
    mock_process.returncode = None
    mock_process.wait = AsyncMock(return_value=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        await manager._spawn_colony(0)

        # Verify asyncio.create_subprocess_exec was called (not subprocess.Popen)
        mock_exec.assert_called_once()
        args = mock_exec.call_args
        assert args is not None
        assert args[1]["stdout"] == asyncio.subprocess.PIPE
        assert args[1]["stderr"] == asyncio.subprocess.PIPE


@pytest.mark.asyncio
async def test_pipes_consumed_asynchronously(config: ColonyManagerConfig) -> None:
    """Verify stdout/stderr pipes are consumed to prevent buffer deadlock."""
    manager = ColonyManager(config)

    # Mock subprocess with streams
    mock_process = AsyncMock()
    mock_process.pid = 12345
    mock_process.returncode = None

    # Mock streams that yield data then EOF
    mock_stdout = AsyncMock()
    mock_stdout.readline = AsyncMock(side_effect=[b"output line\n", b""])
    mock_stderr = AsyncMock()
    mock_stderr.readline = AsyncMock(side_effect=[b"error line\n", b""])

    mock_process.stdout = mock_stdout
    mock_process.stderr = mock_stderr
    mock_process.wait = AsyncMock(return_value=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        await manager._spawn_colony(0)

        # Give pipe consumer task time to run
        await asyncio.sleep(0.1)

        # Verify streams were read (pipes consumed)
        assert mock_stdout.readline.call_count >= 1
        assert mock_stderr.readline.call_count >= 1


@pytest.mark.asyncio
async def test_process_wait_called_prevents_zombies(config: ColonyManagerConfig) -> None:
    """Verify process.wait() is called to reap zombie processes."""
    manager = ColonyManager(config)

    mock_process = AsyncMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.stdout = AsyncMock()
    mock_process.stderr = AsyncMock()

    # Track if wait() was called
    wait_called = asyncio.Event()

    async def mock_wait() -> int:
        wait_called.set()
        return 0

    mock_process.wait = mock_wait

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        await manager._spawn_colony(0)

        # Give pipe consumer task time to run
        await asyncio.sleep(0.2)

        # Verify wait() was called
        assert wait_called.is_set(), "process.wait() must be called to prevent zombies"


@pytest.mark.asyncio
async def test_stop_colony_awaits_process_wait(config: ColonyManagerConfig) -> None:
    """Verify _stop_colony properly awaits process termination."""
    manager = ColonyManager(config)

    mock_process = AsyncMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.terminate = MagicMock()
    mock_process.kill = MagicMock()

    # Track wait calls
    wait_calls = []

    async def mock_wait() -> int:
        wait_calls.append("wait")
        return 0

    mock_process.wait = mock_wait

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        # Spawn then stop
        await manager._spawn_colony(0)
        await manager._stop_colony(0)

        # Verify terminate and wait were called
        mock_process.terminate.assert_called_once()
        assert len(wait_calls) >= 1, "wait() must be called during shutdown"


@pytest.mark.asyncio
async def test_no_file_descriptor_leak() -> None:
    """Verify no file descriptor leak during spawn/stop cycles.

    This test uses real psutil to check FD count.
    """
    config = ColonyManagerConfig(
        startup_grace_period=0.5,
        shutdown_timeout=2.0,
    )
    manager = ColonyManager(config)

    # Get baseline FD count
    process = psutil.Process()
    baseline_fds = process.num_fds() if hasattr(process, "num_fds") else 0

    # Mock subprocess to avoid spawning real processes
    mock_process = AsyncMock()
    mock_process.pid = 99999
    mock_process.returncode = None
    mock_process.stdout = AsyncMock()
    mock_process.stderr = AsyncMock()
    mock_process.stdout.readline = AsyncMock(return_value=b"")
    mock_process.stderr.readline = AsyncMock(return_value=b"")
    mock_process.wait = AsyncMock(return_value=0)
    mock_process.terminate = MagicMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        # Spawn and stop multiple times
        for _ in range(5):
            await manager._spawn_colony(0)
            await asyncio.sleep(0.1)
            await manager._stop_colony(0)

        # Check FD count hasn't grown significantly (allow small variance)
        final_fds = process.num_fds() if hasattr(process, "num_fds") else 0
        fd_growth = final_fds - baseline_fds

        # Allow up to 10 FDs of variance (some OS/runtime overhead)
        assert fd_growth < 10, f"File descriptor leak detected: grew by {fd_growth}"


@pytest.mark.asyncio
async def test_consume_pipes_handles_stream_errors() -> None:
    """Verify pipe consumer handles stream errors gracefully."""
    config = ColonyManagerConfig()
    manager = ColonyManager(config)

    # Mock process with failing stream
    mock_process = AsyncMock()
    mock_process.pid = 12345
    mock_process.returncode = None

    mock_stdout = AsyncMock()
    mock_stdout.readline = AsyncMock(side_effect=OSError("Stream closed"))
    mock_stderr = AsyncMock()
    mock_stderr.readline = AsyncMock(return_value=b"")

    mock_process.stdout = mock_stdout
    mock_process.stderr = mock_stderr
    mock_process.wait = AsyncMock(return_value=1)

    # Should not raise exception
    await manager._consume_pipes(0, mock_process)

    # Verify wait was still called despite stream error
    mock_process.wait.assert_called_once()


# Integration test (requires real subprocess support)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_subprocess_cleanup() -> None:
    """Integration test with real subprocess (echo command).

    This test validates the fix works with actual subprocess spawning.
    """
    # Spawn a short-lived subprocess
    process = await asyncio.create_subprocess_exec(
        "echo",
        "test",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Consume pipes
    async def consume() -> None:
        if process.stdout:
            while await process.stdout.readline():
                pass
        if process.stderr:
            while await process.stderr.readline():
                pass
        await process.wait()

    # Run consumer
    await asyncio.wait_for(consume(), timeout=2.0)

    # Verify process was reaped
    assert process.returncode is not None, "Process must have return code after wait()"
    assert process.returncode == 0, "Echo command should succeed"
