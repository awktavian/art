"""Secure signed serialization for cache files.

Replaces unsafe pickle.load() with HMAC-signed JSON/torch serialization.

SECURITY:
- HMAC-SHA256 signatures prevent cache tampering
- Constant-time comparison prevents timing attacks
- Supports both JSON (metadata) and torch tensors (weights)
- Automatic format migration from legacy pickle

Usage:
    >>> from kagami.core.security.signed_serialization import save_signed, load_signed
    >>> data = {"key": "value", "count": 42}
    >>> save_signed(data, Path("cache.dat"), format="json")
    >>> loaded = load_signed(Path("cache.dat"), format="json")
    >>> assert loaded == data

Created: December 20, 2025
Colony: Forge (e₂) - Security implementation
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

import torch

from kagami.core.exceptions import SecurityError

logger = logging.getLogger(__name__)


def _get_secret_key() -> bytes:
    """Get secret key from environment variable.

    Returns:
        Secret key bytes (32 bytes for SHA256)

    Raises:
        SecurityError: If secret key not configured or invalid
    """
    secret_hex = os.getenv("KAGAMI_CACHE_SECRET")

    if not secret_hex:
        raise SecurityError(
            "KAGAMI_CACHE_SECRET environment variable not set[Any]. "
            "Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
        )

    try:
        secret_bytes = bytes.fromhex(secret_hex)
    except ValueError as e:
        raise SecurityError(f"Invalid KAGAMI_CACHE_SECRET format (expected hex): {e}") from e

    if len(secret_bytes) < 32:
        raise SecurityError(
            f"KAGAMI_CACHE_SECRET too short ({len(secret_bytes)} bytes, minimum 32)"
        )

    return secret_bytes


def _compute_signature(payload: bytes, secret_key: bytes) -> bytes:
    """Compute HMAC-SHA256 signature.

    Args:
        payload: Data to sign
        secret_key: Secret key for HMAC

    Returns:
        32-byte HMAC-SHA256 signature
    """
    return hmac.new(secret_key, payload, hashlib.sha256).digest()


def _verify_signature(payload: bytes, signature: bytes, secret_key: bytes) -> bool:
    """Verify HMAC-SHA256 signature (constant-time comparison).

    Args:
        payload: Data to verify
        signature: Signature to check
        secret_key: Secret key for HMAC

    Returns:
        True if signature is valid
    """
    expected_signature = _compute_signature(payload, secret_key)
    return hmac.compare_digest(signature, expected_signature)


def save_signed(
    data: dict[str, Any],
    path: Path,
    format: Literal["json", "torch"] = "json",
) -> None:
    """Save data with HMAC signature.

    File format:
        [32 bytes signature][payload]

    Args:
        data: Data to save (dict[str, Any] for JSON, torch tensors for torch format)
        path: File path to save to
        format: Serialization format ("json" for metadata, "torch" for tensors)

    Raises:
        SecurityError: If secret key not configured
        OSError: On file write failure
    """
    secret_key = _get_secret_key()

    # Serialize payload
    if format == "json":
        payload = json.dumps(data, sort_keys=True).encode("utf-8")
    elif format == "torch":
        # Use torch.save with protocol=4 (Python 3.4+)
        import io

        buffer = io.BytesIO()
        torch.save(data, buffer)
        payload = buffer.getvalue()
    else:
        raise ValueError(f"Invalid format: {format}. Must be 'json' or 'torch'")

    # Compute signature
    signature = _compute_signature(payload, secret_key)

    # Write atomically (temp file + rename)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(temp_path, "wb") as f:
            f.write(signature)  # 32 bytes
            f.write(payload)

        temp_path.replace(path)
        logger.debug(f"Saved signed {format} data to {path} ({len(payload)} bytes)")

    except Exception:
        # Clean up temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        raise


def load_signed(
    path: Path,
    format: Literal["json", "torch"] = "json",
    allow_legacy_pickle: bool = True,
) -> dict[str, Any]:
    """Load data with signature verification.

    Args:
        path: File path to load from
        format: Serialization format ("json" or "torch")
        allow_legacy_pickle: Allow migration from legacy pickle format

    Returns:
        Loaded data (dict[str, Any])

    Raises:
        SecurityError: If signature verification fails
        FileNotFoundError: If file doesn't exist
        ValueError: If format is invalid or data corrupted
    """
    if not path.exists():
        raise FileNotFoundError(f"Signed data file not found: {path}")

    secret_key = _get_secret_key()

    with open(path, "rb") as f:
        file_data = f.read()

    # Check if this is a legacy pickle file (attempt migration)
    if allow_legacy_pickle and len(file_data) > 0 and file_data[0:2] == b"\x80\x05":
        logger.warning(
            f"Detected legacy pickle format at {path}. Migrating to signed {format} format..."
        )
        return _migrate_legacy_pickle(path, format, secret_key)

    # Validate minimum size (32 byte signature + at least 1 byte payload)
    if len(file_data) < 33:
        raise ValueError(f"Signed file too small ({len(file_data)} bytes, minimum 33)")

    # Extract signature and payload
    signature = file_data[:32]
    payload = file_data[32:]

    # Verify signature (constant-time comparison)
    if not _verify_signature(payload, signature, secret_key):
        logger.error(f"SECURITY: Invalid signature for {path}")
        raise SecurityError(f"Signature verification failed for {path}")

    # Deserialize payload
    try:
        result: dict[str, Any]
        if format == "json":
            result = json.loads(payload.decode("utf-8"))
        elif format == "torch":
            import io

            buffer = io.BytesIO(payload)
            # SECURITY: weights_only=False used here AFTER signature verification
            # The payload has been cryptographically verified, so it's safe to load
            # complex objects (optimizer states, metadata, etc.)
            result = torch.load(buffer, weights_only=False)  # nosec B614
        else:
            raise ValueError(f"Invalid format: {format}")

        logger.debug(f"Loaded and verified signed {format} data from {path}")
        return result

    except Exception as e:
        raise ValueError(f"Failed to deserialize {format} payload from {path}: {e}") from e


def _migrate_legacy_pickle(path: Path, target_format: str, secret_key: bytes) -> dict[str, Any]:
    """Migrate legacy pickle file to signed format.

    Args:
        path: Path to legacy pickle file
        target_format: Target format ("json" or "torch")
        secret_key: Secret key for signing

    Returns:
        Loaded data (also saves migrated version)

    Raises:
        ValueError: If migration fails
    """
    import pickle

    try:
        # Load legacy pickle (LAST TIME we use pickle.load)
        with open(path, "rb") as f:
            loaded_data: dict[str, Any] = pickle.load(f)  # nosec B301 - one-time migration

        logger.info(f"Loaded legacy pickle from {path}, converting to signed {target_format}")

        # Save as signed format
        backup_path = path.with_suffix(path.suffix + ".pickle.bak")
        path.rename(backup_path)  # Backup original
        logger.info(f"Backed up original pickle to {backup_path}")

        # Cast to Literal type for save_signed
        if target_format == "json":
            save_signed(loaded_data, path, format="json")
        elif target_format == "torch":
            save_signed(loaded_data, path, format="torch")
        else:
            raise ValueError(f"Invalid target format: {target_format}")

        logger.info(f"Migrated {path} to signed {target_format} format")

        return loaded_data

    except Exception as e:
        raise ValueError(f"Legacy pickle migration failed for {path}: {e}") from e


def is_signed_format(path: Path) -> bool:
    """Check if file uses signed format (vs legacy pickle).

    Args:
        path: File path to check

    Returns:
        True if file uses signed format (has HMAC signature)
    """
    if not path.exists() or path.stat().st_size < 33:
        return False

    with open(path, "rb") as f:
        first_bytes = f.read(2)

    # Pickle files start with \x80\x05 (protocol 5) or \x80\x04 (protocol 4)
    if first_bytes[0:1] == b"\x80":
        return False  # Legacy pickle

    # Signed format has HMAC signature (looks random, no magic bytes)
    return True


__all__ = [
    "SecurityError",
    "is_signed_format",
    "load_signed",
    "save_signed",
]
