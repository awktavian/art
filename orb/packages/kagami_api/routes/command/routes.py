"""Routes for Intent LANG parsing and execution.

Auth: requires read permission for all endpoints.

Typed with Pydantic schemas for OpenAPI and SDK generation.

REFACTORED: Dec 2025
=====================
Cyclomatic complexity reduced from 108 to ~25 by:
1. Moving helper functions to module level
2. Extracting configuration constants
3. Keeping only route definitions in get_router()
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from kagami.core.embodiment.instruction_translator import generate_virtual_action_plan
from kagami.core.unified_agents.app_registry import APP_REGISTRY_V2 as APP_REGISTRY
from kagami.core.unified_agents.app_registry import list_apps_v2 as _list_apps

from kagami_api.rbac import Permission, require_permission
from kagami_api.response_schemas import get_error_responses
from kagami_api.schemas.command import (
    ExecuteRequest,
    ExecuteResponse,
    IntentData,
    NaturalLanguageRequest,
    NaturalLanguageResponse,
    ParseRequest,
    ParseResponse,
    ParsingQualityMetrics,
    SuggestionItem,
    SuggestResponse,
    VirtualActionPlan,
)

# RedisFS removed (Dec 7, 2025) - Use Weaviate via UnifiedStorageRouter
# For semantic file search, use: kagami.core.caching.storage_routing.get_storage_router()

logger = logging.getLogger(__name__)

# =============================================================================
# MODULE-LEVEL CONFIGURATION
# =============================================================================

_ALLOWED_TOOLS_ENV = os.getenv("ALLOWED_TOOLS", "files,plans,crm,post,analytics").strip()
_ALLOWLIST_TOOLS = {t.strip() for t in _ALLOWED_TOOLS_ENV.split(",") if t.strip()}
_ALLOWED_MODELS_ENV = os.getenv("ALLOWED_MODELS", "").strip()
_ALLOWLIST_MODELS = {m.strip() for m in _ALLOWED_MODELS_ENV.split(",") if m.strip()}

# Metadata keys that should remain in metadata (not promoted to params)
_METADATA_ONLY_KEYS = frozenset(
    {
        "model",
        "format",
        "budget_ms",
        "max_tokens",
        "tools",
        "scope",
        "since",
        "until",
        "regex",
        "schema",
        "structured_schema",
        "confidence",
        "ambiguities",
        "virtual_plan",
        "virtual_action_plan",
        "action_replay",
    }
)

_METADATA_PREFIXES = (
    "goal",
    "context.",
    "boundaries.",
    "acceptance.",
    "workflow.",
    "meta.",
    "ctx.",
    "bounds.",
    "accept.",
)


# =============================================================================
# HELPER FUNCTIONS (Module Level)
# =============================================================================


def _is_app_routing_key(key: str) -> bool:
    """Check if key is an app routing hint."""
    return key in {"app", "@app"}


def _is_metadata_key(key: str) -> bool:
    """Check if key should remain in metadata (not promoted to params)."""
    if key.startswith("@"):
        return True
    if key.startswith(_METADATA_PREFIXES):
        return True
    if key in _METADATA_ONLY_KEYS:
        return True
    return False


def _extract_params_and_metadata(
    raw_metadata: Any,
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    """Split metadata into (params, metadata, app_name).

    The core LANG schemas keep key=value pairs under `metadata`. The orchestrator
    expects operational parameters under `params`. We preserve *true* metadata
    (context/boundaries/workflow hints and @directives) while surfacing likely
    action parameters into `params`.
    """
    if not isinstance(raw_metadata, dict):
        return {}, {}, None

    params: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    app_name: str | None = None

    for k, v in raw_metadata.items():
        key = str(k)

        # Explicit app routing hints
        if _is_app_routing_key(key):
            app_name = str(v).strip() if v is not None else None
            metadata[key] = v
            continue

        # Treat parameters dict(s) as params
        if key in {"params", "parameters"} and isinstance(v, dict):
            params.update(v)
            continue

        # Check if key should remain in metadata
        if _is_metadata_key(key):
            metadata[key] = v
            continue

        # Default: treat as an operational parameter
        params[key] = v

    if app_name is not None:
        app_name = app_name.strip().lower() or None

    return params, metadata, app_name


def _convert_intent_to_dict(intent: Any) -> dict[str, Any]:
    """Convert intent object to dict for orchestrator."""
    if hasattr(intent, "model_dump"):
        return intent.model_dump(mode="json")  # type: ignore[no-any-return]
    if hasattr(intent, "dict"):
        return intent.dict()  # type: ignore[no-any-return]
    if hasattr(intent, "__iter__"):
        return dict(intent)
    return {}


def _parse_lang_command(lang_command: str, cache: Any) -> Any:
    """Parse LANG command with caching."""
    from kagami.core.schemas.schemas.intent_lang import parse_intent_lang_v2

    cached_parsed = cache.get_parsed(lang_command)
    if cached_parsed:
        return cached_parsed

    try:
        parsed = parse_intent_lang_v2(lang_command)
        intent = parsed.intent
        cache.set_parsed(lang_command, intent)
        return intent
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


def _validate_direct_intent(body: ExecuteRequest) -> dict[str, Any]:
    """Validate direct intent dict from request body."""
    if not body.action or not body.target:
        raise HTTPException(
            status_code=400,
            detail="Either 'lang' or both 'action' and 'target' must be provided",
        )

    return {
        "action": body.action,
        "target": body.target,
        "params": dict(body.params or {}),
        "metadata": dict(body.metadata or {}),
    }


def _parse_or_validate_intent(body: ExecuteRequest, cache: Any) -> dict[str, Any]:
    """Parse LANG command or validate direct intent dict.

    Returns normalized intent dict with action/target/params/metadata.
    Raises HTTPException on validation failure.
    """
    if body.lang:
        intent = _parse_lang_command(body.lang, cache)
    else:
        intent = _validate_direct_intent(body)

    return _convert_intent_to_dict(intent)


def _merge_params(
    parsed_params: dict[str, Any], intent_params: Any, body_params: Any
) -> dict[str, Any]:
    """Merge params from various sources."""
    merged: dict[str, Any] = {}
    if isinstance(parsed_params, dict):
        merged.update(parsed_params)
    if isinstance(intent_params, dict):
        merged.update(intent_params or {})
    if isinstance(body_params, dict):
        merged.update(body_params)
    return merged


def _merge_metadata(
    parsed_metadata: dict[str, Any], raw_metadata: Any, body_metadata: Any
) -> dict[str, Any]:
    """Merge metadata from various sources."""
    merged: dict[str, Any] = {}
    if isinstance(parsed_metadata, dict):
        merged.update(parsed_metadata)
    if isinstance(raw_metadata, dict):
        merged.update(raw_metadata)
    if isinstance(body_metadata, dict):
        merged.update(body_metadata)
    return merged


def _extract_app_from_metadata(
    parsed_app: str | None, merged_metadata: dict[str, Any]
) -> str | None:
    """Extract app routing hint from metadata."""
    if not isinstance(merged_metadata, dict):
        return parsed_app  # type: ignore[unreachable]

    md_app = merged_metadata.get("app") or merged_metadata.get("@app")
    app_val = parsed_app or (str(md_app).strip().lower() if md_app else None)
    return app_val or None


def _normalize_intent_params(intent_dict: dict[str, Any], body: ExecuteRequest) -> dict[str, Any]:
    """Extract and merge params/metadata from various sources.

    Normalizes the intent dict to have clean params/metadata/app fields
    expected by the orchestrator.
    """
    if not isinstance(intent_dict, dict):
        return intent_dict  # type: ignore[unreachable]

    raw_md = intent_dict.get("metadata")
    parsed_params, parsed_metadata, parsed_app = _extract_params_and_metadata(raw_md)

    # Merge params and metadata
    merged_params = _merge_params(parsed_params, intent_dict.get("params"), body.params)
    merged_metadata = _merge_metadata(parsed_metadata, raw_md, body.metadata)

    intent_dict["params"] = merged_params
    intent_dict["metadata"] = merged_metadata

    # Promote app routing hint to top-level when present
    if not intent_dict.get("app"):
        app_val = _extract_app_from_metadata(parsed_app, merged_metadata)
        if app_val:
            intent_dict["app"] = app_val

    return intent_dict


def _check_high_risk_confirmation(
    intent_dict: dict[str, Any], confirm: bool
) -> ExecuteResponse | None:
    """Check if high-risk operation needs confirmation.

    Returns ExecuteResponse if confirmation needed, None otherwise.
    """
    risk_level = _assess_risk(intent_dict)
    if risk_level != "high" or confirm:
        return None

    import uuid

    correlation_id = str(intent_dict.get("correlation_id") or uuid.uuid4())

    return ExecuteResponse(
        status="needs_confirmation",
        needs_confirmation=True,
        risk=risk_level,
        result={
            "status": "needs_confirmation",
            "message": "This operation requires explicit confirmation",
            "risk_level": risk_level,
            "action": intent_dict.get("action"),
            "target": intent_dict.get("target"),
        },
        intent=IntentData(
            action=intent_dict.get("action"),
            target=intent_dict.get("target"),
            params=intent_dict.get("params", {}),
            metadata=intent_dict.get("metadata"),
        ),
        cached=False,
        correlation_id=correlation_id,
    )


def _check_dangerous_patterns(intent_dict: dict[str, Any]) -> ExecuteResponse | None:
    """Check for dangerous command patterns in metadata/params.

    Returns ExecuteResponse with block status if dangerous pattern found, None otherwise.
    """
    dangerous_patterns = [
        "rm -rf /",
        "curl | bash",
        "wget | sh",
        "truncate table",
        "drop database",
    ]
    metadata = intent_dict.get("metadata", {})
    params = intent_dict.get("params", {})

    check_texts = [
        str(metadata.get("prompt", "")),
        str(metadata.get("NOTES", "")),
        str(metadata.get("notes", "")),
        str(params.get("message", "")),
        str(params.get("text", "")),
        str(params.get("NOTES", "")),
    ]
    combined_text = " ".join(check_texts).lower()

    if not any(pat.lower() in combined_text for pat in dangerous_patterns):
        return None

    import uuid

    correlation_id = str(intent_dict.get("correlation_id") or uuid.uuid4())

    return ExecuteResponse(
        status="blocked",
        result={
            "status": "blocked",
            "reason": "constitution_block",
            "detail": "Dangerous pattern detected in command",
        },
        intent=IntentData(
            action=intent_dict.get("action"),
            target=intent_dict.get("target"),
            params=intent_dict.get("params", {}),
            metadata=intent_dict.get("metadata"),
        ),
        cached=False,
        correlation_id=correlation_id,
    )


def _check_fast_path_intents(intent_dict: dict[str, Any]) -> ExecuteResponse | None:
    """Handle ultra-fast built-in control intents (noop, ping, echo).

    Returns ExecuteResponse if handled, None otherwise.
    """
    try:
        action_upper = str(intent_dict.get("action") or "").upper()
        target_lower = str(intent_dict.get("target") or "").lower()

        if action_upper != "EXECUTE":
            return None

        if target_lower not in {"noop", "ping", "status"} and "echo" not in target_lower:
            return None

        import uuid

        correlation_id = str(intent_dict.get("correlation_id") or uuid.uuid4())
        result = {
            "status": "accepted",
            "result": {
                "echo": target_lower,
                "params": intent_dict.get("params", {}),
                "message": f"Echo: {target_lower}",
            },
            "correlation_id": correlation_id,
        }

        return ExecuteResponse(
            status="accepted",
            result=result,
            intent=IntentData(
                action=intent_dict.get("action"),
                target=intent_dict.get("target"),
                params=intent_dict.get("params", {}),
                metadata=intent_dict.get("metadata"),
            ),
            cached=False,
            correlation_id=correlation_id,
        )
    except Exception:
        return None


def _attach_virtual_action_plan(intent_dict: dict[str, Any]) -> None:
    """Attach virtual action plan metadata to intent (modifies in-place)."""
    if not isinstance(intent_dict, dict):
        return  # type: ignore[unreachable]

    metadata = intent_dict.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        intent_dict["metadata"] = metadata

    if "virtual_action_plan" in metadata:
        return

    try:
        action_plan = generate_virtual_action_plan(intent_dict)
        metadata["virtual_action_plan"] = action_plan

        if action_plan.get("action_list"):
            replay = metadata.setdefault("action_replay", {})
            replay["action_list"] = list(action_plan["action_list"])
            replay["action_speed_list"] = list(action_plan.get("action_speed_list", []))
    except Exception as exc:
        logger.debug("Virtual action plan generation skipped: %s", exc)


def _check_dry_run(intent_dict: dict[str, Any]) -> ExecuteResponse | None:
    """Check if dry_run requested and return preview response.

    Returns ExecuteResponse if dry_run, None otherwise.
    """
    metadata = intent_dict.get("metadata") if isinstance(intent_dict, dict) else {}
    dry_run_requested = isinstance(metadata, dict) and (
        metadata.get("dry_run") or metadata.get("@dry_run")
    )

    if not dry_run_requested:
        return None

    import uuid

    dryrun_corr = str(uuid.uuid4())

    return ExecuteResponse(
        status="dryrun",
        result={
            "status": "dryrun",
            "message": "Dry run mode - no execution performed",
            "preview": {
                "action": intent_dict.get("action"),
                "target": intent_dict.get("target"),
                "params": intent_dict.get("params", {}),
                "would_execute": True,
            },
            "correlation_id": dryrun_corr,
        },
        intent=IntentData(
            action=intent_dict.get("action"),
            target=intent_dict.get("target"),
            params=intent_dict.get("params", {}),
            metadata=intent_dict.get("metadata"),
        ),
        cached=False,
        correlation_id=dryrun_corr,
    )


def _check_result_cache(intent_dict: dict[str, Any], cache: Any) -> ExecuteResponse | None:
    """Check result cache for read-only operations.

    Returns cached ExecuteResponse if found, None otherwise.
    """
    cached_result = cache.get_result(intent_dict)
    if cached_result is None:
        return None

    logger.debug(f"Returning cached result for intent: {intent_dict.get('action')}")
    cached_corr = None
    if isinstance(cached_result, dict):
        cached_corr = cached_result.get("correlation_id")

    return ExecuteResponse(
        status="success",
        result=cached_result,
        intent=IntentData(
            action=intent_dict.get("action"),
            target=intent_dict.get("target"),
            params=intent_dict.get("params", {}),
            metadata=intent_dict.get("metadata"),
        ),
        cached=True,
        correlation_id=cached_corr,
    )


async def _execute_with_orchestrator(intent_dict: dict[str, Any], cache: Any) -> dict[str, Any]:
    """Execute intent via orchestrator with timeout budget.

    Raises HTTPException on timeout or execution failure.
    Returns result dict.
    """
    from kagami.core.orchestrator.core import IntentOrchestrator
    from kagami.core.utils.operation_budget import operation_timeout

    orchestrator = IntentOrchestrator()
    await orchestrator.initialize()

    try:
        async with operation_timeout("intent.execute") as ctx:
            result = await orchestrator.process_intent(intent_dict)
            ctx["result"] = result

        cache.set_result(intent_dict, result)
        return result

    except TimeoutError:
        logger.error(f"Intent execution timeout: {intent_dict.get('action')}")
        raise HTTPException(
            status_code=504,
            detail={
                "error": "timeout",
                "message": "Intent execution exceeded 100ms timeout budget",
                "action": intent_dict.get("action"),
            },
        ) from None


def _build_execute_response(
    result: dict[str, Any], intent_dict: dict[str, Any], cached: bool = False
) -> ExecuteResponse:
    """Build ExecuteResponse from result dict."""
    status = result.get("status", "success") if isinstance(result, dict) else "success"
    corr_val = result.get("correlation_id") if isinstance(result, dict) else None
    corr = str(corr_val) if corr_val is not None else None

    return ExecuteResponse(
        status=status,
        result=result,
        intent=IntentData(
            action=intent_dict.get("action"),
            target=intent_dict.get("target"),
            params=intent_dict.get("params", {}),
            metadata=intent_dict.get("metadata"),
        ),
        cached=cached,
        correlation_id=corr,
    )


def _assess_risk(intent: dict[str, Any] | Any) -> str:
    """Heuristic risk assessment: 'low' | 'medium' | 'high'."""
    action = (intent.get("action") or "").lower() if isinstance(intent, dict) else ""
    target = (intent.get("target") or "").lower() if isinstance(intent, dict) else ""
    if any(k in target for k in ("delete", "remove", "destroy")) or any(
        k in action for k in ("delete", "remove", "destroy")
    ):
        return "high"
    if action in {"end", "catch"}:
        return "medium"
    return "low"


# =============================================================================
# ROUTER FACTORY
# =============================================================================


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.

    REFACTORED: All helper functions moved to module level to reduce
    cyclomatic complexity from 108 to ~25.
    """
    router = APIRouter(prefix="/api/command", tags=["command"])

    # Concurrency limiter for intent execution
    _intent_execution_semaphore = asyncio.Semaphore(50)

    # ==========================================================================
    # EXECUTE ENDPOINT
    # ==========================================================================

    @router.post(
        "/execute",
        response_model=ExecuteResponse,
        responses=get_error_responses(400, 401, 403, 429, 500, 504),
        summary="Execute an intent",
        description="""
    Execute an intent with optional confirmation for high-risk operations.

    **Performance optimizations (Nov 2025):**
    - Intent parsing cached (eliminates redundant parsing)
    - Read-only results cached (5-minute TTL)
    - 100ms timeout budget enforced
    - Concurrency limited to 50 via semaphore

    Accepts either:
    - LANG/2 command: `{"lang": "SLANG EXECUTE action.target"}`
    - Intent dict: `{"action": "EXECUTE", "target": "action.target", ...}`
        """,
        dependencies=[Depends(require_permission(Permission.SYSTEM_READ))],  # type: ignore[func-returns-value]
    )
    async def execute_intent(request: Request, body: ExecuteRequest) -> ExecuteResponse:
        """Execute an intent with confirmation if high-risk."""
        async with _intent_execution_semaphore:
            try:
                from kagami.core.caching.intent_cache import get_intent_cache

                cache = get_intent_cache()

                # 1. Parse or validate intent
                intent_dict = _parse_or_validate_intent(body, cache)

                # 2. Normalize params/metadata/app
                intent_dict = _normalize_intent_params(intent_dict, body)

                # 3. Safety checks
                confirmation_response = _check_high_risk_confirmation(intent_dict, body.confirm)  # type: ignore[arg-type]
                if confirmation_response:
                    return confirmation_response

                block_response = _check_dangerous_patterns(intent_dict)
                if block_response:
                    return block_response

                # 4. Fast-path built-in control intents
                fast_path_response = _check_fast_path_intents(intent_dict)
                if fast_path_response:
                    return fast_path_response

                # 5. Enrich with virtual action plan metadata
                _attach_virtual_action_plan(intent_dict)

                # 6. Check for dry run
                dry_run_response = _check_dry_run(intent_dict)
                if dry_run_response:
                    return dry_run_response

                # 7. Check result cache
                cached_response = _check_result_cache(intent_dict, cache)
                if cached_response:
                    return cached_response

                # 8. Execute via orchestrator
                result = await _execute_with_orchestrator(intent_dict, cache)

                # 9. Build response
                return _build_execute_response(result, intent_dict, cached=False)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Intent execution failed: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e)) from e

    # ==========================================================================
    # PARSE ENDPOINT
    # ==========================================================================

    @router.post(
        "/parse",
        response_model=ParseResponse,
        responses=get_error_responses(400, 401, 500),
        summary="Parse LANG/2 command",
        description="Parse a LANG/2 command into a structured intent with quality metrics.",
        dependencies=[Depends(require_permission(Permission.SYSTEM_READ))],  # type: ignore[func-returns-value]
    )
    async def parse_intent(request: Request, body: ParseRequest) -> ParseResponse:
        """Parse LANG/2 command into structured intent."""
        try:
            from kagami.core.schemas.schemas.intent_lang import parse_intent_lang_v2

            command_text = body.text
            if not command_text:
                raise HTTPException(status_code=400, detail="Text is required")

            # Auto-prepend SLANG header if missing
            command_upper = command_text.strip().upper()
            if not (command_upper.startswith("LANG/2") or command_upper.startswith("SLANG ")):
                command_text = f"SLANG {command_text}"

            parsed = parse_intent_lang_v2(command_text)

            # Extract params from metadata
            raw_md = getattr(parsed.intent, "metadata", None)
            parsed_params, _parsed_metadata, _parsed_app = _extract_params_and_metadata(raw_md)

            # Build intent data
            intent_data = IntentData(
                action=getattr(parsed.intent, "action", None),
                target=getattr(parsed.intent, "target", None),
                params=parsed_params,
                metadata=raw_md if isinstance(raw_md, dict) else None,
            )

            # Build quality metrics
            quality_dict = parsed.quality if isinstance(parsed.quality, dict) else {}
            score = quality_dict.get("score")
            completeness = quality_dict.get("completeness", 1.0)
            try:
                if isinstance(score, int | float):
                    completeness = max(0.0, min(1.0, float(score) / 6.0))
            except Exception:
                pass
            warnings = quality_dict.get("warnings", []) or quality_dict.get("hints", [])
            quality = ParsingQualityMetrics(
                completeness=completeness,
                confidence=quality_dict.get("confidence", 1.0),
                missing=quality_dict.get("missing", []),
                warnings=warnings if isinstance(warnings, list) else [],
            )

            # Generate action plan
            plan_payload = {
                "action": intent_data.action,
                "target": intent_data.target,
                "parameters": intent_data.params,
                "metadata": intent_data.metadata,
                "goal": parsed.sections.get("GOAL") if isinstance(parsed.sections, dict) else None,
            }
            action_plan_raw = generate_virtual_action_plan(plan_payload, sections=parsed.sections)
            action_plan = VirtualActionPlan(
                action_list=action_plan_raw.get("action_list", []),
                action_speed_list=action_plan_raw.get("action_speed_list", []),
                estimated_duration_ms=action_plan_raw.get("estimated_duration_ms"),
            )

            return ParseResponse(
                status="success",
                intent=intent_data,
                sections=parsed.sections if isinstance(parsed.sections, dict) else {},
                quality=quality,
                original_text=command_text,
                virtual_action_plan=action_plan,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    # ==========================================================================
    # NATURAL LANGUAGE ENDPOINT
    # ==========================================================================

    @router.post(
        "/nl",
        response_model=NaturalLanguageResponse,
        responses=get_error_responses(400, 401, 500),
        summary="Parse natural language",
        description="""
    Parse natural language into a structured intent using semantic understanding.

    Uses ConsciousIntentParser to understand natural language and convert it to
    a structured intent with meaning, emotion, and purpose extraction.
        """,
        dependencies=[Depends(require_permission(Permission.SYSTEM_READ))],  # type: ignore[func-returns-value]
    )
    async def parse_natural_language(
        request: Request, body: NaturalLanguageRequest
    ) -> NaturalLanguageResponse:
        """Parse natural language into structured intent."""
        try:
            from kagami.core.schemas.schemas.coordinated_intent import EnhancedIntentParser

            nl_text = body.text
            if not nl_text:
                raise HTTPException(status_code=400, detail="Text is required")

            parser = EnhancedIntentParser()
            enhanced_intent = await parser.parse_with_context(nl_text)

            # Extract intent data
            intent_data = IntentData(
                action=getattr(enhanced_intent.intent, "action", None)
                if hasattr(enhanced_intent, "intent")
                else None,
                target=getattr(enhanced_intent.intent, "target", None)
                if hasattr(enhanced_intent, "intent")
                else None,
                params=getattr(enhanced_intent.intent, "params", {})
                if hasattr(enhanced_intent, "intent")
                else {},
            )

            # Extract semantic features
            meaning = getattr(enhanced_intent, "meaning", None)
            emotion_value = None
            if hasattr(enhanced_intent, "emotion"):
                emotion_value = (
                    enhanced_intent.emotion.value
                    if hasattr(enhanced_intent.emotion, "value")
                    else str(enhanced_intent.emotion)
                )
            purpose = getattr(enhanced_intent, "purpose", None)
            complexity = getattr(enhanced_intent, "complexity", None)
            depth = None
            if hasattr(enhanced_intent, "depth") and enhanced_intent.depth is not None:
                from kagami.core.schemas.schemas.coordinated_intent import IntentDepth

                depth_order = list(IntentDepth)
                try:
                    depth = depth_order.index(enhanced_intent.depth)
                except (ValueError, TypeError):
                    depth = None

            # Generate action plan
            plan_payload = {
                "action": intent_data.action,
                "target": intent_data.target,
                "parameters": intent_data.params,
                "goal": purpose,
                "metadata": {"meaning": meaning, "emotion": emotion_value},
            }
            action_plan_raw = generate_virtual_action_plan(plan_payload)
            action_plan = VirtualActionPlan(
                action_list=action_plan_raw.get("action_list", []),
                action_speed_list=action_plan_raw.get("action_speed_list", []),
                estimated_duration_ms=action_plan_raw.get("estimated_duration_ms"),
            )

            # Generate LANG/2 equivalent
            generated_lang2 = None
            if intent_data.action and intent_data.target:
                generated_lang2 = f"SLANG {intent_data.action} {intent_data.target}"

            return NaturalLanguageResponse(
                status="success",
                intent=intent_data,
                original_text=nl_text,
                generated_lang2=generated_lang2,
                meaning=meaning,
                emotion=emotion_value,
                purpose=purpose,
                complexity=complexity,
                depth=depth,
                virtual_action_plan=action_plan,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Natural language parsing failed: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from None

    # ==========================================================================
    # SUGGEST ENDPOINT
    # ==========================================================================

    @router.get(
        "/suggest",
        response_model=SuggestResponse,
        responses=get_error_responses(401, 500),
        summary="Get typeahead suggestions",
        description="""
    Return typeahead suggestions for the composer.

    Categories:
    - **command**: Supported slash commands
    - **app**: Known apps from registry
    - **verb**: Intent verbs
    - **file**: Recent/matching files

    Filters by prefix if provided.
        """,
        dependencies=[Depends(require_permission(Permission.SYSTEM_READ))],  # type: ignore[func-returns-value]
    )
    async def suggest(
        request: Request,
        prefix: str | None = Query(None, description="User input prefix for filtering"),
        q: str | None = Query(None, description="Alias for prefix (Actions spec)"),
        limit: int = Query(30, ge=1, le=100, description="Maximum suggestions"),
    ) -> SuggestResponse:
        """Return typeahead suggestions for composer."""
        verb_members: dict[str, object] = {}
        try:
            from kagami.core.schemas.schemas.intents import IntentVerb

            verb_members = dict(IntentVerb.__members__)
        except Exception:
            pass

        # Use q as prefix if provided
        if q is not None and q.strip():
            prefix = q

        # Build suggestion lists
        commands = [
            SuggestionItem(type="command", value="/lang ", label="Preview LANG"),
            SuggestionItem(type="command", value="/exec ", label="Execute LANG"),
            SuggestionItem(type="command", value="/app ", label="Send to app"),
            SuggestionItem(type="command", value="/ping", label="Ping server"),
            SuggestionItem(type="command", value="/1", label="Tab: Notifications"),
            SuggestionItem(type="command", value="/2", label="Tab: Events"),
            SuggestionItem(type="command", value="/3", label="Tab: Responses"),
            SuggestionItem(type="command", value="/4", label="Tab: Status"),
        ]

        # Apps from registry
        try:
            apps_info = _list_apps()
            apps = [
                SuggestionItem(type="app", value=k, label=v.get("name") or k)
                for k, v in apps_info.items()
            ]
        except Exception:
            apps = [SuggestionItem(type="app", value=k, label=k) for k in APP_REGISTRY.keys()]

        # Verbs from IntentVerb enum
        verbs = [
            SuggestionItem(type="verb", value=name, label=name.title())
            for name in verb_members.keys()
        ]

        # Files from Weaviate semantic search
        files: list[SuggestionItem] = []
        try:
            from kagami.core.services.storage_routing import get_storage_router

            storage_router = get_storage_router()
            if prefix and len(prefix) >= 2:
                results = await storage_router.search_semantic(prefix, limit=5)
                for r in results:
                    content = r.get("content", "")[:50]
                    source = r.get("source_id", r.get("uuid", ""))[:20]
                    if content:
                        files.append(
                            SuggestionItem(
                                type="file", value=source, label=f"semantic: {content}..."
                            )
                        )
        except Exception:
            pass

        # Filter by prefix
        def _filter(items: list[SuggestionItem]) -> list[SuggestionItem]:
            if not prefix:
                return items
            p = prefix.lower()
            return [i for i in items if i.value.lower().startswith(p)]

        # Combine and limit
        combined = (
            _filter(commands)[:10] + _filter(apps)[:10] + _filter(verbs)[:10] + _filter(files)[:10]
        )[:limit]

        return SuggestResponse(suggestions=combined)

    return router
