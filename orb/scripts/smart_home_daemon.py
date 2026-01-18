#!/usr/bin/env python3
"""Kagami Smart Home Daemon - Persistent Organism Integration.

🔥 FORGE COLONY AUTOMATIC BOOT CLIENT

This is the persistent smart home client daemon that maintains continuous
integration between Kagami's organism state and the physical home environment.

FEATURES:
- Automatic startup and recovery
- Organism state → home expression
- Real-time device monitoring
- Network resilience and reconnection
- SystemD/LaunchAgent integration
- Performance monitoring
- Graceful shutdown

DEPLOYMENT:
- Development: python scripts/smart_home_daemon.py
- Production: systemctl start kagami-smarthome.service
- macOS: launchctl load ~/Library/LaunchAgents/com.kagami.smarthome.plist

ENVIRONMENT:
- KAGAMI_HOME_DAEMON_LOG_LEVEL: DEBUG/INFO/WARNING/ERROR
- KAGAMI_HOME_DAEMON_SYNC_INTERVAL: Sync interval in seconds
- KAGAMI_HOME_DAEMON_PID_FILE: PID file location
- KAGAMI_SMART_HOME_CONFIG: Smart home config file

Created: December 29, 2025
Author: Forge Colony / Kagami OS
Purpose: Replace lazy initialization with persistent organism integration
"""

from __future__ import annotations

import asyncio
import argparse
import atexit
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Core imports
from kagami.core.boot_mode import BootMode, get_boot_mode
from kagami_smarthome import get_smart_home

# Optional organism integration
try:
    from kagami.boot.actions.smarthome import (
        startup_smart_home_organism_bridge,
        shutdown_smart_home_organism_bridge,
    )

    ORGANISM_INTEGRATION_AVAILABLE = True
except ImportError:
    ORGANISM_INTEGRATION_AVAILABLE = False

# Logging setup
logger = logging.getLogger(__name__)


class SmartHomeDaemon:
    """Persistent smart home daemon with organism integration.

    This daemon runs continuously in the background, maintaining:
    - Smart home controller initialization and monitoring
    - Organism state synchronization (if available)
    - Device state polling and updates
    - Network reconnection and error recovery
    - Performance metrics and health checks
    """

    def __init__(
        self,
        pid_file: str | None = None,
        log_level: str = "INFO",
        sync_interval: float = 2.0,
        daemon_mode: bool = False,
    ):
        self.pid_file = pid_file or "/tmp/kagami_smart_home_daemon.pid"
        self.log_level = log_level
        self.sync_interval = sync_interval
        self.daemon_mode = daemon_mode

        # Runtime state
        self._running = False
        self._start_time = 0.0
        self._cycle_count = 0
        self._error_count = 0

        # Components
        self._smart_home_controller = None
        self._organism_bridge = None

        # Tasks
        self._main_task: asyncio.Task | None = None
        self._health_task: asyncio.Task | None = None

        # Setup
        self._setup_logging()
        self._setup_signal_handlers()

    def _setup_logging(self) -> None:
        """Setup structured logging for the daemon."""
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        if self.daemon_mode:
            # Daemon mode: log to syslog/journald
            from logging.handlers import SysLogHandler

            handler = SysLogHandler(address="/dev/log")
            handler.setFormatter(logging.Formatter("kagami-smarthome: %(levelname)s - %(message)s"))
        else:
            # Interactive mode: log to console
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(log_format))

        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()), handlers=[handler], force=True
        )

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown signal handlers."""

        def signal_handler(signum: int, frame: Any) -> None:
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            if self._running:
                asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _write_pid_file(self) -> None:
        """Write process ID to PID file."""
        try:
            with open(self.pid_file, "w") as f:
                f.write(str(os.getpid()))
            logger.debug(f"PID file written: {self.pid_file}")

            # Cleanup PID file on exit
            atexit.register(self._cleanup_pid_file)
        except Exception as e:
            logger.warning(f"Failed to write PID file {self.pid_file}: {e}")

    def _cleanup_pid_file(self) -> None:
        """Remove PID file on shutdown."""
        try:
            if os.path.exists(self.pid_file):
                os.unlink(self.pid_file)
                logger.debug(f"PID file removed: {self.pid_file}")
        except Exception as e:
            logger.warning(f"Failed to remove PID file: {e}")

    def _check_single_instance(self) -> bool:
        """Check if another instance is already running."""
        if not os.path.exists(self.pid_file):
            return True

        try:
            with open(self.pid_file) as f:
                old_pid = int(f.read().strip())

            # Check if process is still running
            try:
                os.kill(old_pid, 0)  # Signal 0 tests if process exists
                logger.error(f"Another instance already running (PID: {old_pid})")
                return False
            except ProcessLookupError:
                # Old process not running, remove stale PID file
                os.unlink(self.pid_file)
                logger.info("Removed stale PID file")
                return True

        except (ValueError, FileNotFoundError):
            # Invalid or missing PID file
            return True

    async def start(self) -> None:
        """Start the smart home daemon."""
        if self._running:
            logger.warning("Daemon already running")
            return

        # Single instance check
        if not self._check_single_instance():
            raise RuntimeError("Another daemon instance is already running")

        logger.info("🏠 Starting Kagami Smart Home Daemon...")
        self._start_time = time.time()
        self._write_pid_file()

        try:
            # Check boot mode
            boot_mode = get_boot_mode()
            if boot_mode != BootMode.FULL:
                logger.warning(f"Running in {boot_mode.value} mode - some features may be limited")

            # Initialize smart home controller
            logger.info("🔧 Initializing smart home controller...")
            self._smart_home_controller = await get_smart_home()
            logger.info(
                f"✅ Smart home initialized: {len(self._smart_home_controller.get_all_devices())} devices"
            )

            # Initialize organism bridge (if available)
            if ORGANISM_INTEGRATION_AVAILABLE:
                logger.info("🧬 Initializing organism bridge...")
                try:
                    self._organism_bridge = await startup_smart_home_organism_bridge()
                    logger.info("✅ Organism bridge active - home will express organism state")
                except Exception as e:
                    logger.warning(f"Organism bridge initialization failed: {e}")
            else:
                logger.info("🧬 Organism integration not available (running standalone)")

            self._running = True

            # Start background tasks
            self._main_task = asyncio.create_task(self._main_loop())
            self._health_task = asyncio.create_task(self._health_monitor())

            logger.info("🎉 Kagami Smart Home Daemon is now running")
            logger.info(f"🔄 Sync interval: {self.sync_interval}s")
            logger.info(f"📂 PID file: {self.pid_file}")

        except Exception as e:
            logger.error(f"❌ Daemon startup failed: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the daemon gracefully."""
        if not self._running:
            return

        logger.info("🛑 Stopping Kagami Smart Home Daemon...")
        self._running = False

        # Cancel background tasks
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass

        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        # Shutdown organism bridge
        if self._organism_bridge and ORGANISM_INTEGRATION_AVAILABLE:
            try:
                await shutdown_smart_home_organism_bridge()
                logger.info("✅ Organism bridge shutdown complete")
            except Exception as e:
                logger.error(f"Organism bridge shutdown error: {e}")

        # Shutdown smart home controller
        if self._smart_home_controller and self._smart_home_controller._running:
            try:
                await self._smart_home_controller.stop()
                logger.info("✅ Smart home controller shutdown complete")
            except Exception as e:
                logger.error(f"Smart home shutdown error: {e}")

        # Cleanup PID file
        self._cleanup_pid_file()

        runtime = time.time() - self._start_time
        logger.info(f"✅ Daemon stopped (runtime: {runtime:.1f}s, cycles: {self._cycle_count})")

    async def _main_loop(self) -> None:
        """Main daemon loop for continuous monitoring and synchronization."""
        logger.info("🔄 Starting main daemon loop...")

        while self._running:
            try:
                cycle_start = time.time()

                # Perform sync cycle
                await self._sync_cycle()

                # Update counters
                self._cycle_count += 1

                # Calculate sleep time to maintain sync interval
                cycle_time = time.time() - cycle_start
                sleep_time = max(0, self.sync_interval - cycle_time)

                if cycle_time > self.sync_interval * 1.5:
                    logger.warning(
                        f"Sync cycle slow: {cycle_time:.2f}s (target: {self.sync_interval}s)"
                    )

                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._error_count += 1
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(min(30.0, self.sync_interval * 10))  # Error backoff

        logger.info("🔄 Main daemon loop stopped")

    async def _sync_cycle(self) -> None:
        """Perform one synchronization cycle."""
        # Note: The actual organism→home sync is handled by SmartHomeOrganismBridge
        # This main loop focuses on daemon-level monitoring and health checks

        # Check smart home controller health
        if not self._smart_home_controller._running:
            logger.warning("Smart home controller not running, attempting recovery...")
            try:
                await self._smart_home_controller.initialize()
                logger.info("✅ Smart home controller recovered")
            except Exception as e:
                logger.error(f"Smart home recovery failed: {e}")

        # Log periodic status
        if self._cycle_count % (60 // self.sync_interval) == 0:  # Every minute
            runtime = time.time() - self._start_time
            error_rate = self._error_count / max(1, self._cycle_count)
            logger.info(
                f"🏠 Daemon status: {runtime:.0f}s runtime, {self._cycle_count} cycles, {error_rate:.2%} errors"
            )

    async def _health_monitor(self) -> None:
        """Monitor daemon and component health."""
        logger.debug("❤️ Starting health monitor...")

        while self._running:
            try:
                await self._health_check()
                await asyncio.sleep(60.0)  # Health check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(60.0)

        logger.debug("❤️ Health monitor stopped")

    async def _health_check(self) -> None:
        """Perform comprehensive health check."""
        try:
            # Check smart home integrations
            if self._smart_home_controller:
                degraded = self._smart_home_controller.get_degraded_integrations()
                if degraded:
                    logger.warning(f"Degraded smart home integrations: {degraded}")

            # Check system resources
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()

            if memory_mb > 500:  # 500MB threshold
                logger.warning(f"High memory usage: {memory_mb:.1f} MB")

            if cpu_percent > 10:  # 10% threshold
                logger.warning(f"High CPU usage: {cpu_percent:.1f}%")

            logger.debug(f"❤️ Health: {memory_mb:.1f}MB RAM, {cpu_percent:.1f}% CPU")

        except Exception as e:
            logger.error(f"Health check error: {e}")


async def main() -> None:
    """Main entry point for the smart home daemon."""
    parser = argparse.ArgumentParser(
        description="Kagami Smart Home Daemon - Persistent Organism Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/smart_home_daemon.py                    # Run interactively
  python scripts/smart_home_daemon.py --daemon          # Run as daemon
  python scripts/smart_home_daemon.py --status          # Check status
  python scripts/smart_home_daemon.py --stop            # Stop daemon

Environment Variables:
  KAGAMI_HOME_DAEMON_LOG_LEVEL     Log level (default: INFO)
  KAGAMI_HOME_DAEMON_SYNC_INTERVAL Sync interval in seconds (default: 2.0)
  KAGAMI_HOME_DAEMON_PID_FILE      PID file location
        """,
    )

    parser.add_argument("--daemon", "-d", action="store_true", help="Run as background daemon")
    parser.add_argument(
        "--pid-file",
        default=os.getenv("KAGAMI_HOME_DAEMON_PID_FILE", "/tmp/kagami_smart_home_daemon.pid"),
        help="PID file location (default: /tmp/kagami_smart_home_daemon.pid)",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("KAGAMI_HOME_DAEMON_LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )
    parser.add_argument(
        "--sync-interval",
        type=float,
        default=float(os.getenv("KAGAMI_HOME_DAEMON_SYNC_INTERVAL", "2.0")),
        help="Sync interval in seconds (default: 2.0)",
    )
    parser.add_argument("--status", action="store_true", help="Check daemon status and exit")
    parser.add_argument("--stop", action="store_true", help="Stop running daemon and exit")

    args = parser.parse_args()

    # Handle status check
    if args.status:
        if os.path.exists(args.pid_file):
            try:
                with open(args.pid_file) as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    print(f"✅ Daemon running (PID: {pid})")
                    return
                except ProcessLookupError:
                    print("❌ Daemon not running (stale PID file)")
                    return
            except (ValueError, FileNotFoundError):
                pass
        print("❌ Daemon not running")
        return

    # Handle stop command
    if args.stop:
        if os.path.exists(args.pid_file):
            try:
                with open(args.pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"✅ Stop signal sent to daemon (PID: {pid})")
                return
            except (ValueError, FileNotFoundError, ProcessLookupError):
                pass
        print("❌ Daemon not running")
        return

    # Create and start daemon
    daemon = SmartHomeDaemon(
        pid_file=args.pid_file,
        log_level=args.log_level,
        sync_interval=args.sync_interval,
        daemon_mode=args.daemon,
    )

    try:
        await daemon.start()

        # Run until stopped
        while daemon._running:
            await asyncio.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Daemon error: {e}")
        return 1
    finally:
        await daemon.stop()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
