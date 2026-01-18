from __future__ import annotations

"""Unified feedback schema and emit helpers for learning.

- Defines FeedbackEvent (pydantic) with common fields
- Emits to dataset writer (JSONL with de-dup and PII redaction)
- Mirrors to GAIA memory bridge as 'preference' items (best-effort)
"""
import hashlib
import logging
import os
from datetime import UTC, datetime

from kagami_observability.metrics import REGISTRY
from prometheus_client import Counter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

LEARNING_FEEDBACK_EVENTS = Counter(
    "kagami_learning_feedback_events_total",
    "Total learning feedback events",
    ["source", "outcome"],
    registry=REGISTRY,
)


class FeedbackEvent(BaseModel):
    correlation_id: str | None = Field(default=None)
    user_id: str | None = Field(default=None)
    session_id: str | None = Field(default=None)
    app: str | None = Field(default=None)
    action: str | None = Field(default=None)
    thumb: str = Field(description="up|down|neutral")
    rationale: str | None = Field(default=None)
    input_summary: str | None = Field(default=None)
    output_summary: str | None = Field(default=None)
    latency_ms: int | None = Field(default=None)
    tokens_in: int | None = Field(default=None)
    tokens_out: int | None = Field(default=None)
    error: str | None = Field(default=None)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    def fingerprint(self) -> str:
        core = "|".join(
            [
                str(self.correlation_id or ""),
                str(self.user_id or ""),
                str(self.app or ""),
                str(self.action or ""),
                str(self.thumb or ""),
                str((self.rationale or "")[:256]),
                str((self.input_summary or "")[:256]),
                str((self.output_summary or "")[:256]),
            ]
        )
        return hashlib.sha256(core.encode("utf-8")).hexdigest()


def emit_feedback(evt: FeedbackEvent, *, source: str = "api") -> None:
    """Emit feedback to dataset and memory bridge (best-effort)."""
    try:
        from kagami.core.learning.dataset import DatasetWriter

        ds_dir = os.getenv("KAGAMI_DATASET_DIR") or os.path.expanduser("~/.kagami/datasets")
        writer = DatasetWriter(base_dir=ds_dir)
        writer.append("preferences.jsonl", evt.model_dump())
        try:
            LEARNING_FEEDBACK_EVENTS.labels(source, "accepted").inc()
        except Exception:
            logger.debug("Failed to record feedback metric", exc_info=True)
    except Exception:
        logger.error("Failed to write feedback event to dataset", exc_info=True)
        try:
            LEARNING_FEEDBACK_EVENTS.labels(source, "error").inc()
        except Exception:
            logger.debug("Failed to record feedback error metric", exc_info=True)


__all__ = ["FeedbackEvent", "emit_feedback"]
