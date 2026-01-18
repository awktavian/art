from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from fastapi import HTTPException
from pydantic import BaseModel

F = TypeVar("F", bound=Callable[..., Any])


def not_found(resource: str, identifier: Any | None = None) -> HTTPException:
    """Create a 404 Not Found HTTP exception."""
    msg = f"{resource} not found"
    if identifier is not None:
        msg += f" (id={identifier})"
    return HTTPException(status_code=404, detail=msg)


def bad_request(message: str = "Bad request") -> HTTPException:
    """Create a 400 Bad Request HTTP exception."""
    return HTTPException(status_code=400, detail=message)


def unauthorized(message: str = "Authentication required") -> HTTPException:
    """Create a 401 Unauthorized HTTP exception."""
    return HTTPException(status_code=401, detail=message)


def forbidden(message: str = "Forbidden") -> HTTPException:
    """Create a 403 Forbidden HTTP exception."""
    return HTTPException(status_code=403, detail=message)


def unprocessable_entity(message: str = "Unprocessable entity") -> HTTPException:
    """Create a 422 Unprocessable Entity HTTP exception."""
    return HTTPException(status_code=422, detail=message)


def conflict(message: str = "Conflict") -> HTTPException:
    """Create a 409 Conflict HTTP exception."""
    return HTTPException(status_code=409, detail=message)


def service_unavailable(message: str = "Service unavailable") -> HTTPException:
    """Create a 503 Service Unavailable HTTP exception."""
    return HTTPException(status_code=503, detail=message)


def gateway_timeout(message: str = "Gateway timeout") -> HTTPException:
    """Create a 504 Gateway Timeout HTTP exception."""
    return HTTPException(status_code=504, detail=message)


def require_fields(obj: Any, *fields: str) -> None:
    """Ensure obj has all fields; works with dict or Pydantic models."""
    data: dict[str, Any]
    if isinstance(obj, BaseModel):
        data = obj.model_dump()
    elif isinstance(obj, dict):
        data = obj
    else:
        raise HTTPException(status_code=400, detail="Invalid input type") from None

    missing = [f for f in fields if f not in data or data.get(f) in (None, "")]
    if missing:
        raise HTTPException(
            status_code=400, detail=f"Missing required fields: {', '.join(missing)}"
        )


def ensure_exists(obj: Any, resource: str, identifier: Any | None = None) -> None:
    """Return obj if truthy else raise not_found."""
    if obj is None:
        raise not_found(resource, identifier)
    return obj  # type: ignore[no-any-return]


def handle_route_errors(operation_name: str | Callable[..., Any] | None = None) -> Callable[[F], F]:
    """Decorator to handle route errors and convert to HTTPException.

    Can be used with or without arguments:
        @handle_route_errors
        async def my_route(): ...

        @handle_route_errors("my_operation")
        async def my_route(): ...
    """
    import asyncio

    def decorator(func: F) -> F:
        # Determine the operation name for logging
        op_name = operation_name if isinstance(operation_name, str) else func.__name__

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return await func(*args, **kwargs)
                except HTTPException:
                    raise
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"{op_name}: {e!s}") from e

            return cast(F, async_wrapper)
        else:

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return func(*args, **kwargs)
                except HTTPException:
                    raise
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"{op_name}: {e!s}") from e

            return cast(F, sync_wrapper)

    # Support both @handle_route_errors and @handle_route_errors("name")
    if callable(operation_name):
        # Called as @handle_route_errors without parens
        func = operation_name
        operation_name = None
        return decorator(func)
    else:
        # Called as @handle_route_errors() or @handle_route_errors("name")
        return decorator
