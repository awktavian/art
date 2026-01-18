from __future__ import annotations

"""Shared helpers for Intent LANG parsing, suggestions, and metadata.

This module centralizes logic used by REST routes and WebSocket handlers:
- Parse LANG and LANG/2 strings
- Derive/infer LANG/2 suggestions
- Assess risk and sanitize intent metadata

Keeping these helpers here prevents duplication and drift.
"""
import asyncio
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, TypedDict

from kagami.core.exceptions import ValidationError
from kagami.core.schemas.schemas.intent_lang import parse_intent, parse_intent_lang_v2
from kagami.core.schemas.schemas.intents import Intent
from kagami.core.services.llm import TaskType, get_llm_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ============================================================================
# Exception Types
# ============================================================================


class IntentServiceError(ValidationError):
    """Base exception for intent service operations."""

    error_code = "INTENT_SERVICE_ERROR"


class IntentParseError(IntentServiceError):
    """Intent parsing failed due to invalid input."""

    error_code = "INTENT_PARSE_ERROR"


# ============================================================================
# Result Types
# ============================================================================


@dataclass
class IntentResult:
    """Result of an intent service operation.

    Allows distinguishing between success, expected failures (bad input),
    and unexpected failures (system errors).
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_code: str | None = None


class ParsedResult(TypedDict, total=False):
    intent: dict[str, Any]
    event: dict[str, Any]
    quality: dict[str, Any]
    sections: dict[str, Any]
    suggestions: dict[str, Any]
    compiled_lang: str
    prompt_trace: dict[str, Any] | None


def assess_risk(intent: Intent) -> str:
    """Heuristic risk assessment: 'low' | 'medium' | 'high'."""
    action_raw = getattr(intent, "action", "")
    # Handle Enum
    if hasattr(action_raw, "value"):
        action = str(action_raw.value).lower()
    elif hasattr(action_raw, "name"):
        action = str(action_raw.name).lower()
    else:
        action = str(action_raw).lower()

    target = (intent.target or "").lower()

    if any(k in target for k in ("delete", "remove", "destroy")) or any(
        k in action for k in ("delete", "remove", "destroy")
    ):
        return "high"

    # Medium risk: lifecycle or exception paths
    if action in {"end", "catch"} or target.startswith("end.") or target.startswith("catch."):
        return "medium"

    return "low"


def sanitize_intent_metadata(intent: Intent) -> None:
    """Clamp unsafe values and filter tool hints to an allowlist.

    - max_tokens: clamp [16, 1000]; default 300
    - budget_ms: clamp [50, 30000]; default 2000
    - tools: intersect with ALLOWED_TOOLS env
    - cap long string fields

    Raises:
        IntentServiceError: If critical sanitization fails
    """
    try:
        md = intent.metadata or {}

        # Parse max_tokens with fallback to default
        raw_tokens = md.get("max_tokens")
        try:
            tokens = int(raw_tokens) if raw_tokens is not None else 300
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid max_tokens value '{raw_tokens}', using default 300: {e}")
            tokens = 300
        tokens = max(16, min(1000, tokens))
        md["max_tokens"] = tokens

        # Parse budget_ms with fallback to default
        raw_budget = md.get("budget_ms")
        try:
            budget_ms = int(raw_budget) if raw_budget is not None else 2000
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid budget_ms value '{raw_budget}', using default 2000: {e}")
            budget_ms = 2000
        budget_ms = max(50, min(30000, budget_ms))
        md["budget_ms"] = budget_ms

        allowlist_env = os.getenv("ALLOWED_TOOLS", "files,plans,crm,post,analytics").strip()
        allowlist = {t.strip() for t in allowlist_env.split(",") if t.strip()}
        raw_tools = md.get("tools")
        if isinstance(raw_tools, list):
            md["tools"] = [t for t in raw_tools if str(t).strip() in allowlist][:8]

        for key in ("scope", "regex", "since", "until"):
            if key in md and isinstance(md[key], str):
                md[key] = md[key][:2048]

        intent.metadata = md
    except Exception as e:
        # Unexpected error during sanitization - log and raise
        logger.error(f"Unexpected error sanitizing intent metadata: {e}", exc_info=True)
        raise IntentServiceError(f"Failed to sanitize intent metadata: {e}") from e


def derive_v2_suggestions(intent: Intent, sections: dict[str, Any]) -> dict[str, Any]:
    """Heuristic suggestions to fill missing LANG/2 sections (no LLM).

    Returns:
        Dictionary of suggested sections, or empty dict if derivation fails

    Raises:
        IntentServiceError: If critical error occurs during suggestion derivation
    """
    try:
        suggestions: dict[str, Any] = {}
        action = (getattr(intent, "action", None) or "").lower()
        target = (getattr(intent, "target", None) or "").lower()

        if not (isinstance(sections.get("GOAL"), str) and str(sections.get("GOAL")).strip()):
            if "settings" in target:
                suggestions["GOAL"] = "Harden and test /api/settings behavior with smoke coverage."
            elif "plan" in target:
                suggestions["GOAL"] = "Create or update a plan with clear acceptance."
            else:
                suggestions["GOAL"] = (
                    f"{getattr(intent, 'action', 'EXECUTE')} {getattr(intent, 'target', 'operation')} with clear checks."
                )

        ctx = sections.get("CONTEXT") if isinstance(sections.get("CONTEXT"), dict) else {}
        if not ctx or (not ctx.get("paths") and not ctx.get("refs")):
            ctx_s: dict[str, Any] = {}
            paths: list[str] = []
            refs: list[str] = []
            if "settings" in target:
                paths = [
                    "kagami/api/routes/settings.py",
                    "tests/api/test_settings_route_smoke.py",
                ]
                refs = ["doc:docs/api/rest-api.md#settings"]
            elif "plan" in target:
                paths = [
                    "tests/api/test_plans_api_e2e.py",
                    "tests/api/test_plans_import_artifact_counts.py",
                ]
                refs = ["doc:docs/applications/plans.md"]
            else:
                paths = ["tests/api/test_smoke_basic.py"]
            if paths:
                ctx_s["paths"] = paths
            if refs:
                ctx_s["refs"] = refs
            if ctx_s:
                suggestions["CONTEXT"] = ctx_s

        cons = sections.get("CONSTRAINTS") if isinstance(sections.get("CONSTRAINTS"), dict) else {}
        if not cons:
            suggestions["CONSTRAINTS"] = {
                "perf": {"p99_ms": 100 if "settings" in target else 150},
                "security": {
                    "require_rbac": (
                        "SYSTEM_WRITE" if action in {"execute", "start", "merge"} else "SYSTEM_READ"
                    )
                },
                "dependencies": {"allow_new": False},
            }

        acc = sections.get("ACCEPTANCE") if isinstance(sections.get("ACCEPTANCE"), dict) else {}
        if not acc:
            tests: list[str] = []
            behaviors: list[str] = []
            if "settings" in target:
                tests = ["tests/api/test_settings_route_smoke.py"]
                behaviors = ["GET /api/settings returns defaults and caches"]
            elif "plan" in target:
                tests = ["tests/api/test_plans_api_e2e.py"]
                behaviors = ["POST /api/plans creates a plan and returns JSON"]
            else:
                tests = ["tests/api/test_smoke_basic.py"]
                behaviors = ["/health returns 200; /metrics available"]
            suggestions["ACCEPTANCE"] = {"tests": tests, "behaviors": behaviors}

        wf = sections.get("WORKFLOW") if isinstance(sections.get("WORKFLOW"), dict) else {}
        if not wf or not wf.get("plan"):
            suggestions["WORKFLOW"] = {"plan": "auto"}

        bounds = sections.get("BOUNDARIES") if isinstance(sections.get("BOUNDARIES"), dict) else {}
        if not bounds:
            suggestions["BOUNDARIES"] = {
                "only_edit": ["kagami/api/**", "tests/api/**"],
                "confirm_high_risk": False,
            }

        return suggestions
    except Exception as e:
        # Suggestion derivation is non-critical - log and return empty
        logger.warning(f"Failed to derive V2 suggestions: {e}")
        return {}


async def infer_v2_suggestions_with_llm(intent: Intent, sections: dict[str, Any]) -> dict[str, Any]:
    """Use LLM to infer missing LANG/2 sections. Strict time and token bounds.

    Returns:
        Dictionary of LLM-inferred suggestions, or empty dict if inference fails

    Note:
        This is a best-effort operation. Failures are logged but not raised since
        heuristic suggestions are already available as fallback.
    """
    try:
        llm = get_llm_service()
        missing = [
            key
            for key in (
                "GOAL",
                "CONTEXT",
                "CONSTRAINTS",
                "ACCEPTANCE",
                "WORKFLOW",
                "BOUNDARIES",
            )
            if key not in sections or not sections.get(key)
        ]
        if not missing:
            return {}

        class _V2Suggestions(BaseModel):
            GOAL: str | None = None
            CONTEXT: dict[str, Any] | None = None
            CONSTRAINTS: dict[str, Any] | None = None
            ACCEPTANCE: dict[str, Any] | None = None
            WORKFLOW: dict[str, Any] | None = None
            BOUNDARIES: dict[str, Any] | None = None

        prompt = (
            "You are an assistant helping fill missing sections of K os LANG/2.\n"
            "Given the typed intent and current sections, infer concise defaults for ONLY the missing keys.\n"
            "Return STRICT JSON with keys among: GOAL, CONTEXT, CONSTRAINTS, ACCEPTANCE, WORKFLOW, BOUNDARIES.\n"
            "Be pragmatic and short; include at least one test path when ACCEPTANCE requested.\n\n"
            f"Missing: {missing}\n"
            f"Intent (JSON): {intent.model_dump()}\n"
            f"Sections (JSON): {sections}\n"
        )
        md = intent.metadata or {}
        raw_budget = md.get("budget_ms")
        try:
            budget_ms = int(raw_budget) if raw_budget is not None else 900
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid budget_ms in LLM suggestions, using default 900: {e}")
            budget_ms = 900
        budget_ms = max(200, min(900, budget_ms))
        timeout_s = max(0.2, min(1.0, float(budget_ms) / 1200.0))
        routing_hints = {"format": "json", "max_tokens": 120, "budget_ms": budget_ms}
        try:
            raw = await asyncio.wait_for(
                llm.generate(
                    prompt,
                    app_name="System",
                    task_type=(
                        TaskType.REASONING if hasattr(TaskType, "REASONING") else TaskType.SUMMARY
                    ),
                    temperature=0.2,
                    max_tokens=120,
                    routing_hints=routing_hints,
                    structured_output=_V2Suggestions,
                ),
                timeout=timeout_s,
            )
        except TimeoutError:
            logger.debug(f"LLM suggestion inference timed out after {timeout_s}s")
            return {}
        except Exception as e:
            logger.warning(f"LLM suggestion inference failed: {e}")
            return {}

        # Parse LLM response - handle various return types
        try:
            if isinstance(raw, BaseModel):
                obj = raw.model_dump(exclude_none=True)
                return obj if isinstance(obj, dict) else {}
            if isinstance(raw, dict):  # type: ignore[unreachable]
                return {k: v for k, v in raw.items() if v is not None}  # type: ignore[unreachable]
            # Attempt dict() conversion for other iterable types
            return dict(raw)  # type: ignore[arg-type]
        except Exception as e:
            logger.warning(f"Failed to parse LLM suggestion response: {e}")
            return {}
    except Exception as e:
        # Non-critical operation - log and return empty
        logger.warning(f"Unexpected error in LLM suggestion inference: {e}")
        return {}


async def parse_lang_command(lang: str) -> ParsedResult:
    """Parse a LANG or LANG/2 string and return a rich preview.

    Returns a dict containing at least intent and event. When LANG/2 is used,
    also includes quality, sections, and suggestions (with optional LLM merge).

    Args:
        lang: LANG or LANG/2 command string

    Returns:
        ParsedResult with intent, event, and optional quality/sections/suggestions

    Raises:
        ValueError: If lang is empty or invalid
        IntentParseError: If parsing fails due to malformed input
        IntentServiceError: If unexpected error occurs during parsing
    """
    if not isinstance(lang, str) or not lang.strip():
        raise ValueError("Field 'lang' must be a non-empty string")

    u = lang.strip().upper()

    # Handle LANG/2 and SLANG (compact LANG/2 alias)
    if u.startswith("LANG/2") or u.startswith("SLANG "):
        try:
            parsed_v2 = parse_intent_lang_v2(lang)
        except ValueError as e:
            logger.warning(f"LANG/2 parse failed: {e}")
            raise IntentParseError(f"Invalid LANG/2 syntax: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error parsing LANG/2: {e}", exc_info=True)
            raise IntentServiceError(f"Failed to parse LANG/2 command: {e}") from e

        intent = parsed_v2.intent
        result: ParsedResult = {
            "intent": intent.model_dump(),
            "event": intent.to_event(),
            "quality": parsed_v2.quality,
            "sections": parsed_v2.sections,
        }
        # Heuristic suggestions
        suggestions = derive_v2_suggestions(intent, parsed_v2.sections or {})
        # Opportunistic LLM merge (best-effort, failures already logged)
        try:
            llm_suggestions = await infer_v2_suggestions_with_llm(intent, parsed_v2.sections or {})
            if isinstance(llm_suggestions, dict):
                for k, v in llm_suggestions.items():
                    if k not in suggestions or not suggestions.get(k):
                        suggestions[k] = v
        except Exception as e:
            # Already logged in infer_v2_suggestions_with_llm
            logger.debug(f"LLM suggestions skipped: {e}")
        result["suggestions"] = suggestions
        result["compiled_lang"] = lang
        return result

    # Fallback to unified parser (handles CLI verbs and natural language)
    try:
        intent = await parse_intent(lang, mode="auto")
    except ValueError as e:
        logger.warning(f"Intent parse failed: {e}")
        raise IntentParseError(f"Invalid intent syntax: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error parsing intent: {e}", exc_info=True)
        raise IntentServiceError(f"Failed to parse intent command: {e}") from e

    return {"intent": intent.model_dump(), "event": intent.to_event()}


async def parse_lang_command_fast(lang: str) -> ParsedResult:
    """Fast parse that avoids LLM calls for suggestions.

    - LANG/2/SLANG: returns intent, event, quality, sections, and heuristic suggestions
    - Other formats: falls back to unified parse_intent

    Args:
        lang: LANG or LANG/2 command string

    Returns:
        ParsedResult with intent, event, and optional quality/sections/suggestions

    Raises:
        ValueError: If lang is empty or invalid
        IntentParseError: If parsing fails due to malformed input
        IntentServiceError: If unexpected error occurs during parsing
    """
    if not isinstance(lang, str) or not lang.strip():
        raise ValueError("Field 'lang' must be a non-empty string")

    u = lang.strip().upper()
    if u.startswith("LANG/2") or u.startswith("SLANG "):
        try:
            res = _cached_parse_v2_fast(lang)
        except ValueError as e:
            logger.warning(f"Fast LANG/2 parse failed: {e}")
            raise IntentParseError(f"Invalid LANG/2 syntax: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in fast LANG/2 parse: {e}", exc_info=True)
            raise IntentServiceError(f"Failed to parse LANG/2 command: {e}") from e

        if isinstance(res, dict):
            res["compiled_lang"] = lang
        return res

    # Fallback to unified parser
    try:
        intent = await parse_intent(lang, mode="auto")
    except ValueError as e:
        logger.warning(f"Fast intent parse failed: {e}")
        raise IntentParseError(f"Invalid intent syntax: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error in fast intent parse: {e}", exc_info=True)
        raise IntentServiceError(f"Failed to parse intent command: {e}") from e

    return {"intent": intent.model_dump(), "event": intent.to_event()}


__all__ = [
    "IntentParseError",
    # Result types
    "IntentResult",
    # Exception types
    "IntentServiceError",
    "ParsedResult",
    "assess_risk",
    "derive_v2_suggestions",
    "infer_v2_suggestions_with_llm",
    # Functions
    "parse_lang_command",
    "parse_lang_command_fast",
    "sanitize_intent_metadata",
]


# Internal cache: Fast LANG/2 parse (no LLM). Caches up to 512 distinct inputs.
@lru_cache(maxsize=512)
def _cached_parse_v2_fast(lang: str) -> ParsedResult:
    """Cached LANG/2 parser with sanitization.

    Raises:
        ValueError: If LANG/2 syntax is invalid
        IntentServiceError: If unexpected error occurs
    """
    parsed_v2 = parse_intent_lang_v2(lang)
    intent = parsed_v2.intent
    # Sanitize metadata in preview to clamp unsafe values and respect allowlists
    # This raises IntentServiceError on critical failures
    sanitize_intent_metadata(intent)

    result: ParsedResult = {
        "intent": intent.model_dump(),
        "event": intent.to_event(),
        "quality": parsed_v2.quality,
        "sections": parsed_v2.sections,
    }
    # derive_v2_suggestions handles its own errors and returns {} on failure
    suggestions = derive_v2_suggestions(intent, parsed_v2.sections or {})
    result["suggestions"] = suggestions
    return result
