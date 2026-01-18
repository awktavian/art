"""Unified Persistence Manager — Centralized State Storage.

All SmartHome persistence goes through this module:
- Pattern learning (presence patterns)
- Device registry (visitor detection)
- Spotify credentials (OAuth tokens)
- State snapshots (for recovery)

Storage Location: ~/.kagami/
- patterns.json — Learned presence patterns
- device_registry.json — Known device registry
- spotify_credentials.json — Spotify OAuth
- state_snapshot.json — Last known state
- config.json — User preferences

Architecture:
- Single source of truth for file paths
- Atomic writes (write to temp, then rename)
- Auto-save on interval
- Load on startup

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# PATHS
# =============================================================================

# Base directory for all Kagami persistence
KAGAMI_HOME = Path.home() / ".kagami"

# File paths
PATTERNS_FILE = KAGAMI_HOME / "patterns.json"
DEVICE_REGISTRY_FILE = KAGAMI_HOME / "device_registry.json"
SPOTIFY_CREDENTIALS_FILE = KAGAMI_HOME / "spotify_credentials.json"
STATE_SNAPSHOT_FILE = KAGAMI_HOME / "state_snapshot.json"
CONFIG_FILE = KAGAMI_HOME / "config.json"
SESSION_FILE = KAGAMI_HOME / "session.json"


def ensure_kagami_home() -> Path:
    """Ensure ~/.kagami directory exists."""
    KAGAMI_HOME.mkdir(parents=True, exist_ok=True)
    return KAGAMI_HOME


# =============================================================================
# ATOMIC FILE OPERATIONS
# =============================================================================


def atomic_write_json(path: Path, data: dict[str, Any]) -> bool:
    """Write JSON atomically (write to temp, then rename).

    This prevents corruption if the process is interrupted during write.

    Args:
        path: Target file path
        data: Data to write

    Returns:
        True if successful
    """
    ensure_kagami_home()

    try:
        # Write to temp file in same directory
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.stem}_",
            suffix=".tmp",
        )

        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            shutil.move(temp_path, path)
            return True

        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    except Exception as e:
        logger.error(f"Failed to write {path}: {e}")
        return False


def safe_read_json(path: Path) -> dict[str, Any] | None:
    """Safely read JSON file.

    Args:
        path: File path

    Returns:
        Parsed JSON or None if not found/invalid
    """
    if not path.exists():
        return None

    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {path}: {e}")
        return None


# =============================================================================
# STATE SNAPSHOT
# =============================================================================


@dataclass
class StateSnapshot:
    """Snapshot of system state for persistence/recovery."""

    timestamp: float = field(default_factory=time.time)

    # Presence state
    presence_state: str = "unknown"
    owner_room: str | None = None
    occupied_rooms: list[str] = field(default_factory=list)

    # Device states (last known)
    light_levels: dict[str, int] = field(default_factory=dict)  # room -> level
    shade_positions: dict[str, int] = field(default_factory=dict)  # room -> position

    # Mode states
    guest_mode: str = "none"
    vacation_mode: bool = False

    # Visitor tracking
    active_visitors: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "presence_state": self.presence_state,
            "owner_room": self.owner_room,
            "occupied_rooms": self.occupied_rooms,
            "light_levels": self.light_levels,
            "shade_positions": self.shade_positions,
            "guest_mode": self.guest_mode,
            "vacation_mode": self.vacation_mode,
            "active_visitors": self.active_visitors,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateSnapshot:
        """Create from dictionary."""
        return cls(
            timestamp=data.get("timestamp", time.time()),
            presence_state=data.get("presence_state", "unknown"),
            owner_room=data.get("owner_room"),
            occupied_rooms=data.get("occupied_rooms", []),
            light_levels=data.get("light_levels", {}),
            shade_positions=data.get("shade_positions", {}),
            guest_mode=data.get("guest_mode", "none"),
            vacation_mode=data.get("vacation_mode", False),
            active_visitors=data.get("active_visitors", 0),
        )


# =============================================================================
# SESSION STATE
# =============================================================================


@dataclass
class SessionState:
    """Session state tracking (persisted between restarts)."""

    # Session info
    session_start: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    boot_count: int = 0

    # Learning stats
    total_patterns_learned: int = 0
    total_actions_executed: int = 0

    # Health
    last_health_score: float = 0.0
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_start": self.session_start,
            "last_activity": self.last_activity,
            "boot_count": self.boot_count,
            "total_patterns_learned": self.total_patterns_learned,
            "total_actions_executed": self.total_actions_executed,
            "last_health_score": self.last_health_score,
            "uptime_seconds": self.uptime_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """Create from dictionary."""
        return cls(
            session_start=data.get("session_start", time.time()),
            last_activity=data.get("last_activity", time.time()),
            boot_count=data.get("boot_count", 0),
            total_patterns_learned=data.get("total_patterns_learned", 0),
            total_actions_executed=data.get("total_actions_executed", 0),
            last_health_score=data.get("last_health_score", 0.0),
            uptime_seconds=data.get("uptime_seconds", 0.0),
        )


# =============================================================================
# PERSISTENCE MANAGER
# =============================================================================


class PersistenceManager:
    """Unified persistence manager for all SmartHome state.

    Provides:
    - Centralized file paths
    - Atomic writes
    - Auto-save on interval
    - State snapshots
    - Pattern persistence

    Usage:
        manager = PersistenceManager(controller)
        await manager.start()

        # Manual save
        manager.save_patterns()
        manager.save_state_snapshot()

        # Stop (saves all)
        await manager.stop()
    """

    def __init__(self, controller: SmartHomeController | None = None):
        self.controller = controller

        # State tracking
        self._state_snapshot = StateSnapshot()
        self._session_state = SessionState()

        # Auto-save configuration
        self._auto_save_interval = 300.0  # 5 minutes
        self._running = False
        self._auto_save_task: asyncio.Task | None = None

        # Track what's dirty (needs saving)
        self._dirty: set[str] = set()

        # Load session state
        self._load_session()

    def _load_session(self) -> None:
        """Load session state from disk."""
        data = safe_read_json(SESSION_FILE)
        if data:
            self._session_state = SessionState.from_dict(data)
            self._session_state.boot_count += 1
            self._session_state.session_start = time.time()
            logger.info(f"📊 Session loaded (boot #{self._session_state.boot_count})")
        else:
            self._session_state = SessionState()
            self._session_state.boot_count = 1

    async def start(self) -> None:
        """Start persistence manager with auto-save."""
        if self._running:
            return

        self._running = True

        # Load last state snapshot
        self.load_state_snapshot()

        # Load patterns if controller has presence engine
        if self.controller:
            self.load_patterns()

        # Start auto-save loop
        self._auto_save_task = asyncio.create_task(self._auto_save_loop())

        logger.info("💾 Persistence manager started (auto-save every 5 min)")

    async def stop(self) -> None:
        """Stop persistence manager and save all."""
        self._running = False

        if self._auto_save_task:
            self._auto_save_task.cancel()
            try:
                await self._auto_save_task
            except asyncio.CancelledError:
                pass

        # Final save
        self.save_all()

        logger.info("💾 Persistence manager stopped")

    async def _auto_save_loop(self) -> None:
        """Auto-save loop."""
        while self._running:
            try:
                await asyncio.sleep(self._auto_save_interval)

                if self._dirty:
                    self.save_dirty()

                # Always save session state
                self.save_session()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-save error: {e}")
                await asyncio.sleep(60)

    def mark_dirty(self, category: str) -> None:
        """Mark a category as needing save.

        Categories: "patterns", "state", "session"
        """
        self._dirty.add(category)

    def save_dirty(self) -> None:
        """Save all dirty categories."""
        if "patterns" in self._dirty:
            self.save_patterns()
        if "state" in self._dirty:
            self.save_state_snapshot()
        if "session" in self._dirty:
            self.save_session()

        self._dirty.clear()

    def save_all(self) -> None:
        """Save everything."""
        self.save_patterns()
        self.save_state_snapshot()
        self.save_session()
        self._dirty.clear()
        logger.info("💾 All state saved")

    # =========================================================================
    # PATTERNS
    # =========================================================================

    def save_patterns(self) -> bool:
        """Save presence patterns."""
        if not self.controller:
            return False

        try:
            presence = self.controller._presence
            return presence.save_patterns(str(PATTERNS_FILE))
        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")
            return False

    def load_patterns(self) -> bool:
        """Load presence patterns."""
        if not self.controller:
            return False

        try:
            if PATTERNS_FILE.exists():
                presence = self.controller._presence
                return presence.load_patterns(str(PATTERNS_FILE))
            return False
        except Exception as e:
            logger.error(f"Failed to load patterns: {e}")
            return False

    # =========================================================================
    # STATE SNAPSHOT
    # =========================================================================

    def capture_state_snapshot(self) -> StateSnapshot:
        """Capture current state snapshot."""
        if not self.controller:
            return self._state_snapshot

        try:
            state = self.controller.get_state()

            self._state_snapshot = StateSnapshot(
                presence_state=state.presence.value if state.presence else "unknown",
                owner_room=state.owner_room,
                occupied_rooms=state.occupied_rooms or [],
            )

            # Get modes from advanced automation
            try:
                from kagami_smarthome.advanced_automation import get_advanced_automation

                manager = get_advanced_automation(self.controller)
                status = manager.get_status()

                self._state_snapshot.guest_mode = status.get("guest_mode", {}).get("mode", "none")
                self._state_snapshot.vacation_mode = status.get("vacation_mode", {}).get(
                    "active", False
                )
            except Exception:
                pass

            # Get visitor count
            try:
                from kagami_smarthome.visitor_detection import get_visitor_detector

                detector = get_visitor_detector(self.controller)
                self._state_snapshot.active_visitors = detector.get_visitor_count()
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Failed to capture state: {e}")

        return self._state_snapshot

    def save_state_snapshot(self) -> bool:
        """Save state snapshot to disk."""
        self.capture_state_snapshot()
        return atomic_write_json(STATE_SNAPSHOT_FILE, self._state_snapshot.to_dict())

    def load_state_snapshot(self) -> StateSnapshot | None:
        """Load state snapshot from disk."""
        data = safe_read_json(STATE_SNAPSHOT_FILE)
        if data:
            self._state_snapshot = StateSnapshot.from_dict(data)
            return self._state_snapshot
        return None

    def get_state_snapshot(self) -> StateSnapshot:
        """Get current state snapshot."""
        return self._state_snapshot

    # =========================================================================
    # SESSION
    # =========================================================================

    def save_session(self) -> bool:
        """Save session state."""
        self._session_state.last_activity = time.time()

        if self._session_state.session_start > 0:
            self._session_state.uptime_seconds = time.time() - self._session_state.session_start

        return atomic_write_json(SESSION_FILE, self._session_state.to_dict())

    def get_session(self) -> SessionState:
        """Get session state."""
        return self._session_state

    def record_action(self) -> None:
        """Record that an action was executed."""
        self._session_state.total_actions_executed += 1
        self._session_state.last_activity = time.time()

    def record_pattern_learned(self) -> None:
        """Record that a pattern was learned."""
        self._session_state.total_patterns_learned += 1
        self.mark_dirty("patterns")

    def update_health_score(self, score: float) -> None:
        """Update last health score."""
        self._session_state.last_health_score = score

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get persistence manager status."""
        return {
            "running": self._running,
            "kagami_home": str(KAGAMI_HOME),
            "files": {
                "patterns": PATTERNS_FILE.exists(),
                "device_registry": DEVICE_REGISTRY_FILE.exists(),
                "state_snapshot": STATE_SNAPSHOT_FILE.exists(),
                "session": SESSION_FILE.exists(),
                "spotify": SPOTIFY_CREDENTIALS_FILE.exists(),
            },
            "session": {
                "boot_count": self._session_state.boot_count,
                "uptime_seconds": time.time() - self._session_state.session_start,
                "total_actions": self._session_state.total_actions_executed,
                "total_patterns": self._session_state.total_patterns_learned,
            },
            "dirty": list(self._dirty),
            "auto_save_interval": self._auto_save_interval,
        }


# =============================================================================
# FACTORY
# =============================================================================

_persistence_manager: PersistenceManager | None = None


def get_persistence_manager(controller: SmartHomeController | None = None) -> PersistenceManager:
    """Get or create persistence manager."""
    global _persistence_manager

    if _persistence_manager is None:
        _persistence_manager = PersistenceManager(controller)

    return _persistence_manager


async def start_persistence(controller: SmartHomeController) -> PersistenceManager:
    """Start persistence manager.

    Args:
        controller: SmartHomeController instance

    Returns:
        Running PersistenceManager
    """
    manager = get_persistence_manager(controller)
    manager.controller = controller
    await manager.start()
    return manager


# =============================================================================
# PATH HELPERS
# =============================================================================


def get_patterns_path() -> Path:
    """Get patterns file path."""
    return PATTERNS_FILE


def get_device_registry_path() -> Path:
    """Get device registry file path."""
    return DEVICE_REGISTRY_FILE


def get_spotify_credentials_path() -> Path:
    """Get Spotify credentials file path."""
    return SPOTIFY_CREDENTIALS_FILE


def get_state_snapshot_path() -> Path:
    """Get state snapshot file path."""
    return STATE_SNAPSHOT_FILE


__all__ = [
    # Paths
    "KAGAMI_HOME",
    "PATTERNS_FILE",
    "DEVICE_REGISTRY_FILE",
    "SPOTIFY_CREDENTIALS_FILE",
    "STATE_SNAPSHOT_FILE",
    "CONFIG_FILE",
    "SESSION_FILE",
    # Path helpers
    "ensure_kagami_home",
    "get_patterns_path",
    "get_device_registry_path",
    "get_spotify_credentials_path",
    "get_state_snapshot_path",
    # File operations
    "atomic_write_json",
    "safe_read_json",
    # Data classes
    "StateSnapshot",
    "SessionState",
    # Manager
    "PersistenceManager",
    "get_persistence_manager",
    "start_persistence",
]
