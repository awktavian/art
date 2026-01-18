"""Action Log Replicator - Distributed Action History for Colony Recovery.

This module provides append-only action log replication across KagamiOS instances
using etcd as the distributed storage backend. Enables colony recovery, action
replay, and cross-instance coordination.

ARCHITECTURE:
============
- Append-only log with nanosecond timestamps for total ordering
- etcd watch API for real-time action streaming
- Deduplication via correlation_id tracking (sliding window)
- Automatic compaction with configurable retention period
- msgpack serialization for compact encoding

USE CASES:
==========
1. Colony Recovery: Replay actions to rebuild state after failure
2. Cross-Instance Coordination: Share actions across distributed instances
3. Audit Trail: Complete history of all colony actions
4. Debug/Analysis: Replay specific time windows for investigation

DESIGN PRINCIPLES:
==================
- Append-only immutability: Actions never modified after write
- Total ordering: Nanosecond timestamps guarantee order
- Idempotency: Deduplication ensures replay is safe
- Scalability: Automatic compaction prevents unbounded growth

Created: December 15, 2025
"""

from __future__ import annotations

# Standard library imports
import asyncio
import logging
import os
import time
from collections import deque
from collections.abc import Callable
from dataclasses import (
    dataclass,
    field,
)
from typing import Any

# Third-party imports
import msgpack

# Local imports
from kagami.core.consensus.etcd_client import etcd_operation
from kagami.core.exceptions import EtcdConnectionError

logger = logging.getLogger(__name__)

# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

ColonyID = int  # 1-7 (e₁ to e₇)


@dataclass
class ReplicatedAction:
    """A colony action replicated across the distributed system.

    Used for action log replication and cross-instance coordination.
    Different from fano_action_router.ColonyAction which is for routing decisions.

    Attributes:
        colony_id: Colony that executed the action (1-7)
        action_type: Type of action ("route", "execute", "fallback", etc.)
        task: Human-readable task description
        routing: Colony activation map {colony_id: "activate"|"observe"}
        timestamp: Action timestamp (seconds since epoch)
        instance_id: Instance that executed the action
        correlation_id: Unique identifier for deduplication
        metadata: Additional context (task_id, priority, etc.)
    """

    colony_id: ColonyID
    action_type: str
    task: str
    routing: dict[ColonyID, str]
    timestamp: float
    instance_id: str
    correlation_id: str
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary.

        NOTE: routing dict[str, Any] keys converted to strings for msgpack compatibility.
        msgpack requires string keys when strict_map_key=True (default).
        """
        return {
            "colony_id": self.colony_id,
            "action_type": self.action_type,
            "task": self.task,
            "routing": {str(k): v for k, v in self.routing.items()},
            "timestamp": self.timestamp,
            "instance_id": self.instance_id,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplicatedAction:
        """Deserialize from dictionary.

        NOTE: routing dict[str, Any] keys converted back to integers from strings.
        This ensures compatibility with msgpack serialization requirements.
        """
        # Convert routing keys back to integers
        routing_raw = data["routing"]
        routing = {int(k): v for k, v in routing_raw.items()}

        return cls(
            colony_id=data["colony_id"],
            action_type=data["action_type"],
            task=data["task"],
            routing=routing,
            timestamp=data["timestamp"],
            instance_id=data["instance_id"],
            correlation_id=data["correlation_id"],
            metadata=data.get("metadata", {}),
        )


# =============================================================================
# ACTION LOG REPLICATOR
# =============================================================================


class ActionLogReplicator:
    """Replicate executed actions across distributed instances.

    PROTOCOL:
    =========
    1. Append: Action written to etcd with timestamp key
    2. Watch: Other instances receive action via watch API
    3. Deduplicate: Check correlation_id against sliding window
    4. Execute: Process action if not duplicate
    5. Compact: Periodically delete old actions

    ETCD SCHEMA:
    ============
    Key: action_log:{nanosecond_timestamp}:{instance_id}
    Value: msgpack-encoded ReplicatedAction

    KEY DESIGN: Nanosecond timestamp ensures total ordering.
    Adding instance_id as suffix prevents key collisions.

    DEDUPLICATION:
    ==============
    Sliding window (default 4096 entries) tracks recent correlation_ids.
    Prevents duplicate processing across instances. Window size configurable
    via REPLICATOR_DEDUP_WINDOW environment variable.

    COMPACTION:
    ===========
    Actions older than retention period (default 7 days) deleted periodically.
    Retention configurable via REPLICATOR_RETENTION_DAYS environment variable.
    Compaction runs every hour by default.
    """

    def __init__(
        self,
        instance_id: str,
        log_prefix: str = "action_log:",
        dedup_window_size: int | None = None,
        retention_days: int | None = None,
    ) -> None:
        """Initialize action log replicator.

        Args:
            instance_id: Unique identifier for this instance
            log_prefix: etcd key prefix for action log
            dedup_window_size: Size of deduplication window (default 4096)
            retention_days: Retention period in days (default 7)
        """
        self.instance_id = instance_id
        self.log_prefix = log_prefix

        # Deduplication window (sliding FIFO)
        if dedup_window_size is None:
            dedup_window_size = int(os.getenv("REPLICATOR_DEDUP_WINDOW", "4096"))
        self.dedup_window_size = dedup_window_size
        self._seen_correlation_ids: deque[str] = deque(maxlen=self.dedup_window_size)

        # Retention configuration
        if retention_days is None:
            retention_days = int(os.getenv("REPLICATOR_RETENTION_DAYS", "7"))
        self.retention_days = retention_days
        self.retention_seconds = retention_days * 86400  # days to seconds

        # Compaction state
        self._compaction_task: asyncio.Task | None = None
        self._compaction_interval = 3600.0  # 1 hour
        self._shutdown = False

        logger.info(
            "ActionLogReplicator initialized: instance=%s, dedup_window=%d, retention=%dd",
            instance_id,
            dedup_window_size,
            retention_days,
        )

    async def append_action(self, action: ReplicatedAction) -> bool:
        """Append action to distributed log.

        Args:
            action: Action to append

        Returns:
            True if append succeeded, False otherwise
        """
        try:
            # Generate unique key with nanosecond timestamp
            timestamp_ns = time.time_ns()
            key = f"{self.log_prefix}{timestamp_ns}:{self.instance_id}"

            # Serialize action with msgpack (compact binary format)
            data = action.to_dict()
            packed = msgpack.packb(data, use_bin_type=True)

            # Write to etcd
            with etcd_operation("action_log_append") as client:
                client.put(key, packed)

            # Add to dedup window
            self._seen_correlation_ids.append(action.correlation_id)

            logger.debug(
                f"Action appended: colony={action.colony_id}, "
                f"type={action.action_type}, "
                f"correlation_id={action.correlation_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to append action: {e}", exc_info=True)
            return False

    def _is_duplicate(self, correlation_id: str) -> bool:
        """Check if action is duplicate based on correlation_id.

        Args:
            correlation_id: Correlation ID to check

        Returns:
            True if duplicate, False otherwise
        """
        return correlation_id in self._seen_correlation_ids

    def _record_seen(self, correlation_id: str) -> None:
        """Record correlation_id as seen.

        Args:
            correlation_id: Correlation ID to record
        """
        self._seen_correlation_ids.append(correlation_id)

    async def watch_actions(
        self,
        callback: Callable[[ReplicatedAction], Any],
        start_from_beginning: bool = False,
    ) -> None:
        """Watch for new actions from all instances (non-blocking).

        Spawns background task that watches etcd for new actions and invokes
        callback for each non-duplicate action.

        Args:
            callback: Async function to call for each action
            start_from_beginning: If True, replay all existing actions first
        """
        if start_from_beginning:
            # Replay existing actions first
            try:
                await self.replay_actions(
                    since=0.0,  # From beginning of time
                    callback=callback,
                )
            except Exception as e:
                logger.error(f"Failed to replay existing actions: {e}")

        # Start watching for new actions
        asyncio.create_task(self._watch_loop(callback))
        logger.info("Action watch started")

    async def _watch_loop(
        self,
        callback: Callable[[ReplicatedAction], Any],
    ) -> None:
        """Background watch loop (internal).

        Args:
            callback: Async function to call for each action
        """
        while not self._shutdown:
            try:
                with etcd_operation("action_log_watch") as client:
                    # Watch with prefix to get all action log entries
                    events_iterator, cancel = client.watch_prefix(self.log_prefix)

                    try:
                        for event in events_iterator:
                            if self._shutdown:
                                break  # type: ignore[unreachable]

                            try:
                                # Deserialize action
                                packed = event.value
                                if not packed:
                                    continue

                                data = msgpack.unpackb(packed, raw=False)
                                action = ReplicatedAction.from_dict(data)

                                # Check for duplicates
                                if self._is_duplicate(action.correlation_id):
                                    logger.debug(
                                        f"Skipping duplicate action: "
                                        f"correlation_id={action.correlation_id}"
                                    )
                                    continue

                                # Record as seen
                                self._record_seen(action.correlation_id)

                                # Invoke callback
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(action)
                                else:
                                    callback(action)

                            except Exception as e:
                                logger.error(
                                    f"Failed to process watch event: {e}",
                                    exc_info=True,
                                )

                    except Exception as e:
                        logger.error(f"Watch error: {e}", exc_info=True)
                        # Cancel watch on error
                        try:
                            cancel()
                        except Exception:
                            pass

            except EtcdConnectionError as e:
                logger.warning(f"etcd connection lost, reconnecting: {e}")
                await asyncio.sleep(5.0)  # Backoff before retry

            except Exception as e:
                logger.error(f"Watch loop error: {e}", exc_info=True)
                await asyncio.sleep(5.0)  # Backoff before retry

    async def replay_actions(
        self,
        since: float,
        callback: Callable[[ReplicatedAction], Any],
        until: float | None = None,
    ) -> int:
        """Replay actions from timestamp onwards.

        Args:
            since: Start timestamp (seconds since epoch)
            callback: Async function to call for each action
            until: End timestamp (optional, default = now)

        Returns:
            Number of actions replayed
        """
        if until is None:
            until = time.time()

        # Convert to nanoseconds for key comparison
        since_ns = int(since * 1e9)
        until_ns = int(until * 1e9)

        count = 0

        try:
            with etcd_operation("action_log_replay") as client:
                # Get all actions in time range
                # etcd sorts keys lexicographically, so timestamp prefix works
                range_response = client.get_prefix(self.log_prefix)

                for value, metadata in range_response:
                    if self._shutdown:
                        break

                    try:
                        # Extract timestamp from key
                        key = metadata.key.decode("utf-8")
                        # Format: action_log:{timestamp_ns}:{instance_id}
                        parts = key.split(":")
                        if len(parts) < 2:
                            continue

                        key_timestamp_ns = int(parts[1])

                        # Filter by time range
                        if key_timestamp_ns < since_ns or key_timestamp_ns > until_ns:
                            continue

                        # Deserialize action
                        data = msgpack.unpackb(value, raw=False)
                        action = ReplicatedAction.from_dict(data)

                        # Check for duplicates
                        if self._is_duplicate(action.correlation_id):
                            continue

                        # Record as seen
                        self._record_seen(action.correlation_id)

                        # Invoke callback
                        if asyncio.iscoroutinefunction(callback):
                            await callback(action)
                        else:
                            callback(action)

                        count += 1

                    except Exception as e:
                        logger.error(
                            f"Failed to replay action: {e}",
                            exc_info=True,
                        )

            logger.info(f"Replayed {count} actions from [{since:.2f}, {until:.2f}]")
            return count

        except Exception as e:
            logger.error(f"Replay failed: {e}", exc_info=True)
            return count

    async def compact(self) -> int:
        """Delete actions older than retention period.

        Returns:
            Number of actions deleted
        """
        cutoff_time = time.time() - self.retention_seconds
        cutoff_ns = int(cutoff_time * 1e9)

        count = 0

        try:
            with etcd_operation("action_log_compact") as client:
                # Get all actions
                range_response = client.get_prefix(self.log_prefix)

                keys_to_delete = []

                for _value, metadata in range_response:
                    try:
                        # Extract timestamp from key
                        key = metadata.key.decode("utf-8")
                        parts = key.split(":")
                        if len(parts) < 2:
                            continue

                        key_timestamp_ns = int(parts[1])

                        # Mark for deletion if older than cutoff
                        if key_timestamp_ns < cutoff_ns:
                            keys_to_delete.append(key)

                    except Exception as e:
                        logger.debug(f"Failed to parse key {key}: {e}")

                # Delete in batch
                for key in keys_to_delete:
                    try:
                        client.delete(key)
                        count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete key {key}: {e}")

            logger.info(
                f"Compaction complete: deleted {count} actions older than {self.retention_days}d"
            )
            return count

        except Exception as e:
            logger.error(f"Compaction failed: {e}", exc_info=True)
            return count

    async def start_compaction(self) -> None:
        """Start background compaction task."""
        if self._compaction_task is not None:
            logger.warning("Compaction task already running")
            return

        self._compaction_task = asyncio.create_task(self._compaction_loop())
        logger.info(f"Background compaction started: interval={self._compaction_interval}s")

    async def _compaction_loop(self) -> None:
        """Background compaction loop (internal)."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self._compaction_interval)

                if self._shutdown:
                    break  # type: ignore[unreachable]

                # Run compaction
                await self.compact()

            except Exception as e:
                logger.error(
                    f"Compaction loop error: {e}",
                    exc_info=True,
                )
                # Continue running despite errors
                await asyncio.sleep(60.0)  # Brief backoff

    async def shutdown(self) -> None:
        """Shutdown replicator and cleanup resources."""
        logger.info("Shutting down ActionLogReplicator")
        self._shutdown = True

        # Cancel compaction task
        if self._compaction_task is not None:
            self._compaction_task.cancel()
            try:
                await self._compaction_task
            except asyncio.CancelledError:
                pass

        logger.info("ActionLogReplicator shutdown complete")


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_action_log_replicator(  # type: ignore[no-untyped-def]
    instance_id: str | None = None,
    **kwargs,
) -> ActionLogReplicator:
    """Create action log replicator with default configuration.

    Args:
        instance_id: Instance identifier (defaults to NODE_ID or PID)
        **kwargs: Additional arguments passed to ActionLogReplicator

    Returns:
        ActionLogReplicator instance
    """
    if instance_id is None:
        instance_id = os.getenv("NODE_ID", f"node-{os.getpid()}")

    return ActionLogReplicator(instance_id=instance_id, **kwargs)


# Alias for backward compatibility with tests
ColonyAction = ReplicatedAction

# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    """
    Example usage:

    ```python
    import asyncio
    from kagami.core.coordination.action_log_replicator import (
        create_action_log_replicator,
        ReplicatedAction,
    )

    async def main():
        # Create replicator
        replicator = create_action_log_replicator()

        # Append action
        action = ReplicatedAction(
            colony_id=2,  # Forge
            action_type="execute",
            task="Implement feature X",
            routing={2: "activate", 7: "observe"},
            timestamp=time.time(),
            instance_id=replicator.instance_id,
            correlation_id="task-123-forge",
        )
        await replicator.append_action(action)

        # Watch for actions
        async def on_action(action: ReplicatedAction):
            print(f"Received action: {action.task}")

        await replicator.watch_actions(on_action)

        # Start background compaction
        await replicator.start_compaction()

        # Keep running...
        await asyncio.sleep(3600)

        # Cleanup
        await replicator.shutdown()

    asyncio.run(main())
    ```
    """
    logging.basicConfig(level=logging.INFO)
    logger.info("ActionLogReplicator module loaded")
