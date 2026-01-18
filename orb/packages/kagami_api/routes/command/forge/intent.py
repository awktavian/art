"""Forge intent endpoint for LANG/2 style commands.

Provides a unified endpoint that accepts LANG/2 style intent strings
for all Forge operations, aligning with the K OS intent system.

Usage:
    POST /api/forge/intent
    {
        "intent": "character.generate",
        "params": {"concept": "brave warrior", "quality": "draft"}
    }

Or with LANG/2 string:
    POST /api/forge/intent
    {
        "lang": "EXECUTE character.generate @app=Forge {\"concept\": \"warrior\"}"
    }
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from kagami.forge.service import (
    ForgeOperation,
    ForgeRequest,
    ForgeService,
    get_forge_service,
)
from pydantic import BaseModel, Field, field_validator, model_validator

from kagami_api.rbac import Permission, require_permission
from kagami_api.routes.forge_common import build_forge_metadata, emit_forge_receipt

logger = logging.getLogger(__name__)

# Security constants for LANG/2 parser (MODULE LEVEL - PUBLIC API)
MAX_INTENT_LENGTH = 100  # Max characters in intent string
MAX_PARAMS_SIZE = 1024  # Max bytes for params JSON
MAX_NESTING_DEPTH = 5  # Max depth for nested structures
REGEX_TIMEOUT_SEC = 1.0  # Timeout for regex matching

# Allowlist of valid parameter names per operation (MODULE LEVEL - PUBLIC API)
PARAM_ALLOWLISTS = {
    ForgeOperation.CHARACTER_GENERATION: {
        "concept",
        "quality",
        "quality_mode",
        "style",
        "export_formats",
        "metadata",
    },
    ForgeOperation.IMAGE_TO_CHARACTER: {
        "image",
        "image_url",
        "image_path",
        "quality",
        "quality_mode",
        "export_formats",
        "metadata",
    },
    ForgeOperation.ANIMATION_FACIAL: {
        "character_id",
        "animation_type",
        "duration",
        "intensity",
        "export_formats",
        "metadata",
    },
    ForgeOperation.ANIMATION_GESTURE: {
        "character_id",
        "gesture_type",
        "duration",
        "export_formats",
        "metadata",
    },
    ForgeOperation.ANIMATION_MOTION: {
        "character_id",
        "motion_description",
        "duration",
        "export_formats",
        "metadata",
    },
    # Creator-facing Genesis video generation (rich nested spec)
    ForgeOperation.GENESIS_VIDEO: {
        # Either pass everything under `spec`, or pass a compact template payload.
        "spec",
        "template",
        "template_args",
        # Common top-level overrides (for non-spec mode)
        "output_dir",
        "name",
        "preset",
        "width",
        "height",
        "fps",
        "duration",
        "spp",
        "camera_pos",
        "camera_lookat",
        "camera_fov",
        "camera_aperture",
        "camera_focus",
        "ambient_light",
        # Physics
        "gravity",
        "dt",
        "substeps",
        # Entities/lights
        "entities",
        "lights",
        # Rendering/simulation knobs
        "raytracer",
        "sph_bounds",
        "sph_particle_size",
        "sph_options",
        "mpm_options",
        "fem_options",
        "pbd_options",
        "metadata",
    },
}

# Parameter type specifications (MODULE LEVEL - PUBLIC API)
PARAM_TYPES = {
    "concept": str,
    "quality": str,
    "quality_mode": str,
    "style": str,
    "duration": (int, float),
    "intensity": (int, float),
    "character_id": str,
    "animation_type": str,
    "gesture_type": str,
    "motion_description": str,
    "image_url": str,
    "image_path": str,
    "export_formats": list,
    "metadata": dict,
    # Genesis creator params
    "spec": dict,
    "template": str,
    "template_args": dict,
    "output_dir": str,
    "name": str,
    "preset": str,
    "width": int,
    "height": int,
    "fps": int,
    "spp": int,
    "camera_pos": (list, tuple),
    "camera_lookat": (list, tuple),
    "camera_fov": (int, float),
    "camera_aperture": (int, float),
    "camera_focus": (int, float),
    "ambient_light": (list, tuple),
    "gravity": (list, tuple),
    "dt": (int, float),
    "substeps": int,
    "entities": list,
    "lights": list,
    "raytracer": dict,
    "sph_bounds": (list, tuple),
    "sph_particle_size": (int, float),
    "sph_options": dict,
    "mpm_options": dict,
    "fem_options": dict,
    "pbd_options": dict,
}


# Request/Response Models (MODULE LEVEL - PUBLIC API)
class ForgeIntentRequest(BaseModel):
    """Request model for Forge intent endpoint."""

    intent: str | None = Field(
        None,
        description="Intent in 'capability.action' format",
        max_length=MAX_INTENT_LENGTH,
    )
    params: dict[str, Any] = Field(default_factory=dict, description="Intent parameters")
    lang: str | None = Field(
        None,
        description="Full LANG/2 string (alternative to intent)",
        max_length=MAX_INTENT_LENGTH + MAX_PARAMS_SIZE,
    )
    correlation_id: str | None = None
    idempotency_key: str | None = None

    @field_validator("intent")
    @classmethod
    def validate_intent_format(cls, v: str | None) -> str | None:
        """Validate intent follows 'capability.action' format."""
        if v is None:
            return v
        if not re.match(r"^[\w]+\.[\w]+$", v):
            raise ValueError(
                "Intent must follow 'capability.action' format (alphanumeric + dots only)"
            )
        return v

    @field_validator("params")
    @classmethod
    def validate_params_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate params don't exceed size limits."""
        try:
            serialized = json.dumps(v)
            if len(serialized.encode("utf-8")) > MAX_PARAMS_SIZE:
                raise ValueError(f"Parameters exceed maximum size of {MAX_PARAMS_SIZE} bytes")
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid parameters: {e}") from e
        return v

    @model_validator(mode="after")
    def validate_intent_or_lang(self) -> ForgeIntentRequest:
        """Ensure either intent or lang is provided, not both."""
        if not self.intent and not self.lang:
            raise ValueError("Either 'intent' or 'lang' must be provided")
        if self.intent and self.lang:
            raise ValueError("Cannot provide both 'intent' and 'lang'")
        return self


class ForgeIntentResponse(BaseModel):
    """Response model for Forge intent endpoint."""

    success: bool
    capability: str
    data: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    duration_ms: int = 0
    cached: bool = False
    error: str | None = None
    error_code: str | None = None


# Intent to capability mapping (MODULE LEVEL - PUBLIC API)
INTENT_MAPPING = {
    # Character generation
    "character.generate": ForgeOperation.CHARACTER_GENERATION,
    "character.create": ForgeOperation.CHARACTER_GENERATION,
    "forge.generate": ForgeOperation.CHARACTER_GENERATION,
    # Image to character
    "character.from_image": ForgeOperation.IMAGE_TO_CHARACTER,
    "image.to_character": ForgeOperation.IMAGE_TO_CHARACTER,
    "forge.from_image": ForgeOperation.IMAGE_TO_CHARACTER,
    # Animation
    "animation.facial": ForgeOperation.ANIMATION_FACIAL,
    "animation.blinks": ForgeOperation.ANIMATION_FACIAL,
    "animation.expressions": ForgeOperation.ANIMATION_FACIAL,
    "animation.gesture": ForgeOperation.ANIMATION_GESTURE,
    "animation.idle": ForgeOperation.ANIMATION_GESTURE,
    "animation.motion": ForgeOperation.ANIMATION_MOTION,
    "motion.generate": ForgeOperation.ANIMATION_MOTION,
    # Genesis creator video
    "genesis.video": ForgeOperation.GENESIS_VIDEO,
    "video.generate": ForgeOperation.GENESIS_VIDEO,
    "forge.genesis_video": ForgeOperation.GENESIS_VIDEO,
}


# Helper functions (MODULE LEVEL - PUBLIC API)
def _check_nesting_depth(
    obj: Any, max_depth: int = MAX_NESTING_DEPTH, current_depth: int = 0
) -> None:
    """Recursively check nesting depth of dict/list structures.

    Args:
        obj: Object to check
        max_depth: Maximum allowed depth
        current_depth: Current depth level

    Raises:
        ValueError: If nesting exceeds max_depth
    """
    if current_depth > max_depth:
        raise ValueError(f"Nesting depth exceeds maximum of {max_depth} levels")

    if isinstance(obj, dict):
        for value in obj.values():
            _check_nesting_depth(value, max_depth, current_depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _check_nesting_depth(item, max_depth, current_depth + 1)


def _coerce_param_type(value: Any, expected_type: type | tuple[type, ...]) -> Any:
    """Coerce a parameter value to the expected type.

    Args:
        value: Value to coerce
        expected_type: Expected type or tuple of types

    Returns:
        Coerced value

    Raises:
        ValueError: If coercion fails
    """
    if isinstance(expected_type, tuple):
        # Try each type in order
        for t in expected_type:
            try:
                return _coerce_param_type(value, t)
            except (ValueError, TypeError):
                continue
        raise ValueError(f"Cannot coerce {value!r} to any of {expected_type}")

    # Already correct type
    if isinstance(value, expected_type):
        return value

    # Type coercion
    try:
        if expected_type is str:
            return str(value)
        elif expected_type is int:
            if (isinstance(value, str) and value.isdigit()) or isinstance(value, (int, float)):
                return int(value)
        elif expected_type is float:
            if isinstance(value, (str, int, float)):
                return float(value)
        elif expected_type is list:
            if isinstance(value, str):
                # Try to parse as JSON array
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            elif isinstance(value, list):
                return value
        elif expected_type is dict:
            if isinstance(value, str):
                # Try to parse as JSON object
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            elif isinstance(value, dict):
                return value
    except (ValueError, TypeError, json.JSONDecodeError):
        pass

    raise ValueError(
        f"Cannot coerce {value!r} (type {type(value).__name__}) to {expected_type.__name__}"
    )


def _validate_params(params: dict[str, Any], operation: ForgeOperation) -> dict[str, Any]:
    """Validate and coerce parameters against allowlist and types.

    Args:
        params: Raw parameters
        operation: Forge operation to validate against

    Returns:
        Validated and coerced parameters

    Raises:
        ValueError: If validation fails
    """
    # Check depth
    _check_nesting_depth(params)

    # Get allowlist for this operation
    allowed_params = PARAM_ALLOWLISTS.get(operation, set())

    # Validate and coerce
    validated = {}
    for key, value in params.items():
        # Check allowlist
        if allowed_params and key not in allowed_params:
            logger.warning(f"Ignoring unexpected parameter '{key}' for operation {operation}")
            continue

        # Coerce type if specified
        if key in PARAM_TYPES:
            expected_type = PARAM_TYPES[key]
            try:
                value = _coerce_param_type(value, expected_type)  # type: ignore[arg-type]
            except ValueError as e:
                raise ValueError(f"Invalid type for parameter '{key}': {e}") from e

        validated[key] = value

    return validated


def _regex_match_with_timeout(
    pattern: str, text: str, timeout: float = REGEX_TIMEOUT_SEC
) -> re.Match[str] | None:
    """Execute regex match with timeout protection.

    Args:
        pattern: Regex pattern
        text: Text to match
        timeout: Timeout in seconds

    Returns:
        Match object or None

    Raises:
        ValueError: If regex times out (potential ReDoS)
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(re.match, pattern, text)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise ValueError(
                f"Regex matching timed out after {timeout}s (potential ReDoS attack)"
            ) from None


def parse_lang2_string(lang_str: str) -> tuple[str, dict[str, Any]]:
    """Parse a LANG/2 format string into intent and params with security validation.

    Format: EXECUTE intent @app=App {json_params}

    Security measures:
    - Intent length validation (max 100 chars)
    - Params size validation (max 1KB)
    - Regex timeout protection (1s) against ReDoS
    - Depth limit on nested structures (max 5 levels)
    - Type coercion with validation
    - No fallback to unsafe key=value parsing

    Args:
        lang_str: LANG/2 formatted string

    Returns:
        Tuple of (intent, params)

    Raises:
        ValueError: If format is invalid or validation fails
    """
    # Trim and validate length
    lang_str = lang_str.strip()
    if len(lang_str) > (MAX_INTENT_LENGTH + MAX_PARAMS_SIZE):
        raise ValueError(
            f"LANG/2 string exceeds maximum length of "
            f"{MAX_INTENT_LENGTH + MAX_PARAMS_SIZE} characters"
        )

    # Pattern: EXECUTE action.target @app=App {json}
    # Restrict to alphanumeric, dots, underscores for intent
    pattern = r"^EXECUTE\s+([\w.]+)(?:\s+@app=[\w]+)?(?:\s+(.+))?$"

    # Match with timeout protection
    match = _regex_match_with_timeout(pattern, lang_str)

    if not match:
        raise ValueError(
            "Invalid LANG/2 format. Expected: EXECUTE intent [@app=App] [{json_params}]"
        )

    intent = match.group(1)
    params_str = match.group(2)

    # Validate intent length
    if len(intent) > MAX_INTENT_LENGTH:
        raise ValueError(f"Intent exceeds maximum length of {MAX_INTENT_LENGTH} characters")

    # Validate intent format
    if not re.match(r"^[\w]+\.[\w]+$", intent):
        raise ValueError("Intent must follow 'capability.action' format")

    # Parse params
    params: dict[str, Any] = {}
    if params_str:
        # Validate params size
        if len(params_str.encode("utf-8")) > MAX_PARAMS_SIZE:
            raise ValueError(f"Parameters exceed maximum size of {MAX_PARAMS_SIZE} bytes")

        # Only accept valid JSON, no fallback parsing
        try:
            params = json.loads(params_str)
            if not isinstance(params, dict):
                raise ValueError("Parameters must be a JSON object (dict)")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in parameters: {e}") from e

        # Check nesting depth
        _check_nesting_depth(params)

    return intent, params


# Capability descriptions (MODULE LEVEL)
_capability_descriptions = {
    ForgeOperation.CHARACTER_GENERATION: "Generate 3D characters from text descriptions",
    ForgeOperation.IMAGE_TO_CHARACTER: "Generate 3D characters from uploaded images",
    ForgeOperation.ANIMATION_FACIAL: "Generate facial animations (blinks, expressions)",
    ForgeOperation.ANIMATION_GESTURE: "Generate gesture animations (idle, gestures)",
    ForgeOperation.ANIMATION_MOTION: "Generate full-body motion animations from text",
    ForgeOperation.VALIDATION: "Validate generated characters",
    ForgeOperation.CONTENT_SAFETY: "Check content for safety compliance",
}


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/command/forge", tags=["command", "forge"])

    @router.post(
        "/intent",
        response_model=ForgeIntentResponse,
        dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))],  # type: ignore[func-returns-value]
    )
    async def execute_forge_intent(
        request: Request,
        payload: ForgeIntentRequest,
        service: ForgeService = Depends(get_forge_service),
    ) -> ForgeIntentResponse:
        """Execute a Forge operation via intent.

        Accepts either:
        - An intent string (e.g., "character.generate") with params
        - A full LANG/2 string

        This provides a unified interface for all Forge operations,
        aligning with the K OS intent system.

        Args:
            payload: Intent request with either intent+params or lang string

        Returns:
            Standardized ForgeIntentResponse

        Raises:
            HTTPException: If intent is unknown or execution fails

        Example:
            >>> POST /api/forge/intent
            >>> {"intent": "character.generate", "params": {"concept": "warrior"}}

            >>> POST /api/forge/intent
            >>> {"lang": "EXECUTE character.generate @app=Forge {\"concept\": \"ninja\"}"}
        """
        # Build metadata
        forge_meta = build_forge_metadata(request, payload.model_dump())

        # Parse intent
        intent: str
        params: dict[str, Any]

        if payload.lang:
            try:
                intent, params = parse_lang2_string(payload.lang)
                # Merge with any additional params
                params.update(payload.params)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from None
        elif payload.intent:
            intent = payload.intent
            params = payload.params
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'intent' or 'lang' must be provided",
            )

        # Map to capability
        capability = INTENT_MAPPING.get(intent)
        if not capability:
            # Try partial matching
            for key, cap in INTENT_MAPPING.items():
                if intent in key or key in intent:
                    capability = cap
                    break

        if not capability:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown intent: {intent}. Available: {list(INTENT_MAPPING.keys())}",
            )

        # Validate and coerce parameters
        try:
            params = _validate_params(params, capability)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Parameter validation failed: {e}"
            ) from None

        # Build ForgeRequest
        forge_request = ForgeRequest(
            capability=capability,
            params=params,
            quality_mode=params.get("quality_mode", params.get("quality", "preview")),
            export_formats=params.get("export_formats", []),
            metadata=dict(forge_meta),
            correlation_id=payload.correlation_id or forge_meta["correlation_id"],
            idempotency_key=payload.idempotency_key,
        )

        # Execute
        result = await service.execute(forge_request)

        # Emit receipt
        try:
            receipt = emit_forge_receipt(
                action=f"forge.{intent}",
                meta=forge_meta,
                event_name=f"forge.{intent}.completed"
                if result.success
                else f"forge.{intent}.failed",
                event_data={
                    "status": "success" if result.success else "error",
                    "capability": result.capability,
                    "cached": result.cached,
                },
                duration_ms=result.duration_ms,
                status="success" if result.success else "error",
                args=params,
            )
        except Exception as e:
            logger.debug(f"Receipt emission failed: {e}")
            receipt = None

        return ForgeIntentResponse(
            success=result.success,
            capability=result.capability,
            data={**result.data, "receipt": receipt} if receipt else result.data,
            correlation_id=result.correlation_id,
            duration_ms=result.duration_ms,
            cached=result.cached,
            error=result.error,
            error_code=result.error_code,
        )

    @router.get(
        "/capabilities",
        dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))],  # type: ignore[func-returns-value]
    )
    async def list_forge_capabilities() -> dict[str, Any]:
        """List available Forge capabilities and their status.

        Returns:
            Dict with available capabilities and their descriptions
        """
        return {
            "capabilities": [
                {
                    "name": cap.value,
                    "description": _capability_descriptions.get(cap, ""),
                    "intents": [k for k, v in INTENT_MAPPING.items() if v == cap],
                }
                for cap in ForgeOperation
            ],
            "total": len(ForgeOperation),
        }

    return router


__all__ = [
    "MAX_INTENT_LENGTH",
    "MAX_NESTING_DEPTH",
    "MAX_PARAMS_SIZE",
    "REGEX_TIMEOUT_SEC",
    "ForgeIntentRequest",
    "ForgeIntentResponse",
    "_check_nesting_depth",
    "_coerce_param_type",
    "_regex_match_with_timeout",
    "_validate_params",
    "get_router",
    "parse_lang2_string",
]
