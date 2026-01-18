from __future__ import annotations

"""Lightweight, optional execution tracing for K os with OpenTelemetry bridge.

Two modes of operation (auto-selected):
1) Built-in lightweight logger-based tracing, enabled via KAGAMI_TRACE.
2) OpenTelemetry-backed tracing when OTEL is enabled and SDK is available.

Env flags:
- KAGAMI_TRACE=[1|true|yes|on] enables lightweight tracing.
- OTEL_ENABLED=[1|true|yes|on] switches trace_span to emit OpenTelemetry spans
  if opentelemetry SDK is importable. Attributes are attached to spans.
"""
import asyncio
import logging
import os
import time
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from functools import wraps
from typing import Any

_TRACE_ENABLED = (os.getenv("KAGAMI_TRACE") or "0").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

_OTEL_ENABLED = (os.getenv("OTEL_ENABLED") or "0").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

try:
    # Lazy optional import; kept local to avoid hard dependency
    from opentelemetry import trace as _otel_trace

    _OTEL_AVAILABLE = True
except Exception:
    _OTEL_AVAILABLE = False


def is_tracing_enabled() -> bool:
    return _TRACE_ENABLED


class _TraceSpan(AbstractAsyncContextManager["_TraceSpan"], AbstractContextManager["_TraceSpan"]):
    def __init__(self, name: str, attrs: dict[str, Any] | None = None):
        self.name = name
        self.attrs = attrs or {}
        self._start = 0.0
        self._logger = logging.getLogger("kagami.trace")
        # Optional OpenTelemetry context manager span if OTEL is active
        self._otel_cm: object | None = None

    def __enter__(self) -> Any:
        # Prefer OpenTelemetry when enabled and available
        if _OTEL_ENABLED and _OTEL_AVAILABLE:
            try:
                self._otel_cm = _otel_trace.get_tracer("kagami").start_as_current_span(self.name)
                cm = None
                try:
                    enter_fn = getattr(self._otel_cm, "__enter__", None)
                    if callable(enter_fn):
                        cm = enter_fn()
                except Exception:
                    cm = None
                # Attach attributes if provided
                if cm is not None and hasattr(cm, "set_attribute"):
                    for k, v in (self.attrs or {}).items():
                        try:
                            cm.set_attribute(k, v)
                        except Exception:
                            pass
            except Exception:
                # Fall back to lightweight tracing if OTel span creation fails
                self._otel_cm = None
        if _TRACE_ENABLED and getattr(self, "_otel_cm", None) is None:
            self._start = time.perf_counter()
            try:
                self._logger.debug(f"trace.start name={self.name} attrs={self.attrs}")
            except Exception:
                pass
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:  # type: ignore[exit-return]
        # Close OTel span if used
        cm = getattr(self, "_otel_cm", None)
        if cm is not None:
            try:
                exit_fn = getattr(cm, "__exit__", None)
                if callable(exit_fn):
                    exit_fn(exc_type, exc, tb)
            except Exception:
                pass
            return False
        if _TRACE_ENABLED:
            try:
                elapsed_ms = (time.perf_counter() - self._start) * 1000.0
                status = "error" if exc is not None else "ok"
                self._logger.debug(
                    f"trace.end name={self.name} status={status} ms={elapsed_ms:.2f} attrs={self.attrs}"
                )
            except Exception:
                pass
        return False

    async def __aenter__(self) -> Any:
        # Reuse sync enter to avoid duplication
        return self.__enter__()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:  # type: ignore[return]
        # Reuse sync exit for symmetry
        self.__exit__(exc_type, exc, tb)


def trace_span(name: str, attrs: dict[str, Any] | None = None) -> _TraceSpan:
    """Create an async/sync context manager trace span.

    Usage:
        with trace_span("operation", {"key": "value"}):
            ...

        async with trace_span("operation"):
            ...
    """

    return _TraceSpan(name, attrs)


def traced(name: str | None = None) -> Any:
    """Decorator to trace function execution (sync or async)."""

    def _decorator(fn: Any) -> Any:
        span_name = name or fn.__name__

        if asyncio.iscoroutinefunction(fn):

            @wraps(fn)
            async def _aw(*args: Any, **kwargs: Any) -> Any:
                if not _TRACE_ENABLED:
                    return await fn(*args, **kwargs)
                async with trace_span(span_name):
                    return await fn(*args, **kwargs)

            return _aw
        else:

            @wraps(fn)
            def _w(*args: Any, **kwargs: Any) -> Any:
                if not _TRACE_ENABLED:
                    return fn(*args, **kwargs)
                with trace_span(span_name):
                    return fn(*args, **kwargs)

            return _w

    return _decorator


__all__ = ["is_tracing_enabled", "trace_span", "traced"]
