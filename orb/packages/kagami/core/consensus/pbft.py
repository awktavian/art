"""Practical Byzantine Fault Tolerance (PBFT) Consensus Implementation.

Provides Byzantine fault-tolerant consensus for critical state changes.
Tolerates up to f Byzantine (malicious) nodes in a 3f+1 node cluster.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────┐
│                        PBFT CONSENSUS                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Client Request                                                     │
│        │                                                            │
│        ▼                                                            │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐  │
│   │ Primary │─────▶│ Replica │─────▶│ Replica │─────▶│ Replica │  │
│   │  (n=0)  │      │  (n=1)  │      │  (n=2)  │      │  (n=3)  │  │
│   └────┬────┘      └────┬────┘      └────┬────┘      └────┬────┘  │
│        │                │                │                │        │
│   PRE-PREPARE     PREPARE (2f+1)   COMMIT (2f+1)                   │
│        └────────────────┴────────────────┴────────────────┘        │
│                              │                                      │
│                              ▼                                      │
│                         REPLY (f+1)                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

Phases:
1. PRE-PREPARE: Primary assigns sequence number, broadcasts to replicas
2. PREPARE: Replicas validate and broadcast prepare messages
3. COMMIT: After 2f+1 prepares, broadcast commit messages
4. REPLY: After 2f+1 commits, execute and reply to client

View Change:
- Triggered by timeout or suspected Byzantine primary
- New primary = (view + 1) mod n
- Requires 2f+1 view-change messages

Safety: Consensus reached only with 2f+1 honest nodes agreeing.
Liveness: Guaranteed if at most f nodes are Byzantine.

Colony: Crystal (D₅) — Verification and consensus boundary
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# Type for generic messages
T = TypeVar("T")


class PBFTPhase(Enum):
    """PBFT protocol phases."""

    IDLE = auto()
    PRE_PREPARE = auto()
    PREPARE = auto()
    COMMIT = auto()
    REPLY = auto()
    VIEW_CHANGE = auto()


class MessageType(Enum):
    """PBFT message types."""

    REQUEST = "request"
    PRE_PREPARE = "pre-prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    REPLY = "reply"
    VIEW_CHANGE = "view-change"
    NEW_VIEW = "new-view"
    CHECKPOINT = "checkpoint"


@dataclass
class PBFTConfig:
    """PBFT consensus configuration.

    Attributes:
        node_id: Unique identifier for this node.
        cluster_size: Total nodes in cluster (must be 3f+1).
        byzantine_tolerance: Maximum Byzantine nodes (f).
        request_timeout: Timeout for request completion (seconds).
        view_change_timeout: Timeout before triggering view change.
        checkpoint_interval: Sequence numbers between checkpoints.
        secret_key: HMAC key for message authentication.
        async_commit: Allow async commit for better throughput.
        cluster_nodes: List of node IDs in cluster (optional).
    """

    node_id: str = ""
    cluster_size: int = 4  # 3f+1 where f=1
    byzantine_tolerance: int = 1  # f
    request_timeout: float = 30.0
    view_change_timeout: float = 60.0
    checkpoint_interval: int = 100
    secret_key: str = ""
    async_commit: bool = False
    cluster_nodes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Load from environment and validate."""
        if not self.node_id:
            import socket

            self.node_id = os.environ.get("KAGAMI_NODE_ID", f"{socket.gethostname()}-{os.getpid()}")

        self.cluster_size = int(os.environ.get("PBFT_CLUSTER_SIZE", str(self.cluster_size)))
        self.byzantine_tolerance = int(
            os.environ.get("PBFT_BYZANTINE_TOLERANCE", str(self.byzantine_tolerance))
        )

        if not self.secret_key:
            self.secret_key = os.environ.get("PBFT_SECRET_KEY", "kagami-pbft-default")

        # Validate 3f+1 constraint
        expected_size = 3 * self.byzantine_tolerance + 1
        if self.cluster_size < expected_size:
            logger.warning(
                f"⚠️ Cluster size {self.cluster_size} < 3f+1={expected_size}. "
                f"Byzantine tolerance reduced."
            )
            self.byzantine_tolerance = (self.cluster_size - 1) // 3

    @property
    def quorum_size(self) -> int:
        """Minimum nodes for quorum (2f+1)."""
        return 2 * self.byzantine_tolerance + 1

    @property
    def commit_threshold(self) -> int:
        """Minimum commits for consensus (2f+1)."""
        return 2 * self.byzantine_tolerance + 1


@dataclass
class PBFTMessage:
    """PBFT protocol message.

    Attributes:
        msg_type: Type of message.
        view: Current view number.
        sequence: Sequence number for ordering.
        digest: SHA-256 hash of request.
        sender: Node ID of sender.
        timestamp: Message timestamp.
        payload: Message-specific data.
        signature: HMAC signature for authentication.
    """

    msg_type: MessageType
    view: int
    sequence: int
    digest: str
    sender: str
    timestamp: float = field(default_factory=time.time)
    payload: dict[str, Any] = field(default_factory=dict)
    signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "msg_type": self.msg_type.value,
            "view": self.view,
            "sequence": self.sequence,
            "digest": self.digest,
            "sender": self.sender,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PBFTMessage:
        """Deserialize from dictionary."""
        return cls(
            msg_type=MessageType(data["msg_type"]),
            view=data["view"],
            sequence=data["sequence"],
            digest=data["digest"],
            sender=data["sender"],
            timestamp=data.get("timestamp", time.time()),
            payload=data.get("payload", {}),
            signature=data.get("signature", ""),
        )

    def compute_signature(self, secret_key: str) -> str:
        """Compute HMAC signature for message."""
        content = json.dumps(
            {
                "msg_type": self.msg_type.value,
                "view": self.view,
                "sequence": self.sequence,
                "digest": self.digest,
                "sender": self.sender,
                "timestamp": self.timestamp,
                "payload": self.payload,
            },
            sort_keys=True,
        )
        return hmac.new(secret_key.encode(), content.encode(), hashlib.sha256).hexdigest()

    def sign(self, secret_key: str) -> None:
        """Sign this message."""
        self.signature = self.compute_signature(secret_key)

    def verify(self, secret_key: str) -> bool:
        """Verify message signature."""
        expected = self.compute_signature(secret_key)
        return hmac.compare_digest(self.signature, expected)


@dataclass
class ConsensusRequest:
    """Client request for consensus.

    Attributes:
        client_id: Client identifier.
        timestamp: Request timestamp.
        operation: Operation to execute.
        data: Operation data.
    """

    client_id: str
    timestamp: float
    operation: str
    data: dict[str, Any]

    def digest(self) -> str:
        """Compute SHA-256 digest of request."""
        content = json.dumps(
            {
                "client_id": self.client_id,
                "timestamp": self.timestamp,
                "operation": self.operation,
                "data": self.data,
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class ConsensusResult:
    """Result of consensus operation.

    Attributes:
        success: Whether consensus was reached.
        sequence: Assigned sequence number.
        view: View in which consensus was reached.
        result: Operation result if successful.
        error: Error message if failed.
        nodes_agreed: Number of nodes that agreed.
        latency_ms: Time to reach consensus.
    """

    success: bool
    sequence: int
    view: int
    result: Any = None
    error: str | None = None
    nodes_agreed: int = 0
    latency_ms: float = 0.0


class PBFTNode:
    """PBFT consensus node implementation.

    Manages the PBFT protocol for Byzantine fault-tolerant consensus.
    Can operate as primary (leader) or replica (follower).

    Example:
        >>> config = PBFTConfig(cluster_size=4)
        >>> node = PBFTNode(config)
        >>> await node.start()
        >>> result = await node.submit_request(
        ...     operation="update_state",
        ...     data={"key": "value"}
        ... )
        >>> if result.success:
        ...     print(f"Consensus reached at seq {result.sequence}")
    """

    def __init__(
        self,
        config: PBFTConfig | None = None,
        transport: Any = None,
    ) -> None:
        """Initialize PBFT node.

        Args:
            config: PBFT configuration.
            transport: Network transport for message passing.
        """
        self.config = config or PBFTConfig()
        self.transport = transport

        # Node state
        self._view = 0
        self._sequence = 0
        self._low_watermark = 0
        self._high_watermark = self.config.checkpoint_interval

        # Message logs (indexed by (view, sequence))
        self._pre_prepares: dict[tuple[int, int], PBFTMessage] = {}
        self._prepares: dict[tuple[int, int], dict[str, PBFTMessage]] = {}
        self._commits: dict[tuple[int, int], dict[str, PBFTMessage]] = {}
        self._replies: dict[str, ConsensusResult] = {}  # By digest

        # Pending requests
        self._pending: dict[str, asyncio.Future] = {}

        # Checkpoints
        self._checkpoints: dict[int, dict[str, str]] = {}  # seq -> {node_id: digest}
        self._stable_checkpoint = 0

        # View change state
        self._view_change_msgs: dict[int, dict[str, PBFTMessage]] = {}
        self._view_change_timer: asyncio.Task | None = None

        # Execution
        self._executed: set[int] = set()
        self._execute_callback: Callable[[str, dict], Any] | None = None

        # Running state
        self._started = False
        self._shutdown = False

        logger.info(
            f"🔐 PBFT Node initialized: {self.config.node_id} "
            f"(cluster={self.config.cluster_size}, f={self.config.byzantine_tolerance})"
        )

    @property
    def is_primary(self) -> bool:
        """Check if this node is the current primary."""
        # Primary selection: node with index = view mod cluster_size
        # For simplicity, use hash of node_id to determine index
        nodes = self._get_node_list()
        primary_idx = self._view % len(nodes)
        return nodes[primary_idx] == self.config.node_id if nodes else True

    @property
    def primary_id(self) -> str:
        """Get current primary node ID."""
        nodes = self._get_node_list()
        if not nodes:
            return self.config.node_id
        primary_idx = self._view % len(nodes)
        return nodes[primary_idx]

    def _get_node_list(self) -> list[str]:
        """Get sorted list of node IDs in cluster."""
        # Priority: config.cluster_nodes > environment > default
        if self.config.cluster_nodes:
            return sorted(self.config.cluster_nodes)

        # Try environment
        nodes_str = os.environ.get("PBFT_NODES", "")
        if nodes_str:
            nodes = sorted([n.strip() for n in nodes_str.split(",") if n.strip()])
        else:
            nodes = [self.config.node_id]
        return nodes

    async def start(self) -> None:
        """Start the PBFT node."""
        if self._started:
            return

        self._started = True
        self._shutdown = False

        # Start view change timer
        self._start_view_change_timer()

        role = "PRIMARY" if self.is_primary else "REPLICA"
        logger.info(f"✅ PBFT Node started as {role} (view={self._view})")

    async def stop(self) -> None:
        """Stop the PBFT node."""
        if not self._started:
            return

        self._shutdown = True

        # Cancel view change timer
        if self._view_change_timer:
            self._view_change_timer.cancel()
            try:
                await self._view_change_timer
            except asyncio.CancelledError:
                pass

        # Cancel pending requests
        for future in self._pending.values():
            if not future.done():
                future.cancel()

        self._started = False
        logger.info("🛑 PBFT Node stopped")

    async def submit_request(
        self,
        operation: str,
        data: dict[str, Any],
        client_id: str | None = None,
        timeout: float | None = None,
    ) -> ConsensusResult:
        """Submit a request for consensus.

        Args:
            operation: Operation identifier.
            data: Operation data.
            client_id: Client identifier (defaults to node_id).
            timeout: Request timeout (defaults to config).

        Returns:
            ConsensusResult with outcome.

        Example:
            >>> result = await node.submit_request(
            ...     operation="set_value",
            ...     data={"key": "foo", "value": "bar"}
            ... )
        """
        if not self._started:
            return ConsensusResult(
                success=False,
                sequence=-1,
                view=self._view,
                error="Node not started",
            )

        start_time = time.time()
        timeout = timeout or self.config.request_timeout

        # Create request
        request = ConsensusRequest(
            client_id=client_id or self.config.node_id,
            timestamp=time.time(),
            operation=operation,
            data=data,
        )
        digest = request.digest()

        # Check if already processed
        if digest in self._replies:
            return self._replies[digest]

        # Create future for result
        future: asyncio.Future[ConsensusResult] = asyncio.Future()
        self._pending[digest] = future

        try:
            # If primary, start pre-prepare
            if self.is_primary:
                await self._initiate_consensus(request)
            else:
                # Forward to primary
                await self._forward_to_primary(request)

            # Wait for consensus
            result = await asyncio.wait_for(future, timeout=timeout)
            result.latency_ms = (time.time() - start_time) * 1000

            # Cache result
            self._replies[digest] = result
            return result

        except TimeoutError:
            logger.warning(f"Consensus timeout for {operation} after {timeout}s")

            # Consider view change
            if not self.is_primary:
                await self._request_view_change("request_timeout")

            return ConsensusResult(
                success=False,
                sequence=-1,
                view=self._view,
                error="Consensus timeout",
                latency_ms=(time.time() - start_time) * 1000,
            )
        except asyncio.CancelledError:
            return ConsensusResult(
                success=False,
                sequence=-1,
                view=self._view,
                error="Request cancelled",
            )
        finally:
            self._pending.pop(digest, None)

    async def _initiate_consensus(self, request: ConsensusRequest) -> None:
        """Initiate consensus as primary (PRE-PREPARE phase).

        Args:
            request: Client request.
        """
        if not self.is_primary:
            logger.warning("Non-primary attempted to initiate consensus")
            return

        # Assign sequence number
        self._sequence += 1
        seq = self._sequence

        # Check watermarks
        if seq > self._high_watermark:
            logger.warning(f"Sequence {seq} exceeds high watermark {self._high_watermark}")
            return

        digest = request.digest()

        # Create PRE-PREPARE message
        pre_prepare = PBFTMessage(
            msg_type=MessageType.PRE_PREPARE,
            view=self._view,
            sequence=seq,
            digest=digest,
            sender=self.config.node_id,
            payload={
                "operation": request.operation,
                "data": request.data,
                "client_id": request.client_id,
                "timestamp": request.timestamp,
            },
        )
        pre_prepare.sign(self.config.secret_key)

        # Store locally
        self._pre_prepares[(self._view, seq)] = pre_prepare

        # Broadcast to replicas
        await self._broadcast(pre_prepare)

        # Primary also sends PREPARE
        await self._send_prepare(self._view, seq, digest)

        logger.debug(f"PRE-PREPARE sent: view={self._view}, seq={seq}")

    async def handle_message(self, msg: PBFTMessage) -> None:
        """Handle incoming PBFT message.

        Args:
            msg: Received message.
        """
        if not self._started or self._shutdown:
            return

        # Verify signature
        if not msg.verify(self.config.secret_key):
            logger.warning(f"Invalid signature from {msg.sender}")
            return

        # Dispatch by type
        handlers = {
            MessageType.PRE_PREPARE: self._handle_pre_prepare,
            MessageType.PREPARE: self._handle_prepare,
            MessageType.COMMIT: self._handle_commit,
            MessageType.VIEW_CHANGE: self._handle_view_change,
            MessageType.NEW_VIEW: self._handle_new_view,
            MessageType.CHECKPOINT: self._handle_checkpoint,
        }

        handler = handlers.get(msg.msg_type)
        if handler:
            await handler(msg)
        else:
            logger.warning(f"Unknown message type: {msg.msg_type}")

    async def _handle_pre_prepare(self, msg: PBFTMessage) -> None:
        """Handle PRE-PREPARE message (replica receives from primary).

        Args:
            msg: PRE-PREPARE message.
        """
        key = (msg.view, msg.sequence)

        # Validate
        if msg.view != self._view:
            logger.debug(f"PRE-PREPARE for wrong view: {msg.view} != {self._view}")
            return

        if msg.sequence <= self._low_watermark or msg.sequence > self._high_watermark:
            logger.debug(f"PRE-PREPARE outside watermarks: {msg.sequence}")
            return

        if key in self._pre_prepares:
            # Check for conflicting pre-prepare (Byzantine primary)
            existing = self._pre_prepares[key]
            if existing.digest != msg.digest:
                logger.error(f"Conflicting PRE-PREPARE from {msg.sender}! View change needed.")
                await self._request_view_change("conflicting_pre_prepare")
                return
            return  # Duplicate

        # Verify sender is primary
        if msg.sender != self.primary_id:
            logger.warning(f"PRE-PREPARE from non-primary: {msg.sender}")
            return

        # Accept pre-prepare
        self._pre_prepares[key] = msg

        # Send PREPARE
        await self._send_prepare(msg.view, msg.sequence, msg.digest)

        logger.debug(f"Accepted PRE-PREPARE: view={msg.view}, seq={msg.sequence}")

    async def _send_prepare(self, view: int, sequence: int, digest: str) -> None:
        """Send PREPARE message.

        Args:
            view: View number.
            sequence: Sequence number.
            digest: Request digest.
        """
        prepare = PBFTMessage(
            msg_type=MessageType.PREPARE,
            view=view,
            sequence=sequence,
            digest=digest,
            sender=self.config.node_id,
        )
        prepare.sign(self.config.secret_key)

        # Store locally
        key = (view, sequence)
        if key not in self._prepares:
            self._prepares[key] = {}
        self._prepares[key][self.config.node_id] = prepare

        # Broadcast
        await self._broadcast(prepare)

        # Check if we have quorum
        await self._check_prepared(view, sequence, digest)

    async def _handle_prepare(self, msg: PBFTMessage) -> None:
        """Handle PREPARE message.

        Args:
            msg: PREPARE message.
        """
        key = (msg.view, msg.sequence)

        # Validate
        if msg.view != self._view:
            return

        if msg.sequence <= self._low_watermark or msg.sequence > self._high_watermark:
            return

        # Must have pre-prepare
        if key not in self._pre_prepares:
            return

        pre_prepare = self._pre_prepares[key]
        if pre_prepare.digest != msg.digest:
            logger.warning(f"PREPARE digest mismatch from {msg.sender}")
            return

        # Store
        if key not in self._prepares:
            self._prepares[key] = {}
        self._prepares[key][msg.sender] = msg

        # Check quorum
        await self._check_prepared(msg.view, msg.sequence, msg.digest)

    async def _check_prepared(self, view: int, sequence: int, digest: str) -> None:
        """Check if PREPARED predicate is satisfied (2f+1 matching prepares).

        Args:
            view: View number.
            sequence: Sequence number.
            digest: Request digest.
        """
        key = (view, sequence)

        if key not in self._prepares:
            return

        # Count matching prepares
        matching = sum(1 for p in self._prepares[key].values() if p.digest == digest)

        if matching >= self.config.quorum_size:
            # Send COMMIT
            await self._send_commit(view, sequence, digest)

    async def _send_commit(self, view: int, sequence: int, digest: str) -> None:
        """Send COMMIT message.

        Args:
            view: View number.
            sequence: Sequence number.
            digest: Request digest.
        """
        key = (view, sequence)

        # Don't send duplicate commits
        if key in self._commits and self.config.node_id in self._commits[key]:
            return

        commit = PBFTMessage(
            msg_type=MessageType.COMMIT,
            view=view,
            sequence=sequence,
            digest=digest,
            sender=self.config.node_id,
        )
        commit.sign(self.config.secret_key)

        # Store locally
        if key not in self._commits:
            self._commits[key] = {}
        self._commits[key][self.config.node_id] = commit

        # Broadcast
        await self._broadcast(commit)

        # Check if we have quorum
        await self._check_committed(view, sequence, digest)

    async def _handle_commit(self, msg: PBFTMessage) -> None:
        """Handle COMMIT message.

        Args:
            msg: COMMIT message.
        """
        key = (msg.view, msg.sequence)

        # Validate
        if msg.view != self._view:
            return

        if msg.sequence <= self._low_watermark or msg.sequence > self._high_watermark:
            return

        # Store
        if key not in self._commits:
            self._commits[key] = {}
        self._commits[key][msg.sender] = msg

        # Check quorum
        await self._check_committed(msg.view, msg.sequence, msg.digest)

    async def _check_committed(self, view: int, sequence: int, digest: str) -> None:
        """Check if COMMITTED predicate is satisfied (2f+1 matching commits).

        Args:
            view: View number.
            sequence: Sequence number.
            digest: Request digest.
        """
        key = (view, sequence)

        if key not in self._commits:
            return

        # Count matching commits
        matching = sum(1 for c in self._commits[key].values() if c.digest == digest)

        if matching >= self.config.commit_threshold:
            # Execute and reply
            await self._execute_and_reply(view, sequence, digest)

    async def _execute_and_reply(
        self,
        view: int,
        sequence: int,
        digest: str,
    ) -> None:
        """Execute request and send reply.

        Args:
            view: View number.
            sequence: Sequence number.
            digest: Request digest.
        """
        # Don't execute twice
        if sequence in self._executed:
            return

        key = (view, sequence)

        if key not in self._pre_prepares:
            logger.warning(f"Cannot execute: no pre-prepare for ({view}, {sequence})")
            return

        pre_prepare = self._pre_prepares[key]
        payload = pre_prepare.payload

        # Mark as executed
        self._executed.add(sequence)

        # Execute operation
        result = None
        error = None

        try:
            if self._execute_callback:
                result = await asyncio.coroutine(self._execute_callback)(
                    payload.get("operation", ""),
                    payload.get("data", {}),
                )
            else:
                result = {"executed": True, "sequence": sequence}
        except Exception as e:
            error = str(e)
            logger.error(f"Execution failed for seq {sequence}: {e}")

        # Create result
        commits_count = len(self._commits.get(key, {}))
        consensus_result = ConsensusResult(
            success=error is None,
            sequence=sequence,
            view=view,
            result=result,
            error=error,
            nodes_agreed=commits_count,
        )

        # Complete pending future
        if digest in self._pending:
            future = self._pending[digest]
            if not future.done():
                future.set_result(consensus_result)

        # Consider checkpoint
        if sequence % self.config.checkpoint_interval == 0:
            await self._create_checkpoint(sequence)

        logger.info(f"✅ Consensus reached: seq={sequence}, view={view}, nodes={commits_count}")

    async def _create_checkpoint(self, sequence: int) -> None:
        """Create a checkpoint at given sequence.

        Args:
            sequence: Sequence number for checkpoint.
        """
        # Compute state digest (simplified - would hash actual state)
        state_digest = hashlib.sha256(f"{self.config.node_id}:{sequence}".encode()).hexdigest()

        # Create checkpoint message
        checkpoint = PBFTMessage(
            msg_type=MessageType.CHECKPOINT,
            view=self._view,
            sequence=sequence,
            digest=state_digest,
            sender=self.config.node_id,
        )
        checkpoint.sign(self.config.secret_key)

        # Store locally
        if sequence not in self._checkpoints:
            self._checkpoints[sequence] = {}
        self._checkpoints[sequence][self.config.node_id] = state_digest

        # Broadcast
        await self._broadcast(checkpoint)

        # Check if stable
        await self._check_stable_checkpoint(sequence)

    async def _handle_checkpoint(self, msg: PBFTMessage) -> None:
        """Handle CHECKPOINT message.

        Args:
            msg: CHECKPOINT message.
        """
        seq = msg.sequence

        if seq not in self._checkpoints:
            self._checkpoints[seq] = {}
        self._checkpoints[seq][msg.sender] = msg.digest

        await self._check_stable_checkpoint(seq)

    async def _check_stable_checkpoint(self, sequence: int) -> None:
        """Check if checkpoint is stable (2f+1 matching).

        Args:
            sequence: Checkpoint sequence.
        """
        if sequence not in self._checkpoints:
            return

        # Count matching digests
        digests = self._checkpoints[sequence]
        if len(digests) >= self.config.quorum_size:
            # Most common digest
            from collections import Counter

            counts = Counter(digests.values())
            _most_common_digest, count = counts.most_common(1)[0]

            if count >= self.config.quorum_size:
                # Stable checkpoint
                self._stable_checkpoint = sequence
                self._low_watermark = sequence
                self._high_watermark = sequence + self.config.checkpoint_interval

                # Garbage collect old state
                self._garbage_collect(sequence)

                logger.info(f"📍 Stable checkpoint at seq {sequence}")

    def _garbage_collect(self, stable_seq: int) -> None:
        """Remove state older than stable checkpoint.

        Args:
            stable_seq: Stable checkpoint sequence.
        """
        # Clean pre-prepares
        keys_to_remove = [k for k in self._pre_prepares if k[1] <= stable_seq]
        for k in keys_to_remove:
            del self._pre_prepares[k]

        # Clean prepares
        keys_to_remove = [k for k in self._prepares if k[1] <= stable_seq]
        for k in keys_to_remove:
            del self._prepares[k]

        # Clean commits
        keys_to_remove = [k for k in self._commits if k[1] <= stable_seq]
        for k in keys_to_remove:
            del self._commits[k]

        # Clean checkpoints
        seqs_to_remove = [s for s in self._checkpoints if s < stable_seq]
        for s in seqs_to_remove:
            del self._checkpoints[s]

    # =========================================================================
    # View Change Protocol
    # =========================================================================

    def _start_view_change_timer(self) -> None:
        """Start the view change timeout timer."""
        if self._view_change_timer and not self._view_change_timer.done():
            return

        async def timer_task() -> None:
            while not self._shutdown:
                await asyncio.sleep(self.config.view_change_timeout)

                # Check if we're making progress
                # (simplified - would check pending requests)
                if self._pending:
                    logger.warning("View change timer expired with pending requests")
                    await self._request_view_change("timeout")

        self._view_change_timer = asyncio.create_task(timer_task())

    async def _request_view_change(self, reason: str) -> None:
        """Request a view change.

        Args:
            reason: Reason for view change.
        """
        new_view = self._view + 1

        logger.warning(f"Requesting view change to {new_view}: {reason}")

        # Create VIEW-CHANGE message
        view_change = PBFTMessage(
            msg_type=MessageType.VIEW_CHANGE,
            view=new_view,
            sequence=self._stable_checkpoint,
            digest="",
            sender=self.config.node_id,
            payload={
                "reason": reason,
                "checkpoints": dict(self._checkpoints.get(self._stable_checkpoint, {})),
            },
        )
        view_change.sign(self.config.secret_key)

        # Store and broadcast
        if new_view not in self._view_change_msgs:
            self._view_change_msgs[new_view] = {}
        self._view_change_msgs[new_view][self.config.node_id] = view_change

        await self._broadcast(view_change)

        # Check if we can complete view change
        await self._check_view_change(new_view)

    async def _handle_view_change(self, msg: PBFTMessage) -> None:
        """Handle VIEW-CHANGE message.

        Args:
            msg: VIEW-CHANGE message.
        """
        new_view = msg.view

        if new_view <= self._view:
            return  # Old view change

        # Store
        if new_view not in self._view_change_msgs:
            self._view_change_msgs[new_view] = {}
        self._view_change_msgs[new_view][msg.sender] = msg

        # Check if we can complete view change
        await self._check_view_change(new_view)

    async def _check_view_change(self, new_view: int) -> None:
        """Check if view change can be completed.

        Args:
            new_view: Target view number.
        """
        if new_view not in self._view_change_msgs:
            return

        msgs = self._view_change_msgs[new_view]

        if len(msgs) >= self.config.quorum_size:
            # Complete view change
            await self._complete_view_change(new_view)

    async def _complete_view_change(self, new_view: int) -> None:
        """Complete transition to new view.

        Args:
            new_view: New view number.
        """
        old_view = self._view
        self._view = new_view

        # If we're the new primary, send NEW-VIEW
        if self.is_primary:
            new_view_msg = PBFTMessage(
                msg_type=MessageType.NEW_VIEW,
                view=new_view,
                sequence=self._sequence,
                digest="",
                sender=self.config.node_id,
                payload={
                    "view_changes": [
                        m.to_dict() for m in self._view_change_msgs.get(new_view, {}).values()
                    ],
                },
            )
            new_view_msg.sign(self.config.secret_key)
            await self._broadcast(new_view_msg)

        # Clean up view change state
        views_to_remove = [v for v in self._view_change_msgs if v <= new_view]
        for v in views_to_remove:
            del self._view_change_msgs[v]

        logger.info(f"🔄 View change complete: {old_view} → {new_view}")

    async def _handle_new_view(self, msg: PBFTMessage) -> None:
        """Handle NEW-VIEW message from new primary.

        Args:
            msg: NEW-VIEW message.
        """
        if msg.view <= self._view:
            return

        # Validate sender is new primary for this view
        nodes = self._get_node_list()
        expected_primary = nodes[msg.view % len(nodes)] if nodes else msg.sender

        if msg.sender != expected_primary:
            logger.warning(f"NEW-VIEW from wrong primary: {msg.sender}")
            return

        # Accept new view
        self._view = msg.view
        logger.info(f"Accepted NEW-VIEW from {msg.sender}: view={msg.view}")

    # =========================================================================
    # Transport
    # =========================================================================

    async def _broadcast(self, msg: PBFTMessage) -> None:
        """Broadcast message to all nodes.

        Args:
            msg: Message to broadcast.
        """
        if self.transport:
            await self.transport.broadcast(msg.to_dict())
        else:
            # Local mode - handle message locally
            await self.handle_message(msg)

    async def _forward_to_primary(self, request: ConsensusRequest) -> None:
        """Forward request to primary node.

        Args:
            request: Request to forward.
        """
        if self.transport:
            await self.transport.send_to(
                self.primary_id,
                {
                    "type": "request",
                    "request": {
                        "client_id": request.client_id,
                        "timestamp": request.timestamp,
                        "operation": request.operation,
                        "data": request.data,
                    },
                },
            )
        else:
            # Local mode - handle as primary
            await self._initiate_consensus(request)

    def set_execute_callback(
        self,
        callback: Callable[[str, dict], Any],
    ) -> None:
        """Set callback for executing operations.

        Args:
            callback: Function(operation, data) -> result
        """
        self._execute_callback = callback

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get current node status."""
        return {
            "node_id": self.config.node_id,
            "is_primary": self.is_primary,
            "primary_id": self.primary_id,
            "view": self._view,
            "sequence": self._sequence,
            "stable_checkpoint": self._stable_checkpoint,
            "watermarks": {
                "low": self._low_watermark,
                "high": self._high_watermark,
            },
            "pending_requests": len(self._pending),
            "cluster_size": self.config.cluster_size,
            "byzantine_tolerance": self.config.byzantine_tolerance,
            "quorum_size": self.config.quorum_size,
        }


# =============================================================================
# Transport Implementations
# =============================================================================


class LocalTransport:
    """In-process transport for testing and single-node operation."""

    def __init__(self) -> None:
        self._nodes: dict[str, PBFTNode] = {}

    def register(self, node: PBFTNode) -> None:
        """Register a node."""
        self._nodes[node.config.node_id] = node

    async def broadcast(self, msg: dict[str, Any]) -> None:
        """Broadcast to all registered nodes."""
        pbft_msg = PBFTMessage.from_dict(msg)
        for node in self._nodes.values():
            await node.handle_message(pbft_msg)

    async def send_to(self, node_id: str, msg: dict[str, Any]) -> None:
        """Send to specific node."""
        if node_id in self._nodes:
            node = self._nodes[node_id]
            if msg.get("type") == "request":
                request = ConsensusRequest(
                    client_id=msg["request"]["client_id"],
                    timestamp=msg["request"]["timestamp"],
                    operation=msg["request"]["operation"],
                    data=msg["request"]["data"],
                )
                await node._initiate_consensus(request)


class RedisTransport:
    """Redis pub/sub transport for distributed PBFT.

    Uses Redis channels for message passing between PBFT nodes.
    """

    def __init__(self, node: PBFTNode, redis_url: str | None = None) -> None:
        self._node = node
        self._redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        self._client: Any = None
        self._pubsub: Any = None
        self._listen_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start Redis transport."""
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        self._pubsub = self._client.pubsub()

        # Subscribe to channels
        await self._pubsub.subscribe(
            "kagami:pbft:broadcast",
            f"kagami:pbft:node:{self._node.config.node_id}",
        )

        # Start listener
        self._listen_task = asyncio.create_task(self._listen())

        logger.info("Redis PBFT transport started")

    async def stop(self) -> None:
        """Stop Redis transport."""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        if self._client:
            await self._client.close()

    async def _listen(self) -> None:
        """Listen for messages."""
        async for message in self._pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])

                    # Skip our own messages
                    if data.get("sender") == self._node.config.node_id:
                        continue

                    if "msg_type" in data:
                        # PBFT message
                        pbft_msg = PBFTMessage.from_dict(data)
                        await self._node.handle_message(pbft_msg)
                    elif data.get("type") == "request":
                        # Forwarded request
                        request = ConsensusRequest(
                            client_id=data["request"]["client_id"],
                            timestamp=data["request"]["timestamp"],
                            operation=data["request"]["operation"],
                            data=data["request"]["data"],
                        )
                        await self._node._initiate_consensus(request)

                except Exception as e:
                    logger.error(f"Error processing message: {e}")

    async def broadcast(self, msg: dict[str, Any]) -> None:
        """Broadcast message to all nodes."""
        if self._client:
            await self._client.publish(
                "kagami:pbft:broadcast",
                json.dumps(msg),
            )

    async def send_to(self, node_id: str, msg: dict[str, Any]) -> None:
        """Send message to specific node."""
        if self._client:
            await self._client.publish(
                f"kagami:pbft:node:{node_id}",
                json.dumps(msg),
            )


# =============================================================================
# Factory Functions
# =============================================================================


_pbft_node: PBFTNode | None = None


async def get_pbft_node(
    config: PBFTConfig | None = None,
    use_redis: bool | None = None,
) -> PBFTNode:
    """Get or create the singleton PBFT node.

    Automatically wires RedisTransport when:
    - use_redis=True explicitly, OR
    - PBFT_USE_REDIS=true in environment, OR
    - ENVIRONMENT=production in environment

    Args:
        config: PBFT configuration.
        use_redis: Override automatic Redis detection.

    Returns:
        PBFTNode instance.

    Example:
        >>> node = await get_pbft_node()
        >>> result = await node.submit_request("set", {"key": "value"})
    """
    global _pbft_node

    if _pbft_node is None:
        # Determine if we should use Redis transport
        should_use_redis = use_redis
        if should_use_redis is None:
            env = os.environ.get("ENVIRONMENT", "development")
            pbft_redis = os.environ.get("PBFT_USE_REDIS", "").lower()
            should_use_redis = pbft_redis in ("true", "1", "yes") or env == "production"

        _pbft_node = PBFTNode(config)

        # Wire Redis transport if appropriate
        if should_use_redis:
            try:
                redis_transport = RedisTransport(_pbft_node)
                await redis_transport.start()
                _pbft_node.transport = redis_transport
                logger.info("✅ PBFT using Redis transport")
            except Exception as e:
                logger.warning(f"Redis transport failed, using local: {e}")
                local_transport = LocalTransport()
                local_transport.register(_pbft_node)
                _pbft_node.transport = local_transport
        else:
            # Use local transport for development/testing
            local_transport = LocalTransport()
            local_transport.register(_pbft_node)
            _pbft_node.transport = local_transport
            logger.debug("PBFT using local transport (development mode)")

        await _pbft_node.start()

    return _pbft_node


async def shutdown_pbft() -> None:
    """Shutdown the PBFT node and transport."""
    global _pbft_node

    if _pbft_node:
        # Stop Redis transport if present
        if _pbft_node.transport and hasattr(_pbft_node.transport, "stop"):
            try:
                await _pbft_node.transport.stop()
            except Exception as e:
                logger.debug(f"Transport stop error: {e}")

        await _pbft_node.stop()
        _pbft_node = None


__all__ = [
    "ConsensusRequest",
    "ConsensusResult",
    "LocalTransport",
    "MessageType",
    "PBFTConfig",
    "PBFTMessage",
    "PBFTNode",
    "PBFTPhase",
    "RedisTransport",
    "get_pbft_node",
    "shutdown_pbft",
]
