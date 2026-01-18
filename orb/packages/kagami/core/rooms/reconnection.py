from __future__ import annotations

"""Reconnection Handling for Rooms with Smart State Catchup.

Handles client reconnections efficiently by choosing between:
- Delta catchup: Send missed operations (for small gaps)
- Full snapshot: Send complete state (for large gaps)

Design Goals:
    - Minimize bandwidth for common reconnection cases
    - Ensure clients always get complete, consistent state
    - Handle edge cases (missing deltas, sequence gaps)

Threshold Strategy:
    - < SNAPSHOT_THRESHOLD missed ops → Send deltas
    - >= SNAPSHOT_THRESHOLD missed ops → Send snapshot

    This balances bandwidth (deltas are smaller) against complexity
    (more deltas = more risk of inconsistency).

Example:
    >>> manager = get_reconnection_manager()
    >>> result = await manager.handle_reconnection(
    ...     room_id="room-123",
    ...     client_id="client-456",
    ...     last_ack_seq=100,  # Client's last known sequence
    ... )
    >>> if result.status == "catchup":
    ...     # Send deltas to client
    ...     await send_deltas(result.deltas)
    >>> elif result.status == "snapshot":
    ...     # Send full snapshot
    ...     await send_snapshot(result.snapshot)
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import logging  # Error and info logging
from dataclasses import dataclass  # Clean data structures
from typing import Any  # Type hints

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================
# If client is more than SNAPSHOT_THRESHOLD ops behind, send full snapshot.
# This threshold balances bandwidth vs. complexity.
SNAPSHOT_THRESHOLD = 50

# Maximum deltas to include in a catchup response.
# Prevents extremely large responses.
MAX_CATCHUP_DELTAS = 100


# =============================================================================
# RECONNECTION RESULT
# =============================================================================


@dataclass
class ReconnectionResult:
    """Result of a reconnection attempt.

    Contains either deltas (for catchup) or snapshot (for full sync),
    plus metadata about the reconnection.

    Attributes:
        status: "current" | "catchup" | "snapshot" | "error"
        current_seq: Current room sequence number.
        deltas: List of missed operations (if status="catchup").
        snapshot: Full room state (if status="snapshot").
        message: Human-readable status message.

    Example:
        >>> result = ReconnectionResult(
        ...     status="catchup",
        ...     current_seq=150,
        ...     deltas=[{"op_id": "1", ...}, {"op_id": "2", ...}],
        ...     message="Caught up with 2 updates",
        ... )
    """

    status: str  # "current", "catchup", "snapshot", or "error"
    current_seq: int  # Current room sequence number
    deltas: list[dict[str, Any]] | None = None  # Missed operations
    snapshot: dict[str, Any] | None = None  # Full state (if snapshot)
    message: str | None = None  # Human-readable message

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict with status, seq, and deltas or snapshot as appropriate.
        """
        result = {
            "status": self.status,
            "current_seq": self.current_seq,
            "message": self.message,
        }
        # Include deltas if present
        if self.deltas is not None:
            result["deltas"] = self.deltas
            result["delta_count"] = len(self.deltas)
        # Include snapshot if present
        if self.snapshot is not None:
            result["snapshot"] = self.snapshot
        return result


# =============================================================================
# RECONNECTION MANAGER
# =============================================================================


class ReconnectionManager:
    """Manages client reconnections with efficient state catchup.

    Tracks reconnection statistics and makes smart decisions about
    whether to send deltas or full snapshots based on how far behind
    the client is.

    Attributes:
        reconnection_count: Total reconnection attempts handled.
        snapshot_sent_count: Times full snapshot was sent.
        catchup_sent_count: Times delta catchup was sent.

    Thread Safety:
        Statistics are NOT thread-safe. For accurate stats in
        multi-threaded environments, use atomic counters or locks.

    Example:
        >>> manager = ReconnectionManager()
        >>> result = await manager.handle_reconnection(
        ...     "room-123", "client-456", last_ack_seq=100
        ... )
        >>> print(manager.get_stats())
        {'total_reconnections': 1, ...}
    """

    def __init__(self) -> None:
        """Initialize reconnection manager with zeroed stats."""
        self.reconnection_count = 0  # Total reconnections handled
        self.snapshot_sent_count = 0  # Times snapshot was chosen
        self.catchup_sent_count = 0  # Times deltas were chosen

    async def handle_reconnection(
        self, room_id: str, client_id: str, last_ack_seq: int
    ) -> ReconnectionResult:
        """Handle client reconnection with smart catchup strategy.

        Decides whether to send deltas or full snapshot based on
        how far behind the client is.

        Args:
            room_id: Room the client is reconnecting to.
            client_id: Reconnecting client identifier.
            last_ack_seq: Last sequence number client acknowledged.

        Returns:
            ReconnectionResult with catchup strategy and data.

        Algorithm:
            1. Get current room sequence number
            2. If client is current → return "current"
            3. If gap > SNAPSHOT_THRESHOLD → send snapshot
            4. Otherwise → send missed deltas
        """
        # Lazy import to avoid circular dependencies
        from kagami.core.rooms import state_service

        self.reconnection_count += 1

        try:
            # IMPORTANT: do not increment the sequence counter just to read it.
            current_seq = await state_service.get_current_seq(room_id)

            if last_ack_seq >= current_seq:
                return ReconnectionResult(
                    status="current",
                    current_seq=current_seq,
                    message="Client is up-to-date",
                )

            delta_count = current_seq - last_ack_seq

            if delta_count > SNAPSHOT_THRESHOLD:
                logger.info(f"Sending snapshot to {client_id} ({delta_count} deltas)")
                snapshot = await state_service.get_snapshot(room_id)
                self.snapshot_sent_count += 1

                return ReconnectionResult(
                    status="snapshot",
                    current_seq=current_seq,
                    snapshot=snapshot.state,
                    message=f"Snapshot sent ({delta_count} updates behind)",
                )

            logger.info(f"Sending {delta_count} deltas to {client_id}")
            deltas = await state_service.get_recent_deltas(
                room_id, limit=min(delta_count, MAX_CATCHUP_DELTAS)
            )
            # Safety: if deltas are not seq-stamped, we can't guarantee correct catchup.
            # Fall back to snapshot to avoid clients believing they're current when they're not.
            if any(not isinstance(d, dict) or "seq" not in d for d in (deltas or [])):
                snapshot = await state_service.get_snapshot(room_id)
                self.snapshot_sent_count += 1
                return ReconnectionResult(
                    status="snapshot",
                    current_seq=current_seq,
                    snapshot=snapshot.state,
                    message="Snapshot sent (delta stream missing seq)",
                )
            relevant = [d for d in deltas if d.get("seq", 0) > last_ack_seq]
            self.catchup_sent_count += 1

            return ReconnectionResult(
                status="catchup",
                current_seq=current_seq,
                deltas=relevant,
                message=f"Caught up with {len(relevant)} updates",
            )

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return ReconnectionResult(
                status="error",
                current_seq=0,
                message=f"Reconnection failed: {e!s}",
            )

    def get_stats(self) -> dict[str, Any]:
        """Get reconnection statistics.

        Returns:
            Dict with total_reconnections, snapshots_sent, catchups_sent.

        Example:
            >>> stats = manager.get_stats()
            >>> print(f"Snapshot ratio: {stats['snapshots_sent']/stats['total_reconnections']:.0%}")
        """
        return {
            "total_reconnections": self.reconnection_count,
            "snapshots_sent": self.snapshot_sent_count,
            "catchups_sent": self.catchup_sent_count,
        }


# =============================================================================
# SINGLETON FACTORY
# =============================================================================
# Global manager instance for application-wide reconnection handling.

_manager: ReconnectionManager | None = None


def get_reconnection_manager() -> ReconnectionManager:
    """Get the global ReconnectionManager singleton.

    Creates manager on first call. Returns same instance thereafter.

    Returns:
        Global ReconnectionManager instance.

    Example:
        >>> manager = get_reconnection_manager()
        >>> result = await manager.handle_reconnection(...)
    """
    global _manager
    if _manager is None:
        _manager = ReconnectionManager()
    return _manager


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Main class
    "ReconnectionManager",
    # Result dataclass
    "ReconnectionResult",
    # Factory function
    "get_reconnection_manager",
]
