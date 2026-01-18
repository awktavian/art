#!/usr/bin/env python3
"""
鏡 Kagami API Launcher

Production-grade launcher with:
- Single instance enforcement (pidfile lock)
- Proper logging to files with rotation
- Environment loading from .env
- Graceful shutdown handling
- Health monitoring

Usage:
    python scripts/kagami_api_launcher.py [--port PORT] [--workers WORKERS]

LaunchAgent:
    ~/Library/LaunchAgents/com.kagami.api.plist
"""

from __future__ import annotations

import argparse
import atexit
import fcntl
import logging
import os
import signal
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

KAGAMI_ROOT = Path(__file__).parent.parent.resolve()
SATELLITES_API = KAGAMI_ROOT / "packages" / "kagami_api"
RUN_DIR = KAGAMI_ROOT / "run"
LOG_DIR = KAGAMI_ROOT / "logs"
PID_FILE = RUN_DIR / "kagami-api.pid"
LOCK_FILE = RUN_DIR / "kagami-api.lock"

DEFAULT_PORT = 8001
DEFAULT_HOST = "0.0.0.0"
DEFAULT_WORKERS = 1  # Single worker for development, increase for production
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

# =============================================================================
# LOGGING SETUP
# =============================================================================


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging with file rotation."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create formatters
    detailed_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    simple_fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler (for LaunchAgent stdout capture)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(simple_fmt)
    root_logger.addHandler(console)

    # File handler with rotation
    log_file = LOG_DIR / "kagami-api.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_fmt)
    root_logger.addHandler(file_handler)

    # Error log (separate file for errors only)
    error_file = LOG_DIR / "kagami-api-error.log"
    error_handler = RotatingFileHandler(
        error_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_fmt)
    root_logger.addHandler(error_handler)

    return logging.getLogger("kagami.api.launcher")


# =============================================================================
# SINGLE INSTANCE ENFORCEMENT
# =============================================================================


class SingleInstance:
    """Ensure only one instance of the API runs at a time."""

    def __init__(self, lock_path: Path, pid_path: Path):
        self.lock_path = lock_path
        self.pid_path = pid_path
        self.lock_file = None
        self.locked = False

    def acquire(self) -> bool:
        """Attempt to acquire the lock. Returns True if successful."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.lock_file = open(self.lock_path, "w")
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.locked = True

            # Write PID file
            self.pid_path.write_text(str(os.getpid()))

            return True
        except OSError:
            # Lock already held by another process
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False

    def release(self):
        """Release the lock and clean up."""
        if self.locked and self.lock_file:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
            except Exception:
                pass
            self.locked = False

        # Clean up files
        for path in [self.lock_path, self.pid_path]:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

    def get_existing_pid(self) -> int | None:
        """Get the PID of an existing instance, if any."""
        if self.pid_path.exists():
            try:
                return int(self.pid_path.read_text().strip())
            except (ValueError, OSError):
                pass
        return None

    def __enter__(self):
        if not self.acquire():
            existing_pid = self.get_existing_pid()
            raise RuntimeError(
                f"Another instance is already running (PID: {existing_pid or 'unknown'})"
            )
        return self

    def __exit__(self, *args):
        self.release()


# =============================================================================
# ENVIRONMENT SETUP
# =============================================================================


def load_environment():
    """Load environment variables from .env file."""
    env_file = KAGAMI_ROOT / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value

    # Ensure PYTHONPATH includes our paths
    python_paths = [
        str(KAGAMI_ROOT),
        str(SATELLITES_API),
    ]
    existing = os.environ.get("PYTHONPATH", "").split(":") if os.environ.get("PYTHONPATH") else []
    combined = python_paths + [p for p in existing if p and p not in python_paths]
    os.environ["PYTHONPATH"] = ":".join(combined)

    # Add to sys.path for this process
    for p in python_paths:
        if p not in sys.path:
            sys.path.insert(0, p)


# =============================================================================
# SERVER MANAGEMENT
# =============================================================================


def run_server(host: str, port: int, workers: int, log_level: str):
    """Run the uvicorn server."""
    import uvicorn

    # Change to API directory for proper imports
    os.chdir(SATELLITES_API)

    uvicorn.run(
        "kagami_api.main:app",
        host=host,
        port=port,
        workers=workers,
        log_level=log_level.lower(),
        access_log=True,
        loop="auto",
        http="auto",
    )


# =============================================================================
# SIGNAL HANDLERS
# =============================================================================

shutdown_requested = False


def handle_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    signal_name = signal.Signals(signum).name
    logging.getLogger("kagami.api.launcher").info(f"Received {signal_name}, shutting down...")
    shutdown_requested = True
    sys.exit(0)


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Kagami API Launcher",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Number of workers")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    parser.add_argument("--check", action="store_true", help="Check if instance is running")
    parser.add_argument("--stop", action="store_true", help="Stop running instance")

    args = parser.parse_args()

    # Handle check/stop commands
    if args.check:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                os.kill(pid, 0)  # Check if process exists
                print(f"Kagami API is running (PID: {pid})")
                sys.exit(0)
            except OSError:
                print("Kagami API is not running (stale PID file)")
                sys.exit(1)
        else:
            print("Kagami API is not running")
            sys.exit(1)

    if args.stop:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to PID {pid}")
                # Wait for process to exit
                for _ in range(30):
                    try:
                        os.kill(pid, 0)
                        time.sleep(0.1)
                    except OSError:
                        print("Process stopped")
                        sys.exit(0)
                print("Process did not stop, sending SIGKILL")
                os.kill(pid, signal.SIGKILL)
                sys.exit(0)
            except OSError:
                print("Process not running")
                sys.exit(1)
        else:
            print("No PID file found")
            sys.exit(1)

    # Create directories
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Setup logging
    logger = setup_logging(args.log_level)

    # Load environment
    load_environment()

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Acquire single instance lock
    instance = SingleInstance(LOCK_FILE, PID_FILE)

    try:
        with instance:
            logger.info("=" * 60)
            logger.info("鏡 Kagami API Starting")
            logger.info("=" * 60)
            logger.info(f"PID: {os.getpid()}")
            logger.info(f"Host: {args.host}:{args.port}")
            logger.info(f"Workers: {args.workers}")
            logger.info(f"Log Level: {args.log_level}")
            logger.info(f"Log Dir: {LOG_DIR}")
            logger.info(f"API Dir: {SATELLITES_API}")
            logger.info("=" * 60)

            # Register cleanup
            atexit.register(instance.release)

            # Run server
            run_server(args.host, args.port, args.workers, args.log_level)

    except RuntimeError as e:
        logger.error(f"Failed to start: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
