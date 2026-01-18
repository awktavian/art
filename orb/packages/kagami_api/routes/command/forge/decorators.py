"""Forge route decorators for reducing boilerplate.

Provides a @forge_route decorator that standardizes:
- Idempotency enforcement
- Metric recording
- Receipt emission
- Error handling
- Response formatting

Usage:
    @router.post("/generate")
    @forge_route("character.generate")
    async def generate_character(request: Request, payload: ForgeGenerateRequest):
        # Just the business logic, no boilerplate
        return await service.generate_character(...)
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
import typing
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, Request
from kagami.forge.exceptions import (
    ModuleInitializationError,
    ModuleNotAvailableError,
)
from kagami.observability.metrics import API_ERRORS

from kagami_api.idempotency import ensure_idempotency
from kagami_api.routes.forge_common import build_forge_metadata, emit_forge_receipt

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def forge_route(
    action: str,
    *,
    emit_receipt: bool = True,
    idempotency_ttl: int = 300,
    require_confirmation_for: list[str] | None = None,
) -> Callable[[F], F]:
    """Decorator for Forge API routes.

    Reduces boilerplate by automatically handling:
    - Idempotency enforcement
    - Timing and metrics
    - Receipt emission
    - Error handling with proper status codes
    - Response standardization

    Args:
        action: Action name for receipts (e.g., "forge.generate")
        emit_receipt: Whether to emit a receipt (default True)
        idempotency_ttl: TTL for idempotency key in seconds
        require_confirmation_for: List of quality modes requiring confirmation

    Returns:
        Decorated route function

    Example:
        @router.post("/generate")
        @forge_route("forge.generate", require_confirmation_for=["final"])
        async def generate(request: Request, ...):
            return {"character": ...}
    """
    require_confirmation_for = require_confirmation_for or []

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract request from args/kwargs
            request: Request | None = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            # Build metadata
            payload_dict = {}
            for key in ("payload", "body"):
                if key in kwargs:
                    val = kwargs[key]
                    if hasattr(val, "model_dump"):
                        payload_dict = val.model_dump()
                    elif isinstance(val, dict):
                        payload_dict = val
                    break

            forge_meta = build_forge_metadata(request, payload_dict)
            correlation_id = forge_meta["correlation_id"]
            t0 = time.perf_counter()

            # Check confirmation requirement
            quality_mode = payload_dict.get("quality_mode", "preview")
            confirm = payload_dict.get("confirm", False)
            if quality_mode in require_confirmation_for and not confirm:
                return {
                    "status": "needs_confirmation",
                    "summary": f"High-cost operation requires confirmation ({quality_mode})",
                    "confirmation_required": True,
                    "quality_mode": quality_mode,
                    "correlation_id": correlation_id,
                }

            # Enforce idempotency
            try:
                if request is not None:
                    await ensure_idempotency(request, ttl_seconds=idempotency_ttl)
            except HTTPException:
                raise
            except Exception:
                pass

            # Inject metadata into kwargs for the handler
            kwargs["_forge_meta"] = forge_meta
            kwargs["_correlation_id"] = correlation_id

            try:
                # Call the actual handler
                result = await func(*args, **kwargs)

                # Calculate duration
                duration_ms = int((time.perf_counter() - t0) * 1000)

                # Emit receipt if enabled
                if emit_receipt:
                    try:
                        receipt = emit_forge_receipt(
                            action=action,
                            meta=forge_meta,
                            event_name=f"{action}.completed",
                            event_data={
                                "status": "success",
                                **_extract_event_data(result),
                            },
                            duration_ms=duration_ms,
                            args=_extract_args(payload_dict),
                        )
                        if isinstance(result, dict):
                            result["receipt"] = receipt
                    except Exception as e:
                        logger.debug(f"Receipt emission failed: {e}")

                # Ensure correlation_id in response
                if isinstance(result, dict) and "correlation_id" not in result:
                    result["correlation_id"] = correlation_id

                return result

            except ModuleNotAvailableError as e:
                _emit_error_receipt(forge_meta, action, str(e), t0)  # type: ignore[arg-type]
                raise HTTPException(status_code=501, detail=str(e)) from None

            except ModuleInitializationError as e:
                _emit_error_receipt(forge_meta, action, str(e), t0)  # type: ignore[arg-type]
                raise HTTPException(status_code=501, detail=str(e)) from None

            except HTTPException:
                raise

            except Exception as e:
                logger.error(f"Forge route {action} failed: {e}", exc_info=True)
                _record_error(action, e)
                _emit_error_receipt(forge_meta, action, str(e), t0)  # type: ignore[arg-type]
                raise HTTPException(status_code=500, detail=str(e)) from None

        # IMPORTANT: FastAPI evaluates endpoint annotations for DI/OpenAPI.
        # Because this wrapper lives in this module, its `__globals__` does not contain
        # the endpoint module's symbols. With `from __future__ import annotations`,
        # annotations become strings/ForwardRefs and can fail to resolve during OpenAPI
        # generation (e.g., ForgeGenerateRequest).
        #
        # Resolve annotations against the original function's globals and attach them to
        # the wrapper so FastAPI sees fully-defined types.
        try:
            resolved_hints = typing.get_type_hints(func, include_extras=True)
            wrapper.__annotations__ = resolved_hints

            # Ensure inspect.signature() (used by FastAPI) sees resolved annotations even
            # when it evaluates them in this module's global namespace.
            sig = inspect.signature(func)
            params = []
            for p in sig.parameters.values():
                if p.name in resolved_hints:
                    params.append(p.replace(annotation=resolved_hints[p.name]))
                else:
                    params.append(p)
            wrapper.__signature__ = sig.replace(  # type: ignore[attr-defined]
                parameters=params,
                return_annotation=resolved_hints.get("return", sig.return_annotation),
            )
        except Exception:
            # Best-effort: if resolution fails, keep original annotations.
            pass

        return wrapper  # type: ignore

    return decorator


def _extract_event_data(result: Any) -> dict[str, Any]:
    """Extract relevant data for receipt event."""
    if isinstance(result, dict):
        return {
            k: v
            for k, v in result.items()
            if k
            in (
                "status",
                "request_id",
                "concept",
                "quality_mode",
                "cached",
                "animation_type",
            )
        }
    return {}


def _extract_args(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract args for receipt."""
    return {
        k: v
        for k, v in payload.items()
        if k
        in (
            "concept",
            "quality_mode",
            "export_formats",
            "character_id",
            "duration",
            "animation_type",
        )
    }


def _emit_error_receipt(
    meta: dict[str, Any],
    action: str,
    error: str,
    start_time: float,
) -> None:
    """Emit error receipt."""
    try:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        emit_forge_receipt(
            action=action,
            meta=meta,  # type: ignore[arg-type]
            event_name=f"{action}.failed",
            event_data={"status": "error", "error": error},
            duration_ms=duration_ms,
            status="error",
            args={},
        )
    except Exception:
        pass


def _record_error(action: str, error: Exception) -> None:
    """Record error metrics."""
    try:
        API_ERRORS.labels(
            endpoint=action,
            error_type=type(error).__name__,
        ).inc()
    except Exception:
        pass


__all__ = ["forge_route"]
