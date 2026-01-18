"""Receipt persistence helper functions.

Extracted from ingestor.py to reduce complexity (CC=61 -> target <30).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any

from kagami.core.caching.redis_keys import RedisKeys

logger = logging.getLogger(__name__)


def store_to_redis_async(receipt: dict[str, Any]) -> None:
    """Store receipt to Redis asynchronously (fire-and-forget)."""
    try:
        import asyncio

        from kagami.core.async_utils import safe_create_task
        from kagami.core.receipts.redis_storage import get_redis_receipt_storage

        storage = get_redis_receipt_storage()
        try:
            asyncio.get_running_loop()
            # NOTE: `name` is for the task wrapper, not the storage API.
            safe_create_task(storage.store(receipt), name="store_receipt")
        except RuntimeError:
            pass  # No running loop - skip async storage
    except Exception as e:
        logger.debug(f"Redis receipt storage failed: {e}")


def validate_artifacts(receipt: dict[str, Any]) -> None:
    """Validate claimed file artifacts in receipt."""
    try:
        from pathlib import Path

        event = receipt.get("event", {})
        data = event.get("data", {}) if isinstance(event, dict) else {}
        execution = data.get("execution", {}) if isinstance(data, dict) else {}

        claimed = []
        if isinstance(execution, dict):
            for key in ("integrations_built", "files_written"):
                val = execution.get(key)
                if isinstance(val, list):
                    claimed.extend([v for v in val if isinstance(v, dict)])

        validations = []
        for item in claimed:
            rel_path = item.get("file") or item.get("path")
            if not rel_path:
                continue
            abs_path = (Path.cwd() / rel_path).resolve()
            validations.append(
                {
                    "file": rel_path,
                    "abs_path": str(abs_path),
                    "exists": abs_path.exists(),
                }
            )

        if validations:
            receipt.setdefault("validation", {})["files"] = validations
    except Exception as e:
        logger.debug(f"Artifact validation failed: {e}")


def check_honesty_claim(receipt: dict[str, Any]) -> None:
    """Verify honesty claims in receipt using CBF honesty validator."""
    try:
        honesty_claim = receipt.get("honesty_claim")
        if not isinstance(honesty_claim, dict) or not honesty_claim.get("statement"):
            return

        from kagami.core.safety.honesty_validator import Claim, require_honest

        claim = Claim(
            statement=str(honesty_claim.get("statement")),
            evidence_type=str(honesty_claim.get("evidence_type") or "benchmark_result"),
            data_source=str(honesty_claim.get("data_source") or ""),
            required_fields=honesty_claim.get("required_fields") or None,
            expected_value=honesty_claim.get("expected_value"),
            tolerance=float(honesty_claim.get("tolerance", 0.1)),
        )
        try:
            require_honest(claim)
            receipt.setdefault("honesty", {})["verified"] = True
        except Exception as e:
            receipt.setdefault("honesty", {})["verified"] = False
            receipt["honesty"]["error"] = str(e)
    except Exception as e:
        logger.debug(f"Honesty check failed: {e}")


async def _persist_receipt_db_async(receipt: dict[str, Any]) -> bool:
    """Persist receipt to CockroachDB (async, non-blocking).

    Args:
        receipt: Receipt dict[str, Any] with correlation_id, phase, etc.

    Returns:
        True if persisted successfully, False otherwise.
    """
    try:
        from kagami.core.database.async_connection import (
            get_async_db_session_with_retry,
            reset_async_engine,
        )
        from kagami.core.database.models import Receipt as _Receipt
    except ImportError as e:
        logger.warning(f"Database modules not available: {e}")
        return False

    # Extract fields
    cid = str(receipt.get("correlation_id") or "").strip()
    if not cid:
        logger.warning("Receipt missing correlation_id, cannot persist")
        return False

    phase = str(receipt.get("phase") or "EXECUTE").upper()

    # First attempt - may fail due to event loop mismatch or missing tables
    _tables_created = False
    for attempt in range(3):  # 3 attempts: loop mismatch, table creation, final try
        try:
            # Use async session with automatic retry on serialization conflicts
            async with get_async_db_session_with_retry(max_retries=3) as session:
                # Check for existing row first (Receipt has UUID primary key)
                from sqlalchemy import select

                existing = await session.execute(
                    select(_Receipt).filter(_Receipt.correlation_id == cid, _Receipt.phase == phase)
                )
                existing_row = existing.scalar_one_or_none()

                if existing_row:
                    # Update existing
                    existing_row.intent = receipt.get("intent") or {}  # type: ignore[assignment]
                    existing_row.event = receipt.get("event") or {}  # type: ignore[assignment]
                    existing_row.metrics = receipt.get("metrics") or {}  # type: ignore[assignment]
                    existing_row.data = receipt.get("data") or {}  # type: ignore[assignment]
                    existing_row.status = receipt.get("status", "success")
                    existing_row.duration_ms = receipt.get("duration_ms", 0)
                    existing_row.ts = datetime.utcnow()  # type: ignore[assignment]
                else:
                    # Insert new
                    # parent_receipt_id is a String(100), not UUID - just pass through
                    new_row = _Receipt(
                        correlation_id=cid,
                        phase=phase,
                        action=receipt.get("action"),
                        app=receipt.get("app"),
                        status=receipt.get("status", "success"),
                        intent=receipt.get("intent") or {},
                        event=receipt.get("event") or {},
                        metrics=receipt.get("metrics") or {},
                        data=receipt.get("data") or {},
                        duration_ms=receipt.get("duration_ms", 0),
                        ts=datetime.utcnow(),
                        parent_receipt_id=receipt.get("parent_receipt_id"),
                        user_id=receipt.get("user_id"),
                        tenant_id=receipt.get("tenant_id"),
                    )
                    session.add(new_row)

                # Note: commit happens automatically in the context manager
                return True

        except RuntimeError as e:
            # Handle event loop mismatch - reset engine and retry once
            if "attached to a different loop" in str(e) and attempt == 0:
                logger.warning(
                    "Detected event loop mismatch in receipt persistence. "
                    "Resetting async engine and retrying..."
                )
                reset_async_engine()
                continue
            # Other RuntimeError or second attempt - log and return False
            logger.error(f"Async receipt persistence failed (RuntimeError): {e}")
            return False
        except Exception as e:
            error_str = str(e).lower()
            # Handle missing tables in test mode (SQLite)
            if "no such table" in error_str and not _tables_created:
                logger.info("Creating database tables for test mode...")
                try:
                    from kagami.core.database.async_connection import init_async_db

                    await init_async_db()
                    _tables_created = True
                    continue  # Retry after table creation
                except Exception as create_err:
                    logger.warning(f"Could not auto-create tables: {create_err}")
            logger.error(f"Async receipt persistence failed: {e}")
            return False

    return False  # Should not reach here, but for safety


async def _persist_receipt_db_with_retry_async(
    receipt: dict[str, Any],
    max_retries: int = 5,
    initial_delay: float = 0.05,
) -> bool:
    """Persist receipt to CockroachDB with exponential backoff retry (async).

    Retries on:
    - OperationalError (network issues)
    - DatabaseError (transient failures)
    - SerializationError / RETRY_SERIALIZABLE (CockroachDB transaction conflicts)

    Does NOT retry on:
    - IntegrityError (duplicate key, schema violation)

    Args:
        receipt: Receipt dict[str, Any] to persist
        max_retries: Maximum number of retry attempts (increased for serialization)
        initial_delay: Initial retry delay in seconds

    Returns:
        True if persistence succeeded, False otherwise.
    """
    import random

    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return await _persist_receipt_db_async(receipt)
        except Exception as e:
            error_str = str(e).lower()

            # Don't retry on integrity errors (permanent failures)
            if "integrity" in error_str or "duplicate" in error_str or "unique" in error_str:
                logger.error(f"Receipt integrity error (not retrying): {e}")
                return False

            # CockroachDB serialization conflicts - MUST retry with jitter
            # These are normal and expected under concurrent load
            is_serialization = (
                "serialization" in error_str
                or "retry_serializable" in error_str
                or "restart transaction" in error_str
                or "transactionretryerror" in error_str
            )

            if attempt < max_retries - 1:
                # Add jitter to prevent thundering herd on serialization conflicts
                jitter = random.uniform(0, delay * 0.5) if is_serialization else 0
                actual_delay = delay + jitter

                if is_serialization:
                    logger.debug(
                        f"Receipt serialization conflict (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {actual_delay:.3f}s"
                    )
                else:
                    logger.warning(
                        f"Receipt persistence failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {actual_delay:.3f}s: {e}"
                    )

                await asyncio.sleep(actual_delay)
                delay *= 2  # Exponential backoff
            else:
                logger.error(f"Receipt persistence failed after {max_retries} attempts: {e}")
                return False
    return False


async def persist_to_storage_async(receipt: dict[str, Any]) -> bool:
    """Persist receipt to CockroachDB with retry logic and fallback to DLQ or JSONL (async).

    PRODUCTION PATH:
    1. CockroachDB (3 retries with exponential backoff)
    2. On failure: DLQ (Redis list[Any])
    3. Alert PagerDuty

    TEST MODE PATH:
    1. CockroachDB (3 retries)
    2. On failure: JSONL file (test-mode only)

    Returns:
        True if persistence succeeded, False otherwise.
    """
    from kagami.core.boot_mode import is_test_mode

    test_mode = is_test_mode()

    # Stage 1: Try CockroachDB with retry (async)
    success = await _persist_receipt_db_with_retry_async(receipt, max_retries=3)
    if success:
        return True

    # Stage 2: Fallback chain
    logger.critical(f"Receipt persistence failed after retries: {receipt.get('correlation_id')}")

    if test_mode:
        # Test mode: fallback to JSONL
        logger.info("Receipt failed CockroachDB, using JSONL (test mode)")
        return _persist_to_jsonl_fallback(receipt)
    else:
        # Production mode: DLQ
        logger.error("Receipt failed CockroachDB, writing to DLQ")
        _persist_to_dlq(receipt)
        _send_pagerduty_alert(receipt)
        return False


def _persist_to_dlq(receipt: dict[str, Any]) -> bool:
    """Persist failed receipt to Dead Letter Queue (Redis list[Any]).

    Args:
        receipt: Receipt dict[str, Any] to persist

    Returns:
        True if DLQ write succeeded, False otherwise.
    """
    try:
        import json

        from kagami.core.caching.redis.factory import RedisClientFactory

        redis_client = RedisClientFactory.get_client(purpose="default", async_mode=False)
        receipt_json = json.dumps(receipt, ensure_ascii=False, default=str)
        redis_client.lpush(RedisKeys.dlq(), receipt_json)
        logger.info(f"Receipt written to DLQ: {receipt.get('correlation_id')}")
        return True
    except Exception as e:
        logger.error(f"Failed to write receipt to DLQ: {e}")
        return False


def _send_pagerduty_alert(receipt: dict[str, Any]) -> None:
    """Send PagerDuty alert for failed receipt persistence.

    Args:
        receipt: Failed receipt dict[str, Any]
    """
    try:
        import os

        correlation_id = receipt.get("correlation_id", "unknown")
        logger.critical(
            f"ALERT: Receipt persistence failed for correlation_id={correlation_id}. "
            f"Receipt is in DLQ ({RedisKeys.dlq()}). Manual recovery required."
        )
        # HARDENED (Dec 22, 2025): PagerDuty via environment config
        pagerduty_key = os.getenv("PAGERDUTY_ROUTING_KEY")
        if pagerduty_key:
            import httpx

            httpx.post(
                "https://events.pagerduty.com/v2/enqueue",
                json={
                    "routing_key": pagerduty_key,
                    "event_action": "trigger",
                    "payload": {
                        "summary": f"Receipt persistence failed: {correlation_id}",
                        "severity": "critical",
                        "source": "kagami-receipts",
                    },
                },
                timeout=5.0,
            )
    except Exception as e:
        logger.debug(f"Failed to send PagerDuty alert: {e}")


def _persist_to_jsonl_fallback(receipt: dict[str, Any]) -> bool:
    """Fallback to local JSONL file when unified storage fails."""
    try:
        # Dynamic import to avoid static receipts import cycles:
        # ingestor -> persistence_helpers (add_receipt), persistence_helpers -> ingestor (fallback)
        import importlib

        ingestor_mod = importlib.import_module("kagami.core.receipts.ingestor")
        _append_jsonl_locked = getattr(ingestor_mod, "_append_jsonl_locked", None)
        _maybe_enforce_record_cap = getattr(ingestor_mod, "_maybe_enforce_record_cap", None)
        _receipts_file_path = getattr(ingestor_mod, "_receipts_file_path", None)
        _rotate_receipts_file = getattr(ingestor_mod, "_rotate_receipts_file", None)

        if not (_append_jsonl_locked and _maybe_enforce_record_cap and _receipts_file_path):
            return False

        path = _receipts_file_path()
        try:
            if _rotate_receipts_file is not None:
                _rotate_receipts_file(
                    max_mb=int(os.getenv("KAGAMI_RECEIPTS_MAX_MB", "50")),
                    backups=int(os.getenv("KAGAMI_RECEIPTS_BACKUPS", "3")),
                )
        except Exception:
            pass
        _maybe_enforce_record_cap(path)
        _append_jsonl_locked(path, {"receipt": receipt})
        return True
    except Exception as e:
        logger.debug(f"JSONL fallback failed: {e}")
        return False


def publish_to_hive(receipt: dict[str, Any]) -> None:
    """Publish completed receipts to the hive event bus."""
    try:
        phase_str = str(receipt.get("phase") or "").strip().lower()
        event_name = str((receipt.get("event") or {}).get("name") or "").lower()

        # Only publish completed/verified receipts
        if phase_str != "verify" and "verified" not in event_name and "completed" not in event_name:
            return

        from kagami.core.async_utils import safe_create_task
        from kagami.core.events import get_unified_bus

        bus = get_unified_bus()
        publish_fn = getattr(bus, "publish", None)
        if not publish_fn:
            return

        intent = receipt.get("intent") or {}
        action = str(intent.get("action") or "").strip() or "operation"
        app_name = str(intent.get("app") or "").strip()
        agent = (
            str((intent.get("args") or {}).get("agent") or app_name or "Agent").strip() or "Agent"
        )
        duration_ms = int(receipt.get("duration_ms") or 0)

        msg = f"✅ {agent} completed {action}"
        if duration_ms:
            msg += f" in {max(1, int(duration_ms))}ms"

        payload = {
            "agent": agent,
            "message": msg,
            "thread": f"agent:{agent}",
            "ts": time.time(),
            "topic": "hive.message",
        }

        try:
            import asyncio

            asyncio.get_running_loop()
            safe_create_task(
                publish_fn("hive.message", payload),
                name="receipt_hive_publish",
            )
        except RuntimeError:
            pass  # No running loop - skip async publish
    except Exception as e:
        logger.debug(f"Hive publish failed: {e}")
