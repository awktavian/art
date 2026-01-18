"""Receipts API Schemas.

Typed request/response models for:
- GET /api/mind/receipts/
- GET /api/mind/receipts/search
- GET /api/mind/receipts/stream (SSE)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReceiptRecord(BaseModel):
    """Single receipt record."""

    id: str = Field(..., description="Receipt ID")
    correlation_id: str = Field(..., description="Correlation ID linking related operations")
    phase: Literal["PLAN", "EXECUTE", "VERIFY"] = Field(..., description="Receipt phase")
    status: Literal["success", "failure", "partial"] = Field(..., description="Operation status")

    # Context
    app: str | None = Field(None, description="Application name")
    action: str | None = Field(None, description="Action performed")
    agent: str | None = Field(None, description="Agent that emitted receipt")

    # Timing
    timestamp: datetime = Field(..., description="Receipt timestamp")
    duration_ms: int | None = Field(None, description="Operation duration in ms")

    # Data
    event_name: str | None = Field(None, description="Event name")
    event_data: dict[str, Any] = Field(default_factory=dict, description="Event data")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "rcpt-abc123",
                "correlation_id": "cmd-xyz789",
                "phase": "EXECUTE",
                "status": "success",
                "app": "files",
                "action": "files.list",
                "agent": "forge",
                "timestamp": "2025-12-06T15:30:00Z",
                "duration_ms": 45,
                "event_name": "files.list.completed",
                "event_data": {"count": 10},
            }
        }
    }


class ReceiptsListResponse(BaseModel):
    """Response for receipts list."""

    receipts: list[ReceiptRecord] = Field(..., description="List of receipts")
    count: int = Field(..., description="Number of receipts returned")
    has_more: bool = Field(False, description="More receipts available")


class ReceiptSearchParams(BaseModel):
    """Search parameters for receipts."""

    app: str | None = Field(None, description="Filter by app")
    correlation_id: str | None = Field(None, description="Filter by correlation ID")
    phase: Literal["PLAN", "EXECUTE", "VERIFY"] | None = Field(None, description="Filter by phase")
    status: Literal["success", "failure", "partial"] | None = Field(
        None, description="Filter by status"
    )
    since: datetime | None = Field(None, description="Receipts after this time")
    until: datetime | None = Field(None, description="Receipts before this time")
    limit: int = Field(50, ge=1, le=200, description="Maximum results")
    page: int = Field(1, ge=1, description="Page number")


class ReceiptSearchResponse(BaseModel):
    """Response for receipt search."""

    receipts: list[ReceiptRecord] = Field(..., description="Matching receipts")
    total: int = Field(..., description="Total matching receipts")
    page: int = Field(..., description="Current page")
    pages: int = Field(..., description="Total pages")
    has_more: bool = Field(False, description="More pages available")


__all__ = [
    "ReceiptRecord",
    "ReceiptSearchParams",
    "ReceiptSearchResponse",
    "ReceiptsListResponse",
]
