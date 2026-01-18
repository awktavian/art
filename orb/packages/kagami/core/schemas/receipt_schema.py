"""Receipt schema (lightweight) for K OS tests and instrumentation.

RECEIPTS AS EXECUTION COMMITS:
===============================
A Receipt is an immutable record of task execution - an "execution commit"
analogous to a git commit but for runtime operations instead of code changes.

Structural parallel to git commits:
- correlation_id ≈ commit hash (unique identifier)
- workspace_hash ≈ author/branch (execution context)
- parent_receipt_id ≈ parent commit (DAG structure)
- timestamp ≈ commit timestamp
- action/tool_calls ≈ commit message/diff
- status ≈ CI pass/fail

Both git commits and receipts are:
- Immutable (append-only)
- Cryptographically signed (provenance)
- Stigmergic traces (enable learning from past)
- Form DAGs (parent-child relationships)

Git commits track DEVELOPMENT history (code evolution).
Runtime receipts track EXECUTION history (task outcomes).

Together they form the superorganism's complete memory.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


def _now_utc() -> datetime:
    return datetime.now(UTC)


class Receipt(BaseModel):
    """Lightweight receipt model with sensible defaults.

    CRITICAL OBSERVABILITY FIELDS:
    - tool_calls: List of tools used during execution (enables Strange Loop observability)
    - phase: Which phase of PLAN/EXECUTE/VERIFY this receipt represents
    - correlation_id: Links related receipts across phases
    - parent_receipt_id: Links to parent receipt for phase/operation DAG
    - workspace_hash: Agent domain/colony identifier
    - self_pointer: Agent identity hash
    """

    correlation_id: str
    parent_receipt_id: str | None = Field(
        default=None, description="Parent receipt ID for phase/operation DAG traversal"
    )
    phase: str | None = None
    workspace_hash: str | None = None
    timestamp: datetime | None = Field(default=None)
    ts: int | None = Field(default=None)
    status: str | None = None
    loop_depth: int | None = Field(default=None, ge=0, le=10)
    self_pointer: str | None = None
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list[Any],
        description="Tools used during execution (CRITICAL for observability)",
    )
    guardrails: dict[str, Any] = Field(default_factory=dict[str, Any])
    metrics: dict[str, Any] = Field(default_factory=dict[str, Any])
    intent: dict[str, Any] = Field(default_factory=dict[str, Any])
    event: dict[str, Any] = Field(default_factory=dict[str, Any])
    verifier: dict[str, Any] | None = None
    prediction: dict[str, Any] | None = None
    prediction_error_ms: float | None = None
    valence: float | None = None
    quality_gates: dict[str, str] | None = None
    learning: dict[str, bool] | None = None
    app: str | None = None
    action: str | None = None
    args: dict[str, Any] | None = None
    content_id: str | None = None
    # Legacy fields (migrated from schemas/receipt.py)
    duration_ms: int = Field(default=0, description="Execution duration in milliseconds")
    prompt_trace: dict[str, Any] | None = Field(
        default=None, description="Prompt execution trace for audit"
    )
    precision: float | None = Field(default=None, description="Evaluator confidence 0..1")

    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def _synchronise_timestamps(self) -> Receipt:
        if self.timestamp is not None and self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=UTC)

        if self.timestamp is None and self.ts is not None:
            self.timestamp = datetime.fromtimestamp(self.ts / 1000.0, tz=UTC)
        elif self.timestamp is not None and self.ts is None:
            self.ts = int(self.timestamp.timestamp() * 1000)
        elif self.timestamp is None and self.ts is None:
            now = _now_utc()
            self.timestamp = now
            self.ts = int(now.timestamp() * 1000)

        if self.status is None:
            self.status = "unknown"

        return self


ReceiptSchema = Receipt


def validate_receipt(receipt: dict[str, Any]) -> Receipt:
    """Validate a receipt dictionary against the lightweight schema."""
    return Receipt(**receipt)


__all__ = ["Receipt", "ReceiptSchema", "validate_receipt"]
