"""Cryptographic Provenance Chain with etcd Integration.

Provides tamper-evident audit trails for agent actions using:
1. Ed25519 signatures for authenticity
2. Hash chains for integrity
3. etcd distributed consensus for witness/ordering
4. Multi-instance verification

SECURITY PROPERTIES:
- Non-repudiation: Signatures prove origin
- Tamper-evidence: Hash chain detects modifications
- Distributed witness: etcd consensus provides ordering
- Verifiability: Any instance can verify any record

Usage:
    from kagami.core.safety.provenance_chain import get_provenance_chain

    chain = get_provenance_chain()
    await chain.initialize()

    # Record an action
    record = await chain.record_action(
        action="file_write",
        context={"path": "foo.py", "lines_changed": 10},
        output_hash="sha256:abc123...",
    )

    # Verify a record
    is_valid = await chain.verify_record(record.record_hash)

    # Get full chain for correlation
    records = await chain.get_chain("correlation_id_123")

Created: December 5, 2025
Based on: CBF threat mitigation analysis for deception/sleeper/worm attacks
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


# =============================================================================
# CRYPTOGRAPHIC PRIMITIVES
# =============================================================================


class SignatureScheme(Enum):
    """Supported signature schemes."""

    ED25519 = "ed25519"
    HMAC_SHA256 = "hmac_sha256"  # Fallback if nacl unavailable


@dataclass
class KeyPair:
    """Cryptographic key pair for signing."""

    public_key: bytes
    private_key: bytes
    scheme: SignatureScheme
    instance_id: str
    created_at: float = field(default_factory=time.time)

    def public_key_hex(self) -> str:
        """Get public key as hex string."""
        return self.public_key.hex()

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage (public key only!)."""
        return {
            "public_key": self.public_key_hex(),
            "scheme": self.scheme.value,
            "instance_id": self.instance_id,
            "created_at": self.created_at,
        }


@dataclass
class ProvenanceRecord:
    """Single provenance record in the chain."""

    record_hash: str  # SHA-256 of canonical content
    previous_hash: str | None  # Link to previous record (None for genesis)
    correlation_id: str  # Links related records
    instance_id: str  # Originating instance
    timestamp: float  # Unix timestamp
    action: str  # Action type (e.g., "file_write", "shell_exec")
    context: dict[str, Any]  # Action context (sanitized)
    output_hash: str | None  # Hash of action output (for verification)
    signature: str  # Ed25519 signature (hex)
    scheme: str  # Signature scheme used
    witnesses: list[str] = field(default_factory=list[Any])  # Witness signatures

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "record_hash": self.record_hash,
            "previous_hash": self.previous_hash,
            "correlation_id": self.correlation_id,
            "instance_id": self.instance_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "context": self.context,
            "output_hash": self.output_hash,
            "signature": self.signature,
            "scheme": self.scheme,
            "witnesses": self.witnesses,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProvenanceRecord:
        """Deserialize from storage."""
        return cls(
            record_hash=data["record_hash"],
            previous_hash=data.get("previous_hash"),
            correlation_id=data["correlation_id"],
            instance_id=data["instance_id"],
            timestamp=data["timestamp"],
            action=data["action"],
            context=data.get("context", {}),
            output_hash=data.get("output_hash"),
            signature=data["signature"],
            scheme=data.get("scheme", "ed25519"),
            witnesses=data.get("witnesses", []),
        )

    def canonical_bytes(self) -> bytes:
        """Get canonical byte representation for hashing/signing."""
        # Deterministic JSON serialization
        canonical = {
            "previous_hash": self.previous_hash,
            "correlation_id": self.correlation_id,
            "instance_id": self.instance_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "context": self.context,
            "output_hash": self.output_hash,
        }
        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()


# =============================================================================
# CRYPTOGRAPHIC OPERATIONS
# =============================================================================


class CryptoProvider:
    """Handles cryptographic operations with fallback support."""

    def __init__(self) -> None:
        self._nacl_available: bool = False
        # Optional runtime dependency (PyNaCl). Keep typing permissive.
        self._signing_key: Any | None = None
        self._verify_key: Any | None = None
        self._hmac_key: bytes | None = None

        # Try to import nacl for Ed25519
        try:
            import nacl.encoding
            import nacl.signing

            self._nacl_available = True
            logger.info("Using Ed25519 signatures (nacl available)")
        except ImportError:
            logger.warning("nacl not available, falling back to HMAC-SHA256")

    def generate_keypair(self, instance_id: str) -> KeyPair:
        """Generate new signing keypair."""
        if self._nacl_available:
            import nacl.signing

            signing_key = nacl.signing.SigningKey.generate()
            verify_key = signing_key.verify_key

            return KeyPair(
                public_key=bytes(verify_key),
                private_key=bytes(signing_key),
                scheme=SignatureScheme.ED25519,
                instance_id=instance_id,
            )
        else:
            # HMAC fallback - use random key
            import secrets

            key = secrets.token_bytes(32)
            return KeyPair(
                public_key=key,  # In HMAC, "public" key is shared secret
                private_key=key,
                scheme=SignatureScheme.HMAC_SHA256,
                instance_id=instance_id,
            )

    def load_keypair(self, keypair: KeyPair) -> None:
        """Load keypair for signing operations."""
        if keypair.scheme == SignatureScheme.ED25519:
            if not self._nacl_available:
                raise RuntimeError("Ed25519 keypair requires nacl")
            import nacl.signing

            self._signing_key = nacl.signing.SigningKey(keypair.private_key)
            self._verify_key = self._signing_key.verify_key
        else:
            self._hmac_key = keypair.private_key

    def sign(self, data: bytes) -> tuple[str, str]:
        """Sign data and return (signature_hex, scheme).

        Returns:
            Tuple of (signature as hex string, scheme name)
        """
        if self._nacl_available and self._signing_key is not None:
            signed = self._signing_key.sign(data)
            # Extract just the signature (first 64 bytes)
            signature = signed.signature
            return signature.hex(), SignatureScheme.ED25519.value
        elif self._hmac_key is not None:
            import hmac as hmac_module

            signature = hmac_module.new(self._hmac_key, data, hashlib.sha256).digest()
            return signature.hex(), SignatureScheme.HMAC_SHA256.value
        else:
            raise RuntimeError("No signing key loaded")

    def verify(
        self,
        data: bytes,
        signature_hex: str,
        public_key_hex: str,
        scheme: str,
    ) -> bool:
        """Verify signature against data.

        Args:
            data: Original data bytes
            signature_hex: Signature as hex string
            public_key_hex: Public key as hex string
            scheme: Signature scheme name

        Returns:
            True if signature is valid
        """
        try:
            signature = bytes.fromhex(signature_hex)
            public_key = bytes.fromhex(public_key_hex)

            if scheme == SignatureScheme.ED25519.value:
                if not self._nacl_available:
                    logger.error("Cannot verify Ed25519 signature: nacl unavailable")
                    return False
                import nacl.signing

                verify_key = nacl.signing.VerifyKey(public_key)
                try:
                    verify_key.verify(data, signature)
                    return True
                except (nacl.exceptions.BadSignatureError, ValueError, TypeError) as e:
                    # BadSignatureError: signature verification failed
                    # ValueError: invalid signature or data format
                    # TypeError: wrong argument types
                    logger.debug(f"Signature verification failed: {e}")
                    return False

            elif scheme == SignatureScheme.HMAC_SHA256.value:
                import hmac as hmac_module

                expected = hmac_module.new(public_key, data, hashlib.sha256).digest()
                return hmac_module.compare_digest(signature, expected)

            else:
                logger.error(f"Unknown signature scheme: {scheme}")
                return False

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False


# =============================================================================
# ETCD STORAGE BACKEND
# =============================================================================


class EtcdProvenanceStorage:
    """etcd-backed storage for provenance records."""

    # Key prefixes
    PREFIX_RECORDS = "kagami:provenance:records:"
    PREFIX_CHAINS = "kagami:provenance:chains:"
    PREFIX_WITNESSES = "kagami:provenance:witnesses:"
    PREFIX_KEYS = "kagami:provenance:keys:"

    def __init__(self, ttl: int = 86400 * 30) -> None:
        """Initialize etcd storage.

        Args:
            ttl: Record TTL in seconds (default: 30 days)
        """
        self.ttl = ttl
        # etcd client is dynamically typed (etcd3/grpc). Keep permissive.
        self._client: Any | None = None
        self._enabled: bool = False

        # CBF rate limiting state
        self._last_write: float = 0.0
        self._write_count: int = 0
        self._rate_limit_window: float = 1.0  # 1 second window
        self._max_writes_per_window: int = 100  # 100 writes/sec limit

    async def initialize(self) -> bool:
        """Initialize etcd connection."""
        try:
            # Dynamic import to avoid safety ↔ consensus cycles.
            import importlib

            consensus_mod = importlib.import_module("kagami.core.consensus")
            get_etcd_client = getattr(consensus_mod, "get_etcd_client", None)
            if get_etcd_client is None:
                return False
            self._client = get_etcd_client()
            if self._client is not None:
                self._enabled = True
                logger.info("✅ Provenance storage connected to etcd")
                return True
            else:
                logger.warning("etcd unavailable for provenance storage")
                return False
        except Exception as e:
            logger.warning(f"Failed to initialize etcd provenance storage: {e}")
            return False

    def _check_rate_limit(self) -> float:
        """Check if rate limit is violated.

        Returns:
            Barrier value (positive = safe, negative = violation)
        """
        current_time = time.time()

        # Reset counter if outside window
        if current_time - self._last_write > self._rate_limit_window:
            self._write_count = 0
            self._last_write = current_time

        # Increment counter
        self._write_count += 1

        # Compute barrier: remaining writes before limit
        h_value = float(self._max_writes_per_window - self._write_count)
        return h_value

    async def _cbf_protected_put(self, key: str, value: bytes, lease: Any | None = None) -> bool:
        """Execute etcd PUT with CBF rate limit protection.

        Args:
            key: etcd key
            value: Value bytes
            lease: Optional lease for TTL

        Returns:
            True if write succeeded

        Raises:
            RuntimeError: If rate limit violated
        """

        # Check rate limit barrier
        h_value = self._check_rate_limit()

        if h_value < 0:
            logger.error(
                f"⛔ CBF violation: provenance_etcd_write rate limit exceeded "
                f"({self._write_count}/{self._max_writes_per_window} writes/sec)"
            )
            raise RuntimeError(
                f"Provenance write rate limit exceeded: "
                f"{self._write_count} writes in {self._rate_limit_window}s"
            )

        if h_value < 10:  # Warning threshold
            logger.warning(
                f"⚠️  CBF warning: provenance_etcd_write approaching limit "
                f"({self._write_count}/{self._max_writes_per_window})"
            )

        # Execute write
        if self._client is None:
            raise RuntimeError("etcd client not initialized")

        try:
            self._client.put(key, value, lease=lease)
            return True
        except Exception as e:
            logger.error(f"etcd PUT failed: {e}")
            raise

    async def store_record(self, record: ProvenanceRecord) -> bool:
        """Store provenance record in etcd with CBF protection.

        Args:
            record: Record to store

        Returns:
            True if stored successfully
        """
        if not self._enabled or self._client is None:
            return False

        try:
            # Store the record by hash (CBF-protected)
            record_key = f"{self.PREFIX_RECORDS}{record.record_hash}"
            record_value = json.dumps(record.to_dict())

            # Use lease for TTL
            lease = self._client.lease(self.ttl)
            await self._cbf_protected_put(record_key, record_value.encode(), lease=lease)

            # Update chain head pointer (CBF-protected)
            chain_key = f"{self.PREFIX_CHAINS}{record.instance_id}:{record.correlation_id}"
            chain_value = json.dumps(
                {
                    "head": record.record_hash,
                    "updated_at": time.time(),
                    "record_count": await self._count_chain_records(record.correlation_id) + 1,
                }
            )
            await self._cbf_protected_put(chain_key, chain_value.encode(), lease=lease)

            logger.debug(f"Stored provenance record: {record.record_hash[:16]}...")
            return True

        except RuntimeError:
            # CBF violations must propagate - they are safety-critical
            raise
        except Exception as e:
            logger.error(f"Failed to store provenance record: {e}")
            return False

    async def get_record(self, record_hash: str) -> ProvenanceRecord | None:
        """Retrieve record by hash.

        Args:
            record_hash: SHA-256 hash of record

        Returns:
            ProvenanceRecord or None if not found
        """
        if not self._enabled or self._client is None:
            return None

        try:
            key = f"{self.PREFIX_RECORDS}{record_hash}"
            value, _ = self._client.get(key)

            if value:
                data = json.loads(value.decode())
                return ProvenanceRecord.from_dict(data)
            return None

        except Exception as e:
            logger.error(f"Failed to get provenance record: {e}")
            return None

    async def get_chain(self, correlation_id: str) -> list[ProvenanceRecord]:
        """Get all records in a chain by correlation_id.

        Args:
            correlation_id: Correlation ID linking records

        Returns:
            List of records in chain order (newest first)
        """
        if not self._enabled or self._client is None:
            return []

        try:
            # Get all records and filter by correlation_id
            records = []
            for value, _metadata in self._client.get_prefix(self.PREFIX_RECORDS):
                try:
                    data = json.loads(value.decode())
                    if data.get("correlation_id") == correlation_id:
                        records.append(ProvenanceRecord.from_dict(data))
                except (json.JSONDecodeError, UnicodeDecodeError, KeyError, ValueError) as e:
                    # JSONDecodeError: malformed JSON
                    # UnicodeDecodeError: invalid encoding
                    # KeyError: missing required field
                    # ValueError: invalid field value
                    logger.debug(f"Skipping malformed record: {e}")
                    continue

            # Sort by timestamp (newest first)
            records.sort(key=lambda r: r.timestamp, reverse=True)
            return records

        except Exception as e:
            logger.error(f"Failed to get provenance chain: {e}")
            return []

    async def store_public_key(self, instance_id: str, public_key_hex: str, scheme: str) -> bool:
        """Store instance public key for verification with CBF protection.

        Args:
            instance_id: Instance identifier
            public_key_hex: Public key as hex string
            scheme: Signature scheme

        Returns:
            True if stored successfully
        """
        if not self._enabled or self._client is None:
            return False

        try:
            key = f"{self.PREFIX_KEYS}{instance_id}"
            value = json.dumps(
                {
                    "public_key": public_key_hex,
                    "scheme": scheme,
                    "registered_at": time.time(),
                }
            )

            # Keys don't expire (no lease) - CBF-protected
            await self._cbf_protected_put(key, value.encode())
            logger.info(f"Registered public key for instance: {instance_id}")
            return True

        except RuntimeError:
            # CBF violations must propagate - they are safety-critical
            raise
        except Exception as e:
            logger.error(f"Failed to store public key: {e}")
            return False

    async def get_public_key(self, instance_id: str) -> tuple[str, str] | None:
        """Get instance public key.

        Args:
            instance_id: Instance identifier

        Returns:
            Tuple of (public_key_hex, scheme) or None
        """
        if not self._enabled or self._client is None:
            return None

        try:
            key = f"{self.PREFIX_KEYS}{instance_id}"
            value, _ = self._client.get(key)

            if value:
                data = json.loads(value.decode())
                return (data["public_key"], data["scheme"])
            return None

        except Exception as e:
            logger.error(f"Failed to get public key: {e}")
            return None

    async def add_witness(self, record_hash: str, witness_id: str, signature: str) -> bool:
        """Add witness signature to record with CBF protection.

        Args:
            record_hash: Record being witnessed
            witness_id: Witnessing instance ID
            signature: Witness signature

        Returns:
            True if added successfully
        """
        if not self._enabled or self._client is None:
            return False

        try:
            key = f"{self.PREFIX_WITNESSES}{record_hash}:{witness_id}"
            value = json.dumps(
                {
                    "witness_id": witness_id,
                    "signature": signature,
                    "witnessed_at": time.time(),
                }
            )

            lease = self._client.lease(self.ttl)
            await self._cbf_protected_put(key, value.encode(), lease=lease)
            return True

        except RuntimeError:
            # CBF violations must propagate - they are safety-critical
            raise
        except Exception as e:
            logger.error(f"Failed to add witness: {e}")
            return False

    async def get_witnesses(self, record_hash: str) -> list[dict[str, Any]]:
        """Get all witnesses for a record.

        Args:
            record_hash: Record hash

        Returns:
            List of witness records
        """
        if not self._enabled or self._client is None:
            return []

        try:
            prefix = f"{self.PREFIX_WITNESSES}{record_hash}:"
            witnesses = []

            for value, _ in self._client.get_prefix(prefix):
                try:
                    witnesses.append(json.loads(value.decode()))
                except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
                    # JSONDecodeError: malformed JSON
                    # UnicodeDecodeError: invalid encoding
                    # KeyError: missing required field
                    logger.debug(f"Skipping malformed witness record: {e}")
                    continue

            return witnesses

        except Exception as e:
            logger.error(f"Failed to get witnesses: {e}")
            return []

    async def _count_chain_records(self, correlation_id: str) -> int:
        """Count records in a chain."""
        records = await self.get_chain(correlation_id)
        return len(records)


# =============================================================================
# PROVENANCE CHAIN MANAGER
# =============================================================================


class ProvenanceChain:
    """Main interface for cryptographic provenance tracking.

    Provides:
    - Action recording with signatures
    - Chain verification
    - Distributed witnessing
    - Tamper detection
    """

    def __init__(
        self,
        instance_id: str | None = None,
        key_path: str | None = None,
    ) -> None:
        """Initialize provenance chain.

        Args:
            instance_id: Unique instance identifier
            key_path: Path to store/load keypair (default: .kagami/provenance_key.json)
        """
        self.instance_id = instance_id or self._generate_instance_id()
        self.key_path = Path(key_path or os.path.expanduser("~/.kagami/provenance_key.json"))

        self._crypto = CryptoProvider()
        self._storage = EtcdProvenanceStorage()
        self._keypair: KeyPair | None = None
        self._chain_heads: dict[str, str] = {}  # correlation_id -> latest hash
        self._initialized = False

    def _generate_instance_id(self) -> str:
        """Generate unique instance ID."""
        import socket
        import uuid

        hostname = socket.gethostname()
        pid = os.getpid()
        unique = uuid.uuid4().hex[:8]
        return f"kagami-{hostname}-{pid}-{unique}"

    async def initialize(self) -> bool:
        """Initialize provenance chain.

        - Loads or generates keypair
        - Connects to etcd
        - Registers public key

        Returns:
            True if initialized successfully
        """
        if self._initialized:
            return True

        try:
            # Load or generate keypair
            if self.key_path.exists():
                self._keypair = self._load_keypair()
                logger.info(f"Loaded existing keypair for {self.instance_id}")
            else:
                self._keypair = self._crypto.generate_keypair(self.instance_id)
                self._save_keypair()
                logger.info(f"Generated new keypair for {self.instance_id}")

            # Load keypair into crypto provider
            if self._keypair is None:
                raise RuntimeError(
                    f"ProvenanceChain initialization failed: keypair is None after "
                    f"generation/loading for instance {self.instance_id}"
                )
            self._crypto.load_keypair(self._keypair)

            # Initialize storage
            await self._storage.initialize()

            # Register public key in etcd
            if self._storage._enabled:
                await self._storage.store_public_key(
                    self.instance_id,
                    self._keypair.public_key_hex(),
                    self._keypair.scheme.value,
                )

            self._initialized = True
            logger.info(f"✅ Provenance chain initialized for {self.instance_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize provenance chain: {e}")
            return False

    def _load_keypair(self) -> KeyPair:
        """Load keypair from disk."""
        with open(self.key_path) as f:
            data = json.load(f)

        return KeyPair(
            public_key=bytes.fromhex(data["public_key"]),
            private_key=bytes.fromhex(data["private_key"]),
            scheme=SignatureScheme(data["scheme"]),
            instance_id=data["instance_id"],
            created_at=data.get("created_at", time.time()),
        )

    def _save_keypair(self) -> None:
        """Save keypair to disk (SECURE THE FILE!)."""
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self._keypair is None:
            raise RuntimeError("Cannot save keypair before it is generated/loaded")
        keypair = self._keypair

        data = {
            "public_key": keypair.public_key_hex(),
            "private_key": keypair.private_key.hex(),
            "scheme": keypair.scheme.value,
            "instance_id": keypair.instance_id,
            "created_at": keypair.created_at,
        }

        with open(self.key_path, "w") as f:
            json.dump(data, f, indent=2)

        # Restrict permissions (owner read/write only)
        os.chmod(self.key_path, 0o600)
        logger.info(f"Saved keypair to {self.key_path} (mode 0600)")

    async def record_action(
        self,
        action: str,
        context: dict[str, Any],
        correlation_id: str | None = None,
        output_hash: str | None = None,
    ) -> ProvenanceRecord:
        """Record an action with cryptographic signature.

        Args:
            action: Action type (e.g., "file_write", "shell_exec")
            context: Action context (will be sanitized)
            correlation_id: Links related records (auto-generated if None)
            output_hash: Hash of action output for verification

        Returns:
            Signed ProvenanceRecord
        """
        if not self._initialized:
            await self.initialize()

        # Generate correlation_id if not provided
        if correlation_id is None:
            import uuid

            correlation_id = uuid.uuid4().hex[:16]

        # Get previous hash for chain linking
        previous_hash = self._chain_heads.get(correlation_id)

        # Sanitize context (remove sensitive data)
        sanitized_context = self._sanitize_context(context)

        # Create record (unsigned)
        timestamp = time.time()
        record = ProvenanceRecord(
            record_hash="",  # Will be computed
            previous_hash=previous_hash,
            correlation_id=correlation_id,
            instance_id=self.instance_id,
            timestamp=timestamp,
            action=action,
            context=sanitized_context,
            output_hash=output_hash,
            signature="",  # Will be computed
            scheme="",  # Will be set[Any]
        )

        # Compute hash of canonical content
        canonical = record.canonical_bytes()
        record_hash = hashlib.sha256(canonical).hexdigest()
        record.record_hash = record_hash

        # Sign the record
        signature, scheme = self._crypto.sign(canonical)
        record.signature = signature
        record.scheme = scheme

        # Store in etcd
        await self._storage.store_record(record)

        # Update chain head
        self._chain_heads[correlation_id] = record_hash

        logger.debug(
            f"Recorded action '{action}' with hash {record_hash[:16]}... "
            f"(correlation: {correlation_id})"
        )

        return record

    async def verify_record(self, record_hash: str) -> tuple[bool, str]:
        """Verify a record's signature and chain integrity.

        Args:
            record_hash: Hash of record to verify

        Returns:
            Tuple of (is_valid, reason)
        """
        # Fetch record
        record = await self._storage.get_record(record_hash)
        if record is None:
            return False, f"Record not found: {record_hash}"

        # Verify hash matches content
        canonical = record.canonical_bytes()
        computed_hash = hashlib.sha256(canonical).hexdigest()
        if computed_hash != record.record_hash:
            return False, f"Hash mismatch: computed {computed_hash}, stored {record.record_hash}"

        # Get public key for instance
        key_info = await self._storage.get_public_key(record.instance_id)
        if key_info is None:
            return False, f"Public key not found for instance: {record.instance_id}"

        public_key_hex, scheme = key_info

        # Verify signature
        is_valid = self._crypto.verify(
            canonical,
            record.signature,
            public_key_hex,
            scheme,
        )

        if not is_valid:
            return False, "Invalid signature"

        # Verify chain link (if not genesis)
        if record.previous_hash is not None:
            prev_record = await self._storage.get_record(record.previous_hash)
            if prev_record is None:
                return False, f"Chain broken: previous record not found {record.previous_hash}"

            # Verify previous record is older
            if prev_record.timestamp >= record.timestamp:
                return False, "Chain ordering violation: previous record is not older"

        return True, "Valid"

    async def verify_chain(self, correlation_id: str) -> tuple[bool, list[str]]:
        """Verify entire chain integrity.

        Args:
            correlation_id: Chain to verify

        Returns:
            Tuple of (all_valid, list[Any] of issues)
        """
        issues = []
        records = await self._storage.get_chain(correlation_id)

        if not records:
            return True, []  # Empty chain is valid

        # Verify each record and chain links
        for i, record in enumerate(records):
            is_valid, reason = await self.verify_record(record.record_hash)
            if not is_valid:
                issues.append(f"Record {record.record_hash[:16]}: {reason}")

            # Verify link to next (older) record
            if i < len(records) - 1:
                next_record = records[i + 1]
                if record.previous_hash != next_record.record_hash:
                    issues.append(
                        f"Chain break between {record.record_hash[:16]} and {next_record.record_hash[:16]}"
                    )

        return len(issues) == 0, issues

    async def witness_record(self, record_hash: str) -> bool:
        """Add this instance's witness signature to a record.

        Args:
            record_hash: Record to witness

        Returns:
            True if witnessed successfully
        """
        if not self._initialized:
            await self.initialize()

        # Fetch and verify record first
        is_valid, reason = await self.verify_record(record_hash)
        if not is_valid:
            logger.warning(f"Cannot witness invalid record: {reason}")
            return False

        # Sign the record hash as witness
        signature, _ = self._crypto.sign(record_hash.encode())

        # Store witness
        return await self._storage.add_witness(
            record_hash,
            self.instance_id,
            signature,
        )

    async def get_chain(self, correlation_id: str) -> list[ProvenanceRecord]:
        """Get all records in a chain.

        Args:
            correlation_id: Chain identifier

        Returns:
            List of records (newest first)
        """
        return await self._storage.get_chain(correlation_id)

    def _sanitize_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive data from context.

        ARCHITECTURE (December 22, 2025):
        Use exact key matching only - no substring heuristics.

        Args:
            context: Raw context dict[str, Any]

        Returns:
            Sanitized context
        """
        # Exact sensitive key names - no substring matching
        sensitive_keys = {
            "password",
            "secret",
            "token",
            "api_key",
            "private_key",
            "credential",
            "credentials",
            "auth",
            "auth_token",
            "bearer",
            "bearer_token",
            "jwt",
            "jwt_token",
            "access_token",
            "refresh_token",
            "session_token",
            "encryption_key",
            "signing_key",
        }

        def _sanitize(obj: Any, depth: int = 0) -> Any:
            if depth > 10:  # Prevent infinite recursion
                return "[TRUNCATED]"

            if isinstance(obj, dict):
                return {
                    k: "[REDACTED]"
                    # Exact match on lowercase key - no substring matching
                    if k.lower() in sensitive_keys
                    else _sanitize(v, depth + 1)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [_sanitize(item, depth + 1) for item in obj[:100]]  # Limit list[Any] size
            elif isinstance(obj, str):
                if len(obj) > 1000:
                    return obj[:1000] + "...[TRUNCATED]"
                return obj
            elif isinstance(obj, int | float | bool | type(None)):
                return obj
            else:
                return str(obj)[:200]

        # context is a dict[str, Any] -> sanitized result is also a dict[str, Any]; cast for mypy.
        return cast(dict[str, Any], _sanitize(context))


# =============================================================================
# GLOBAL SINGLETON
# =============================================================================


_provenance_chain: ProvenanceChain | None = None


def get_provenance_chain() -> ProvenanceChain:
    """Get global provenance chain instance."""
    global _provenance_chain

    if _provenance_chain is None:
        instance_id = os.getenv("KAGAMI_INSTANCE_ID")
        _provenance_chain = ProvenanceChain(instance_id=instance_id)

    return _provenance_chain


__all__ = [
    "KeyPair",
    "ProvenanceChain",
    "ProvenanceRecord",
    "SignatureScheme",
    "get_provenance_chain",
]
