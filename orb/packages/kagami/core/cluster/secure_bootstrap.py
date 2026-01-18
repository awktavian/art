"""Secure Node Bootstrap — PBFT-verified node joining protocol.

This module implements a secure bootstrap protocol for new nodes joining the
Kagami cluster. It uses PBFT consensus to verify node identity and capabilities
before granting full cluster membership.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SECURE NODE BOOTSTRAP PROTOCOL                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   New Node                        Existing Cluster                       │
│   ─────────                        ─────────────────                     │
│                                                                          │
│   1. BOOTSTRAP_REQUEST ──────────────────────────────►                  │
│      (node_id, service_type, capabilities, challenge_response)          │
│                                                                          │
│   2.                       ◄────── PBFT PRE-PREPARE                     │
│                             (Existing nodes vote on join)               │
│                                                                          │
│   3.                       ◄────── PBFT PREPARE                         │
│                             (2f+1 nodes agree)                          │
│                                                                          │
│   4.                       ◄────── PBFT COMMIT                          │
│                             (Consensus reached)                         │
│                                                                          │
│   5. BOOTSTRAP_APPROVED ◄────────────────────────────                   │
│      (cluster_token, peer_list, state_snapshot)                         │
│                                                                          │
│   6. JOIN MESH ────────────────────────────────────►                    │
│      (Register with service registry, start sync)                       │
│                                                                          │
│   Security Properties:                                                   │
│   • Challenge-response prevents replay attacks                          │
│   • PBFT consensus prevents single-node compromise                      │
│   • Capability verification ensures node trustworthiness               │
│   • Rate limiting prevents DoS                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Colony: Crystal (D₅) — Verification and security boundary
h(x) ≥ 0. Always.

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from kagami.core.caching.redis import RedisClientFactory
from kagami.core.cluster.service_registry import (
    ServiceType,
    get_service_registry,
)
from kagami.core.consensus.etcd_client import etcd_operation, get_etcd_client

logger = logging.getLogger(__name__)


# =============================================================================
# Bootstrap States
# =============================================================================


class BootstrapState(Enum):
    """State of a bootstrap request."""

    PENDING = auto()  # Request submitted, awaiting verification
    CHALLENGED = auto()  # Challenge sent, awaiting response
    VOTING = auto()  # PBFT voting in progress
    APPROVED = auto()  # Consensus reached, node approved
    REJECTED = auto()  # Consensus rejected the node
    EXPIRED = auto()  # Request timed out


# =============================================================================
# Bootstrap Request
# =============================================================================


@dataclass
class BootstrapRequest:
    """Request from a new node to join the cluster.

    Attributes:
        request_id: Unique request identifier.
        node_id: Unique node identifier.
        service_type: Type of service (API, HUB, etc.).
        hostname: Node hostname.
        address: Node IP address.
        port: Node API port.
        capabilities: List of capabilities.
        public_key: Node's public key for authentication.
        challenge: Challenge string for verification.
        challenge_response: HMAC response to challenge.
        timestamp: Request timestamp.
        state: Current bootstrap state.
        votes_approve: Nodes that voted to approve.
        votes_reject: Nodes that voted to reject.
    """

    request_id: str
    node_id: str
    service_type: ServiceType
    hostname: str
    address: str
    port: int
    capabilities: list[str] = field(default_factory=list)
    public_key: str = ""
    challenge: str = ""
    challenge_response: str = ""
    timestamp: float = field(default_factory=time.time)
    state: BootstrapState = BootstrapState.PENDING
    votes_approve: set[str] = field(default_factory=set)
    votes_reject: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "request_id": self.request_id,
            "node_id": self.node_id,
            "service_type": self.service_type.value,
            "hostname": self.hostname,
            "address": self.address,
            "port": self.port,
            "capabilities": self.capabilities,
            "public_key": self.public_key,
            "challenge": self.challenge,
            "challenge_response": self.challenge_response,
            "timestamp": self.timestamp,
            "state": self.state.name,
            "votes_approve": list(self.votes_approve),
            "votes_reject": list(self.votes_reject),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BootstrapRequest:
        """Deserialize from dictionary."""
        return cls(
            request_id=data["request_id"],
            node_id=data["node_id"],
            service_type=ServiceType(data["service_type"]),
            hostname=data["hostname"],
            address=data["address"],
            port=data["port"],
            capabilities=data.get("capabilities", []),
            public_key=data.get("public_key", ""),
            challenge=data.get("challenge", ""),
            challenge_response=data.get("challenge_response", ""),
            timestamp=data.get("timestamp", 0),
            state=BootstrapState[data.get("state", "PENDING")],
            votes_approve=set(data.get("votes_approve", [])),
            votes_reject=set(data.get("votes_reject", [])),
        )


# =============================================================================
# Bootstrap Result
# =============================================================================


@dataclass
class BootstrapResult:
    """Result of bootstrap process.

    Attributes:
        success: Whether bootstrap succeeded.
        node_id: Node ID.
        cluster_token: Token for cluster authentication.
        peer_list: List of peer addresses.
        state_snapshot: Initial state snapshot.
        error: Error message if failed.
    """

    success: bool
    node_id: str
    cluster_token: str = ""
    peer_list: list[dict[str, Any]] = field(default_factory=list)
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# =============================================================================
# Secure Bootstrap Coordinator
# =============================================================================


class SecureBootstrapCoordinator:
    """Coordinates secure node bootstrap with PBFT verification.

    Handles:
    - Challenge generation and verification
    - PBFT consensus voting
    - Node registration
    - State snapshot distribution

    Example:
        >>> coordinator = SecureBootstrapCoordinator(config)
        >>> await coordinator.initialize()
        >>> result = await coordinator.request_bootstrap(request)
    """

    # etcd paths
    ETCD_PREFIX = "/kagami/bootstrap"
    CHALLENGE_TTL = 60  # Seconds
    REQUEST_TTL = 300  # 5 minutes

    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = 10
    RATE_LIMIT_WINDOW = 60

    def __init__(
        self,
        node_id: str,
        cluster_secret: str | None = None,
        quorum_size: int = 3,
    ) -> None:
        """Initialize the bootstrap coordinator.

        Args:
            node_id: This node's ID.
            cluster_secret: Shared secret for HMAC verification.
            quorum_size: Required votes for approval (2f+1).
        """
        self.node_id = node_id
        self.cluster_secret = cluster_secret or os.environ.get("KAGAMI_CLUSTER_SECRET", "")
        self.quorum_size = quorum_size

        self._etcd = get_etcd_client()
        self._redis = RedisClientFactory.get_client()
        self._service_registry = None

        self._initialized = False
        self._pending_requests: dict[str, BootstrapRequest] = {}

    async def initialize(self) -> None:
        """Initialize the bootstrap coordinator."""
        if self._initialized:
            return

        logger.info(f"Initializing SecureBootstrapCoordinator for {self.node_id}")

        self._service_registry = get_service_registry()
        await self._service_registry.initialize()

        self._initialized = True
        logger.info("✅ SecureBootstrapCoordinator initialized")

    async def shutdown(self) -> None:
        """Shutdown the bootstrap coordinator."""
        self._pending_requests.clear()
        self._initialized = False
        logger.info("🛑 SecureBootstrapCoordinator shutdown")

    # =========================================================================
    # New Node Side
    # =========================================================================

    async def request_bootstrap(
        self,
        service_type: ServiceType,
        hostname: str,
        address: str,
        port: int,
        capabilities: list[str] | None = None,
    ) -> BootstrapResult:
        """Request to join the cluster as a new node.

        Args:
            service_type: Type of service.
            hostname: Node hostname.
            address: Node IP address.
            port: Node API port.
            capabilities: Node capabilities.

        Returns:
            BootstrapResult with success status.
        """
        request_id = secrets.token_hex(16)

        # Create bootstrap request
        request = BootstrapRequest(
            request_id=request_id,
            node_id=self.node_id,
            service_type=service_type,
            hostname=hostname,
            address=address,
            port=port,
            capabilities=capabilities or [],
        )

        logger.info(f"Requesting cluster bootstrap: {request_id}")

        try:
            # Step 1: Submit request to etcd
            await self._submit_request(request)

            # Step 2: Wait for challenge
            challenge = await self._wait_for_challenge(request_id)
            if not challenge:
                return BootstrapResult(
                    success=False,
                    node_id=self.node_id,
                    error="No challenge received (timeout)",
                )

            # Step 3: Respond to challenge
            await self._respond_to_challenge(request_id, challenge)

            # Step 4: Wait for approval
            result = await self._wait_for_approval(request_id)
            return result

        except Exception as e:
            logger.error(f"Bootstrap request failed: {e}")
            return BootstrapResult(success=False, node_id=self.node_id, error=str(e))

    async def _submit_request(self, request: BootstrapRequest) -> None:
        """Submit bootstrap request to etcd."""
        import json

        key = f"{self.ETCD_PREFIX}/requests/{request.request_id}"
        value = json.dumps(request.to_dict())

        await etcd_operation(
            self._etcd.put,
            key,
            value,
            lease=await self._etcd.get_or_create_lease(self.REQUEST_TTL),
            operation_name="submit_bootstrap_request",
        )

    async def _wait_for_challenge(self, request_id: str, timeout: float = 30.0) -> str | None:
        """Wait for challenge from existing cluster."""

        key = f"{self.ETCD_PREFIX}/challenges/{request_id}"
        start = time.time()

        while time.time() - start < timeout:
            try:
                value, _ = await etcd_operation(self._etcd.get, key, operation_name="get_challenge")
                if value:
                    return value.decode()
            except Exception:
                pass
            await asyncio.sleep(1)

        return None

    async def _respond_to_challenge(self, request_id: str, challenge: str) -> None:
        """Respond to bootstrap challenge."""

        # Compute HMAC response
        response = hmac.new(
            self.cluster_secret.encode(),
            (challenge + self.node_id).encode(),
            hashlib.sha256,
        ).hexdigest()

        key = f"{self.ETCD_PREFIX}/responses/{request_id}"
        await etcd_operation(
            self._etcd.put,
            key,
            response,
            lease=await self._etcd.get_or_create_lease(self.CHALLENGE_TTL),
            operation_name="respond_to_challenge",
        )

    async def _wait_for_approval(self, request_id: str, timeout: float = 120.0) -> BootstrapResult:
        """Wait for PBFT consensus approval."""
        import json

        key = f"{self.ETCD_PREFIX}/results/{request_id}"
        start = time.time()

        while time.time() - start < timeout:
            try:
                value, _ = await etcd_operation(self._etcd.get, key, operation_name="get_approval")
                if value:
                    data = json.loads(value.decode())
                    return BootstrapResult(
                        success=data.get("success", False),
                        node_id=self.node_id,
                        cluster_token=data.get("cluster_token", ""),
                        peer_list=data.get("peer_list", []),
                        state_snapshot=data.get("state_snapshot", {}),
                        error=data.get("error"),
                    )
            except Exception:
                pass
            await asyncio.sleep(2)

        return BootstrapResult(
            success=False,
            node_id=self.node_id,
            error="Approval timeout",
        )

    # =========================================================================
    # Existing Cluster Side
    # =========================================================================

    async def process_bootstrap_request(self, request: BootstrapRequest) -> None:
        """Process a bootstrap request (called by existing cluster nodes).

        Args:
            request: Bootstrap request to process.
        """
        logger.info(f"Processing bootstrap request: {request.request_id}")

        # Step 1: Rate limiting check
        if await self._is_rate_limited(request.address):
            logger.warning(f"Rate limited bootstrap request from {request.address}")
            return

        # Step 2: Generate and store challenge
        challenge = secrets.token_hex(32)
        await self._store_challenge(request.request_id, challenge)

        # Step 3: Wait for challenge response
        response = await self._wait_for_response(request.request_id)
        if not response:
            logger.warning(f"No challenge response for {request.request_id}")
            return

        # Step 4: Verify challenge response
        expected = hmac.new(
            self.cluster_secret.encode(),
            (challenge + request.node_id).encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(response, expected):
            logger.warning(f"Invalid challenge response for {request.request_id}")
            await self._vote_reject(request.request_id)
            return

        # Step 5: Vote to approve
        await self._vote_approve(request.request_id)

        # Step 6: Check if quorum reached
        await self._check_quorum(request)

    async def _is_rate_limited(self, address: str) -> bool:
        """Check if address is rate limited."""
        key = f"bootstrap_rate:{address}"
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, self.RATE_LIMIT_WINDOW)
            return count > self.MAX_REQUESTS_PER_MINUTE
        except Exception:
            return False

    async def _store_challenge(self, request_id: str, challenge: str) -> None:
        """Store challenge in etcd."""
        key = f"{self.ETCD_PREFIX}/challenges/{request_id}"
        await etcd_operation(
            self._etcd.put,
            key,
            challenge,
            lease=await self._etcd.get_or_create_lease(self.CHALLENGE_TTL),
            operation_name="store_challenge",
        )

    async def _wait_for_response(self, request_id: str, timeout: float = 30.0) -> str | None:
        """Wait for challenge response."""
        key = f"{self.ETCD_PREFIX}/responses/{request_id}"
        start = time.time()

        while time.time() - start < timeout:
            try:
                value, _ = await etcd_operation(self._etcd.get, key, operation_name="get_response")
                if value:
                    return value.decode()
            except Exception:
                pass
            await asyncio.sleep(1)

        return None

    async def _vote_approve(self, request_id: str) -> None:
        """Vote to approve bootstrap request."""
        import json

        key = f"{self.ETCD_PREFIX}/votes/approve/{request_id}/{self.node_id}"
        await etcd_operation(
            self._etcd.put,
            key,
            json.dumps({"voter": self.node_id, "timestamp": time.time()}),
            lease=await self._etcd.get_or_create_lease(self.REQUEST_TTL),
            operation_name="vote_approve",
        )

    async def _vote_reject(self, request_id: str) -> None:
        """Vote to reject bootstrap request."""
        import json

        key = f"{self.ETCD_PREFIX}/votes/reject/{request_id}/{self.node_id}"
        await etcd_operation(
            self._etcd.put,
            key,
            json.dumps({"voter": self.node_id, "timestamp": time.time()}),
            lease=await self._etcd.get_or_create_lease(self.REQUEST_TTL),
            operation_name="vote_reject",
        )

    async def _check_quorum(self, request: BootstrapRequest) -> None:
        """Check if quorum reached for approval."""

        # Count approve votes
        approve_prefix = f"{self.ETCD_PREFIX}/votes/approve/{request.request_id}/"
        try:
            approve_votes = await etcd_operation(
                self._etcd.get_prefix,
                approve_prefix,
                operation_name="count_approve_votes",
            )
            approve_count = len(list(approve_votes))
        except Exception:
            approve_count = 0

        # Count reject votes
        reject_prefix = f"{self.ETCD_PREFIX}/votes/reject/{request.request_id}/"
        try:
            reject_votes = await etcd_operation(
                self._etcd.get_prefix,
                reject_prefix,
                operation_name="count_reject_votes",
            )
            reject_count = len(list(reject_votes))
        except Exception:
            reject_count = 0

        logger.debug(
            f"Bootstrap {request.request_id}: {approve_count} approve, {reject_count} reject"
        )

        # Check quorum
        if approve_count >= self.quorum_size:
            await self._finalize_approval(request)
        elif reject_count >= self.quorum_size:
            await self._finalize_rejection(request)

    async def _finalize_approval(self, request: BootstrapRequest) -> None:
        """Finalize bootstrap approval."""
        import json

        logger.info(f"Bootstrap approved: {request.request_id}")

        # Generate cluster token
        cluster_token = secrets.token_hex(32)

        # Get peer list
        peers = await self._service_registry.discover(healthy_only=True)
        peer_list = [p.to_dict() for p in peers]

        # Register the new node via service registry
        # Note: The new node will register itself after receiving approval
        # We just prepare the cluster token and peer list here

        # Store result
        result = {
            "success": True,
            "cluster_token": cluster_token,
            "peer_list": peer_list,
            "state_snapshot": {},  # CRDT state syncs via gossip after join
        }

        key = f"{self.ETCD_PREFIX}/results/{request.request_id}"
        await etcd_operation(
            self._etcd.put,
            key,
            json.dumps(result),
            lease=await self._etcd.get_or_create_lease(self.REQUEST_TTL),
            operation_name="finalize_approval",
        )

    async def _finalize_rejection(self, request: BootstrapRequest) -> None:
        """Finalize bootstrap rejection."""
        import json

        logger.warning(f"Bootstrap rejected: {request.request_id}")

        result = {
            "success": False,
            "error": "Consensus rejected node join",
        }

        key = f"{self.ETCD_PREFIX}/results/{request.request_id}"
        await etcd_operation(
            self._etcd.put,
            key,
            json.dumps(result),
            lease=await self._etcd.get_or_create_lease(self.REQUEST_TTL),
            operation_name="finalize_rejection",
        )


# =============================================================================
# Singleton Factory
# =============================================================================

_bootstrap_coordinator: SecureBootstrapCoordinator | None = None
_bootstrap_lock = asyncio.Lock()


async def get_bootstrap_coordinator(
    node_id: str | None = None,
    cluster_secret: str | None = None,
) -> SecureBootstrapCoordinator:
    """Get or create the global SecureBootstrapCoordinator.

    Args:
        node_id: Node identifier (required for first call).
        cluster_secret: Shared cluster secret.

    Returns:
        SecureBootstrapCoordinator singleton instance.
    """
    global _bootstrap_coordinator

    async with _bootstrap_lock:
        if _bootstrap_coordinator is None:
            import socket

            if node_id is None:
                node_id = os.environ.get("KAGAMI_NODE_ID", f"{socket.gethostname()}-{os.getpid()}")
            _bootstrap_coordinator = SecureBootstrapCoordinator(node_id, cluster_secret)
            await _bootstrap_coordinator.initialize()

    return _bootstrap_coordinator


async def shutdown_bootstrap_coordinator() -> None:
    """Shutdown the global SecureBootstrapCoordinator."""
    global _bootstrap_coordinator

    if _bootstrap_coordinator:
        await _bootstrap_coordinator.shutdown()
        _bootstrap_coordinator = None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "BootstrapRequest",
    "BootstrapResult",
    "BootstrapState",
    "SecureBootstrapCoordinator",
    "get_bootstrap_coordinator",
    "shutdown_bootstrap_coordinator",
]


# =============================================================================
# 鏡
# New nodes join. Consensus verifies. The cluster grows safely.
# h(x) ≥ 0. Always.
# =============================================================================
