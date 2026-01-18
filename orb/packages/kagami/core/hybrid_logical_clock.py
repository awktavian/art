"""Hybrid Logical Clock (HLC) implementation for K os.

Provides a causally consistent clock that combines physical time with logical counters
to handle clock skew and ensure total ordering of events across distributed nodes.

Based on the paper "Logical Physical Clocks and Consistent Snapshots in Globally
Distributed Databases" by Kulkarni et al.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HLCTimestamp:
    """Immutable HLC timestamp with physical and logical components."""

    physical: float  # Physical wall clock time
    logical: int  # Logical counter for same physical time
    node_id: str  # Node identifier for tie-breaking

    def __lt__(self, other: "HLCTimestamp") -> bool:
        """Total ordering: physical time, then logical counter, then node ID."""
        if self.physical != other.physical:
            return self.physical < other.physical
        if self.logical != other.logical:
            return self.logical < other.logical
        return self.node_id < other.node_id

    def __le__(self, other: "HLCTimestamp") -> bool:
        return self == other or self < other

    def __gt__(self, other: "HLCTimestamp") -> bool:
        return not self <= other

    def __ge__(self, other: "HLCTimestamp") -> bool:
        return not self < other

    def to_bytes(self) -> bytes:
        """Serialize to bytes for network transmission."""
        import struct

        # Pack as: 8 bytes physical (double), 4 bytes logical (uint), variable node_id
        node_bytes = self.node_id.encode("utf-8")
        return struct.pack("!dI", self.physical, self.logical) + node_bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> "HLCTimestamp":
        """Deserialize from bytes."""
        import struct

        physical, logical = struct.unpack("!dI", data[:12])
        node_id = data[12:].decode("utf-8")
        return cls(physical=physical, logical=logical, node_id=node_id)

    def to_tuple(self) -> tuple[float, int, str]:
        """Convert to tuple[Any, ...] for easy comparison and storage."""
        return (self.physical, self.logical, self.node_id)

    def __str__(self) -> str:
        return f"HLC({self.physical:.6f}:{self.logical}@{self.node_id})"


class HybridLogicalClock:
    """Thread-safe Hybrid Logical Clock implementation.

    Ensures:
    - Monotonically increasing timestamps
    - Causal consistency across nodes
    - Bounded clock skew handling
    - Total ordering of events
    """

    # Maximum acceptable clock skew in seconds (default: 1 minute)
    MAX_CLOCK_SKEW = float(os.getenv("KAGAMI_MAX_CLOCK_SKEW", "60.0"))

    def __init__(self, node_id: str | None = None) -> None:
        """Initialize HLC with optional node identifier.

        Args:
            node_id: Unique node identifier. If None, generates from hostname/PID.
        """
        if node_id is None:
            import socket

            node_id = f"{socket.gethostname()}:{os.getpid()}"

        self.node_id = node_id
        self._lock = threading.Lock()

        # Initialize with current time
        now = time.time()
        self._last_physical = now
        self._last_logical = 0

        logger.info(f"Initialized HLC for node {self.node_id}")

    def now(self) -> HLCTimestamp:
        """Generate a new HLC timestamp for the current moment.

        Returns:
            HLCTimestamp: Current HLC timestamp
        """
        with self._lock:
            physical_now = time.time()

            if physical_now > self._last_physical:
                # Physical time has advanced
                self._last_physical = physical_now
                self._last_logical = 0
            else:
                # Physical time hasn't advanced, increment logical
                self._last_logical += 1

                # Warn if logical counter is getting high (potential clock issues)
                if self._last_logical > 1000:
                    logger.warning(
                        f"HLC logical counter high: {self._last_logical}. "
                        "Possible clock stall or high event rate."
                    )

            return HLCTimestamp(
                physical=self._last_physical,
                logical=self._last_logical,
                node_id=self.node_id,
            )

    def update(self, remote: HLCTimestamp) -> HLCTimestamp:
        """Update clock with remote timestamp and generate new local timestamp.

        This is the core HLC algorithm that ensures causal consistency.

        Args:
            remote: Remote HLC timestamp received from another node

        Returns:
            HLCTimestamp: New local timestamp after update

        Raises:
            ValueError: If remote timestamp is too far in the future (clock skew)
        """
        with self._lock:
            physical_now = time.time()

            # Check for excessive clock skew
            if remote.physical > physical_now + self.MAX_CLOCK_SKEW:
                raise ValueError(
                    f"Remote timestamp too far in future: {remote.physical:.6f} vs "
                    f"local {physical_now:.6f} (max skew: {self.MAX_CLOCK_SKEW}s)"
                )

            # HLC update algorithm
            new_physical = max(self._last_physical, physical_now, remote.physical)

            if new_physical == self._last_physical and new_physical == remote.physical:
                # All three timestamps equal, increment logical
                new_logical = max(self._last_logical, remote.logical) + 1
            elif new_physical == self._last_physical:
                # Local physical time is ahead
                new_logical = self._last_logical + 1
            elif new_physical == remote.physical:
                # Remote physical time is ahead
                new_logical = remote.logical + 1
            else:
                # Physical time has advanced
                new_logical = 0

            self._last_physical = new_physical
            self._last_logical = new_logical

            return HLCTimestamp(physical=new_physical, logical=new_logical, node_id=self.node_id)

    def send(self) -> HLCTimestamp:
        """Generate timestamp for sending a message.

        Alias for now() to match HLC paper terminology.
        """
        return self.now()

    def receive(self, remote: HLCTimestamp) -> HLCTimestamp:
        """Process received timestamp and update local clock.

        Alias for update() to match HLC paper terminology.
        """
        return self.update(remote)

    def happens_before(self, a: HLCTimestamp, b: HLCTimestamp) -> bool:
        """Check if event a happened before event b.

        Args:
            a: First timestamp
            b: Second timestamp

        Returns:
            bool: True if a happened before b
        """
        return a < b

    def concurrent(self, a: HLCTimestamp, b: HLCTimestamp) -> bool:
        """Check if two events are concurrent (no causal relationship).

        In HLC, events are never truly concurrent due to total ordering,
        but this checks if they have the same physical and logical time.

        Args:
            a: First timestamp
            b: Second timestamp

        Returns:
            bool: True if timestamps are equal (extremely rare)
        """
        return a.physical == b.physical and a.logical == b.logical and a.node_id != b.node_id


# Global HLC instance for the current process
_global_hlc: HybridLogicalClock | None = None
_global_lock = threading.Lock()


class GlobalHLC:
    """Global HLC singleton for process-wide clock coordination."""

    @classmethod
    def get_clock(cls) -> HybridLogicalClock:
        """Get or create the global HLC instance.

        Returns:
            HybridLogicalClock: Global clock instance
        """
        global _global_hlc

        if _global_hlc is None:
            with _global_lock:
                if _global_hlc is None:
                    _global_hlc = HybridLogicalClock()

        return _global_hlc

    @classmethod
    def now(cls) -> HLCTimestamp:
        """Generate a new timestamp using the global clock.

        Returns:
            HLCTimestamp: Current timestamp
        """
        return cls.get_clock().now()

    @classmethod
    def update(cls, remote: HLCTimestamp) -> HLCTimestamp:
        """Update global clock with remote timestamp.

        Args:
            remote: Remote timestamp

        Returns:
            HLCTimestamp: New local timestamp after update
        """
        return cls.get_clock().update(remote)


# Convenience functions for module-level usage
def hlc_now() -> HLCTimestamp:
    """Get current HLC timestamp using global clock."""
    return GlobalHLC.now()


def hlc_update(remote: HLCTimestamp) -> HLCTimestamp:
    """Update global clock with remote timestamp."""
    return GlobalHLC.update(remote)


def hlc_from_tuple(physical: float, logical: int, node_id: str) -> HLCTimestamp:
    """Create HLC timestamp from components."""
    return HLCTimestamp(physical=physical, logical=logical, node_id=node_id)
