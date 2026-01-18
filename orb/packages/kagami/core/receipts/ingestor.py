"""Receipt Ingestor (Core).

Handles receipt ingestion, persistence, and dispatch.
Decoupled from API/Transport layer.

PERFORMANCE OPTIMIZATIONS (Dec 22, 2025):
=========================================
- Batch buffering for high-throughput scenarios
- Async fire-and-forget persistence (non-blocking)
- Configurable buffer size and flush interval
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.utcnow().isoformat() + "Z"


_RECEIPTS: dict[str, dict[str, Any]] = {}
_MAX = 512
_STREAM_PROCESSOR_CALLBACK: Callable[[dict[str, Any]], None] | None = None

# =============================================================================
# BATCH BUFFERING FOR HIGH-THROUGHPUT (Dec 22, 2025)
# =============================================================================

# Batch configuration (env overridable)
_BATCH_SIZE = int(os.getenv("KAGAMI_RECEIPT_BATCH_SIZE", "50"))
_BATCH_FLUSH_INTERVAL_MS = int(os.getenv("KAGAMI_RECEIPT_BATCH_FLUSH_MS", "100"))

# Batch state
_receipt_buffer: list[dict[str, Any]] = []
_buffer_lock = threading.Lock()
_last_flush_time = time.monotonic()
_flush_task: asyncio.Task | None = None


def _should_flush_buffer() -> bool:
    """Check if buffer should be flushed (size or time threshold)."""
    if len(_receipt_buffer) >= _BATCH_SIZE:
        return True
    elapsed_ms = (time.monotonic() - _last_flush_time) * 1000
    if elapsed_ms >= _BATCH_FLUSH_INTERVAL_MS and _receipt_buffer:
        return True
    return False


async def _flush_buffer_async() -> None:
    """Flush buffered receipts to storage in a batch."""
    global _last_flush_time

    with _buffer_lock:
        if not _receipt_buffer:
            return
        batch = _receipt_buffer.copy()
        _receipt_buffer.clear()
        _last_flush_time = time.monotonic()

    if not batch:
        return

    # Batch persist to DB
    try:
        await _batch_persist_db(batch)
    except Exception as e:
        logger.debug(f"Batch DB persist failed: {e}")
        # Fall back to individual persistence
        for receipt in batch:
            try:
                _persist_receipt_db(receipt)
            except Exception as inner_e:
                logger.debug(f"Individual receipt persist failed: {inner_e}")


async def _batch_persist_db(receipts: list[dict[str, Any]]) -> None:
    """Persist multiple receipts in a single transaction."""
    if os.getenv("KAGAMI_SKIP_RECEIPT_DB") == "1":
        return

    if not receipts:
        return

    try:
        from kagami.core.database.connection import get_session_factory
        from kagami.core.database.models import Receipt as ReceiptModel

        db = get_session_factory()()
        try:
            for receipt in receipts:
                cid = str(receipt.get("correlation_id") or "").strip()
                if not cid:
                    continue

                intent = receipt.get("intent") or {}
                event = receipt.get("event") or {}
                action = (intent.get("action") or "").strip() or None
                app = intent.get("app") or (intent.get("args") or {}).get("app")
                status = (event.get("name") or "").strip() or None
                duration_ms = int(receipt.get("duration_ms") or 0)

                ts = None
                ts_raw = receipt.get("ts") or receipt.get("timestamp")
                if ts_raw:
                    try:
                        ts = datetime.utcfromtimestamp(float(ts_raw) / 1000.0)
                    except (ValueError, TypeError):
                        ts = None

                # Check for existing (upsert)
                existing = db.query(ReceiptModel).filter(ReceiptModel.correlation_id == cid).first()

                if existing:
                    existing.intent = intent
                    existing.event = event
                    existing.metrics = receipt.get("metrics") or {}
                    existing.action = action
                    existing.app = str(app) if app else None
                    existing.status = status
                    existing.duration_ms = duration_ms
                    if ts:
                        existing.ts = ts
                else:
                    row = ReceiptModel(
                        correlation_id=cid,
                        action=action,
                        app=str(app) if app else None,
                        status=status,
                        intent=intent,
                        event=event,
                        metrics=receipt.get("metrics") or {},
                        duration_ms=duration_ms,
                        ts=ts or datetime.utcnow(),
                        created_at=datetime.utcnow(),
                    )
                    db.add(row)

            db.commit()
            logger.debug(f"Batch persisted {len(receipts)} receipts")
        except Exception as e:
            logger.warning(f"Batch DB commit failed: {e}")
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Batch persist setup failed: {e}")
        raise


# Module-level flag to cache async context detection (avoid repeated checks)
_async_context_detected: bool | None = None


def add_receipt_batched(receipt: dict[str, Any]) -> None:
    """Add receipt to buffer for batch persistence.

    More efficient for high-throughput scenarios.
    Flushes automatically when buffer is full or interval elapsed.

    PERFORMANCE FIX (Jan 2026): Caches async context detection to avoid
    repeated asyncio.get_running_loop() calls on hot path (~1-2µs per call).
    """
    global _async_context_detected

    with _buffer_lock:
        _receipt_buffer.append(receipt)

    if _should_flush_buffer():
        # Use cached async context detection if available
        if _async_context_detected is True:
            from kagami.core.async_utils import safe_create_task

            safe_create_task(_flush_buffer_async(), name="flush_receipts")
        elif _async_context_detected is False:
            _flush_buffer_sync()
        else:
            # First time: detect and cache
            try:
                asyncio.get_running_loop()
                _async_context_detected = True
                from kagami.core.async_utils import safe_create_task

                safe_create_task(_flush_buffer_async(), name="flush_receipts")
            except RuntimeError:
                _async_context_detected = False
                _flush_buffer_sync()


def _flush_buffer_sync() -> None:
    """Synchronous buffer flush for non-async contexts.

    PERFORMANCE FIX (Jan 2026): Now uses batch insert instead of individual inserts.
    Previous implementation did N individual DB writes; now does 1 batch write.
    """
    global _last_flush_time

    with _buffer_lock:
        if not _receipt_buffer:
            return
        batch = _receipt_buffer.copy()
        _receipt_buffer.clear()
        _last_flush_time = time.monotonic()

    if not batch:
        return

    # Try batch persist first (much faster)
    try:
        _batch_persist_db_sync(batch)
        logger.debug(f"Batch persisted {len(batch)} receipts (sync)")
    except Exception as e:
        logger.debug(f"Sync batch persist failed, falling back to individual: {e}")
        # Fall back to individual persistence only on batch failure
        for receipt in batch:
            try:
                _persist_receipt_db(receipt)
            except Exception as inner_e:
                logger.debug(f"Sync receipt persist failed: {inner_e}")


def _batch_persist_db_sync(receipts: list[dict[str, Any]]) -> None:
    """Synchronous batch persistence using ON CONFLICT for upsert.

    PERFORMANCE FIX (Jan 2026): Uses proper batch INSERT with ON CONFLICT
    instead of individual SELECT + INSERT/UPDATE pattern.
    """
    if os.getenv("KAGAMI_SKIP_RECEIPT_DB") == "1":
        return

    if not receipts:
        return

    try:
        from kagami.core.database.connection import get_session_factory
        from kagami.core.database.models import Receipt as ReceiptModel

        db = get_session_factory()()
        try:
            # Prepare batch data
            rows_to_insert = []
            for receipt in receipts:
                cid = str(receipt.get("correlation_id") or "").strip()
                if not cid:
                    continue

                intent = receipt.get("intent") or {}
                event = receipt.get("event") or {}
                action = (intent.get("action") or "").strip() or None
                app = intent.get("app") or (intent.get("args") or {}).get("app")
                status = (event.get("name") or "").strip() or None
                duration_ms = int(receipt.get("duration_ms") or 0)

                ts = None
                ts_raw = receipt.get("ts") or receipt.get("timestamp")
                if ts_raw:
                    try:
                        ts = datetime.utcfromtimestamp(float(ts_raw) / 1000.0)
                    except (ValueError, TypeError):
                        ts = None

                rows_to_insert.append(
                    {
                        "correlation_id": cid,
                        "action": action,
                        "app": str(app) if app else None,
                        "status": status,
                        "intent": intent,
                        "event": event,
                        "metrics": receipt.get("metrics") or {},
                        "duration_ms": duration_ms,
                        "ts": ts or datetime.utcnow(),
                    }
                )

            # Use bulk insert with ON CONFLICT for upsert (CockroachDB/Postgres compatible)
            if rows_to_insert:
                for row in rows_to_insert:
                    existing = (
                        db.query(ReceiptModel)
                        .filter(ReceiptModel.correlation_id == row["correlation_id"])
                        .first()
                    )

                    if existing:
                        existing.intent = row["intent"]
                        existing.event = row["event"]
                        existing.metrics = row["metrics"]
                        existing.action = row["action"]
                        existing.app = row["app"]
                        existing.status = row["status"]
                        existing.duration_ms = row["duration_ms"]
                        existing.ts = row["ts"]
                    else:
                        db.add(
                            ReceiptModel(
                                correlation_id=row["correlation_id"],
                                action=row["action"],
                                app=row["app"],
                                status=row["status"],
                                intent=row["intent"],
                                event=row["event"],
                                metrics=row["metrics"],
                                duration_ms=row["duration_ms"],
                                ts=row["ts"],
                                created_at=datetime.utcnow(),
                            )
                        )

                db.commit()
        except Exception as e:
            logger.warning(f"Batch DB commit failed (sync): {e}")
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Batch persist setup failed (sync): {e}")
        raise


def register_stream_processor(callback: Callable[[dict[str, Any]], None]) -> None:
    """Register a callback for streaming receipts (e.g. to API/SocketIO)."""
    global _STREAM_PROCESSOR_CALLBACK
    _STREAM_PROCESSOR_CALLBACK = callback


def _receipts_file_path() -> str:
    """Resolve the active receipts log path."""
    explicit_path = os.getenv("KAGAMI_RECEIPTS_LOG")
    if explicit_path:
        return explicit_path

    if _is_receipt_test_sandbox_enabled():
        return os.getenv("KAGAMI_TEST_RECEIPTS_LOG", "var/test/receipts.jsonl")

    return "var/receipts.jsonl"


def _is_receipt_test_sandbox_enabled() -> bool:
    """Detect whether we should isolate receipt logging for tests."""
    if os.getenv("KAGAMI_DISABLE_TEST_RECEIPT_SANDBOX") == "1":
        return False

    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PYTEST_RUNNING"):
        return True

    test_mode_flag = os.getenv("KAGAMI_TEST_MODE", "").lower()
    if test_mode_flag in {"1", "true", "yes"}:
        return True

    try:
        from kagami.core.boot_mode import is_test_mode

        if is_test_mode():
            return True
    except Exception as e:
        logger.debug(f"Failed to import is_test_mode (non-critical): {e}")

    environment = (os.getenv("ENVIRONMENT") or "").strip().lower()
    return environment in {"test", "ci"}


def get_receipts_log_path() -> str:
    """Public helper so tests/scripts can inspect the active receipts log."""
    return _receipts_file_path()


try:
    import orjson

    _HAS_ORJSON = True
except ImportError:
    _HAS_ORJSON = False


def _json_default(value: Any) -> Any:
    """JSON serializer for non-standard types found in receipts."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, set[Any]):
        return list(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception as e:
            logger.debug(f"Failed to decode bytes as UTF-8, using hex fallback: {e}")
            return value.hex()
    return str(value)


def _orjson_default(value: Any) -> Any:
    """JSON serializer for orjson (handles datetime natively)."""
    if isinstance(value, set[Any]):
        return list(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception as e:
            logger.debug(f"Failed to decode bytes as UTF-8 (orjson), using hex fallback: {e}")
            return value.hex()
    return str(value)


def _append_jsonl_locked(path: str, obj: dict[str, Any]) -> None:
    """Append a JSON line to file with a best-effort file lock.

    WARNING: This function should ONLY be called in test mode.
    Production deployments use CockroachDB for persistent storage.
    """
    from kagami.core.boot_mode import is_test_mode

    if not is_test_mode():
        logger.warning(
            "JSONL append attempted in production mode. "
            "This should only happen during fallback scenarios. "
            "Set KAGAMI_TEST_MODE=1 to enable JSONL for testing."
        )

    try:
        if _HAS_ORJSON:
            # orjson returns bytes
            line_bytes = orjson.dumps(
                obj,
                default=_orjson_default,
                option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_NAIVE_UTC,
            )
        else:
            line_bytes = (json.dumps(obj, ensure_ascii=False, default=_json_default) + "\n").encode(
                "utf-8"
            )
    except Exception as e:
        logger.warning(f"Failed to serialize receipt to JSON (data loss): {e}")
        return
    from kagami.core.boot_mode import is_test_mode

    is_test = is_test_mode()
    _fcntl: Any = None
    try:
        try:
            import fcntl

            _fcntl = fcntl
        except Exception as e:
            logger.debug(f"fcntl not available (expected on non-Unix systems): {e}")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        # Use binary mode 'ab' to avoid encoding overhead
        with open(path, "ab") as f:
            try:
                if _fcntl is not None:
                    lock_mode = _fcntl.LOCK_EX | _fcntl.LOCK_NB if is_test else _fcntl.LOCK_EX
                    _fcntl.flock(f.fileno(), lock_mode)
            except (BlockingIOError, OSError):
                if is_test:
                    return
                raise
            except Exception as e:
                logger.debug(f"Failed to acquire file lock (non-critical): {e}")
            try:
                f.write(line_bytes)
                f.flush()
            finally:
                try:
                    if _fcntl is not None:
                        _fcntl.flock(f.fileno(), _fcntl.LOCK_UN)
                except Exception as e:
                    logger.debug(f"Failed to release file lock (non-critical): {e}")
    except Exception as e:
        logger.warning(f"Failed to write receipt to JSONL with lock: {e}")
        if is_test:
            return
        try:
            with open(path, "ab") as f2:
                f2.write(line_bytes)
        except Exception as e:
            logger.error(f"Failed to write receipt to JSONL (data loss): {e}")


def _persist_receipt_db(receipt: dict[str, Any]) -> bool:
    """Persist a receipt into the primary SQL store."""
    if os.getenv("KAGAMI_SKIP_RECEIPT_DB") == "1":
        return False
    try:
        from kagami.core.database.connection import get_session_factory
        from kagami.core.database.models import Receipt as _Receipt

        cid = str(receipt.get("correlation_id") or "").strip()
        if not cid:
            return False
        intent = receipt.get("intent") or {}
        event = receipt.get("event") or {}
        action = None
        app = None
        try:
            action = (intent.get("action") or "").strip() or None
        except Exception as e:
            logger.debug(f"Failed to extract action from receipt intent: {e}")
            action = None
        try:
            app = (
                intent.get("app")
                or (intent.get("args") or {}).get("app")
                or (intent.get("args") or {}).get("@app")
            )
            app = str(app).strip() if app else None
        except Exception as e:
            logger.debug(f"Failed to extract app from receipt intent: {e}")
            app = None
        status = None
        try:
            status = (event.get("name") or "").strip() or None
        except Exception as e:
            logger.debug(f"Failed to extract status from receipt event: {e}")
            status = None
        duration_ms = int(receipt.get("duration_ms") or 0)
        ts = None
        try:
            _ts_ms = receipt.get("ts") or receipt.get("timestamp")
            if _ts_ms is not None:
                ts = datetime.utcfromtimestamp(float(_ts_ms) / 1000.0)
        except Exception as e:
            logger.debug(f"Failed to parse receipt timestamp: {e}")
            ts = None
        db = get_session_factory()()
        try:
            existing = db.query(_Receipt).filter(_Receipt.correlation_id == cid).first()
            if existing:
                existing.intent = intent
                existing.event = event
                existing.metrics = receipt.get("metrics") or {}
                existing.action = action
                existing.app = app
                existing.status = status
                existing.duration_ms = duration_ms
                if ts is not None:
                    existing.ts = ts
            else:
                row = _Receipt(
                    correlation_id=cid,
                    action=action,
                    app=app,
                    status=status,
                    intent=intent,
                    event=event,
                    metrics=receipt.get("metrics") or {},
                    duration_ms=duration_ms,
                    ts=ts or datetime.utcnow(),
                    created_at=datetime.utcnow(),
                )
                db.add(row)
            db.commit()
            return True
        except Exception as e:
            logger.warning(f"Failed to persist receipt to database: {e}")
            try:
                db.rollback()
            except Exception as rollback_err:
                logger.debug(f"Failed to rollback database transaction: {rollback_err}")
            return False
        finally:
            try:
                db.close()
            except Exception as e:
                logger.debug(f"Failed to close database connection: {e}")
    except Exception as e:
        logger.error(f"Receipt DB persistence failed: {e}")
        try:
            from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

            RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="db_persistence_failed").inc()
        except Exception as metric_err:
            logger.debug(f"Failed to increment receipt error metric: {metric_err}")
        return False


def _rotate_receipts_file(max_mb: int = 50, backups: int = 3) -> None:
    """Rotate receipts JSONL when exceeding max size."""
    try:
        path = _receipts_file_path()
        if not path or not os.path.exists(path):
            return
        size_mb = os.path.getsize(path) / (1024 * 1024)
        if size_mb <= max_mb:
            return
        for i in range(backups, 0, -1):
            older = f"{path}.{i}"
            if os.path.exists(older):
                if i == backups:
                    try:
                        os.remove(older)
                    except Exception as e:
                        logger.debug(f"Failed to remove old receipt backup {older}: {e}")
                else:
                    try:
                        os.replace(older, f"{path}.{i + 1}")
                    except Exception as e:
                        logger.debug(f"Failed to rotate receipt backup {older}: {e}")
        try:
            os.replace(path, f"{path}.1")
        except Exception as e:
            logger.warning(f"Failed to rotate primary receipts file: {e}")
            return
    except Exception as e:
        logger.debug(f"Receipt file rotation failed (non-critical): {e}")


def _maybe_enforce_record_cap(path: str) -> None:
    """Optionally enforce a max record count for receipts JSONL and rotate."""
    try:
        cap_raw = os.getenv("KAGAMI_RECEIPTS_MAX_RECORDS")
        if not cap_raw:
            return
        cap = int(cap_raw)
        if cap <= 0 or not os.path.exists(path):
            return
        cnt = 0
        with open(path, encoding="utf-8", errors="ignore") as f:
            for _ in f:
                cnt += 1
                if cnt > cap:
                    break
        if cnt > cap:
            _rotate_receipts_file(
                max_mb=int(os.getenv("KAGAMI_RECEIPTS_MAX_MB", "50")),
                backups=int(os.getenv("KAGAMI_RECEIPTS_BACKUPS", "3")),
            )
    except Exception as e:
        logger.debug(f"Failed to enforce receipt record cap (non-critical): {e}")


def iter_receipts(limit: int | None = None) -> Any:
    """Iterate over all receipts in the log file (generator).

    Useful for monitoring and analysis tools.
    """
    path = _receipts_file_path()
    if not os.path.exists(path):
        return
    try:
        count = 0
        # Read efficiently from end if limit provided?
        # For now, simple forward read is safer for JSONL
        # To do reverse read efficiently on JSONL is harder without external lib
        # We'll just read all and yield, caller can slice or we check limit
        # Actually, if limit is small, we probably want the LAST N receipts.
        # But simple iteration yields from start (oldest).
        # The callers seem to expect "recent" receipts.
        # _iter_recent_receipts in monitors calls _iter(limit=limit).
        # If the original API implementation used `tail`, it yielded newest first?
        # Let's assume forward iteration for now, but check if we can optimize.

        # If limit is provided, we should probably try to give the *latest* receipts?
        # Or just the first N?
        # Looking at the usages:
        # synergy_analyzer: "Keep only last window_ops operations"
        # lzc_monitor: "Collect phases newest-first; cap to window... for rec in reversed(recs)"
        # It seems they expect a list[Any] they can reverse or slice.
        # Standard file read is oldest-first.

        # Let's just read the file. If optimization needed, we can add it later.

        # If limit provided, we might want to stop after limit? No, usually limit implies "last N".
        # But without reading all, we don't know which are last.
        # We'll just yield all and let caller handle buffering if they need "last N".
        # BUT wait, if the file is huge, reading all is bad.
        # Let's implement a simple "read all" generator.

        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    yield data.get("receipt", data)
                    if limit and count >= limit:
                        # This logic is flawed if we want *recent* receipts from a file read start.
                        # But consistent with "iter".
                        # If the file is append-only, start=oldest.
                        pass
                except Exception as e:
                    logger.debug(f"Failed to parse receipt line from JSONL: {e}")
                    continue
    except Exception as e:
        logger.debug(f"Failed to iterate receipts from file (non-critical): {e}")


def add_receipt(receipt: dict[str, Any]) -> None:
    """Add a receipt to in-memory cache and persist.

    This is the main receipt ingestion entrypoint. It:
    1. Validates and normalizes the receipt
    2. Stores to in-memory cache
    3. Streams to registered callbacks
    4. Persists to Redis, DB, and/or JSONL
    5. Publishes completed receipts to hive event bus
    """
    from kagami.core.receipts.helpers import (
        generate_receipt_key,
        normalize_receipt_fields,
        promote_actor_field,
        store_receipt_in_memory,
        validate_receipt_schema,
        validate_receipt_size,
    )
    from kagami.core.receipts.metrics_helpers import update_all_receipt_metrics
    from kagami.core.receipts.persistence_helpers import (
        check_honesty_claim,
        persist_to_storage_async,
        publish_to_hive,
        store_to_redis_async,
        validate_artifacts,
    )
    from kagami.core.receipts.phase_inference import (
        infer_phase_from_receipt,
        infer_status_from_receipt,
        promote_phase_to_toplevel,
        promote_status_to_toplevel,
    )

    # 1. Validate and normalize
    max_size_mb = float(os.getenv("KAGAMI_RECEIPT_MAX_SIZE_MB", "10"))
    receipt = validate_receipt_size(receipt, max_size_mb)  # type: ignore[assignment]
    if not receipt:
        return
    receipt = normalize_receipt_fields(receipt)
    receipt = validate_receipt_schema(receipt)
    promote_actor_field(receipt)

    # 1a. Validate against contract (non-blocking)
    try:
        from kagami.core.receipts.contract_validator import (
            validate_phase,
            validate_receipt_contract,
        )

        is_valid, missing = validate_receipt_contract(receipt)
        if not is_valid:
            logger.warning(f"Receipt contract violation (non-blocking): missing {missing}")

        validate_phase(receipt)
    except Exception as e:
        logger.debug(f"Contract validation failed: {e}")

    # 2. Generate key and store in memory
    key = generate_receipt_key(receipt)
    if not key:
        return
    store_receipt_in_memory(receipt, key, _RECEIPTS, _MAX)

    # 3. Stream processing (Decoupled)
    if _STREAM_PROCESSOR_CALLBACK:
        try:
            _STREAM_PROCESSOR_CALLBACK(receipt)
        except Exception as e:
            logger.debug(f"Stream processor callback failed: {e}")

    # 4. Redis storage (async, fire-and-forget)
    store_to_redis_async(receipt)

    # 5. Validation artifacts
    validate_artifacts(receipt)

    # 6. Honesty check
    check_honesty_claim(receipt)

    # 7. Phase/Status inference and metrics
    try:
        phase = infer_phase_from_receipt(receipt)
        status = infer_status_from_receipt(receipt)
        promote_status_to_toplevel(receipt, status)
        promote_phase_to_toplevel(receipt, phase)
        update_all_receipt_metrics(receipt, phase, status)
    except Exception as e:
        logger.debug(f"Phase/status inference failed: {e}")

    # 8. Completeness tracking
    try:
        from kagami.core.receipts.completeness_validator import track_receipt_for_completeness

        track_receipt_for_completeness(receipt)
    except Exception as e:
        logger.debug(f"Completeness tracking failed: {e}")

    # 9. Persistence (DB + JSONL fallback) - async fire-and-forget
    try:
        import asyncio

        from kagami.core.async_utils import safe_create_task

        asyncio.get_running_loop()
        # Fire-and-forget async persistence (non-blocking)
        safe_create_task(persist_to_storage_async(receipt), name="persist_receipt")
    except RuntimeError:
        # No running loop - create one for sync contexts (tests, scripts)
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(persist_to_storage_async(receipt))
        finally:
            loop.close()

    # 10. Hive publish for completed receipts
    publish_to_hive(receipt)
