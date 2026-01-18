"""Offline Cache Layer for Client Applications.

Provides SQLite-based local caching for client apps to function offline:
- Last-known device states
- Command queue for offline actions
- Sync protocol with conflict resolution
- Per-user preference caching

This module is designed to be used by client apps (iOS, Android, Desktop, etc.)
to maintain functionality when the API server is unreachable.

Usage:
    from kagami.core.caching.offline import OfflineCache

    # Initialize cache for a user
    cache = OfflineCache(user_id="user-123", db_path="/tmp/kagami-cache.db")
    await cache.initialize()

    # Store device state
    await cache.store_device_state("light-1", {"on": True, "brightness": 50})

    # Queue offline command
    await cache.queue_command({
        "action": "set_lights",
        "params": {"brightness": 75, "rooms": ["Living Room"]}
    })

    # Sync with server when online
    result = await cache.sync_with_server(api_client)

Created: January 1, 2026
Part of: Apps 100/100 Transformation - Phase 1.3
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class SyncStatus(str, Enum):
    """Status of a queued command."""

    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictResolution(str, Enum):
    """Conflict resolution strategy."""

    SERVER_WINS = "server_wins"  # Default - server state takes precedence
    CLIENT_WINS = "client_wins"  # Client state takes precedence
    MERGE = "merge"  # Attempt to merge both states
    NOTIFY = "notify"  # Keep both, notify user


@dataclass
class QueuedCommand:
    """A command queued for execution when online."""

    id: str
    action: str
    params: dict[str, Any]
    created_at: datetime
    status: SyncStatus = SyncStatus.PENDING
    attempts: int = 0
    last_attempt: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "action": self.action,
            "params": self.params,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "attempts": self.attempts,
            "last_attempt": self.last_attempt.isoformat() if self.last_attempt else None,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueuedCommand:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            action=data["action"],
            params=data["params"],
            created_at=datetime.fromisoformat(data["created_at"]),
            status=SyncStatus(data["status"]),
            attempts=data.get("attempts", 0),
            last_attempt=datetime.fromisoformat(data["last_attempt"])
            if data.get("last_attempt")
            else None,
            error=data.get("error"),
        )


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    synced_commands: int = 0
    failed_commands: int = 0
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    updated_devices: int = 0
    errors: list[str] = field(default_factory=list)


class APIClientProtocol(Protocol):
    """Protocol for API client (for type hints)."""

    async def execute_command(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a command on the server."""
        ...

    async def get_device_states(self) -> dict[str, dict[str, Any]]:
        """Get all device states from server."""
        ...

    async def get_home_state(self) -> dict[str, Any]:
        """Get complete home state from server."""
        ...


class OfflineCache:
    """SQLite-based offline cache for client applications.

    Provides:
    - Device state caching (last-known state)
    - Command queue for offline actions
    - Sync with server when online
    - Conflict resolution
    - User preference caching

    Thread-safe through connection-per-operation pattern.
    """

    def __init__(
        self,
        user_id: str,
        db_path: str | Path | None = None,
        conflict_resolution: ConflictResolution = ConflictResolution.SERVER_WINS,
        max_queue_age_hours: int = 24,
        max_retries: int = 3,
    ):
        """Initialize offline cache.

        Args:
            user_id: User identifier
            db_path: Path to SQLite database. If None, uses default location.
            conflict_resolution: Default conflict resolution strategy
            max_queue_age_hours: Max age of queued commands before expiry
            max_retries: Max retry attempts for failed commands
        """
        self.user_id = user_id
        self.conflict_resolution = conflict_resolution
        self.max_queue_age_hours = max_queue_age_hours
        self.max_retries = max_retries

        if db_path is None:
            # Default to user-specific database in temp directory
            db_path = Path("/tmp") / f"kagami-cache-{user_id}.db"
        self.db_path = Path(db_path)

        self._initialized = False
        self._lock = asyncio.Lock()

        # Callbacks for sync events
        self._on_sync_complete: Callable[[SyncResult], None] | None = None
        self._on_conflict: Callable[[dict[str, Any]], ConflictResolution] | None = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get a new database connection.

        Each operation uses its own connection for thread safety.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    async def initialize(self) -> None:
        """Initialize the database schema."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            conn = self._get_connection()
            try:
                cursor = conn.cursor()

                # Device states table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS device_states (
                        device_id TEXT PRIMARY KEY,
                        state TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        server_updated_at TEXT
                    )
                """
                )

                # Command queue table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS command_queue (
                        id TEXT PRIMARY KEY,
                        action TEXT NOT NULL,
                        params TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        attempts INTEGER DEFAULT 0,
                        last_attempt TEXT,
                        error TEXT
                    )
                """
                )

                # User preferences table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS preferences (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """
                )

                # Home state snapshot
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS home_state (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        state TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """
                )

                # Sync log for auditing
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sync_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        action TEXT NOT NULL,
                        success INTEGER NOT NULL,
                        details TEXT
                    )
                """
                )

                # Create indexes
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_queue_status ON command_queue(status)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_queue_created ON command_queue(created_at)"
                )

                conn.commit()
                self._initialized = True
                logger.info(f"Offline cache initialized at: {self.db_path}")

            finally:
                conn.close()

    async def store_device_state(
        self,
        device_id: str,
        state: dict[str, Any],
        server_updated_at: datetime | None = None,
    ) -> None:
        """Store a device's state in the local cache.

        Args:
            device_id: Device identifier
            state: Device state dictionary
            server_updated_at: When the server last updated this state
        """
        await self.initialize()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO device_states
                (device_id, state, updated_at, server_updated_at)
                VALUES (?, ?, ?, ?)
            """,
                (
                    device_id,
                    json.dumps(state),
                    datetime.utcnow().isoformat(),
                    server_updated_at.isoformat() if server_updated_at else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def get_device_state(self, device_id: str) -> dict[str, Any] | None:
        """Get a device's cached state.

        Args:
            device_id: Device identifier

        Returns:
            Device state dictionary or None if not cached
        """
        await self.initialize()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT state FROM device_states WHERE device_id = ?", (device_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["state"])
            return None
        finally:
            conn.close()

    async def get_all_device_states(self) -> dict[str, dict[str, Any]]:
        """Get all cached device states.

        Returns:
            Dictionary mapping device_id to state
        """
        await self.initialize()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT device_id, state FROM device_states")
            rows = cursor.fetchall()
            return {row["device_id"]: json.loads(row["state"]) for row in rows}
        finally:
            conn.close()

    async def queue_command(self, command: dict[str, Any]) -> str:
        """Queue a command for execution when online.

        Args:
            command: Command dictionary with 'action' and 'params'

        Returns:
            Command ID
        """
        await self.initialize()

        command_id = str(uuid.uuid4())
        queued = QueuedCommand(
            id=command_id,
            action=command["action"],
            params=command.get("params", {}),
            created_at=datetime.utcnow(),
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO command_queue
                (id, action, params, created_at, status)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    queued.id,
                    queued.action,
                    json.dumps(queued.params),
                    queued.created_at.isoformat(),
                    queued.status.value,
                ),
            )
            conn.commit()
            logger.info(f"Queued offline command: {command_id} ({command['action']})")
            return command_id
        finally:
            conn.close()

    async def get_pending_commands(self) -> list[QueuedCommand]:
        """Get all pending commands in the queue.

        Returns:
            List of pending commands ordered by creation time
        """
        await self.initialize()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM command_queue
                WHERE status IN ('pending', 'failed')
                ORDER BY created_at ASC
            """
            )
            rows = cursor.fetchall()

            commands = []
            for row in rows:
                cmd = QueuedCommand(
                    id=row["id"],
                    action=row["action"],
                    params=json.loads(row["params"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    status=SyncStatus(row["status"]),
                    attempts=row["attempts"] or 0,
                    last_attempt=datetime.fromisoformat(row["last_attempt"])
                    if row["last_attempt"]
                    else None,
                    error=row["error"],
                )
                commands.append(cmd)

            return commands
        finally:
            conn.close()

    async def update_command_status(
        self,
        command_id: str,
        status: SyncStatus,
        error: str | None = None,
    ) -> None:
        """Update the status of a queued command.

        Args:
            command_id: Command identifier
            status: New status
            error: Error message if failed
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE command_queue
                SET status = ?, attempts = attempts + 1, last_attempt = ?, error = ?
                WHERE id = ?
            """,
                (
                    status.value,
                    datetime.utcnow().isoformat(),
                    error,
                    command_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def remove_command(self, command_id: str) -> None:
        """Remove a command from the queue.

        Args:
            command_id: Command identifier
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM command_queue WHERE id = ?", (command_id,))
            conn.commit()
        finally:
            conn.close()

    async def cleanup_expired_commands(self) -> int:
        """Remove expired commands from the queue.

        Returns:
            Number of commands removed
        """
        await self.initialize()

        cutoff = datetime.utcnow() - timedelta(hours=self.max_queue_age_hours)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM command_queue WHERE created_at < ?", (cutoff.isoformat(),))
            removed = cursor.rowcount
            conn.commit()

            if removed > 0:
                logger.info(f"Cleaned up {removed} expired commands")

            return removed
        finally:
            conn.close()

    async def store_home_state(self, state: dict[str, Any]) -> None:
        """Store a complete home state snapshot.

        Args:
            state: Complete home state from server
        """
        await self.initialize()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO home_state (id, state, updated_at)
                VALUES (1, ?, ?)
            """,
                (
                    json.dumps(state),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def get_home_state(self) -> dict[str, Any] | None:
        """Get the cached home state snapshot.

        Returns:
            Home state dictionary or None if not cached
        """
        await self.initialize()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT state FROM home_state WHERE id = 1")
            row = cursor.fetchone()
            if row:
                return json.loads(row["state"])
            return None
        finally:
            conn.close()

    async def store_preference(self, key: str, value: Any) -> None:
        """Store a user preference.

        Args:
            key: Preference key
            value: Preference value (will be JSON serialized)
        """
        await self.initialize()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO preferences (key, value, updated_at)
                VALUES (?, ?, ?)
            """,
                (
                    key,
                    json.dumps(value),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference.

        Args:
            key: Preference key
            default: Default value if not found

        Returns:
            Preference value or default
        """
        await self.initialize()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["value"])
            return default
        finally:
            conn.close()

    async def sync_with_server(
        self,
        api_client: APIClientProtocol,
    ) -> SyncResult:
        """Sync offline changes with the server.

        This method:
        1. Cleans up expired commands
        2. Processes pending commands in order
        3. Fetches latest device states
        4. Resolves any conflicts

        Args:
            api_client: API client for server communication

        Returns:
            SyncResult with sync statistics
        """
        result = SyncResult(success=True)

        try:
            # Clean up expired commands
            await self.cleanup_expired_commands()

            # Get pending commands
            commands = await self.get_pending_commands()

            # Process each command
            for cmd in commands:
                # Skip if too many retries
                if cmd.attempts >= self.max_retries:
                    await self.update_command_status(
                        cmd.id, SyncStatus.FAILED, f"Max retries ({self.max_retries}) exceeded"
                    )
                    result.failed_commands += 1
                    continue

                # Mark as syncing
                await self.update_command_status(cmd.id, SyncStatus.SYNCING)

                try:
                    # Execute command
                    await api_client.execute_command(cmd.action, cmd.params)

                    # Success - remove from queue
                    await self.remove_command(cmd.id)
                    result.synced_commands += 1
                    logger.debug(f"Synced command: {cmd.id}")

                except Exception as e:
                    # Failed - mark for retry
                    error_msg = str(e)
                    await self.update_command_status(cmd.id, SyncStatus.FAILED, error_msg)
                    result.failed_commands += 1
                    result.errors.append(f"Command {cmd.id} failed: {error_msg}")
                    logger.warning(f"Command sync failed: {cmd.id} - {error_msg}")

            # Fetch latest device states from server
            try:
                server_states = await api_client.get_device_states()

                for device_id, server_state in server_states.items():
                    # Get local state
                    local_state = await self.get_device_state(device_id)

                    if local_state is not None:
                        # Check for conflicts
                        conflict = self._detect_conflict(local_state, server_state)
                        if conflict:
                            resolution = self._resolve_conflict(
                                device_id, local_state, server_state
                            )
                            result.conflicts.append(
                                {
                                    "device_id": device_id,
                                    "local_state": local_state,
                                    "server_state": server_state,
                                    "resolution": resolution,
                                }
                            )

                            if resolution == ConflictResolution.SERVER_WINS:
                                await self.store_device_state(
                                    device_id, server_state, datetime.utcnow()
                                )
                            # CLIENT_WINS: keep local state
                            # NOTIFY: callback handles it
                    else:
                        # No local state, just store server state
                        await self.store_device_state(device_id, server_state, datetime.utcnow())

                    result.updated_devices += 1

            except Exception as e:
                result.errors.append(f"Failed to fetch device states: {e}")
                logger.error(f"Device state fetch failed: {e}")

            # Fetch full home state snapshot
            try:
                home_state = await api_client.get_home_state()
                await self.store_home_state(home_state)
            except Exception as e:
                result.errors.append(f"Failed to fetch home state: {e}")
                logger.warning(f"Home state fetch failed: {e}")

            # Log sync operation
            await self._log_sync(
                "sync",
                result.success,
                json.dumps(
                    {
                        "synced": result.synced_commands,
                        "failed": result.failed_commands,
                        "conflicts": len(result.conflicts),
                    }
                ),
            )

            # Call completion callback
            if self._on_sync_complete:
                self._on_sync_complete(result)

            return result

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error(f"Sync failed: {e}")
            return result

    def _detect_conflict(
        self,
        local_state: dict[str, Any],
        server_state: dict[str, Any],
    ) -> bool:
        """Detect if there's a conflict between local and server state.

        Simple conflict detection based on state differences.
        More sophisticated detection could use timestamps or vector clocks.
        """
        # Check key differences
        local_keys = set(local_state.keys())
        server_keys = set(server_state.keys())

        # If different keys, potential conflict
        if local_keys != server_keys:
            return True

        # Check value differences for common keys
        for key in local_keys:
            if local_state[key] != server_state[key]:
                return True

        return False

    def _resolve_conflict(
        self,
        device_id: str,
        local_state: dict[str, Any],
        server_state: dict[str, Any],
    ) -> ConflictResolution:
        """Resolve a conflict between local and server state.

        Uses the configured resolution strategy, or calls the callback
        if NOTIFY is selected.
        """
        # Check if there's a custom conflict handler
        if self._on_conflict:
            try:
                return self._on_conflict(
                    {
                        "device_id": device_id,
                        "local_state": local_state,
                        "server_state": server_state,
                    }
                )
            except Exception as e:
                logger.error(f"Conflict handler error: {e}")

        # Use default resolution strategy
        return self.conflict_resolution

    async def _log_sync(self, action: str, success: bool, details: str) -> None:
        """Log a sync operation."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sync_log (timestamp, action, success, details)
                VALUES (?, ?, ?, ?)
            """,
                (
                    datetime.utcnow().isoformat(),
                    action,
                    1 if success else 0,
                    details,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def get_sync_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent sync history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of sync log entries
        """
        await self.initialize()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM sync_log ORDER BY timestamp DESC LIMIT ?
            """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    async def clear_all(self) -> None:
        """Clear all cached data.

        Use with caution - this removes all offline data.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM device_states")
            cursor.execute("DELETE FROM command_queue")
            cursor.execute("DELETE FROM preferences")
            cursor.execute("DELETE FROM home_state")
            conn.commit()
            logger.info("Cleared all offline cache data")
        finally:
            conn.close()

    def on_sync_complete(self, callback: Callable[[SyncResult], None]) -> None:
        """Register a callback for sync completion.

        Args:
            callback: Function called with SyncResult when sync completes
        """
        self._on_sync_complete = callback

    def on_conflict(self, callback: Callable[[dict[str, Any]], ConflictResolution]) -> None:
        """Register a callback for conflict resolution.

        Args:
            callback: Function that receives conflict info and returns resolution
        """
        self._on_conflict = callback


# Convenience factory function
_caches: dict[str, OfflineCache] = {}


def get_offline_cache(
    user_id: str,
    db_path: str | Path | None = None,
) -> OfflineCache:
    """Get or create an offline cache for a user.

    This is a convenience factory that maintains a cache per user.

    Args:
        user_id: User identifier
        db_path: Optional custom database path

    Returns:
        OfflineCache instance
    """
    if user_id not in _caches:
        _caches[user_id] = OfflineCache(user_id=user_id, db_path=db_path)
    return _caches[user_id]


__all__ = [
    "ConflictResolution",
    "OfflineCache",
    "QueuedCommand",
    "SyncResult",
    "SyncStatus",
    "get_offline_cache",
]
