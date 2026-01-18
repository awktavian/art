"""Receipts API - Memory and audit trail.

Fully typed with Pydantic schemas for OpenAPI and SDK generation.

Endpoints:
- GET /api/mind/receipts/ - List recent receipts
- GET /api/mind/receipts/stream - SSE stream of receipts
- GET /api/mind/receipts/search - Search receipts
"""

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

from kagami.core.receipts.ingestor import add_receipt

from kagami_api.response_schemas import get_error_responses
from kagami_api.schemas.receipts import (
    ReceiptRecord,
    ReceiptSearchResponse,
    ReceiptsListResponse,
)
from kagami_api.security import require_auth

from .queries import list_receipts as _list_receipts
from .queries import search_receipts as _search_receipts
from .streaming import stream_receipts

# Alias for tests/compatibility
get_receipts = _list_receipts

__all__ = [
    "get_receipts",
    "get_router",
]


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/mind/receipts", tags=["mind", "receipts"])

    def _dict_to_receipt(r: dict) -> ReceiptRecord:
        """Convert receipt dict to typed ReceiptRecord."""
        intent = r.get("intent") or {}
        event = r.get("event") or {}

        # Parse timestamp
        ts = r.get("ts")
        if isinstance(ts, str):
            try:
                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                logger.debug("Failed to parse timestamp %s, using current time", ts, exc_info=True)
                timestamp = datetime.now()
        elif isinstance(ts, int | float):
            timestamp = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
        else:
            timestamp = datetime.now()

        # Determine phase
        phase: Literal["PLAN", "EXECUTE", "VERIFY"] = "EXECUTE"
        raw_phase = r.get("phase", "execute").upper()
        if raw_phase in ("PLAN", "EXECUTE", "VERIFY"):
            phase = raw_phase

        # Determine status
        status: Literal["success", "failure", "partial"] = "success"
        raw_status = r.get("status", "success").lower()
        if raw_status in ("success", "failure", "partial"):
            status = raw_status

        return ReceiptRecord(
            id=r.get("correlation_id", "unknown"),
            correlation_id=r.get("correlation_id", "unknown"),
            phase=phase,
            status=status,
            app=intent.get("app"),
            action=intent.get("action"),
            agent=r.get("agent"),
            timestamp=timestamp,
            duration_ms=int(r.get("duration_ms") or 0),
            event_name=event.get("name"),
            event_data=event,
            metadata=r.get("metrics") or {},
        )

    @router.get(
        "/",
        response_model=ReceiptsListResponse,
        responses=get_error_responses(500),
        summary="List recent receipts",
        description="List recent receipts from in-memory cache, newest first.",
    )
    async def list_receipts_route(
        limit: int = Query(50, ge=1, le=200, description="Number of receipts to return"),
    ) -> ReceiptsListResponse:
        """List recent receipts."""
        raw = await _list_receipts(limit)
        raw_receipts = raw.get("receipts", [])

        receipts = [_dict_to_receipt(r) for r in raw_receipts]

        return ReceiptsListResponse(
            receipts=receipts,
            count=len(receipts),
            has_more=raw.get("cache_size", 0) > limit,
        )

    @router.post(
        "/",
        responses=get_error_responses(400, 401, 403, 500),
        summary="Ingest a receipt (authenticated)",
        description="Ingest a receipt into the in-memory receipt cache. Requires authentication.",
    )
    async def ingest_receipt_route(  # type: ignore[no-untyped-def]
        payload: dict = Body(..., description="Receipt payload"),
        _user=Depends(require_auth),
    ) -> dict[str, str]:
        """Receipt ingestion endpoint (primarily for internal/testing clients)."""
        # NOTE: `add_receipt` handles validation and persistence.
        add_receipt(payload)
        return {"status": "accepted"}

    @router.get(
        "/stream",
        response_class=StreamingResponse,
        summary="Stream receipts via SSE",
        description="Server-Sent Events stream of receipts as they arrive.",
    )
    async def stream_receipts_route() -> None:
        """SSE stream of receipts."""
        return await stream_receipts()

    @router.get(
        "/search",
        response_model=ReceiptSearchResponse,
        responses=get_error_responses(400, 500),
        summary="Search receipts",
        description="Search receipts with filters on app, correlation_id, and time range.",
    )
    async def search_receipts_route(
        app: str | None = Query(None, description="Filter by app name prefix"),
        correlation_id: str | None = Query(None, description="Filter by correlation ID"),
        since: str | None = Query(None, description="ISO timestamp lower bound"),
        until: str | None = Query(None, description="ISO timestamp upper bound"),
        limit: int = Query(50, ge=1, le=200, description="Results per page"),
        page: int = Query(1, ge=1, description="Page number"),
    ) -> ReceiptSearchResponse:
        """Search receipts with filters."""
        raw = await _search_receipts(app, correlation_id, since, until, limit, page)

        raw_results = raw.get("results", [])
        receipts = [_dict_to_receipt(r) for r in raw_results]

        total = raw.get("total", 0)
        pages = (total + limit - 1) // limit if limit > 0 else 1

        return ReceiptSearchResponse(
            receipts=receipts,
            total=total,
            page=page,
            pages=pages,
            has_more=page < pages,
        )

    return router
