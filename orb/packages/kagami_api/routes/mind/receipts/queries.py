"""Receipt query logic."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from kagami.core.receipts.ingestor import _RECEIPTS, _now_iso

logger = logging.getLogger(__name__)


async def list_receipts(limit: int = 100) -> dict[str, Any]:
    """List recent receipts from in-memory cache."""
    try:
        receipts = list(_RECEIPTS.values())
        # Reverse first to ensure newer items (added later) come first when timestamps are equal
        receipts.reverse()

        def _sort_key(r: dict[str, Any]) -> float:
            ts = r.get("ts", 0)
            if isinstance(ts, (int, float)):
                return float(ts)
            if isinstance(ts, str):
                if ts.isdigit():
                    return float(ts)
                try:
                    # Try ISO format
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    return dt.timestamp() * 1000
                except Exception:
                    logger.debug("Failed to parse timestamp %s in sort key", ts, exc_info=True)
            return 0.0

        receipts.sort(key=_sort_key, reverse=True)
        receipts = receipts[:limit]

        return {
            "receipts": receipts,
            "count": len(receipts),
            "generated_at": _now_iso(),
            "cache_size": len(_RECEIPTS),
        }
    except Exception as e:
        logger.error(f"Failed to list receipts: {e}")
        return {"receipts": [], "count": 0, "generated_at": _now_iso(), "error": str(e)}


async def search_receipts(
    app: str | None,
    correlation_id: str | None,
    since: str | None,
    until: str | None,
    limit: int,
    page: int,
) -> dict[str, Any]:
    """Search recent receipts."""
    use_db_flag = (os.getenv("KAGAMI_RECEIPTS_PG") or "0").lower() in ("1", "true", "yes", "on")
    is_prod = (os.getenv("ENVIRONMENT") or "development").lower() == "production"
    full_op = (os.getenv("KAGAMI_FULL_OPERATION") or "0").lower() in ("1", "true", "yes", "on")

    if use_db_flag or is_prod or full_op:
        try:
            from kagami.core.database.connection import get_session_factory
            from kagami.core.database.models import Receipt as _Receipt

            db = get_session_factory()()
            try:
                q = db.query(_Receipt)
                if app:
                    term = (app or "").strip()
                    q = q.filter(_Receipt.app.ilike(f"{term}%"))
                if correlation_id:
                    q = q.filter(_Receipt.correlation_id == correlation_id)
                try:
                    if since:
                        ts_min = datetime.fromisoformat(since)
                        q = q.filter(_Receipt.ts >= ts_min)
                    if until:
                        ts_max = datetime.fromisoformat(until)
                        q = q.filter(_Receipt.ts <= ts_max)
                except Exception:
                    raise HTTPException(status_code=400, detail="invalid_timestamp") from None
                total = q.count()
                items = q.order_by(_Receipt.ts.desc()).offset((page - 1) * limit).limit(limit).all()
                results: list[dict[str, Any]] = []
                for receipt_row in items:
                    try:
                        intent_obj: dict[str, Any] = receipt_row.intent or {}
                        event_obj: dict[str, Any] = receipt_row.event or {}
                        app_name = intent_obj.get("app") or None
                        action_name = intent_obj.get("action") or None
                        event_name = event_obj.get("name") or None

                        results.append(
                            {
                                "correlation_id": receipt_row.correlation_id,
                                "intent": intent_obj,
                                "event": event_obj,
                                "metrics": receipt_row.metrics or {},
                                "duration_ms": int(getattr(receipt_row, "duration_ms", 0) or 0),
                                "ts": receipt_row.ts.isoformat()
                                if getattr(receipt_row, "ts", None)
                                else None,
                                "guardrails": {},
                                "app": app_name,
                                "action": action_name,
                                "event_name": event_name,
                            }
                        )
                    except Exception:
                        logger.debug("Failed to process receipt row", exc_info=True)
                        continue
                return {
                    "results": results,
                    "generated_at": _now_iso(),
                    "page": page,
                    "page_size": limit,
                    "total": total,
                }
            finally:
                try:
                    db.close()
                except Exception:
                    logger.debug("Failed to close database connection", exc_info=True)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=503, detail="receipts_backend_unavailable") from None

    # Fallback to in-memory cache and file search
    try:
        results: list[dict[str, Any]] = []  # type: ignore[no-redef]
        # First check in-memory cache (fastest)
        for receipt_dict in _RECEIPTS.values():
            match = True
            if correlation_id and receipt_dict.get("correlation_id") != correlation_id:
                match = False
            if app:
                r_app = (receipt_dict.get("intent") or {}).get("app") or ""
                if not str(r_app).startswith(app):
                    match = False
            if since:
                # Simple string comparison for ISO format (approximate)
                if (receipt_dict.get("ts") or "") < since:
                    match = False
            if until:
                if (receipt_dict.get("ts") or "") > until:
                    match = False

            if match:
                # Normalize fields for response
                r_out = receipt_dict.copy()
                intent_data: dict[str, Any] = receipt_dict.get("intent") or {}
                event_data: dict[str, Any] = receipt_dict.get("event") or {}
                r_out["app"] = intent_data.get("app")
                r_out["action"] = intent_data.get("action")
                r_out["event_name"] = event_data.get("name")
                results.append(r_out)

        # Sort by timestamp descending
        results.sort(key=lambda x: x.get("ts", ""), reverse=True)

        # Pagination
        total = len(results)
        start = (page - 1) * limit
        paginated = results[start : start + limit]

        return {
            "results": paginated,
            "generated_at": _now_iso(),
            "page": page,
            "page_size": limit,
            "total": total,
        }
    except Exception as e:
        logger.error(f"Search fallback failed: {e}")
        return {
            "results": [],
            "generated_at": _now_iso(),
            "page": page,
            "page_size": limit,
            "total": 0,
        }


async def get_receipt_completeness() -> dict[str, Any]:
    """Get receipt completeness statistics."""
    try:
        from kagami.core.receipts.completeness_validator import get_completeness_validator

        validator = get_completeness_validator()
        stats = validator.get_statistics()
        incomplete_ops = validator.get_incomplete_operations(limit=20)

        return {
            "status": "success",
            "generated_at": _now_iso(),
            "statistics": stats,
            "incomplete_operations_sample": incomplete_ops,
            "recommendation": (
                (
                    "Complete operations should have PLAN→EXECUTE→VERIFY. "
                    "Consider using ReceiptContext manager for automatic emission."
                )
                if stats["completeness_rate"] < 0.9
                else "Receipt completeness is healthy."
            ),
        }
    except Exception as e:
        logger.error(f"Failed to get completeness stats: {e}")
        return {
            "status": "error",
            "error": str(e),
            "generated_at": _now_iso(),
        }
