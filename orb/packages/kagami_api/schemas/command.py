"""Command/Intent API Schemas.

Typed request/response models for:
- POST /api/command/execute
- POST /api/command/parse
- POST /api/command/nl
- GET /api/command/suggest
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field

# =============================================================================
# SHARED MODELS
# =============================================================================


class IntentData(BaseModel):
    """Structured intent representation."""

    action: str | None = Field(None, description="Intent action verb (EXECUTE, CREATE, etc.)")
    target: str | None = Field(None, description="Target of the action")
    params: dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "action": "EXECUTE",
                "target": "system.status",
                "params": {"verbose": True},
                "metadata": {"source": "cli"},
            }
        }
    }


class VirtualActionPlan(BaseModel):
    """Virtual action plan for embodiment."""

    action_list: list[str] = Field(default_factory=list, description="Sequence of actions")
    action_speed_list: list[float] = Field(
        default_factory=list, description="Speed for each action"
    )
    estimated_duration_ms: int | None = Field(None, description="Estimated execution time")

    model_config = {
        "json_schema_extra": {
            "example": {
                "action_list": ["init", "execute", "verify"],
                "action_speed_list": [1.0, 0.8, 1.0],
                "estimated_duration_ms": 150,
            }
        }
    }


class ParsingQualityMetrics(BaseModel):
    """Intent parsing quality metrics.

    Note: Distinct from kagami.forge.schema.QualityMetrics
    which measures character generation quality. This class measures
    LANG/2 command parsing quality.
    """

    completeness: float = Field(ge=0, le=1, description="How complete the intent is (0-1)")
    confidence: float = Field(ge=0, le=1, description="Parser confidence (0-1)")
    missing: list[str] = Field(default_factory=list, description="Missing required fields")
    warnings: list[str] = Field(default_factory=list, description="Parsing warnings")


# =============================================================================
# REQUEST MODELS
# =============================================================================


class ExecuteRequest(BaseModel):
    """Request for intent execution."""

    # Either 'lang' (LANG/2 command) or direct intent fields
    lang: str | None = Field(None, description="LANG/2 command string")
    action: str | None = Field(None, description="Direct intent action")
    target: str | None = Field(None, description="Direct intent target")
    params: dict[str, Any] = Field(default_factory=dict, description="Intent parameters")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Execution metadata")
    confirm: bool | None = Field(
        None,
        description="Optional explicit confirmation for high-risk operations",
    )
    model: str | None = Field(
        None,
        description="Preferred LLM model key (auto, claude, gpt4o, deepseek, gemini, local)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"lang": "SLANG EXECUTE system.status"},
                {"action": "EXECUTE", "target": "system.status", "params": {"verbose": True}},
                {"lang": "help me plan my day", "model": "claude"},
            ]
        }
    }


class ParseRequest(BaseModel):
    """Request for LANG/2 parsing."""

    # Contract compatibility: some clients (and tests) send `{"lang": "..."}` for parse,
    # while others send `{"text": "..."}`. Accept both while presenting a single field.
    text: str = Field(
        ...,
        min_length=1,
        description="LANG/2 command to parse",
        validation_alias=AliasChoices("text", "lang"),
    )

    model_config = {
        "json_schema_extra": {"example": {"text": "SLANG EXECUTE files.list path=/tmp"}}
    }


class NaturalLanguageRequest(BaseModel):
    """Request for natural language parsing."""

    text: str = Field(..., min_length=1, description="Natural language input")
    context: dict[str, Any] = Field(default_factory=dict, description="Context for parsing")
    model: str | None = Field(
        None,
        description="Preferred LLM model key (auto, claude, gpt4o, deepseek, gemini, local)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "show me the system status",
                "context": {"user_role": "admin"},
                "model": "auto",
            }
        }
    }


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class ExecuteResponse(BaseModel):
    """Response from intent execution."""

    status: Literal[
        "success",
        "accepted",
        "executing",
        "completed",
        "needs_confirmation",
        "pending_confirmation",
        "dryrun",
        "blocked",
        "rejected",
        "error",
    ] = Field(..., description="Execution status")
    result: dict[str, Any] = Field(..., description="Execution result")
    intent: IntentData = Field(..., description="Executed intent")
    cached: bool = Field(False, description="Whether result was from cache")
    correlation_id: str | None = Field(None, description="Request correlation ID")
    needs_confirmation: bool | None = Field(
        None, description="Whether operation requires explicit confirmation"
    )
    risk: str | None = Field(
        None, description="Risk level of operation (low, medium, high, critical)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "result": {"output": "System status: healthy"},
                "intent": {"action": "EXECUTE", "target": "system.status", "params": {}},
                "cached": False,
                "correlation_id": "req-abc123",
            }
        }
    }


class ParseResponse(BaseModel):
    """Response from LANG/2 parsing."""

    status: Literal["success", "error"] = Field(..., description="Parse status")
    intent: IntentData = Field(..., description="Parsed intent")
    sections: dict[str, Any] = Field(default_factory=dict, description="LANG/2 sections")
    quality: ParsingQualityMetrics = Field(..., description="Parse quality metrics")
    original_text: str = Field(..., description="Original input text")
    virtual_action_plan: VirtualActionPlan | None = Field(None, description="Generated action plan")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "intent": {"action": "EXECUTE", "target": "files.list"},
                "sections": {"PARAMS": {"path": "/tmp"}},
                "quality": {"completeness": 1.0, "confidence": 0.95, "missing": []},
                "original_text": "SLANG EXECUTE files.list path=/tmp",
            }
        }
    }


class NaturalLanguageResponse(BaseModel):
    """Response from natural language parsing."""

    status: Literal["success", "error"] = Field(..., description="Parse status")
    intent: IntentData = Field(..., description="Parsed intent")
    original_text: str = Field(..., description="Original input")
    generated_lang2: str | None = Field(None, description="Generated LANG/2 equivalent")
    meaning: str | None = Field(None, description="Semantic meaning")
    emotion: str | None = Field(None, description="Detected emotion")
    purpose: str | None = Field(None, description="Inferred purpose")
    complexity: float | None = Field(None, ge=0, le=1, description="Complexity score")
    depth: int | None = Field(None, ge=0, description="Reasoning depth")
    virtual_action_plan: VirtualActionPlan | None = Field(None, description="Action plan")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "intent": {"action": "EXECUTE", "target": "system.status"},
                "original_text": "show me the system status",
                "generated_lang2": "SLANG EXECUTE system.status",
                "meaning": "User wants to view system health",
                "emotion": "curious",
                "purpose": "monitoring",
            }
        }
    }


class SuggestionItem(BaseModel):
    """Single suggestion item."""

    type: Literal["command", "app", "verb", "file"] = Field(..., description="Suggestion type")
    value: str = Field(..., description="Suggestion value")
    label: str = Field(..., description="Display label")

    model_config = {
        "json_schema_extra": {
            "example": {"type": "command", "value": "/exec ", "label": "Execute LANG"}
        }
    }


class SuggestResponse(BaseModel):
    """Response with suggestions."""

    suggestions: list[SuggestionItem] = Field(..., description="List of suggestions")

    model_config = {
        "json_schema_extra": {
            "example": {
                "suggestions": [
                    {"type": "command", "value": "/exec ", "label": "Execute LANG"},
                    {"type": "app", "value": "files", "label": "Files"},
                ]
            }
        }
    }


class CommandFallbackResponse(BaseModel):
    """Response when kagami_intelligence is not available."""

    ok: bool = Field(True, description="Operation accepted but not processed")

    model_config = {"json_schema_extra": {"example": {"ok": True}}}


class CommandBlockedResponse(BaseModel):
    """Response when command is blocked by CBF safety check."""

    status: Literal["blocked"] = Field(..., description="Command was blocked")
    reason: str = Field(..., description="High-level reason for blocking")
    detail: str = Field(..., description="Detailed explanation")
    correlation_id: str = Field(..., description="Request correlation ID")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    h_x: float | None = Field(None, description="CBF safety barrier value")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "blocked",
                "reason": "cbf_violation",
                "detail": "Safety barrier h(x) < 0: operation violates safety constraints",
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-12-27T10:30:00.000Z",
                "h_x": -0.15,
            }
        }
    }


class CommandSuccessResponse(BaseModel):
    """Response for successful command execution."""

    response: Any = Field(..., description="Command execution result")
    status: Literal["success"] = Field(..., description="Execution succeeded")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    correlation_id: str = Field(..., description="Request correlation ID")
    receipt: dict[str, Any] = Field(..., description="Execution receipt with metrics")

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": {"output": "Command executed successfully"},
                "status": "success",
                "timestamp": "2025-12-27T10:30:00.000Z",
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                "receipt": {
                    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "intent": {
                        "action": "command.execute",
                        "app": "Core",
                        "args": {"text": "system.status", "command": "status"},
                    },
                    "event": {"name": "command.executed", "data": {}},
                    "duration_ms": 42,
                    "ts": 1735296600000,
                    "guardrails": {
                        "rbac": "enforced",
                        "cbf_safety": "passed",
                        "csrf": "n/a",
                        "rate_limit": "ok",
                        "idempotency": "accepted",
                    },
                    "metrics": {"endpoint": "/metrics"},
                },
            }
        }
    }


# Union type for all possible command responses
CommandResponse = CommandFallbackResponse | CommandBlockedResponse | CommandSuccessResponse


__all__ = [
    "CommandBlockedResponse",
    "CommandFallbackResponse",
    "CommandResponse",
    "CommandSuccessResponse",
    "ExecuteRequest",
    "ExecuteResponse",
    "IntentData",
    "NaturalLanguageRequest",
    "NaturalLanguageResponse",
    "ParseRequest",
    "ParseResponse",
    "ParsingQualityMetrics",
    "SuggestResponse",
    "SuggestionItem",
    "VirtualActionPlan",
]
