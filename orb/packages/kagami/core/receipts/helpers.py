from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def validate_receipt_size(receipt: dict[str, Any], max_size_mb: float) -> dict[str, Any] | None:
    """Validate receipt size is within limits."""
    try:
        serialized = json.dumps(receipt, default=str)
        if len(serialized) > max_size_mb * 1024 * 1024:
            logger.warning(f"Receipt too large ({len(serialized)} bytes), dropping")
            return None
    except Exception:
        # If serialization fails, log warning but let it pass (will fail later if critical)
        pass
    return receipt


def normalize_receipt_fields(receipt: dict[str, Any]) -> dict[str, Any]:
    """Normalize receipt fields."""
    if "ts" not in receipt:
        receipt["ts"] = int(time.time() * 1000)
    if "correlation_id" not in receipt:
        return receipt  # Will be rejected by validator

    # Ensure consistent types
    receipt["duration_ms"] = int(receipt.get("duration_ms", 0) or 0)

    return receipt


def validate_receipt_schema(receipt: dict[str, Any]) -> dict[str, Any]:
    """Validate minimal required schema."""
    if not receipt.get("correlation_id"):
        # Generate if missing for internal events, but log warning
        import uuid

        receipt["correlation_id"] = uuid.uuid4().hex
        logger.debug("Generated correlation_id for receipt missing one")

    return receipt


def promote_actor_field(receipt: dict[str, Any]) -> None:
    """Promote actor field from intent if missing at top level."""
    if not receipt.get("actor"):
        intent = receipt.get("intent", {})
        receipt["actor"] = intent.get("user_id") or intent.get("actor")


def generate_receipt_key(receipt: dict[str, Any]) -> str | None:
    """Generate unique key for receipt."""
    cid = receipt.get("correlation_id")
    if not cid:
        return None
    phase = receipt.get("phase", "unknown")
    ts = receipt.get("ts", int(time.time() * 1000))
    return f"{cid}:{phase}:{ts}"


def store_receipt_in_memory(
    receipt: dict[str, Any], key: str, cache: dict[str, dict[str, Any]], limit: int
) -> None:
    """Store receipt in memory cache with eviction."""
    if len(cache) >= limit:
        # Evict oldest
        try:
            oldest = min(cache.keys(), key=lambda k: cache[k].get("ts", 0))
            del cache[oldest]
        except Exception:
            cache.clear()
    cache[key] = receipt


def iter_recent_receipts(limit: int) -> list[dict[str, Any]]:
    """Get the most recent receipts from storage.

    This function consolidates the duplicate `_iter_recent_receipts` implementations
    from various monitor modules (fractal_monitor, lzc_monitor, causal_monitor,
    synergy_analyzer).

    Args:
        limit: Maximum number of recent receipts to return

    Returns:
        List of receipt dicts, most recent last

    Note:
        Currently reads all receipts and returns the tail. For very large
        receipt stores, consider implementing indexed access in the ingestor.
    """
    try:
        # Dynamic import to avoid static receipts import cycles:
        # ingestor -> helpers (add_receipt), helpers -> ingestor (iter_recent_receipts)
        import importlib

        ingestor_mod = importlib.import_module("kagami.core.receipts.ingestor")
        iter_receipts = getattr(ingestor_mod, "iter_receipts", None)
        if iter_receipts is None:
            return []

        all_recs = list(iter_receipts())
        return all_recs[-limit:] if limit else all_recs
    except Exception:
        return []
