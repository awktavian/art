"""Unified Instance Identity for Distributed K OS.

This module provides a SINGLE source of truth for instance identity across
all distributed coordination systems. Previously, there were duplicate
implementations of `_generate_instance_id()` scattered across:
- homeostasis_sync.py
- etcd_coordinator.py
- etcd_receipt_sync.py
- service_discovery.py
- instance_mesh.py
- message_bus.py
- checkpoint.py

Now there is ONE.

Instance Identity Structure:
===========================

An instance ID encodes:
1. Hostname (machine identity)
2. PID (process identity)
3. UUID suffix (uniqueness across restarts)
4. Optional colony affinity (octonion basis e₁-e₇)

Format: `{hostname}-{pid}-{uuid8}`
Example: `kagami-worker-1-12345-a1b2c3d4`

With colony: `{hostname}-{pid}-{uuid8}:{colony}`
Example: `kagami-worker-1-12345-a1b2c3d4:forge`

Octonion Colony Mapping:
========================

Colony     | Octonion | Index | Color
-----------|----------|-------|-------
Spark      | e₁       | 1     | Magenta
Forge      | e₂       | 2     | Red
Flow       | e₃       | 3     | Cyan
Nexus      | e₄       | 4     | Violet
Beacon     | e₅       | 5     | Yellow
Grove      | e₆       | 6     | Green
Crystal    | e₇       | 7     | Blue

Created: November 29, 2025
"""

from __future__ import annotations

import os
import socket
import threading
import uuid
from dataclasses import dataclass
from enum import Enum

# Colony enum - use DomainType from canonical source with color extensions
from kagami.core.unified_agents.colony_constants import COLONY_TO_INDEX

# Color mapping for colonies
COLONY_COLORS = {
    "spark": "magenta",
    "forge": "red",
    "flow": "cyan",
    "nexus": "violet",
    "beacon": "yellow",
    "grove": "green",
    "crystal": "blue",
}


class Colony(Enum):
    """The 7 octonion colonies (imaginary units e₁ through e₇).

    Note: This wraps DomainType with additional properties (color, octonion_index).
    The canonical source is kagami.core.catastrophe.constants.COLONY_NAMES.
    """

    SPARK = "spark"  # e₁ - Creativity, divergence
    FORGE = "forge"  # e₂ - Action, implementation
    FLOW = "flow"  # e₃ - Recovery, adaptation
    NEXUS = "nexus"  # e₄ - Memory, integration
    BEACON = "beacon"  # e₅ - Planning, focus
    GROVE = "grove"  # e₆ - Research, knowledge
    CRYSTAL = "crystal"  # e₇ - Safety, verification

    @property
    def octonion_index(self) -> int:
        """Get octonion basis index (1-7)."""
        return COLONY_TO_INDEX[self.value] + 1

    @property
    def color(self) -> str:
        """Get associated color."""
        return COLONY_COLORS.get(self.value, "white")


@dataclass(frozen=True)
class InstanceIdentity:
    """Immutable identity for a K OS instance.

    Attributes:
        hostname: Machine hostname
        pid: Process ID
        uuid_suffix: Unique suffix (8 hex chars)
        colony: Optional colony affinity
    """

    hostname: str
    pid: int
    uuid_suffix: str
    colony: Colony | None = None

    @property
    def base_id(self) -> str:
        """Get base instance ID (without colony)."""
        return f"{self.hostname}-{self.pid}-{self.uuid_suffix}"

    @property
    def full_id(self) -> str:
        """Get full instance ID (with colony if set[Any])."""
        if self.colony:
            return f"{self.base_id}:{self.colony.value}"
        return self.base_id

    def __str__(self) -> str:
        return self.full_id

    def with_colony(self, colony: Colony) -> InstanceIdentity:
        """Create new identity with colony affinity."""
        return InstanceIdentity(
            hostname=self.hostname,
            pid=self.pid,
            uuid_suffix=self.uuid_suffix,
            colony=colony,
        )


# Global singleton
_instance_identity: InstanceIdentity | None = None
_identity_lock = threading.Lock()


def get_instance_identity(colony: Colony | None = None) -> InstanceIdentity:
    """Get the singleton instance identity.

    Thread-safe. Creates identity on first call, returns same thereafter.

    Args:
        colony: Optional colony to associate with this instance

    Returns:
        Immutable InstanceIdentity
    """
    global _instance_identity

    with _identity_lock:
        if _instance_identity is None:
            hostname = os.getenv("HOSTNAME") or socket.gethostname() or "kagami"
            pid = os.getpid()
            uuid_suffix = uuid.uuid4().hex[:8]

            _instance_identity = InstanceIdentity(
                hostname=hostname,
                pid=pid,
                uuid_suffix=uuid_suffix,
                colony=colony,
            )

        # If colony requested and not already set[Any], create new identity with colony
        if colony and _instance_identity.colony is None:
            _instance_identity = _instance_identity.with_colony(colony)

        return _instance_identity


def get_instance_id() -> str:
    """Get instance ID string (backward compatible).

    This is the canonical way to get instance ID across the codebase.
    Replaces all the duplicate `_generate_instance_id()` functions.

    Returns:
        Instance ID string
    """
    return get_instance_identity().base_id


def reset_instance_identity() -> None:
    """Reset instance identity (for testing only).

    WARNING: Do not use in production code.
    """
    global _instance_identity
    with _identity_lock:
        _instance_identity = None
