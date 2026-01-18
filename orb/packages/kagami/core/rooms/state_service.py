from __future__ import annotations

"""Room State Service — Persistent Storage and CRDT Integration.

This module provides the persistence layer for room state management,
integrating with Redis for storage and the CRDT module for conflict
resolution.

Architecture:
    Client → API Route → StateService → Redis
                            ↓
                          CRDT Layer
                            ↓
                       World Model Sync

Key Responsibilities:
    1. **Snapshot Persistence**: Store and retrieve room state snapshots
    2. **Delta History**: Track operation history for catchup
    3. **Sequence Numbers**: Assign monotonic sequence numbers to operations
    4. **Encryption**: Optional transparent encryption for sensitive rooms
    5. **CRDT Coordination**: Apply operations through CRDT for consistency
    6. **World Model Sync**: Notify world model of state changes

Redis Key Schema:
    - kagami:rooms:{room_id}:snapshot — Current state snapshot
    - kagami:rooms:{room_id}:deltas — Delta history (list)
    - kagami:rooms:{room_id}:seq — Current sequence number
    - kagami:rooms:{room_id}:anchors — Anchor positions (hash)
    - kagami:rooms:{room_id}:crdt_meta — CRDT metadata
    - kagami:rooms:{room_id}:lock — Distributed lock
    - kagami:rooms:{room_id}:encryption_enabled — Encryption flag

Encryption:
    Room encryption is monotonic: once enabled, it cannot be disabled.
    This prevents accidental data exposure if encryption is toggled.

Thread Safety:
    Uses both Redis-based distributed locks and local asyncio locks
    to prevent concurrent modifications to room state.

Example:
    >>> # Get current snapshot
    >>> snapshot = await get_snapshot("room-123")
    >>> print(snapshot.state)
    >>>
    >>> # Apply an operation
    >>> op = Operation(...)
    >>> await apply_operation_to_room("room-123", op)
    >>>
    >>> # Get recent deltas for catchup
    >>> deltas = await get_recent_deltas("room-123", limit=50)

See Also:
    - kagami.core.rooms.crdt: CRDT implementation
    - kagami.core.rooms.compression: State compression
    - kagami.core.rooms.reconnection: Client reconnection handling
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import asyncio  # Async I/O and locks
import base64  # Encoding for encrypted data
import json  # JSON serialization fallback
import logging  # Error and debug logging
import os  # Environment configuration
import time  # Timestamps
import uuid  # Unique ID generation
from dataclasses import dataclass  # Clean data structures
from typing import Any  # Type hints

# =============================================================================
# INTERNAL IMPORTS
# =============================================================================
from kagami.core.caching.redis import RedisClientFactory  # Redis client factory

logger = logging.getLogger(__name__)

# =============================================================================
# OPTIONAL DEPENDENCIES
# =============================================================================
# CRDT and compression are optional to allow basic room functionality
# even if the full CRDT module has import issues.

try:
    from kagami.core.rooms.crdt import RoomStateCRDT as _RoomStateCRDT  # noqa: F401

    CRDT_AVAILABLE = True  # Full CRDT conflict resolution available
except ImportError:
    CRDT_AVAILABLE = False  # Fall back to basic state replacement

try:
    from kagami.core.rooms.compression import compress_state as _compress_state  # noqa: F401

    COMPRESSION_AVAILABLE = True  # MessagePack compression available
except ImportError:
    COMPRESSION_AVAILABLE = False  # Fall back to JSON

# =============================================================================
# REDIS KEY TEMPLATES
# =============================================================================
# All room data is namespaced under kagami:rooms:{room_id}:*

_SNAP_KEY = "kagami:rooms:{room_id}:snapshot"  # Current state snapshot
_DELTA_KEY = "kagami:rooms:{room_id}:deltas"  # Delta history (Redis list)
_SEQ_KEY = "kagami:rooms:{room_id}:seq"  # Monotonic sequence counter
_ANCHORS_HASH = "kagami:rooms:{room_id}:anchors"  # User cursor positions
_ROOM_ENC_FLAG_KEY = "kagami:rooms:{room_id}:encryption_enabled"  # Encryption latch
_CRDT_META_KEY = "kagami:rooms:{room_id}:crdt_meta"  # CRDT metadata (LWW, etc.)
_ROOM_LOCK_KEY = "kagami:rooms:{room_id}:lock"  # Distributed lock key

# =============================================================================
# ENCRYPTION CONFIGURATION
# =============================================================================
# Prefix for encrypted payloads (allows detection during reads)
_ENC_PREFIX = "enc:"

# Global encryption provider instance (lazy-initialized)
_ENCRYPTION_PROVIDER: Any | None = None

# =============================================================================
# CONCURRENCY PRIMITIVES
# =============================================================================
# Local asyncio locks per room (supplements Redis distributed locks)
_LOCAL_ROOM_LOCKS: dict[str, asyncio.Lock] = {}

# =============================================================================
# WORLD MODEL INTEGRATION
# =============================================================================
# When enabled, room state changes are synced to the world model for
# predictive planning by the Nexus (e₄) colony RSSM.
#
# Environment variable: ENABLE_WORLD_MODEL_SYNC
#   - Default: "1" (enabled)
#   - Set to "0", "false", "no", or "off" to disable
#
# Integration provides:
#   - Social graph updates (member presence, relationships)
#   - Spatial scene updates (physics entities, positions)
#   - Event: "room.state_changed" on unified bus

_ENABLE_WORLD_MODEL_SYNC = os.getenv("ENABLE_WORLD_MODEL_SYNC", "1").lower() in (
    "1",
    "true",
    "yes",
    "on",
)


# =============================================================================
# ENCRYPTION DETECTION
# =============================================================================
# Functions to detect and handle encrypted room data.


def _looks_encrypted(raw: str | bytes) -> bool:
    """Check if a stored value uses the rooms encryption prefix.

    Encrypted values are prefixed with 'enc:' followed by base64 data.
    This allows detection without attempting decryption.

    Args:
        raw: Stored value from Redis (bytes or string).

    Returns:
        True if value starts with encryption prefix.
    """
    try:
        s = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
        return s.startswith(_ENC_PREFIX)
    except (TypeError, ValueError, UnicodeDecodeError):
        return False  # Treat parse errors as not encrypted


async def is_room_encryption_enabled(room_id: str) -> bool:
    """Check if encryption has been latched ON for this room.

    Encryption is monotonic: once enabled, it cannot be disabled.
    This prevents accidental data exposure if configuration changes.

    Args:
        room_id: Room identifier.

    Returns:
        True if room has encryption enabled.

    Note:
        This flag is stored in Redis and checked on every read/write.
        Once set to '1', any attempt to set to '0' will be rejected.
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    raw = await r.get(_ROOM_ENC_FLAG_KEY.format(room_id=room_id))
    return str(raw or "").strip() == "1"


async def set_room_encryption_enabled(room_id: str, enabled: bool) -> None:
    """Enable encryption for a room (irreversible operation).

    Encryption enablement is monotonic: once enabled, it cannot be disabled.
    This is a safety feature to prevent accidental data exposure.

    Args:
        room_id: Room identifier.
        enabled: True to enable encryption.

    Raises:
        RuntimeError: If attempting to disable after enabling.
        RuntimeError: If no encryption provider is available.
        RuntimeError: If encryption keys are not configured properly.

    Note:
        Validates encryption provider works before latching.
        In test mode, allows ephemeral keys; in production, requires
        KAGAMI_ENCRYPTION_KEYS environment variable.
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    cur = await r.get(_ROOM_ENC_FLAG_KEY.format(room_id=room_id))
    cur_on = str(cur or "").strip() == "1"
    if not enabled:
        if cur_on:
            raise RuntimeError("Rooms encryption cannot be disabled once enabled for a room")
        # If it was never enabled, leave unset/disabled.
        return
    if not cur_on:
        # Validate provider works BEFORE latching.
        prov = _get_encryption_provider()
        if prov is None:
            raise RuntimeError("Rooms encryption requested but no EncryptionProvider available")
        # Safety: do not allow irreversible encryption with an ephemeral dev key.
        # In tests we allow this (fake redis + ephemeral keys), but in real runs it can
        # brick rooms across restarts.
        try:
            is_test_mode = os.getenv("KAGAMI_TEST_MODE", "0").lower() in ("1", "true", "yes", "on")
        except (TypeError, AttributeError):
            is_test_mode = False
        if not is_test_mode:
            try:
                keys_env = str(os.getenv("KAGAMI_ENCRYPTION_KEYS", "") or "").strip()
            except (TypeError, AttributeError):
                keys_env = ""
            if not keys_env:
                try:
                    from kagami.core.security.privacy import KagamiOSEncryptionProvider

                    if isinstance(prov, KagamiOSEncryptionProvider):
                        raise RuntimeError(
                            "Rooms encryption requested but KAGAMI_ENCRYPTION_KEYS is not set[Any]. "
                            "Refusing to enable irreversible encryption with an ephemeral dev key."
                        )
                except ImportError:
                    msg = (
                        "Rooms encryption requested but no stable encryption key "
                        "configuration found (missing KAGAMI_ENCRYPTION_KEYS)."
                    )
                    raise RuntimeError(msg) from None
        try:
            probe = await prov.encrypt(b"rooms_probe")
            _ = await prov.decrypt(probe)
        except Exception as e:
            raise RuntimeError(f"Rooms encryption provider not usable: {e}") from None
        await r.set(_ROOM_ENC_FLAG_KEY.format(room_id=room_id), "1")


async def _rooms_encryption_enabled(room_id: str, kind: str) -> bool:
    """Check if encryption is enabled for a specific data kind.

    Currently all kinds share the same encryption flag (room-level).
    The kind parameter is reserved for future per-surface policies.

    Args:
        room_id: Room identifier.
        kind: Data kind (snapshots, deltas, anchors, cursors, crdt).

    Returns:
        True if encryption is enabled for this room.

    Note:
        UX requirement: rooms start unencrypted. Once enabled,
        encryption is guaranteed and cannot be disabled.
    """
    _ = kind  # Reserved for future per-surface policies
    return await is_room_encryption_enabled(room_id)


def _get_encryption_provider() -> Any | None:
    """Get or create the encryption provider singleton.

    Resolution order:
    1. Cached singleton (if already resolved)
    2. DI container (if EncryptionProvider is registered)
    3. Built-in KagamiOSEncryptionProvider (loads keys from env)

    Returns:
        EncryptionProvider instance, or None if not available.
    """
    global _ENCRYPTION_PROVIDER
    if _ENCRYPTION_PROVIDER is not None:
        return _ENCRYPTION_PROVIDER

    # Try DI container first (cleanest integration)
    try:
        from kagami.core.di import try_resolve
        from kagami.core.interfaces import EncryptionProvider

        prov = try_resolve(EncryptionProvider)
        if prov is not None:
            _ENCRYPTION_PROVIDER = prov
            return _ENCRYPTION_PROVIDER
    except (ImportError, KeyError, AttributeError):
        pass  # DI not available or provider not registered

    # Fallback: use built-in provider (loads keys from env)
    try:
        from kagami.core.security.privacy import KagamiOSEncryptionProvider

        _ENCRYPTION_PROVIDER = KagamiOSEncryptionProvider()
        return _ENCRYPTION_PROVIDER
    except (ImportError, RuntimeError) as e:
        logger.debug(f"Encryption provider init failed: {type(e).__name__}")
        _ENCRYPTION_PROVIDER = None
        return None


async def _encrypt_to_storage(data: bytes) -> str:
    """Encrypt bytes and encode as storage-safe string.

    Args:
        data: Plaintext bytes to encrypt.

    Returns:
        Encrypted string with 'enc:' prefix + base64 ciphertext.

    Raises:
        RuntimeError: If no encryption provider is available.
    """
    prov = _get_encryption_provider()
    if prov is None:
        raise RuntimeError("Rooms encryption enabled but no EncryptionProvider available")

    # Encrypt data using provider
    encrypted: bytes = await prov.encrypt(data)

    # Encode as prefixed base64 string (safe for Redis string storage)
    return _ENC_PREFIX + base64.b64encode(encrypted).decode("ascii")


async def _decrypt_from_storage(raw: str | bytes) -> bytes | None:
    """Decrypt storage value if encrypted, else return None.

    Args:
        raw: Stored value (may or may not be encrypted).

    Returns:
        Decrypted bytes if encrypted and decryption succeeds, else None.

    Note:
        Returns None (not raises) on decryption failure to allow
        callers to fall through to plaintext handling.
    """
    # Convert to string for prefix check
    raw_s = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)

    # Check for encryption prefix
    if not raw_s.startswith(_ENC_PREFIX):
        return None  # Not encrypted

    # Extract and decode base64 ciphertext
    try:
        blob = base64.b64decode(raw_s[len(_ENC_PREFIX) :].encode("ascii"))
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return None  # Invalid base64

    # Get provider and decrypt
    prov = _get_encryption_provider()
    if prov is None:
        return None  # No provider available

    try:
        return await prov.decrypt(blob)  # type: ignore[no-any-return]
    except Exception as e:
        logger.debug(f"Decryption failed: {type(e).__name__}")
        return None  # Decryption failed (wrong key, corrupted data, etc.)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class RoomSnapshot:
    """Snapshot of room state at a point in time.

    Contains the full materialized state plus metadata for synchronization.

    Attributes:
        room_id: Unique room identifier.
        seq: Sequence number at time of snapshot.
        state: Full room state dictionary.
        cursor_3d: Optional 3D cursor positions for CORTEX UI.

    Example:
        >>> snapshot = await get_snapshot("room-123")
        >>> print(f"Room {snapshot.room_id} at seq {snapshot.seq}")
        >>> print(f"State keys: {list(snapshot.state.keys())}")
    """

    room_id: str  # Unique room identifier
    seq: int  # Sequence number at snapshot time
    state: dict[str, Any]  # Full materialized state
    cursor_3d: dict[str, list[float]] | None = None  # user_id → [x, y, z] for CORTEX 3D UI


# =============================================================================
# SEQUENCE NUMBER FUNCTIONS
# =============================================================================
# Sequence numbers are monotonically increasing counters used for:
# - Ordering operations
# - Detecting missed updates during reconnection
# - Providing a total order across clients


async def get_next_seq(room_id: str) -> int:
    """Atomically increment and return the next sequence number.

    Uses Redis INCR for atomicity across distributed clients.

    Args:
        room_id: Room identifier.

    Returns:
        Next sequence number (always > previous value).
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    val = await r.incr(_SEQ_KEY.format(room_id=room_id))
    return int(val or 0)


async def get_current_seq(room_id: str) -> int:
    """Read the current sequence counter without incrementing it.

    Used for reconnection logic to determine how far behind a client is.

    Args:
        room_id: Room identifier.

    Returns:
        Current sequence number (0 if room doesn't exist).
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    raw = await r.get(_SEQ_KEY.format(room_id=room_id))
    try:
        return int(raw or 0)
    except (ValueError, TypeError):
        return 0


# =============================================================================
# SNAPSHOT PERSISTENCE
# =============================================================================
# Snapshots are complete room state at a point in time.
# Stored compressed (MessagePack) and optionally encrypted.


async def get_snapshot(room_id: str) -> RoomSnapshot:
    """Retrieve current room snapshot from Redis.

    Handles both encrypted and plaintext snapshots automatically.
    Decompresses MessagePack if compression module is available.

    Args:
        room_id: Room identifier.

    Returns:
        RoomSnapshot with current state and sequence number.

    Raises:
        RuntimeError: If encrypted snapshot cannot be decrypted
            (indicates misconfigured encryption keys).

    Note:
        If an encrypted snapshot is successfully read, encryption
        is latched ON for the room (monotonic encryption).
    """
    state: dict[str, Any] = {}
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    raw = await r.get(_SNAP_KEY.format(room_id=room_id))

    if raw:
        # ─────────────────────────────────────────────────────────────────
        # Try decryption first (if encrypted)
        # ─────────────────────────────────────────────────────────────────
        decrypted = await _decrypt_from_storage(raw)
        if decrypted is not None:
            # Successfully decrypted — latch encryption on for this room
            try:
                await set_room_encryption_enabled(room_id, True)
            except (OSError, ConnectionError) as e:
                logger.debug(f"Encryption latch failed: {type(e).__name__}")  # Best-effort

            # Decrypted payload is bytes (MessagePack or JSON)
            try:
                from kagami.core.rooms.compression import decompress_state as _decompress

                state = _decompress(decrypted)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.debug(f"State decompress failed: {type(e).__name__}")
                state = {}
        else:
            # ─────────────────────────────────────────────────────────────
            # Not encrypted or decryption failed
            # ─────────────────────────────────────────────────────────────
            if _looks_encrypted(raw):
                # Payload looks encrypted but couldn't decrypt — fail closed
                raise RuntimeError(
                    f"Encrypted room snapshot could not be decrypted (room_id={room_id}). "
                    "Check KAGAMI_ENCRYPTION_KEYS / EncryptionProvider configuration."
                )

            # Plain snapshot — decompress if available
            try:
                if COMPRESSION_AVAILABLE:
                    from kagami.core.rooms.compression import decompress_state as _decompress

                    state = _decompress(raw)
                else:
                    state = json.loads(raw)  # Fallback to JSON
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"State JSON parse failed: {type(e).__name__}")
                state = {}

    # Get current sequence number
    seq = await get_current_seq(room_id)
    return RoomSnapshot(room_id=room_id, seq=seq, state=state or {})


async def persist_snapshot(room_id: str, state: dict[str, Any], use_crdt: bool = False) -> None:
    """Persist room snapshot to Redis with compression and optional encryption.

    Serializes state using MessagePack (if available) for 50-70% size reduction.
    Encrypts if room encryption is enabled.

    Args:
        room_id: Room identifier.
        state: Room state dictionary to persist.
        use_crdt: Legacy flag (CRDT mutations now use apply_crdt_operations).

    Note:
        CRDT state mutations should use apply_crdt_operations() instead.
        This function is for direct snapshot persistence.

        If encryption is enabled for the room, the snapshot is encrypted
        before storage and encryption is latched ON (cannot be disabled).
    """
    # NOTE: CRDT state mutation is handled via `apply_crdt_operations()`.
    # `persist_snapshot(use_crdt=True)` is kept for backward compatibility but
    # intentionally behaves the same as a plain snapshot persist.
    _ = use_crdt

    # Get Redis client
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)

    # ─────────────────────────────────────────────────────────────────
    # Encrypted Storage Path
    # ─────────────────────────────────────────────────────────────────
    if await _rooms_encryption_enabled(room_id, "snapshots"):
        # Compress first (more efficient to encrypt compressed data)
        try:
            from kagami.core.rooms.compression import compress_state as _compress

            payload = _compress(state)
        except (TypeError, ValueError) as e:
            logger.debug(f"State compress failed, using JSON: {type(e).__name__}")
            payload = json.dumps(state).encode("utf-8")  # Fallback to JSON

        # Encrypt and store
        enc = await _encrypt_to_storage(payload)
        await r.set(_SNAP_KEY.format(room_id=room_id), enc)

        # Latch encryption (successful write confirms it's working)
        await set_room_encryption_enabled(room_id, True)
        return

    # ─────────────────────────────────────────────────────────────────
    # Plain Storage Path (compressed but not encrypted)
    # ─────────────────────────────────────────────────────────────────
    if COMPRESSION_AVAILABLE:
        from kagami.core.rooms.compression import persist_snapshot_compressed as _persist

        await _persist(room_id, state)
    else:
        # Fallback: store as JSON string
        await r.set(_SNAP_KEY.format(room_id=room_id), json.dumps(state))


# =============================================================================
# MEMBER MANAGEMENT
# =============================================================================
# Room members are tracked in the "members" collection for presence awareness.
# Uses CRDT operations for conflict-free membership updates.


async def upsert_member(room_id: str, user_id: str, member: dict[str, Any] | None = None) -> None:
    """Add or update a member record in the room.

    Persists member presence in the room snapshot using CRDT ADD operation.
    This keeps membership available across server restarts.

    Args:
        room_id: Room identifier.
        user_id: User identifier (element_id in CRDT terms).
        member: Optional member metadata (merged with defaults).

    Note:
        Updates last_seen timestamp automatically. Uses CRDT to ensure
        concurrent member updates from multiple servers converge.
    """
    # Build member record with defaults
    record = dict(member or {})
    record.setdefault("id", user_id)
    record["last_seen"] = time.time()  # Auto-update presence timestamp

    # Create CRDT ADD operation
    from kagami.core.rooms.crdt import OperationType, create_operation

    op = create_operation(
        op_type=OperationType.ADD,
        path="members",
        value=record,
        element_id=user_id,
        client_id="presence",  # System client for presence updates
        version=int(time.time() * 1000),
    )
    await apply_crdt_operations(room_id, [op.to_dict()], default_client_id="presence")


async def remove_member(room_id: str, user_id: str) -> None:
    """Remove a member from the room (best-effort).

    Uses CRDT REMOVE operation to tombstone the member.

    Args:
        room_id: Room identifier.
        user_id: User identifier to remove.
    """
    from kagami.core.rooms.crdt import OperationType, create_operation

    op = create_operation(
        op_type=OperationType.REMOVE,
        path="members",
        value=None,  # Value not needed for REMOVE
        element_id=user_id,
        client_id="presence",
        version=int(time.time() * 1000),
    )
    await apply_crdt_operations(room_id, [op.to_dict()], default_client_id="presence")


async def list_members(room_id: str) -> list[dict[str, Any]]:
    """List all members currently in a room.

    Args:
        room_id: Room identifier.

    Returns:
        List of member dictionaries with id and metadata.

    Note:
        Handles both dict and list storage modes for members collection.
    """
    snap = await get_snapshot(room_id)
    members = (snap.state or {}).get("members")

    # Dict mode: keyed by user_id
    if isinstance(members, dict):
        out: list[dict[str, Any]] = []
        for uid, rec in members.items():
            if isinstance(rec, dict):
                item = dict(rec)
                item.setdefault("id", uid)  # Ensure id is present
                out.append(item)
        return out

    # List mode: array of member objects
    if isinstance(members, list):
        return [m for m in members if isinstance(m, dict)]

    return []


# =============================================================================
# DELTA HISTORY
# =============================================================================
# Deltas are individual operations stored for reconnection catchup.
# Stored in a Redis list with automatic pruning to prevent unbounded growth.


async def append_delta(room_id: str, delta: dict[str, Any], maxlen: int = 200) -> int:
    """Append a delta to the room's operation history.

    Automatically assigns a monotonic sequence number if not present.
    Prunes old deltas to keep history bounded.

    Args:
        room_id: Room identifier.
        delta: Operation delta dictionary.
        maxlen: Maximum number of deltas to retain (default: 200).

    Returns:
        Assigned sequence number.

    Note:
        Deltas without a 'seq' field get one assigned automatically.
        This ensures all deltas have monotonic sequence numbers for
        reconnection catchup.
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    key = _DELTA_KEY.format(room_id=room_id)
    # Ensure every delta has a monotonic sequence number so reconnection can be correct.
    seq: int
    if isinstance(delta, dict) and "seq" in delta:
        try:
            seq = int(delta.get("seq") or 0)
        except (ValueError, TypeError, AttributeError):
            seq = 0
    else:
        seq = 0
    if seq <= 0:
        seq = await get_next_seq(room_id)
        try:
            delta["seq"] = seq
        except (TypeError, KeyError):
            # If delta isn't mutable, we still carry the seq on the wire.
            delta = dict(delta or {})
            delta["seq"] = seq
    else:
        # Keep delta normalized to int seq for downstream consumers.
        try:
            delta["seq"] = int(seq)
        except (ValueError, TypeError, KeyError):
            pass
    payload = json.dumps(delta)
    if await _rooms_encryption_enabled(room_id, "deltas"):
        try:
            payload = await _encrypt_to_storage(payload.encode("utf-8"))
            # Redundant if already latched, but keeps the guarantee explicit.
            await set_room_encryption_enabled(room_id, True)
        except (OSError, ConnectionError) as e:
            # If encryption is enabled for this room, fail closed.
            logger.debug(f"Encryption latch failed: {type(e).__name__}")
            raise
    await r.lpush(key, payload)
    await r.ltrim(key, 0, max(0, int(maxlen)))
    # Best-effort: publish delta to unified bus for non-Socket.IO consumers.
    try:
        from kagami.core.events import get_unified_bus

        bus = get_unified_bus()
        asyncio.create_task(
            bus.publish(
                "room.delta",
                {"room_id": room_id, "seq": int(seq), "delta": delta},
            )
        )
    except (OSError, ConnectionError, RuntimeError) as e:
        logger.debug(f"Event publish failed: {type(e).__name__}")
    return int(seq)


async def get_recent_deltas(room_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve recent deltas for reconnection catchup.

    Returns deltas in chronological order (oldest first) for sequential replay.

    Args:
        room_id: Room identifier.
        limit: Maximum number of deltas to return (default: 50).

    Returns:
        List of delta dictionaries in chronological order.

    Raises:
        RuntimeError: If encrypted deltas cannot be decrypted.

    Note:
        Deltas are stored in reverse chronological order (LPUSH),
        so this function reverses them before returning.
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    key = _DELTA_KEY.format(room_id=room_id)

    # Fetch most recent deltas (stored newest first)
    items = await r.lrange(key, 0, max(0, int(limit)))
    out: list[dict[str, Any]] = []

    for it in items or []:
        # Try decryption first
        decrypted = await _decrypt_from_storage(it)
        if decrypted is not None:
            # Successfully decrypted — latch encryption
            try:
                await set_room_encryption_enabled(room_id, True)
            except (OSError, ConnectionError):
                pass

            try:
                out.append(json.loads(decrypted.decode("utf-8", errors="strict")))
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                continue  # Skip malformed delta
            continue

        # Check if encrypted but decryption failed
        if _looks_encrypted(it):
            raise RuntimeError(
                f"Encrypted room delta could not be decrypted (room_id={room_id}). "
                "Check KAGAMI_ENCRYPTION_KEYS / EncryptionProvider configuration."
            )

        # Plain delta — parse JSON
        try:
            out.append(json.loads(it))
        except (json.JSONDecodeError, TypeError):
            continue  # Skip malformed delta

    # Reverse to chronological order (oldest first)
    return list(reversed(out))


# =============================================================================
# PHYSICS ENTITY MANAGEMENT
# =============================================================================
# Physics entities are updated by the Genesis simulation engine.
# Uses CRDT SET operations to sync transforms across clients.


async def update_physics_entities(room_id: str, entities: list[dict[str, Any]]) -> None:
    """Update physics entity transforms from Genesis simulation.

    Stores entity positions, orientations, and velocities for
    synchronized physics visualization across clients.

    Args:
        room_id: Room identifier.
        entities: List of entity state dicts with position, orientation, velocity.

    Entity Format:
        {
            "id": "entity-123",       # Unique entity ID
            "position": [x, y, z],    # World position
            "orientation": [x, y, z, w],  # Quaternion rotation
            "velocity": [vx, vy, vz], # Linear velocity
        }

    Note:
        Uses CRDT SET operation for atomic update of all physics entities.
        timestamp is automatically added for staleness detection.
    """
    # Get Redis client (for potential future use)
    RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)

    # Build physics entities map keyed by entity ID
    physics_entities = {}
    for entity in entities:
        entity_id = str(entity.get("id", entity.get("name", "")))
        if entity_id:
            physics_entities[entity_id] = {
                "position": entity.get("position", [0, 0, 0]),
                "orientation": entity.get("orientation", [0, 0, 0, 1]),  # Identity quaternion
                "velocity": entity.get("velocity", [0, 0, 0]),
                "updated_at": time.time(),  # Staleness tracking
            }

    # Create CRDT SET operation for atomic update
    from kagami.core.rooms.crdt import OperationType, create_operation

    op = create_operation(
        op_type=OperationType.SET,
        path="physics_entities",
        value=physics_entities,
        client_id="physics",  # System client for physics updates
        version=int(time.time() * 1000),
    )
    await apply_crdt_operations(room_id, [op.to_dict()], default_client_id="physics")


async def get_physics_entities(room_id: str) -> dict[str, Any]:
    """Get physics entities for room.

    Tries scene graph first for live data, falls back to snapshot.

    Args:
        room_id: Room identifier.

    Returns:
        Dict mapping entity_id → entity state (position, orientation, velocity).
    """
    # Prefer scene graph for live physics data
    try:
        from kagami.core.spatial.unified_scene_graph import get_scene_graph

        sg = get_scene_graph(room_id)
        ents = {}
        for e in sg.get_all_entities():
            ents[str(e.entity_id)] = {
                "position": list(e.position),
                "orientation": list(e.orientation),
                "velocity": list(e.velocity) if e.velocity else [0, 0, 0],
                "updated_at": time.time(),
            }
        return ents
    except (TypeError, KeyError, AttributeError, OSError) as e:
        logger.debug(f"Physics entities fetch failed: {type(e).__name__}")
        # Fallback to snapshot physics data
        snapshot = await get_snapshot(room_id)
        return snapshot.state.get("physics_entities", {})  # type: ignore[no-any-return]


# =============================================================================
# 3D CURSOR MANAGEMENT
# =============================================================================
# 3D cursors track user positions in spatial UI (CORTEX).
# Stored in Redis with TTL for automatic cleanup of stale cursors.


async def update_cursor_3d(room_id: str, user_id: str, position: list[float]) -> None:
    """Update 3D cursor position for CORTEX spatial UI.

    Stores cursor position with 5-minute TTL for automatic cleanup.
    Encrypts if room encryption is enabled.

    Args:
        room_id: Room identifier.
        user_id: User identifier.
        position: [x, y, z] 3D world position.

    Note:
        User IDs are URL-encoded in Redis keys because they may contain
        colons (e.g., 'apikey:xxxx' for API key authentication).
    """
    from urllib.parse import quote as _quote

    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)

    # Encode user_id for safe use in Redis key
    # (user_id may contain ':' which conflicts with Redis key delimiter)
    encoded_user_id = _quote(str(user_id), safe="")
    key = f"kagami:rooms:{room_id}:cursor_3d:{encoded_user_id}"

    # Serialize position
    payload = json.dumps(position)

    # Encrypt if room encryption is enabled
    if await _rooms_encryption_enabled(room_id, "cursors"):
        try:
            payload = await _encrypt_to_storage(payload.encode("utf-8"))
            await set_room_encryption_enabled(room_id, True)
        except Exception as e:
            logger.error(f"Encryption failed: {type(e).__name__}: {e}")
            raise  # Fail closed on encryption errors

    # Store with TTL (cursors auto-expire after 5 minutes of no updates)
    await r.set(key, payload, ex=300)


async def get_all_cursors_3d(room_id: str) -> dict[str, list[float]]:
    """Get all 3D cursor positions for room.

    Scans for all cursor keys and returns decoded positions.

    Args:
        room_id: Room identifier.

    Returns:
        Dict mapping user_id → [x, y, z] position.

    Note:
        Handles both URL-encoded and plain user IDs for
        backward compatibility during migration.
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    pattern = f"kagami:rooms:{room_id}:cursor_3d:*"
    cursors = {}

    from urllib.parse import unquote as _unquote

    prefix = f"kagami:rooms:{room_id}:cursor_3d:"

    # Scan for all cursor keys (efficient for large keyspaces)
    async for key in r.scan_iter(match=pattern):
        # Parse user_id from key (handle URL-encoded format)
        try:
            raw = str(key)
            if raw.startswith(prefix):
                user_id_raw = raw[len(prefix) :]  # Preferred: use prefix
            else:
                user_id_raw = raw.split(":")[-1]  # Fallback: split by ':'
            user_id = _unquote(user_id_raw)  # Decode URL encoding
            position_json = await r.get(key)
        except (ValueError, TypeError, OSError):
            continue  # Skip malformed keys

        if not position_json:
            continue  # Skip empty values

        decrypted = await _decrypt_from_storage(position_json)
        if decrypted is not None:
            try:
                await set_room_encryption_enabled(room_id, True)
            except (OSError, ConnectionError):
                pass
            try:
                cursors[user_id] = json.loads(decrypted.decode("utf-8", errors="strict"))
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                continue
            continue

        if _looks_encrypted(position_json):
            raise RuntimeError(
                f"Encrypted room cursor could not be decrypted (room_id={room_id}). "
                "Check KAGAMI_ENCRYPTION_KEYS / EncryptionProvider configuration."
            )

        try:
            cursors[user_id] = json.loads(position_json)
        except (json.JSONDecodeError, TypeError):
            continue

    return cursors


# =============================================================================
# SPATIAL ANCHOR MANAGEMENT
# =============================================================================
# Spatial anchors are persistent 3D reference points for AR/VR applications.
# Used for AR games, multiplayer synchronization, and spatial annotations.
# Stored in a Redis hash for efficient per-anchor access.


async def update_anchor(room_id: str, anchor_id: str, data: dict[str, Any]) -> None:
    """Update or create a spatial anchor for AR games and multiplayer.

    Spatial anchors provide persistent 3D reference points that multiple
    clients can use to align content in physical or virtual space.

    Args:
        room_id: Room identifier.
        anchor_id: Unique anchor identifier.
        data: Anchor data including position, type, and properties.

    Anchor Data Format:
        {
            "position": [x, y, z],         # World position
            "orientation": [x, y, z, w],   # Quaternion rotation
            "type": "floor" | "wall" | "table" | "custom",
            "properties": {...},            # Type-specific properties
        }

    Note:
        Creates a delta for room catchup so anchors participate in
        the standard reconnection flow.
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    key = _ANCHORS_HASH.format(room_id=room_id)

    # Serialize anchor data
    payload = json.dumps(data)

    # Encrypt if room encryption is enabled
    if await _rooms_encryption_enabled(room_id, "anchors"):
        try:
            payload = await _encrypt_to_storage(payload.encode("utf-8"))
            await set_room_encryption_enabled(room_id, True)
        except Exception as e:
            logger.error(f"Encryption failed: {type(e).__name__}: {e}")
            raise  # Fail closed on encryption errors

    # Store in Redis hash (efficient for multiple anchors per room)
    await r.hset(key, anchor_id, payload)

    # Create delta for room catchup (best-effort)
    try:
        await append_delta(
            room_id,
            {
                "type": "anchor.upsert",
                "anchor_id": anchor_id,
                "anchor": data,
                "ts": time.time(),
            },
        )
    except (OSError, ConnectionError, RuntimeError) as e:
        logger.debug(f"Delta persist failed: {type(e).__name__}")  # Best-effort


async def get_anchors(room_id: str) -> dict[str, Any]:
    """Get all spatial anchors for a room.

    Retrieves and decrypts all anchors stored for the room.

    Args:
        room_id: Room identifier.

    Returns:
        Dict mapping anchor_id → anchor data.

    Raises:
        RuntimeError: If encrypted anchors cannot be decrypted.
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    key = _ANCHORS_HASH.format(room_id=room_id)

    # Get all anchors from Redis hash
    anchors_raw = await r.hgetall(key)
    anchors = {}

    for anchor_id, data_json in (anchors_raw or {}).items():
        # Try decryption first
        decrypted = await _decrypt_from_storage(data_json)
        if decrypted is not None:
            # Successfully decrypted — latch encryption
            try:
                await set_room_encryption_enabled(room_id, True)
            except (OSError, ConnectionError):
                pass

            try:
                anchors[anchor_id] = json.loads(decrypted.decode("utf-8", errors="strict"))
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                continue  # Skip malformed anchor
            continue

        if _looks_encrypted(data_json):
            raise RuntimeError(
                f"Encrypted room anchor could not be decrypted (room_id={room_id}). "
                "Check KAGAMI_ENCRYPTION_KEYS / EncryptionProvider configuration."
            )

        try:
            anchors[anchor_id] = json.loads(data_json)
        except (json.JSONDecodeError, TypeError):
            continue
    return anchors


# =============================================================================
# DISTRIBUTED LOCKING
# =============================================================================
# Uses both local asyncio locks and Redis distributed locks to prevent
# concurrent modifications to room state from multiple servers.


def _get_local_room_lock(room_id: str) -> asyncio.Lock:
    """Get or create a local asyncio lock for a room.

    Local locks prevent concurrent access within the same process.
    Combined with distributed locks for multi-server safety.

    Args:
        room_id: Room identifier.

    Returns:
        Asyncio lock for the room (created if not exists).
    """
    lock = _LOCAL_ROOM_LOCKS.get(room_id)
    if lock is None:
        lock = asyncio.Lock()
        _LOCAL_ROOM_LOCKS[room_id] = lock
    return lock


async def _acquire_distributed_room_lock(
    room_id: str,
    *,
    timeout_s: float = 5.0,
    ttl_s: int = 10,
) -> str | None:
    """Acquire a distributed lock using Redis SET NX.

    Implements a simple Redis-based lock with automatic expiration.
    Uses retry loop with exponential-ish backoff.

    Args:
        room_id: Room identifier.
        timeout_s: Maximum time to wait for lock (default: 5s).
        ttl_s: Lock TTL to prevent deadlocks (default: 10s).

    Returns:
        Lock token if acquired, None if timeout.

    Note:
        Lock has TTL to prevent deadlocks if holder crashes.
        Token must be passed to _release_distributed_room_lock.
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    key = _ROOM_LOCK_KEY.format(room_id=room_id)
    token = uuid.uuid4().hex  # Unique token to identify lock owner
    deadline = time.time() + max(0.1, float(timeout_s))

    # Retry loop until deadline
    while time.time() < deadline:
        try:
            # SET NX = only set if not exists (atomic acquire)
            ok = await r.set(key, token, nx=True, ex=int(ttl_s))
        except (OSError, ConnectionError, RuntimeError) as e:
            logger.debug(f"Lock acquire failed: {type(e).__name__}")
            ok = False

        if ok:
            return token  # Successfully acquired

        await asyncio.sleep(0.05)  # Brief pause before retry

    return None  # Timeout — failed to acquire


async def _release_distributed_room_lock(room_id: str, token: str | None) -> None:
    """Release a distributed lock.

    Only releases if current token matches (prevents releasing
    another holder's lock).

    Args:
        room_id: Room identifier.
        token: Lock token from _acquire_distributed_room_lock.
    """
    if not token:
        return  # No lock to release

    try:
        r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
        key = _ROOM_LOCK_KEY.format(room_id=room_id)

        # Only delete if we hold the lock (token matches)
        cur = await r.get(key)
        if str(cur or "") == str(token):
            try:
                await r.delete(key)
            except (OSError, ConnectionError):
                # Last resort: clear key value
                try:
                    await r.set(key, "")
                except (OSError, ConnectionError):
                    pass  # Best-effort release
    except (OSError, ConnectionError, RuntimeError) as e:
        logger.debug(f"Lock release failed: {type(e).__name__}")  # Best-effort


# =============================================================================
# CRDT METADATA PERSISTENCE
# =============================================================================
# CRDT metadata (LWW clocks, collection metadata, counter ops) is stored
# separately from the materialized state to enable conflict resolution.


async def get_crdt_meta(room_id: str) -> dict[str, Any]:
    """Load CRDT metadata for a room.

    CRDT metadata includes LWW register clocks, collection element
    clocks, and counter operation histories.

    Args:
        room_id: Room identifier.

    Returns:
        CRDT metadata dict (empty dict if not found).
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    raw = await r.get(_CRDT_META_KEY.format(room_id=room_id))

    if not raw:
        return {}  # No metadata yet

    # Try decryption first
    decrypted = await _decrypt_from_storage(raw)
    if decrypted is not None:
        # Successfully decrypted — latch encryption
        try:
            await set_room_encryption_enabled(room_id, True)
        except (OSError, ConnectionError):
            pass

        try:
            return json.loads(decrypted.decode("utf-8", errors="strict"))  # type: ignore[no-any-return]
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            return {}

    if _looks_encrypted(raw):
        raise RuntimeError(
            f"Encrypted room CRDT metadata could not be decrypted (room_id={room_id}). "
            "Check KAGAMI_ENCRYPTION_KEYS / EncryptionProvider configuration."
        )

    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, TypeError):
        return {}


async def persist_crdt_meta(room_id: str, meta: dict[str, Any]) -> None:
    """Persist CRDT metadata for a room.

    Stores CRDT metadata (LWW clocks, collection metadata, counter ops)
    to Redis, optionally encrypted if room encryption is enabled.

    Args:
        room_id: Room identifier.
        meta: CRDT metadata dictionary to persist.

    Note:
        Uses compact JSON encoding (no extra whitespace) to minimize
        storage size. Encryption is applied if room encryption is enabled.
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)

    # Serialize to compact JSON
    meta_json = json.dumps(meta or {}, ensure_ascii=False, separators=(",", ":"))
    payload_bytes = meta_json.encode("utf-8")

    # Encrypt if room encryption is enabled
    if await _rooms_encryption_enabled(room_id, "crdt"):
        enc = await _encrypt_to_storage(payload_bytes)
        await r.set(_CRDT_META_KEY.format(room_id=room_id), enc)
        await set_room_encryption_enabled(room_id, True)  # Latch
        return

    # Store as plain JSON string
    key = _CRDT_META_KEY.format(room_id=room_id)
    await r.set(key, payload_bytes.decode("utf-8", errors="strict"))


async def sync_room_to_world_model(room_id: str, snapshot: RoomSnapshot) -> None:
    """Sync room state changes to world model for predictive planning.

    This function extracts social graph and spatial scene data from the room snapshot
    and emits events to the unified bus for consumption by Nexus (e₄) colony RSSM.

    Integration point: World model predictive coordination
    - Social graph: member presence and relationships
    - Spatial scene: physics entities positions and velocities
    - Event: "room.state_changed" for unified bus

    Args:
        room_id: Room identifier
        snapshot: Current room snapshot after CRDT operations

    Note:
        This function is fire-and-forget; errors are logged but don't block
        the calling CRDT operation. World model sync is an optional enhancement.
    """
    if not _ENABLE_WORLD_MODEL_SYNC:
        return

    try:
        # Extract social graph from room members
        social_graph: dict[str, Any] = {}
        members = snapshot.state.get("members", {})
        if isinstance(members, dict):
            social_graph = {
                "member_count": len(members),
                "member_ids": list(members.keys()),
                "active_members": [
                    uid
                    for uid, member in members.items()
                    if isinstance(member, dict)
                    and member.get("last_seen", 0) > time.time() - 300  # Active in last 5 min
                ],
            }

        # Extract spatial scene from physics entities
        spatial_scene: dict[str, Any] = {}
        physics_entities = snapshot.state.get("physics_entities", {})
        if isinstance(physics_entities, dict):
            spatial_scene = {
                "entity_count": len(physics_entities),
                "entities": [
                    {
                        "id": entity_id,
                        "position": entity.get("position", [0, 0, 0]),
                        "orientation": entity.get("orientation", [0, 0, 0, 1]),
                        "velocity": entity.get("velocity", [0, 0, 0]),
                    }
                    for entity_id, entity in physics_entities.items()
                    if isinstance(entity, dict)
                ],
            }

        # Emit event to unified bus for Nexus colony consumption
        from kagami.core.events import get_unified_bus

        bus = get_unified_bus()

        # Fire-and-forget: don't await, don't block CRDT operation
        asyncio.create_task(
            bus.publish(
                "room.state_changed",
                {
                    "room_id": room_id,
                    "seq": snapshot.seq,
                    "timestamp": time.time(),
                    "social_graph": social_graph,
                    "spatial_scene": spatial_scene,
                },
            )
        )

        logger.debug(
            f"Synced room {room_id} state to world model: "
            f"{social_graph.get('member_count', 0)} members, "
            f"{spatial_scene.get('entity_count', 0)} entities"
        )

    except Exception as e:
        # Log warning but don't fail the CRDT operation
        # World model sync is optional enhancement
        logger.warning(
            f"Failed to sync room {room_id} to world model: {e}",
            exc_info=True,
        )


async def _atomic_persist_snapshot_and_deltas(
    room_id: str,
    snapshot_state: dict[str, Any],
    crdt_meta: dict[str, Any],
    changed_ops: list[Any],
    *,
    correlation_id: str,
) -> list[dict[str, Any]]:
    """Atomically persist snapshot + CRDT metadata + all deltas using Redis transaction.

    This function ensures that snapshot and deltas are persisted together or not at all,
    preventing data loss from partial failures.

    Args:
        room_id: Room identifier
        snapshot_state: Materialized CRDT state to persist
        crdt_meta: CRDT metadata to persist
        changed_ops: List of CRDT operations to persist as deltas
        correlation_id: UUID linking snapshot and deltas for debugging

    Returns:
        List of applied deltas with assigned sequence numbers

    Raises:
        RuntimeError: If transaction fails to commit atomically
    """
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)

    # Check if we're using the fake Redis (no pipeline support)
    is_fake = isinstance(r, type(r)) and hasattr(r, "_kv")

    if is_fake:
        # Fallback: non-atomic for fake Redis (test environments only)
        logger.warning(
            f"[{correlation_id}] Using non-atomic persistence fallback (fake Redis detected)"
        )
        await persist_snapshot(room_id, snapshot_state)
        await persist_crdt_meta(room_id, crdt_meta)

        applied_deltas: list[dict[str, Any]] = []
        for op in changed_ops:
            delta = {
                "type": "crdt.op",
                "op": op.to_dict(),
                "ts": time.time(),
                "correlation_id": correlation_id,
            }
            seq = await append_delta(room_id, delta)
            applied_deltas.append({"seq": seq, "delta": delta})

        return applied_deltas

    # Real Redis: use pipeline with MULTI/EXEC for atomicity
    try:
        # Pre-allocate sequence numbers for all deltas
        num_deltas = len(changed_ops)
        if num_deltas == 0:
            return []

        # Atomically allocate N sequence numbers
        base_seq = await r.incrby(_SEQ_KEY.format(room_id=room_id), num_deltas)
        first_seq = base_seq - num_deltas + 1

        # Prepare serialized snapshot and metadata
        snap_key = _SNAP_KEY.format(room_id=room_id)
        meta_key = _CRDT_META_KEY.format(room_id=room_id)
        delta_key = _DELTA_KEY.format(room_id=room_id)

        # Serialize snapshot
        if await _rooms_encryption_enabled(room_id, "snapshots"):
            try:
                from kagami.core.rooms.compression import compress_state as _compress

                payload = _compress(snapshot_state)
            except (TypeError, ValueError) as e:
                logger.debug(f"Compress failed: {type(e).__name__}")
                payload = json.dumps(snapshot_state).encode("utf-8")
            snap_payload = await _encrypt_to_storage(payload)
            await set_room_encryption_enabled(room_id, True)
        else:
            if COMPRESSION_AVAILABLE:
                from kagami.core.rooms.compression import compress_state as _compress

                snap_payload = _compress(snapshot_state).decode("utf-8", errors="replace")
            else:
                snap_payload = json.dumps(snapshot_state)

        # Serialize metadata
        meta_json = json.dumps(crdt_meta or {}, ensure_ascii=False, separators=(",", ":"))
        meta_payload_bytes = meta_json.encode("utf-8")
        if await _rooms_encryption_enabled(room_id, "crdt"):
            meta_payload = await _encrypt_to_storage(meta_payload_bytes)
            await set_room_encryption_enabled(room_id, True)
        else:
            meta_payload = meta_payload_bytes.decode("utf-8", errors="strict")

        # Prepare all deltas with pre-assigned seq numbers
        delta_payloads: list[str] = []
        applied_deltas: list[dict[str, Any]] = []  # type: ignore[no-redef]

        for idx, op in enumerate(changed_ops):
            seq = first_seq + idx
            delta = {
                "type": "crdt.op",
                "op": op.to_dict(),
                "ts": time.time(),
                "seq": seq,
                "correlation_id": correlation_id,
            }

            delta_json = json.dumps(delta)
            if await _rooms_encryption_enabled(room_id, "deltas"):
                try:
                    delta_payload = await _encrypt_to_storage(delta_json.encode("utf-8"))
                    await set_room_encryption_enabled(room_id, True)
                except Exception as e:
                    logger.error(f"Delta encryption failed: {type(e).__name__}: {e}")
                    raise

                delta_payloads.append(delta_payload)
            else:
                delta_payloads.append(delta_json)

            applied_deltas.append({"seq": seq, "delta": delta})

        # Execute atomic transaction: snapshot + metadata + all deltas
        pipe = r.pipeline(transaction=True)

        try:
            # Write snapshot
            pipe.set(snap_key, snap_payload)

            # Write metadata
            pipe.set(meta_key, meta_payload)

            # Write all deltas atomically
            for delta_payload in delta_payloads:
                pipe.lpush(delta_key, delta_payload)

            # Trim delta list[Any] to maxlen (default 200)
            pipe.ltrim(delta_key, 0, 199)

            # Execute transaction
            results = await pipe.execute()

            # Verify all operations succeeded
            if not all(results):
                raise RuntimeError(
                    f"[{correlation_id}] Redis transaction partial failure: {results}"
                )

        except Exception as e:
            logger.error(
                f"[{correlation_id}] Atomic persist failed, rolling back: {e}",
                exc_info=True,
            )
            raise RuntimeError(
                f"[{correlation_id}] Failed to atomically persist snapshot and deltas: {e}"
            ) from e

        # Verify sequence continuity
        final_seq = await get_current_seq(room_id)
        expected_seq = first_seq + num_deltas - 1

        if final_seq != expected_seq:
            logger.error(
                f"[{correlation_id}] Sequence mismatch after atomic persist: "
                f"expected {expected_seq}, got {final_seq}"
            )
            raise RuntimeError(
                f"[{correlation_id}] Sequence number inconsistency detected: "
                f"expected {expected_seq}, got {final_seq}"
            )

        logger.info(
            f"[{correlation_id}] Atomically persisted snapshot + {num_deltas} deltas "
            f"(seq {first_seq}..{final_seq})"
        )

        # Best-effort: publish deltas to unified bus for non-Socket.IO consumers
        try:
            from kagami.core.events import get_unified_bus

            bus = get_unified_bus()
            for delta_info in applied_deltas:
                asyncio.create_task(
                    bus.publish(
                        "room.delta",
                        {
                            "room_id": room_id,
                            "seq": delta_info["seq"],
                            "delta": delta_info["delta"],
                            "correlation_id": correlation_id,
                        },
                    )
                )
        except (OSError, ConnectionError, RuntimeError) as e:
            logger.debug(f"Snapshot save event failed: {type(e).__name__}")

        return applied_deltas

    except Exception as e:
        logger.error(
            f"[{correlation_id}] Atomic persist failed: {e}",
            exc_info=True,
        )
        raise


# =============================================================================
# CRDT OPERATION APPLICATION
# =============================================================================
# The canonical mutation API for room state. All state changes go through
# apply_crdt_operations() to ensure consistency across clients.


async def apply_crdt_operations(
    room_id: str,
    operations: list[Any],
    *,
    default_client_id: str | None = None,
) -> tuple[RoomSnapshot, list[dict[str, Any]]]:
    """Apply CRDT operations to room state and emit replayable deltas.

    This is the canonical mutation API for room state. It:
    1. Acquires local + distributed locks to serialize writes
    2. Loads current CRDT state and metadata
    3. Applies each operation through CRDT (conflict resolution)
    4. Atomically persists snapshot + metadata + deltas
    5. Syncs to world model (optional, fire-and-forget)
    6. Returns updated snapshot and applied deltas

    Concurrency Control:
        Uses both local asyncio locks (per-process) and Redis distributed
        locks (cross-process) to prevent lost updates from concurrent writers.

    Atomicity Guarantee:
        Snapshot and all deltas are persisted atomically using Redis
        MULTI/EXEC transaction. This prevents data loss from partial
        failures where snapshot persists but deltas fail.

    Args:
        room_id: Room identifier.
        operations: List of operation dicts or Operation objects.
        default_client_id: Fallback client_id for operations without one.

    Returns:
        Tuple of (updated_snapshot, list_of_applied_deltas).

    Raises:
        RuntimeError: If CRDT module is not available.

    Example:
        >>> op = {"type": "SET", "path": "status", "value": "active", ...}
        >>> snapshot, deltas = await apply_crdt_operations("room-1", [op])
    """
    if not CRDT_AVAILABLE:
        raise RuntimeError("CRDT not available — install kagami[crdt]")

    # Generate correlation ID for tracing this batch through logs
    correlation_id = uuid.uuid4().hex

    # Acquire local lock first (fast path for single-process)
    lock = _get_local_room_lock(room_id)
    await lock.acquire()
    token: str | None = None
    try:
        token = await _acquire_distributed_room_lock(room_id)
        if token is None:
            raise RuntimeError("Could not acquire room lock")

        from kagami.core.rooms.crdt import Operation, RoomStateCRDT

        snap = await get_snapshot(room_id)
        meta = await get_crdt_meta(room_id)
        crdt = RoomStateCRDT(room_id, state=dict(snap.state or {}), meta=meta)

        changed_ops: list[Operation] = []
        for raw in list(operations or []):
            op: Operation
            if isinstance(raw, Operation):
                op = raw
            elif isinstance(raw, dict):
                op = Operation.from_dict(raw)
            else:
                continue
            if default_client_id and not str(op.client_id or "").strip():
                op.client_id = str(default_client_id)

            res = crdt.apply_operation(op)
            if bool(res.get("changed")):
                changed_ops.append(op)

        applied_deltas: list[dict[str, Any]] = []
        if changed_ops:
            # Atomically persist snapshot + metadata + all deltas
            # This replaces the non-atomic pattern:
            #   await persist_snapshot(room_id, dict(crdt.state or {}))
            #   await persist_crdt_meta(room_id, dict(crdt.meta or {}))
            #   for op in changed_ops:
            #       seq = await append_delta(room_id, delta)  # CAN FAIL INDEPENDENTLY
            applied_deltas = await _atomic_persist_snapshot_and_deltas(
                room_id,
                dict(crdt.state or {}),
                dict(crdt.meta or {}),
                changed_ops,
                correlation_id=correlation_id,
            )

        # Return a fresh snapshot view (seq reflects latest delta seq)
        out_snap = RoomSnapshot(
            room_id=room_id,
            seq=await get_current_seq(room_id),
            state=dict(crdt.state or {}),
        )

        # World model integration: Sync room state changes to world model
        # for predictive planning (fire-and-forget, doesn't block return)
        if changed_ops:
            asyncio.create_task(sync_room_to_world_model(room_id, out_snap))

        return out_snap, applied_deltas
    finally:
        try:
            await _release_distributed_room_lock(room_id, token)
        finally:
            try:
                lock.release()
            except (RuntimeError, OSError):
                pass  # Lock already released or connection lost


# =============================================================================
# PUBLIC API
# =============================================================================
# Exported names for external use.
# Internal helpers (_func) are NOT exported.

__all__ = [
    # Feature flags
    "COMPRESSION_AVAILABLE",  # True if MessagePack is installed
    "CRDT_AVAILABLE",  # True if CRDT module is available
    # Data classes
    "RoomSnapshot",  # Snapshot of room state
    # Delta operations
    "append_delta",  # Append operation to delta history
    "apply_crdt_operations",  # Main mutation API (CRDT)
    # 3D cursor management
    "get_all_cursors_3d",  # Get all cursor positions
    # Anchor management
    "get_anchors",  # Get spatial anchors
    # CRDT metadata
    "get_crdt_meta",  # Get CRDT metadata
    # Sequence numbers
    "get_current_seq",  # Read current seq (no increment)
    "get_next_seq",  # Atomically get next seq
    # Physics entities
    "get_physics_entities",  # Get physics entity states
    # Delta history
    "get_recent_deltas",  # Get deltas for catchup
    # Snapshot operations
    "get_snapshot",  # Get current room snapshot
    # Encryption management
    "is_room_encryption_enabled",  # Check if room is encrypted
    # Member management
    "list_members",  # List room members
    # Persistence operations
    "persist_crdt_meta",  # Save CRDT metadata
    "persist_snapshot",  # Save room snapshot
    "remove_member",  # Remove member from room
    "set_room_encryption_enabled",  # Enable encryption (irreversible)
    # World model integration
    "sync_room_to_world_model",  # Sync state to predictive model
    # Spatial anchor management
    "update_anchor",  # Update spatial anchor
    # 3D cursor operations
    "update_cursor_3d",  # Update user's 3D position
    # Physics integration
    "update_physics_entities",  # Update physics entity transforms
    "upsert_member",  # Add/update member
]
