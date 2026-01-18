"""Receipts Service - Logic extracted from API routes.

Provides unified interface for receipt persistence and retrieval,
used by both API routes and Core logic.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from kagami.core.database.connection import get_session_factory
from kagami.core.database.models import Receipt as _Receipt

logger = logging.getLogger(__name__)


class ReceiptStorage(Protocol):
    """Protocol for receipt storage backends."""

    def store(self, receipt: dict[str, Any]) -> bool: ...

    def retrieve(self, correlation_id: str) -> dict[str, Any] | None: ...

    def search(
        self,
        app: str | None = None,
        correlation_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]: ...


class SQLReceiptStorage:
    """SQL-based receipt storage (primary).

    Provides persistent receipt storage using SQL database backend.
    This is the primary storage mechanism for production deployments.

    Receipts are stored with correlation IDs and can have multiple phases
    (PLAN, EXECUTE, VERIFY) per correlation ID.
    """

    def store(self, receipt: dict[str, Any]) -> bool:
        """Store a receipt in the SQL database.

        Args:
            receipt: Receipt dictionary containing correlation_id, intent,
                event, metrics, and other metadata.

        Returns:
            True if successfully stored, False otherwise.

        Note:
            Does NOT upsert by correlation_id - a single correlation_id
            can produce multiple rows (PLAN→EXECUTE→VERIFY triplets).
        """
        if os.getenv("KAGAMI_SKIP_RECEIPT_DB") == "1":
            return False

        try:
            from datetime import datetime

            cid = str(receipt.get("correlation_id") or "").strip()
            if not cid:
                return False

            # Extract indices
            intent = receipt.get("intent") or {}
            event = receipt.get("event") or {}
            action = (intent.get("action") or "").strip() or None
            app = (
                intent.get("app")
                or (intent.get("args") or {}).get("app")
                or (intent.get("args") or {}).get("@app")
            )
            app = str(app).strip() if app else None
            # Receipt status is canonical at top-level (inferred by ingestor).
            # Preserve event name inside event JSON, not in status column.
            status = str(receipt.get("status") or "").strip() or None
            duration_ms = int(receipt.get("duration_ms") or 0)

            # Convert timestamp
            ts = None
            ts_ms = receipt.get("ts") or receipt.get("timestamp")
            if ts_ms is not None:
                ts = datetime.utcfromtimestamp(float(ts_ms) / 1000.0)

            # Phase (required by DB schema)
            raw_phase = receipt.get("phase")
            phase = str(raw_phase).strip() if raw_phase is not None else ""
            if not phase:
                # Best-effort inference from event name
                ev_name = str(event.get("name") or "").lower()
                if "plan" in ev_name:
                    phase = "plan"
                elif "verify" in ev_name or "valid" in ev_name:
                    phase = "verify"
                else:
                    phase = "execute"
            phase = phase.upper()

            # Optional identity fields (best-effort)
            def _coerce_uuid(val: Any) -> UUID | None:
                try:
                    if val is None:
                        return None
                    if isinstance(val, UUID):
                        return val
                    s = str(val).strip()
                    if not s:
                        return None
                    return UUID(s)
                except Exception:
                    return None

            user_id = _coerce_uuid(
                receipt.get("user_id")
                or intent.get("user_id")
                or (intent.get("args") or {}).get("user_id")
            )
            tenant_id = (
                receipt.get("tenant_id")
                or intent.get("tenant_id")
                or (intent.get("args") or {}).get("tenant_id")
            )
            tenant_id = (
                str(tenant_id).strip() if tenant_id is not None and str(tenant_id).strip() else None
            )

            db = get_session_factory()()
            try:
                # IMPORTANT: Do NOT upsert by correlation_id.
                # A single correlation_id produces PLAN→EXECUTE→VERIFY triplets.
                row = _Receipt(
                    correlation_id=cid,
                    phase=phase,
                    action=action,
                    app=app,
                    status=status,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    intent=intent,
                    event=event,
                    data=receipt.get("data"),
                    metrics=receipt.get("metrics") or {},
                    duration_ms=duration_ms,
                    ts=ts or datetime.utcnow(),
                    created_at=datetime.utcnow(),
                )
                db.add(row)
                db.commit()
                return True
            except Exception as e:
                logger.warning(f"Receipt store failed (rollback): {e}")
                try:
                    from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

                    RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="sql_store_failed").inc()
                except Exception:
                    pass
                db.rollback()
                return False
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Receipt store error: {e}")
            return False

    def retrieve(self, correlation_id: str) -> dict[str, Any] | None:
        """Retrieve the most recent receipt for a correlation ID.

        Args:
            correlation_id: Unique identifier for the receipt chain.

        Returns:
            Receipt dictionary if found, None otherwise.
            Returns the most recent row when multiple phases exist.
        """
        try:
            db = get_session_factory()()
            try:
                # A correlation_id can have multiple rows (PLAN/EXECUTE/VERIFY).
                # Return the most recent row for convenience.
                orm_rec = (
                    db.query(_Receipt)
                    .filter(_Receipt.correlation_id == correlation_id)
                    .order_by(_Receipt.ts.desc())
                    .first()
                )
                if orm_rec:
                    return {
                        "correlation_id": orm_rec.correlation_id,
                        "intent": orm_rec.intent or {},
                        "event": orm_rec.event or {},
                        "metrics": orm_rec.metrics or {},
                        "duration_ms": int(getattr(orm_rec, "duration_ms", 0) or 0),
                        "ts": orm_rec.ts.isoformat() if getattr(orm_rec, "ts", None) else None,
                    }
                return None
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Receipt retrieve error: {e}")
            return None

    def search(
        self,
        app: str | None = None,
        correlation_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search receipts with optional filters.

        Args:
            app: Optional app name filter (case-insensitive partial match).
            correlation_id: Optional exact correlation ID filter.
            limit: Maximum number of results to return.

        Returns:
            List of matching receipt dictionaries, ordered by timestamp desc.
        """
        try:
            db = get_session_factory()()
            try:
                q = db.query(_Receipt)
                if app:
                    q = q.filter(_Receipt.app.ilike(f"%{app}%"))
                if correlation_id:
                    q = q.filter(_Receipt.correlation_id == correlation_id)

                items = q.order_by(_Receipt.ts.desc()).limit(limit).all()
                results: list[Any] = []
                for r in items:
                    results.append(
                        {
                            "correlation_id": r.correlation_id,
                            "intent": r.intent or {},
                            "event": r.event or {},
                            "metrics": r.metrics or {},
                            "duration_ms": int(getattr(r, "duration_ms", 0) or 0),
                            "ts": r.ts.isoformat() if getattr(r, "ts", None) else None,
                        }
                    )
                return results
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Receipt search error: {e}")
            return []


class JSONLReceiptStorage:
    """JSONL file-based receipt storage (fallback/dev).

    Uses newline-delimited JSON for simple file-based storage.
    Only available in test mode - raises RuntimeError in production.

    Attributes:
        file_path: Optional explicit path to JSONL file.
    """

    def __init__(self, file_path: str | None = None):
        """Initialize JSONL storage.

        Args:
            file_path: Optional explicit path. If None, uses environment
                variables or defaults based on test mode.
        """
        self.file_path = file_path

    def _get_path(self) -> str:
        """Get the JSONL file path based on environment.

        Returns:
            Path to the receipts JSONL file.
        """
        if self.file_path:
            return self.file_path

        # Dynamic resolution to match ingestor logic
        is_test = (
            bool(os.getenv("PYTEST_CURRENT_TEST"))
            or bool(os.getenv("PYTEST_RUNNING"))
            or os.getenv("KAGAMI_TEST_MODE") == "1"
        )

        if is_test and os.getenv("KAGAMI_DISABLE_TEST_RECEIPT_SANDBOX") != "1":
            return os.getenv("KAGAMI_TEST_RECEIPTS_LOG", "var/test/receipts.jsonl")

        return os.getenv("KAGAMI_RECEIPTS_LOG", "var/receipts.jsonl")

    def store(self, receipt: dict[str, Any]) -> bool:
        """Persist receipt to JSONL file.

        WARNING: This function should ONLY be called in test mode or as a fallback.
        Production deployments should never use JSONL storage.

        Raises:
            RuntimeError: If called in production mode (not test mode)
        """
        from kagami.core.boot_mode import is_test_mode

        if not is_test_mode():
            raise RuntimeError(
                "JSONL storage is disabled in production. "
                "Use CockroachDB for persistent storage. "
                "Set KAGAMI_TEST_MODE=1 to enable JSONL for testing."
            )

        try:
            from kagami.utils.jsonl_writer import append_jsonl_locked

            path = self._get_path()
            line = json.dumps({"receipt": receipt}, ensure_ascii=False)
            append_jsonl_locked(path, line)
            return True
        except Exception as e:
            logger.debug(f"JSONL storage failed: {e}")
            return False

    def retrieve(self, correlation_id: str) -> dict[str, Any] | None:
        """Retrieve a receipt by correlation ID.

        Args:
            correlation_id: Unique identifier for the receipt.

        Returns:
            Receipt dictionary if found, None otherwise.
        """
        receipts = self.search(correlation_id=correlation_id, limit=1)
        return receipts[0] if receipts else None

    def search(
        self,
        app: str | None = None,
        correlation_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search receipts in JSONL file with optional filters.

        Args:
            app: Optional app/actor name filter (case-insensitive).
            correlation_id: Optional exact correlation ID filter.
            limit: Maximum number of results to return.

        Returns:
            List of matching receipt dictionaries.
        """
        results: list[Any] = []

        try:
            path = Path(self._get_path())
            if not path.exists():
                return results

            with open(path) as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        receipt = obj.get("receipt", obj)

                        if correlation_id and receipt.get("correlation_id") != correlation_id:
                            continue
                        if app and app.lower() not in str(receipt.get("actor", "")).lower():
                            continue

                        results.append(receipt)

                        if len(results) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.debug(f"JSONL search error: {e}")

        return results[-limit:]


class UnifiedReceiptStorage:
    """Unified receipt storage with multiple backends.

    Provides a facade over SQL and JSONL storage backends, allowing
    receipts to be stored in both for redundancy and easy debugging.

    Attributes:
        sql: SQL storage backend (primary).
        jsonl: JSONL storage backend (fallback/dev).
    """

    def __init__(self) -> None:
        """Initialize unified storage with both backends."""
        self.sql = SQLReceiptStorage()
        self.jsonl = JSONLReceiptStorage()
        self._use_sql = True
        self._use_jsonl = True

    def store(self, receipt: dict[str, Any]) -> bool:
        """Store receipt in all enabled backends.

        Args:
            receipt: Receipt dictionary to store.

        Returns:
            True if stored successfully in at least one backend.
        """
        success = False
        if self._use_sql:
            success = self.sql.store(receipt) or success
        if self._use_jsonl:
            success = self.jsonl.store(receipt) or success
        return success

    def retrieve(self, correlation_id: str) -> dict[str, Any] | None:
        if self._use_sql:
            result = self.sql.retrieve(correlation_id)
            if result:
                return result
        if self._use_jsonl:
            return self.jsonl.retrieve(correlation_id)
        return None

    def search(
        self,
        app: str | None = None,
        correlation_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if self._use_sql:
            results = self.sql.search(app, correlation_id, limit)
            if results:
                return results
        if self._use_jsonl:
            return self.jsonl.search(app, correlation_id, limit)
        return []


_unified_storage: UnifiedReceiptStorage | None = None


def get_unified_receipt_storage() -> UnifiedReceiptStorage:
    """Get singleton unified receipt storage.

    Returns:
        UnifiedReceiptStorage instance
    """
    global _unified_storage
    if _unified_storage is None:
        _unified_storage = UnifiedReceiptStorage()
    return _unified_storage
