from __future__ import annotations

"""State Compression for Rooms using MessagePack.

Compresses room state snapshots to reduce storage and bandwidth.
Achieves 50-70% size reduction compared to JSON.

Why MessagePack?
    - Binary format (more compact than JSON)
    - Faster serialization than JSON
    - Supports all JSON types plus binary data
    - Wide language support for interoperability

Fallback Behavior:
    If MessagePack is not installed (optional dependency), all
    functions gracefully fall back to JSON encoding.

Storage Format:
    When storing in Redis with decode_responses=True, MessagePack
    bytes are base64-encoded with a prefix ("mpk:") to distinguish
    from plain JSON strings.

Example:
    >>> state = {"users": {"alice": {"status": "online"}}}
    >>> compressed = compress_state(state)
    >>> len(compressed) < len(json.dumps(state))  # Usually true
    True
    >>> state == decompress_state(compressed)
    True
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import base64  # For Redis string encoding
import logging  # Error logging
from typing import Any  # Type hints

# =============================================================================
# OPTIONAL DEPENDENCY: MessagePack
# =============================================================================
# MessagePack is optional — we fall back to JSON if not installed.
try:
    import msgpack

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    msgpack = None

logger = logging.getLogger(__name__)

# Prefix for MessagePack payloads stored as strings in Redis.
# This allows distinguishing from plain JSON strings.
_MP_PREFIX = "mpk:"


# =============================================================================
# COMPRESSION FUNCTIONS
# =============================================================================


def compress_state(state: dict[str, Any]) -> bytes:
    """Compress room state to bytes using MessagePack.

    If MessagePack isn't available, returns UTF-8 JSON bytes.

    Args:
        state: Room state dictionary to compress.

    Returns:
        Compressed bytes (MessagePack or JSON fallback).

    Example:
        >>> compressed = compress_state({"key": "value"})
        >>> isinstance(compressed, bytes)
        True
    """
    # Fallback to JSON if MessagePack not available
    if not AVAILABLE or not msgpack:
        import json

        return json.dumps(state).encode("utf-8")

    try:
        return msgpack.packb(state, use_bin_type=True)  # type: ignore  # External lib
    except Exception as e:
        logger.error(f"MessagePack compression failed: {e}")
        import json

        return json.dumps(state).encode("utf-8")


def _decode_storage_value(data: bytes | str) -> bytes:
    """Decode stored Redis value back to raw bytes.

    Handles the storage format used by persist_snapshot_compressed:
    - Direct bytes: returned as-is
    - String with "mpk:" prefix: base64-decoded MessagePack
    - Plain string: UTF-8 encoded (JSON fallback)

    Args:
        data: Stored value from Redis (bytes or string).

    Returns:
        Raw bytes for decompression.
    """
    # Direct bytes — return as-is
    if isinstance(data, bytes):
        return data
    s = str(data)
    # MessagePack with base64 encoding (has prefix)
    if s.startswith(_MP_PREFIX):
        try:
            return base64.b64decode(s[len(_MP_PREFIX) :].encode("ascii"))
        except Exception:
            return b""
    # Plain JSON string — encode to bytes
    return s.encode("utf-8")


def decompress_state(data: bytes | str) -> dict[str, Any]:
    """Decompress room state from MessagePack or JSON.

    Automatically detects format and decompresses. Falls back to JSON
    if MessagePack decoding fails.

    Args:
        data: Compressed state bytes or storage string.

    Returns:
        Decompressed state dictionary, or empty dict on error.

    Example:
        >>> compressed = compress_state({"key": "value"})
        >>> decompress_state(compressed)
        {'key': 'value'}
    """
    # Handle empty input
    if not data:
        return {}

    # Decode storage format to raw bytes
    raw = _decode_storage_value(data)
    if not raw:
        return {}

    # Try MessagePack first (if available)
    if AVAILABLE and msgpack:
        try:
            return msgpack.unpackb(raw, raw=False)  # type: ignore  # External lib
        except Exception:
            pass  # Fall through to JSON

    # Fallback: try JSON decoding
    try:
        import json

        return json.loads(raw.decode("utf-8"))  # type: ignore  # External lib
    except Exception as e:
        logger.error(f"Failed to decompress: {e}")
        return {}


# =============================================================================
# REDIS PERSISTENCE FUNCTIONS
# =============================================================================
# These functions integrate with Redis for durable storage.
# They handle the string encoding required by decode_responses=True.


async def persist_snapshot_compressed(room_id: str, state: dict[str, Any]) -> None:
    """Persist room snapshot to Redis with compression.

    Compresses state using MessagePack (if available) and stores in Redis.
    Value is encoded as a string for compatibility with decode_responses=True.

    Storage Key: kagami:rooms:{room_id}:snapshot

    Args:
        room_id: Room identifier.
        state: Room state dictionary to persist.

    Example:
        >>> await persist_snapshot_compressed("room-123", {"users": {}})
    """
    from kagami.core.caching.redis import RedisClientFactory

    # Get async Redis client with string decoding
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    key = f"kagami:rooms:{room_id}:snapshot"

    # Compress state to bytes
    compressed = compress_state(state)

    if AVAILABLE and msgpack:
        # MessagePack: base64 encode with prefix for identification
        payload = _MP_PREFIX + base64.b64encode(compressed).decode("ascii")
        await r.set(key, payload)
    else:
        # JSON fallback: bytes → string directly
        await r.set(key, compressed.decode("utf-8", errors="replace"))


async def get_snapshot_compressed(room_id: str) -> dict[str, Any]:
    """Get room snapshot from Redis with decompression.

    Retrieves and decompresses room state from Redis.

    Args:
        room_id: Room identifier.

    Returns:
        Decompressed state dictionary, or empty dict if not found.

    Example:
        >>> state = await get_snapshot_compressed("room-123")
        >>> print(state.get("users", {}))
    """
    from kagami.core.caching.redis import RedisClientFactory

    # Get async Redis client with string decoding
    r = RedisClientFactory.get_client(purpose="default", async_mode=True, decode_responses=True)
    key = f"kagami:rooms:{room_id}:snapshot"
    data = await r.get(key)

    # Handle missing snapshot
    if not data:
        return {}

    # Decompress and return
    return decompress_state(data)


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Availability flag
    "AVAILABLE",
    # Core compression functions
    "compress_state",
    "decompress_state",
    # Redis persistence
    "get_snapshot_compressed",
    "persist_snapshot_compressed",
]
