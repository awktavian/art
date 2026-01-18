from __future__ import annotations

"Intent schema for structured app intents.\n\nThis models the distilled intent pattern (action/target/state/condition/\nalternative/amplification) in a typed, unambiguous way suitable for APIs,\nWebSockets, and the internal app event bus.\n"
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IntentVerb(str, Enum):
    EXECUTE = "EXECUTE"
    PREVIEW = "PREVIEW"  # Preview intent without executing
    OBSERVE = "OBSERVE"
    SYNC = "SYNC"
    MERGE = "MERGE"
    START = "START"
    WORK = "WORK"
    END = "END"
    CHECK = "CHECK"
    TRY = "TRY"
    CATCH = "CATCH"
    STATUS = "STATUS"
    TRACK = "TRACK"  # Track a conversation, thread, or entity over time


class IntentState(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    SYNC = "SYNC"
    ERROR = "ERROR"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


INTENT_EVENT_SCHEMA_VERSION = "1"


class Intent(BaseModel):
    """Typed intent for cross-app coordination.

    - action: verb of the intent (required)
    - target: object or resource the action concerns (required)
    - state/condition/alternative/amplification: optional qualifiers
    - metadata: arbitrary context; do not place secrets here
    - source/user_id/correlation_id/timestamp: tracing fields
    """

    action: IntentVerb = Field(..., description="Primary verb of the intent")
    target: str | None = Field(None, description="Target resource or logical subject")
    state: IntentState | None = Field(None, description="Execution or lifecycle state qualifier")
    condition: str | None = Field(None, description="Condition for execution or branching")
    alternative: str | None = Field(None, description="Alternative branch or fallback behavior")
    amplification: str | None = Field(None, description="Optimization or emphasis hint")
    source: str | None = Field(None, description="Originating subsystem/app")
    user_id: str | None = Field(None, description="End-user associated to intent")
    correlation_id: str | None = Field(None, description="Correlation ID for tracing across events")
    timestamp: str | None = Field(None, description="ISO-8601 timestamp when created (optional)")
    metadata: dict[str, Any] | None = Field(
        default=None, description="Additional non-sensitive context"
    )
    model_config = ConfigDict(extra="forbid")

    def topic(self) -> str:
        """Derive an event topic for this intent.

        Simple, predictable pattern for the app event bus.
        """
        return f"intent.{self.action.value.lower()}"

    def to_event(self) -> dict[str, Any]:
        """Serialize to an event payload suitable for the app event bus."""
        data: dict[str, Any] = self.model_dump()
        data.setdefault("type", "intent")
        data.setdefault("topic", self.topic())
        data.setdefault("schema_version", INTENT_EVENT_SCHEMA_VERSION)
        return data
