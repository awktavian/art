"""Colony Manager - Process Supervisor for 7 Colony Agents.

This module manages the lifecycle of 7 colony agent processes:
- Spawns and monitors colony processes
- Health checks via HTTP ping
- Auto-restart on failure (exponential backoff)
- Load balancing (least-loaded routing)
- Graceful shutdown

ARCHITECTURE:
=============
Each colony runs as a separate process with:
- Main port: 8001-8007 (API server)
- Health port: 9001-9007 (health check endpoint)
- Colony index: 0-6 (spark, forge, flow, nexus, beacon, grove, crystal)

USAGE:
======
    manager = ColonyManager()
    await manager.start_all()

    # Check health
    if manager.all_healthy():
        logger.info("All colonies healthy")

    # Route to least-loaded
    colony_idx = manager.get_least_loaded_colony()

    # Graceful shutdown
    await manager.stop_all()

Created: December 14, 2025
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from dataclasses import dataclass
from typing import Any

import aiohttp

# Import from canonical source to avoid circular dependencies
from kagami_math.catastrophe_constants import COLONY_NAMES

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ColonyProcessInfo:
    """Process information for a colony."""

    colony_idx: int
    process: asyncio.subprocess.Process
    port: int
    pid: int
    start_time: float
    restart_count: int = 0
    last_health_check: float | None = None
    is_healthy: bool = False
    request_count: int = 0
    last_restart_attempt: float = 0.0


@dataclass
class ColonyManagerConfig:
    """Configuration for colony manager."""

    base_port: int = 8001
    health_check_interval: float = 5.0
    max_restart_attempts: int = 3
    restart_backoff_base: float = 2.0  # Exponential backoff base
    restart_backoff_max: float = 60.0  # Max backoff (seconds)
    health_timeout: float = 3.0  # HTTP request timeout
    startup_grace_period: float = 10.0  # Allow startup before health checks
    shutdown_timeout: float = 10.0  # Wait for graceful shutdown


# =============================================================================
# COLONY MANAGER
# =============================================================================


class ColonyManager:
    """Process supervisor for 7 colony agents.

    Spawns, monitors, and restarts colony processes. Provides health
    monitoring and load balancing capabilities.
    """

    def __init__(
        self,
        config: ColonyManagerConfig | None = None,
    ):
        """Initialize colony manager.

        Args:
            config: Manager configuration
        """
        self.config = config or ColonyManagerConfig()

        # Process tracking
        self._colonies: dict[int, ColonyProcessInfo] = {}

        # Background tasks
        self._monitor_task: asyncio.Task | None = None
        self._running = False

        # HTTP session for health checks
        self._session: aiohttp.ClientSession | None = None

        logger.info("ColonyManager initialized")

    # =========================================================================
    # LIFECYCLE MANAGEMENT
    # =========================================================================

    async def start_all(self) -> None:
        """Spawn all 7 colony processes."""
        if self._running:
            logger.warning("Colony manager already running")
            return

        self._running = True

        # Create HTTP session
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.health_timeout)
        )

        # Spawn all colonies
        for colony_idx in range(7):
            try:
                await self._spawn_colony(colony_idx)
            except Exception as e:
                logger.error(f"Failed to spawn colony {colony_idx}: {e}")

        # Wait for startup grace period
        logger.info(f"Waiting {self.config.startup_grace_period}s for colonies to start...")
        await asyncio.sleep(self.config.startup_grace_period)

        # Start health monitoring loop
        self._monitor_task = asyncio.create_task(self.health_monitor_loop())

        logger.info("All colonies started, health monitoring active")

    async def stop_all(self) -> None:
        """Gracefully stop all colonies."""
        if not self._running:
            return

        self._running = False

        # Stop monitoring
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Terminate all processes
        logger.info("Stopping all colonies...")
        for colony_idx, _info in list(self._colonies.items()):
            try:
                await self._stop_colony(colony_idx)
            except Exception as e:
                logger.error(f"Error stopping colony {colony_idx}: {e}")

        # Close HTTP session
        if self._session:
            await self._session.close()
            self._session = None

        logger.info("All colonies stopped")

    async def _spawn_colony(self, colony_idx: int) -> None:
        """Spawn a single colony process.

        Args:
            colony_idx: Colony index (0-6)
        """
        colony_name = COLONY_NAMES[colony_idx]
        port = self.config.base_port + colony_idx

        # Build command
        # Spawn colony HTTP server with CLI args
        cmd = [
            sys.executable,
            "-m",
            "kagami.core.unified_agents.colony_server",
            "--colony-idx",
            str(colony_idx),
            "--port",
            str(port),
        ]

        # Spawn async process with pipe consumption to prevent buffer fill
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Don't inherit parent's environment completely (optional)
            # env={**os.environ, "COLONY_IDX": str(colony_idx)},
        )

        # Spawn background task to consume pipes and prevent buffer deadlock
        asyncio.create_task(self._consume_pipes(colony_idx, process))

        # Track process
        info = ColonyProcessInfo(
            colony_idx=colony_idx,
            process=process,
            port=port,
            pid=process.pid,
            start_time=time.time(),
        )
        self._colonies[colony_idx] = info

        logger.info(
            f"Spawned colony {colony_idx} ({colony_name}) on port {port}, PID {process.pid}"
        )

    async def _consume_pipes(self, colony_idx: int, process: asyncio.subprocess.Process) -> None:
        """Consume stdout/stderr pipes asynchronously to prevent buffer deadlock.

        Args:
            colony_idx: Colony index (0-6)
            process: Async subprocess to monitor
        """
        try:
            # Read and discard output to prevent buffer fill
            # Pipes must be consumed continuously or child process will block
            async def consume_stream(stream: asyncio.StreamReader | None, name: str) -> None:
                if stream is None:
                    return
                try:
                    while True:
                        line = await stream.readline()
                        if not line:
                            break
                        # Log output at debug level for troubleshooting
                        logger.debug(f"Colony {colony_idx} {name}: {line.decode().rstrip()}")
                except Exception as e:
                    logger.debug(f"Colony {colony_idx} {name} stream closed: {e}")

            # Consume both streams concurrently
            await asyncio.gather(
                consume_stream(process.stdout, "stdout"),
                consume_stream(process.stderr, "stderr"),
                return_exceptions=True,
            )

            # Wait for process exit
            await process.wait()
            logger.debug(f"Colony {colony_idx} process exited with code {process.returncode}")

        except Exception as e:
            logger.error(f"Error consuming pipes for colony {colony_idx}: {e}")

    async def _stop_colony(self, colony_idx: int) -> None:
        """Stop a single colony process.

        Args:
            colony_idx: Colony index (0-6)
        """
        info = self._colonies.get(colony_idx)
        if not info:
            return

        colony_name = COLONY_NAMES[colony_idx]
        process = info.process

        # Try graceful shutdown first (SIGTERM)
        logger.info(f"Terminating colony {colony_idx} ({colony_name}) PID {info.pid}")
        process.terminate()

        # Wait for shutdown
        try:
            await asyncio.wait_for(process.wait(), timeout=self.config.shutdown_timeout)
            logger.info(f"Colony {colony_idx} terminated gracefully")
        except TimeoutError:
            # Force kill
            logger.warning(f"Colony {colony_idx} did not terminate, force killing...")
            process.kill()
            await process.wait()

        # Remove from tracking
        del self._colonies[colony_idx]

    async def restart_colony(self, colony_idx: int) -> None:
        """Restart a specific colony process.

        Args:
            colony_idx: Colony index (0-6)
        """
        info = self._colonies.get(colony_idx)
        if not info:
            logger.warning(f"Cannot restart colony {colony_idx}: not running")
            return

        # Check restart attempts
        if info.restart_count >= self.config.max_restart_attempts:
            logger.error(
                f"Colony {colony_idx} exceeded max restart attempts "
                f"({self.config.max_restart_attempts}), giving up"
            )
            return

        # Calculate backoff (2s, 4s, 8s, ...)
        backoff = min(
            self.config.restart_backoff_base ** (info.restart_count + 1),
            self.config.restart_backoff_max,
        )

        # Check if we need to wait (exponential backoff)
        time_since_last = time.time() - info.last_restart_attempt
        if time_since_last < backoff:
            wait_time = backoff - time_since_last
            logger.info(
                f"Waiting {wait_time:.1f}s before restarting colony {colony_idx} "
                f"(attempt {info.restart_count + 1})"
            )
            await asyncio.sleep(wait_time)

        # Store restart info BEFORE stopping (stop removes from _colonies)
        previous_restart_count = info.restart_count
        restart_time = time.time()

        # Stop existing process
        await self._stop_colony(colony_idx)

        # Spawn new process
        try:
            await self._spawn_colony(colony_idx)
        except Exception as e:
            logger.error(f"Failed to spawn colony {colony_idx} after restart: {e}")
            # Colony is now stopped and not running - caller should handle
            return

        # Update restart tracking on successfully spawned colony
        new_info = self._colonies.get(colony_idx)
        if new_info:
            new_info.restart_count = previous_restart_count + 1
            new_info.last_restart_attempt = restart_time

            colony_name = COLONY_NAMES[colony_idx]
            logger.info(
                f"Restarted colony {colony_idx} ({colony_name}), attempt {new_info.restart_count}"
            )

    # =========================================================================
    # HEALTH MONITORING
    # =========================================================================

    async def health_monitor_loop(self) -> None:
        """Continuous health monitoring (background task)."""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._check_all_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")

    async def _check_all_health(self) -> None:
        """Check health of all colonies."""
        tasks = [self._check_colony_health(colony_idx) for colony_idx in self._colonies.keys()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_colony_health(self, colony_idx: int) -> None:
        """Check health of a single colony.

        Args:
            colony_idx: Colony index (0-6)
        """
        info = self._colonies.get(colony_idx)
        if not info:
            return

        # Skip health checks during startup grace period
        uptime = time.time() - info.start_time
        if uptime < self.config.startup_grace_period:
            return

        # Check if process is alive
        if info.process.returncode is not None:
            logger.warning(
                f"Colony {colony_idx} process died (exit code {info.process.returncode})"
            )
            info.is_healthy = False
            await self.restart_colony(colony_idx)
            return

        # HTTP health check
        health_url = f"http://localhost:{info.port}/health"

        try:
            if not self._session:
                logger.warning("HTTP session not available for health check")
                return

            async with self._session.get(health_url) as resp:
                if resp.status == 200:
                    # Healthy
                    was_unhealthy = not info.is_healthy
                    info.is_healthy = True
                    info.last_health_check = time.time()

                    if was_unhealthy:
                        colony_name = COLONY_NAMES[colony_idx]
                        logger.info(f"Colony {colony_idx} ({colony_name}) is now healthy")
                else:
                    # Unhealthy response
                    logger.warning(f"Colony {colony_idx} health check failed: HTTP {resp.status}")
                    info.is_healthy = False
                    await self.restart_colony(colony_idx)

        except TimeoutError:
            logger.warning(f"Colony {colony_idx} health check timed out")
            info.is_healthy = False
            await self.restart_colony(colony_idx)

        except aiohttp.ClientError as e:
            logger.warning(f"Colony {colony_idx} health check error: {e}")
            info.is_healthy = False
            await self.restart_colony(colony_idx)

    def is_healthy(self, colony_idx: int) -> bool:
        """Check if specific colony is healthy.

        Args:
            colony_idx: Colony index (0-6)

        Returns:
            True if healthy, False otherwise
        """
        info = self._colonies.get(colony_idx)
        return info.is_healthy if info else False

    def all_healthy(self) -> bool:
        """Check if all colonies are healthy.

        Returns:
            True if all colonies healthy, False otherwise
        """
        if not self._colonies:
            return False

        return all(info.is_healthy for info in self._colonies.values())

    def get_unhealthy_colonies(self) -> list[int]:
        """Get list[Any] of unhealthy colony indices.

        Returns:
            List of colony indices that are unhealthy
        """
        return [idx for idx, info in self._colonies.items() if not info.is_healthy]

    # =========================================================================
    # LOAD BALANCING
    # =========================================================================

    def get_least_loaded_colony(self) -> int | None:
        """Return index of least-loaded colony for routing.

        Uses request count as load metric.

        Returns:
            Colony index (0-6) or None if no healthy colonies
        """
        # Filter healthy colonies
        healthy_colonies = [(idx, info) for idx, info in self._colonies.items() if info.is_healthy]

        if not healthy_colonies:
            return None

        # Find colony with minimum request count
        min_idx, _min_info = min(healthy_colonies, key=lambda x: x[1].request_count)

        return min_idx

    def record_request(self, colony_idx: int) -> None:
        """Record a request routed to a colony.

        Args:
            colony_idx: Colony index (0-6)
        """
        info = self._colonies.get(colony_idx)
        if info:
            info.request_count += 1

    def get_load_stats(self) -> dict[int, int]:
        """Get request count per colony.

        Returns:
            Dict mapping colony_idx → request_count
        """
        return {idx: info.request_count for idx, info in self._colonies.items()}

    # =========================================================================
    # STATS & MONITORING
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get colony manager statistics.

        Returns:
            Statistics dictionary
        """
        colony_stats = {}
        for idx, info in self._colonies.items():
            colony_name = COLONY_NAMES[idx]
            uptime = time.time() - info.start_time

            colony_stats[colony_name] = {
                "colony_idx": idx,
                "port": info.port,
                "pid": info.pid,
                "is_healthy": info.is_healthy,
                "uptime": round(uptime, 2),
                "restart_count": info.restart_count,
                "request_count": info.request_count,
                "last_health_check": info.last_health_check,
            }

        return {
            "running": self._running,
            "total_colonies": len(self._colonies),
            "healthy_colonies": sum(1 for info in self._colonies.values() if info.is_healthy),
            "unhealthy_colonies": self.get_unhealthy_colonies(),
            "all_healthy": self.all_healthy(),
            "colonies": colony_stats,
        }


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================

_COLONY_MANAGER: ColonyManager | None = None


def get_colony_manager() -> ColonyManager | None:
    """Get the global colony manager instance.

    Returns:
        ColonyManager instance, or None if not initialized
    """
    return _COLONY_MANAGER


def set_colony_manager(manager: ColonyManager | None) -> None:
    """Set the global colony manager instance.

    Args:
        manager: ColonyManager instance to set[Any]
    """
    global _COLONY_MANAGER
    _COLONY_MANAGER = manager


def create_colony_manager(
    config: ColonyManagerConfig | None = None,
) -> ColonyManager:
    """Create a colony manager.

    Args:
        config: Manager configuration

    Returns:
        Configured ColonyManager
    """
    return ColonyManager(config=config)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ColonyManager",
    "ColonyManagerConfig",
    "ColonyProcessInfo",
    "create_colony_manager",
    "get_colony_manager",
    "set_colony_manager",
]
